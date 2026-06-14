from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.students import bp
from app.extensions import db
from app.models import Student, Attendance, Evaluation, Grade, Class, School, Parent, User, Role, Teacher
from app.kpi.service import get_student_kpi_display
from app.utils import permission_required
from app.services.student_service import (
    can_edit_student, can_manage_student, can_student_edit_own, update_student,
    deactivate_student, activate_student,
    bulk_manage_students,
)
from app.services.audit_service import log_action
from app.services.config_service import (
    get_attendance_status_map, get_config_choices, get_config_map,
    get_criterion_category_labels, get_unspecified_label, get_daily_category_field_map,
)
from app.services.teacher_student_service import students_for_teacher, teacher_can_access_student
from app.services.teacher_tracking_service import tracking_by_student_id
from app.services.registration_lookup_service import registration_form_meta


@bp.route("/")
@login_required
@permission_required("view_students", "manage_students")
def index():
    show_inactive = request.args.get("show_inactive") == "1"
    search_q = (request.args.get("q") or "").strip()
    school_id = request.args.get("school_id", type=int)
    grade_id = request.args.get("grade_id", type=int)
    class_id = request.args.get("class_id", type=int)

    query = Student.query
    if not show_inactive:
        query = query.filter_by(is_active=True)

    if not current_user.is_platform_admin:
        query = query.filter_by(school_id=current_user.school_id)
    elif school_id:
        query = query.filter_by(school_id=school_id)

    teacher_tracking = None
    if current_user.is_teacher and current_user.teacher_profile:
        teacher = current_user.teacher_profile
        assigned = students_for_teacher(teacher)
        assigned_ids = [s.id for s in assigned]
        query = query.filter(Student.id.in_(assigned_ids)) if assigned_ids else query.filter(False)
        teacher_tracking = tracking_by_student_id(teacher)

    if grade_id:
        query = query.filter_by(grade_id=grade_id)
    if class_id:
        query = query.filter_by(class_id=class_id)
    if search_q:
        like = f"%{search_q}%"
        query = query.filter(
            or_(
                Student.full_name_ar.ilike(like),
                Student.full_name.ilike(like),
                Student.student_id.ilike(like),
            )
        )

    students = query.order_by(Student.grade_id, Student.class_id, Student.full_name_ar).all()
    editable_ids = {s.id for s in students if can_edit_student(current_user, s)}
    manageable_ids = {s.id for s in students if can_manage_student(current_user, s)}

    schools, grades, classes = _filter_options(school_id, grade_id)

    sid = school_id or (current_user.school_id if not current_user.is_platform_admin else None)
    unspecified = get_unspecified_label(sid)
    grouped = {}
    for student in students:
        level_key = student.grade.name_ar if student.grade else unspecified
        class_key = student.class_.name if student.class_ else unspecified
        grouped.setdefault(level_key, {}).setdefault(class_key, []).append(student)

    return render_template(
        "students/index.html",
        students=students,
        grouped=grouped,
        schools=schools,
        grades=grades,
        classes=classes,
        selected_school=school_id,
        selected_grade=grade_id,
        selected_class=class_id,
        teacher_tracking=teacher_tracking,
        editable_ids=editable_ids,
        manageable_ids=manageable_ids,
        show_inactive=show_inactive,
        search_q=search_q,
    )


@bp.route("/register")
@login_required
@permission_required("register_students", "manage_students")
def register():
    return redirect(url_for("evaluations.register"))


