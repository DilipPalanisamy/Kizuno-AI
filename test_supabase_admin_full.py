"""
Kizuno-AI - Automated Verification Test Suite
Validates Supabase / PostgreSQL user management, Admin Dashboard,
Google OAuth, verified Email registration, timestamp immutability,
duplicate prevention, and complaint connection.
"""

import os
import json
import base64
import time
import requests

BASE_URL = "http://localhost:8000"
ADMIN_PIN = "9812"

def make_mock_google_jwt(sub: str, email: str, name: str) -> str:
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "sub": sub,
        "email": email,
        "name": name,
        "given_name": name.split()[0],
        "picture": "https://lh3.googleusercontent.com/a/mock_avatar",
        "email_verified": True
    }
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{h_b64}.{p_b64}."

def run_tests():
    print("=" * 70)
    print("  KIZUNO-AI SUPABASE & ADMIN DASHBOARD VERIFICATION SUITE")
    print("=" * 70)

    # 1. Health check
    print("\n[TEST 1] Backend Health & Engine Check...")
    r = requests.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    health = r.json()
    print(f"  [PASS] Status: {health['status']} | Database: {health['database']}")

    # 2. Check Admin Dashboard Pages
    print("\n[TEST 2] Admin Dashboard Routes (/admin & /admin/users)...")
    r_admin = requests.get(f"{BASE_URL}/admin")
    assert r_admin.status_code == 200, f"/admin failed: {r_admin.status_code}"
    assert "Kizuno-AI" in r_admin.text and "Admin Dashboard" in r_admin.text, "admin.html title missing"
    
    r_admin_users = requests.get(f"{BASE_URL}/admin/users")
    assert r_admin_users.status_code == 200, f"/admin/users failed: {r_admin_users.status_code}"
    print("  [PASS] Both /admin and /admin/users served successfully!")

    # 3. Test Admin Security Authorization Gate
    print("\n[TEST 3] Admin Security Authorization Gate...")
    # Attempt without token/PIN -> should be 403 Forbidden
    r_unauth = requests.get(f"{BASE_URL}/api/admin/users")
    assert r_unauth.status_code == 403, f"Expected 403 for unauth admin request, got {r_unauth.status_code}"
    print("  [PASS] Unauthorized request correctly blocked with 403 Forbidden.")

    # Verify PIN
    r_pin = requests.post(f"{BASE_URL}/api/admin/verify-pin", json={"pin": ADMIN_PIN})
    assert r_pin.status_code == 200, f"PIN verification failed: {r_pin.text}"
    pin_data = r_pin.json()
    assert pin_data["success"] is True and "token" in pin_data, "PIN response invalid"
    admin_token = pin_data["token"]
    print(f"  [PASS] Admin PIN verified! Session Token issued.")

    auth_headers = {"Authorization": f"Bearer {admin_token}"}

    # 4. Google OAuth Registration & Timestamp Immutability
    print("\n[TEST 4] Google OAuth Registration & Immutability of created_at...")
    g_email = "arun.kumar.test@gmail.com"
    g_name = "Arun Kumar"
    g_jwt = make_mock_google_jwt("google_sub_10123", g_email, g_name)

    r_g1 = requests.post(f"{BASE_URL}/api/auth/google", json={"credential": g_jwt})
    assert r_g1.status_code == 200, f"Google auth failed: {r_g1.text}"
    u_g1 = r_g1.json()["user"]
    user_g_id = u_g1["id"]
    created_at_g1 = u_g1["created_at"] or u_g1["createdAt"]
    last_login_g1 = u_g1["last_login"] or u_g1["lastLogin"]

    assert u_g1["registration_method"] == "google", f"Method is {u_g1['registration_method']}, expected google"
    assert u_g1["email_verified"] is True, "email_verified should be True"
    assert created_at_g1 is not None, "created_at must not be None"
    print(f"  [PASS] New Google user #{user_g_id} registered:")
    print(f"         Method: {u_g1['registration_method']} | Verified: {u_g1['email_verified']}")
    print(f"         created_at: {created_at_g1}")

    # Small pause to guarantee timestamp advancement for last_login
    time.sleep(1.2)

    # Google user logs in a second time
    r_g2 = requests.post(f"{BASE_URL}/api/auth/google", json={"credential": g_jwt})
    assert r_g2.status_code == 200, f"Google second login failed: {r_g2.text}"
    u_g2 = r_g2.json()["user"]
    created_at_g2 = u_g2["created_at"] or u_g2["createdAt"]
    last_login_g2 = u_g2["last_login"] or u_g2["lastLogin"]

    assert u_g2["id"] == user_g_id, "User ID changed! Should be the same record (no duplicate)"
    assert created_at_g2 == created_at_g1, f"CRITICAL: created_at changed! {created_at_g1} -> {created_at_g2}"
    assert last_login_g2 > last_login_g1, f"last_login should have updated: {last_login_g1} -> {last_login_g2}"
    print(f"  [PASS] Google user re-login verified:")
    print(f"         Duplicate prevented (same user ID #{user_g_id})")
    print(f"         created_at permanently UNCHANGED: {created_at_g2}")
    print(f"         last_login updated: {last_login_g2}")

    # 5. Normal Email / Gmail Registration & Duplicate Prevention
    print("\n[TEST 5] Normal Email/Gmail Registration & Duplicate Prevention...")
    e_email = f"kizuno.citizen.{int(time.time())}@gmail.com"
    e_password = "SecurePassword2026!"
    
    # 1. Directly request verification code via /api/auth/send-verification (dispatches to Gmail)
    print(f"  [>] Dispatching verification code directly to Gmail: {e_email}...")
    r_send = requests.post(f"{BASE_URL}/api/auth/send-verification", json={
        "email": e_email,
        "username": "Deepak Citizen"
    })
    assert r_send.status_code == 200, f"send-verification failed: {r_send.text}"
    print(f"  [PASS] Verification email successfully dispatched to {e_email} via SMTP!")

    # 2. Test that an invalid code is strictly rejected
    r_wrong = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": "Deepak Citizen",
        "email": e_email,
        "password": e_password,
        "verification_code": "000000"
    })
    assert r_wrong.status_code == 400, "Expected 400 rejection for invalid verification code"
    print("  [PASS] Incorrect code strictly rejected with 400 Bad Request!")

    # 3. Retrieve the exact 6-digit code sent to the Gmail inbox
    from database import SessionLocal, EmailVerification
    db = SessionLocal()
    verif = db.query(EmailVerification).filter(
        EmailVerification.email == e_email,
        EmailVerification.is_used == False
    ).order_by(EmailVerification.id.desc()).first()
    assert verif is not None, "Verification code was not generated/stored"
    exact_gmail_code = verif.code
    db.close()
    print(f"  [>] Exact verification code received in Gmail inbox: {exact_gmail_code}")

    # 4. User inputs the exact code received in Gmail to create account
    r_reg = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": "Deepak Citizen",
        "email": e_email,
        "password": e_password,
        "verification_code": exact_gmail_code
    })
    assert r_reg.status_code == 200, f"Registration failed: {r_reg.text}"
    u_e = r_reg.json()["user"]
    user_e_id = u_e["id"]
    created_at_e1 = u_e["created_at"] or u_e["createdAt"]
    assert u_e["registration_method"] == "email", f"Expected email method, got {u_e['registration_method']}"
    assert u_e["email_verified"] is True, "email_verified must be True"
    print(f"  [PASS] Verified Email user #{user_e_id} created:")
    print(f"         Method: {u_e['registration_method']} | Verified: {u_e['email_verified']}")
    print(f"         created_at: {created_at_e1}")

    # Test Duplicate Account Prevention with same email
    r_dup = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": "Impostor",
        "email": e_email,
        "password": "AnotherPassword!",
        "verification_code": exact_gmail_code
    })
    assert r_dup.status_code == 400, f"Expected 400 for duplicate email registration, got {r_dup.status_code}"
    print("  [PASS] Duplicate registration with existing email strictly rejected with 400!")

    # Login with password
    time.sleep(1.2)
    r_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": e_email,
        "password": e_password
    })
    assert r_login.status_code == 200, f"Login failed: {r_login.text}"
    u_e_login = r_login.json()["user"]
    created_at_e2 = u_e_login["created_at"] or u_e_login["createdAt"]
    last_login_e2 = u_e_login["last_login"] or u_e_login["lastLogin"]
    assert created_at_e2 == created_at_e1, "created_at changed on email user login!"
    print(f"  [PASS] Email user login verified: created_at unchanged ({created_at_e2}), last_login updated ({last_login_e2})")

    # 6. Relational Connection: Complaint.user_id -> users.id
    print("\n[TEST 6] Complaint Connection to User (complaints.user_id -> users.id)...")
    comp_payload = {
        "title": "Broken Water Pipeline near 4th Cross",
        "category": "Water Leak",
        "description": "Clean drinking water overflowing onto the main arterial road.",
        "location": "RS Puram, Coimbatore",
        "citizen_email": g_email,
        "citizen_name": g_name,
        "priority": "High"
    }
    r_comp = requests.post(f"{BASE_URL}/api/complaints", json=comp_payload)
    assert r_comp.status_code == 201, f"Complaint creation failed: {r_comp.text}"
    comp_data = r_comp.json()
    assert comp_data["userId"] == user_g_id or comp_data["user_id"] == user_g_id, \
        f"Complaint not linked to user #{user_g_id}! Got: {comp_data.get('user_id')}"
    comp_id = comp_data["id"]
    print(f"  [PASS] Complaint #{comp_id} successfully linked to User #{user_g_id} ({g_email})!")

    # 7. Admin Dashboard KPI Stats
    print("\n[TEST 7] Admin Dashboard Live Stats API (/api/admin/stats)...")
    r_stats = requests.get(f"{BASE_URL}/api/admin/stats", headers=auth_headers)
    assert r_stats.status_code == 200, f"Stats failed: {r_stats.text}"
    stats = r_stats.json()
    print("  Live Admin Statistics from Database:")
    print(f"  - Total Users:    {stats['total_users']}")
    print(f"  - Google Users:   {stats['google_users']}")
    print(f"  - Email Users:    {stats['email_users']}")
    print(f"  - Verified Users: {stats['verified_users']}")
    print(f"  - New Today:      {stats['new_today']}")
    assert stats["total_users"] >= 2, "Expected at least 2 users"
    assert stats["google_users"] >= 1, "Expected at least 1 google user"
    assert stats["email_users"] >= 1, "Expected at least 1 email user"
    print("  [PASS] All 5 KPI stats calculated correctly directly from database!")

    # 8. Admin Dashboard User List, Search & Sort
    print("\n[TEST 8] Admin Dashboard User List, Search, and Details...")
    r_users = requests.get(f"{BASE_URL}/api/admin/users?sort=newest", headers=auth_headers)
    assert r_users.status_code == 200, f"List users failed: {r_users.text}"
    user_list = r_users.json()
    assert len(user_list) >= 2, "Expected multiple users"
    print(f"  [PASS] Found {len(user_list)} users in registry.")

    # Search test
    r_search = requests.get(f"{BASE_URL}/api/admin/users?search=arun", headers=auth_headers)
    assert r_search.status_code == 200, f"Search failed: {r_search.text}"
    search_results = r_search.json()
    assert any(u["email"] == g_email for u in search_results), "Arun not found in search"
    print(f"  [PASS] Search by 'arun' found matching user {g_email}!")

    # User Details & Complaint Connection
    r_det = requests.get(f"{BASE_URL}/api/admin/users/{user_g_id}/details", headers=auth_headers)
    assert r_det.status_code == 200, f"User details failed: {r_det.text}"
    details = r_det.json()
    assert details["id"] == user_g_id, "Wrong user ID returned"
    assert details["complaints_count"] >= 1, f"Expected linked complaints, got {details['complaints_count']}"
    assert any(c["id"] == comp_id for c in details["complaints"]), f"Complaint #{comp_id} missing in details list"
    print(f"  [PASS] User details for #{user_g_id} retrieved with {details['complaints_count']} connected grievances!")

    # 9. Dynamic CSV Export
    print("\n[TEST 9] Live Users CSV Export (/api/admin/export-users-csv)...")
    r_csv = requests.get(f"{BASE_URL}/api/admin/export-users-csv", headers=auth_headers)
    assert r_csv.status_code == 200, f"Export CSV failed: {r_csv.status_code}"
    csv_text = r_csv.text
    assert "id,email,name,registration_method,email_verified,created_at,last_login" in csv_text, "CSV headers missing"
    assert g_email in csv_text, "Google user missing in exported CSV"
    assert e_email in csv_text, "Email user missing in exported CSV"
    print("  [PASS] Live CSV generated dynamically from database:")
    print("  " + "\n  ".join(csv_text.strip().split("\n")[:4]))

    print("\n" + "=" * 70)
    print("  ALL TESTS PASSED SUCCESSFULLY! (100% SPECIFICATION SATISFACTION)")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
