"""Tests for student and teacher management (edit, deactivate)."""

from app.models import Student, User
from app.services.student_service import can_edit_student, can_manage_student


def test_manager_can_edit_student(app):
    with app.app_context():
        manager = User.query.filter_by(username="manager").first()
        student = Student.query.filter_by(school_id=manager.school_id, is_active=True).first()
        assert can_edit_student(manager, student)
        assert can_manage_student(manager, student)


def test_teacher_can_edit_assigned_student(app):
    with app.app_context():
        teacher = User.query.filter_by(username="teacher").first()
        from app.services.teacher_student_service import students_for_teacher
        student = students_for_teacher(teacher.teacher_profile)[0]
        assert can_edit_student(teacher, student)
        assert not can_manage_student(teacher, student)


def test_manager_students_index(client, app):
    client.post("/auth/login", data={"username": "manager", "password": "admin123"})
    resp = client.get("/students/")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "تسجيل طالب" in text or "الطلاب" in text


def test_manager_teachers_index(client, app):
    client.post("/auth/login", data={"username": "manager", "password": "admin123"})
    resp = client.get("/teachers/")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "تسجيل معلم" in text
    assert "المادة" in text
    assert "المجموعة / الفصل" in text


def test_manager_can_open_teacher_edit(client, app):
    with app.app_context():
        from app.models import Teacher
        teacher = Teacher.query.filter_by(is_active=True).first()
        tid = teacher.id

    client.post("/auth/login", data={"username": "manager", "password": "admin123"})
    resp = client.get(f"/teachers/{tid}/edit")
    assert resp.status_code == 200


def test_bulk_deactivate_students(client, app):
    with app.app_context():
        manager = User.query.filter_by(username="manager").first()
        students = (
            Student.query.filter_by(school_id=manager.school_id, is_active=True)
            .limit(1)
            .all()
        )
        assert students
        ids = [s.id for s in students]

    client.post("/auth/login", data={"username": "manager", "password": "admin123"})
    resp = client.post(
        "/students/bulk-action",
        data={"action": "deactivate", "student_ids": ids},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        for sid in ids:
            assert Student.query.get(sid).is_active is False


def test_manager_can_open_student_edit_with_grade_create(client, app):
    with app.app_context():
        student = Student.query.filter_by(is_active=True).first()
        sid = student.id

    client.post("/auth/login", data={"username": "manager", "password": "admin123"})
    resp = client.get(f"/students/{sid}/edit")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "إضافة مستوى" in text or "academicCreateGradeModal" in text


def test_bulk_action_requires_selection(client, app):
    client.post("/auth/login", data={"username": "manager", "password": "admin123"})
    resp = client.post(
        "/students/bulk-action",
        data={"action": "deactivate"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "لم يتم تحديد" in resp.get_data(as_text=True)

