"""School / grade / class / teacher lookups and quick-create for student registration."""

from datetime import date

from app.extensions import db
from app.models import School, Grade, Class, Teacher
from app.services.config_service import (
    ensure_school_defaults,
    get_setting,
    provision_school_kpis,
    get_registration_section_labels,
)
from app.services.registration_field_service import get_registration_config


ACADEMIC_LOOKUP_DEFAULTS = {
    "school_id": {
        "label": "المدرسة",
        "select_empty": "— اختر المدرسة —",
        "create_title": "إضافة مدرسة جديدة",
        "create_button": "إضافة مدرسة",
        "hint": "",
    },
    "grade_id": {
        "label": "المستوى الدراسي",
        "select_empty": "— اختر المستوى —",
        "create_title": "إضافة مستوى دراسي",
        "create_button": "إضافة مستوى",
        "hint": "",
    },
    "class_id": {
        "label": "المجموعة / الفصل",
        "select_empty": "— اختر المجموعة —",
        "create_title": "إضافة مجموعة / فصل",
        "create_button": "إضافة فصل",
        "hint": "اختر المستوى أولاً لعرض المجموعات المتاحة.",
    },
}


def get_academic_lookup_labels(school_id=None):
    """Editable labels for school / grade / class on registration form."""
    import json

    raw = get_setting("registration_academic_labels_json", school_id)
    if isinstance(raw, str):
        try:
            stored = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            stored = {}
    elif isinstance(raw, dict):
        stored = raw
    else:
        stored = {}

    labels = {}
    for key, defaults in ACADEMIC_LOOKUP_DEFAULTS.items():
        labels[key] = {**defaults, **(stored.get(key) or {})}
    return labels


def registration_school_allowed(user, school_id):
    if not school_id:
        return False
    if user.is_platform_admin:
        return True
    return user.school_id == school_id


def list_grades(school_id):
    return Grade.query.filter_by(school_id=school_id).order_by(Grade.level).all()


def list_classes(school_id, grade_id):
    return (
        Class.query.filter_by(school_id=school_id, grade_id=grade_id)
        .order_by(Class.name)
        .all()
    )


def list_teachers(school_id):
    return Teacher.query.filter_by(school_id=school_id, is_active=True).order_by(
        Teacher.full_name_ar
    ).all()


def _generate_employee_id(school_id):
    school = db.session.get(School, school_id)
    prefix = school.code if school else "TCH"
    count = (
        Teacher.query.filter(Teacher.employee_id.like(f"{prefix}-EMP-%")).count() + 1
    )
    return f"{prefix}-EMP-{count:04d}"


def create_grade(school_id, *, name_ar, level, name=None):
    level = int(level)
    if level < 1:
        raise ValueError("رقم المستوى غير صالح.")
    if not str(name_ar or "").strip():
        raise ValueError("اسم المستوى بالعربية مطلوب.")

    existing = Grade.query.filter_by(school_id=school_id, level=level).first()
    if existing:
        raise ValueError(f"المستوى {level} موجود مسبقاً: {existing.name_ar}")

    grade = Grade(
        school_id=school_id,
        name=name or name_ar,
        name_ar=name_ar.strip(),
        level=level,
    )
    db.session.add(grade)
    db.session.commit()
    return grade


def create_class(school_id, grade_id, *, name, section=None, capacity=None):
    if not str(name or "").strip():
        raise ValueError("اسم الفصل مطلوب.")

    grade = Grade.query.filter_by(id=grade_id, school_id=school_id).first()
    if not grade:
        raise ValueError("المستوى الدراسي غير صالح لهذه المدرسة.")

    if capacity is None:
        capacity = int(get_setting("default_class_capacity", school_id, 30))

    class_ = Class(
        school_id=school_id,
        grade_id=grade_id,
        name=name.strip(),
        section=(section or "").strip() or None,
        capacity=int(capacity),
    )
    db.session.add(class_)
    db.session.commit()
    return class_


def create_teacher(school_id, *, full_name_ar, full_name=None, employee_id=None):
    if not str(full_name_ar or "").strip():
        raise ValueError("اسم المسؤول مطلوب.")

    employee_id = (employee_id or "").strip() or _generate_employee_id(school_id)
    if Teacher.query.filter_by(employee_id=employee_id).first():
        raise ValueError("الرقم الوظيفي مستخدم مسبقاً.")

    teacher = Teacher(
        school_id=school_id,
        employee_id=employee_id,
        full_name=full_name or full_name_ar,
        full_name_ar=full_name_ar.strip(),
        hire_date=date.today(),
        is_active=True,
    )
    db.session.add(teacher)
    db.session.flush()
    from app.services.identity_service import ensure_identity_for_teacher
    ensure_identity_for_teacher(teacher)
    db.session.commit()
    return teacher


def create_school(*, name_ar, code, name=None, region=None, district=None, address=None):
    if not str(name_ar or "").strip():
        raise ValueError("اسم المدرسة بالعربية مطلوب.")
    code = (code or "").strip().upper()
    if not code:
        raise ValueError("رمز المدرسة مطلوب.")
    if School.query.filter_by(code=code).first():
        raise ValueError("رمز المدرسة مستخدم مسبقاً.")

    school = School(
        name=name or name_ar,
        name_ar=name_ar.strip(),
        code=code,
        region=(region or "").strip() or None,
        district=(district or "").strip() or None,
        address=(address or "").strip() or None,
        is_active=True,
    )
    db.session.add(school)
    db.session.flush()
    ensure_school_defaults(school.id)
    provision_school_kpis(school.id)
    db.session.commit()
    return school


def registration_form_meta(school_id=None, user=None):
    """Extra template context for registration academic panel."""
    config = get_registration_config(school_id)
    teacher_field = config["fields_map"].get("responsible_teacher_id", {})
    can_create_school = bool(user and user.is_platform_admin)
    can_manage_structure = bool(
        user
        and (
            user.has_permission("register_students")
            or user.has_permission("manage_school")
            or user.is_platform_admin
        )
    )
    can_create_teacher = bool(
        user
        and (
            user.has_permission("register_students")
            or user.has_permission("manage_teachers")
            or user.has_permission("manage_school")
            or user.is_platform_admin
        )
    )
    return {
        "academic_labels": get_academic_lookup_labels(school_id),
        "section_labels": get_registration_section_labels(school_id),
        "teacher_field": teacher_field,
        "can_create_school": can_create_school,
        "can_create_grade_class": can_manage_structure,
        "can_create_teacher": can_create_teacher and teacher_field.get("visible", True),
    }
