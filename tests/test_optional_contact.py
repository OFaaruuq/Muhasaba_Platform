"""Optional email and phone for students and teachers."""

from app.extensions import db
from app.models import Role, School, Teacher, User
from app.services.student_service import update_student
from app.services.teacher_service import update_teacher
from app.utils.contact_fields import normalize_optional_email, normalize_optional_phone


def test_normalize_optional_contact_fields():
    assert normalize_optional_email("") is None
    assert normalize_optional_email("  a@b.so  ") == "a@b.so"
    assert normalize_optional_phone("   ") is None
    assert normalize_optional_phone("0612345678") == "0612345678"


def test_user_email_nullable(app):
    with app.app_context():
        role = Role.query.filter_by(name="teacher").first()
        school = School.query.first()
        user = User(
            username="noteacher_email_test",
            email=None,
            full_name="Test",
            full_name_ar="اختبار",
            role_id=role.id,
            school_id=school.id,
            is_active=True,
            email_verified=True,
        )
        user.set_password("admin123")
        db.session.add(user)
        db.session.commit()
        saved = User.query.filter_by(username="noteacher_email_test").first()
        assert saved.email is None
        db.session.delete(saved)
        db.session.commit()


def test_update_teacher_clears_email_and_phone(app):
    with app.app_context():
        teacher = Teacher.query.filter_by(is_active=True).first()
        form = {
            "full_name_ar": teacher.full_name_ar,
            "employee_id": teacher.employee_id,
            "phone": "",
            "email": "",
            "username": teacher.user.username,
        }
        update_teacher(teacher, form)
        assert teacher.phone is None
        assert teacher.user.email is None


def test_update_student_clears_phone(app):
    with app.app_context():
        from app.models import Student

        student = Student.query.filter(
            Student.is_active.is_(True), Student.user_id.isnot(None)
        ).first()
        form = {
            "full_name_ar": student.full_name_ar,
            "grade_id": student.grade_id,
            "class_id": student.class_id,
            "region": student.region,
            "district": student.district,
            "address": student.address,
            "phone": "",
            "email": "",
            "username": student.user.username,
        }
        update_student(student, form)
        assert student.phone is None
        assert student.user.email is None


def test_create_teacher_without_email_or_phone(client, app):
    with app.app_context():
        school = School.query.first()

    from tests.auth_helpers import login_session
    login_session(client, "manager")
    resp = client.post(
        "/teachers/create",
        data={
            "school_id": school.id,
            "full_name_ar": "معلم بدون تواصل",
            "employee_id": "EMP-NO-CONTACT",
            "phone": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "المشرف الأعلى" in resp.get_data(as_text=True)

    with app.app_context():
        teacher = Teacher.query.filter_by(employee_id="EMP-NO-CONTACT").first()
        assert teacher is not None
        assert teacher.user_id is None
        assert teacher.phone is None
        db.session.delete(teacher)
        db.session.commit()
