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
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from sqlalchemy.orm import Session

from database import (
    init_db, get_db, SessionLocal, Account, Campaign, CallRecord,
    hash_password, verify_password, generate_api_token
)
from dialer_engine import start_campaign_dialer, pause_campaign_dialer, stop_campaign_dialer
from vobiz_service import get_vobiz_account_details

load_dotenv()

# Timezone Configuration (Indian Standard Time: UTC+05:30)
try:
    IST_TZ = ZoneInfo("Asia/Kolkata")
except Exception:
    IST_TZ = timezone.utc

def format_datetime_ist(dt: Optional[datetime], fmt: str = "%I:%M:%S %p") -> str:
    """Converts UTC datetime from database into localized IST string."""
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST_TZ).strftime(fmt)

def format_datetime_iso(dt: Optional[datetime]) -> str:
    """Formats datetime as ISO 8601 UTC string for client-side localization."""
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

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
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

# Mount static and audio directories
app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://localhost:8000").rstrip("/")
VOBIZ_PER_MINUTE_RATE = float(os.getenv("VOBIZ_PER_MINUTE_RATE", 0.45))  # INR 0.45 carrier rate
VOBIZ_OUTBOUND_NUMBER = os.getenv("VOBIZ_OUTBOUND_NUMBER", "+917965853227")


# ==========================================
# AUTH & USER PYDANTIC MODELS
# ==========================================
class LoginModel(BaseModel):
    username: str
    password: str

class TokenLoginModel(BaseModel):
    token: str

class CreateUserModel(BaseModel):
    username: str
    password: str
    name: str = "Client User"
    email: str = "user@example.com"
    role: str = "client"
    credits: float = 5000.0

class UserCreditUpdateModel(BaseModel):
    credits: float

class ResetPasswordModel(BaseModel):
    new_password: str

class CreditUpdateModel(BaseModel):
    credits: float

class CreditAddModel(BaseModel):
    amount: float

class WalletRechargeModel(BaseModel):
    amount: float


# ==========================================
# AUTH DEPENDENCIES
# ==========================================
def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[Account]:
    """Retrieve logged-in user from HTTP-only cookie, Bearer header, or X-API-Token."""
    token = request.cookies.get("vobiz_session_token")
    if not token:
        auth_hdr = request.headers.get("Authorization")
        if auth_hdr and auth_hdr.startswith("Bearer "):
            token = auth_hdr.split(" ", 1)[1].strip()
    if not token:
        token = request.headers.get("X-API-Token")
    if not token:
        return None
    return db.query(Account).filter(Account.api_token == token, Account.is_active == 1).first()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Account:
    """Strict dependency for protected routes; raises 401 if unauthenticated."""
    user = get_current_user_optional(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in."
        )
    return user


