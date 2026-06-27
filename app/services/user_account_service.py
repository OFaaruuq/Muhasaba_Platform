import secrets
from datetime import datetime, timezone, timedelta

from flask import url_for

from app.extensions import db
from app.models import User
from app.services.email_service import send_verification_email
from app.services.otp_service import create_login_otp


def generate_email_verification_token():
    return secrets.token_urlsafe(32)


def create_user_by_super_admin(
    *,
    username,
    email,
    full_name_ar,
    password,
    role_id,
    school_id=None,
    phone=None,
    is_active=False,
    send_verification=True,
):
    """Only super admin should call this — new users start inactive until activated."""
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("البريد الإلكتروني مطلوب لتفعيل الحساب وإرسال OTP.")

    if User.query.filter_by(username=username).first():
        raise ValueError("اسم المستخدم موجود.")
    if User.query.filter_by(email=email).first():
        raise ValueError("البريد الإلكتروني مستخدم.")

    token = generate_email_verification_token()
    user = User(
        username=username.strip(),
        email=email,
        full_name=full_name_ar,
        full_name_ar=full_name_ar,
        phone=phone,
        role_id=role_id,
        school_id=school_id,
        is_active=is_active,
        email_verified=False,
        email_verification_token=token,
        email_verification_sent_at=datetime.now(timezone.utc),
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    from app.services.identity_service import ensure_identity_for_user
    ensure_identity_for_user(user)

    if send_verification:
        verify_url = url_for("auth.verify_email", token=token, _external=True)
        send_verification_email(user, verify_url)

    return user


def create_user_by_admin(
    actor,
    *,
    username,
    email,
    full_name_ar,
    password,
    role_id,
    school_id=None,
    phone=None,
    is_active=False,
    send_verification=True,
):
    """Create a user scoped by the acting admin's permissions and school."""
    from app.models import Role
    from app.utils.permissions import (
        can_create_users,
        can_assign_role,
        resolve_new_user_school_id,
    )

    if not can_create_users(actor):
        raise ValueError("ليس لديك صلاحية إنشاء المستخدمين.")

    role = Role.query.get(role_id)
    if not role or not can_assign_role(actor, role.name):
        raise ValueError("لا يمكن تعيين هذا الدور.")

    scoped_school = resolve_new_user_school_id(actor, school_id)
    if not scoped_school and role.name in ("school_manager", "teacher", "student", "parent"):
        raise ValueError("يجب تحديد المدرسة لهذا الدور.")

    return create_user_by_super_admin(
        username=username,
        email=email,
        full_name_ar=full_name_ar,
        password=password,
        role_id=role_id,
        school_id=scoped_school,
        phone=phone,
        is_active=is_active,
        send_verification=send_verification,
    )


def update_user_by_admin(actor, user, form):
    """Update user fields with validation (email uniqueness, role assignment)."""
    from app.models import Role
    from app.utils.permissions import can_assign_role, is_platform_admin

    new_role_id = int(form["role_id"])
    new_role = Role.query.get(new_role_id)
    if not new_role or not can_assign_role(actor, new_role.name):
        raise ValueError("لا يمكن تعيين هذا الدور.")

    email = (form.get("email") or "").strip().lower()
    if not email:
        raise ValueError("البريد الإلكتروني مطلوب.")
    if User.query.filter(User.email == email, User.id != user.id).first():
        raise ValueError("البريد الإلكتروني مستخدم.")

    user.full_name_ar = (form.get("full_name_ar") or "").strip()
    user.full_name = user.full_name_ar
    user.email = email
    user.phone = form.get("phone")
    user.role_id = new_role_id

    if is_platform_admin(actor):
        school_id = form.get("school_id", type=int)
        if school_id:
            user.school_id = school_id

    if form.get("password"):
        user.set_password(form["password"])

    return user, new_role


def resend_verification_email(user):
    if not user.email:
        raise ValueError("لا يوجد بريد إلكتروني لهذا المستخدم.")
    if user.email_verified:
        raise ValueError("البريد مُفعَّل مسبقاً.")

    user.email_verification_token = generate_email_verification_token()
    user.email_verification_sent_at = datetime.now(timezone.utc)
    db.session.commit()
    verify_url = url_for("auth.verify_email", token=user.email_verification_token, _external=True)
    send_verification_email(user, verify_url)
    return user


def verify_email_token(token):
    from flask import current_app

    user = User.query.filter_by(email_verification_token=token).first()
    if not user:
        return None, "invalid"
    sent_at = user.email_verification_sent_at
    if sent_at:
        hours = int(current_app.config.get("EMAIL_VERIFICATION_EXPIRY_HOURS", 48))
        expires = sent_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires + timedelta(hours=hours):
            return None, "expired"
    user.email_verified = True
    user.email_verification_token = None
    db.session.commit()
    return user, None


def can_user_authenticate(user):
    """Checks before sending login OTP."""
    if not user:
        return False, "invalid"
    if not user.is_active:
        return False, "inactive"
    if not user.email_verified:
        return False, "unverified"
    if not user.email:
        return False, "no_email"
    return True, None


def issue_login_otp(user, ip_address=None):
    from app.services.email_service import send_login_otp_email

    code = create_login_otp(user, purpose="login", ip_address=ip_address)
    if not send_login_otp_email(user, code):
        raise RuntimeError("تعذّر إرسال رمز التحقق إلى البريد الإلكتروني.")
    return code
