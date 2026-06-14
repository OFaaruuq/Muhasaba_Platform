import os
from datetime import timedelta

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


def _postgres_uri_from_env():
    user = os.environ.get("POSTGRES_USER", "muhasaba")
    password = os.environ.get("POSTGRES_PASSWORD", "muhasaba")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "muhasaba")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def _database_uri():
    uri = os.environ.get("DATABASE_URL")
    if not uri:
        return _postgres_uri_from_env()
    if uri.startswith("postgres://"):
        uri = "postgresql://" + uri[len("postgres://"):]
    if uri.startswith("sqlite:///") and not uri.startswith("sqlite:////"):
        db_file = uri[len("sqlite:///"):]
        if not os.path.isabs(db_file):
            db_file = os.path.join(basedir, db_file)
        return "sqlite:///" + db_file.replace("\\", "/")
    return uri


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "muhasaba-dev-secret-change-in-production")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(os.environ.get("DB_POOL_RECYCLE", "300")),
    }
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "muhasaba-jwt-secret-change-in-production")
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
    FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER",
        os.environ.get("MAIL_USERNAME", "noreply@muhasaba.local"),
    )
    OTP_LENGTH = int(os.environ.get("OTP_LENGTH", "6"))
    OTP_EXPIRY_MINUTES = int(os.environ.get("OTP_EXPIRY_MINUTES", "10"))
