import requests
import json

BASE = "http://127.0.0.1:8000/api"

def run_tests():
    print("=== Testing Kizuno-AI SQL Backend Integration ===")

    # 1. Health & SQL connectivity
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200, f"Health failed: {r.text}"
    health = r.json()
    print("1. Health Check (SQL):", health)
    assert health["status"] == "online"
    assert "ComplaintsInSQL" in str(health)

    # 2. Login with Seeded Citizen from SQL
    r = requests.post(f"{BASE}/auth/login", json={
        "email": "kumar.citizen@gmail.com",
        "password": "password123"
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    login_data = r.json()
    print("2. Seeded Citizen SQL Login:", login_data)
    assert login_data["success"] is True
    assert login_data["user"]["email"] == "kumar.citizen@gmail.com"

    # 3. Wrong password rejection from SQL
    r = requests.post(f"{BASE}/auth/login", json={
        "email": "kumar.citizen@gmail.com",
        "password": "wrongpassword"
    })
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
    print("3. SQL Password Verification (Rejection on wrong password): PASSED")

    # 4. Request Gmail Verification Code (stored in SQL email_verifications)
    import time
    test_email = f"test.citizen.{int(time.time())}@gmail.com"
    r = requests.post(f"{BASE}/auth/send-verification", json={
        "email": test_email,
        "username": "Test Citizen 99"
    })
    assert r.status_code == 200, f"Send OTP failed: {r.text}"
    otp_data = r.json()
    print("4. Gmail OTP Generated and Stored in SQL:", otp_data)
    dev_code = otp_data.get("devCode")
    assert dev_code is not None, "Dev code should be returned in local mode"

    # 5. Register User with OTP and Hash Password into SQL
    r = requests.post(f"{BASE}/auth/register", json={
        "username": "Test Citizen 99",
        "email": test_email,
        "password": "mypassword999",
        "verification_code": dev_code
    })
    assert r.status_code == 200, f"Register failed: {r.text}"
    reg_data = r.json()
    print("5. User Registered and Verified in SQL:", reg_data)
    assert reg_data["user"]["email"] == test_email
    assert reg_data["user"]["isVerified"] is True

    # 6. Login with Newly Registered User from SQL
    r = requests.post(f"{BASE}/auth/login", json={
        "email": test_email,
        "password": "mypassword999"
    })
    assert r.status_code == 200, f"New user login failed: {r.text}"
    new_login = r.json()
    print("6. New Registered User Logged in from SQL:", new_login["user"]["name"])

    # 7. Submit Complaint into SQL
    prev_count = health["activeComplaintsInSQL"]
    r = requests.post(f"{BASE}/complaints", json={
        "category": "Roads & Infrastructure",
        "title": "Severe Pothole on Gandhipuram Cross Cut Road",
        "description": "Large dangerous pothole causing traffic jams and bike skidding near cross cut junction.",
        "location": "Gandhipuram, Coimbatore",
        "priority": "High",
        "citizen_email": test_email,
        "citizen_name": "Test Citizen 99"
    })
    assert r.status_code in (200, 201), f"Complaint submission failed: {r.text}"
    created_comp = r.json()
    print(f"7. Complaint Saved into SQL! ID: {created_comp['id']}, Key: {created_comp['trackingKey']}")
    comp_id = created_comp["id"]
    track_key = created_comp["trackingKey"]

    # 8. Query Complaint by ID and Tracking Key from SQL
    r = requests.get(f"{BASE}/complaints/{comp_id}")
    assert r.status_code == 200, f"Fetch by ID failed: {r.text}"
    fetched = r.json()
    assert fetched["id"] == comp_id
    assert fetched["citizenEmail"] == test_email
    print("8a. Fetched Complaint by ID from SQL: PASSED")

    r = requests.get(f"{BASE}/complaints/{track_key}")
    assert r.status_code == 200, f"Fetch by Key failed: {r.text}"
    fetched_key = r.json()
    assert fetched_key["id"] == comp_id
    print("8b. Fetched Complaint by Tracking Key from SQL: PASSED")

    # 9. Verify Complaint Count Incremented in SQL
    r = requests.get(f"{BASE}/health")
    new_health = r.json()
    assert new_health["activeComplaintsInSQL"] == prev_count + 1
    print(f"9. SQL Complaint count incremented: {prev_count} -> {new_health['activeComplaintsInSQL']}")

    # 10. Delete Complaint by Non-Owner (Should Fail 403)
    r = requests.delete(f"{BASE}/complaints/{comp_id}?requester_email=other.citizen@gmail.com")
    assert r.status_code == 403, f"Expected 403 Forbidden, got {r.status_code}"
    print("10. SQL Ownership Protection (Delete Forbidden for Non-Owner): PASSED")

    # 11. Delete Complaint by Owner (Should Succeed 200)
    r = requests.delete(f"{BASE}/complaints/{comp_id}?requester_email={test_email}")
    assert r.status_code == 200, f"Delete failed: {r.text}"
    print("11. Owner Deleted Complaint from SQL: PASSED")

    # 12. Verify Complaint is Gone from SQL
    r = requests.get(f"{BASE}/complaints/{comp_id}")
    assert r.status_code == 404
    print("12. Confirmed Deletion in SQL (404 Not Found): PASSED")

    print("\nALL 12 SQL INTEGRATION TESTS PASSED SUCCESSFULLY! [OK]")

if __name__ == "__main__":
    run_tests()
