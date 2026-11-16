import asyncio
import os
import time
from datetime import datetime
from threading import Thread, Event
from sqlalchemy.orm import Session
from database import SessionLocal, Campaign, CallRecord, Account
from vobiz_service import trigger_vobiz_outbound_call, hangup_vobiz_call

# Global thread-safe controllers for running campaigns
active_campaign_threads = {}
campaign_stop_events = {}
campaign_pause_events = {}


class CampaignWorker(Thread):
    def __init__(self, campaign_id: int, delay_between_calls: float = 0.8):
        super().__init__(daemon=True)
        self.campaign_id = campaign_id
        self.delay_between_calls = delay_between_calls
        self.stop_event = Event()
        self.pause_event = Event()

    def run(self):
        print(f"[*] Starting Auto-Dialer Worker for Campaign #{self.campaign_id}")
        db = SessionLocal()
        try:
            campaign = db.query(Campaign).filter(Campaign.id == self.campaign_id).first()
            if not campaign:
                print(f"[!] Campaign #{self.campaign_id} not found.")
                return

            campaign.status = "running"
            db.commit()

            while not self.stop_event.is_set():
                # Handle pause
                if self.pause_event.is_set():
                    time.sleep(1.0)
                    continue

                # Refresh DB session
                db.expire_all()
                campaign = db.query(Campaign).filter(Campaign.id == self.campaign_id).first()
                if not campaign or campaign.status in ["paused", "stopped"]:
                    break

                account = db.query(Account).filter(Account.id == campaign.account_id).first()
                if not account or account.credits <= 0:
                    print(f"[!] Campaign #{self.campaign_id} paused: OUT OF CREDITS.")
                    campaign.status = "paused"
                    db.commit()
                    break

                # Fetch next pending call
                record = (
                    db.query(CallRecord)
                    .filter(CallRecord.campaign_id == self.campaign_id, CallRecord.status == "pending")
                    .order_by(CallRecord.id.asc())
                    .first()
                )

                if not record:
                    print(f"[✓] Campaign #{self.campaign_id} finished all numbers!")
                    campaign.status = "completed"
                    db.commit()
                    break

                # Update call record to dialing
                record.status = "dialing"
                record.called_at = datetime.utcnow()
                db.commit()

                print(f"\n[AUTO-DIALER] Dialing {record.phone_number} (Current Credits: {account.credits:.1f})...")

                # Execute live call with audio streaming and interactive DTMF
                from run_live_call import execute_live_call
                token_deducted = 0.3
                c_course = record.course_type or (campaign.course_type if campaign else "bca_internship")
                c_lang = record.language or (campaign.language if campaign else "en")
                try:
                    call_res = asyncio.run(execute_live_call(
                        target_phone=record.phone_number,
                        record_id=record.id,
                        course_type=c_course,
                        language=c_lang
                    ))
                    db.refresh(record)

                    # Determine token deduction: 1.0 for answered, 0.3 for unanswered/failed/declined
                    is_answered = (call_res.get("success") is True) or (record.status in ["answered", "completed"])
                    token_deducted = 1.0 if is_answered else 0.3

                    if is_answered:
                        print(f" [✓] Call answered & completed for {record.phone_number} (Deduction: 1.0 Token)")
                    else:
                        print(f" [!] Call not answered/declined ({record.status}: {record.response_note}). Deduction: 0.3 Token")
                except Exception as e:
                    print(f" [✕] Call failed: {e}")
                    record.status = "failed"
                    record.response_note = f"Call Error: {e}"
                    token_deducted = 0.3

                # Deduct token (1.0 if connected, 0.3 if failed/unanswered/declined)
                record.tokens_used = token_deducted
                account.credits = round(max(0.0, float(account.credits) - token_deducted), 2)
                account.total_calls_made += 1
                db.commit()

                print(f" [TOKEN LEDGER] Remaining Credits: {account.credits:.1f} | Token Cost: {token_deducted} 🪙")

                # Update completed counter
                completed_count = (
                    db.query(CallRecord)
                    .filter(CallRecord.campaign_id == self.campaign_id, CallRecord.status != "pending")
                    .count()
                )
                campaign.completed_numbers = completed_count
                db.commit()

                # Clean delay between calls (e.g. 2.5s) to allow telecom line to clear
                print(f" [*] Waiting {self.delay_between_calls}s before dialing next number...")
                for _ in range(int(self.delay_between_calls * 10)):
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.1)

        except Exception as e:
            print(f"[ERROR in Campaign Worker #{self.campaign_id}]: {e}")
        finally:
            campaign = db.query(Campaign).filter(Campaign.id == self.campaign_id).first()
            if campaign and campaign.status == "running":
                campaign.status = "paused"
                db.commit()
            db.close()
            print(f"[*] Auto-Dialer Worker for Campaign #{self.campaign_id} stopped.")


def start_campaign_dialer(campaign_id: int, delay_between_calls: float = 0.8, course_type: str = None, language: str = None) -> dict:
    db = SessionLocal()
    try:
        c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if c:
            if course_type:
                c.course_type = course_type
            if language:
                c.language = language
            db.commit()

            update_data = {}
            if course_type:
                update_data["course_type"] = course_type
            if language:
                update_data["language"] = language
            if update_data:
                db.query(CallRecord).filter(
                    CallRecord.campaign_id == campaign_id,
                    CallRecord.status == "pending"
                ).update(update_data)
                db.commit()
    finally:
        db.close()

    if campaign_id in active_campaign_threads:
        worker = active_campaign_threads[campaign_id]
        if worker.is_alive():
            if worker.pause_event.is_set():
                worker.pause_event.clear()
                # Update DB
                db = SessionLocal()
                c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
                if c:
                    c.status = "running"
                    db.commit()
                db.close()
                return {"status": "resumed", "campaign_id": campaign_id}
            return {"status": "already_running", "campaign_id": campaign_id}

    worker = CampaignWorker(campaign_id=campaign_id, delay_between_calls=delay_between_calls)
    active_campaign_threads[campaign_id] = worker
    worker.start()
    return {"status": "started", "campaign_id": campaign_id}


def pause_campaign_dialer(campaign_id: int) -> dict:
    if campaign_id in active_campaign_threads:
        worker = active_campaign_threads[campaign_id]
        worker.pause_event.set()
        db = SessionLocal()
        c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if c:
            c.status = "paused"
            db.commit()
        db.close()
        return {"status": "paused", "campaign_id": campaign_id}
    return {"status": "not_running", "campaign_id": campaign_id}


def stop_campaign_dialer(campaign_id: int) -> dict:
    if campaign_id in active_campaign_threads:
        worker = active_campaign_threads[campaign_id]
        worker.stop_event.set()
        worker.pause_event.clear()
        del active_campaign_threads[campaign_id]
        db = SessionLocal()
        c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if c:
            c.status = "stopped"
            db.commit()
        db.close()
        return {"status": "stopped", "campaign_id": campaign_id}
    return {"status": "not_running", "campaign_id": campaign_id}
