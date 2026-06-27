"""Platform identity number tests."""

from app.models import Student, User
from app.services.identity_service import (
    allocate_platform_uid,
    ensure_identity_for_student,
    ensure_identity_for_user,
    person_display_label,
    can_view_person_names,
)


def test_allocate_platform_uid_unique(client, app):
    with app.app_context():
        uid1 = allocate_platform_uid()
        uid2 = allocate_platform_uid()
        assert uid1 != uid2
        assert uid1.startswith("MP-")


def test_student_gets_identity_on_registration(client, app):
    with app.app_context():
        student = Student.query.filter(Student.platform_uid.isnot(None)).first()
        assert student is not None
        assert student.platform_uid.startswith("MP-")


def test_non_admin_sees_uid_not_name(client, app):
    with app.app_context():
        student = Student.query.first()
        teacher_user = User.query.filter_by(username="teacher").first()
        label = person_display_label(student, teacher_user)
        assert label == student.platform_uid
        assert not can_view_person_names(teacher_user)


def test_admin_sees_name(client, app):
    with app.app_context():
        student = Student.query.first()
        manager = User.query.filter_by(username="manager").first()
        label = person_display_label(student, manager)
        assert label == (student.full_name_ar or student.full_name)
        assert can_view_person_names(manager)
