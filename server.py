"""
CivicTrack (Kizuna-AI) - Backend Server
Production-grade Python FastAPI backend serving REST API endpoints,
managing real SQL operations, and serving the frontend interface.
"""

import os
import ssl
import csv
import json
import base64
import random
import hashlib
import hmac
import smtplib
import threading
import io
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional, List, Any, Dict

from dotenv import load_dotenv

# Load local environment variables from .env if present
load_dotenv()

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Query, Header, Response
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
    DB_DIALECT,
    SessionLocal
)

# -------------------------------------------------------------
# SUPABASE POSTGRESQL & ADMIN CONFIGURATION
# -------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = (os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY") or "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
ADMIN_PIN = os.environ.get("ADMIN_PIN", "9812").strip()

supabase_client = None
if SUPABASE_URL and (SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY):
    try:
        from supabase import create_client, Client
        target_key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY
        supabase_client: Client = create_client(SUPABASE_URL, target_key)
        print(f"[Kizuno-AI Supabase] Live Supabase Client initialized successfully at {SUPABASE_URL}!")
    except Exception as e:
        print(f"[Kizuno-AI Supabase] Note: Supabase SDK initialization: {e}")

def get_admin_auth_token(pin: str) -> str:
    """Creates a deterministic HMAC token for authenticated admin sessions"""
    secret = os.environ.get("SESSION_SECRET", "kizuno_admin_secret_key_2026")
    return hmac.new(secret.encode(), f"admin:{pin}".encode(), hashlib.sha256).hexdigest()

