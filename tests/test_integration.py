"""Integration tests for module wiring, auth, and core flows."""

from app.models import Student, User
from app.kpi.service import recalculate_student_kpis, get_student_kpi_display
from tests.auth_helpers import jwt_headers, login_session


def test_all_blueprints_registered(app):
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    expected = {
        "auth.login", "dashboards.index", "schools.index", "students.index",
        "teachers.index", "attendance.index", "evaluations.index", "kpi.index",
        "questionnaires.index", "exams.index", "reports.index", "notifications.index",
        "users.index", "admin.index", "super_admin.index", "followup_surveys.index",
        "ai.index", "auth.api_token", "evaluations.api_grades", "evaluations.api_classes",
        "kpi.api_student_kpi",
    }
    missing = expected - endpoints
    assert not missing, f"Missing endpoints: {missing}"


def test_jwt_token_endpoint(client):
    headers = jwt_headers(client, "teacher")
    assert "Authorization" in headers
    resp = client.get("/kpi/api/student/1", headers=headers)
    assert resp.status_code in (200, 404)


def test_jwt_otp_challenge(client):
    resp = client.post(
        "/auth/api/token",
        json={"username": "teacher", "password": "admin123"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("otp_required") is True
    assert "challenge" in data


def test_jwt_api_requires_auth(client):
    resp = client.get("/kpi/api/student/1")
    assert resp.status_code == 401


def test_jwt_kpi_api(client, auth_headers, app):
    with app.app_context():
        student = Student.query.filter_by(is_active=True).first()
        assert student is not None
        resp = client.get(
            f"/kpi/api/student/{student.id}",
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "overall" in data
    assert "kpis" in data


def test_jwt_evaluations_api_grades(client, manager_auth_headers, app):
    with app.app_context():
        user = User.query.filter_by(username="manager").first()
        school_id = user.school_id
        resp = client.get(
            f"/evaluations/api/grades?school_id={school_id}",
            headers=manager_auth_headers,
        )
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_kpi_recalculation(app):
    with app.app_context():
        student = Student.query.filter_by(is_active=True).first()
        recalculate_student_kpis(student.id)
        scores, overall, breakdown = get_student_kpi_display(student.id)
        assert overall is not None
        assert len(breakdown) > 0


def test_login_and_dashboard(client):
    login_session(client, "teacher")
    resp = client.get("/dashboard/")
    assert resp.status_code == 200


def test_ai_module_accessible(client):
    login_session(client, "teacher")
    resp = client.get("/ai/")
    assert resp.status_code == 200
