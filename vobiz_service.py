import os
import requests
import asyncio
from dotenv import load_dotenv

load_dotenv()

VOBIZ_AUTH_ID = os.getenv("VOBIZ_AUTH_ID", "MA_SB41BBZ8")
VOBIZ_AUTH_TOKEN = os.getenv("VOBIZ_AUTH_TOKEN", "t3ItE037RVn814BMcFhmrdJ2usXNDpRQ8NqVQi1VhlZzJJpk5jYX2s7ZdQRWtYBz")
VOBIZ_OUTBOUND_NUMBER = os.getenv("VOBIZ_OUTBOUND_NUMBER", "+917965853227")
OUTBOUND_TRUNK_ID = os.getenv("OUTBOUND_TRUNK_ID", "ST_z4V2wYPm5ar3")
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://localhost:8000").rstrip("/")


def get_vobiz_account_details() -> dict:
    """
    Fetch REAL-TIME account status, live cash credits balance, and CDR directly from Vobiz REST API.
    Live Balance Endpoint: https://api.vobiz.ai/api/v1/accounts/{auth_id}
    Live Calls Endpoint:    https://api.vobiz.ai/api/v1/Account/{auth_id}/Call/
    """
    auth_id = os.getenv("VOBIZ_AUTH_ID", VOBIZ_AUTH_ID)
    auth_token = os.getenv("VOBIZ_AUTH_TOKEN", VOBIZ_AUTH_TOKEN)

    if not auth_id or not auth_token:
        return {
            "status": "unconfigured",
            "connected": False,
            "cash_credits": "0.00",
            "total_calls": 0,
            "total_spent_inr": 0.0,
            "recent_calls": []
        }

    headers = {
        "X-Auth-ID": auth_id,
        "X-Auth-Token": auth_token,
        "Content-Type": "application/json"
    }

    # 1. Fetch exact live cash balance from Vobiz
    live_cash_credits = "0.00"
    account_name = "Vobiz Enterprise"
    pricing_rate = "0.4500"
    pricing_tier_name = "Base Tier - New - KYC"
    billing_increment_sec = 60
    currency = "INR"

    account_url = f"https://api.vobiz.ai/api/v1/accounts/{auth_id}"
    try:
        acc_res = requests.get(account_url, headers=headers, timeout=5)
        if acc_res.status_code == 200:
            acc_data = acc_res.json()
            raw_cash = acc_data.get("cash_credits") or "0.00"
            live_cash_credits = f"{float(raw_cash):.2f}"
            account_name = acc_data.get("name", "AMMAR RAZA")
            pricing_info = acc_data.get("pricing_tier", {})
            pricing_rate = pricing_info.get("rate_per_minute", "0.4500")
            pricing_tier_name = pricing_info.get("name", "Base Tier - New - KYC")
            billing_increment_sec = pricing_info.get("billing_increment_seconds", 60)
            currency = pricing_info.get("currency", "INR")
    except Exception as e:
        print(f"[!] Warning fetching live Vobiz account balance: {e}")

    # 2. Fetch live CDR (calls ledger)
    cdr_url = f"https://api.vobiz.ai/api/v1/Account/{auth_id}/Call/"
    total_count = 0
    total_spent = 0.0
    total_duration_sec = 0.0
    recent_calls = []

    try:
        cdr_res = requests.get(cdr_url, headers=headers, timeout=5)
        if cdr_res.status_code == 200:
            cdr_data = cdr_res.json()
            objects = cdr_data.get("objects", [])
            total_count = cdr_data.get("meta", {}).get("total_count", len(objects))

            for c in objects:
                try:
                    cost_val = float(c.get("cost") or 0.45)
                except Exception:
                    cost_val = 0.45
                total_spent += cost_val

                try:
                    dur_val = float(c.get("bill_duration") or 0)
                except Exception:
                    dur_val = 0
                total_duration_sec += dur_val

                recent_calls.append({
                    "call_uuid": c.get("call_uuid"),
                    "from_number": c.get("from_number"),
                    "to_number": c.get("to_number"),
                    "duration": dur_val,
                    "cost": round(cost_val, 2),
                    "hangup_cause": c.get("hangup_cause_name", "Normal Hangup"),
                    "time": c.get("answer_time") or c.get("initiation_time") or ""
                })
    except Exception as e:
        print(f"[!] Warning fetching live Vobiz CDR: {e}")

    return {
        "status": "connected",
        "connected": True,
        "auth_id": auth_id,
        "account_name": account_name,
        "caller_id": VOBIZ_OUTBOUND_NUMBER,
        "cash_credits": live_cash_credits,
        "currency": currency,
        "wholesale_rate": pricing_rate,
        "pricing_tier_name": pricing_tier_name,
        "billing_increment_sec": billing_increment_sec,
        "total_calls": total_count,
        "total_spent_inr": round(total_spent, 2),
        "total_duration_sec": round(total_duration_sec, 1),
        "recent_calls": recent_calls[:10]
    }