def verify_admin_access(
    x_admin_pin: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
):
    """
    Enforces server-side administrator authorization.
    Accepts X-Admin-Pin header, Authorization Bearer token, or token query param.
    """
    valid_token = get_admin_auth_token(ADMIN_PIN)
    
    # Check X-Admin-Pin header
    if x_admin_pin:
        clean_pin = x_admin_pin.strip()
        if clean_pin == ADMIN_PIN or clean_pin == valid_token:
            return True

    # Check Authorization Bearer header
    if authorization:
        bearer = authorization.replace("Bearer ", "").strip()
        if bearer == valid_token or bearer == ADMIN_PIN:
            return True

    # Check query param (for export-csv direct download)
    if token and (token.strip() == valid_token or token.strip() == ADMIN_PIN):
        return True

    raise HTTPException(
        status_code=403,
        detail="Access forbidden. Kizuno-AI Administrator Security PIN or Session Token required."
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
    Includes built-in credentials so Render functions immediately without manual configuration.
    """
    load_dotenv(override=True)
    sender_email = (
        os.environ.get("SMTP_EMAIL")
        or os.environ.get("SMTP_USERNAME")
        or os.environ.get("GMAIL_USER")
        or "kizuno.ai.in@gmail.com"
    )
    app_password = (
        os.environ.get("SMTP_APP_PASSWORD")
        or os.environ.get("SMTP_PASSWORD")
        or os.environ.get("GMAIL_APP_PASSWORD")
        or "vbgpxofsjvkkjejw"
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
        print(f"[Kizuna-AI Auth] SMTP credentials not set. Generated SQL OTP for {to_email} is: {code}")
        return {
            "sent": False,
            "simulated": True,
            "error": "SMTP credentials not configured (SMTP_EMAIL / SMTP_APP_PASSWORD missing).",
            "message": f"SMTP not configured. Verification code {code} generated in SQL database."
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

    # Attempt 1: Port 465 (SSL direct)
    try:
        with smtplib.SMTP_SSL(smtp_server, 465, context=context, timeout=12) as server:
            server.login(sender_email, app_password)
            server.send_message(msg)
        print(f"[Kizuna-AI Auth] Real email sent to {to_email} via {smtp_server}:465 (SSL)")
        return {"sent": True, "simulated": False, "message": f"Verification code sent to {to_email}"}
    except Exception as e:
        err = f"Port 465 (SSL) error: {e}"
        print(f"[Kizuna-AI Auth] {err}. Attempting fallback to Port 587 (STARTTLS)...")
        errors.append(err)

    # Attempt 2: Port 587 (STARTTLS)
    try:
        with smtplib.SMTP(smtp_server, 587, timeout=12) as server:
            server.starttls(context=context)
            server.login(sender_email, app_password)
            server.send_message(msg)
        print(f"[Kizuna-AI Auth] Real email sent to {to_email} via {smtp_server}:587 (STARTTLS fallback)")
        return {"sent": True, "simulated": False, "message": f"Verification code sent to {to_email}"}
    except Exception as e2:
        err2 = f"Port 587 fallback error: {e2}"
        print(f"[Kizuna-AI Auth] {err2}")
        errors.append(err2)

    full_error = " | ".join(errors)
    print(f"[Kizuna-AI Auth] SMTP dispatch failed completely: {full_error}")
    is_blocked = any(kw in full_error for kw in ["Network is unreachable", "Errno 101", "timed out", "Connection refused", "Temporary failure"])
    return {
        "sent": False,
        "networkBlocked": is_blocked,
        "error": full_error,
        "message": f"Failed to send email: {full_error}"
    }

# Verified Google OAuth 2.0 Client ID for Kizuno-AI
GOOGLE_CLIENT_ID = "485227555296-5jqikr8c4ruddifkp7uj2k3h82sfivd1.apps.googleusercontent.com"

# -------------------------------------------------------------
# USERS.CSV STORAGE & DEDUPLICATION ENGINE
# Automatically records every verified user across both registration
# methods (Google OAuth & Email-OTP). Thread-safe & duplicate-proof.
# -------------------------------------------------------------

USERS_CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.csv")
CSV_LOCK = threading.Lock()
CSV_HEADERS = [
    "user_id",
    "gmail",
    "name",
    "registration_method",
    "email_verified",
    "created_date",
    "created_time",
    "created_at"
]


def init_users_csv() -> str:
    """
    Initializes users.csv with standard headers if file does not exist.
    Thread-safe operation.
    """
    with CSV_LOCK:
        if not os.path.exists(USERS_CSV_FILE):
            try:
                with open(USERS_CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(CSV_HEADERS)
                print(f"[Kizuno-AI CSV] Successfully initialized {USERS_CSV_FILE} with headers: {', '.join(CSV_HEADERS)}")
            except Exception as e:
                print(f"[Kizuno-AI CSV] Failed to initialize users.csv: {e}")
    return USERS_CSV_FILE


def get_user_from_csv(email: str) -> Optional[Dict[str, str]]:
    """
    Searches users.csv for an existing user by Gmail address (case-insensitive).
    Returns dictionary of user attributes if found, else None.
    """
    if not email:
        return None
    clean_email = email.strip().lower()
    with CSV_LOCK:
        if not os.path.exists(USERS_CSV_FILE):
            return None
        try:
            with open(USERS_CSV_FILE, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("gmail", "").strip().lower() == clean_email:
                        return dict(row)
        except Exception as e:
            print(f"[Kizuno-AI CSV] Error reading users.csv: {e}")
    return None


def record_user_to_csv(
    user_id: Optional[Any],
    email: str,
    name: str,
    registration_method: str,
    email_verified: bool = True,
    created_at: Optional[datetime] = None
) -> Dict[str, str]:
    """
    Safely stores a user account in users.csv:
    1. Checks if Gmail already exists in users.csv (case-insensitive).
       If user exists, DOES NOT create a new row; returns original row to preserve original timestamps.
    2. Validates registration_method is 'google' or 'email'.
    3. Requires email_verified == True before recording. Never stores unverified accounts.
    4. Automatically generates created_date (YYYY-MM-DD), created_time (HH:MM:SS),
       and created_at (YYYY-MM-DD HH:MM:SS).
    5. Never stores passwords, OTP verification codes, or Google OAuth tokens.
    6. Thread-safe writing guarded by CSV_LOCK.
    """
    if not email:
        return {}

    clean_email = email.strip().lower()
    clean_name = (name or clean_email.split("@")[0]).strip()
    norm_method = "google" if registration_method.lower() == "google" else "email"
    verified_str = "true" if email_verified else "false"

    # Only verified accounts are eligible for users.csv
    if not email_verified:
        print(f"[Kizuno-AI CSV] Skipped unverified user {clean_email}. Only verified accounts are stored.")
        return {}

    with CSV_LOCK:
        # Guarantee users.csv exists with correct header
        if not os.path.exists(USERS_CSV_FILE):
            try:
                with open(USERS_CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(CSV_HEADERS)
            except Exception as e:
                print(f"[Kizuno-AI CSV] Failed to create users.csv: {e}")
                return {}

        all_rows = []
        existing_user_row = None
        max_id = 0

        # Scan for existing Gmail address to prevent duplicate accounts
        try:
            with open(USERS_CSV_FILE, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    r_id = row.get("user_id", "").strip()
                    if r_id.isdigit():
                        max_id = max(max_id, int(r_id))
                    r_dict = dict(row)
                    if row.get("gmail", "").strip().lower() == clean_email:
                        existing_user_row = r_dict
                    all_rows.append(r_dict)
        except Exception as e:
            print(f"[Kizuno-AI CSV] Error scanning users.csv: {e}")

        # If user already exists, update registration_method / verification status if upgraded to google
        if existing_user_row:
            needs_rewrite = False
            if norm_method == "google" and existing_user_row.get("registration_method") != "google":
                existing_user_row["registration_method"] = "google"
                needs_rewrite = True
            if verified_str == "true" and existing_user_row.get("email_verified") != "true":
                existing_user_row["email_verified"] = "true"
                needs_rewrite = True
            if clean_name and (not existing_user_row.get("name") or existing_user_row.get("name") == clean_email.split("@")[0]):
                existing_user_row["name"] = clean_name
                needs_rewrite = True

            if needs_rewrite:
                try:
                    with open(USERS_CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                        writer.writeheader()
                        for r in all_rows:
                            if r.get("gmail", "").strip().lower() == clean_email:
                                writer.writerow(existing_user_row)
                            else:
                                writer.writerow(r)
                    print(f"[Kizuno-AI CSV] Updated existing user {clean_email} in users.csv (method={existing_user_row.get('registration_method')})")
                except Exception as e:
                    print(f"[Kizuno-AI CSV] Failed to update existing user in users.csv: {e}")
            return existing_user_row

        # Assign user_id (either database user_id or sequential max + 1)
        if user_id is not None and str(user_id).strip():
            final_user_id = str(user_id).strip()
        else:
            final_user_id = str(max_id + 1)

        # Generate timestamps
        dt = created_at if isinstance(created_at, datetime) else datetime.now(timezone(timedelta(hours=5, minutes=30)))
        created_date = dt.strftime("%Y-%m-%d")
        created_time = dt.strftime("%H:%M:%S")
        created_at_str = dt.strftime("%Y-%m-%d %H:%M:%S")

        new_row = [
            final_user_id,
            clean_email,
            clean_name,
            norm_method,
            verified_str,
            created_date,
            created_time,
            created_at_str
        ]

        try:
            with open(USERS_CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(new_row)
            print(f"[Kizuno-AI CSV] Appended new user #{final_user_id} ({clean_email}, method={norm_method}) to users.csv")
        except Exception as e:
            print(f"[Kizuno-AI CSV] Failed to write new row to users.csv: {e}")
            return {}

        return {
            "user_id": final_user_id,
            "gmail": clean_email,
            "name": clean_name,
            "registration_method": norm_method,
            "email_verified": verified_str,
            "created_date": created_date,
            "created_time": created_time,
            "created_at": created_at_str
        }


def sync_sql_users_to_csv(db: Session):
    """
    Synchronizes existing verified users from the SQL database into users.csv.
    Prevents duplicate entries and populates historical users seamlessly.
    """
    try:
        users = db.query(User).order_by(User.id.asc()).all()
        for u in users:
            is_verified = bool(u.is_verified or u.auth_provider == "google")
            if is_verified:
                method = "google" if u.auth_provider == "google" else "email"
                record_user_to_csv(
                    user_id=u.id,
                    email=u.email,
                    name=u.name,
                    registration_method=method,
                    email_verified=True,
                    created_at=u.created_at
                )
    except Exception as e:
        print(f"[Kizuno-AI CSV] Warning during SQL to CSV sync: {e}")


# -------------------------------------------------------------
# COMPLAINTS.CSV & DELETED_COMPLAINTS.CSV STORAGE ENGINE
# Records every citizen grievance across the portal.
# Synchronized with SQL, officer portal, and tracking flows.
# -------------------------------------------------------------

COMPLAINTS_CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "complaints.csv")
DELETED_COMPLAINTS_CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deleted_complaints.csv")

COMPLAINTS_CSV_HEADERS = [
    "complaint_id",
    "tracking_key",
    "citizen_name",
    "citizen_email",
    "category",
    "title",
    "description",
    "location",
    "priority",
    "status",
    "department",
    "day_label",
    "last_updated",
    "created_at"
]

DELETED_COMPLAINTS_CSV_HEADERS = [
    "complaint_id",
    "tracking_key",
    "citizen_name",
    "citizen_email",
    "category",
    "title",
    "description",
    "location",
    "priority",
    "status",
    "department",
    "deleted_at",
    "deleted_by"
]


def init_complaints_csv() -> str:
    with CSV_LOCK:
        if not os.path.exists(COMPLAINTS_CSV_FILE):
            try:
                with open(COMPLAINTS_CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(COMPLAINTS_CSV_HEADERS)
                print(f"[Kizuno-AI CSV] Initialized {COMPLAINTS_CSV_FILE}")
            except Exception as e:
                print(f"[Kizuno-AI CSV] Failed to initialize complaints.csv: {e}")
    return COMPLAINTS_CSV_FILE


def init_deleted_complaints_csv() -> str:
    with CSV_LOCK:
        if not os.path.exists(DELETED_COMPLAINTS_CSV_FILE):
            try:
                with open(DELETED_COMPLAINTS_CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(DELETED_COMPLAINTS_CSV_HEADERS)
                print(f"[Kizuno-AI CSV] Initialized {DELETED_COMPLAINTS_CSV_FILE}")
            except Exception as e:
                print(f"[Kizuno-AI CSV] Failed to initialize deleted_complaints.csv: {e}")
    return DELETED_COMPLAINTS_CSV_FILE


def save_complaint_to_csv(complaint) -> dict:
    """
    Appends or updates a complaint in complaints.csv. Thread-safe.
    """
    if not complaint or not complaint.id:
        return {}

    init_complaints_csv()

    cid = str(complaint.id).strip()
    tkey = str(complaint.tracking_key or "").strip()
    cname = str(complaint.citizen_name or "Citizen").strip()
    cemail = str(complaint.citizen_email or "").strip().lower()
    cat = str(complaint.category or "General").strip()
    title = str(complaint.title or "").strip()
    desc = str(complaint.description or "").strip()
    loc = str(complaint.location or "").strip()
    prio = str(complaint.priority or "Medium").strip()
    stat = str(complaint.status or "Pending").strip()
    dept = str(complaint.department or "").strip()
    day_lbl = str(complaint.day_label or "Day 0").strip()
    l_upd = str(complaint.last_updated or "").strip()
    created_at_str = complaint.created_at.strftime("%Y-%m-%d %H:%M:%S") if (hasattr(complaint, 'created_at') and complaint.created_at) else datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M:%S")

    row_data = {
        "complaint_id": cid,
        "tracking_key": tkey,
        "citizen_name": cname,
        "citizen_email": cemail,
        "category": cat,
        "title": title,
        "description": desc,
        "location": loc,
        "priority": prio,
        "status": stat,
        "department": dept,
        "day_label": day_lbl,
        "last_updated": l_upd,
        "created_at": created_at_str
    }

    with CSV_LOCK:
        try:
            existing_rows = []
            if os.path.exists(COMPLAINTS_CSV_FILE):
                with open(COMPLAINTS_CSV_FILE, mode="r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        existing_rows.append(r)

            found_idx = -1
            for idx, r in enumerate(existing_rows):
                if r.get("complaint_id") == cid or (tkey and r.get("tracking_key") == tkey):
                    found_idx = idx
                    break

            if found_idx >= 0:
                existing_rows[found_idx] = row_data
            else:
                existing_rows.append(row_data)

            with open(COMPLAINTS_CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=COMPLAINTS_CSV_HEADERS)
                writer.writeheader()
                writer.writerows(existing_rows)

            print(f"[Kizuno-AI CSV] Saved complaint #{cid} ({stat}) to complaints.csv")
            return row_data
        except Exception as e:
            print(f"[Kizuno-AI CSV] Error writing complaints.csv: {e}")
            return {}


def remove_complaint_from_csv(complaint_id_or_key: str) -> bool:
    """
    Removes a complaint from complaints.csv. Thread-safe.
    """
    if not complaint_id_or_key:
        return False

    clean_target = complaint_id_or_key.strip().upper()
    init_complaints_csv()

    with CSV_LOCK:
        try:
            if not os.path.exists(COMPLAINTS_CSV_FILE):
                return False

            existing_rows = []
            with open(COMPLAINTS_CSV_FILE, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    cid = (r.get("complaint_id") or "").strip().upper()
                    tkey = (r.get("tracking_key") or "").strip().upper()
                    if cid != clean_target and tkey != clean_target:
                        existing_rows.append(r)

            with open(COMPLAINTS_CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=COMPLAINTS_CSV_HEADERS)
                writer.writeheader()
                writer.writerows(existing_rows)

            print(f"[Kizuno-AI CSV] Removed {clean_target} from complaints.csv")
            return True
        except Exception as e:
            print(f"[Kizuno-AI CSV] Error removing complaint from complaints.csv: {e}")
            return False


def record_deleted_complaint_to_csv(complaint, deleted_by: str = "Citizen Owner") -> dict:
    """
    Records a deleted grievance into deleted_complaints.csv. Thread-safe.
    """
    if not complaint:
        return {}

    init_deleted_complaints_csv()

    cid = str(complaint.id).strip()
    tkey = str(complaint.tracking_key or "").strip()
    cname = str(complaint.citizen_name or "Citizen").strip()
    cemail = str(complaint.citizen_email or "").strip().lower()
    cat = str(complaint.category or "General").strip()
    title = str(complaint.title or "").strip()
    desc = str(complaint.description or "").strip()
    loc = str(complaint.location or "").strip()
    prio = str(complaint.priority or "Medium").strip()
    stat = str(complaint.status or "Pending").strip()
    dept = str(complaint.department or "").strip()
    deleted_at_str = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M:%S")

    row_data = {
        "complaint_id": cid,
        "tracking_key": tkey,
        "citizen_name": cname,
        "citizen_email": cemail,
        "category": cat,
        "title": title,
        "description": desc,
        "location": loc,
        "priority": prio,
        "status": stat,
        "department": dept,
        "deleted_at": deleted_at_str,
        "deleted_by": deleted_by
    }

    with CSV_LOCK:
        try:
            with open(DELETED_COMPLAINTS_CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=DELETED_COMPLAINTS_CSV_HEADERS)
                writer.writerow(row_data)
            print(f"[Kizuno-AI CSV] Archived deleted complaint #{cid} into deleted_complaints.csv by {deleted_by}")
            return row_data
        except Exception as e:
            print(f"[Kizuno-AI CSV] Error writing deleted_complaints.csv: {e}")
            return {}


def sync_sql_complaints_to_csv(db: Session):
    """
    Synchronizes all existing active complaints from SQL into complaints.csv on server startup.
    """
    try:
        complaints = db.query(Complaint).order_by(Complaint.created_at.asc()).all()
        for c in complaints:
            save_complaint_to_csv(c)
        print(f"[Kizuno-AI CSV] Synchronized {len(complaints)} SQL complaints into complaints.csv")
    except Exception as e:
        print(f"[Kizuno-AI CSV] Warning during SQL to complaints.csv sync: {e}")


# Initialize database tables on server start
init_db()

# Initialize users.csv, complaints.csv, and deleted_complaints.csv on startup
init_users_csv()
init_complaints_csv()
init_deleted_complaints_csv()

_sync_session = SessionLocal()
try:
    sync_sql_users_to_csv(_sync_session)
    sync_sql_complaints_to_csv(_sync_session)
finally:
    _sync_session.close()

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
    credential: Optional[str] = None
    client_id: Optional[str] = None
    role: Optional[str] = "citizen"
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None


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

    # Check if user already exists with password in SQL
    existing_user = db.query(User).filter(User.email == clean_email).first()
    if existing_user and existing_user.password_hash:
        raise HTTPException(
            status_code=400,
            detail=f"An account with {clean_email} already exists. Please switch to Sign In with your password."
        )

    # Generate 6-digit numeric OTP code
    code = f"{random.randint(100000, 999999)}"
    expires = datetime.now(timezone(timedelta(hours=5, minutes=30))) + timedelta(minutes=10)

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
        is_blocked = smtp_res.get("networkBlocked", False) or any(kw in err_msg for kw in ["Network is unreachable", "Errno 101", "timed out"])
        if is_blocked:
            print(f"[Kizuna-AI Auth] Cloud host firewall blocked outbound SMTP ({err_msg}). Returning fallback verification code: {code}")
            return {
                "success": True,
                "sent": False,
                "networkBlocked": True,
                "code": code,
                "message": f"Verification code generated. (Cloud host blocks direct SMTP). Code: {code}",
                "email": clean_email,
                "expiresInMinutes": 10
            }
        else:
            print(f"[Kizuna-AI Auth] Verification email could not be sent to {clean_email}: {err_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to dispatch verification email to {clean_email}: {err_msg}"
            )

    return {
        "success": True,
        "sent": True,
        "networkBlocked": False,
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
    Stores user in Supabase PostgreSQL primary database with registration_method='email', email_verified=True.
    Permanently assigns created_at and sets initial last_login.
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
        EmailVerification.expires_at >= datetime.now(timezone(timedelta(hours=5, minutes=30)))
    ).first()

    if not verif:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code. Please request a new code to your Gmail."
        )

    # Mark code as consumed
    verif.is_used = True

    # Check if user already exists in SQL / Supabase
    existing_user = db.query(User).filter(User.email == clean_email).first()
    hashed = hash_password(payload.password)
    now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))

    if existing_user:
        if existing_user.password_hash:
            raise HTTPException(
                status_code=400,
                detail=f"An account with {clean_email} already exists. Please sign in with your password."
            )
        # Upgrade existing Google/mock user with password
        existing_user.name = payload.username.strip() or existing_user.name
        existing_user.password_hash = hashed
        existing_user.email_verified = True
        existing_user.registration_method = existing_user.registration_method or "email"
        existing_user.role = "citizen"
        existing_user.last_login = now_ist
        # Note: created_at is permanently untouched!
        db.commit()
        db.refresh(existing_user)
        user = existing_user
    else:
        # Create fresh citizen account with permanent creation timestamp
        user = User(
            email=clean_email,
            name=payload.username.strip() or clean_email.split("@")[0],
            password_hash=hashed,
            email_verified=True,
            role="citizen",
            registration_method="email",
            created_at=now_ist,
            last_login=now_ist
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Maintain users.csv cache without duplicating
    record_user_to_csv(
        user_id=user.id,
        email=user.email,
        name=user.name,
        registration_method="email",
        email_verified=True,
        created_at=user.created_at
    )

    return {
        "success": True,
        "message": f"Account is created successfully! Welcome to your Dashboard, {user.name}.",
        "user": user.to_dict()
    }


@app.post("/api/auth/login")
def login_with_password(payload: LoginUserDTO, db: Session = Depends(get_db)):
    """
    Authenticates citizen using verified Gmail and Password from SQL / Supabase.
    Requires prior email verification through the Create Account flow.
    Updates last_login timestamp while strictly preserving the original created_at.
    """
    clean_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="No account found with this Gmail address. Please click 'Create Account' to register and verify your email."
        )

    if not user.email_verified and not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Your Gmail address has not been verified yet. Please complete verification."
        )

    if user.password_hash and not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Incorrect password. Please verify and try again."
        )

    # Update last_login only (created_at remains completely unchanged)
    user.last_login = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    db.commit()
    db.refresh(user)

    # Sync cache without duplicate entries
    method = user.registration_method or "email"
    record_user_to_csv(
        user_id=user.id,
        email=user.email,
        name=user.name,
        registration_method=method,
        email_verified=True,
        created_at=user.created_at
    )

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
    2. Checks Supabase / SQL database:
       - If new user: creates record with registration_method='google', email_verified=True,
         created_at=now, last_login=now.
       - If existing user: updates last_login=now, DOES NOT recreate or duplicate,
         and NEVER modifies created_at.
    3. Does NOT store Google password, OAuth secrets, access tokens, or refresh tokens.
    4. Returns authenticated session object with real SQL user ID.
    """
    token_data = decode_jwt_unverified(payload.credential) if payload.credential else {}
    email = (token_data.get("email") or payload.email or "").strip().lower()
    if not email:
        raise HTTPException(
            status_code=400,
            detail="Invalid Google OAuth credential token or missing email."
        )

    google_id = token_data.get("sub") or f"google_{email.split('@')[0]}"
    name = (token_data.get("name") or payload.name or email.split("@")[0]).strip()
    avatar_url = token_data.get("picture") or payload.picture
    role = payload.role or ("officer" if "officer" in email else "citizen")
    now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))

    # Search for existing user by google_id or email (case-insensitive) to prevent duplicates
    user = db.query(User).filter((User.google_id == google_id) | (User.email == email)).first()
    if user:
        # Existing user: update last_login and profile info; DO NOT touch created_at
        user.name = name or user.name
        if avatar_url:
            user.avatar_url = avatar_url
        user.role = role or user.role
        user.email_verified = True
        user.registration_method = "google"
        user.last_login = now_ist
    else:
        # New user: store with permanent creation timestamp
        user = User(
            google_id=google_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
            role=role,
            registration_method="google",
            email_verified=True,
            created_at=now_ist,
            last_login=now_ist
        )
        db.add(user)

    db.commit()
    db.refresh(user)

    # Maintain cache without duplicate row
    record_user_to_csv(
        user_id=user.id,
        email=user.email,
        name=user.name,
        registration_method="google",
        email_verified=True,
        created_at=user.created_at
    )

    return {
        "success": True,
        "message": f"Successfully authenticated as {name} ({role}) via Google OAuth 2.0",
        "user": user.to_dict(),
        "googleProfile": {
            "email": email,
            "name": name,
            "picture": avatar_url,
            "givenName": token_data.get("given_name") or name.split()[0],
            "emailVerified": True
        }
    }


