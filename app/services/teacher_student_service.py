"""Teacher ↔ student group scoping (dynamic class assignments + responsible teacher).

A user may have a teacher profile, a student profile, both, or neither.
Teachers only see students in their assigned groups (TeacherClass) or where
they are the responsible teacher (Mas'uul).
"""

from sqlalchemy import or_

from app.models import Student, Class


def teacher_assigned_class_ids(teacher):
    """Class IDs from dynamic TeacherClass assignments."""
    if not teacher:
        return []
    return [tc.class_id for tc in teacher.class_assignments]


def teacher_can_access_student(user, student):
    """True if this user (as teacher) may access the student record."""
    if not user or not student:
        return False
    if not user.teacher_profile:
        return False
    if user.school_id and student.school_id != user.school_id:
        return False
    teacher = user.teacher_profile
    if student.responsible_teacher_id == teacher.id:
        return True
    class_ids = teacher_assigned_class_ids(teacher)
    return bool(class_ids and student.class_id in class_ids)


def students_for_teacher(teacher, *, grade_id=None, class_id=None, search=None, active_only=True):
    """Students visible to this teacher: assigned groups + explicit responsible students."""
    if not teacher:
        return []

    class_ids = teacher_assigned_class_ids(teacher)
    filters = [Student.responsible_teacher_id == teacher.id]
    if class_ids:
        filters.append(Student.class_id.in_(class_ids))

    query = Student.query.filter(
        Student.school_id == teacher.school_id,
        or_(*filters),
    )
    if active_only:
        query = query.filter(Student.is_active == True)  # noqa: E712
    if grade_id:
        query = query.filter_by(grade_id=grade_id)
    if class_id:
        query = query.filter_by(class_id=class_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Student.full_name_ar.ilike(term),
                Student.full_name.ilike(term),
                Student.platform_uid.ilike(term),
                Student.student_id.ilike(term),
            )
        )
    return query.order_by(Student.grade_id, Student.class_id, Student.full_name_ar).all()


def student_ids_for_teacher(teacher, **kwargs):
    return [s.id for s in students_for_teacher(teacher, **kwargs)]


def classes_for_teacher(teacher, *, school_id=None):
    """Classes/groups this teacher is assigned to (for filters and attendance)."""
    if not teacher:
        return []
    class_ids = teacher_assigned_class_ids(teacher)
    if not class_ids:
        return []
    query = Class.query.filter(Class.id.in_(class_ids))
    if school_id:
        query = query.filter_by(school_id=school_id)
    return query.order_by(Class.name).all()


def user_has_teacher_profile(user):
    return bool(user and user.teacher_profile)


def user_has_student_profile(user):
    return bool(user and user.student_profile)