def trigger_vobiz_outbound_call(to_number: str, webhook_base_url: str = None) -> dict:
    """
    Triggers an outbound phone call:
    - If base_url is localhost, initiates via LiveKit Vobiz SIP Trunk (works with zero public tunnel).
    - If base_url is public (Railway/ngrok), initiates via native Vobiz REST API.
    """
    auth_id = os.getenv("VOBIZ_AUTH_ID", VOBIZ_AUTH_ID)
    auth_token = os.getenv("VOBIZ_AUTH_TOKEN", VOBIZ_AUTH_TOKEN)
    from_number = os.getenv("VOBIZ_OUTBOUND_NUMBER", VOBIZ_OUTBOUND_NUMBER)
    base_url = (webhook_base_url or os.getenv("SERVER_BASE_URL", SERVER_BASE_URL)).rstrip("/")

    # Format phone
    cleaned = to_number.strip().replace(" ", "").replace("-", "")
    if not cleaned.startswith("+"):
        if len(cleaned) == 10:
            cleaned = "+91" + cleaned
        else:
            cleaned = "+" + cleaned

    # Check if local development without public tunnel
    is_localhost = any(h in base_url for h in ["localhost", "127.0.0.1", "0.0.0.0"])

    if is_localhost and LIVEKIT_URL and OUTBOUND_TRUNK_ID:
        try:
            from make_call import call_via_livekit_sip
            res = asyncio.run(call_via_livekit_sip(cleaned))
            if res.get("status") == "success":
                return {
                    "success": True,
                    "status_code": 200,
                    "call_uuid": res.get("sip_call_id") or res.get("participant_id"),
                    "data": res,
                    "phone": cleaned
                }
            else:
                return {
                    "success": False,
                    "error": res.get("message", "SIP initiation failed"),
                    "phone": cleaned
                }
        except Exception as e:
            print(f"[!] LiveKit SIP Trunk fallback error: {e}")

    # Otherwise, use native Vobiz REST API
    url = f"https://api.vobiz.ai/api/v1/Account/{auth_id}/Call/"
    headers = {
        "Content-Type": "application/json",
        "X-Auth-ID": auth_id,
        "X-Auth-Token": auth_token
    }

    answer_url = f"{base_url}/call/incoming"
    hangup_url = f"{base_url}/call/status"

    payload = {
        "from": from_number,
        "to": cleaned,
        "answer_url": answer_url,
        "answer_method": "POST",
        "hangup_url": hangup_url,
        "hangup_method": "POST"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        data = {}
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        call_uuid = data.get("request_uuid") or data.get("call_uuid") or ""

        return {
            "success": response.status_code in [200, 201, 202],
            "status_code": response.status_code,
            "call_uuid": call_uuid,
            "data": data,
            "phone": cleaned
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "phone": cleaned
        }


def hangup_vobiz_call(call_uuid: str) -> bool:
    """
    Force hangup a live call via Vobiz REST API.
    """
    if not call_uuid:
        return False
    auth_id = os.getenv("VOBIZ_AUTH_ID", VOBIZ_AUTH_ID)
    auth_token = os.getenv("VOBIZ_AUTH_TOKEN", VOBIZ_AUTH_TOKEN)
    url = f"https://api.vobiz.ai/api/v1/Account/{auth_id}/Call/{call_uuid}/"
    headers = {
        "X-Auth-ID": auth_id,
        "X-Auth-Token": auth_token
    }
    try:
        r = requests.delete(url, headers=headers, timeout=5)
        return r.status_code in [200, 204]
    except Exception as e:
        print(f"[!] Error hanging up call {call_uuid}: {e}")
        return False
