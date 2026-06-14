"""Dynamic KPI index page tests."""

from app.services.config_service import get_kpi_source_options, ensure_school_defaults
from app.services.kpi_page_service import (
    build_kpi_summaries,
    build_students_kpi_rows,
    students_for_kpi_index,
)
from app.kpi.service import get_active_kpis
from app.models import School, User


def test_kpi_data_sources_from_config(app):
    with app.app_context():
        ensure_school_defaults(None)
        sources = dict(get_kpi_source_options(None))
        assert "attendance" in sources
        assert "homework" in sources
        assert sources["attendance"] == "سجل الحضور"


def test_build_kpi_summaries_for_school(app):
    with app.app_context():
        school = School.query.first()
        manager = User.query.filter_by(username="manager").first()
        kpis = get_active_kpis(school.id)
        students = students_for_kpi_index(manager, school.id)
        rows = build_students_kpi_rows(students[:3], kpis, "term")
        summaries = build_kpi_summaries(rows, kpis)
        assert len(summaries) == len(kpis)
        assert all("kpi" in item and "average" in item for item in summaries)


def test_kpi_index_page_renders_dynamic_columns(client, app):
    with app.app_context():
        school = School.query.first()
    from tests.auth_helpers import login_session; login_session(client, "manager", "admin123")
    resp = client.get("/kpi/?period=term")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "مؤشرات الأداء" in text
    assert "تعريف المؤشرات النشطة" in text
    assert "الحضور" in text or "الواجبات" in text
