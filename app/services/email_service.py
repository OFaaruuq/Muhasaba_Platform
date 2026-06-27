import logging
import smtplib
from email.message import EmailMessage

from flask import current_app, render_template_string

logger = logging.getLogger(__name__)


def _mail_configured():
    return bool(current_app.config.get("MAIL_SERVER"))


def _dev_email_fallback(to_address, subject, body_text, reason):
    """Log email to console when SMTP is unavailable (dev/test only)."""
    safe_body = body_text
    if "رمز التحقق" in (body_text or "") or "OTP" in (body_text or "").upper():
        safe_body = "[REDACTED OTP]"
    logger.info(
        "Email not sent (%s) — to %s | subject: %s | body: %s",
        reason,
        to_address,
        subject,
        safe_body,
    )
    if current_app.config.get("FLASK_DEBUG") or current_app.config.get("TESTING"):
        current_app.logger.warning(
            "[DEV EMAIL] %s\n to=%s subject=%s\n%s",
            reason,
            to_address,
            subject,
            safe_body,
        )


def send_email(to_address, subject, body_text, body_html=None):
    """Send an email; logs instead when SMTP is not configured or fails in dev."""
    if not to_address:
        return False

    if not _mail_configured():
        _dev_email_fallback(to_address, subject, body_text, "MAIL not configured")
        return True

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = current_app.config["MAIL_DEFAULT_SENDER"]
    msg["To"] = to_address
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    use_tls = current_app.config.get("MAIL_USE_TLS", True)
    port = current_app.config.get("MAIL_PORT", 587)
    server_host = current_app.config["MAIL_SERVER"]
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")

    try:
        if use_tls:
            with smtplib.SMTP(server_host, port, timeout=30) as smtp:
                smtp.starttls()
                if username and password:
                    smtp.login(username, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(server_host, port, timeout=30) as smtp:
                if username and password:
                    smtp.login(username, password)
                smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("SMTP failed for %s: %s", to_address, exc)
        if current_app.config.get("FLASK_DEBUG") or current_app.config.get("TESTING"):
            _dev_email_fallback(
                to_address,
                subject,
                body_text,
                f"SMTP failed ({exc.__class__.__name__})",
            )
            return True
        return False


def send_verification_email(user, verify_url):
    from app.services.config_service import get_setting
    from flask import has_request_context
    platform = get_setting("platform_name_ar", user.school_id, "منصة المحاسبة")
    if not has_request_context():
        platform = current_app.config.get("PLATFORM_NAME", platform)
    subject = f"تفعيل البريد — {platform}"
    body = render_template_string(
        """مرحباً {{ name }},

يرجى تفعيل بريدك الإلكتروني للوصول إلى {{ platform }}.

رابط التفعيل:
{{ url }}

إذا لم تطلب هذا الحساب، تجاهل هذه الرسالة.
""",
        name=user.full_name_ar or user.full_name,
        platform=platform,
        url=verify_url,
    )
    return send_email(user.email, subject, body)


def send_login_otp_email(user, otp_code):
    from app.services.config_service import get_setting
    platform = get_setting("platform_name_ar", user.school_id, "منصة المحاسبة")
    minutes = current_app.config.get("OTP_EXPIRY_MINUTES", 10)
    subject = f"رمز الدخول — {platform}"
    body = render_template_string(
        """مرحباً {{ name }},

رمز التحقق لمرة واحدة (OTP) لتسجيل الدخول:
{{ otp }}

صالح لمدة {{ minutes }} دقائق.
لا تشارك هذا الرمز مع أي شخص.
""",
        name=user.full_name_ar or user.full_name,
        otp=otp_code,
        minutes=minutes,
        platform=platform,
    )
    return send_email(user.email, subject, body)
