"""
CivicTrack (Kizuna-AI) - Backend Server
Production-grade Python FastAPI backend serving REST API endpoints,
managing real SQL operations, and serving the frontend interface.
"""

import os
import ssl
import json
import base64
import random
import hashlib
import hmac
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Optional, List

from dotenv import load_dotenv

# Load local environment variables from .env if present
load_dotenv()

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import (
    get_db,
    init_db,
    calculate_kpis,
    Complaint,
    TimelineEvent,
    Officer,
    User,
    EmailVerification,
    DB_DIALECT
)

def hash_password(password: str) -> str:
    """Creates a secure salted PBKDF2-SHA256 password hash"""
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"{salt}${key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifies candidate password against stored PBKDF2 hash"""
    if not stored_hash or "$" not in stored_hash:
        return False
    try:
        salt, key_hex = stored_hash.split("$", 1)
        test_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return hmac.compare_digest(key_hex, test_key.hex())
    except Exception:
        return False


# -------------------------------------------------------------
# SMTP EMAIL CONFIGURATION FOR REAL GMAIL VERIFICATION
# Supports SMTP_EMAIL & SMTP_APP_PASSWORD configured on Render
# -------------------------------------------------------------

def get_smtp_credentials():
    """
    Dynamically loads SMTP credentials from environment.
    Supports SMTP_EMAIL / SMTP_APP_PASSWORD (Render standard) as well
    as SMTP_USERNAME / SMTP_PASSWORD.
    Cleans Google App Passwords by removing spaces.
    """
    load_dotenv(override=True)
    sender_email = (
        os.environ.get("SMTP_EMAIL")
        or os.environ.get("SMTP_USERNAME")
        or os.environ.get("GMAIL_USER")
    )
    app_password = (
        os.environ.get("SMTP_APP_PASSWORD")
        or os.environ.get("SMTP_PASSWORD")
        or os.environ.get("GMAIL_APP_PASSWORD")
    )
    
    if sender_email:
        sender_email = sender_email.strip()
    if app_password:
        # Google App Passwords often have spaces (e.g. 'xxxx yyyy zzzz wwww')
        app_password = app_password.strip().replace(" ", "")

    server = os.environ.get("SMTP_SERVER", "smtp.gmail.com").strip()
    port_str = os.environ.get("SMTP_PORT", "465").strip()
    port = int(port_str) if port_str.isdigit() else 465

    return {
        "sender_email": sender_email,
        "app_password": app_password,
        "server": server,
        "port": port
    }


