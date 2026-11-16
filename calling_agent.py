import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import os
import io
import csv
import json
import time
import math
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, UploadFile, File, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from sqlalchemy.orm import Session

from database import init_db, get_db, SessionLocal, Account, Campaign, CallRecord
from dialer_engine import start_campaign_dialer, pause_campaign_dialer, stop_campaign_dialer
from vobiz_service import get_vobiz_account_details

load_dotenv()

# Initialize DB tables and seed default accounts
init_db()

app = FastAPI(title="Vobiz Automated Calling & Response Tracker")

# Directories
BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR = BASE_DIR / "templates"
EXPORTS_DIR = BASE_DIR / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

# Mount audio directory
app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")

SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://localhost:8000").rstrip("/")
VOBIZ_PER_MINUTE_RATE = float(os.getenv("VOBIZ_PER_MINUTE_RATE", 0.45))  # INR 0.45 carrier rate
VOBIZ_OUTBOUND_NUMBER = os.getenv("VOBIZ_OUTBOUND_NUMBER", "+917965853227")


# Pydantic models
class CreditUpdateModel(BaseModel):
    credits: float

class CreditAddModel(BaseModel):
    amount: float

class WalletRechargeModel(BaseModel):
    amount: float


# ==========================================
# 1. FRONTEND DASHBOARDS (SEPARATE USER & ADMIN)
# ==========================================
@app.get("/", response_class=HTMLResponse)
def user_portal():
    """Client / User Interface: Upload 30k numbers, auto-dialer, credit view, response logs."""
    html_file = TEMPLATES_DIR / "user.html"
    if html_file.exists():
        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>User portal template not found.</h1>"


@app.get("/admin", response_class=HTMLResponse)
def admin_portal():
    """Dedicated Admin Panel: Vobiz wholesale balance, carrier cost ledger, client credit allocation."""
    html_file = TEMPLATES_DIR / "admin.html"
    if html_file.exists():
        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Admin portal template not found.</h1>"