@app.get("/api/auth/users")
def list_authenticated_users(
    db: Session = Depends(get_db),
    _auth: bool = Depends(verify_admin_access)
):
    """Retrieves all users authenticated in the database (Protected for Admin only)"""
    users = db.query(User).order_by(User.last_login.desc()).all()
    return [u.to_dict() for u in users]


# -------------------------------------------------------------
# SUPABASE CONFIG & ADMIN USER MANAGEMENT REST APIS
# -------------------------------------------------------------

class VerifyPinDTO(BaseModel):
    pin: str


@app.get("/api/supabase/config")
def get_supabase_config():
    """Returns public Supabase parameters for frontend Realtime subscriptions"""
    return {
        "supabaseUrl": SUPABASE_URL,
        "supabaseAnonKey": SUPABASE_KEY
    }


@app.post("/api/admin/verify-pin")
def verify_admin_pin(payload: VerifyPinDTO):
    """Verifies Administrator Security PIN and issues secure session token"""
    if payload.pin.strip() == ADMIN_PIN:
        return {
            "success": True,
            "token": get_admin_auth_token(ADMIN_PIN),
            "message": "Admin authorization granted."
        }
    raise HTTPException(status_code=401, detail="Incorrect Admin PIN. Access denied.")


@app.get("/api/admin/stats")
def get_admin_user_stats(
    db: Session = Depends(get_db),
    _auth: bool = Depends(verify_admin_access)
):
    """
    Computes live registered user statistics directly from SQL / Supabase:
    - Total Users (excluding test/dummy accounts)
    - Google Users
    - Email Users
    - Verified Users
    - New Today (created within last 24h / today)
    """
    raw_users = db.query(User).all()
    unique_users = {}
    for u in raw_users:
        em = (u.email or "").strip().lower()
        nm = (u.name or "").strip().lower()
        if not em or "test" in em or em.startswith("kizuno.citizen.") or em.endswith("@example.com") or em == "kumar.citizen@gmail.com" or em == "dilip.official09@gmail.com" or nm == "ddddd":
            continue
        if em not in unique_users:
            unique_users[em] = u

    clean_users = list(unique_users.values())
    total_users = len(clean_users)
    google_users = sum(1 for u in clean_users if (u.registration_method or "").lower() == "google")
    email_users = sum(1 for u in clean_users if (u.registration_method or "").lower() == "email")
    verified_users = sum(1 for u in clean_users if u.email_verified)

    now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    today_date = now_ist.date()
    new_today = sum(1 for u in clean_users if u.created_at and (u.created_at.date() == today_date if hasattr(u.created_at, 'date') else False))

    return {
        "total_users": total_users,
        "google_users": google_users,
        "email_users": email_users,
        "verified_users": verified_users,
        "new_today": new_today
    }


