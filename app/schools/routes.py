from datetime import datetime

from flask import flash, redirect, render_template, request, url_for
from app.services.message_service import flash_msg
from flask_login import login_required, current_user

from app.schools import bp
from app.extensions import db
from app.models import School, Grade, Class, Subject, AcademicYear
from app.services.config_service import ensure_school_defaults, provision_school_kpis, get_setting
from app.services.school_service import (
    can_delete_school, delete_school_permanently, school_delete_blockers,
    can_delete_subject,
)
from app.utils import permission_required


def _school_access(school_id):
    school = School.query.get_or_404(school_id)
    if not current_user.is_platform_admin and school.id != current_user.school_id:
        flash_msg("permission_denied", "danger")
        return None
    return school


@bp.route("/")
@login_required
@permission_required("view_all_schools", "manage_school")
def index():
    show_inactive = request.args.get("show_inactive") == "1"
    if current_user.is_platform_admin:
        query = School.query
        if not show_inactive:
            query = query.filter_by(is_active=True)
        schools = query.order_by(School.name_ar).all()
    else:
        schools = School.query.filter_by(
            id=current_user.school_id, is_active=True
        ).all()
    return render_template(
        "schools/index.html",
        schools=schools,
        show_inactive=show_inactive,
        can_delete_school=can_delete_school,
    )


@bp.route("/<int:school_id>")
@login_required
@permission_required("view_all_schools", "manage_school")
def detail(school_id):
    school = _school_access(school_id)
    if not school:
        return redirect(url_for("schools.index"))

    grades = Grade.query.filter_by(school_id=school.id).order_by(Grade.level).all()
    classes = Class.query.filter_by(school_id=school.id).all()
    subjects = Subject.query.filter_by(school_id=school.id).all()
    years = AcademicYear.query.filter_by(school_id=school.id).all()

    return render_template(
        "schools/detail.html",
        school=school,
        grades=grades,
        classes=classes,
        subjects=subjects,
        years=years,
        default_class_capacity=get_setting("default_class_capacity", school.id, 30),
        delete_blockers=school_delete_blockers(school.id),
    )


@bp.route("/create", methods=["GET", "POST"])
@login_required
@permission_required("view_all_schools")
def create():
    if request.method == "POST":
        school = School(
            name=request.form["name"],
            name_ar=request.form["name_ar"],
            code=request.form["code"],
            district=request.form.get("district"),
            region=request.form.get("region"),
            address=request.form.get("address"),
            phone=request.form.get("phone"),
            email=request.form.get("email"),
            principal_name=request.form.get("principal_name"),
        )
        db.session.add(school)
        db.session.flush()
        ensure_school_defaults(school.id)
        provision_school_kpis(school.id)
        db.session.commit()
        flash_msg("school_registered", "success")
        return redirect(url_for("schools.detail", school_id=school.id))

    return render_template("schools/create.html")


@bp.route("/<int:school_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("view_all_schools", "manage_school")
def edit_school(school_id):
    school = _school_access(school_id)
    if not school:
        return redirect(url_for("schools.index"))

    if request.method == "POST":
        school.name = request.form["name"]
        school.name_ar = request.form["name_ar"]
        school.region = request.form.get("region")
        school.district = request.form.get("district")
        school.address = request.form.get("address")
        school.phone = request.form.get("phone")
        school.email = request.form.get("email")
        school.principal_name = request.form.get("principal_name")
        if current_user.is_platform_admin and request.form.get("code"):
            existing = School.query.filter(
                School.code == request.form["code"], School.id != school.id
            ).first()
            if existing:
                flash_msg("school_code_taken", "danger")
                return redirect(url_for("schools.edit_school", school_id=school.id))
            school.code = request.form["code"]
        db.session.commit()
        flash_msg("school_updated", "success", school.id)
        next_url = request.form.get("next") or url_for("schools.detail", school_id=school.id)
        return redirect(next_url)

    return render_template("schools/edit.html", school=school)


@bp.route("/<int:school_id>/toggle", methods=["POST"])
@login_required
@permission_required("view_all_schools")
def toggle_school(school_id):
    school = School.query.get_or_404(school_id)
    school.is_active = not school.is_active
    db.session.commit()
    state = "تفعيل" if school.is_active else "تعطيل"
    flash_msg("school_state_changed", "success", school.id, state=state)
    return redirect(url_for("schools.index", show_inactive="1" if not school.is_active else None))


@bp.route("/<int:school_id>/delete", methods=["POST"])
@login_required
@permission_required("view_all_schools")
def delete_school(school_id):
    school = School.query.get_or_404(school_id)
    confirm_code = (request.form.get("confirm_code") or "").strip()
    if confirm_code != school.code:
        flash_msg("school_delete_code_wrong", "danger")
        return redirect(url_for("schools.detail", school_id=school.id))

    name_ar = school.name_ar
    try:
        delete_school_permanently(school)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("schools.detail", school_id=school_id))

    flash_msg("school_deleted", "success", name=name_ar)
    return redirect(url_for("schools.index", show_inactive="1"))