def require_admin(user: Account = Depends(get_current_user)) -> Account:
    """Strict dependency for admin-only routes; raises 403 if role is not admin."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required."
        )
    return user


# ==========================================
# 1. FRONTEND DASHBOARDS (ROLE-BASED & PROTECTED)
# ==========================================
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    """Render login UI. If already authenticated, redirect to proper dashboard."""
    user = get_current_user_optional(request, db)
    if user:
        if user.role == "admin":
            return RedirectResponse(url="/admin", status_code=302)
        return RedirectResponse(url="/", status_code=302)
    html_file = TEMPLATES_DIR / "login.html"
    if html_file.exists():
        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Login template not found.</h1>"


@app.get("/", response_class=HTMLResponse)
def user_portal(request: Request, db: Session = Depends(get_db)):
    """Client / User Interface: Upload 30k numbers, auto-dialer, credit view, response logs."""
    user = get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    html_file = TEMPLATES_DIR / "user.html"
    if html_file.exists():
        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()
            content = content.replace("{{USER_NAME}}", user.name or user.username or "User")
            content = content.replace("{{USER_ROLE}}", user.role)
            return content
    return "<h1>User portal template not found.</h1>"


@app.get("/admin", response_class=HTMLResponse)
def admin_portal(request: Request, db: Session = Depends(get_db)):
    """Dedicated Admin Panel: Vobiz wholesale balance, carrier cost ledger, client credit allocation."""
    user = get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/login?next=/admin", status_code=302)
    if user.role != "admin":
        return RedirectResponse(url="/", status_code=302)
    html_file = TEMPLATES_DIR / "admin.html"
    if html_file.exists():
        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()
            content = content.replace("{{ADMIN_NAME}}", user.name or user.username or "Admin")
            return content
    return "<h1>Admin portal template not found.</h1>"


@app.get("/logout")
def logout():
    """Clear session cookie and redirect to login page."""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="vobiz_session_token", path="/")
    return response


# ==========================================
# AUTHENTICATION API ENDPOINTS
# ==========================================
@app.post("/api/auth/login")
def api_login(data: LoginModel, response: Response, db: Session = Depends(get_db)):
    uname = data.username.strip()
    account = db.query(Account).filter(Account.username == uname).first()
    if not account or not verify_password(data.password, account.password_hash):
        raise HTTPException(status_code=400, detail="Invalid username or password.")
    if account.is_active == 0:
        raise HTTPException(status_code=403, detail="Account is disabled. Contact system administrator.")

    if not account.api_token:
        account.api_token = generate_api_token()
        db.commit()

    response.set_cookie(
        key="vobiz_session_token",
        value=account.api_token,
        max_age=30 * 86400,
        httponly=True,
        samesite="lax",
        path="/"
    )
    return {
        "status": "ok",
        "username": account.username,
        "name": account.name,
        "role": account.role,
        "redirect_url": "/admin" if account.role == "admin" else "/"
    }


@app.post("/api/auth/token-login")
def api_token_login(data: TokenLoginModel, response: Response, db: Session = Depends(get_db)):
    tok = data.token.strip()
    account = db.query(Account).filter(Account.api_token == tok).first()
    if not account:
        raise HTTPException(status_code=400, detail="Invalid or unrecognized access token.")
    if account.is_active == 0:
        raise HTTPException(status_code=403, detail="Account is disabled. Contact system administrator.")

    response.set_cookie(
        key="vobiz_session_token",
        value=account.api_token,
        max_age=30 * 86400,
        httponly=True,
        samesite="lax",
        path="/"
    )
    return {
        "status": "ok",
        "username": account.username,
        "name": account.name,
        "role": account.role,
        "redirect_url": "/admin" if account.role == "admin" else "/"
    }


@app.post("/api/auth/logout")
def api_logout(response: Response):
    response.delete_cookie(key="vobiz_session_token", path="/")
    return {"status": "ok", "message": "Logged out successfully"}


@app.get("/api/auth/me")
def api_me(user: Account = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "credits": user.credits,
        "total_calls_made": user.total_calls_made,
        "api_token": user.api_token
    }


# ==========================================
# ADMIN USER & TOKEN MANAGEMENT APIS
# ==========================================
@app.get("/api/admin/users")
def list_users(admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(Account).order_by(Account.id.asc()).all()
    return [
        {
            "id": u.id,
            "username": u.username or f"user_{u.id}",
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "credits": round(float(u.credits), 1),
            "total_calls_made": u.total_calls_made,
            "is_active": u.is_active if u.is_active is not None else 1,
            "api_token": u.api_token or "",
            "created_at": format_datetime_ist(u.created_at, "%d %b %Y") if u.created_at else ""
        }
        for u in users
    ]


@app.post("/api/admin/users")
def create_user(data: CreateUserModel, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    uname = data.username.strip().lower()
    if not uname:
        raise HTTPException(status_code=400, detail="Username is required.")
    
    existing = db.query(Account).filter(Account.username == uname).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Username '{uname}' already exists.")

    new_user = Account(
        name=data.name.strip() or uname.capitalize(),
        email=data.email.strip() or f"{uname}@example.com",
        username=uname,
        password_hash=hash_password(data.password),
        api_token=generate_api_token(),
        role=data.role if data.role in ["admin", "client"] else "client",
        credits=float(data.credits),
        is_active=1
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {
        "status": "ok",
        "message": f"User '{new_user.username}' created successfully.",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "name": new_user.name,
            "role": new_user.role,
            "credits": new_user.credits,
            "api_token": new_user.api_token
        }
    }


@app.post("/api/admin/users/{user_id}/credits")
def update_user_credits(user_id: int, data: UserCreditUpdateModel, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    target_user = db.query(Account).filter(Account.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")
    target_user.credits = float(data.credits)
    db.commit()
    return {"status": "ok", "user_id": user_id, "credits": target_user.credits}


@app.post("/api/admin/users/{user_id}/toggle-status")
def toggle_user_status(user_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    target_user = db.query(Account).filter(Account.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")
    if target_user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own admin account.")
    target_user.is_active = 0 if target_user.is_active == 1 else 1
    db.commit()
    return {"status": "ok", "user_id": user_id, "is_active": target_user.is_active}


@app.post("/api/admin/users/{user_id}/reset-password")
def reset_user_password(user_id: int, data: ResetPasswordModel, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    target_user = db.query(Account).filter(Account.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")
    if not data.new_password:
        raise HTTPException(status_code=400, detail="Password cannot be empty.")
    target_user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"status": "ok", "message": f"Password for '{target_user.username}' reset successfully."}


@app.post("/api/admin/users/{user_id}/regenerate-token")
def regenerate_user_token(user_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    target_user = db.query(Account).filter(Account.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")
    target_user.api_token = generate_api_token()
    db.commit()
    return {"status": "ok", "user_id": user_id, "api_token": target_user.api_token}


# ==========================================
# 2. EXCEL / CSV UPLOAD (Handles 30,000+ numbers)
# ==========================================
@app.post("/api/campaign/upload")
async def upload_campaign_file(
    file: UploadFile = File(...),
    course_type: str = "bca_internship",
    language: str = "en",
    user: Account = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    filename = file.filename or "uploaded_numbers"
    contents = await file.read()

    # Create new Campaign assigned to the logged-in user
    campaign_name = f"Campaign - {Path(filename).stem} ({datetime.now().strftime('%d %b %H:%M')})"
    campaign = Campaign(
        account_id=user.id,
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
async def start_campaign(
    campaign_id: int,
    request: Request,
    user: Account = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if user.role != "admin" and campaign.account_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to this campaign")
    if user.credits < 1.0:
        raise HTTPException(status_code=400, detail="Insufficient credits. Please contact admin to allocate credits.")

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
def pause_campaign(
    campaign_id: int,
    user: Account = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if user.role != "admin" and campaign.account_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    res = pause_campaign_dialer(campaign_id)
    return res

@app.post("/api/campaign/{campaign_id}/stop")
def stop_campaign(
    campaign_id: int,
    user: Account = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if user.role != "admin" and campaign.account_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    res = stop_campaign_dialer(campaign_id)
    return res

class CampaignConfigModel(BaseModel):
    course_type: str = "bca_internship"
    language: str = "en"

@app.post("/api/campaign/{campaign_id}/config")
def update_campaign_config(
    campaign_id: int,
    config: CampaignConfigModel,
    user: Account = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if user.role != "admin" and campaign.account_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
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
def list_campaigns(
    user: Account = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns campaigns belonging to authenticated user (or all if admin)."""
    if user.role == "admin":
        campaigns = db.query(Campaign).order_by(Campaign.id.desc()).all()
    else:
        campaigns = db.query(Campaign).filter(Campaign.account_id == user.id).order_by(Campaign.id.desc()).all()
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
            "created_at": format_datetime_ist(c.created_at, "%d %b %I:%M %p") if c.created_at else ""
        }
        for c in campaigns
    ]


