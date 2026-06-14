"""Tests for dynamic attendance time rules."""

from app.models import Class, User
from app.services.attendance_time_service import (
    suggest_status_from_time, get_attendance_time_settings, parse_hhmm,
)


def test_parse_hhmm():
    assert parse_hhmm("08:15").hour == 8
    assert parse_hhmm("08:15").minute == 15


def test_suggest_present_on_time(app):
    with app.app_context():
        user = User.query.filter_by(username="manager").first()
        sid = user.school_id
        assert suggest_status_from_time(sid, "08:10") == "present"


def test_suggest_late(app):
    with app.app_context():
        user = User.query.filter_by(username="manager").first()
        sid = user.school_id
        assert suggest_status_from_time(sid, "08:30") == "late"


def test_suggest_absent(app):
    with app.app_context():
        user = User.query.filter_by(username="manager").first()
        sid = user.school_id
        assert suggest_status_from_time(sid, "09:00") == "absent"


def test_attendance_time_settings_defaults(app):
    with app.app_context():
        user = User.query.filter_by(username="manager").first()
        settings = get_attendance_time_settings(user.school_id)
        assert settings["enabled"] is True
        assert settings["on_time_until"] == "08:15"


def test_record_form_shows_time(client, app):
    with app.app_context():
        user = User.query.filter_by(username="teacher").first()
        class_id = user.teacher_profile.class_assignments[0].class_id

    from tests.auth_helpers import login_session; login_session(client, "teacher", "admin123")
    resp = client.get(f"/attendance/record/{class_id}")
    assert resp.status_code == 200
    assert "وقت الحضور" in resp.get_data(as_text=True)
