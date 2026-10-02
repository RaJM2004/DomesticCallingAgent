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
from calling_agent import save_log_entry, calculate_cost, print_cost_summary
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
    Streams a WAV file into the LiveKit audio track with pre-buffering to eliminate any stuttering or breaking.
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

            # Keep a healthy buffer (0.4s) in queue so Windows timer jitter never starves WebRTC
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


async def execute_live_call(target_phone: str):
    target_phone = format_phone(target_phone)
    call_start_time = time.time()
    dt_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    room_name = f"call-{target_phone.replace('+', '')}-{int(call_start_time)}"

    print("=" * 65)
    print("      DIALING PHONE NUMBER - LIVE ZERO-COST AUDIO AGENT      ")
    print("=" * 65)
    print(f" Target Number (To)    : {target_phone}")
    print(f" Caller ID (From)      : {VOBIZ_OUTBOUND_NUMBER}")
    print(f" LiveKit Room          : {room_name}")
    print(f" Outbound SIP Trunk    : {OUTBOUND_TRUNK_ID}")
    print("=" * 65)

    # 1. Create a JWT token for our audio bot to join the room
    token_builder = (
        api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity("audio_player_agent")
        .with_name("IVR Audio Bot")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
    )
    token = token_builder.to_jwt()

    # 2. Connect to the LiveKit Room
    room = rtc.Room()
    print("[*] Connecting Audio Bot to LiveKit room...")
    ws_url = LIVEKIT_URL
    await room.connect(ws_url, token)
    print(f"[+] Audio Bot connected to room: {room.name}")

    # 3. Create Audio Source & Track (48kHz HD Audio)
    sample_rate = 48000
    audio_source = rtc.AudioSource(sample_rate=sample_rate, num_channels=1)
    track = rtc.LocalAudioTrack.create_audio_track("agent_ivr_audio", audio_source)
    options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    publication = await room.local_participant.publish_track(track, options)
    print("[+] Audio Track published to room (48kHz Studio Quality).")

    # State variables
    call_answered = asyncio.Event()
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
        print(f"\n[PHONE HUNG UP] Caller disconnected: {p.identity}")
        call_active = False
        dtmf_received_event.set()

    @room.on("sip_dtmf_received")
    def on_sip_dtmf(dtmf_event: rtc.SipDTMF):
        digit = str(dtmf_event.digit)
        print(f"\n" + "★" * 60)
        print(f"  [KEYPAD PRESSED!] Caller pressed digit: '{digit}'")
        print("★" * 60)
        dtmf_digit_holder["digit"] = digit
        dtmf_received_event.set()

    # 4. Dial the SIP Participant through Vobiz Trunk with wait_until_answered=True
    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    print(f"[*] Placing phone call to {target_phone} via Vobiz Trunk...")
    try:
        sip_req = api.CreateSIPParticipantRequest(
            sip_trunk_id=OUTBOUND_TRUNK_ID,
            sip_call_to=target_phone,
            sip_number=VOBIZ_OUTBOUND_NUMBER,
            room_name=room_name,
            participant_identity=f"caller_{target_phone}",
            wait_until_answered=True  # Crucial: only join room once human answers phone!
        )
        res = await lk_api.sip.create_sip_participant(sip_req)
        sip_call_id = res.sip_call_id
        print(f"[+] Call Dispatched! SIP Call ID: {sip_call_id}")
        print("[*] Phone is ringing... Please answer your phone when it rings!")
    except Exception as e:
        print(f"[!] Error creating SIP participant: {e}")
        await lk_api.aclose()
        await room.disconnect()
        return

    # Wait for phone to be answered (up to 45 seconds timeout)
    try:
        await asyncio.wait_for(call_answered.wait(), timeout=45.0)
    except asyncio.TimeoutError:
        print("\n[!] Call not answered within 45 seconds.")
        await lk_api.aclose()
        await room.disconnect()
        return

    # 5. Caller answered! Allow 1.5s for audio channel / phone speaker to settle
    answered_time = time.time()
    print("\n[CONNECTED] Caller answered. Pausing 1.5s for telecom audio channel to settle...")
    await asyncio.sleep(1.5)

    print("[*] Playing welcome.wav to caller now...")
    welcome_path = AUDIO_DIR / "welcome.wav"

    # Play welcome audio while listening for DTMF
    welcome_task = asyncio.create_task(play_audio_file(audio_source, welcome_path, dtmf_received_event))

    # Wait for either DTMF keypress or timeout (give 25s window so caller can hear full message + decide)
    try:
        await asyncio.wait_for(dtmf_received_event.wait(), timeout=25.0)
    except asyncio.TimeoutError:
        print("[*] No DTMF received before timeout.")

    welcome_task.cancel()
    audio_source.clear_queue()

    digit = dtmf_digit_holder["digit"]
    if digit == "1":
        print("[*] Condition DTMF == 1: Playing audio_1.wav (Sales option)...")
        audio_history.append("audio_1.wav")
        await play_audio_file(audio_source, AUDIO_DIR / "audio_1.wav")
    elif digit == "2":
        print("[*] Condition DTMF == 2: Playing audio_2.wav (Support option)...")
        audio_history.append("audio_2.wav")
        await play_audio_file(audio_source, AUDIO_DIR / "audio_2.wav")
    elif digit is not None:
        print(f"[*] Other digit '{digit}': Playing timeout.wav...")
        audio_history.append("timeout.wav")
        await play_audio_file(audio_source, AUDIO_DIR / "timeout.wav")
    else:
        print("[*] No digit pressed: Playing timeout.wav...")
        audio_history.append("timeout.wav")
        await play_audio_file(audio_source, AUDIO_DIR / "timeout.wav")

    # Give 1 second buffer before terminating
    await asyncio.sleep(1.0)
    total_duration = time.time() - answered_time

    # Disconnect from room
    await room.disconnect()
    await lk_api.aclose()

    # 6. Fetch live billing deduction directly from Vobiz Carrier API
    print("\n[*] Fetching live billing deduction directly from Vobiz Carrier API...")
    live_cdr = fetch_live_vobiz_call_cost(to_number=target_phone)

    if live_cdr:
        vobiz_cost = live_cdr["live_vobiz_cost"]
        bill_sec = live_cdr["bill_duration_sec"]
        call_uuid_actual = live_cdr.get("call_uuid") or sip_call_id
        currency = live_cdr.get("currency", "INR")
        billing_source = "Live Vobiz Carrier Ledger"
        print(f"[+] Live Vobiz Ledger: Billed Duration = {bill_sec}s | Exact Deduction = {vobiz_cost} {currency}")
    else:
        bill_min = math.ceil(total_duration / 60.0)
        vobiz_cost = round(bill_min * 0.45, 2)
        call_uuid_actual = sip_call_id
        billing_source = "Telecom Pulse Benchmark"

    cost_data = {
        "duration_seconds": round(total_duration, 2),
        "billable_pulses_minutes": math.ceil(total_duration / 60.0),
        "vobiz_telecom_cost_inr": vobiz_cost,
        "billing_source": billing_source,
        "ai_stt_cost_inr": 0.00,
        "ai_llm_cost_inr": 0.00,
        "ai_tts_cost_inr": 0.00,
        "total_cost_inr": vobiz_cost,
        "savings_vs_full_ai_inr": round(math.ceil(total_duration / 60.0) * 3.00 - vobiz_cost, 2)
    }

    log_entry = {
        "call_uuid": call_uuid_actual,
        "from": VOBIZ_OUTBOUND_NUMBER,
        "to": target_phone,
        "status": "completed",
        "start_time_iso": dt_now,
        "start_time_ts": call_start_time,
        "dtmf_digit": digit or "None",
        "audio_played": " -> ".join(audio_history),
        "cost_breakdown": cost_data
    }
    save_log_entry(log_entry)
    print_cost_summary(log_entry)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "9980113561"
    asyncio.run(execute_live_call(target))
