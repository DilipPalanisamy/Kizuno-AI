import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

def test_backend_auth():
    print("Testing FastAPI app directly with TestClient...")

    # 1. Health
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.status_code}"
    print("[OK] /api/health returned 200 OK:", res.json())

    # 2. Fast Verification Code Generation
    test_email = f"fast_user_{int(time.time())}@gmail.com"
    start_t = time.time()
    res = client.post("/api/auth/send-verification", json={
        "email": test_email,
        "username": "Speed Tester"
    })
    elapsed = time.time() - start_t
    print(f"[OK] /api/auth/send-verification completed in {elapsed:.2f}s with status {res.status_code}")
    assert res.status_code == 200, f"Failed: {res.text}"
    data = res.json()
    assert data.get("success") is True, "Success should be true"
    assert "code" in data, "Code should be in response"
    code = data["code"]
    print(f"[OK] Verification code returned: {code} (Length: {len(code)})")

    # 3. Complete Registration with Code
    res = client.post("/api/auth/register", json={
        "username": "Speed Tester",
        "email": test_email,
        "password": "Password123!",
        "verification_code": code
    })
    print(f"[OK] /api/auth/register status {res.status_code}")
    assert res.status_code == 200, f"Failed: {res.text}"
    reg_data = res.json()
    assert reg_data.get("success") is True
    print(f"[OK] Registered User: {reg_data.get('user', {}).get('name')}")

    # 4. Google Auth Login
    google_email = f"google_speed_{int(time.time())}@gmail.com"
    res = client.post("/api/auth/google", json={
        "credential": "test_google_token",
        "client_id": "test_client_id",
        "role": "citizen",
        "email": google_email,
        "name": "Google Fast User",
        "picture": "https://example.com/avatar.png"
    })
    print(f"[OK] /api/auth/google status {res.status_code}")
    assert res.status_code == 200, f"Failed: {res.text}"
    g_data = res.json()
    assert g_data.get("success") is True
    print(f"[OK] Google User: {g_data.get('user', {}).get('name')} (ID: {g_data.get('user', {}).get('id')})")

    # 5. Officer Complaint Submission & Real Routing
    res = client.post("/api/complaints", json={
        "title": "Broken Streetlight on 5th Cross Road",
        "description": "Streetlight bulb broken for 3 days and dark at night",
        "category": "Street Lighting",
        "location": "Ward 12, Gandhipuram",
        "department": "Electrical Dept",
        "user_id": str(g_data.get('user', {}).get('id')),
        "citizen_email": google_email,
        "citizen_name": "Google Fast User"
    })
    print(f"[OK] /api/complaints creation status {res.status_code}")
    assert res.status_code in [200, 201]
    comp_data = res.json()
    print(f"[OK] Complaint Created: {comp_data.get('id')} - Tracking: {comp_data.get('trackingKey')}")

    print("\nALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_backend_auth()
