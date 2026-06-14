"""RBAC: roles, permissions bootstrap, and per-user grants."""

from app.extensions import db
from app.models import Permission, Role, User
from app.services.permission_registry import (
    PERMISSIONS, SYSTEM_ROLE_DEFINITIONS, ensure_system_roles,
    set_user_extra_permissions,
)
from app.utils.permissions import user_has_permission, clear_permission_cache
from tests.auth_helpers import login_session


def test_all_permissions_exist_after_sync(app):
    with app.app_context():
        ensure_system_roles()
        assert Permission.query.count() == len(PERMISSIONS)


def test_all_system_roles_created(app):
    with app.app_context():
        ensure_system_roles()
        names = {r.name for r in Role.query.all()}
        assert names >= set(SYSTEM_ROLE_DEFINITIONS.keys())


def test_teacher_cannot_register_students_without_permission(client, app):
    with app.app_context():
        user = User.query.filter_by(username="teacher").first()
        assert not user_has_permission(user, "register_students")

    login_session(client, "teacher")
    resp = client.get("/evaluations/register", follow_redirects=True)
    assert resp.status_code == 403


def test_user_extra_permission_grants_register_students(client, app):
    with app.app_context():
        user = User.query.filter_by(username="teacher").first()
        perm = Permission.query.filter_by(name="register_students").first()
        set_user_extra_permissions(user, [perm.id])
        db.session.commit()
        clear_permission_cache()
        assert user_has_permission(user, "register_students")

    login_session(client, "teacher")
    resp = client.get("/evaluations/register", follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        user = User.query.filter_by(username="teacher").first()
        set_user_extra_permissions(user, [])
        db.session.commit()


def test_manager_can_create_teachers_with_permission(client, app):
    login_session(client, "manager")
    resp = client.get("/teachers/create")
    assert resp.status_code == 200


def test_manager_can_create_administrator_user(client, app):
    login_session(client, "manager")
    with app.app_context():
        from app.models import Role
        admin_role = Role.query.filter_by(name="school_manager").first()
        teacher_role = Role.query.filter_by(name="teacher").first()

    import re
    page = client.get("/users/create")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True))
    token = csrf.group(1) if csrf else ""

    resp = client.post(
        "/users/create",
        data={
            "username": "newadmin1",
            "full_name_ar": "مسؤول جديد",
            "email": "newadmin1@test.so",
            "password": "Secret123!",
            "role_id": admin_role.id,
            "phone": "",
            "csrf_token": token,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(username="newadmin1").first()
        assert user is not None
        assert user.role.name == "school_manager"
        assert user.school_id == 1

    # Also create a teacher in same school
    page2 = client.get("/users/create")
    csrf2 = re.search(r'name="csrf_token" value="([^"]+)"', page2.get_data(as_text=True))
    client.post(
        "/users/create",
        data={
            "username": "newteacheracct",
            "full_name_ar": "معلم حساب",
            "email": "newteacheracct@test.so",
            "password": "Secret123!",
            "role_id": teacher_role.id,
            "csrf_token": csrf2.group(1) if csrf2 else "",
        },
        follow_redirects=True,
    )
    with app.app_context():
        tuser = User.query.filter_by(username="newteacheracct").first()
        assert tuser is not None
        assert tuser.role.name == "teacher"


def test_teacher_cannot_assign_administrator_role(client, app):
    login_session(client, "teacher")
    resp = client.get("/users/create")
    assert resp.status_code == 403
