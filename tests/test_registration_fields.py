"""Tests for dynamic student registration fields."""

from app.models import Student, Grade, Class, School
from app.services.registration_field_service import (
    get_registration_config, validate_registration_fields, extract_registration_values,
)


def test_default_config_is_concise(app):
    with app.app_context():
        school = School.query.filter_by(is_active=True).first()
        config = get_registration_config(school.id)
        assert config["mode"] == "concise"
        visible_keys = {f["key"] for f in config["fields"] if f["visible"]}
        assert "full_name_ar" in visible_keys
        assert "gender" in visible_keys
        assert "region" not in visible_keys
        assert "address" not in visible_keys


def test_concise_registration_minimal_post(client, app):
    with app.app_context():
        school = School.query.filter_by(is_active=True).first()
        grade = Grade.query.filter_by(school_id=school.id).first()
        class_ = Class.query.filter_by(school_id=school.id, grade_id=grade.id).first()
        before = Student.query.count()

    client.post("/auth/login", data={"username": "manager", "password": "admin123"})
    resp = client.post(
        "/evaluations/register",
        data={
            "school_id": school.id,
            "grade_id": grade.id,
            "class_id": class_.id,
            "full_name_ar": "طالب تجريبي",
            "gender": "male",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        assert Student.query.count() == before + 1
        student = Student.query.filter_by(full_name_ar="طالب تجريبي").first()
        assert student is not None
        assert student.region
        assert student.district
        assert student.address


def test_validate_requires_core_fields(app):
    with app.app_context():
        school = School.query.filter_by(is_active=True).first()
        errors = validate_registration_fields({}, school.id)
        assert any("الاسم بالعربية" in e for e in errors)
        assert any("المدرسة" in e for e in errors)


def test_extract_uses_school_defaults_for_hidden_location(app):
    with app.app_context():
        from app.extensions import db
        school = School.query.filter_by(is_active=True).first()
        school.region = "بنادر"
        school.district = "هودان"
        school.address = "مقديشو"
        db.session.commit()
        values = extract_registration_values({"full_name_ar": "اختبار"}, school.id)
        assert values["region"] == "بنادر"
        assert values["district"] == "هودان"
        assert values["address"] == "مقديشو"