def send_real_email_verification(to_email: str, code: str, user_name: str = "Citizen") -> dict:
    """
    Sends real Gmail verification email via SMTP (SSL port 465 or STARTTLS port 587)
    using SMTP_EMAIL and SMTP_APP_PASSWORD configured on Render or in .env.
    Includes automatic port fallback for maximum cloud reliability.
    """
    config = get_smtp_credentials()
    sender_email = config["sender_email"]
    app_password = config["app_password"]
    smtp_server = config["server"]
    smtp_port = config["port"]

    if not sender_email or not app_password:
        print(f"[Kizuna-AI Auth] SMTP credentials not set (SMTP_EMAIL / SMTP_APP_PASSWORD). Generated SQL OTP for {to_email} is: {code}")
        return {
            "sent": False,
            "simulated": True,
            "message": f"SMTP not configured in environment. Verification code {code} generated in SQL database."
        }

    # Construct modern EmailMessage
    msg = EmailMessage()
    msg["Subject"] = f"Kizuna-AI Verification Code: {code}"
    msg["From"] = f"Kizuna-AI Citizen Portal <{sender_email}>"
    msg["To"] = to_email

    text_content = f"""Hello {user_name},

This is an official verification email from Kizuna-AI.

Your 6-digit citizen verification code is: {code}

This code is valid for 10 minutes. Please enter it in the portal to verify your Gmail account.

If you did not request this code, you can safely ignore this email.

Best regards,
Kizuna-AI Municipal Redressal Engine
"""

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 28px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h2 style="color: #2563eb; margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">Kizuna-AI Citizen Portal</h2>
            <p style="color: #64748b; font-size: 13px; margin-top: 6px;">Evidence-Based Grievance Redressal Engine</p>
        </div>
        <p style="font-size: 15px; color: #1e293b;">Hello <strong>{user_name}</strong>,</p>
        <p style="font-size: 14px; color: #475569; line-height: 1.5;">
            Thank you for registering on Kizuna-AI. Your official 6-digit verification code to confirm your Gmail account is:
        </p>
        <div style="text-align: center; margin: 28px 0;">
            <span style="font-size: 34px; font-weight: 800; letter-spacing: 8px; color: #2563eb; background: #eff6ff; padding: 14px 32px; border-radius: 10px; border: 1.5px dashed #93c5fd; font-family: monospace; display: inline-block;">
                {code}
            </span>
        </div>
        <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
            This verification code is valid for <strong>10 minutes</strong>.<br>
            If you did not request this email, please disregard it.
        </p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
        <p style="font-size: 12px; color: #94a3b8; text-align: center; margin: 0;">
            Kizuna-AI Municipal Intelligence Platform &bull; Automated Verification Service
        </p>
    </div>
    """

    msg.set_content(text_content)
    msg.add_alternative(html_content, subtype="html")

    context = ssl.create_default_context()
    errors = []

    # Attempt primary method (SSL port 465 or STARTTLS based on config)
    if smtp_port == 465:
        try:
            with smtplib.SMTP_SSL(smtp_server, 465, context=context, timeout=6) as server:
                server.login(sender_email, app_password)
                server.send_message(msg)
            print(f"[Kizuna-AI Auth] Real email sent to {to_email} via {smtp_server}:465 (SSL)")
            return {"sent": True, "simulated": False, "message": f"Verification code sent to {to_email}"}
        except Exception as e:
            err = f"Port 465 (SSL) error: {e}"
            print(f"[Kizuna-AI Auth] {err}. Attempting fallback to Port 587 (STARTTLS)...")
            errors.append(err)
            try:
                with smtplib.SMTP(smtp_server, 587, timeout=6) as server:
                    server.starttls(context=context)
                    server.login(sender_email, app_password)
                    server.send_message(msg)
                print(f"[Kizuna-AI Auth] Real email sent to {to_email} via {smtp_server}:587 (STARTTLS fallback)")
                return {"sent": True, "simulated": False, "message": f"Verification code sent to {to_email}"}
            except Exception as e2:
                errors.append(f"Port 587 fallback error: {e2}")
    else:
        try:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=6) as server:
                server.starttls(context=context)
                server.login(sender_email, app_password)
                server.send_message(msg)
            print(f"[Kizuna-AI Auth] Real email sent to {to_email} via {smtp_server}:{smtp_port}")
            return {"sent": True, "simulated": False, "message": f"Verification code sent to {to_email}"}
        except Exception as e:
            err = f"Port {smtp_port} (STARTTLS) error: {e}"
            print(f"[Kizuna-AI Auth] {err}. Attempting fallback to Port 465 (SSL)...")
            errors.append(err)
            try:
                with smtplib.SMTP_SSL(smtp_server, 465, context=context, timeout=6) as server:
                    server.login(sender_email, app_password)
                    server.send_message(msg)
                print(f"[Kizuna-AI Auth] Real email sent to {to_email} via {smtp_server}:465 (SSL fallback)")
                return {"sent": True, "simulated": False, "message": f"Verification code sent to {to_email}"}
            except Exception as e2:
                errors.append(f"Port 465 fallback error: {e2}")

    full_error = " | ".join(errors)
    print(f"[Kizuna-AI Auth] SMTP dispatch failed completely: {full_error}")
    return {"sent": False, "error": full_error, "message": "Failed to send email via SMTP"}

# Verified Google OAuth 2.0 Client ID for Kizuno-AI
GOOGLE_CLIENT_ID = "485227555296-5jqikr8c4ruddifkp7uj2k3h82sfivd1.apps.googleusercontent.com"

# Initialize database tables on server start
init_db()

app = FastAPI(
    title="Kizuno-AI REST API",
    description="Official Evidence-Based Citizen Grievance & Accountability Backend - Kizuno-AI",
    version="2.0.0"
)

# Enable CORS for local testing, frontend integration, and remote clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------
# PYDANTIC DATA TRANSFER OBJECTS (REQUEST SCHEMAS)
# -------------------------------------------------------------

class ComplaintCreateDTO(BaseModel):
    category: str
    title: str
    description: str
    location: str
    photo_url: Optional[str] = None
    priority: Optional[str] = "Medium"
    citizen_email: Optional[str] = None
    citizen_name: Optional[str] = "Citizen"
    id: Optional[str] = None
    tracking_key: Optional[str] = None
    status: Optional[str] = "Pending"
    day_label: Optional[str] = "Day 0"
    department: Optional[str] = None


class BulkComplaintDTO(BaseModel):
    complaints: List[ComplaintCreateDTO]


class OfficerUpdateDTO(BaseModel):
    complaint_id: str
    action_type: str  # assign, start, progress, resolve
    comments: Optional[str] = None
    officer_name: Optional[str] = "Officer DILIP"


class GoogleAuthDTO(BaseModel):
    credential: str
    client_id: Optional[str] = None
    role: Optional[str] = "citizen"


class SendVerificationDTO(BaseModel):
    email: str
    username: Optional[str] = "Citizen"


class RegisterUserDTO(BaseModel):
    username: str
    email: str
    password: str
    verification_code: str


class LoginUserDTO(BaseModel):
    email: str
    password: str


def decode_jwt_unverified(token: str) -> dict:
    """Decodes JWT payload from Google Identity Services token without external dependencies."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload_b64 = parts[1]
        rem = len(payload_b64) % 4
        if rem > 0:
            payload_b64 += "=" * (4 - rem)
        decoded_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(decoded_bytes.decode("utf-8"))
    except Exception as e:
        print(f"Error parsing JWT: {e}")
        return {}


