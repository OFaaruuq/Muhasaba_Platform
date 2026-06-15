from flask import flash, redirect, render_template, request, url_for, jsonify
from app.services.message_service import flash_msg
from flask_login import login_required, current_user

from app.kpi import bp
from app.extensions import db
from app.models import Student
from app.services.kpi_admin_service import (
    kpi_query_for_school, total_active_kpi_weight, add_kpi_for_school,
    toggle_kpi, update_kpi_weights,
)
from app.kpi.service import (
    get_active_kpis, recalculate_student_kpis, recalculate_school_kpis,
    get_student_kpi_display,
)
from app.kpi.calculator import calculate_overall
from app.utils import permission_required
from app.utils.api_auth import api_auth_required, api_user
from app.utils.school_context import get_active_school_id
from app.services.report_service import can_access_student_report
from app.services.config_service import get_kpi_source_options, get_kpi_source_description
from app.services.kpi_page_service import (
    classes_for_kpi_filter,
    students_for_kpi_index,
    build_students_kpi_rows,
    build_kpi_summaries,
)


@bp.route("/")
@login_required
@permission_required("view_kpi", "view_own_kpi", "view_children_kpi", "manage_kpi")
def index():
    period = request.args.get("period", "term")
    sid = get_active_school_id() or current_user.school_id
    kpis = get_active_kpis(sid)

    if current_user.is_student and current_user.student_profile:
        student = current_user.student_profile
        scores, overall, breakdown = get_student_kpi_display(student.id, period)
        return render_template(
            "kpi/student.html",
            scores=scores,
            breakdown=breakdown,
            overall=overall,
            period=period,
            student=student,
        )

    if current_user.is_parent and current_user.parent_profile:
        children_kpi = []
        for child in current_user.parent_profile.children:
            scores, overall, breakdown = get_student_kpi_display(child.id, period)
            children_kpi.append({
                "student": child,
                "scores": scores,
                "breakdown": breakdown,
                "overall": overall,
            })
        return render_template("kpi/parent.html", children_kpi=children_kpi, period=period)

    class_id = request.args.get("class_id", type=int)
    search = (request.args.get("q") or "").strip()
    classes = classes_for_kpi_filter(current_user, sid)
    students = students_for_kpi_index(current_user, sid, class_id, search)
    students_data = build_students_kpi_rows(students, kpis, period) if students else []
    kpi_summaries = build_kpi_summaries(students_data, kpis) if kpis else []
    total_weight = sum(k.weight for k in kpis)

    return render_template(
        "kpi/index.html",
        kpis=kpis,
        can_manage=current_user.has_permission("manage_kpi"),
        students_data=students_data,
        kpi_summaries=kpi_summaries,
        total_weight=total_weight,
        period=period,
        class_id=class_id,
        search=search,
        classes=classes,
        school_id=sid,
        get_kpi_source_description=get_kpi_source_description,
    )


@bp.route("/manage", methods=["GET", "POST"])
@login_required
@permission_required("manage_kpi")
def manage():
    sid = get_active_school_id() or current_user.school_id
    if request.method == "POST":
        action = request.form.get("action", "add")
        try:
            if action == "add":
                add_kpi_for_school(sid, request.form)
                flash_msg("kpi_added", "success", sid)
            elif action == "update_weights":
                update_kpi_weights(request.form, sid)
                flash_msg("kpi_weights_updated", "success", sid)
            elif action == "toggle":
                toggle_kpi(request.form.get("kpi_id", type=int))
                flash_msg("kpi_status_updated", "success", sid)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("kpi.manage"))

        db.session.commit()
        if sid:
            recalculate_school_kpis(sid)
        return redirect(url_for("kpi.manage"))

    kpis = kpi_query_for_school(sid).all()
    total_weight = total_active_kpi_weight(kpis)
    return render_template(
        "kpi/manage.html",
        kpis=kpis,
        total_weight=total_weight,
        sources=get_kpi_source_options(sid),
    )


@bp.route("/student/<int:student_id>")
@login_required
def student_kpi(student_id):
    student = Student.query.get_or_404(student_id)
    period = request.args.get("period", "term")
    scores, overall, breakdown = get_student_kpi_display(student_id, period)

    sid = student.school_id
    return render_template(
        "kpi/student_detail.html",
        student=student,
        scores=scores,
        breakdown=breakdown,
        overall=overall,
        period=period,
        active_kpis=get_active_kpis(sid),
    )


@bp.route("/recalculate/<int:student_id>", methods=["POST"])
@login_required
@permission_required("manage_kpi", "manage_evaluations")
def recalculate_one(student_id):
    student = Student.query.get_or_404(student_id)
    period = request.form.get("period", "term")
    recalculate_student_kpis(student_id, period)
    flash_msg("kpi_recalculated", "success", student.school_id)
    return redirect(url_for("kpi.student_kpi", student_id=student_id, period=period))


@bp.route("/recalculate-school", methods=["POST"])
@login_required
@permission_required("manage_kpi")
def recalculate_school():
    sid = get_active_school_id() or current_user.school_id
    if not sid:
        flash_msg("kpi_select_school", "danger")
        return redirect(url_for("kpi.manage"))
    count = recalculate_school_kpis(sid)
    flash_msg("kpi_students_updated", "success", sid, count=count)
    return redirect(url_for("kpi.manage"))


@bp.route("/api/student/<int:student_id>")
@api_auth_required()
def api_student_kpi(student_id):
    user = api_user()
    student = Student.query.get_or_404(student_id)
    if not can_access_student_report(user, student):
        return jsonify({"error": "غير مصرح"}), 403
    period = request.args.get("period", "term")
    overall, breakdown = calculate_overall(student_id, period)
    return jsonify({
        "overall": overall,
        "kpis": [
            {
                "name": b["kpi"].name_ar,
                "code": b["kpi"].code,
                "score": b["score"],
                "weight": b["kpi"].weight,
                "source": b["detail"].get("source"),
                "records": b["detail"].get("records"),
            }
            for b in breakdown
        ],
    })
