"""Tests for teacher-scoped attendance."""

from app.models import Class, User
from app.services.attendance_service import (
    can_record_class, attendance_teams_summary, classes_for_attendance,
)


def test_teacher_sees_assigned_classes(app):
    with app.app_context():
        user = User.query.filter_by(username="teacher").first()
        classes = classes_for_attendance(user)
        assert len(classes) >= 1
        teacher_class_ids = [tc.class_id for tc in user.teacher_profile.class_assignments]
        assert all(c.id in teacher_class_ids for c in classes)


def test_teacher_can_record_own_class(app):
    with app.app_context():
        user = User.query.filter_by(username="teacher").first()
        class_id = user.teacher_profile.class_assignments[0].class_id
        class_ = Class.query.get(class_id)
        assert can_record_class(user, class_)


def test_teacher_cannot_record_unassigned_class(app):
    with app.app_context():
        user = User.query.filter_by(username="teacher").first()
        assigned = {tc.class_id for tc in user.teacher_profile.class_assignments}
        other = Class.query.filter(Class.id.notin_(assigned)).first()
        if other:
            assert not can_record_class(user, other)


def test_teacher_attendance_index(client, app):
    from tests.auth_helpers import login_session; login_session(client, "teacher", "admin123")
    resp = client.get("/attendance/")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "فريقي" in text or "تسجيل الحضور" in text


def test_teacher_can_open_record_form(client, app):
    with app.app_context():
        user = User.query.filter_by(username="teacher").first()
        class_id = user.teacher_profile.class_assignments[0].class_id

    from tests.auth_helpers import login_session; login_session(client, "teacher", "admin123")
    resp = client.get(f"/attendance/record/{class_id}")
    assert resp.status_code == 200
    assert "حفظ حضور الفريق" in resp.get_data(as_text=True)