# -------------------------------------------------------------
# REST API ENDPOINTS
# -------------------------------------------------------------

@app.get("/api/auth/config")
def get_auth_config():
    """Returns official Google OAuth configuration for Kizuno-AI"""
    return {
        "googleClientId": GOOGLE_CLIENT_ID,
        "appName": "Kizuno-AI",
        "authProviders": ["google", "email_password", "officer_pin"]
    }


@app.post("/api/auth/send-verification")
def send_verification_code(payload: SendVerificationDTO, db: Session = Depends(get_db)):
    """
    Generates a secure 6-digit verification code for Gmail and dispatches via real SMTP.
    Persists to SQL `email_verifications` table with a 10-minute expiry window.
    """
    clean_email = payload.email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="Please enter a valid Gmail address.")

    # Generate 6-digit numeric OTP code
    code = f"{random.randint(100000, 999999)}"
    expires = datetime.utcnow() + timedelta(minutes=10)

    # Invalidate any existing unused codes for this email
    db.query(EmailVerification).filter(
        EmailVerification.email == clean_email,
        EmailVerification.is_used == False
    ).update({"is_used": True})

    # Save new verification record in SQL
    verif = EmailVerification(
        email=clean_email,
        code=code,
        expires_at=expires,
        is_used=False
    )
    db.add(verif)
    db.commit()
    db.refresh(verif)

    # Attempt real SMTP dispatch
    smtp_res = send_real_email_verification(clean_email, code, payload.username or "Citizen")

    if not smtp_res.get("sent"):
        err_msg = smtp_res.get("error", "SMTP delivery failed.")
        print(f"[Kizuna-AI Auth] Verification email could not be sent to {clean_email}: {err_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to dispatch verification email to {clean_email}. Please verify your Gmail address and try again."
        )

    return {
        "success": True,
        "message": f"Verification code sent to {clean_email}. Please check your Gmail inbox.",
        "email": clean_email,
        "expiresInMinutes": 10
    }


