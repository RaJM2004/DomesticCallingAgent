import os
import sys
import wave
import time
import math
import asyncio
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

from livekit import api, rtc
from database import SessionLocal, CallRecord, Account
from vobiz_cdr import fetch_live_vobiz_call_cost

AUDIO_DIR = Path(__file__).parent / "audio"
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
OUTBOUND_TRUNK_ID = os.getenv("OUTBOUND_TRUNK_ID", "ST_z4V2wYPm5ar3")
VOBIZ_OUTBOUND_NUMBER = os.getenv("VOBIZ_OUTBOUND_NUMBER", "+917965853227")


def format_phone(phone: str) -> str:
    cleaned = phone.strip().replace(" ", "").replace("-", "")
    if not cleaned.startswith("+"):
        if len(cleaned) == 10:
            cleaned = "+91" + cleaned
        else:
            cleaned = "+" + cleaned
    return cleaned


async def play_audio_file(audio_source: rtc.AudioSource, filepath: Path, interrupt_event: asyncio.Event = None):
    """
    Streams a WAV file into the LiveKit audio track with buffering to guarantee clean playback.
    """
    if not filepath.exists():
        print(f"[!] Audio file not found: {filepath}")
        return

    with wave.open(str(filepath), "rb") as wf:
        sample_rate = wf.getframerate()
        num_channels = wf.getnchannels()
        chunk_ms = 20
        samples_per_channel = int(sample_rate * (chunk_ms / 1000.0))
        bytes_per_sample = wf.getsampwidth()
        chunk_bytes = samples_per_channel * num_channels * bytes_per_sample

        while True:
            if interrupt_event and interrupt_event.is_set():
                break

            if audio_source.queued_duration > 0.4:
                await asyncio.sleep(0.05)
                continue

            data = wf.readframes(samples_per_channel)
            if not data or len(data) < chunk_bytes:
                break
            frame = rtc.AudioFrame(
                data=data,
                sample_rate=sample_rate,
                num_channels=num_channels,
                samples_per_channel=samples_per_channel
            )
            await audio_source.capture_frame(frame)

        if not (interrupt_event and interrupt_event.is_set()):
            await audio_source.wait_for_playout()