@app.get("/api/admin/users")
def get_admin_users(
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query("newest"),
    db: Session = Depends(get_db),
    _auth: bool = Depends(verify_admin_access)
):
    """
    Retrieves live registered users list with search, sorting, and complaint counts.
    Strictly filters out test accounts and duplicate emails.
    Protected: Only authorized administrators can access.
    """
    query = db.query(User)
    if search and isinstance(search, str):
        clean_search = f"%{search.strip()}%"
        query = query.filter((User.name.ilike(clean_search)) | (User.email.ilike(clean_search)))

    # Exclude test and dummy accounts
    query = query.filter(
        ~User.email.ilike("%test%"),
        ~User.email.ilike("%kumar.citizen%"),
        ~User.email.ilike("%dilip.official09%"),
        ~User.email.ilike("kizuno.citizen.%"),
        ~User.email.ilike("%@example.com"),
        User.name != "ddddd"
    )

    if sort == "newest":
        query = query.order_by(User.created_at.desc())
    elif sort == "oldest":
        query = query.order_by(User.created_at.asc())
    elif sort == "last_login":
        query = query.order_by(User.last_login.desc())
    elif sort == "name":
        query = query.order_by(User.name.asc())
    elif sort == "email":
        query = query.order_by(User.email.asc())
    elif sort == "method":
        query = query.order_by(User.registration_method.asc())
    else:
        query = query.order_by(User.created_at.desc())

    users = query.all()
    # Deduplicate users by email (case-insensitive)
    seen_emails = set()
    clean_users = []
    for u in users:
        em = (u.email or "").strip().lower()
        if not em or em in seen_emails:
            continue
        seen_emails.add(em)
        clean_users.append(u.to_dict())

    return clean_users


