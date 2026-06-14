"""Admin settings center — dynamic CRUD."""

import re

from app.models import ConfigOption, PlatformSetting
from app.services.config_service import get_admin_config_sections


def _csrf(client):
    page = client.get("/admin/")
    m = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True))
    return m.group(1) if m else ""


def _login_manager(client):
    client.post("/auth/login", data={"username": "manager", "password": "admin123"})


def test_admin_index_loads(client):
    _login_manager(client)
    resp = client.get("/admin/")
    assert resp.status_code == 200
    assert "مركز إعدادات المنصة" in resp.get_data(as_text=True)
    assert "إعدادات متقدمة" in resp.get_data(as_text=True)
    assert "مصادر بيانات KPI" in resp.get_data(as_text=True)


def test_edit_config_option(client, app):
    _login_manager(client)
    with app.app_context():
        opt = ConfigOption.query.filter_by(option_type="exam_type", code="quiz").first()
        assert opt is not None
        opt_id = opt.id
        old_name = opt.name_ar

    resp = client.post(
        f"/admin/config-option/{opt_id}/edit",
        data={"name_ar": "اختبار قصير", "order": 1, "csrf_token": _csrf(client)},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        opt = ConfigOption.query.get(opt_id)
        assert opt.name_ar == "اختبار قصير"
        opt.name_ar = old_name
        from app.extensions import db
        db.session.commit()


def test_save_advanced_settings(client, app):
    _login_manager(client)
    with app.app_context():
        row = PlatformSetting.query.filter_by(key="report_kpi_title").first()
        assert row is not None
        new_title = "تقرير KPI مخصص"
        resp = client.post(
            "/admin/advanced-settings",
            data={f"ps_{row.id}": new_title, "csrf_token": _csrf(client)},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        updated = PlatformSetting.query.get(row.id)
        assert updated.value == new_title


def test_create_platform_setting(client, app):
    _login_manager(client)
    key = "test_custom_notify_title"
    resp = client.post(
        "/admin/platform-setting",
        data={
            "key": key,
            "value": "عنوان تجريبي",
            "category": "notifications",
            "label_ar": "عنوان تجريبي",
            "value_type": "string",
            "csrf_token": _csrf(client),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "تم إضافة الإعداد" in resp.get_data(as_text=True)
    with app.app_context():
        row = PlatformSetting.query.filter_by(key=key).first()
        assert row is not None
        assert row.value == "عنوان تجريبي"


def test_edit_rating(client, app):
    _login_manager(client)
    from app.models import RatingLevel
    with app.app_context():
        r = RatingLevel.query.filter_by(scale_type="qualitative", code="good").first()
        if not r:
            r = RatingLevel.query.filter(
                RatingLevel.scale_type.in_(("qualitative", None))
            ).first()
        assert r is not None
        rid = r.id

    resp = client.post(
        f"/admin/ratings/{rid}/edit",
        data={"name_ar": r.name_ar, "score": r.score, "order": r.order, "csrf_token": _csrf(client)},
        follow_redirects=True,
    )
    assert resp.status_code == 200


def test_get_admin_config_sections_includes_kpi_source(app):
    with app.app_context():
        sections, labels = get_admin_config_sections()
        assert "kpi_data_source" in sections
        assert "مصادر بيانات KPI" in labels.values()
