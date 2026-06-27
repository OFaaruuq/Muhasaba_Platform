import logging
import os
import secrets
from datetime import timedelta

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))

logger = logging.getLogger(__name__)


def _env_bool(name, default="false"):
    return os.environ.get(name, default).lower() in ("1", "true", "yes")


def _postgres_uri_from_env(*, strict=False):
    user = os.environ.get("POSTGRES_USER", "muhasaba")
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        if strict:
            raise RuntimeError("POSTGRES_PASSWORD or DATABASE_URL is required in production.")
        password = "muhasaba"
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "muhasaba")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def _database_uri(*, strict=False):
    uri = os.environ.get("DATABASE_URL")
    if not uri:
        return _postgres_uri_from_env(strict=strict)
    if uri.startswith("postgres://"):
        uri = "postgresql://" + uri[len("postgres://"):]
    if uri.startswith("sqlite:///") and not uri.startswith("sqlite:////"):
        db_file = uri[len("sqlite:///"):]
        if not os.path.isabs(db_file):
            db_file = os.path.join(basedir, db_file)
        return "sqlite:///" + db_file.replace("\\", "/")
    return uri


def finalize_app_config(app):
    """Resolve secrets and database URI after config object is loaded."""
    debug = app.config.get("FLASK_DEBUG", False)
    testing = app.config.get("TESTING", False)

    for key in ("SECRET_KEY", "JWT_SECRET_KEY"):
        if not app.config.get(key):
            if debug or testing:
                app.config[key] = secrets.token_hex(32)
                logger.warning("%s not set — using ephemeral dev secret", key)
            else:
                raise RuntimeError(f"{key} must be set when FLASK_DEBUG is disabled.")

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = _database_uri(strict=not debug and not testing)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or None
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(os.environ.get("DB_POOL_RECYCLE", "300")),
    }
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    UPLOAD_FOLDER = os.path.join(basedir, "uploads")
    REPORTS_FOLDER = os.path.join(basedir, "reports")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    WTF_CSRF_ENABLED = True
    BABEL_DEFAULT_LOCALE = "ar"
    PLATFORM_NAME = os.environ.get("PLATFORM_NAME", "منصة المحاسبة التعليمية")
    PLATFORM_TAGLINE = os.environ.get(
        "PLATFORM_TAGLINE",
        "قياس الأداء، تطوير السلوك، وبناء مستقبل أفضل",
    )
    PLATFORM_OWNER_SLUG = os.environ.get("PLATFORM_OWNER_SLUG", "netrich")
    PLATFORM_OWNER_NAME = os.environ.get("PLATFORM_OWNER_NAME", "Netrich")
    PLATFORM_OWNER_NAME_AR = os.environ.get("PLATFORM_OWNER_NAME_AR", "نيتريش")
    FLASK_DEBUG = _env_bool("FLASK_DEBUG", "false")

    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", "false")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=int(os.environ.get("SESSION_LIFETIME_HOURS", "8"))
    )
    REMEMBER_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", "false")
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", "true")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER",
        os.environ.get("MAIL_USERNAME", "noreply@muhasaba.local"),
    )
    OTP_LENGTH = int(os.environ.get("OTP_LENGTH", "6"))
    OTP_EXPIRY_MINUTES = int(os.environ.get("OTP_EXPIRY_MINUTES", "10"))
    OTP_MAX_ATTEMPTS = int(os.environ.get("OTP_MAX_ATTEMPTS", "5"))
    EMAIL_VERIFICATION_EXPIRY_HOURS = int(os.environ.get("EMAIL_VERIFICATION_EXPIRY_HOURS", "48"))

    RATELIMIT_ENABLED = _env_bool("RATELIMIT_ENABLED", "true")
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200 per hour")
    RATELIMIT_LOGIN = os.environ.get("RATELIMIT_LOGIN", "10 per minute")
    RATELIMIT_OTP = os.environ.get("RATELIMIT_OTP", "10 per minute")