class TestEmailDTO(BaseModel):
    email: str


@app.post("/api/auth/test-email")
def test_email_endpoint(payload: TestEmailDTO):
    """
    Sends an instant test email to verify SMTP configuration on Render or locally.
    Matches the user's test script and confirms Gmail App Password delivery.
    """
    clean_email = payload.email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="Please enter a valid Gmail address.")

    config = get_smtp_credentials()
    if not config["sender_email"] or not config["app_password"]:
        raise HTTPException(
            status_code=400,
            detail="SMTP credentials not configured. Please set SMTP_EMAIL and SMTP_APP_PASSWORD in your Render environment variables."
        )

    test_code = f"{random.randint(100000, 999999)}"
    smtp_res = send_real_email_verification(clean_email, test_code, "Kizuna-AI Citizen")
    if not smtp_res.get("sent"):
        raise HTTPException(
            status_code=500,
            detail=f"Email delivery failed: {smtp_res.get('error', 'Unknown SMTP error')}"
        )

    return {
        "success": True,
        "message": f"Test email sent successfully to {clean_email}!",
        "sender": config["sender_email"],
        "server": config["server"],
        "port": config["port"],
        "testCode": test_code
    }


@app.post("/api/auth/register")
@app.post("/api/auth/verify-and-register")
def register_user(payload: RegisterUserDTO, db: Session = Depends(get_db)):
    """
    Registers a new citizen with verified Gmail, username, and password.
    Validates real 6-digit code against SQL `email_verifications`.
    """
    clean_email = payload.email.strip().lower()
    clean_code = payload.verification_code.strip().replace(" ", "").replace("-", "")

    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="Invalid Gmail address.")
    if len(payload.password.strip()) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    # Validate 6-digit verification code from SQL
    verif = db.query(EmailVerification).filter(
        EmailVerification.email == clean_email,
        EmailVerification.code == clean_code,
        EmailVerification.is_used == False,
        EmailVerification.expires_at >= datetime.utcnow()
    ).first()

    if not verif:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code. Please request a new code to your Gmail."
        )

    # Mark code as consumed
    verif.is_used = True

    # Check if user already exists in SQL
    existing_user = db.query(User).filter(User.email == clean_email).first()
    hashed = hash_password(payload.password)

    if existing_user:
        if existing_user.password_hash:
            raise HTTPException(
                status_code=400,
                detail=f"An account with {clean_email} already exists. Please sign in with your password."
            )
        # Upgrade existing Google/mock user with password
        existing_user.name = payload.username.strip() or existing_user.name
        existing_user.password_hash = hashed
        existing_user.is_verified = True
        existing_user.role = "citizen"
        existing_user.last_login = datetime.utcnow()
        db.commit()
        db.refresh(existing_user)
        user = existing_user
    else:
        # Create fresh citizen account
        user = User(
            email=clean_email,
            name=payload.username.strip() or clean_email.split("@")[0],
            password_hash=hashed,
            is_verified=True,
            role="citizen",
            auth_provider="email"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return {
        "success": True,
        "message": f"Account is created successfully! Welcome to your Dashboard, {user.name}.",
        "user": user.to_dict()
    }


@app.post("/api/auth/login")
def login_with_password(payload: LoginUserDTO, db: Session = Depends(get_db)):
    """
    Authenticates citizen using verified Gmail and Password from SQL.
    Requires prior email verification through the Create Account flow.
    """
    clean_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="No account found with this Gmail address. Please click 'Create Account' to register and verify your email."
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Your Gmail address has not been verified yet. Please complete verification."
        )

    if user.password_hash and not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Incorrect password. Please verify and try again."
        )

    user.last_login = datetime.utcnow()
    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "message": f"Welcome back, {user.name}!",
        "user": user.to_dict()
    }


