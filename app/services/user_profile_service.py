"""Link login accounts to Teacher / Student profiles (including dual profiles)."""

from datetime import date

from app.extensions import db
from app.models import Class, Grade, School, Student, Teacher, TeacherClass
from app.services.permission_registry import DEFAULT_ROLE_PERMISSIONS
from app.students.registration import generate_student_id


PROFILE_ROLE_NAMES = frozenset({"teacher", "student", "parent"})


def effective_permissions_for_user(user):
    """Role + linked profile permissions (see effective_user_permissions for extras)."""
    return profile_permissions_for_user(user)


def profile_permissions_for_user(user):
    """Role permissions plus defaults for each active linked profile."""
    names = set()
    if user and getattr(user, "is_authenticated", False) and user.role:
        names = {p.name for p in user.role.permissions}
    if user.teacher_profile and user.teacher_profile.is_active:
        names.update(DEFAULT_ROLE_PERMISSIONS.get("teacher", []))
    if user.student_profile and user.student_profile.is_active:
        names.update(DEFAULT_ROLE_PERMISSIONS.get("student", []))
    if user.parent_profile:
        names.update(DEFAULT_ROLE_PERMISSIONS.get("parent", []))
    return names


def role_suggests_profile(role_name, profile_type):
    return role_name == profile_type


def wants_teacher_profile(form, role_name):
    if form.get("create_teacher_profile") == "on":
        return True
    return role_suggests_profile(role_name, "teacher")


def wants_student_profile(form, role_name):
    if form.get("create_student_profile") == "on":
        return True
    return role_suggests_profile(role_name, "student")


def _require_school_id(school_id):
    if not school_id:
        raise ValueError("المدرسة مطلوبة لإنشاء ملف معلم أو طالب.")


def _generate_employee_id(school_id, username):
    school = School.query.get(school_id)
    prefix = school.code if school else "TCH"
    base = f"{prefix}-{username}"[:20]
    if not Teacher.query.filter_by(employee_id=base).first():
        return base
    n = Teacher.query.filter(Teacher.employee_id.like(f"{base}-%")).count() + 1
    return f"{base}-{n}"[:20]


def _parse_class_ids(form):
    raw = form.getlist("teacher_class_ids") if hasattr(form, "getlist") else []
    if not raw and form.get("teacher_class_ids"):
        raw = [form.get("teacher_class_ids")]
    ids = []
    for val in raw:
        try:
            ids.append(int(val))
        except (TypeError, ValueError):
            continue
    return ids


def create_teacher_profile_for_user(user, *, school_id, form):
    _require_school_id(school_id)
    if user.teacher_profile:
        raise ValueError("المستخدم لديه ملف معلم مسبقاً.")

    employee_id = (form.get("employee_id") or "").strip() or _generate_employee_id(
        school_id, user.username
    )
    if Teacher.query.filter_by(employee_id=employee_id).first():
        raise ValueError("الرقم الوظيفي مستخدم.")

    teacher = Teacher(
        user_id=user.id,
        school_id=school_id,
        employee_id=employee_id,
        full_name=user.full_name,
        full_name_ar=user.full_name_ar,
        specialization=(form.get("specialization") or "").strip() or None,
        phone=user.phone,
        hire_date=date.today(),
        is_active=True,
    )
    db.session.add(teacher)
    db.session.flush()

    class_ids = _parse_class_ids(form)
    for class_id in class_ids:
        class_ = Class.query.filter_by(id=class_id, school_id=school_id).first()
        if not class_:
            continue
        exists = TeacherClass.query.filter_by(
            teacher_id=teacher.id, class_id=class_id
        ).first()
        if not exists:
            db.session.add(TeacherClass(teacher_id=teacher.id, class_id=class_id))
    return teacher


def create_student_profile_for_user(user, *, school_id, form):
    _require_school_id(school_id)
    if user.student_profile:
        raise ValueError("المستخدم لديه ملف طالب مسبقاً.")

    grade_id = form.get("grade_id", type=int) if hasattr(form, "get") else None
    class_id = form.get("class_id", type=int) if hasattr(form, "get") else None
    if not grade_id or not class_id:
        raise ValueError("الصف والفصل مطلوبان لملف الطالب.")

    class_ = Class.query.filter_by(id=class_id, school_id=school_id, grade_id=grade_id).first()
    if not class_:
        raise ValueError("الفصل المحدد غير صالح لهذه المدرسة.")

    student_number = (form.get("student_id") or "").strip()
    if not student_number:
        student_number = generate_student_id(school_id)
    if Student.query.filter_by(student_id=student_number).first():
        raise ValueError("رقم الطالب مستخدم.")

    school = School.query.get(school_id)
    default_place = school.name_ar if school else "غير محدد"

    student = Student(
        user_id=user.id,
        school_id=school_id,
        grade_id=grade_id,
        class_id=class_id,
        student_id=student_number,
        full_name=user.full_name,
        full_name_ar=user.full_name_ar,
        region=(form.get("region") or "").strip() or default_place,
        district=(form.get("district") or "").strip() or default_place,
        address=(form.get("address") or "").strip() or default_place,
        phone=user.phone,
        enrollment_date=date.today(),
        responsible_teacher_id=form.get("responsible_teacher_id", type=int),
        is_active=True,
    )
    db.session.add(student)
    db.session.flush()
    return student


