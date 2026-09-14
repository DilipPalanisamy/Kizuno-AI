import os
import sys
import time
import requests

BASE_URL = "http://localhost:8000"

def test_flow():
    print("Testing Kizuno-AI backend & authentication flow...")

    # 1. Health check
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=3)
        assert r.status_code == 200, f"Health check failed: {r.status_code}"
        print("✓ Backend /health is OK")
    except Exception as e:
        print(f"Health check error (is server running?): {e}")

    # 2. Test send-verification speed and code generation
    test_email = f"testuser_{int(time.time())}@gmail.com"
    start_t = time.time()
    r = requests.post(f"{BASE_URL}/api/auth/send-verification", json={
        "email": test_email,
        "username": "Test Speed User"
    }, timeout=5)
    elapsed = time.time() - start_t
    print(f"✓ /auth/send-verification responded in {elapsed:.2f}s with status {r.status_code}")
    assert r.status_code == 200, f"Send verification failed: {r.text}"
    data = r.json()
    assert data.get("success") is True, "Success should be True"
    assert "code" in data, "Verification code should be returned in payload"
    code = data["code"]
    print(f"✓ Generated code: {code} (Length: {len(code)})")

    # 3. Test registration with this code
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": "Test Speed User",
        "email": test_email,
        "password": "Password123!",
        "verification_code": code
    }, timeout=5)
    print(f"✓ /auth/register status: {r.status_code}")
    assert r.status_code == 200, f"Register failed: {r.text}"
    reg_data = r.json()
    assert reg_data.get("success") is True
    print(f"✓ User registered: {reg_data.get('user', {}).get('name')}")

    # 4. Test Google OAuth login endpoint
    google_email = f"googleuser_{int(time.time())}@gmail.com"
    r = requests.post(f"{BASE_URL}/api/auth/google", json={
        "credential": "test_google_token",
        "client_id": "test_client_id",
        "role": "citizen",
        "email": google_email,
        "name": "Google Fast Citizen",
        "picture": "https://example.com/avatar.png"
    }, timeout=5)
    print(f"✓ /auth/google status: {r.status_code}")
    assert r.status_code == 200, f"Google login failed: {r.text}"
    g_data = r.json()
    assert g_data.get("success") is True
    print(f"✓ Google user logged in: {g_data.get('user', {}).get('name')} (ID: {g_data.get('user', {}).get('id')})")

    print("\nALL BACKEND AUTH TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_flow()
