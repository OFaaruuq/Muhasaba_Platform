import os
import tempfile

import pytest

from config import Config
from app import create_app, db
from app.models import seed_database


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    class TestConfig(Config):
        TESTING = True
        SECRET_KEY = "test-secret"
        JWT_SECRET_KEY = "test-jwt-secret"
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"
        WTF_CSRF_ENABLED = False

    application = create_app(TestConfig)

    with application.app_context():
        db.create_all()
        from app.utils.db_upgrade import (
            upgrade_student_schema, upgrade_kpi_schema, upgrade_config_schema,
            upgrade_attendance_schema, upgrade_attendance_weekly_schema, upgrade_reading_schema, upgrade_followup_survey_schema,
            upgrade_auth_schema, ensure_super_admin_role, upgrade_user_permissions_schema,
        )
        from app.services.config_service import ensure_school_defaults

        upgrade_student_schema()
        upgrade_kpi_schema()
        upgrade_config_schema()
        upgrade_attendance_schema()
        upgrade_attendance_weekly_schema()
        upgrade_reading_schema()
        upgrade_followup_survey_schema()
        upgrade_auth_schema()
        upgrade_user_permissions_schema()
        from app.utils.db_upgrade import upgrade_permissions
        upgrade_permissions()
        ensure_school_defaults(None)
        seed_database()
        from app.models import School
        for school in School.query.filter_by(is_active=True).all():
            ensure_school_defaults(school.id)
        ensure_super_admin_role()
        yield application
        db.session.remove()
        db.drop_all()

    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(client, app):
    """Return Authorization headers with a valid JWT for teacher user."""
    from tests.auth_helpers import jwt_headers
    with app.app_context():
        return jwt_headers(client, "teacher")


@pytest.fixture
def manager_auth_headers(client, app):
    """JWT headers for school manager (grades/classes API)."""
    from tests.auth_helpers import jwt_headers
    with app.app_context():
        return jwt_headers(client, "manager")
