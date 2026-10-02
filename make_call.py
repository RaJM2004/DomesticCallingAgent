import os
import sys
import asyncio
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# LiveKit SIP Configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
OUTBOUND_TRUNK_ID = os.getenv("OUTBOUND_TRUNK_ID", "ST_z4V2wYPm5ar3")
VOBIZ_OUTBOUND_NUMBER = os.getenv("VOBIZ_OUTBOUND_NUMBER", "+917965853227")

# Vobiz REST API Configuration
VOBIZ_AUTH_ID = os.getenv("VOBIZ_AUTH_ID")
VOBIZ_AUTH_TOKEN = os.getenv("VOBIZ_AUTH_TOKEN")
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://localhost:8000").rstrip("/")


def format_phone_number(phone: str) -> str:
    cleaned = phone.strip().replace(" ", "").replace("-", "")
    if not cleaned.startswith("+"):
        if len(cleaned) == 10:
            cleaned = "+91" + cleaned
        else:
            cleaned = "+" + cleaned
    return cleaned


async def call_via_livekit_sip(to_number: str, room_name: str = None) -> dict:
    """
    Initiate call using LiveKit SIP trunk connected to Vobiz.
    """
    from livekit import api

    to_number = format_phone_number(to_number)
    room_name = room_name or f"call-{to_number.replace('+', '')}-{int(datetime.now().timestamp())}"

    print(f"\n[*] Initiating Call via LiveKit Vobiz SIP Trunk...")
    print(f"[*] Destination (To)   : {to_number}")
    print(f"[*] Caller ID (From)   : {VOBIZ_OUTBOUND_NUMBER}")
    print(f"[*] SIP Trunk ID       : {OUTBOUND_TRUNK_ID}")
    print(f"[*] Room Name          : {room_name}")

    lk = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        req = api.CreateSIPParticipantRequest(
            sip_trunk_id=OUTBOUND_TRUNK_ID,
            sip_call_to=to_number,
            sip_number=VOBIZ_OUTBOUND_NUMBER,
            room_name=room_name,
            participant_identity=f"caller_{to_number}"
        )
        res = await lk.sip.create_sip_participant(req)
        print("\n" + "=" * 60)
        print("          [CALL RINGING / INITIATED SUCCESSFULLY]          ")
        print("=" * 60)
        print(f" Participant ID : {res.participant_id}")
        print(f" SIP Call ID    : {res.sip_call_id}")
        print(f" Room Name      : {res.room_name}")
        print(f" Identity       : {res.participant_identity}")
        print("=" * 60 + "\n")
        return {
            "status": "success",
            "participant_id": res.participant_id,
            "sip_call_id": res.sip_call_id,
            "room_name": res.room_name
        }
    except Exception as e:
        print(f"\n[ERROR] Failed to initiate SIP call: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        await lk.aclose()


def call_via_vobiz_rest(to_number: str) -> dict:
    """
    Initiate call using native Vobiz REST API (if Auth ID/Token configured).
    """
    to_number = format_phone_number(to_number)
    url = f"https://api.vobiz.ai/api/v1/Account/{VOBIZ_AUTH_ID}/Call/"
    headers = {
        "Content-Type": "application/json",
        "X-Auth-ID": VOBIZ_AUTH_ID,
        "X-Auth-Token": VOBIZ_AUTH_TOKEN
    }
    answer_url = f"{SERVER_BASE_URL}/call/incoming"
    payload = {
        "from": VOBIZ_OUTBOUND_NUMBER,
        "to": to_number,
        "answer_url": answer_url,
        "answer_method": "POST"
    }

    print(f"\n[*] Initiating Outbound Call via Vobiz REST API to: {to_number}")
    response = requests.post(url, json=payload, headers=headers, timeout=20)
    print(f"[*] Status: {response.status_code} | Body: {response.text}")
    return {"status_code": response.status_code, "text": response.text}


def make_call(to_number: str):
    if LIVEKIT_URL and LIVEKIT_API_KEY and OUTBOUND_TRUNK_ID:
        asyncio.run(call_via_livekit_sip(to_number))
    elif VOBIZ_AUTH_ID and VOBIZ_AUTH_TOKEN:
        call_via_vobiz_rest(to_number)
    else:
        print("[!] Error: No calling provider configured. Please check your .env credentials.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = "9980113561"
    make_call(target)