@bp.route("/<int:school_id>/grade", methods=["POST"])
@login_required
@permission_required("view_all_schools", "manage_school")
def add_grade(school_id):
    school = _school_access(school_id)
    if not school:
        return redirect(url_for("schools.index"))
    try:
        from app.services.registration_lookup_service import create_grade
        create_grade(
            school.id,
            name_ar=request.form["name_ar"],
            level=request.form["level"],
            name=request.form.get("name") or request.form["name_ar"],
        )
        flash_msg("grade_added", "success", school_id)
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("schools.detail", school_id=school.id))


@bp.route("/<int:school_id>/class", methods=["POST"])
@login_required
@permission_required("view_all_schools", "manage_school")
def add_class(school_id):
    school = _school_access(school_id)
    if not school:
        return redirect(url_for("schools.index"))
    try:
        from app.services.registration_lookup_service import create_class
        create_class(
            school.id,
            int(request.form["grade_id"]),
            name=request.form["name"],
            section=request.form.get("section"),
            capacity=request.form.get("capacity", get_setting("default_class_capacity", school.id, 30)),
        )
        flash_msg("class_added", "success", school_id)
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("schools.detail", school_id=school.id))


@bp.route("/<int:school_id>/subject", methods=["POST"])
@login_required
@permission_required("view_all_schools", "manage_school")
def add_subject(school_id):
    school = _school_access(school_id)
    if not school:
        return redirect(url_for("schools.index"))
    db.session.add(Subject(
        school_id=school.id,
        name=request.form["name"],
        name_ar=request.form["name_ar"],
        code=request.form.get("code"),
    ))
    db.session.commit()
    flash_msg("subject_added", "success", school_id)
    return redirect(url_for("schools.detail", school_id=school.id))


@bp.route("/<int:school_id>/year", methods=["POST"])
@login_required
@permission_required("view_all_schools", "manage_school")
def add_year(school_id):
    school = _school_access(school_id)
    if not school:
        return redirect(url_for("schools.index"))
    is_current = request.form.get("is_current") == "on"
    if is_current:
        AcademicYear.query.filter_by(school_id=school.id).update({"is_current": False})
    db.session.add(AcademicYear(
        school_id=school.id,
        name=request.form["name"],
        start_date=datetime.strptime(request.form["start_date"], "%Y-%m-%d").date(),
        end_date=datetime.strptime(request.form["end_date"], "%Y-%m-%d").date(),
        is_current=is_current,
    ))
    db.session.commit()
    flash_msg("year_added", "success", school_id)
    return redirect(url_for("schools.detail", school_id=school.id))


@bp.route("/<int:school_id>/grade/<int:grade_id>/edit", methods=["POST"])
@login_required
@permission_required("view_all_schools", "manage_school")
def edit_grade(school_id, grade_id):
    school = _school_access(school_id)
    if not school:
        return redirect(url_for("schools.index"))
    grade = Grade.query.filter_by(id=grade_id, school_id=school.id).first_or_404()
    grade.name = request.form["name"]
    grade.name_ar = request.form["name_ar"]
    grade.level = int(request.form["level"])
    db.session.commit()
    flash_msg("grade_updated", "success", school_id)
    return redirect(url_for("schools.detail", school_id=school.id))


@bp.route("/<int:school_id>/grade/<int:grade_id>/delete", methods=["POST"])
@login_required
@permission_required("view_all_schools", "manage_school")
def delete_grade(school_id, grade_id):
    school = _school_access(school_id)
    if not school:
        return redirect(url_for("schools.index"))
    grade = Grade.query.filter_by(id=grade_id, school_id=school.id).first_or_404()
    if grade.classes.count():
        flash_msg("grade_delete_blocked", "danger")
        return redirect(url_for("schools.detail", school_id=school.id))
    db.session.delete(grade)
    db.session.commit()
    flash_msg("grade_deleted", "success", school_id)
    return redirect(url_for("schools.detail", school_id=school.id))


