"""Daily evaluation routes."""

from tests.auth_helpers import login_session


def test_daily_evaluation_superadmin_without_teacher_profile(client, app):
    login_session(client, "superadmin", "admin123")
    with app.app_context():
        from app.models import Student
        from app.services.config_service import get_criteria_grouped, get_default_rating_code

        student = Student.query.filter_by(is_active=True).first()
        assert student is not None
        sid = student.school_id
        form = {"notes": "test"}
        for category, items in get_criteria_grouped(sid).items():
            default = get_default_rating_code(sid)
            for crit in items:
                form[f"{category}_{crit.code}"] = default
        student_id = student.id

    resp = client.post(f"/evaluations/daily/{student_id}", data=form, follow_redirects=True)
    assert resp.status_code == 200
