"""Tests for dynamic teacher ↔ student group scoping."""

from app.models import Student, Teacher, TeacherClass
from app.services.teacher_student_service import (
    students_for_teacher,
    teacher_can_access_student,
    teacher_assigned_class_ids,
)
from app.services.followup_survey_service import students_for_user


def test_teacher_sees_only_assigned_group_students(app):
    with app.app_context():
        from app.models import User
        teacher_user = User.query.filter_by(username="teacher").first()
        teacher = teacher_user.teacher_profile
        assigned = students_for_teacher(teacher)
        assigned_ids = {s.id for s in assigned}

        all_school = Student.query.filter_by(
            school_id=teacher.school_id, is_active=True,
        ).all()
        assert len(assigned) <= len(all_school)

        for student in assigned:
            assert teacher_can_access_student(teacher_user, student)
            assert (
                student.responsible_teacher_id == teacher.id
                or student.class_id in teacher_assigned_class_ids(teacher)
            )

        for student in all_school:
            if student.id not in assigned_ids:
                assert not teacher_can_access_student(teacher_user, student)


def test_students_for_user_teacher_matches_students_for_teacher(app):
    with app.app_context():
        from app.models import User
        teacher_user = User.query.filter_by(username="teacher").first()
        direct = students_for_teacher(teacher_user.teacher_profile)
        via_user = students_for_user(teacher_user)
        assert {s.id for s in direct} == {s.id for s in via_user}


def test_teacher_without_class_assignments_sees_responsible_students_only(app):
    with app.app_context():
        from app.models import User
        teacher = Teacher.query.filter_by(is_active=True).first()
        TeacherClass.query.filter_by(teacher_id=teacher.id).delete()
        from app.extensions import db
        db.session.commit()

        students = students_for_teacher(teacher)
        for student in students:
            assert student.responsible_teacher_id == teacher.id