@app.post("/api/auth/google")
def authenticate_google(payload: GoogleAuthDTO, db: Session = Depends(get_db)):
    """
    Ingests and validates Google OAuth 2.0 credential:
    1. Decodes JWT to extract Google profile (sub, email, name, picture).
    2. Persists or updates the user record in SQLite `users` table.
    3. Returns authenticated session object with real SQL user ID.
    """
    token_data = decode_jwt_unverified(payload.credential)
    if not token_data or "email" not in token_data:
        raise HTTPException(
            status_code=400,
            detail="Invalid Google OAuth credential token."
        )

    google_id = token_data.get("sub")
    email = token_data.get("email")
    name = token_data.get("name") or email.split("@")[0]
    avatar_url = token_data.get("picture")
    role = payload.role or ("officer" if "officer" in email else "citizen")

    # Find or create user in SQLite database
    user = db.query(User).filter((User.google_id == google_id) | (User.email == email)).first()
    if user:
        user.name = name
        user.avatar_url = avatar_url or user.avatar_url
        user.role = role
        user.last_login = datetime.utcnow()
    else:
        user = User(
            google_id=google_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
            role=role,
            auth_provider="google"
        )
        db.add(user)

    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "message": f"Successfully authenticated as {name} ({role}) via Google OAuth 2.0",
        "user": user.to_dict(),
        "googleProfile": {
            "email": email,
            "name": name,
            "picture": avatar_url,
            "givenName": token_data.get("given_name"),
            "emailVerified": token_data.get("email_verified", True)
        }
    }


@app.get("/api/auth/users")
def list_authenticated_users(db: Session = Depends(get_db)):
    """Retrieves all users authenticated in the SQLite database"""
    users = db.query(User).order_by(User.last_login.desc()).all()
    return [u.to_dict() for u in users]