# ==========================================
# 2. EXCEL / CSV UPLOAD (Handles 30,000+ numbers)
# ==========================================
@app.post("/api/campaign/upload")
async def upload_campaign_file(
    file: UploadFile = File(...),
    course_type: str = "bca_internship",
    language: str = "en",
    db: Session = Depends(get_db)
):
    filename = file.filename or "uploaded_numbers"
    contents = await file.read()

    # Get client account
    account = db.query(Account).filter(Account.role == "client").first()
    if not account:
        account = Account(name="Client Account", role="client", credits=30000)
        db.add(account)
        db.commit()
        db.refresh(account)

    # Create new Campaign
    campaign_name = f"Campaign - {Path(filename).stem} ({datetime.now().strftime('%d %b %H:%M')})"
    campaign = Campaign(
        account_id=account.id,
        name=campaign_name,
        file_name=filename,
        course_type=course_type,
        language=language,
        total_numbers=0,
        status="idle"
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    records_to_insert = []
    
    # Parse CSV or Excel
    if filename.lower().endswith(".csv"):
        text_data = contents.decode("utf-8", errors="ignore")
        reader = csv.reader(io.StringIO(text_data))
        headers = next(reader, None)
        
        phone_col = 0
        name_col = None
        if headers:
            for idx, h in enumerate(headers):
                h_clean = h.strip().lower()
                if any(x in h_clean for x in ["phone", "mobile", "contact", "number", "tel"]):
                    phone_col = idx
                elif any(x in h_clean for x in ["name", "customer", "lead", "client"]):
                    name_col = idx

        for row in reader:
            if not row or len(row) <= phone_col:
                continue
            raw_phone = str(row[phone_col]).strip()
            if not raw_phone or not any(char.isdigit() for char in raw_phone):
                continue
            cust_name = str(row[name_col]).strip() if name_col is not None and len(row) > name_col else ""
            
            # Format phone
            cleaned_phone = raw_phone.replace(" ", "").replace("-", "")
            if not cleaned_phone.startswith("+"):
                if len(cleaned_phone) == 10:
                    cleaned_phone = "+91" + cleaned_phone
                else:
                    cleaned_phone = "+" + cleaned_phone

            records_to_insert.append({
                "campaign_id": campaign.id,
                "phone_number": cleaned_phone,
                "customer_name": cust_name,
                "course_type": course_type,
                "language": language,
                "status": "pending",
                "dtmf_digit": "",
                "audio_flow": "",
                "response_note": "Queued",
                "duration_sec": 0.0,
                "carrier_cost_inr": 0.0,
                "created_at": datetime.utcnow()
            })

    else:
        # Excel .xlsx / .xls
        wb = openpyxl.load_workbook(io.BytesIO(contents), read_only=True, data_only=True)
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        headers = next(rows, None)

        phone_col = 0
        name_col = None
        if headers:
            for idx, h in enumerate(headers):
                if not h:
                    continue
                h_clean = str(h).strip().lower()
                if any(x in h_clean for x in ["phone", "mobile", "contact", "number", "tel"]):
                    phone_col = idx
                elif any(x in h_clean for x in ["name", "customer", "lead", "client"]):
                    name_col = idx

        for row in rows:
            if not row or len(row) <= phone_col:
                continue
            raw_val = row[phone_col]
            if raw_val is None:
                continue
            raw_phone = str(raw_val).strip().replace(".0", "")
            if not raw_phone or not any(char.isdigit() for char in raw_phone):
                continue
            cust_name = str(row[name_col]).strip() if name_col is not None and len(row) > name_col and row[name_col] else ""

            cleaned_phone = raw_phone.replace(" ", "").replace("-", "")
            if not cleaned_phone.startswith("+"):
                if len(cleaned_phone) == 10:
                    cleaned_phone = "+91" + cleaned_phone
                else:
                    cleaned_phone = "+" + cleaned_phone

            records_to_insert.append({
                "campaign_id": campaign.id,
                "phone_number": cleaned_phone,
                "customer_name": cust_name,
                "course_type": course_type,
                "language": language,
                "status": "pending",
                "dtmf_digit": "",
                "audio_flow": "",
                "response_note": "Queued",
                "duration_sec": 0.0,
                "carrier_cost_inr": 0.0,
                "created_at": datetime.utcnow()
            })
        wb.close()

    # Bulk insert for speed (up to 30,000+ records)
    if records_to_insert:
        db.bulk_insert_mappings(CallRecord, records_to_insert)
        campaign.total_numbers = len(records_to_insert)
        db.commit()

    return {
        "success": True,
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "course_type": campaign.course_type,
        "language": campaign.language,
        "total_numbers": len(records_to_insert)
    }


# ==========================================
# 3. AUTO-DIALER CONTROLS
# ==========================================
@app.post("/api/campaign/{campaign_id}/start")
async def start_campaign(campaign_id: int, request: Request):
    delay = float(request.query_params.get("delay", 0.8))
    course_type = request.query_params.get("course_type", None)
    language = request.query_params.get("language", None)

    try:
        body = await request.json()
        if isinstance(body, dict):
            delay = float(body.get("delay", delay))
            course_type = body.get("course_type", course_type)
            language = body.get("language", language)
    except Exception:
        pass

    res = start_campaign_dialer(campaign_id, delay_between_calls=delay, course_type=course_type, language=language)
    return res

@app.post("/api/campaign/{campaign_id}/pause")
def pause_campaign(campaign_id: int):
    res = pause_campaign_dialer(campaign_id)
    return res

@app.post("/api/campaign/{campaign_id}/stop")
def stop_campaign(campaign_id: int):
    res = stop_campaign_dialer(campaign_id)
    return res

class CampaignConfigModel(BaseModel):
    course_type: str = "bca_internship"
    language: str = "en"

@app.post("/api/campaign/{campaign_id}/config")
def update_campaign_config(campaign_id: int, config: CampaignConfigModel, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.course_type = config.course_type
    campaign.language = config.language
    db.query(CallRecord).filter(
        CallRecord.campaign_id == campaign_id,
        CallRecord.status == "pending"
    ).update({
        "course_type": config.course_type,
        "language": config.language
    })
    db.commit()
    return {"status": "ok", "course_type": campaign.course_type, "language": campaign.language}


# ==========================================
# 4. CAMPAIGN STATUS & RESPONSE LOGS
# ==========================================
@app.get("/api/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    """Returns all campaigns so the frontend can display a campaign switcher or auto-select latest."""
    campaigns = db.query(Campaign).order_by(Campaign.id.desc()).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "file_name": c.file_name,
            "course_type": c.course_type or "bca_internship",
            "language": c.language or "en",
            "total_numbers": c.total_numbers,
            "completed_numbers": c.completed_numbers,
            "status": c.status,
            "created_at": c.created_at.strftime("%d %b %H:%M") if c.created_at else ""
        }
        for c in campaigns
    ]


@app.get("/api/campaign/{campaign_id}/status")
def get_campaign_status(campaign_id: str, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.role == "client").first()
    credits_left = account.credits if account else 30000.0
    total_calls_made = account.total_calls_made if account else 0

    if campaign_id == "all":
        # Aggregate view of ALL campaigns
        all_records = db.query(CallRecord).order_by(CallRecord.id.desc()).all()
        records = all_records[:200]
        total_records = len(all_records)
        completed_records = sum(1 for r in all_records if r.status in ["answered", "completed", "failed", "busy", "no-answer"])
        answered_count = sum(1 for r in all_records if r.status in ["answered", "completed"])
        response_count = sum(1 for r in all_records if r.dtmf_digit != "")
        total_cost_inr = sum(r.carrier_cost_inr or 0.0 for r in all_records)
        unanswered_count = sum(1 for r in all_records if r.status in ["no-answer", "busy", "failed"])

        return {
            "campaign": {
                "id": "all",
                "name": "All Campaigns (All Calls)",
                "status": "active",
                "course_type": "all",
                "language": "all",
                "file_name": "Combined Historical & Live",
                "created_at": "All Time"
            },
            "credits": round(float(credits_left), 2),
            "total_calls_made": total_calls_made,
            "total_records": total_records,
            "completed_records": completed_records,
            "answered_count": answered_count,
            "unanswered_count": unanswered_count,
            "response_count": response_count,
            "total_cost_inr": round(total_cost_inr, 2),
            "records": [
                {
                    "id": r.id,
                    "phone_number": r.phone_number,
                    "customer_name": r.customer_name,
                    "course_type": r.course_type or "bca_internship",
                    "language": r.language or "en",
                    "status": r.status,
                    "dtmf_digit": r.dtmf_digit,
                    "response_note": r.response_note,
                    "duration_sec": r.duration_sec,
                    "carrier_cost_inr": r.carrier_cost_inr,
                    "tokens_used": round(r.tokens_used, 1) if (r.tokens_used and r.tokens_used > 0) else (1.0 if r.status in ["answered", "completed"] else 0.3 if r.status not in ["pending", "dialing"] else 0.0),
                    "called_at": r.called_at.strftime("%H:%M:%S") if r.called_at else ""
                }
                for r in records
            ]
        }

    # Otherwise fetch specific or latest campaign
    campaign = None
    if campaign_id in ["latest", "0", "", "undefined"]:
        campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()
    else:
        try:
            cid = int(campaign_id)
            campaign = db.query(Campaign).filter(Campaign.id == cid).first()
        except ValueError:
            campaign = None

    if not campaign:
        campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()

    if not campaign:
        return {
            "campaign": None,
            "credits": 30000.0,
            "total_calls_made": 0,
            "total_records": 0,
            "completed_records": 0,
            "answered_count": 0,
            "unanswered_count": 0,
            "response_count": 0,
            "total_cost_inr": 0.0,
            "records": []
        }

    records = (
        db.query(CallRecord)
        .filter(CallRecord.campaign_id == campaign.id)
        .order_by(CallRecord.id.desc())
        .limit(200)
        .all()
    )

    all_records_query = db.query(CallRecord).filter(CallRecord.campaign_id == campaign.id)
    total_records = all_records_query.count()
    completed_records = all_records_query.filter(CallRecord.status.in_(["answered", "completed", "failed", "busy", "no-answer"])).count()
    answered_count = all_records_query.filter(CallRecord.status.in_(["answered", "completed"])).count()
    response_count = all_records_query.filter(CallRecord.dtmf_digit != "").count()

    all_records = all_records_query.all()
    total_cost_inr = sum(r.carrier_cost_inr or 0.0 for r in all_records)
    unanswered_count = sum(1 for r in all_records if r.status in ["no-answer", "busy", "failed"])

    return {
        "campaign": {
            "id": campaign.id,
            "name": campaign.name,
            "status": campaign.status,
            "course_type": campaign.course_type or "bca_internship",
            "language": campaign.language or "en",
            "file_name": campaign.file_name,
            "created_at": campaign.created_at.strftime("%Y-%m-%d %H:%M") if campaign.created_at else ""
        },
        "credits": round(float(credits_left), 2) if credits_left is not None else 30000.0,
        "total_calls_made": total_calls_made,
        "total_records": total_records,
        "completed_records": completed_records,
        "answered_count": answered_count,
        "unanswered_count": unanswered_count,
        "response_count": response_count,
        "total_cost_inr": round(total_cost_inr, 2),
        "records": [
            {
                "id": r.id,
                "phone_number": r.phone_number,
                "customer_name": r.customer_name,
                "course_type": r.course_type or "bca_internship",
                "language": r.language or "en",
                "status": r.status,
                "dtmf_digit": r.dtmf_digit,
                "response_note": r.response_note,
                "duration_sec": r.duration_sec,
                "carrier_cost_inr": r.carrier_cost_inr,
                "tokens_used": round(r.tokens_used, 1) if (r.tokens_used and r.tokens_used > 0) else (1.0 if r.status in ["answered", "completed"] else 0.3 if r.status not in ["pending", "dialing"] else 0.0),
                "called_at": r.called_at.strftime("%H:%M:%S") if r.called_at else ""
            }
            for r in records
        ]
    }


# ==========================================
# 5. EXPORT ANNOTATED RESPONSES TO EXCEL (.xlsx)
# ==========================================
@app.get("/api/campaign/{campaign_id}/export-excel")
def export_campaign_excel(campaign_id: str, db: Session = Depends(get_db)):
    if campaign_id == "all":
        records = db.query(CallRecord).order_by(CallRecord.id.desc()).all()
        file_label = "all_campaigns"
    elif campaign_id in ["latest", "0", ""]:
        campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="No campaigns found")
        records = db.query(CallRecord).filter(CallRecord.campaign_id == campaign.id).order_by(CallRecord.id.asc()).all()
        file_label = f"campaign_{campaign.id}"
    else:
        try:
            cid = int(campaign_id)
            campaign = db.query(Campaign).filter(Campaign.id == cid).first()
        except ValueError:
            campaign = None
        if not campaign:
            campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        records = db.query(CallRecord).filter(CallRecord.campaign_id == campaign.id).order_by(CallRecord.id.asc()).all()
        file_label = f"campaign_{campaign.id}"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Call Responses"

    # Styling
    header_fill = PatternFill(start_color="DB8B70", end_color="DB8B70", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    center_align = Alignment(horizontal="center", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")

    headers = [
        "S.No",
        "Phone Number",
        "Customer Name",
        "Program / Course",
        "Language",
        "Call Status",
        "Tokens Deducted (🪙)",
        "DTMF Key Pressed",
        "Annotated Response",
        "Duration (Seconds)",
        "Vobiz Cost (INR)",
        "Call UUID",
        "Timestamp"
    ]
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align

    course_labels = {
        "bca_internship": "BCA Internship",
        "distance_education": "Distance Education",
        "deep_courses": "DEEP Courses"
    }

    for idx, r in enumerate(records, start=1):
        t_used = round(r.tokens_used, 1) if (r.tokens_used and r.tokens_used > 0) else (1.0 if r.status in ["answered", "completed"] else 0.3 if r.status not in ["pending", "dialing"] else 0.0)
        c_name = course_labels.get(r.course_type, r.course_type or "BCA Internship")
        lang_name = (r.language or "en").upper()
        ws.append([
            idx,
            r.phone_number,
            r.customer_name or "—",
            c_name,
            lang_name,
            r.status.upper(),
            f"{t_used} Tokens" if r.status not in ["pending", "dialing"] else "Pending",
            r.dtmf_digit or "—",
            r.response_note or "—",
            r.duration_sec,
            round(r.carrier_cost_inr, 2),
            r.vobiz_call_uuid or "—",
            r.called_at.strftime("%Y-%m-%d %H:%M:%S") if r.called_at else "—"
        ])

    # Auto column width
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    export_path = EXPORTS_DIR / f"campaign_{campaign_id}_responses.xlsx"
    wb.save(export_path)

    return FileResponse(
        path=str(export_path),
        filename=f"annotated_responses_campaign_{campaign_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ==========================================
# 6. ADMIN & CREDIT MANAGEMENT
# ==========================================
@app.get("/api/vobiz/account")
def vobiz_account_info():
    """Fetches real-time live account cash credits balance and CDR directly from Vobiz API."""
    info = get_vobiz_account_details()
    info["caller_id"] = VOBIZ_OUTBOUND_NUMBER
    return info

@app.post("/api/account/credits")
def update_credits(data: CreditUpdateModel, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.role == "client").first()
    if account:
        account.credits = data.credits
        db.commit()
        return {"status": "ok", "credits": account.credits}
    return {"status": "error", "message": "Account not found"}

@app.post("/api/account/credits/add")
def add_credits(data: CreditAddModel, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.role == "client").first()
    if account:
        account.credits += data.amount
        db.commit()
        return {"status": "ok", "credits": account.credits}
    return {"status": "error", "message": "Account not found"}


# ==========================================
# 7. TELEPHONY WEBHOOKS (Vobiz Interactive Call Flow)
# ==========================================
@app.api_route("/call/incoming", methods=["GET", "POST"])
async def incoming_call(request: Request, db: Session = Depends(get_db)):
    """
    Triggered when outbound call answers or connects.
    Plays the configured course & language audio and awaits DTMF 1.
    """
    form = {}
    if request.method == "POST":
        try:
            form = await request.form()
        except Exception:
            pass

    to_num = str(form.get("To", "")).strip()
    call_uuid = str(form.get("CallUUID", form.get("call_uuid", ""))).strip()

    record = None
    if to_num or call_uuid:
        cleaned_to = to_num.replace(" ", "").replace("-", "")
        record = (
            db.query(CallRecord)
            .filter((CallRecord.phone_number.contains(cleaned_to[-10:])) | (CallRecord.vobiz_call_uuid == call_uuid))
            .order_by(CallRecord.id.desc())
            .first()
        )

    course_type = record.course_type or "bca_internship" if record else "bca_internship"
    lang = record.language or "en" if record else "en"

    prompt_file = f"{course_type}_{lang}.wav"
    if not (AUDIO_DIR / prompt_file).exists():
        prompt_file = f"{course_type}_en.wav"
        if not (AUDIO_DIR / prompt_file).exists():
            prompt_file = "welcome.wav"

    timeout_file = f"timeout_{lang}.wav"
    if not (AUDIO_DIR / timeout_file).exists():
        timeout_file = "timeout.wav"

    if record:
        record.status = "answered"
        record.response_note = f"Call answered. Playing {course_type} ({lang.upper()})"
        record.audio_flow = prompt_file
        if call_uuid:
            record.vobiz_call_uuid = call_uuid
        db.commit()

    prompt_audio_url = f"{SERVER_BASE_URL}/audio/{prompt_file}"
    timeout_audio_url = f"{SERVER_BASE_URL}/audio/{timeout_file}"
    dtmf_action_url = f"{SERVER_BASE_URL}/call/dtmf"

    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="{dtmf_action_url}" method="POST" inputType="dtmf" numDigits="1" timeout="6">
        <Play>{prompt_audio_url}</Play>
    </Gather>
    <Play>{timeout_audio_url}</Play>
    <Hangup/>
</Response>"""
    return Response(content=xml_content.strip(), media_type="application/xml")


@app.api_route("/call/dtmf", methods=["GET", "POST"])
async def handle_dtmf(request: Request, db: Session = Depends(get_db)):
    """
    Caller pressed a keypad key. Notate the response into the DB!
    """
    digits = ""
    call_uuid = ""
    to_num = ""

    if request.method == "POST":
        try:
            form = await request.form()
            digits = str(form.get("Digits", "")).strip()
            call_uuid = str(form.get("CallUUID", form.get("call_uuid", ""))).strip()
            to_num = str(form.get("To", "")).strip()
        except Exception as e:
            print(f"[!] Error reading DTMF form: {e}")
    else:
        digits = request.query_params.get("Digits", "").strip()

    # Match database record
    cleaned_to = to_num.replace(" ", "").replace("-", "") if to_num else ""
    record = (
        db.query(CallRecord)
        .filter((CallRecord.vobiz_call_uuid == call_uuid) | (CallRecord.phone_number.contains(cleaned_to[-10:]) if cleaned_to else False))
        .order_by(CallRecord.id.desc())
        .first()
    )

    course_type = record.course_type or "bca_internship" if record else "bca_internship"
    lang = record.language or "en" if record else "en"

    course_name_map = {
        "bca_internship": "BCA Internship Program",
        "distance_education": "Online & Distance Education",
        "deep_courses": "DEEP Courses"
    }
    course_name = course_name_map.get(course_type, "Program Details")

    # Determine response note and audio
    if digits == "1":
        selected_audio = f"ack_{lang}.wav"
        if not (AUDIO_DIR / selected_audio).exists():
            selected_audio = "ack_en.wav"
        response_note = f"Pressed 1: WhatsApp Details Requested ({course_name})"
    elif digits:
        selected_audio = f"timeout_{lang}.wav"
        if not (AUDIO_DIR / selected_audio).exists():
            selected_audio = "timeout.wav"
        response_note = f"Pressed Key: {digits}"
    else:
        selected_audio = f"timeout_{lang}.wav"
        if not (AUDIO_DIR / selected_audio).exists():
            selected_audio = "timeout.wav"
        response_note = "Listened to prompt (No key pressed / Timeout)"

    if record:
        record.dtmf_digit = digits
        record.response_note = response_note
        record.audio_flow = f"{course_type}_{lang}.wav -> {selected_audio}"
        record.status = "answered"
        db.commit()
        print(f"\n[RESPONSE NOTATED] Phone: {record.phone_number} | Key: {digits} | Response: {response_note}")

    audio_url = f"{SERVER_BASE_URL}/audio/{selected_audio}"
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Hangup/>
</Response>"""
    return Response(content=xml_content.strip(), media_type="application/xml")


@app.api_route("/call/status", methods=["GET", "POST"])
async def call_status(request: Request, db: Session = Depends(get_db)):
    """
    Carrier hangup callback. Calculates exact telecom cost and duration.
    """
    form = {}
    try:
        form = await request.form()
    except Exception:
        pass

    call_uuid = str(form.get("CallUUID", form.get("call_uuid", ""))).strip()
    to_num = str(form.get("To", "")).strip()
    carrier_duration = form.get("Duration", form.get("BillDuration"))

    cleaned_to = to_num.replace(" ", "").replace("-", "") if to_num else ""
    record = (
        db.query(CallRecord)
        .filter((CallRecord.vobiz_call_uuid == call_uuid) | (CallRecord.phone_number.contains(cleaned_to[-10:]) if cleaned_to else False))
        .order_by(CallRecord.id.desc())
        .first()
    )

    if record:
        if carrier_duration:
            dur = float(carrier_duration)
            record.duration_sec = dur
            billable_minutes = math.ceil(dur / 60.0) if dur > 0 else 0
            record.carrier_cost_inr = round(billable_minutes * VOBIZ_PER_MINUTE_RATE, 2)
            if dur > 0:
                record.status = "completed"
                record.tokens_used = 1.0
            else:
                record.status = "no-answer"
                record.response_note = "Rings but Nobody Answers"
                record.tokens_used = 0.3
        else:
            record.status = "completed"
            record.tokens_used = 1.0
        db.commit()

    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print("=" * 65)
    print(f" Starting Vobiz Auto-Dialer & Response Hub on port {port}")
    print(f" Web UI        : {SERVER_BASE_URL}/")
    print(f" Admin Panel   : {SERVER_BASE_URL}/ (Click 'Admin & Carrier Wallet' tab)")
    print("=" * 65)
    uvicorn.run("calling_agent:app", host="0.0.0.0", port=port, reload=True)