@bp.route("/<int:student_id>")
@login_required
def profile(student_id):
    student = Student.query.get_or_404(student_id)
    denied = _check_student_access(student)
    if denied:
        return denied

    kpi_scores, overall_kpi, kpi_breakdown = get_student_kpi_display(student.id, "term")
    attendance = Attendance.query.filter_by(student_id=student.id).order_by(
        Attendance.date.desc()
    ).limit(30).all()
    evaluations = Evaluation.query.filter_by(student_id=student.id).order_by(
        Evaluation.date.desc()
    ).limit(10).all()

    parents_available = _parents_for_school(student.school_id)
    relationship_choices = get_config_choices("parent_relationship", student.school_id)
    relationship_labels = get_config_map("parent_relationship", student.school_id)

    return render_template(
        "students/profile.html",
        student=student,
        kpi_scores=kpi_scores,
        kpi_breakdown=kpi_breakdown,
        overall_kpi=overall_kpi,
        attendance=attendance,
        evaluations=evaluations,
        status_map=get_attendance_status_map(student.school_id),
        parents_available=parents_available,
        relationship_choices=relationship_choices,
        relationship_labels=relationship_labels,
        category_labels=get_criterion_category_labels(student.school_id),
        daily_category_fields=get_daily_category_field_map(student.school_id),
        can_edit=can_edit_student(current_user, student),
        can_manage=can_manage_student(current_user, student),
        can_self_edit=can_student_edit_own(current_user, student),
    )