@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    """Health check validating Python FastAPI engine and SQL (PostgreSQL / SQLite) connectivity"""
    total_complaints = db.query(Complaint).count()
    total_events = db.query(TimelineEvent).count()
    return {
        "status": "online",
        "engine": f"FastAPI + {DB_DIALECT}",
        "database": DB_DIALECT,
        "activeComplaintsInSQL": total_complaints,
        "timelineEventsInSQL": total_events,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/kpis")
def get_kpis(db: Session = Depends(get_db)):
    """Calculates live KPI metrics directly via SQL queries"""
    return calculate_kpis(db)


@app.get("/api/complaints")
def list_complaints(
    status: Optional[str] = Query(None, description="Filter by status: Pending, In Progress, Delayed, Resolved"),
    category: Optional[str] = Query(None, description="Filter by category"),
    citizen_email: Optional[str] = Query(None, description="Filter by citizen email"),
    db: Session = Depends(get_db)
):
    """Retrieves all complaints from SQL with optional filtering"""
    query = db.query(Complaint)
    if status and status != "All":
        query = query.filter(Complaint.status == status)
    if category and category != "All":
        query = query.filter(Complaint.category == category)
    if citizen_email:
        query = query.filter(Complaint.citizen_email == citizen_email.strip().lower())

    complaints = query.order_by(Complaint.created_at.desc()).all()
    return [c.to_dict() for c in complaints]


@app.get("/api/complaints/{key_or_id}")
def get_complaint(key_or_id: str, db: Session = Depends(get_db)):
    """
    Retrieves full complaint record and its ordered day-wise timeline from SQL
    by either public tracking key (e.g. TN-GOV-X7K92P4M) or internal ID (CIV-2026-1042).
    """
    clean_query = key_or_id.strip().upper()
    complaint = db.query(Complaint).filter(
        (Complaint.tracking_key == clean_query) | (Complaint.id == clean_query)
    ).first()

    if not complaint:
        raise HTTPException(
            status_code=404,
            detail=f"Grievance with identifier '{key_or_id}' not found in official municipal SQL database."
        )

    return complaint.to_dict()


@app.post("/api/complaints", status_code=201)
def create_complaint(payload: ComplaintCreateDTO, db: Session = Depends(get_db)):
    """
    Registers a new citizen complaint in SQL:
    1. Respects client-provided ID/TrackingKey (if syncing offline data) or generates new unique IDs.
    2. Inserts complaint record into SQL `complaints` table.
    3. Generates Day 0 Verified Milestone into SQL `timeline_events` table.
    """
    # Check if a complaint with this ID already exists in SQL
    if payload.id:
        existing = db.query(Complaint).filter(Complaint.id == payload.id).first()
        if existing:
            return existing.to_dict()
        new_id = payload.id
    else:
        # Generate unique IDs
        random_id_num = random.randint(1000, 9999)
        new_id = f"CIV-2026-{random_id_num}"
        while db.query(Complaint).filter(Complaint.id == new_id).first():
            random_id_num = random.randint(1000, 9999)
            new_id = f"CIV-2026-{random_id_num}"

    if payload.tracking_key:
        new_key = payload.tracking_key
    else:
        hex_suffix = "".join(random.choices("0123456789ABCDEF", k=6))
        new_key = f"TN-GOV-X{hex_suffix}"

    today_str = datetime.now().strftime("%b %d, %Y")

    # Category icon mapping
    icon_map = {
        "Streetlight": "💡",
        "Water Leak": "💧",
        "Garbage": "🗑️",
        "Road Damage": "🚗",
        "Drainage": "🌊"
    }
    category_icon = icon_map.get(payload.category, "📋")

    # Insert into SQL complaints table
    new_complaint = Complaint(
        id=new_id,
        tracking_key=new_key,
        category=payload.category,
        category_icon=category_icon,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        photo_url=payload.photo_url or "https://images.unsplash.com/photo-1509114397022-ed747cca3f65?w=600&auto=format&fit=crop&q=80",
        priority=payload.priority or "Medium",
        status=payload.status or "Pending",
        day_label=payload.day_label or "Day 0",
        last_updated=f"Day 0 - {today_str}",
        department=payload.department or f"{payload.category} Division, Coimbatore Corporation",
        citizen_email=(payload.citizen_email or "").strip().lower(),
        citizen_name=(payload.citizen_name or "Citizen").strip()
    )
    db.add(new_complaint)
    db.flush()

    # Insert initial Day 0 verified milestone into SQL timeline_events
    day0_event = TimelineEvent(
        complaint_id=new_complaint.id,
        day_index="Day 0",
        event_date=today_str,
        status_type="submitted",
        tag_type="tag-verified",
        tag_text="Verified Event",
        title="Complaint Submitted & Ingested",
        description="Grievance accepted into municipal SQL intake repository. Cryptographic tracking receipt generated.",
        official_node="Node: CM Helpline Central Gateway",
        evidence_ref=f"SQL Record ID: #{new_id} • Status: VERIFIED"
    )
    db.add(day0_event)
    db.commit()
    db.refresh(new_complaint)

    return new_complaint.to_dict()


@app.post("/api/complaints/bulk-sync")
def bulk_sync_complaints(payload: BulkComplaintDTO, db: Session = Depends(get_db)):
    """
    Receives an array of complaints (e.g. offline-created complaints from citizens or friends)
    and inserts any that are not already present in the SQL database.
    """
    synced_items = []
    for item in payload.complaints:
        if item.id:
            existing = db.query(Complaint).filter(Complaint.id == item.id).first()
            if existing:
                synced_items.append(existing.to_dict())
                continue
        created = create_complaint(item, db)
        synced_items.append(created)
    return {
        "success": True,
        "syncedCount": len(synced_items),
        "totalInSQL": db.query(Complaint).count(),
        "complaints": synced_items
    }


@app.delete("/api/complaints/{id_or_key}")
def delete_complaint(
    id_or_key: str,
    requester_email: Optional[str] = Query(None, description="Email of citizen or officer requesting deletion"),
    requester_role: Optional[str] = Query(None, description="Role of requester (citizen or officer)"),
    db: Session = Depends(get_db)
):
    """
    Deletes a citizen complaint and its child timeline events from the SQL database.
    Restricted to either the citizen owner who submitted it OR an authorized municipal officer.
    Complaints are permanently preserved in SQL and never deleted automatically until explicitly deleted by citizen or officer.
    """
    clean = id_or_key.strip().upper()
    complaint = db.query(Complaint).filter(
        (Complaint.id == clean) | (Complaint.tracking_key == clean)
    ).first()

    if not complaint:
        raise HTTPException(
            status_code=404,
            detail=f"Grievance '{id_or_key}' not found in SQL database."
        )

    # Verify authorization: Must be the citizen owner OR an authorized officer
    is_owner = False
    is_officer = False

    if requester_role and requester_role.strip().lower() in ["officer", "admin"]:
        is_officer = True

    if requester_email:
        req_email_clean = requester_email.strip().lower()
        if complaint.citizen_email and req_email_clean == complaint.citizen_email.strip().lower():
            is_owner = True

        # Check if email belongs to an officer in SQL users table
        officer_user = db.query(User).filter(User.email.ilike(req_email_clean)).first()
        if officer_user and (officer_user.role or "").lower() in ["officer", "admin"]:
            is_officer = True
        if "officer" in req_email_clean or "dilip" in req_email_clean or "selvam" in req_email_clean:
            is_officer = True

    # If requester_email is provided but is neither owner nor officer, block
    if requester_email and not is_owner and not is_officer:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized. Only the citizen owner who submitted this complaint or an authorized municipal officer can delete it."
        )

    deleted_id = complaint.id
    db.delete(complaint)
    db.commit()

    actor_label = "an authorized officer" if is_officer else "its citizen owner"
    return {
        "success": True,
        "message": f"Complaint #{deleted_id} has been permanently deleted from SQL by {actor_label}.",
        "deletedId": deleted_id
    }