@app.get("/api/campaign/{campaign_id}/status")
def get_campaign_status(
    campaign_id: str,
    user: Account = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    credits_left = user.credits
    total_calls_made = user.total_calls_made

    # Calculate overall lifetime totals across ALL campaigns for this user/client
    if user.role == "admin":
        user_camps = db.query(Campaign.id).all()
    else:
        user_camps = db.query(Campaign.id).filter(Campaign.account_id == user.id).all()

    user_camp_ids = [c[0] for c in user_camps]

    if user_camp_ids:
        overall_calls_q = db.query(CallRecord).filter(CallRecord.campaign_id.in_(user_camp_ids))
        overall_answered_count = overall_calls_q.filter(CallRecord.status.in_(["answered", "completed"])).count()
        overall_unanswered_count = overall_calls_q.filter(CallRecord.status.in_(["no-answer", "busy", "failed"])).count()
        overall_response_count = overall_calls_q.filter(CallRecord.dtmf_digit != "").count()
        overall_total_calls = overall_calls_q.filter(CallRecord.status.in_(["answered", "completed", "no-answer", "busy", "failed"])).count()
    else:
        overall_answered_count = 0
        overall_unanswered_count = 0
        overall_response_count = 0
        overall_total_calls = 0

    if campaign_id == "all":
        # Aggregate view of ALL campaigns for this user
        if user.role == "admin":
            all_records_q = db.query(CallRecord).order_by(CallRecord.id.desc())
        else:
            all_records_q = db.query(CallRecord).filter(CallRecord.campaign_id.in_(user_camp_ids)).order_by(CallRecord.id.desc()) if user_camp_ids else db.query(CallRecord).filter(False)

        all_records = all_records_q.all()
        records = all_records[:200]
        total_records = len(all_records)
        completed_records = overall_total_calls
        total_cost_inr = sum(r.carrier_cost_inr or 0.0 for r in all_records)

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
            "total_calls_made": overall_total_calls,
            "total_records": total_records,
            "completed_records": completed_records,
            "answered_count": overall_answered_count,
            "unanswered_count": overall_unanswered_count,
            "response_count": overall_response_count,
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
                    "called_at": format_datetime_ist(r.called_at, "%I:%M:%S %p"),
                    "called_at_iso": format_datetime_iso(r.called_at)
                }
                for r in records
            ]
        }

    # Otherwise fetch specific or latest campaign
    campaign = None
    if campaign_id in ["latest", "0", "", "undefined"]:
        if user.role == "admin":
            campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()
        else:
            campaign = db.query(Campaign).filter(Campaign.account_id == user.id).order_by(Campaign.id.desc()).first()
    else:
        try:
            cid = int(campaign_id)
            if user.role == "admin":
                campaign = db.query(Campaign).filter(Campaign.id == cid).first()
            else:
                campaign = db.query(Campaign).filter(Campaign.id == cid, Campaign.account_id == user.id).first()
        except ValueError:
            campaign = None

    if not campaign:
        if user.role == "admin":
            campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()
        else:
            campaign = db.query(Campaign).filter(Campaign.account_id == user.id).order_by(Campaign.id.desc()).first()

    if not campaign:
        return {
            "campaign": None,
            "credits": round(float(credits_left), 2) if credits_left is not None else 30000.0,
            "total_calls_made": overall_total_calls,
            "total_records": 0,
            "completed_records": 0,
            "answered_count": overall_answered_count,
            "unanswered_count": overall_unanswered_count,
            "response_count": overall_response_count,
            "total_cost_inr": 0.0,
            "records": []
        }

    campaign_records_q = db.query(CallRecord).filter(CallRecord.campaign_id == campaign.id)
    total_records = campaign_records_q.count()
    completed_records = campaign_records_q.filter(CallRecord.status.in_(["answered", "completed", "failed", "busy", "no-answer"])).count()
    campaign_cost_inr = sum(r.carrier_cost_inr or 0.0 for r in campaign_records_q.all())

    records = (
        campaign_records_q
        .order_by(CallRecord.id.desc())
        .limit(200)
        .all()
    )

    return {
        "campaign": {
            "id": campaign.id,
            "name": campaign.name,
            "status": campaign.status,
            "course_type": campaign.course_type or "bca_internship",
            "language": campaign.language or "en",
            "file_name": campaign.file_name,
            "created_at": format_datetime_ist(campaign.created_at, "%d %b %Y, %I:%M %p") if campaign.created_at else ""
        },
        "credits": round(float(credits_left), 2) if credits_left is not None else 30000.0,
        "total_calls_made": overall_total_calls,
        "total_records": total_records,  # Variable based on active spreadsheet
        "completed_records": completed_records,  # Progress of active spreadsheet
        "answered_count": overall_answered_count,  # Total calls answered across all sheets
        "unanswered_count": overall_unanswered_count,  # Total calls unanswered across all sheets
        "response_count": overall_response_count,  # Total responses captured across all sheets
        "total_cost_inr": round(campaign_cost_inr, 2),
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
                "called_at": format_datetime_ist(r.called_at, "%I:%M:%S %p"),
                "called_at_iso": format_datetime_iso(r.called_at)
            }
            for r in records
        ]
    }


