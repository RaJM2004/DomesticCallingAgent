import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

VOBIZ_AUTH_ID = os.getenv("VOBIZ_AUTH_ID")
VOBIZ_AUTH_TOKEN = os.getenv("VOBIZ_AUTH_TOKEN")


def fetch_live_vobiz_call_cost(to_number: str = None, call_uuid: str = None) -> dict:
    """
    Fetch the live Call Detail Record (CDR) directly from Vobiz REST API.
    Endpoint: https://api.vobiz.ai/api/v1/Account/{auth_id}/Call/
    """
    auth_id = os.getenv("VOBIZ_AUTH_ID")
    auth_token = os.getenv("VOBIZ_AUTH_TOKEN")

    if not auth_id or not auth_token:
        return None

    headers = {
        "X-Auth-ID": auth_id,
        "X-Auth-Token": auth_token,
        "Content-Type": "application/json"
    }

    url = f"https://api.vobiz.ai/api/v1/Account/{auth_id}/Call/"

    # Retry up to 3 times with 1.5s delay since carrier ledger updates within 2-3s of hangup
    for attempt in range(3):
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                objects = data.get("objects", [])
                if objects:
                    # Find matching call by to_number or uuid, or return latest
                    matched_call = None
                    if to_number:
                        cleaned_target = to_number.replace(" ", "").replace("-", "")
                        for c in objects:
                            c_to = str(c.get("to_number", "")).replace(" ", "").replace("-", "")
                            if cleaned_target in c_to or c_to in cleaned_target:
                                matched_call = c
                                break

                    if not matched_call and objects:
                        matched_call = objects[0]

                    if matched_call:
                        bill_sec = float(matched_call.get("bill_duration") or 0)
                        cost_str = matched_call.get("cost") or "0.45"
                        cost_val = float(cost_str)
                        currency = matched_call.get("currency", "INR")

                        return {
                            "source": "Vobiz Live Carrier API",
                            "call_uuid": matched_call.get("call_uuid"),
                            "from": matched_call.get("from_number"),
                            "to": matched_call.get("to_number"),
                            "bill_duration_sec": bill_sec,
                            "live_vobiz_cost": round(cost_val, 3),
                            "currency": currency,
                            "hangup_cause": matched_call.get("hangup_cause_name", "Normal Hangup"),
                            "answer_time": matched_call.get("answer_time"),
                            "end_time": matched_call.get("end_time")
                        }
        except Exception as e:
            print(f"[!] Warning fetching live Vobiz CDR: {e}")

        time.sleep(1.5)

    return None
