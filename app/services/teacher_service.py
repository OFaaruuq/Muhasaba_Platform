"""Teacher management — update, deactivate, assignment helpers."""

from app.extensions import db
from app.utils.contact_fields import normalize_optional_email, normalize_optional_phone
from app.services.subject_service import resolve_subject_from_form
from app.models import (
    Teacher, TeacherClass, User, Student, Exam,
    Evaluation, TeacherMonthlySurvey, EducationalProgramFollowupSurvey,
    ClassSubject,
)


def teacher_in_scope(user, teacher):
    if user.is_platform_admin:
        return True
    return teacher.school_id == user.school_id


def update_teacher(teacher, form, allow_school_change=False):
    """Update teacher profile and linked user account from form data."""
    employee_id = (form.get("employee_id") or "").strip()
    if employee_id and employee_id != teacher.employee_id:
        existing = Teacher.query.filter(
            Teacher.employee_id == employee_id,
            Teacher.id != teacher.id,
        ).first()
        if existing:
            raise ValueError("الرقم الوظيفي مستخدم لمعلم آخر.")

    full_name_ar = (form.get("full_name_ar") or "").strip()
    if not full_name_ar:
        raise ValueError("الاسم مطلوب.")

    teacher.employee_id = employee_id or teacher.employee_id
    teacher.full_name_ar = full_name_ar
    teacher.full_name = (form.get("full_name") or full_name_ar).strip()
    teacher.specialization = resolve_subject_from_form(teacher.school_id, form)
    teacher.phone = normalize_optional_phone(form.get("phone"))

    hire_date = form.get("hire_date")
    if hire_date:
        from datetime import datetime
        teacher.hire_date = datetime.strptime(hire_date, "%Y-%m-%d").date()

    if allow_school_change and form.get("school_id"):
        teacher.school_id = int(form["school_id"])

    user = teacher.user
    if user:
        username = (form.get("username") or "").strip()
        if username and username != user.username:
            if User.query.filter(User.username == username, User.id != user.id).first():
                raise ValueError("اسم المستخدم موجود.")
            user.username = username

        email = normalize_optional_email(form.get("email"))
        if email:
            existing_email = User.query.filter(
                User.email == email, User.id != user.id
            ).first()
            if existing_email:
                raise ValueError("البريد الإلكتروني مستخدم.")
        user.email = email

        user.full_name = teacher.full_name
        user.full_name_ar = teacher.full_name_ar
        user.phone = teacher.phone
        if allow_school_change and form.get("school_id"):
            user.school_id = teacher.school_id

        password = form.get("password")
        if password:
            user.set_password(password)

    db.session.commit()


def deactivate_teacher(teacher):
    teacher.is_active = False
    if teacher.user:
        teacher.user.is_active = False
    db.session.commit()


def activate_teacher(teacher):
    teacher.is_active = True
    if teacher.user:
        teacher.user.is_active = True
    db.session.commit()


def remove_assignment(teacher, assignment_id):
    assignment = TeacherClass.query.filter_by(
        id=assignment_id, teacher_id=teacher.id,
    ).first()
    if not assignment:
        raise ValueError("التعيين غير موجود.")
    db.session.delete(assignment)
    db.session.commit()


def teacher_usage_counts(teacher_id):
    return {
        "students": Student.query.filter_by(
            responsible_teacher_id=teacher_id, is_active=True,
        ).count(),
        "exams": Exam.query.filter_by(teacher_id=teacher_id).count(),
        "evaluations": Evaluation.query.filter_by(teacher_id=teacher_id).count(),
        "teacher_surveys": TeacherMonthlySurvey.query.filter_by(
            teacher_id=teacher_id,
        ).count(),
        "program_surveys": EducationalProgramFollowupSurvey.query.filter_by(
            teacher_id=teacher_id,
        ).count(),
        "class_subjects": ClassSubject.query.filter_by(teacher_id=teacher_id).count(),
        "assignments": TeacherClass.query.filter_by(teacher_id=teacher_id).count(),
    }


def teacher_index_summaries(teachers):
    """
    Per-teacher class groups and subjects for list views.
    Returns {teacher_id: {"classes": [...], "subjects": [...]}}.
    """
    if not teachers:
        return {}

    teacher_ids = [t.id for t in teachers]
    summaries = {tid: {"classes": [], "subjects": []} for tid in teacher_ids}

    assignments = (
        TeacherClass.query.filter(TeacherClass.teacher_id.in_(teacher_ids))
        .all()
    )
    for assignment in assignments:
        row = summaries[assignment.teacher_id]
        if assignment.class_:
            name = assignment.class_.name
            if name not in row["classes"]:
                row["classes"].append(name)
        if assignment.subject and assignment.subject.name_ar:
            subj = assignment.subject.name_ar
            if subj not in row["subjects"]:
                row["subjects"].append(subj)

    responsible_students = Student.query.filter(
        Student.responsible_teacher_id.in_(teacher_ids),
        Student.is_active == True,  # noqa: E712
    ).all()
    for student in responsible_students:
        if student.class_:
            name = student.class_.name
            row = summaries[student.responsible_teacher_id]
            if name not in row["classes"]:
                row["classes"].append(name)

    for teacher in teachers:
        row = summaries[teacher.id]
        if not row["subjects"] and teacher.specialization:
            row["subjects"] = [teacher.specialization]

    return summaries