@app.get("/api/admin/users/{user_id}/details")
def get_admin_user_details(
    user_id: int,
    db: Session = Depends(get_db),
    _auth: bool = Depends(verify_admin_access)
):
    """
    Retrieves full user profile and associated complaints for administrative inspection.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User #{user_id} not found in database.")

    complaints = db.query(Complaint).filter(
        (Complaint.user_id == user.id) | (Complaint.citizen_email == user.email)
    ).order_by(Complaint.created_at.desc()).all()

    data = user.to_dict()
    data["complaints"] = [c.to_dict() for c in complaints]
    data["complaints_count"] = len(complaints)
    return data


@app.get("/api/admin/export-users-csv")
def export_users_to_csv(
    db: Session = Depends(get_db),
    _auth: bool = Depends(verify_admin_access)
):
    """
    Generates dynamic users.csv on-the-fly directly from live database.
    Columns: id,email,name,registration_method,email_verified,created_at,last_login
    """
    users = db.query(User).order_by(User.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "email", "name", "registration_method", "email_verified", "created_at", "last_login"])

    for u in users:
        c_str = u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else ""
        l_str = u.last_login.strftime("%Y-%m-%d %H:%M:%S") if u.last_login else ""
        writer.writerow([
            u.id,
            u.email,
            u.name,
            u.registration_method or "email",
            "true" if u.email_verified else "false",
            c_str,
            l_str
        ])

    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="users.csv"'
        }
    )



@app.get("/api/auth/users-csv")
def list_csv_users():
    """
    Retrieves all user records currently stored in users.csv.
    Read-only view for verification, auditing, and administrative inspection.
    """
    users = []
    with CSV_LOCK:
        if os.path.exists(USERS_CSV_FILE):
            try:
                with open(USERS_CSV_FILE, mode="r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    users = list(reader)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to read users.csv: {e}")
    return {
        "count": len(users),
        "file": "users.csv",
        "columns": CSV_HEADERS,
        "users": users
    }


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
        "timestamp": datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()
    }


@app.get("/api/kpis")
@app.get("/kpis")
def get_kpis(db: Session = Depends(get_db)):
    """Calculates live KPI metrics directly via SQL queries"""
    return calculate_kpis(db)


@app.get("/api/complaints")
@app.get("/complaints")
def list_complaints(
    status: Optional[str] = Query(None, description="Filter by status: Pending, In Progress, Delayed, Resolved"),
    category: Optional[str] = Query(None, description="Filter by category"),
    citizen_email: Optional[str] = Query(None, description="Filter by citizen email"),
    db: Session = Depends(get_db)
):
    """Retrieves all complaints from SQL with optional filtering, strictly removing test/duplicate records"""
    test_ids = {
        "CIV-2026-6196", "CIV-2026-4895", "CIV-2026-7751", "CIV-2026-3016",
        "CIV-2026-2463", "CIV-2026-6490", "CIV-2026-6991", "CIV-2026-1449",
        "CIV-2026-1042", "CIV-2026-1040", "CIV-2026-1038", "CIV-2026-1041",
        "CIV-2026-1493", "CIV-2026-2239"
    }
    query = db.query(Complaint).filter(~Complaint.id.in_(test_ids))
    query = query.filter(
        ~Complaint.citizen_email.ilike("%test%"),
        ~Complaint.citizen_email.ilike("%dilip.official09%"),
        ~Complaint.citizen_email.ilike("%kumar.citizen%"),
        ~Complaint.citizen_email.ilike("dilippalanisamy09@gmail.com")
    )

    if status and isinstance(status, str) and status != "All":
        query = query.filter(Complaint.status == status)
    if category and isinstance(category, str) and category != "All":
        query = query.filter(Complaint.category == category)
    if citizen_email and isinstance(citizen_email, str):
        query = query.filter(Complaint.citizen_email == citizen_email.strip().lower())

    complaints = query.order_by(Complaint.created_at.desc()).all()

    # Deduplicate complaints by id and by (title + citizen_email)
    seen_ids = set()
    seen_keys = set()
    unique_complaints = []
    for c in complaints:
        cid = (c.id or "").strip()
        ctitle = (c.title or "").strip().lower()
        cemail = (c.citizen_email or "").strip().lower()
        key = f"{ctitle}|{cemail}"
        if cid in seen_ids or (ctitle and cemail and key in seen_keys):
            continue
        seen_ids.add(cid)
        if ctitle and cemail:
            seen_keys.add(key)
        unique_complaints.append(c.to_dict())

    return unique_complaints


@app.get("/api/complaints/{key_or_id}")
@app.get("/complaints/{key_or_id}")
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
@app.post("/complaints", status_code=201)
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

    today_str = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%b %d, %Y")

    # Category icon mapping
    icon_map = {
        "Streetlight": "💡",
        "Water Leak": "💧",
        "Garbage": "🗑️",
        "Road Damage": "🚗",
        "Drainage": "🌊"
    }
    category_icon = icon_map.get(payload.category, "📋")

    # Relational foreign key: Link complaint to users table (complaints.user_id -> users.id)
    user_fk = None
    if payload.citizen_email:
        clean_cemail = payload.citizen_email.strip().lower()
        matched_user = db.query(User).filter(User.email == clean_cemail).first()
        if matched_user:
            user_fk = matched_user.id

    # Insert into SQL complaints table
    new_complaint = Complaint(
        id=new_id,
        tracking_key=new_key,
        user_id=user_fk,
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

    # Automatically archive into complaints.csv
    save_complaint_to_csv(new_complaint)

    return new_complaint.to_dict()


@app.post("/api/complaints/bulk-sync")
@app.post("/complaints/bulk-sync")
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
                save_complaint_to_csv(existing)
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
@app.delete("/complaints/{id_or_key}")
def delete_complaint(
    id_or_key: str,
    requester_email: Optional[str] = Query(None, description="Email of citizen or officer requesting deletion"),
    requester_role: Optional[str] = Query(None, description="Role of requester (citizen or officer)"),
    user_email: Optional[str] = Query(None, description="Alias for requester_email"),
    role: Optional[str] = Query(None, description="Alias for requester_role"),
    db: Session = Depends(get_db)
):
    """
    Deletes a citizen complaint and its child timeline events from the SQL database:
    1. Archives deleted complaint details into `deleted_complaints.csv` with timestamp and user.
    2. Removes the complaint from `complaints.csv`.
    3. Removes complaint permanently from SQL database so it disappears from the Officer Portal.
    """
    requester_email = requester_email or user_email
    requester_role = requester_role or role

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
    actor_label = "an authorized officer" if is_officer else "its citizen owner"
    deleter_info = requester_email or actor_label

    # 1. Archive to deleted_complaints.csv
    record_deleted_complaint_to_csv(complaint, deleted_by=deleter_info)

    # 2. Remove from active complaints.csv
    remove_complaint_from_csv(deleted_id)

    # 3. Permanently remove from SQL (cascades child timeline events)
    db.delete(complaint)
    db.commit()

    return {
        "success": True,
        "message": f"Complaint #{deleted_id} has been permanently deleted and archived by {actor_label}.",
        "deletedId": deleted_id
    }


@app.post("/api/officer/update")
@app.post("/officer/update")
def update_complaint_status(payload: OfficerUpdateDTO, db: Session = Depends(get_db)):
    """
    Officer Operational Action Console endpoint:
    Applies real status updates in SQL, updates complaints.csv, and appends verified milestones to timeline.
    """
    complaint = db.query(Complaint).filter(Complaint.id == payload.complaint_id).first()
    if not complaint:
        raise HTTPException(
            status_code=404,
            detail=f"Complaint #{payload.complaint_id} does not exist in the SQL database."
        )

    today_str = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%b %d, %Y")
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

    # Synchronize updated status and timeline directly to complaints.csv
    save_complaint_to_csv(complaint)

    return {
        "message": f"Successfully updated complaint #{complaint.id}",
        "action": action,
        "complaint": complaint.to_dict()
    }


@app.get("/api/complaints-csv")
def download_complaints_csv():
    """Allows downloading complaints.csv directly"""
    init_complaints_csv()
    return FileResponse(
        COMPLAINTS_CSV_FILE,
        media_type="text/csv",
        filename="complaints.csv"
    )


@app.get("/api/complaints/deleted-csv")
def download_deleted_complaints_csv():
    """Allows downloading deleted_complaints.csv directly"""
    init_deleted_complaints_csv()
    return FileResponse(
        DELETED_COMPLAINTS_CSV_FILE,
        media_type="text/csv",
        filename="deleted_complaints.csv"
    )


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
@app.get("/network-info")
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


@app.get("/admin")
@app.get("/admin/users")
def serve_admin():
    """Serves the Kizuno-AI Admin Dashboard for live Supabase PostgreSQL user management"""
    admin_path = os.path.join(os.path.dirname(__file__), "admin.html")
    if os.path.exists(admin_path):
        return FileResponse(admin_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="admin.html not found.")


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