async def execute_live_call(target_phone: str, record_id: int = None, course_type: str = "bca_internship", language: str = "en", stop_event: asyncio.Event = None) -> dict:
    """
    1. Connects LiveKit Room with audio track.
    2. Places SIP call through Vobiz Trunk.
    3. Streams the configured course & language audio (e.g. bca_internship_hi.wav) at calm speed.
    4. Listens for live DTMF keypress (Press 1 for WhatsApp details).
    5. Streams multilingual acknowledgment audio (ack_hi.wav) or timeout audio.
    6. Automatically terminates the telephone call via SIP BYE (delete_room).
    7. Updates DB CallRecord with duration, cost, DTMF input, and WhatsApp interest annotation.
    """
    target_phone = format_phone(target_phone)
    call_start_time = time.time()
    room_name = f"call-{target_phone.replace('+', '')}-{int(call_start_time)}"

    # Determine course and language from record if present
    if record_id:
        db = SessionLocal()
        try:
            rec = db.query(CallRecord).filter(CallRecord.id == record_id).first()
            if rec:
                if rec.course_type:
                    course_type = rec.course_type
                if rec.language:
                    language = rec.language
        except Exception:
            pass
        finally:
            db.close()

    prompt_filename = f"{course_type}_{language}.wav"
    prompt_path = AUDIO_DIR / prompt_filename
    if not prompt_path.exists():
        prompt_filename = f"{course_type}_en.wav"
        prompt_path = AUDIO_DIR / prompt_filename
        if not prompt_path.exists():
            prompt_filename = "welcome.wav"
            prompt_path = AUDIO_DIR / prompt_filename

    ack_filename = f"ack_{language}.wav"
    ack_path = AUDIO_DIR / ack_filename
    if not ack_path.exists():
        ack_path = AUDIO_DIR / "ack_en.wav"
        ack_filename = ack_path.name

    timeout_filename = f"timeout_{language}.wav"
    timeout_path = AUDIO_DIR / timeout_filename
    if not timeout_path.exists():
        timeout_path = AUDIO_DIR / "timeout.wav"
        timeout_filename = timeout_path.name

    print("\n" + "=" * 65)
    print(f"[*] DIALING: {target_phone} via Vobiz SIP Trunk")
    print(f"[*] Program : {course_type} | Language: {language.upper()}")
    print(f"[*] Prompt  : {prompt_filename}")
    print(f"[*] Room    : {room_name}")
    print("=" * 65)

    def update_record(**kwargs):
        if not record_id:
            return
        db = SessionLocal()
        try:
            rec = db.query(CallRecord).filter(CallRecord.id == record_id).first()
            if rec:
                for k, v in kwargs.items():
                    setattr(rec, k, v)
                db.commit()
        except Exception as e:
            print(f"[!] DB update error: {e}")
        finally:
            db.close()

    update_record(status="calling", response_note="Ringing destination...", vobiz_call_uuid=room_name)

    # 1. Generate JWT token
    token_builder = (
        api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity("audio_player_agent")
        .with_name("IVR Audio Bot")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
    )
    token = token_builder.to_jwt()

    # 2. Connect Room
    room = rtc.Room()
    await room.connect(LIVEKIT_URL, token)
    print(f"[+] Audio Bot joined LiveKit room: {room.name}")

    # 3. Create Audio Track (48kHz)
    audio_source = rtc.AudioSource(sample_rate=48000, num_channels=1)
    track = rtc.LocalAudioTrack.create_audio_track("agent_ivr_audio", audio_source)
    options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    await room.local_participant.publish_track(track, options)
    print("[+] Audio Track published to room (48kHz Studio Quality).")

    call_answered = asyncio.Event()
    call_declined = asyncio.Event()
    dtmf_received_event = asyncio.Event()
    dtmf_digit_holder = {"digit": None}
    audio_history = ["welcome.wav"]
    call_active = True

    @room.on("participant_connected")
    def on_participant_connected(p: rtc.RemoteParticipant):
        if p.identity.startswith("caller_"):
            print(f"\n[PHONE PICKED UP!] Caller answered the phone: {p.identity}")
            call_answered.set()

    @room.on("participant_disconnected")
    def on_participant_disconnected(p: rtc.RemoteParticipant):
        nonlocal call_active
        if p.identity.startswith("caller_"):
            print(f"\n[PHONE HUNG UP / DECLINED] Caller disconnected: {p.identity}")
            call_active = False
            if not call_answered.is_set():
                call_declined.set()
            dtmf_received_event.set()

    @room.on("sip_dtmf_received")
    def on_sip_dtmf(dtmf_event: rtc.SipDTMF):
        digit = str(dtmf_event.digit)
        print(f"\n" + "★" * 60)
        print(f"  [KEYPAD PRESSED!] Caller pressed digit: '{digit}'")
        print("★" * 60)
        dtmf_digit_holder["digit"] = digit
        dtmf_received_event.set()

    # 4. Dial through Vobiz Trunk
    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    sip_call_id = ""
    try:
        sip_req = api.CreateSIPParticipantRequest(
            sip_trunk_id=OUTBOUND_TRUNK_ID,
            sip_call_to=target_phone,
            sip_number=VOBIZ_OUTBOUND_NUMBER,
            room_name=room_name,
            participant_identity=f"caller_{target_phone}",
            wait_until_answered=True
        )
        res = await lk_api.sip.create_sip_participant(sip_req)
        sip_call_id = res.sip_call_id
        update_record(vobiz_call_uuid=sip_call_id)
        print(f"[+] Call Ringing! SIP Call ID: {sip_call_id}")
    except Exception as e:
        print(f"[!] Error creating SIP participant: {e}")
        err_lower = str(e).lower()
        if any(w in err_lower for w in ["busy", "decline", "reject", "486", "603", "cancelled"]):
            status_val = "busy"
            note_val = "User declines before picking up"
        elif any(w in err_lower for w in ["invalid", "unallocated", "format", "not found", "404", "410", "unreachable"]):
            status_val = "failed"
            note_val = "Failed / Invalid Number"
        else:
            status_val = "failed"
            note_val = f"Failed / Network Error ({e})"

        update_record(status=status_val, response_note=note_val, tokens_used=0.3)
        await lk_api.aclose()
        await room.disconnect()
        return {"success": False, "status": status_val, "tokens_used": 0.3, "error": str(e)}

    # Wait for phone to be answered (or declined, up to 40s timeout)
    answered_task = asyncio.create_task(call_answered.wait())
    declined_task = asyncio.create_task(call_declined.wait())

    done, pending = await asyncio.wait(
        [answered_task, declined_task],
        timeout=40.0,
        return_when=asyncio.FIRST_COMPLETED
    )

    for p in pending:
        p.cancel()

    if not done:
        # Ringing timeout - nobody answered
        print("\n[!] Call not answered within 40 seconds (Rings but Nobody Answers).")
        update_record(status="no-answer", response_note="Rings but Nobody Answers", tokens_used=0.3)
        try:
            await lk_api.room.delete_room(api.DeleteRoomRequest(room=room_name))
        except Exception:
            pass
        await lk_api.aclose()
        await room.disconnect()
        return {"success": False, "status": "no-answer", "tokens_used": 0.3}

    if call_declined.is_set() and not call_answered.is_set():
        # User declined or rejected call before answering
        print("\n[!] Caller disconnected before answering (User declines before picking up).")
        update_record(status="busy", response_note="User declines before picking up", tokens_used=0.3)
        try:
            await lk_api.room.delete_room(api.DeleteRoomRequest(room=room_name))
        except Exception:
            pass
        await lk_api.aclose()
        await room.disconnect()
        return {"success": False, "status": "busy", "tokens_used": 0.3}

    # Caller answered!
    answered_time = time.time()
    update_record(status="answered", response_note=f"Call answered. Playing {course_type} ({language.upper()})...", audio_flow=prompt_filename, tokens_used=1.0)
    print(f"\n[CONNECTED] Caller answered. Streaming {prompt_filename} into call now...")
    await asyncio.sleep(0.8)  # Settle audio channel

    welcome_task = asyncio.create_task(play_audio_file(audio_source, prompt_path, dtmf_received_event))

    # Wait for welcome audio to finish OR dtmf to be pressed
    while not welcome_task.done() and not dtmf_received_event.is_set():
        if not call_active:
            break
        await asyncio.sleep(0.1)

    # If welcome finished and caller still on line, wait up to 4s for keypress
    if call_active and not dtmf_received_event.is_set():
        try:
            await asyncio.wait_for(dtmf_received_event.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            print("[*] No DTMF received within 4s after prompt.")

    welcome_task.cancel()
    audio_source.clear_queue()

    digit = dtmf_digit_holder["digit"]
    response_note = "Completed"

    course_name_map = {
        "bca_internship": "BCA Internship Program",
        "distance_education": "Online & Distance Education",
        "deep_courses": "DEEP Courses"
    }
    course_name = course_name_map.get(course_type, "Program Details")

    # Only play response audio if caller is still connected
    if call_active:
        if digit == "1":
            print(f"[*] Condition DTMF == 1: Caller pressed 1 for WhatsApp details ({course_name})")
            audio_history.append(ack_filename)
            response_note = f"Pressed 1: WhatsApp Details Requested ({course_name})"
            update_record(dtmf_digit="1", response_note=response_note, audio_flow=f"{prompt_filename} -> {ack_filename}")
            await play_audio_file(audio_source, ack_path)
        elif digit:
            print(f"[*] Caller pressed key '{digit}'")
            audio_history.append(timeout_filename)
            response_note = f"Pressed Key {digit}"
            update_record(dtmf_digit=digit, response_note=response_note, audio_flow=f"{prompt_filename} -> {timeout_filename}")
            await play_audio_file(audio_source, timeout_path)
        else:
            print("[*] No DTMF received (Timeout / Listened).")
            audio_history.append(timeout_filename)
            response_note = "Listened to prompt (No key pressed / Timeout)"
            update_record(dtmf_digit="", response_note=response_note, audio_flow=f"{prompt_filename} -> {timeout_filename}")
            await play_audio_file(audio_source, timeout_path)

    # Give brief buffer then FORCEFULLY TERMINATE the telephone call
    await asyncio.sleep(0.5)
    total_duration = time.time() - answered_time

    print(f"\n" + "=" * 65)
    print(f" [AUTOMATIC HANGUP] Terminating telephone call for {target_phone}...")
    print("=" * 65)

    try:
        # Delete room sends SIP BYE to Vobiz carrier, hanging up caller's phone immediately!
        await lk_api.room.delete_room(api.DeleteRoomRequest(room=room_name))
        print(f"[✓] Room deleted - Phone line hung up successfully!")
    except Exception as e:
        print(f"[!] DeleteRoom error: {e}")
        try:
            await lk_api.room.remove_participant(
                api.RoomParticipantIdentity(room=room_name, identity=f"caller_{target_phone}")
            )
        except Exception:
            pass

    await room.disconnect()
    await lk_api.aclose()

    # Calculate wholesale cost
    bill_min = math.ceil(total_duration / 60.0) if total_duration > 0 else 0
    vobiz_cost = round(bill_min * 0.45, 2)

    update_record(
        status="completed",
        duration_sec=round(total_duration, 1),
        carrier_cost_inr=vobiz_cost,
        tokens_used=1.0
    )

    return {
        "success": True,
        "status": "completed",
        "duration_sec": total_duration,
        "dtmf_digit": digit,
        "response_note": response_note,
        "vobiz_cost_inr": vobiz_cost,
        "tokens_used": 1.0
    }


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "9980113561"
    asyncio.run(execute_live_call(target))