@bp.route("/<int:school_id>/class/<int:class_id>/edit", methods=["POST"])
@login_required
@permission_required("view_all_schools", "manage_school")
def edit_class(school_id, class_id):
    school = _school_access(school_id)
    if not school:
        return redirect(url_for("schools.index"))
    class_ = Class.query.filter_by(id=class_id, school_id=school.id).first_or_404()
    class_.grade_id = int(request.form["grade_id"])
    class_.name = request.form["name"]
    class_.section = request.form.get("section")
    class_.capacity = int(request.form.get("capacity", class_.capacity))
    class_.academic_year_id = request.form.get("academic_year_id", type=int) or None
    db.session.commit()
    flash_msg("class_updated", "success", school_id)
    return redirect(url_for("schools.detail", school_id=school.id))


@bp.route("/<int:school_id>/class/<int:class_id>/delete", methods=["POST"])
@login_required
@permission_required("view_all_schools", "manage_school")
def delete_class(school_id, class_id):
    school = _school_access(school_id)
    if not school:
        return redirect(url_for("schools.index"))
    class_ = Class.query.filter_by(id=class_id, school_id=school.id).first_or_404()
    if class_.students.filter_by(is_active=True).count():
        flash_msg("class_delete_blocked", "danger")
        return redirect(url_for("schools.detail", school_id=school.id))
    db.session.delete(class_)
    db.session.commit()
    flash_msg("class_deleted", "success", school_id)
    return redirect(url_for("schools.detail", school_id=school.id))


@bp.route("/<int:school_id>/subject/<int:subject_id>/edit", methods=["POST"])
@login_required
@permission_required("view_all_schools", "manage_school")
def edit_subject(school_id, subject_id):
    school = _school_access(school_id)
    if not school:
        return redirect(url_for("schools.index"))
    subject = Subject.query.filter_by(id=subject_id, school_id=school.id).first_or_404()
    subject.name = request.form["name"]
    subject.name_ar = request.form["name_ar"]
    subject.code = request.form.get("code")
    db.session.commit()
    flash_msg("subject_updated", "success", school_id)
    return redirect(url_for("schools.detail", school_id=school.id))


@bp.route("/<int:school_id>/subject/<int:subject_id>/delete", methods=["POST"])
@login_required
@permission_required("view_all_schools", "manage_school")
def delete_subject(school_id, subject_id):
    school = _school_access(school_id)
    if not school:
        return redirect(url_for("schools.index"))
    subject = Subject.query.filter_by(id=subject_id, school_id=school.id).first_or_404()
    ok, blockers = can_delete_subject(subject.id)
    if not ok:
        flash_msg("subject_delete_blocked", "danger", reason="؛ ".join(blockers))
        return redirect(url_for("schools.detail", school_id=school.id))
    from app.models import TeacherClass
    TeacherClass.query.filter_by(subject_id=subject.id).update(
        {TeacherClass.subject_id: None}, synchronize_session=False
    )
    db.session.delete(subject)
    db.session.commit()
    flash_msg("subject_deleted", "success", school_id)
    return redirect(url_for("schools.detail", school_id=school.id))


@bp.route("/<int:school_id>/year/<int:year_id>/edit", methods=["POST"])
@login_required
@permission_required("view_all_schools", "manage_school")
def edit_year(school_id, year_id):
    school = _school_access(school_id)
    if not school:
        return redirect(url_for("schools.index"))
    year = AcademicYear.query.filter_by(id=year_id, school_id=school.id).first_or_404()
    year.name = request.form["name"]
    year.start_date = datetime.strptime(request.form["start_date"], "%Y-%m-%d").date()
    year.end_date = datetime.strptime(request.form["end_date"], "%Y-%m-%d").date()
    is_current = request.form.get("is_current") == "on"
    if is_current:
        AcademicYear.query.filter_by(school_id=school.id).update({"is_current": False})
    year.is_current = is_current
    db.session.commit()
    flash_msg("year_updated", "success", school_id)
    return redirect(url_for("schools.detail", school_id=school.id))


@bp.route("/<int:school_id>/year/<int:year_id>/delete", methods=["POST"])
@login_required
@permission_required("view_all_schools", "manage_school")
def delete_year(school_id, year_id):
    school = _school_access(school_id)
    if not school:
        return redirect(url_for("schools.index"))
    year = AcademicYear.query.filter_by(id=year_id, school_id=school.id).first_or_404()
    if Class.query.filter_by(academic_year_id=year.id).count():
        flash_msg("year_delete_blocked", "danger")
        return redirect(url_for("schools.detail", school_id=school.id))
    db.session.delete(year)
    db.session.commit()
    flash_msg("year_deleted", "success", school_id)
    return redirect(url_for("schools.detail", school_id=school.id))
