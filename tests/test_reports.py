"""Reports hub page tests."""

from tests.auth_helpers import login_session


def test_reports_index_loads_for_manager(client):
    login_session(client, "manager", "admin123")
    resp = client.get("/reports/")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "مركز التقارير" in text or "التقارير" in text
    assert "reports-table" in text or "تقارير الطلاب" in text


def test_reports_index_with_filters(client):
    login_session(client, "manager", "admin123")
    resp = client.get("/reports/?tab=students&status=complete")
    assert resp.status_code == 200


def test_reports_kpi_pdf_requires_auth(client, app):
    with app.app_context():
        from app.models import Student
        student = Student.query.filter_by(is_active=True).first()
        sid = student.id
    resp = client.get(f"/reports/student/{sid}/kpi-pdf")
    assert resp.status_code in (302, 403)