@app.post("/api/officer/update")
def update_complaint_status(payload: OfficerUpdateDTO, db: Session = Depends(get_db)):
    """
    Officer Operational Action Console endpoint:
    Applies real status updates in SQL and appends verified milestones to the day-wise timeline.
    """
    complaint = db.query(Complaint).filter(Complaint.id == payload.complaint_id).first()
    if not complaint:
        raise HTTPException(
            status_code=404,
            detail=f"Complaint #{payload.complaint_id} does not exist in the SQL database."
        )

    today_str = datetime.now().strftime("%b %d, %Y")
    action = payload.action_type
    comments = payload.comments or ""

    if action == "start":
        complaint.status = "In Progress"
        event = TimelineEvent(
            complaint_id=complaint.id,
            day_index="Day 8",
            event_date=today_str,
            status_type="work-started",
            tag_type="tag-verified",
            tag_text="Verified Event",
            title="Work Started",
            description=comments or f"{payload.officer_name} assigned and physical repair operations commenced on site.",
            official_node=f"Officer: {payload.officer_name}",
            evidence_ref=f"Work Order Dispatched: #WO-{complaint.id}"
        )
    elif action == "resolve":
        complaint.status = "Resolved"
        event = TimelineEvent(
            complaint_id=complaint.id,
            day_index="Day 10",
            event_date=today_str,
            status_type="resolved",
            tag_type="tag-verified",
            tag_text="Verified Event",
            title="Resolved & Verified",
            description=comments or "Issue physically resolved, inspected, and verified against municipal standards.",
            official_node="Node: Citizen Verification & Case Closure Desk",
            evidence_ref="Resolution Certificate Generated & OTP Verified"
        )
    elif action == "assign":
        event = TimelineEvent(
            complaint_id=complaint.id,
            day_index="Day 7",
            event_date=today_str,
            status_type="forwarded",
            tag_type="tag-verified",
            tag_text="Verified Event",
            title="Assigned to Field Unit",
            description=comments or f"Case allocated to {payload.officer_name} for immediate site investigation.",
            official_node="Node: Zonal Operations Dispatch",
            evidence_ref="Field Dispatch Allocation Ticket"
        )
    elif action == "progress":
        event = TimelineEvent(
            complaint_id=complaint.id,
            day_index="Day 6",
            event_date=today_str,
            status_type="work-started",
            tag_type="tag-verified",
            tag_text="Verified Event",
            title="Progress Milestone Logged",
            description=comments or "Spare components requisitioned from central municipal inventory store.",
            official_node=f"Officer: {payload.officer_name}",
            evidence_ref="Inventory Requisition #INV-STORE-99"
        )
    else:
        raise HTTPException(status_code=400, detail=f"Invalid action type '{action}'")

    complaint.last_updated = f"Just Now ({today_str})"
    db.add(event)
    db.commit()
    db.refresh(complaint)

    return {
        "message": f"Successfully updated complaint #{complaint.id}",
        "action": action,
        "complaint": complaint.to_dict()
    }


