from flask import flash, redirect, render_template, request, url_for, jsonify
from flask_login import login_required, current_user

from app.kpi import bp
from app.extensions import db
from app.models import KPI, Student, StudentKPI
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
    if request.method == "POST":
        action = request.form.get("action", "add")

        if action == "add":
            code = request.form.get("code", "").strip()
            if not code:
                code = request.form["name"].lower().replace(" ", "_")
            sid = get_active_school_id() or current_user.school_id
            kpi = KPI(
                code=code,
                name=request.form["name"],
                name_ar=request.form["name_ar"],
                weight=float(request.form["weight"]),
                description=request.form.get("description"),
                school_id=sid,
            )
            db.session.add(kpi)
            flash("تم إضافة مؤشر الأداء.", "success")

        elif action == "update_weights":
            sid = get_active_school_id() or current_user.school_id
            query = KPI.query.filter_by(is_active=True)
            if sid:
                query = query.filter((KPI.school_id == sid) | (KPI.school_id.is_(None)))
            for kpi in query.all():
                val = request.form.get(f"weight_{kpi.id}")
                if val is not None:
                    kpi.weight = float(val)
            flash("تم تحديث الأوزان.", "success")

        elif action == "toggle":
            kpi = KPI.query.get(request.form.get("kpi_id", type=int))
            if kpi:
                kpi.is_active = not kpi.is_active
                flash("تم تحديث حالة المؤشر.", "success")

        db.session.commit()

        sid = get_active_school_id() or current_user.school_id
        if sid:
            recalculate_school_kpis(sid)

        return redirect(url_for("kpi.manage"))

    sid = get_active_school_id() or current_user.school_id
    kpi_query = KPI.query
    if sid:
        kpi_query = kpi_query.filter((KPI.school_id == sid) | (KPI.school_id.is_(None)))
    kpis = kpi_query.order_by(KPI.is_active.desc(), KPI.weight.desc()).all()
    total_weight = sum(k.weight for k in kpis if k.is_active)
    return render_template(
        "kpi/manage.html",
        kpis=kpis,
        total_weight=total_weight,
        sources=get_kpi_source_options(get_active_school_id() or current_user.school_id),
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
    period = request.form.get("period", "term")
    recalculate_student_kpis(student_id, period)
    flash("تم تحديث مؤشرات الأداء ديناميكياً.", "success")
    return redirect(url_for("kpi.student_kpi", student_id=student_id, period=period))


@bp.route("/recalculate-school", methods=["POST"])
@login_required
@permission_required("manage_kpi")
def recalculate_school():
    sid = get_active_school_id() or current_user.school_id
    if not sid:
        flash("حدد مدرسة أولاً.", "danger")
        return redirect(url_for("kpi.manage"))
    count = recalculate_school_kpis(sid)
    flash(f"تم تحديث مؤشرات {count} طالب.", "success")
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
