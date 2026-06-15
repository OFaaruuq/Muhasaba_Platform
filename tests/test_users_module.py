"""Tests for /users/ school admin module."""

from app.models import User, Role, Teacher
from tests.auth_helpers import login_session


def _login_manager(client):
    login_session(client, "manager", "admin123")


def test_users_index_with_filters(client, app):
    _login_manager(client)
    resp = client.get("/users/?status=active")
    assert resp.status_code == 200
    assert "إدارة المستخدمين" in resp.get_data(as_text=True)


def test_users_create_teacher_with_profile(client, app):
    _login_manager(client)
    with app.app_context():
        role = Role.query.filter_by(name="teacher").first()
        school_id = User.query.filter_by(username="manager").first().school_id

    resp = client.post(
        "/users/create",
        data={
            "username": "newteacher99",
            "full_name_ar": "معلم تجريبي",
            "email": "newteacher99@test.local",
            "password": "admin123",
            "role_id": role.id,
            "school_id": school_id,
            "create_teacher_profile": "on",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(username="newteacher99").first()
        assert user is not None
        assert user.teacher_profile is not None
        db_cleanup_user(app, user)


def test_users_edit_email_duplicate(client, app):
    _login_manager(client)
    with app.app_context():
        manager = User.query.filter_by(username="manager").first()
        other = User.query.filter(
            User.school_id == manager.school_id,
            User.id != manager.id,
        ).first()
        if not other:
            return
        resp = client.post(
            f"/users/{other.id}/edit",
            data={
                "full_name_ar": other.full_name_ar,
                "email": manager.email,
                "role_id": other.role_id,
                "school_id": other.school_id,
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "مستخدم" in resp.get_data(as_text=True)


def test_users_resend_verification_route(client, app):
    _login_manager(client)
    with app.app_context():
        user = User.query.filter_by(email_verified=False).first()
        if not user or user.username == "manager":
            user = User.query.filter(
                User.email_verified == False,  # noqa: E712
                User.school_id == User.query.filter_by(username="manager").first().school_id,
            ).first()
        if not user:
            return
        uid = user.id

    resp = client.post(f"/users/{uid}/resend-verification", follow_redirects=True)
    assert resp.status_code == 200


def db_cleanup_user(app, user):
    from app.extensions import db
    with app.app_context():
        u = User.query.get(user.id)
        if u.teacher_profile:
            Teacher.query.filter_by(id=u.teacher_profile.id).delete()
        db.session.delete(u)
        db.session.commit()
