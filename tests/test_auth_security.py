"""Authentication security: OTP, email verification, super-admin-only creation."""

from app.extensions import db
from app.models import User
from tests.auth_helpers import login_session, jwt_headers, TEST_OTP


def _login_password_only(client, username, password="admin123"):
    return client.post("/auth/login", data={"username": username, "password": password})


def test_inactive_user_cannot_login(client, app):
    with app.app_context():
        user = User.query.filter_by(username="manager").first()
        user.is_active = False
        db.session.commit()

    resp = _login_password_only(client, "manager")
    assert "غير مفعّل" in resp.get_data(as_text=True) or resp.status_code == 200

    with app.app_context():
        user = User.query.filter_by(username="manager").first()
        user.is_active = True
        db.session.commit()


def test_unverified_user_cannot_login(client, app):
    with app.app_context():
        user = User.query.filter_by(username="teacher").first()
        user.email_verified = False
        db.session.commit()

    resp = _login_password_only(client, "teacher")
    text = resp.get_data(as_text=True)
    assert "تفعيل بريدك" in text or "البريد" in text

    with app.app_context():
        user = User.query.filter_by(username="teacher").first()
        user.email_verified = True
        db.session.commit()


def test_otp_required_for_login(client):
    resp = _login_password_only(client, "manager")
    assert resp.status_code == 302
    assert "/auth/verify-otp" in resp.headers.get("Location", "")

    resp = client.post("/auth/verify-otp", data={"otp": TEST_OTP}, follow_redirects=True)
    assert resp.status_code == 200
    resp = client.get("/dashboard/")
    assert resp.status_code == 200


def test_wrong_otp_rejected(client):
    _login_password_only(client, "manager")
    resp = client.post("/auth/verify-otp", data={"otp": "000000"}, follow_redirects=True)
    assert "غير صحيح" in resp.get_data(as_text=True)


def test_manager_can_open_user_create_form(client):
    login_session(client, "manager")
    resp = client.get("/users/create")
    assert resp.status_code == 200
    assert "مدير المدرسة" in resp.get_data(as_text=True) or "مسؤول" in resp.get_data(as_text=True)


def test_super_admin_creates_inactive_unverified_user(client, app):
    login_session(client, "superadmin")
    with app.app_context():
        from app.models import Role
        role = Role.query.filter_by(name="school_manager").first()
        role_id = role.id

    resp = client.post(
        "/super-admin/users/create",
        data={
            "username": "newuser1",
            "full_name_ar": "مستخدم جديد",
            "email": "newuser1@test.so",
            "password": "Secret123!",
            "role_id": role_id,
            "csrf_token": _csrf_from_superadmin(client),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(username="newuser1").first()
        assert user is not None
        assert user.email_verified is False
        assert user.is_active is False


def test_jwt_requires_otp_second_step(client):
    step1 = client.post(
        "/auth/api/token",
        json={"username": "teacher", "password": "admin123"},
    )
    assert step1.get_json().get("otp_required") is True
    headers = jwt_headers(client, "teacher")
    assert headers["Authorization"].startswith("Bearer ")


def _csrf_from_superadmin(client):
    import re
    page = client.get("/super-admin/users/create")
    m = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True))
    return m.group(1) if m else ""
