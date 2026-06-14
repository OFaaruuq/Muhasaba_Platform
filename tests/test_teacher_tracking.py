"""Tests for teacher student performance and follow-up tracking."""

from app.models import User
from app.services.teacher_tracking_service import build_teacher_tracking


def test_teacher_tracking_includes_students(client, app):
    with app.app_context():
        teacher_user = User.query.filter_by(username="teacher").first()
        teacher = teacher_user.teacher_profile
        tracking = build_teacher_tracking(teacher)
        assert tracking["student_count"] >= 1
        assert len(tracking["rows"]) == tracking["student_count"]
        row = tracking["rows"][0]
        assert "overall_kpi" in row
        assert "status_text" in row
        assert "needs_survey" in row


def test_teacher_dashboard_shows_tracking(client, app):
    from tests.auth_helpers import login_session; login_session(client, "teacher", "admin123")
    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "أداء طلابي" in text or "متابعة شهرية" in text
