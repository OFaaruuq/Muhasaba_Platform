from datetime import datetime, timezone

from app.extensions import db


class LoginOtp(db.Model):
    """One-time codes for login and email verification."""

    __tablename__ = "login_otps"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    code_hash = db.Column(db.String(256), nullable=False)
    purpose = db.Column(db.String(20), default="login", index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    failed_attempts = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ip_address = db.Column(db.String(45))

    user = db.relationship("User", backref=db.backref("login_otps", lazy="dynamic"))
