"""Tests for dynamic roles and permissions."""

from app.extensions import db
from app.models import Role, User, Permission
from app.services.permission_registry import (
    sync_permissions, apply_default_role_permissions, PERMISSIONS,
    user_matches_legacy_roles,
)
from app.utils.permissions import user_has_permission, clear_permission_cache


def test_permissions_synced(app):
    with app.app_context():
        sync_permissions()
        count = Permission.query.count()
        assert count == len(PERMISSIONS)


def test_teacher_has_record_attendance(app):
    with app.app_context():
        user = User.query.filter_by(username="teacher").first()
        assert user_has_permission(user, "record_attendance")
        assert user_has_permission(user, "manage_evaluations")


def test_student_denied_manage_evaluations(app):
    with app.app_context():
        user = User.query.filter_by(username="student").first()
        assert not user_has_permission(user, "manage_evaluations")
        assert user_has_permission(user, "self_assess")


def test_custom_role_inherits_teacher_capabilities(app, client):
    with app.app_context():
        sync_permissions()
        role = Role(name="counselor", name_ar="مرشد", description="Test role")
        db.session.add(role)
        db.session.flush()
        for perm_name in ("record_attendance", "manage_evaluations", "view_students"):
            perm = Permission.query.filter_by(name=perm_name).first()
            role.permissions.append(perm)
        counselor = User(
            username="counselor1",
            email="counselor@test.so",
            full_name="Counselor",
            full_name_ar="مرشد",
            role_id=role.id,
            school_id=1,
            is_active=True,
            email_verified=True,
        )
        counselor.set_password("admin123")
        db.session.add(counselor)
        db.session.commit()
        clear_permission_cache()

        counselor = User.query.filter_by(username="counselor1").first()
        assert user_matches_legacy_roles(counselor, "teacher")

        from tests.auth_helpers import login_session
        login_session(client, "counselor1")
        resp = client.get("/attendance/")
        assert resp.status_code == 200


def test_super_admin_manage_system(app):
    with app.app_context():
        user = User.query.filter_by(username="superadmin").first()
        assert user_has_permission(user, "manage_system")
        assert user_has_permission(user, "manage_roles")
