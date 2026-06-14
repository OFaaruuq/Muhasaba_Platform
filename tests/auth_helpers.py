"""Two-step login helpers for tests (OTP is 123456 when TESTING=True)."""

TEST_OTP = "123456"


def login_session(client, username, password="admin123", otp=TEST_OTP):
    client.post("/auth/login", data={"username": username, "password": password})
    return client.post("/auth/verify-otp", data={"otp": otp}, follow_redirects=True)


def jwt_headers(client, username, password="admin123", otp=TEST_OTP):
    step1 = client.post("/auth/api/token", json={"username": username, "password": password})
    data = step1.get_json() or {}
    if step1.status_code != 200 or not data.get("otp_required"):
        raise AssertionError(f"Expected OTP challenge, got {step1.status_code}: {data}")
    step2 = client.post(
        "/auth/api/verify-otp",
        json={"challenge": data["challenge"], "otp": otp},
    )
    token_data = step2.get_json() or {}
    token = token_data.get("access_token")
    if not token:
        raise AssertionError(f"JWT verify failed: {step2.status_code}: {token_data}")
    return {"Authorization": f"Bearer {token}"}
