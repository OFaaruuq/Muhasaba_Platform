from datetime import datetime, timezone, timedelta

from flask import current_app, redirect, render_template, request, session, url_for
from app.services.message_service import flash_msg, msg
from flask_login import current_user, login_required, login_user, logout_user
from flask_jwt_extended import create_access_token

from app.auth import bp
from app.extensions import db, limiter
from app.models import User, AuditLog
from app.services.otp_service import verify_otp as verify_otp_code
from app.services.user_account_service import (
    can_user_authenticate,
    issue_login_otp,
    resend_verification_email,
    verify_email_token,
)
from app.utils.security import is_safe_url, safe_redirect_target

AUTH_PUBLIC_ENDPOINTS = {
    "auth.login",
    "auth.verify_otp",
    "auth.verify_email",
    "auth.resend_verification",
    "auth.api_token",
    "auth.api_verify_otp",
}


def _login_flash(reason):
    keys = {
        "inactive": "auth_login_inactive",
        "unverified": "auth_login_unverified",
        "no_email": "auth_login_no_email",
        "invalid": "auth_login_invalid",
    }
    flash_msg(keys.get(reason, "auth_login_invalid"), "danger")


def _login_error_message(reason):
    keys = {
        "inactive": "auth_login_inactive",
        "unverified": "auth_login_unverified",
        "no_email": "auth_login_no_email",
        "invalid": "auth_login_invalid",
    }
    return msg(keys.get(reason, "auth_login_invalid"))


def _rate_limit_login():
    return current_app.config.get("RATELIMIT_LOGIN", "10 per minute")


def _rate_limit_otp():
    return current_app.config.get("RATELIMIT_OTP", "10 per minute")


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(_rate_limit_login, methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboards.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            _login_flash("invalid")
            return render_template("auth/login.html")

        ok, reason = can_user_authenticate(user)
        if not ok:
            _login_flash(reason)
            if reason == "unverified":
                session["resend_user_id"] = user.id
            return render_template("auth/login.html", show_resend=reason == "unverified")

        try:
            issue_login_otp(user, ip_address=request.remote_addr)
        except RuntimeError:
            flash_msg("auth_otp_send_failed", "danger")
            return render_template("auth/login.html")

        session["pending_login_user_id"] = user.id
        session["pending_remember"] = bool(request.form.get("remember"))
        next_arg = request.args.get("next")
        session["pending_next"] = next_arg if is_safe_url(next_arg) else None
        flash_msg("auth_otp_sent", "info")
        return redirect(url_for("auth.verify_otp"))

    return render_template("auth/login.html")


@bp.route("/verify-otp", methods=["GET", "POST"])
@limiter.limit(_rate_limit_otp, methods=["POST"])
def verify_otp():
    if current_user.is_authenticated:
        return redirect(url_for("dashboards.index"))

    user_id = session.get("pending_login_user_id")
    if not user_id:
        flash_msg("auth_otp_session_expired", "warning")
        return redirect(url_for("auth.login"))

    user = User.query.get(user_id)
    if not user:
        session.pop("pending_login_user_id", None)
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        code = request.form.get("otp", "").strip()
        if verify_otp_code(user.id, code, purpose="login"):
            login_user(user, remember=session.pop("pending_remember", False))
            user.last_login = datetime.now(timezone.utc)
            db.session.add(AuditLog(
                user_id=user.id,
                action="login",
                module="auth",
                ip_address=request.remote_addr,
            ))
            db.session.commit()
            session.pop("pending_login_user_id", None)
            next_page = session.pop("pending_next", None)
            flash_msg("auth_welcome", "success", name=user.full_name_ar or user.full_name)
            return redirect(
                safe_redirect_target(next_page, "dashboards.index")
            )
        flash_msg("auth_otp_invalid", "danger")

    masked_email = user.email
    if masked_email and "@" in masked_email:
        local, domain = masked_email.split("@", 1)
        masked_email = (local[:2] + "***@" + domain) if len(local) > 2 else ("***@" + domain)

    return render_template("auth/verify_otp.html", masked_email=masked_email)


@bp.route("/verify-email/<token>")
def verify_email(token):
    user, err = verify_email_token(token)
    if err:
        flash_msg("auth_verify_link_invalid", "danger")
        return render_template("auth/verify_email.html", success=False)
    flash_msg("auth_email_verified", "success")
    return render_template("auth/verify_email.html", success=True, user=user)


@bp.route("/resend-verification", methods=["POST"])
def resend_verification():
    user_id = session.get("resend_user_id") or request.form.get("user_id", type=int)
    if not user_id:
        flash_msg("auth_resend_blocked", "danger")
        return redirect(url_for("auth.login"))

    user = User.query.get(user_id)
    if not user:
        flash_msg("auth_user_not_found", "danger")
        return redirect(url_for("auth.login"))

    try:
        resend_verification_email(user)
        flash_msg("auth_verification_sent", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    return redirect(url_for("auth.login"))


@bp.route("/logout")
@login_required
def logout():
    db.session.add(AuditLog(
        user_id=current_user.id,
        action="logout",
        module="auth",
        ip_address=request.remote_addr,
    ))
    db.session.commit()
    logout_user()
    session.clear()
    flash_msg("auth_logout", "info")
    return redirect(url_for("auth.login"))


@bp.route("/api/token", methods=["POST"])
@limiter.limit(_rate_limit_login)
def api_token():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password):
        return {"error": "بيانات الدخول غير صحيحة"}, 401

    ok, reason = can_user_authenticate(user)
    if not ok:
        return {"error": _login_error_message(reason), "reason": reason}, 403

    issue_login_otp(user, ip_address=request.remote_addr)
    challenge = create_access_token(
        identity=str(user.id),
        additional_claims={"type": "otp_challenge"},
        expires_delta=timedelta(minutes=10),
    )
    return {
        "otp_required": True,
        "challenge": challenge,
        "message": "تم إرسال رمز OTP إلى البريد الإلكتروني.",
    }


@bp.route("/api/verify-otp", methods=["POST"])
@limiter.limit(_rate_limit_otp)
def api_verify_otp():
    from flask_jwt_extended import decode_token
    from flask_jwt_extended.exceptions import JWTDecodeError

    data = request.get_json(silent=True) or {}
    challenge = data.get("challenge", "")
    otp = data.get("otp", "").strip()
    if not challenge or not otp:
        return {"error": "رمز التحقق والتحدي مطلوبان"}, 400

    try:
        decoded = decode_token(challenge)
    except JWTDecodeError:
        return {"error": "جلسة التحقق غير صالحة"}, 401

    if decoded.get("type") != "otp_challenge":
        return {"error": "رمز التحدي غير صالح"}, 401

    user_id = int(decoded["sub"])
    user = User.query.get(user_id)
    if not user:
        return {"error": "المستخدم غير موجود"}, 404

    ok, reason = can_user_authenticate(user)
    if not ok:
        return {"error": _login_error_message(reason), "reason": reason}, 403

    if not verify_otp_code(user.id, otp, purpose="login"):
        return {"error": "رمز OTP غير صحيح أو منتهٍ"}, 401

    user.last_login = datetime.now(timezone.utc)
    db.session.add(AuditLog(
        user_id=user.id,
        action="api_login",
        module="auth",
        ip_address=request.remote_addr,
    ))
    db.session.commit()

    token = create_access_token(identity=str(user.id), additional_claims={
        "role": user.role.name,
        "school_id": user.school_id,
    })
    return {"access_token": token, "role": user.role.name}