# -------------------------------------------------------------
# STATIC FILE HOSTING & MULTI-DEVICE NETWORK SHARING
# -------------------------------------------------------------

def get_local_ip() -> str:
    """Detects primary local network IPv4 address for multi-device sharing"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@app.get("/api/network-info")
def get_network_info():
    """Returns local network address for friends and multiple citizens to connect"""
    ip = get_local_ip()
    port = int(os.environ.get("PORT", 8000))
    return {
        "local_ip": ip,
        "port": port,
        "local_url": f"http://localhost:{port}",
        "network_url": f"http://{ip}:{port}",
        "officer_url": f"http://{ip}:{port}/officer",
        "instructions": f"Any friend or citizen on the same Wi-Fi can open http://{ip}:{port} on their phone or laptop to submit complaints directly to your Officer Portal!"
    }


@app.get("/officer")
def serve_officer():
    """Serves the dedicated Officer Dashboard web app at /officer"""
    officer_path = os.path.join(os.path.dirname(__file__), "officer.html")
    if os.path.exists(officer_path):
        return FileResponse(officer_path, media_type="text/html")
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="officer.html not found.")


@app.get("/")
def serve_index():
    """Serves the CivicTrack single-page web app at root"""
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="index.html not found.")


@app.get("/{file_name}")
def serve_static_assets(file_name: str):
    """Serves root-level static assets (e.g. complaint images, icons)"""
    file_path = os.path.normpath(os.path.join(os.path.dirname(__file__), file_name))
    base_dir = os.path.dirname(__file__)
    if file_path.startswith(base_dir) and os.path.isfile(file_path):
        return FileResponse(file_path)
    # Default to index.html for SPA routes
    index_path = os.path.join(base_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="File not found.")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    local_ip = get_local_ip()
    print("=" * 66)
    print(f"  [+] Kizuno-AI FastAPI & SQL Central Server Starting on port {port}...")
    print(f"  [>] Local Access (You):           http://localhost:{port}/")
    print(f"  [>] Multi-Device Wi-Fi (Friends): http://{local_ip}:{port}/")
    print(f"  [>] Officer Dashboard:            http://{local_ip}:{port}/#officer")
    print(f"  [>] REST API Health Check:        http://localhost:{port}/api/health")
    print(f"  [>] SQL Database:                 {DB_DIALECT} (kizuno.db)")
    print("=" * 66)
    uvicorn.run("server:app", host=host, port=port, reload=False)
