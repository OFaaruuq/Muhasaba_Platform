from datetime import date, datetime

from flask import flash, redirect, render_template, url_for
from flask_login import current_user

from app.extensions import db
from app.models import Student, Grade, Class, School, User, Role, Teacher
from app.kpi.hooks import sync_kpis_for_student
from app.services.registration_field_service import (
    get_registration_config,
    validate_registration_fields,
    extract_registration_values,
)
from app.services.registration_lookup_service import registration_form_meta
from app.utils.contact_fields import normalize_optional_email, normalize_optional_phone


def registration_schools():
    if current_user.is_platform_admin:
        return School.query.filter_by(is_active=True).order_by(School.name_ar).all()
    return School.query.filter_by(id=current_user.school_id, is_active=True).all()


def grades_for_school(school_id):
    if not school_id:
        return []
    return Grade.query.filter_by(school_id=school_id).order_by(Grade.level).all()


def teachers_for_school(school_id):
    if not school_id:
        return []
    return Teacher.query.filter_by(school_id=school_id, is_active=True).order_by(
        Teacher.full_name_ar
    ).all()


def classes_for_grade(grade_id, school_id=None):
    if not grade_id:
        return []
    query = Class.query.filter_by(grade_id=grade_id)
    if school_id:
        query = query.filter_by(school_id=school_id)
    return query.order_by(Class.name).all()


def _default_school_id():
    return current_user.school_id if not current_user.is_platform_admin else None


def _form_int(form, key):
    if not form:
        return None
    val = form.get(key)
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def registration_template_context(form=None, school_id=None):
    """Shared context for GET and validation error re-render."""
    form = form or {}
    schools = registration_schools()
    default_school = _default_school_id()
    sid = school_id or _form_int(form, "school_id") or default_school
    if not sid and schools:
        sid = schools[0].id
    reg_config = get_registration_config(sid)
    meta = registration_form_meta(sid, current_user)
    return {
        "schools": schools,
        "grades": grades_for_school(sid),
        "classes": classes_for_grade(_form_int(form, "grade_id"), sid),
        "teachers": teachers_for_school(sid),
        "form": form,
        "default_school": default_school,
        "reg_config": reg_config,
        **meta,
    }


def generate_student_id(school_id):
    school = School.query.get(school_id)
    prefix = school.code if school else "STD"
    year = date.today().year
    count = Student.query.filter(Student.student_id.like(f"{prefix}-{year}-%")).count() + 1
    return f"{prefix}-{year}-{count:03d}"


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def process_registration(form, register_url):
    """Process POST registration. Returns redirect or re-rendered form."""
    school_id = _form_int(form, "school_id")
    errors = validate_registration_fields(form, school_id)
    if errors:
        for err in errors:
            flash(err, "danger")
        return render_template(
            "evaluations/register.html",
            **registration_template_context(form, school_id),
        )

    school_id = int(form["school_id"])
    grade_id = int(form["grade_id"])
    class_id = int(form["class_id"])

    class_ = Class.query.filter_by(id=class_id, school_id=school_id, grade_id=grade_id).first()
    if not class_:
        flash("الفصل المحدد غير صالح لهذا المستوى والمدرسة.", "danger")
        return redirect(register_url)

    values = extract_registration_values(form, school_id)

    student_number = values["student_id"]
    if not student_number:
        student_number = generate_student_id(school_id)

    if Student.query.filter_by(student_id=student_number).first():
        flash("رقم الطالب مستخدم مسبقاً.", "danger")
        return redirect(register_url)

    student = Student(
        school_id=school_id,
        grade_id=grade_id,
        class_id=class_id,
        student_id=student_number,
        full_name=values["full_name"] or values["full_name_ar"],
        full_name_ar=values["full_name_ar"],
        gender=values["gender"],
        date_of_birth=parse_date(values["date_of_birth"]),
        enrollment_date=parse_date(values["enrollment_date"]) or date.today(),
        region=values["region"],
        district=values["district"],
        address=values["address"],
        phone=normalize_optional_phone(values["phone"]),
        responsible_teacher_id=values["responsible_teacher_id"],
    )
    db.session.add(student)
    db.session.flush()

    if values["create_account"]:
        username = values["username"]
        password = values["password"]
        if username and password:
            role = Role.query.filter_by(name="student").first()
            if User.query.filter_by(username=username).first():
                flash("اسم المستخدم موجود. تم تسجيل الطالب بدون حساب.", "warning")
            else:
                account_email = normalize_optional_email(values["email"])
                if account_email and User.query.filter_by(email=account_email).first():
                    flash("البريد الإلكتروني مستخدم. تم تسجيل الطالب بدون حساب.", "warning")
                else:
                    user = User(
                        username=username,
                        email=account_email,
                        full_name=student.full_name_ar,
                        full_name_ar=student.full_name_ar,
                        role_id=role.id,
                        school_id=school_id,
                    )
                    user.set_password(password)
                    db.session.add(user)
                    db.session.flush()
                    student.user_id = user.id

    db.session.commit()
    sync_kpis_for_student(student.id)
    flash(f"تم تسجيل الطالب {student.full_name_ar} بنجاح.", "success")
    return redirect(url_for("evaluations.index"))
