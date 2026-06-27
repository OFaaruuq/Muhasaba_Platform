import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.auth_token import LoginOtp


def _otp_length():
    return int(current_app.config.get("OTP_LENGTH", 6))


def _otp_expiry_minutes():
    return int(current_app.config.get("OTP_EXPIRY_MINUTES", 10))


def _otp_max_attempts():
    return int(current_app.config.get("OTP_MAX_ATTEMPTS", 5))


def generate_otp_code():
    if current_app.config.get("TESTING"):
        return "123456"
    return "".join(secrets.choice("0123456789") for _ in range(_otp_length()))


def _invalidate_pending(user_id, purpose):
    LoginOtp.query.filter_by(
        user_id=user_id,
        purpose=purpose,
        used=False,
    ).update({"used": True})
    db.session.flush()


def create_login_otp(user, purpose="login", ip_address=None):
    code = generate_otp_code()
    expires = datetime.now(timezone.utc) + timedelta(minutes=_otp_expiry_minutes())
    _invalidate_pending(user.id, purpose)
    row = LoginOtp(
        user_id=user.id,
        code_hash=generate_password_hash(code),
        purpose=purpose,
        expires_at=expires,
        ip_address=ip_address,
        failed_attempts=0,
    )
    db.session.add(row)
    db.session.commit()
    return code


def verify_otp(user_id, code, purpose="login"):
    if not code:
        return False
    now = datetime.now(timezone.utc)
    row = (
        LoginOtp.query.filter_by(user_id=user_id, purpose=purpose, used=False)
        .order_by(LoginOtp.created_at.desc())
        .first()
    )
    if not row:
        return False
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now > expires:
        return False
    if (row.failed_attempts or 0) >= _otp_max_attempts():
        row.used = True
        db.session.commit()
        return False
    if not check_password_hash(row.code_hash, code.strip()):
        row.failed_attempts = (row.failed_attempts or 0) + 1
        if row.failed_attempts >= _otp_max_attempts():
            row.used = True
        db.session.commit()
        return False
    row.used = True
    db.session.commit()
    return True