@bp.route("/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
def edit(student_id):
    student = Student.query.get_or_404(student_id)
    if not can_edit_student(current_user, student):
        flash("ليس لديك صلاحية لتعديل هذا الطالب.", "danger")
        return redirect(url_for("students.profile", student_id=student.id))

    schools = (
        School.query.filter_by(is_active=True).order_by(School.name_ar).all()
        if current_user.is_platform_admin else []
    )
    sid = student.school_id
    if request.method == "POST" and current_user.is_platform_admin and request.form.get("school_id"):
        sid = int(request.form["school_id"])

    grades = Grade.query.filter_by(school_id=sid).order_by(Grade.level).all()
    classes = Class.query.filter_by(school_id=sid, grade_id=student.grade_id).order_by(Class.name).all() if student.grade_id else []
    teachers = Teacher.query.filter_by(school_id=sid, is_active=True).order_by(Teacher.full_name_ar).all()
    academic_meta = registration_form_meta(sid, current_user)

    if request.method == "POST":
        try:
            update_student(
                student,
                request.form,
                allow_school_change=current_user.is_platform_admin,
            )
            flash("تم تحديث بيانات الطالب.", "success")
            return redirect(url_for("students.profile", student_id=student.id))
        except ValueError as exc:
            flash(str(exc), "danger")

    return render_template(
        "students/edit.html",
        student=student,
        schools=schools,
        grades=grades,
        classes=classes,
        teachers=teachers,
        gender_choices=get_config_choices("gender", sid),
        school_id=sid,
        selected_grade=student.grade_id,
        selected_class=student.class_id,
        **academic_meta,
    )


@bp.route("/<int:student_id>/self-edit", methods=["GET", "POST"])
@login_required
@permission_required("self_assess")
def self_edit(student_id):
    student = Student.query.get_or_404(student_id)
    if not can_student_edit_own(current_user, student):
        flash("ليس لديك صلاحية لتعديل هذا الملف.", "danger")
        return redirect(url_for("dashboards.index"))

    if request.method == "POST":
        update_student(student, request.form, self_edit=True)
        flash("تم تحديث بياناتك.", "success")
        return redirect(url_for("students.profile", student_id=student.id))

    return render_template("students/self_edit.html", student=student)


@bp.route("/bulk-action", methods=["POST"])
@login_required
@permission_required("manage_students")
def bulk_action():
    action = (request.form.get("action") or "").strip()
    student_ids = request.form.getlist("student_ids")
    redirect_args = {
        "show_inactive": request.form.get("show_inactive") or None,
        "school_id": request.form.get("school_id", type=int),
        "grade_id": request.form.get("grade_id", type=int),
        "class_id": request.form.get("class_id", type=int),
        "q": request.form.get("q") or None,
    }
    redirect_args = {k: v for k, v in redirect_args.items() if v}

    try:
        count = bulk_manage_students(current_user, student_ids, action)
        log_action(
            f"bulk_{action}_students",
            "students",
            f"count={count} ids={','.join(student_ids[:20])}",
        )
        if action == "deactivate":
            flash(f"تم تعطيل {count} طالب/طلاب.", "success")
        else:
            flash(f"تم تفعيل {count} طالب/طلاب.", "success")
    except ValueError as exc:
        flash(str(exc), "danger")

    return redirect(url_for("students.index", **redirect_args))


@bp.route("/<int:student_id>/deactivate", methods=["POST"])
@login_required
@permission_required("manage_students")
def deactivate(student_id):
    student = Student.query.get_or_404(student_id)
    if not can_manage_student(current_user, student):
        flash("ليس لديك صلاحية.", "danger")
        return redirect(url_for("students.index"))
    if not student.is_active:
        flash("الطالب معطّل مسبقاً.", "info")
        return redirect(url_for("students.profile", student_id=student.id))
    deactivate_student(student)
    flash("تم تعطيل الطالب. لن يظهر في القوائم النشطة.", "success")
    return redirect(url_for("students.index"))


@bp.route("/<int:student_id>/activate", methods=["POST"])
@login_required
@permission_required("manage_students")
def activate(student_id):
    student = Student.query.get_or_404(student_id)
    if not can_manage_student(current_user, student):
        flash("ليس لديك صلاحية.", "danger")
        return redirect(url_for("students.index"))
    activate_student(student)
    flash("تم تفعيل الطالب.", "success")
    return redirect(url_for("students.profile", student_id=student.id))


@bp.route("/<int:student_id>/link-parent", methods=["POST"])
@login_required
@permission_required("view_students", "manage_students")
def link_parent(student_id):
    student = Student.query.get_or_404(student_id)
    denied = _check_student_access(student)
    if denied:
        return denied

    parent = Parent.query.get_or_404(request.form.get("parent_id", type=int))
    if student not in parent.children:
        parent.children.append(student)
    rel = request.form.get("relationship_type")
    if rel:
        parent.relationship_type = rel
    db.session.commit()
    flash("تم ربط ولي الأمر بالطالب.", "success")
    return redirect(url_for("students.profile", student_id=student_id))


@bp.route("/<int:student_id>/unlink-parent/<int:parent_id>", methods=["POST"])
@login_required
@permission_required("view_students", "manage_students")
def unlink_parent(student_id, parent_id):
    student = Student.query.get_or_404(student_id)
    denied = _check_student_access(student)
    if denied:
        return denied
    parent = Parent.query.get_or_404(parent_id)
    if student in parent.children:
        parent.children.remove(student)
        db.session.commit()
        flash("تم إلغاء الربط.", "success")
    return redirect(url_for("students.profile", student_id=student_id))


def _filter_options(school_id, grade_id):
    if current_user.is_platform_admin:
        schools = School.query.filter_by(is_active=True).order_by(School.name_ar).all()
        sid = school_id or (schools[0].id if schools else None)
    else:
        schools = []
        sid = current_user.school_id

    grades = Grade.query.filter_by(school_id=sid).order_by(Grade.level).all() if sid else []
    classes = (
        Class.query.filter_by(school_id=sid, grade_id=grade_id).order_by(Class.name).all()
        if sid and grade_id else
        Class.query.filter_by(school_id=sid).order_by(Class.name).all() if sid else []
    )
    return schools, grades, classes


def _parents_for_school(school_id):
    role = Role.query.filter_by(name="parent").first()
    if not role:
        return []
    q = Parent.query.join(User).filter(User.role_id == role.id)
    if not current_user.is_platform_admin:
        q = q.filter(User.school_id == school_id)
    elif school_id:
        q = q.filter(User.school_id == school_id)
    return q.order_by(Parent.full_name_ar).all()


def _check_student_access(student):
    if current_user.is_platform_admin:
        return None
    if current_user.is_student and current_user.student_profile:
        if current_user.student_profile.id != student.id:
            flash("ليس لديك صلاحية.", "danger")
            return redirect(url_for("dashboards.index"))
    elif current_user.is_parent and current_user.parent_profile:
        if student not in current_user.parent_profile.children:
            flash("ليس لديك صلاحية.", "danger")
            return redirect(url_for("dashboards.index"))
    elif current_user.is_teacher and current_user.teacher_profile:
        if not teacher_can_access_student(current_user, student):
            flash("ليس لديك صلاحية.", "danger")
            return redirect(url_for("students.index"))
    elif current_user.school_id and student.school_id != current_user.school_id:
        flash("ليس لديك صلاحية.", "danger")
        return redirect(url_for("dashboards.index"))
    return None
