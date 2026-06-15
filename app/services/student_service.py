"""Student profile updates and access helpers."""

from datetime import datetime

from app.extensions import db
from app.models import Student, User, Class, Grade
from app.utils.contact_fields import normalize_optional_email, normalize_optional_phone
from app.services.attendance_limit_service import parse_weekly_limit
from app.services.teacher_student_service import teacher_can_access_student


def can_edit_student(user, student):
    if user.is_platform_admin:
        return True
    if user.is_school_manager and user.school_id == student.school_id:
        return user.has_permission("manage_students")
    if user.is_teacher and teacher_can_access_student(user, student):
        return user.has_permission("manage_evaluations") or user.has_permission("manage_students")
    return False


def can_manage_student(user, student):
    """Deactivate/activate and full admin control (managers + platform admin)."""
    if user.is_platform_admin:
        return True
    return (
        user.is_school_manager
        and user.school_id == student.school_id
        and user.has_permission("manage_students")
    )


def deactivate_student(student):
    student.is_active = False
    if student.user:
        student.user.is_active = False
    db.session.commit()


def activate_student(student):
    student.is_active = True
    if student.user:
        student.user.is_active = True
    db.session.commit()


def bulk_manage_students(user, student_ids, action):
    """
    Deactivate or activate multiple students.
    Returns number of students updated.
    """
    if action not in ("deactivate", "activate"):
        raise ValueError("إجراء غير صالح.")

    ids = []
    for raw_id in student_ids or []:
        try:
            ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    if not ids:
        raise ValueError("لم يتم تحديد أي طالب.")

    students = Student.query.filter(Student.id.in_(ids)).all()
    updated = 0
    for student in students:
        if not can_manage_student(user, student):
            continue
        if action == "deactivate" and student.is_active:
            student.is_active = False
            if student.user:
                student.user.is_active = False
            updated += 1
        elif action == "activate" and not student.is_active:
            student.is_active = True
            if student.user:
                student.user.is_active = True
            updated += 1

    if not updated:
        raise ValueError("لا يوجد طلاب مطابقون للإجراء المحدد أو ليس لديك صلاحية.")

    db.session.commit()
    return updated


def can_student_edit_own(user, student):
    return (
        user.student_profile is not None
        and user.student_profile.id == student.id
        and user.has_permission("self_assess")
    )


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def update_student(student, form, *, allow_school_change=False, self_edit=False):
    """Update student record and linked user account."""
    if self_edit:
        student.phone = normalize_optional_phone(form.get("phone"))
        student.region = (form.get("region") or "").strip() or student.region
        student.district = (form.get("district") or "").strip() or student.district
        student.address = (form.get("address") or "").strip() or student.address
        if student.user:
            student.user.phone = student.phone
        db.session.commit()
        return student

    full_name_ar = (form.get("full_name_ar") or "").strip()
    if not full_name_ar:
        raise ValueError("الاسم بالعربية مطلوب.")

    student_number = (form.get("student_id") or "").strip()
    if student_number and student_number != student.student_id:
        existing = Student.query.filter(
            Student.student_id == student_number,
            Student.id != student.id,
        ).first()
        if existing:
            raise ValueError("رقم الطالب مستخدم مسبقاً.")
        student.student_id = student_number

    school_id = student.school_id
    if allow_school_change and form.get("school_id"):
        school_id = int(form["school_id"])
        student.school_id = school_id

    grade_id = int(form["grade_id"]) if form.get("grade_id") else student.grade_id
    class_id = int(form["class_id"]) if form.get("class_id") else student.class_id
    class_ = Class.query.filter_by(id=class_id, school_id=school_id, grade_id=grade_id).first()
    if not class_:
        raise ValueError("الفصل المحدد غير صالح لهذا المستوى والمدرسة.")
    student.grade_id = grade_id
    student.class_id = class_id

    student.full_name_ar = full_name_ar
    student.full_name = (form.get("full_name") or full_name_ar).strip()
    student.gender = form.get("gender") or student.gender
    if "weekly_class_limit" in form:
        student.weekly_class_limit = parse_weekly_limit(form.get("weekly_class_limit"))
    student.date_of_birth = parse_date(form.get("date_of_birth")) or student.date_of_birth
    student.enrollment_date = parse_date(form.get("enrollment_date")) or student.enrollment_date
    student.region = (form.get("region") or "").strip() or student.region
    student.district = (form.get("district") or "").strip() or student.district
    student.address = (form.get("address") or "").strip() or student.address
    student.phone = normalize_optional_phone(form.get("phone"))
    rt_id = form.get("responsible_teacher_id")
    student.responsible_teacher_id = int(rt_id) if rt_id else None

    user = student.user
    if user:
        user.full_name = student.full_name
        user.full_name_ar = student.full_name_ar
        user.phone = student.phone
        if allow_school_change:
            user.school_id = school_id
        username = (form.get("username") or "").strip()
        if username and username != user.username:
            if User.query.filter(User.username == username, User.id != user.id).first():
                raise ValueError("اسم المستخدم موجود.")
            user.username = username
        email = normalize_optional_email(form.get("email"))
        if email and User.query.filter(User.email == email, User.id != user.id).first():
            raise ValueError("البريد الإلكتروني مستخدم.")
        user.email = email
        password = form.get("password")
        if password:
            user.set_password(password)

    db.session.commit()
    return student