# ==========================================
# 5. EXPORT ANNOTATED RESPONSES TO EXCEL (.xlsx)
# ==========================================
@app.get("/api/campaign/{campaign_id}/export-excel")
def export_campaign_excel(
    campaign_id: str,
    user: Account = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if campaign_id == "all":
        if user.role == "admin":
            records = db.query(CallRecord).order_by(CallRecord.id.desc()).all()
        else:
            records = db.query(CallRecord).join(Campaign).filter(Campaign.account_id == user.id).order_by(CallRecord.id.desc()).all()
        file_label = "all_campaigns"
    elif campaign_id in ["latest", "0", ""]:
        if user.role == "admin":
            campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()
        else:
            campaign = db.query(Campaign).filter(Campaign.account_id == user.id).order_by(Campaign.id.desc()).first()
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
            raise HTTPException(status_code=404, detail="Campaign not found")
        if user.role != "admin" and campaign.account_id != user.id:
            raise HTTPException(status_code=403, detail="Unauthorized access to this campaign export")
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
            format_datetime_ist(r.called_at, "%Y-%m-%d %I:%M:%S %p") if r.called_at else "—"
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
def update_credits(data: CreditUpdateModel, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.role == "client").first()
    if account:
        account.credits = data.credits
        db.commit()
        return {"status": "ok", "credits": account.credits}
    return {"status": "error", "message": "Account not found"}

@app.post("/api/account/credits/add")
def add_credits(data: CreditAddModel, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
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
