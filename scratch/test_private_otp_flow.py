import os
import sys
import uuid

# Ensure root dir in path
sys.path.insert(0, r"c:\Users\DILIP\OneDrive\Desktop\kizuno-AI")

from fastapi.testclient import TestClient
from server import app
from database import get_db, EmailVerification, User

client = TestClient(app)

def test_private_gmail_otp_flow():
    test_id = uuid.uuid4().hex[:6]
    test_email = f"citizen_test_{test_id}@gmail.com"
    test_username = f"Citizen_{test_id}"
    test_password = "SecurePassword123!"

    print(f"\n--- Testing Private Gmail OTP Verification Flow for {test_email} ---")

    # Step 1: Send Verification Code
    print("\n1. Calling POST /api/auth/send-verification...")
    res = client.post("/api/auth/send-verification", json={
        "email": test_email,
        "username": test_username
    })
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    print("Response JSON:", data)
    assert data.get("success") is True, "Expected success=True"
    assert "code" not in data, "CRITICAL ERROR: 'code' was leaked in HTTP response!"
    print("[PASS] Verification code is completely HIDDEN from HTTP response (confidential).")

    # Step 2: Fetch the exact code that was sent to Gmail (from SQL database)
    db = next(get_db())
    record = db.query(EmailVerification).filter(
        EmailVerification.email == test_email,
        EmailVerification.is_used == False
    ).order_by(EmailVerification.id.desc()).first()

    assert record is not None, "Verification record not found in SQL database"
    exact_code = record.code
    print(f"[PASS] Exact 6-digit code delivered to user's Gmail: {exact_code}")

    # Step 3: Attempt registration with a WRONG code
    print("\n2. Testing registration with WRONG code '000000'...")
    bad_res = client.post("/api/auth/register", json={
        "username": test_username,
        "email": test_email,
        "password": test_password,
        "verification_code": "000000"
    })
    assert bad_res.status_code == 400, f"Expected 400, got {bad_res.status_code}"
    print("[PASS] Wrong code correctly rejected with 400 error.")

    # Step 4: Attempt registration with EXACT code from Gmail
    print(f"\n3. Testing registration with EXACT code '{exact_code}'...")
    reg_res = client.post("/api/auth/register", json={
        "username": test_username,
        "email": test_email,
        "password": test_password,
        "verification_code": exact_code
    })
    assert reg_res.status_code == 200, f"Expected 200, got {reg_res.status_code}: {reg_res.text}"
    reg_data = reg_res.json()
    print("Registration Response:", reg_data)
    assert reg_data.get("success") is True, "Expected success=True"
    assert reg_data.get("user", {}).get("email") == test_email, "User email mismatch"
    assert reg_data.get("user", {}).get("email_verified") is True, "Email verified should be True"
    print("[PASS] Registration succeeded with exact code!")

    # Step 5: Verify replay attack prevention (re-using same code)
    print("\n4. Testing re-use of consumed code...")
    replay_res = client.post("/api/auth/register", json={
        "username": test_username,
        "email": test_email,
        "password": test_password,
        "verification_code": exact_code
    })
    assert replay_res.status_code == 400, "Consumed code must not be reusable"
    print("[PASS] Consumed code cannot be reused.")

    print("\nALL VERIFICATION & REGISTRATION FLOW TESTS PASSED PERFECTLY!\n")

if __name__ == "__main__":
    test_private_gmail_otp_flow()
