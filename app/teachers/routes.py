from datetime import date

from flask import flash, redirect, render_template, request, url_for
from app.services.message_service import flash_msg
from flask_login import login_required, current_user

from sqlalchemy import or_

from app.teachers import bp
from app.extensions import db
from app.models import Teacher, TeacherClass, Class, Subject, School
from app.utils import permission_required
from app.services.teacher_service import (
    teacher_in_scope,
    update_teacher,
    deactivate_teacher,
    activate_teacher,
    remove_assignment,
    teacher_usage_counts,
    teacher_index_summaries,
)
from app.services.subject_service import (
    resolve_subject_from_form,
    teacher_selected_subject_id,
    list_subjects,
)
from app.utils.contact_fields import normalize_optional_email, normalize_optional_phone


def _get_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    if not teacher_in_scope(current_user, teacher):
        flash_msg("permission_denied", "danger")
        return None
    return teacher


@bp.route("/")
@login_required
@permission_required("manage_teachers")
def index():
    show_inactive = request.args.get("show_inactive") == "1"
    search_q = (request.args.get("q") or "").strip()

    query = Teacher.query
    if not show_inactive:
        query = query.filter_by(is_active=True)
    if not current_user.is_platform_admin:
        query = query.filter_by(school_id=current_user.school_id)
    if search_q:
        like = f"%{search_q}%"
        query = query.filter(
            or_(
                Teacher.full_name_ar.ilike(like),
                Teacher.full_name.ilike(like),
                Teacher.employee_id.ilike(like),
                Teacher.specialization.ilike(like),
            )
        )
    teachers = query.order_by(Teacher.full_name_ar).all()
    return render_template(
        "teachers/index.html",
        teachers=teachers,
        teacher_summaries=teacher_index_summaries(teachers),
        show_inactive=show_inactive,
        search_q=search_q,
    )


@bp.route("/create", methods=["GET", "POST"])
@login_required
@permission_required("manage_teachers")
def create():
    school_id = current_user.school_id
    schools = School.query.filter_by(is_active=True).all() if current_user.is_platform_admin else []

    if request.method == "POST":
        sid = int(request.form["school_id"]) if current_user.is_platform_admin else school_id
        employee_id = request.form["employee_id"].strip()

        if Teacher.query.filter_by(employee_id=employee_id).first():
            flash_msg("teacher_employee_id_taken", "danger", sid)
            return redirect(url_for("teachers.create"))

        teacher = Teacher(
            school_id=sid,
            employee_id=employee_id,
            full_name=request.form.get("full_name", request.form["full_name_ar"]),
            full_name_ar=request.form["full_name_ar"],
            specialization=resolve_subject_from_form(sid, request.form),
            phone=normalize_optional_phone(request.form.get("phone")),
            hire_date=date.today(),
        )
        db.session.add(teacher)
        db.session.commit()
        flash_msg("teacher_registered", "success", sid)
        return redirect(url_for("teachers.detail", teacher_id=teacher.id))

    subjects = list_subjects(school_id) if school_id else []
    return render_template(
        "teachers/create.html",
        schools=schools,
        school_id=school_id,
        subjects=subjects,
    )


@bp.route("/<int:teacher_id>")
@login_required
@permission_required("manage_teachers")
def detail(teacher_id):
    teacher = _get_teacher(teacher_id)
    if not teacher:
        return redirect(url_for("teachers.index"))

    classes = Class.query.filter_by(school_id=teacher.school_id).all()
    subjects = Subject.query.filter_by(school_id=teacher.school_id).all()
    assignments = teacher.class_assignments.all()
    usage = teacher_usage_counts(teacher.id)

    return render_template(
        "teachers/detail.html",
        teacher=teacher,
        classes=classes,
        subjects=subjects,
        assignments=assignments,
        usage=usage,
    )


@bp.route("/<int:teacher_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_teachers")
def edit(teacher_id):
    teacher = _get_teacher(teacher_id)
    if not teacher:
        return redirect(url_for("teachers.index"))

    schools = School.query.filter_by(is_active=True).all() if current_user.is_platform_admin else []

    if request.method == "POST":
        try:
            update_teacher(
                teacher,
                request.form,
                allow_school_change=current_user.is_platform_admin,
            )
            flash_msg("teacher_updated", "success", teacher.school_id)
            return redirect(url_for("teachers.detail", teacher_id=teacher.id))
        except ValueError as exc:
            flash(str(exc), "danger")

    return render_template(
        "teachers/edit.html",
        teacher=teacher,
        schools=schools,
        subjects=list_subjects(teacher.school_id),
        selected_subject_id=teacher_selected_subject_id(teacher),
        school_id=teacher.school_id,
    )


@bp.route("/<int:teacher_id>/deactivate", methods=["POST"])
@login_required
@permission_required("manage_teachers")
def deactivate(teacher_id):
    teacher = _get_teacher(teacher_id)
    if not teacher:
        return redirect(url_for("teachers.index"))
    if not teacher.is_active:
        flash_msg("teacher_already_inactive", "info")
        return redirect(url_for("teachers.detail", teacher_id=teacher.id))

    deactivate_teacher(teacher)
    flash_msg("teacher_deactivated", "success", teacher.school_id)
    return redirect(url_for("teachers.index"))


@bp.route("/<int:teacher_id>/activate", methods=["POST"])
@login_required
@permission_required("manage_teachers")
def activate(teacher_id):
    teacher = _get_teacher(teacher_id)
    if not teacher:
        return redirect(url_for("teachers.index"))

    activate_teacher(teacher)
    flash_msg("teacher_activated", "success", teacher.school_id)
    return redirect(url_for("teachers.detail", teacher_id=teacher.id))


@bp.route("/<int:teacher_id>/assign", methods=["POST"])
@login_required
@permission_required("manage_teachers")
def assign_class(teacher_id):
    teacher = _get_teacher(teacher_id)
    if not teacher:
        return redirect(url_for("teachers.index"))

    class_id = int(request.form["class_id"])
    subject_id = request.form.get("subject_id", type=int)
    existing = TeacherClass.query.filter_by(
        teacher_id=teacher.id,
        class_id=class_id,
        subject_id=subject_id,
    ).first()
    if existing:
        flash_msg("teacher_assignment_exists", "warning", teacher.school_id)
        return redirect(url_for("teachers.detail", teacher_id=teacher.id))

    db.session.add(TeacherClass(
        teacher_id=teacher.id,
        class_id=class_id,
        subject_id=subject_id,
    ))
    db.session.commit()
    flash_msg("teacher_class_assigned", "success", teacher.school_id)
    return redirect(url_for("teachers.detail", teacher_id=teacher.id))


@bp.route("/<int:teacher_id>/assignment/<int:assignment_id>/delete", methods=["POST"])
@login_required
@permission_required("manage_teachers")
def delete_assignment(teacher_id, assignment_id):
    teacher = _get_teacher(teacher_id)
    if not teacher:
        return redirect(url_for("teachers.index"))
    try:
        remove_assignment(teacher, assignment_id)
        flash_msg("teacher_assignment_removed", "success", teacher.school_id)
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("teachers.detail", teacher_id=teacher.id))
