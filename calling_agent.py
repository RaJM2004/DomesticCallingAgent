import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import os
import json
import time
import math
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

load_dotenv()

app = FastAPI(title="Vobiz DTMF Calling Agent & Cost Logger")

# Directories and file paths
BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True)
LOGS_FILE = BASE_DIR / "call_logs.json"
EXCEL_FILE = BASE_DIR / "call_billing_log.xlsx"

# Mount audio directory to serve static audio files directly
app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")

SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://localhost:8000").rstrip("/")
VOBIZ_PER_MINUTE_RATE = float(os.getenv("VOBIZ_PER_MINUTE_RATE", 0.45))  # INR 0.45 carrier rate

# In-memory store for active calls
active_calls = {}


def load_logs() -> list:
    if LOGS_FILE.exists():
        try:
            with open(LOGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def update_excel_sheet(logs: list):
    """
    Generates a professionally styled Microsoft Excel (.xlsx) file
    with full cost audit and client savings.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Call Billing & Cost Audit"

    # Define styles
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    total_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    total_font = Font(name="Calibri", size=11, bold=True, color="0F172A")
    regular_font = Font(name="Calibri", size=11)
    center_align = Alignment(horizontal="center", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0")
    )

    headers = [
        "Date & Time",
        "Call UUID",
        "From (Caller)",
        "To (Destination)",
        "DTMF Key Pressed",
        "Audio Flow Played",
        "Duration (Sec)",
        "Billable Minutes",
        "Vobiz Telecom Cost (INR)",
        "Live STT Cost (INR)",
        "Live LLM Cost (INR)",
        "Live TTS Cost (INR)",
        "Total Cost (INR)",
        "Client Savings vs Full AI (INR)"
    ]

    ws.append(headers)
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        ws.row_dimensions[1].height = 28

    total_sec = 0.0
    total_bill_min = 0
    total_cost_inr = 0.0
    total_saved_inr = 0.0

    for row_idx, entry in enumerate(logs, start=2):
        cost = entry.get("cost_breakdown", {})
        dur_sec = cost.get("duration_seconds", 0)
        bill_min = cost.get("billable_pulses_minutes", 1)
        vobiz_cost = cost.get("vobiz_telecom_cost_inr", 0.0)
        stt_cost = cost.get("ai_stt_cost_inr", 0.0)
        llm_cost = cost.get("ai_llm_cost_inr", 0.0)
        tts_cost = cost.get("ai_tts_cost_inr", 0.0)
        total_call_cost = cost.get("total_cost_inr", 0.0)
        saved = cost.get("savings_vs_full_ai_inr", 0.0)

        total_sec += dur_sec
        total_bill_min += bill_min
        total_cost_inr += total_call_cost
        total_saved_inr += saved

        row_data = [
            entry.get("start_time_iso", ""),
            entry.get("call_uuid", ""),
            entry.get("from", ""),
            entry.get("to", ""),
            entry.get("dtmf_digit") or "None",
            entry.get("audio_played", ""),
            dur_sec,
            bill_min,
            vobiz_cost,
            stt_cost,
            llm_cost,
            tts_cost,
            total_call_cost,
            saved
        ]
        ws.append(row_data)

        # Style data cells
        for col_idx in range(1, len(row_data) + 1):
            c = ws.cell(row=row_idx, column=col_idx)
            c.font = regular_font
            c.border = thin_border
            if col_idx in [5, 7, 8]:
                c.alignment = center_align
            elif col_idx in [9, 10, 11, 12, 13, 14]:
                c.alignment = right_align
                c.number_format = "#,##0.00"
            else:
                c.alignment = left_align

    # Add Summary Row at the bottom
    summary_row_idx = len(logs) + 2
    summary_data = [
        "TOTAL / SUMMARY",
        f"{len(logs)} Calls",
        "-",
        "-",
        "-",
        "-",
        round(total_sec, 2),
        total_bill_min,
        round(total_cost_inr, 2),
        0.00,
        0.00,
        0.00,
        round(total_cost_inr, 2),
        round(total_saved_inr, 2)
    ]
    ws.append(summary_data)
    ws.row_dimensions[summary_row_idx].height = 24
    for col_idx in range(1, len(summary_data) + 1):
        c = ws.cell(row=summary_row_idx, column=col_idx)
        c.fill = total_fill
        c.font = total_font
        c.border = thin_border
        if col_idx in [9, 10, 11, 12, 13, 14]:
            c.alignment = right_align
            c.number_format = "#,##0.00"
        else:
            c.alignment = center_align

    # Auto-fit column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

    try:
        wb.save(str(EXCEL_FILE))
    except PermissionError:
        # If user has the file open in Excel on Windows, save to a fallback copy
        fallback = BASE_DIR / "call_billing_log_latest.xlsx"
        wb.save(str(fallback))
        print(f"[*] Note: '{EXCEL_FILE.name}' is currently open in Excel. Saved update to '{fallback.name}'")

    # Also maintain CSV mirror for instant access
    try:
        import csv
        csv_file = BASE_DIR / "call_billing_log.csv"
        with open(csv_file, "w", newline="", encoding="utf-8-sig") as cf:
            writer = csv.writer(cf)
            writer.writerow(headers)
            for entry in logs:
                cost = entry.get("cost_breakdown", {})
                writer.writerow([
                    entry.get("start_time_iso", ""),
                    entry.get("call_uuid", ""),
                    entry.get("from", ""),
                    entry.get("to", ""),
                    entry.get("dtmf_digit") or "None",
                    entry.get("audio_played", ""),
                    cost.get("duration_seconds", 0),
                    cost.get("billable_pulses_minutes", 1),
                    f"{cost.get('vobiz_telecom_cost_inr', 0):.2f}",
                    "0.00",
                    "0.00",
                    "0.00",
                    f"{cost.get('total_cost_inr', 0):.2f}",
                    f"{cost.get('savings_vs_full_ai_inr', 0):.2f}"
                ])
            writer.writerow(summary_data)
    except Exception as e:
        print(f"[!] Warning updating CSV: {e}")


def save_log_entry(entry: dict):
    logs = load_logs()
    existing_index = next((i for i, x in enumerate(logs) if x.get("call_uuid") == entry.get("call_uuid")), None)
    if existing_index is not None:
        logs[existing_index] = entry
    else:
        logs.append(entry)

    with open(LOGS_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)

    # Refresh Excel spreadsheet
    try:
        update_excel_sheet(logs)
    except Exception as e:
        print(f"[!] Warning: Could not update Excel file: {e}")


from vobiz_cdr import fetch_live_vobiz_call_cost


def calculate_cost(duration_seconds: float, call_id: str = None) -> dict:
    """
    Calculates cost based on live Vobiz CDR API ledger deduction if available,
    otherwise standard 60-second telecom carrier pulse benchmark.
    AI Cost is 0.00 since pre-rendered audio and hardware DTMF are used.
    """
    duration = max(1.0, float(duration_seconds))
    billable_minutes = math.ceil(duration / 60.0)

    live_cdr = fetch_live_vobiz_call_cost(call_id)
    if live_cdr:
        vobiz_cost = live_cdr["live_vobiz_cost_inr"]
        billing_source = "Live Vobiz Carrier CDR"
        billable_minutes = math.ceil(live_cdr.get("bill_duration_sec", duration) / 60.0)
    else:
        vobiz_cost = round(billable_minutes * VOBIZ_PER_MINUTE_RATE, 3)
        billing_source = "Telecom Pulse Benchmark"

    total_cost = vobiz_cost

    return {
        "duration_seconds": round(duration, 2),
        "billable_pulses_minutes": billable_minutes,
        "vobiz_telecom_cost_inr": vobiz_cost,
        "billing_source": billing_source,
        "ai_stt_cost_inr": 0.00,
        "ai_llm_cost_inr": 0.00,
        "ai_tts_cost_inr": 0.00,
        "total_cost_inr": total_cost,
        "savings_vs_full_ai_inr": round(billable_minutes * 3.00 - total_cost, 2)
    }


def print_cost_summary(call_data: dict):
    c = call_data.get("cost_breakdown", {})
    print("\n" + "=" * 65)
    print("                CALL COMPLETED - COST AUDIT                ")
    print("=" * 65)
    print(f" Call UUID         : {call_data.get('call_uuid')}")
    print(f" Caller (From)     : {call_data.get('from')}")
    print(f" Destination (To)  : {call_data.get('to')}")
    print(f" DTMF Key Pressed  : {call_data.get('dtmf_digit', 'None')}")
    print(f" Audio Played      : {call_data.get('audio_played')}")
    print(f" Call Duration     : {c.get('duration_seconds', 0)} seconds ({c.get('billable_pulses_minutes', 1)} billable min)")
    print("-" * 65)
    print(f" 1. Vobiz Telecom Cost : INR {c.get('vobiz_telecom_cost_inr', 0):.2f}")
    print(f" 2. Live STT Cost      : INR 0.00 (Zero - Keypad DTMF used)")
    print(f" 3. Live LLM Cost      : INR 0.00 (Zero - Deterministic Python routing)")
    print(f" 4. Live TTS Cost      : INR 0.00 (Zero - Pre-rendered on disk)")
    print("-" * 65)
    print(f" TOTAL COST FOR THIS CALL : INR {c.get('total_cost_inr', 0):.2f}")
    print(f" Estimated Client Savings : INR {c.get('savings_vs_full_ai_inr', 0):.2f}")
    print(f" Excel Sheet Updated      : {EXCEL_FILE.name}")
    print("=" * 65 + "\n")


@app.get("/")
def home():
    logs = load_logs()
    total_calls = len(logs)
    total_cost = sum(x.get("cost_breakdown", {}).get("total_cost_inr", 0) for x in logs)

    return {
        "status": "online",
        "agent": "Vobiz DTMF Calling Agent with Real-Time Excel Cost Audit",
        "total_calls_logged": total_calls,
        "total_cost_spent_inr": round(total_cost, 2),
        "excel_download_url": f"{SERVER_BASE_URL}/download-excel",
        "dashboard_url": f"{SERVER_BASE_URL}/dashboard",
        "logs_api": f"{SERVER_BASE_URL}/logs",
        "audio_files_available": [f.name for f in AUDIO_DIR.glob("*.*")],
        "endpoints": {
            "incoming_call": f"{SERVER_BASE_URL}/call/incoming",
            "dtmf_handler": f"{SERVER_BASE_URL}/call/dtmf",
            "status_handler": f"{SERVER_BASE_URL}/call/status"
        }
    }


@app.get("/download-excel")
def download_excel():
    """Download the formatted Excel spreadsheet directly."""
    if not EXCEL_FILE.exists():
        logs = load_logs()
        update_excel_sheet(logs)
    return FileResponse(
        path=str(EXCEL_FILE),
        filename="call_billing_log.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.api_route("/call/incoming", methods=["GET", "POST"])
async def incoming_call(request: Request):
    """
    Triggered when a call is connected. Starts the timing clock and plays welcome.wav.
    """
    call_start_time = time.time()
    dt_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    form = {}
    if request.method == "POST":
        try:
            form = await request.form()
        except Exception:
            pass

    call_uuid = str(form.get("CallUUID", form.get("call_uuid", f"call_{int(call_start_time)}")))
    from_num = str(form.get("From", "Unknown"))
    to_num = str(form.get("To", "Unknown"))

    call_entry = {
        "call_uuid": call_uuid,
        "from": from_num,
        "to": to_num,
        "status": "connected",
        "start_time_iso": dt_now,
        "start_time_ts": call_start_time,
        "dtmf_digit": None,
        "audio_played": "welcome.wav",
        "cost_breakdown": calculate_cost(0.1)
    }
    active_calls[call_uuid] = call_entry
    save_log_entry(call_entry)

    print(f"\n[CALL INITIATED] CallUUID: {call_uuid} | From: {from_num} | To: {to_num} at {dt_now}")

    welcome_audio_url = f"{SERVER_BASE_URL}/audio/welcome.wav"
    timeout_audio_url = f"{SERVER_BASE_URL}/audio/timeout.wav"
    dtmf_action_url = f"{SERVER_BASE_URL}/call/dtmf"

    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="{dtmf_action_url}" method="POST" inputType="dtmf" numDigits="1" executionTimeout="25">
        <Play>{welcome_audio_url}</Play>
    </Gather>
    <Play>{timeout_audio_url}</Play>
    <Hangup/>
</Response>"""

    return Response(content=xml_content.strip(), media_type="application/xml")


@app.api_route("/call/dtmf", methods=["GET", "POST"])
async def handle_dtmf(request: Request):
    """
    Triggered when caller presses a keypad digit (DTMF).
    Logs the exact timestamp, updates the audio played, and computes live cost.
    """
    dtmf_time = time.time()
    digits = ""
    call_uuid = ""
    caller = ""

    if request.method == "POST":
        try:
            form = await request.form()
            digits = str(form.get("Digits", "")).strip()
            call_uuid = str(form.get("CallUUID", form.get("call_uuid", ""))).strip()
            caller = str(form.get("From", "")).strip()
        except Exception as e:
            print(f"[!] Error reading form: {e}")
    else:
        digits = request.query_params.get("Digits", "").strip()

    call_entry = active_calls.get(call_uuid)
    if not call_entry:
        if active_calls:
            call_uuid = list(active_calls.keys())[-1]
            call_entry = active_calls[call_uuid]
        else:
            call_entry = {
                "call_uuid": call_uuid or f"call_{int(dtmf_time)}",
                "from": caller,
                "to": "N/A",
                "start_time_iso": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "start_time_ts": dtmf_time - 5.0,
            }

    start_ts = call_entry.get("start_time_ts", dtmf_time)
    elapsed = dtmf_time - start_ts

    call_entry["dtmf_digit"] = digits
    call_entry["dtmf_timestamp_iso"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if digits == "1":
        selected_audio = "audio_1.wav"
        est_final_duration = elapsed + 10.0
    elif digits == "2":
        selected_audio = "audio_2.wav"
        est_final_duration = elapsed + 10.0
    else:
        selected_audio = "timeout.wav"
        est_final_duration = elapsed + 6.0

    call_entry["audio_played"] = f"welcome.wav -> {selected_audio}"
    call_entry["status"] = "playing_response"
    call_entry["cost_breakdown"] = calculate_cost(est_final_duration)
    save_log_entry(call_entry)

    print(f"\n[DTMF RECEIVED] CallUUID: {call_uuid} | Key: '{digits}' | Elapsed so far: {elapsed:.1f}s")
    print_cost_summary(call_entry)

    audio_url = f"{SERVER_BASE_URL}/audio/{selected_audio}"
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Hangup/>
</Response>"""

    return Response(content=xml_content.strip(), media_type="application/xml")


@app.api_route("/call/status", methods=["GET", "POST"])
async def call_status(request: Request):
    """
    Called by Vobiz carrier on hangup with official carrier duration and billing duration.
    """
    form = {}
    try:
        form = await request.form()
    except Exception:
        pass

    call_uuid = str(form.get("CallUUID", form.get("call_uuid", ""))).strip()
    carrier_duration = form.get("Duration", form.get("BillDuration"))

    if call_uuid and call_uuid in active_calls:
        call_entry = active_calls[call_uuid]
        call_entry["status"] = "completed"
        call_entry["end_time_iso"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if carrier_duration:
            duration_sec = float(carrier_duration)
            call_entry["cost_breakdown"] = calculate_cost(duration_sec)
        save_log_entry(call_entry)
        print_cost_summary(call_entry)

    return {"status": "ok"}


@app.get("/logs")
def get_logs():
    return {"calls": load_logs()}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Interactive visual dashboard showing call durations and exact costs with Excel download."""
    logs = load_logs()
    total_calls = len(logs)
    total_sec = sum(x.get("cost_breakdown", {}).get("duration_seconds", 0) for x in logs)
    total_cost = sum(x.get("cost_breakdown", {}).get("total_cost_inr", 0) for x in logs)
    total_savings = sum(x.get("cost_breakdown", {}).get("savings_vs_full_ai_inr", 0) for x in logs)

    rows = ""
    for c in reversed(logs):
        cost = c.get("cost_breakdown", {})
        rows += f"""
        <tr>
            <td style="padding:10px; border-bottom:1px solid #334155;">{c.get('start_time_iso')}</td>
            <td style="padding:10px; border-bottom:1px solid #334155; font-family:monospace;">{c.get('call_uuid')[:14]}...</td>
            <td style="padding:10px; border-bottom:1px solid #334155;">{c.get('from')}</td>
            <td style="padding:10px; border-bottom:1px solid #334155; text-align:center;"><strong>{c.get('dtmf_digit', '-')}</strong></td>
            <td style="padding:10px; border-bottom:1px solid #334155;">{c.get('audio_played')}</td>
            <td style="padding:10px; border-bottom:1px solid #334155; text-align:center;">{cost.get('duration_seconds', 0)}s</td>
            <td style="padding:10px; border-bottom:1px solid #334155; text-align:right; color:#10b981; font-weight:bold;">₹{cost.get('total_cost_inr', 0):.2f}</td>
            <td style="padding:10px; border-bottom:1px solid #334155; text-align:right; color:#38bdf8;">₹{cost.get('savings_vs_full_ai_inr', 0):.2f}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Call Cost & Duration Dashboard</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: #f8fafc; padding: 30px; }}
            .container {{ max-width: 1100px; margin: 0 auto; }}
            .header-flex {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; }}
            .btn-excel {{ background: #10b981; color: white; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-flex; align-items: center; gap: 8px; }}
            .btn-excel:hover {{ background: #059669; }}
            .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }}
            .card {{ background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; }}
            .card-title {{ font-size: 13px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; }}
            .card-value {{ font-size: 28px; font-weight: bold; margin-top: 10px; }}
            table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 12px; overflow: hidden; }}
            th {{ background: #334155; padding: 12px 10px; text-align: left; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-flex">
                <div>
                    <h1>📞 Vobiz DTMF Calling Agent - Live Cost Audit</h1>
                    <p style="color:#94a3b8; margin: 4px 0 0 0;">Real-time call duration tracker and client billing audit</p>
                </div>
                <a href="/download-excel" class="btn-excel">📥 Download Excel (.xlsx)</a>
            </div>
            <div class="cards">
                <div class="card"><div class="card-title">Total Calls</div><div class="card-value">{total_calls}</div></div>
                <div class="card"><div class="card-title">Total Duration</div><div class="card-value">{int(total_sec)}s</div></div>
                <div class="card"><div class="card-title">Total Billed (Vobiz)</div><div class="card-value" style="color:#10b981;">₹{total_cost:.2f}</div></div>
                <div class="card"><div class="card-title">Client Saved</div><div class="card-value" style="color:#38bdf8;">₹{total_savings:.2f}</div></div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Date & Time</th><th>Call UUID</th><th>Caller</th><th style="text-align:center;">DTMF</th><th>Audio Flow</th><th style="text-align:center;">Duration</th><th style="text-align:right;">Actual Cost</th><th style="text-align:right;">Client Saved</th>
                    </tr>
                </thead>
                <tbody>
                    {rows if rows else '<tr><td colspan="8" style="padding:20px; text-align:center; color:#94a3b8;">No calls logged yet. Initiate a call to see live data!</td></tr>'}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print("=" * 65)
    print(f" Starting Calling Agent & Live Excel Cost Tracker on port {port}")
    print(f" Excel Report  : {EXCEL_FILE.resolve()}")
    print(f" Dashboard URL : {SERVER_BASE_URL}/dashboard")
    print("=" * 65)
    uvicorn.run("calling_agent:app", host="0.0.0.0", port=port, reload=True)
