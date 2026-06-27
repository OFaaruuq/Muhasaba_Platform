"""Database bootstrap and connection helpers — single source: config / .env."""

import logging

from sqlalchemy import inspect, text

from app.extensions import db

logger = logging.getLogger(__name__)


def get_dialect():
    return db.engine.dialect.name


def is_postgresql():
    return get_dialect() in ("postgresql", "postgres")


def database_label(app):
    """Safe URI for logs (password hidden)."""
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if "@" in uri and "://" in uri:
        prefix, rest = uri.split("://", 1)
        if "@" in rest:
            creds, hostpart = rest.rsplit("@", 1)
            if ":" in creds:
                user = creds.split(":", 1)[0]
                return f"{prefix}://{user}:***@{hostpart}"
    return uri


def validate_connection():
    """Fail fast if DATABASE_URL from .env is unreachable."""
    with db.engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def _tables_exist():
    return bool(inspect(db.engine).get_table_names())


def apply_migrations():
    """Run Alembic migrations (uses SQLALCHEMY_DATABASE_URI from .env)."""
    from flask_migrate import upgrade
    upgrade()


def init_database(seed=True):
    """
    Initialize DB from .env: migrations (or create_all), schema patches, optional seed.
    Safe to call on every startup — seed skips if data exists.
    """
    from app.utils.db_upgrade import (
        apply_schema_upgrades,
        repair_student_user_links,
        ensure_super_admin_role,
    )
    from app.services.config_service import ensure_school_defaults

    if not _tables_exist():
        try:
            apply_migrations()
        except Exception as exc:
            logger.warning("Migration upgrade failed (%s); falling back to create_all.", exc)
            db.create_all()
    else:
        try:
            apply_migrations()
        except Exception as exc:
            logger.debug("Migration check skipped: %s", exc)

    apply_schema_upgrades()
    repair_student_user_links()
    ensure_school_defaults(None)

    if seed:
        from app.models import seed_database, School
        from app.models.seed_bulk import seed_bulk_accounts

        seed_database()
        seed_bulk_accounts()
        for school in School.query.filter_by(is_active=True).all():
            ensure_school_defaults(school.id)
        ensure_super_admin_role()

    db.session.commit()