def update_teacher_profile(user, form):
    teacher = user.teacher_profile
    if not teacher:
        return None

    employee_id = (form.get("employee_id") or "").strip()
    if employee_id and employee_id != teacher.employee_id:
        if Teacher.query.filter_by(employee_id=employee_id).first():
            raise ValueError("الرقم الوظيفي مستخدم.")
        teacher.employee_id = employee_id

    spec = (form.get("specialization") or "").strip()
    if spec:
        teacher.specialization = spec

    class_ids = _parse_class_ids(form)
    if class_ids:
        TeacherClass.query.filter_by(teacher_id=teacher.id).delete()
        for class_id in class_ids:
            class_ = Class.query.filter_by(id=class_id, school_id=teacher.school_id).first()
            if class_:
                db.session.add(TeacherClass(teacher_id=teacher.id, class_id=class_id))
    return teacher


def update_student_profile(user, form):
    student = user.student_profile
    if not student:
        return None

    grade_id = form.get("grade_id", type=int)
    class_id = form.get("class_id", type=int)
    if grade_id and class_id:
        class_ = Class.query.filter_by(
            id=class_id, school_id=student.school_id, grade_id=grade_id
        ).first()
        if not class_:
            raise ValueError("الفصل المحدد غير صالح.")
        student.grade_id = grade_id
        student.class_id = class_id
    return student


def provision_user_profiles(user, form, role_name, school_id):
    """Create teacher and/or student profiles from super-admin form."""
    created = []
    if wants_teacher_profile(form, role_name):
        create_teacher_profile_for_user(user, school_id=school_id, form=form)
        created.append("teacher")
    if wants_student_profile(form, role_name):
        create_student_profile_for_user(user, school_id=school_id, form=form)
        created.append("student")
    return created


def sync_user_profiles(user, form, role_name):
    """Create missing profiles or update existing ones on edit."""
    school_id = form.get("school_id", type=int) or user.school_id
    changes = []

    if wants_teacher_profile(form, role_name):
        if user.teacher_profile:
            update_teacher_profile(user, form)
            changes.append("teacher_updated")
        elif school_id:
            create_teacher_profile_for_user(user, school_id=school_id, form=form)
            changes.append("teacher_created")

    if wants_student_profile(form, role_name):
        if user.student_profile:
            update_student_profile(user, form)
            changes.append("student_updated")
        elif school_id:
            create_student_profile_for_user(user, school_id=school_id, form=form)
            changes.append("student_created")

    return changes


def school_structure_payload(school_id):
    """Grades, classes, and subjects for dynamic super-admin forms."""
    grades = Grade.query.filter_by(school_id=school_id).order_by(Grade.level).all()
    classes = Class.query.filter_by(school_id=school_id).order_by(Class.name).all()
    from app.services.subject_service import list_subjects

    subjects = list_subjects(school_id)
    teachers = Teacher.query.filter_by(school_id=school_id, is_active=True).order_by(
        Teacher.full_name_ar
    ).all()
    return {
        "grades": [{"id": g.id, "name_ar": g.name_ar, "level": g.level} for g in grades],
        "classes": [
            {
                "id": c.id,
                "name": c.name,
                "section": c.section or "",
                "grade_id": c.grade_id,
            }
            for c in classes
        ],
        "subjects": [{"id": s.id, "name_ar": s.name_ar} for s in subjects],
        "teachers": [
            {
                "id": t.id,
                "full_name_ar": t.full_name_ar or t.full_name,
                "employee_id": t.employee_id,
            }
            for t in teachers
        ],
    }


def user_profile_summary(user):
    """Short labels for admin user list."""
    parts = []
    if user.teacher_profile:
        t = user.teacher_profile
        n = len(t.class_assignments.all())
        parts.append(f"معلم ({n} فصل)")
    if user.student_profile:
        s = user.student_profile
        class_ = Class.query.get(s.class_id)
        grade_label = s.grade.name_ar if s.grade else ""
        class_label = class_.name if class_ else ""
        cls = f"{grade_label} / {class_label}".strip(" /")
        parts.append(f"طالب ({cls})" if cls else "طالب")
    return parts
