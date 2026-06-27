import io
from datetime import date, timedelta

from flask import render_template, request, send_file, abort
from flask_login import login_required, current_user
from openpyxl import Workbook

from app.reports import bp
from app.models import Student, Teacher, School, Attendance, Evaluation, MonthlyEvaluation, Grade, Class
from app.kpi.service import get_student_kpi_display
from app.services.config_service import get_setting, get_attendance_status_map
from app.services.followup_survey_service import (
    arabic_months,
    followup_period_context,
    can_view_family_surveys,
    can_fill_teacher_surveys,
    resolve_followup_school_id,
)
from app.services.educational_program_service import can_fill_program_surveys
from app.services.report_service import (
    can_access_reports,
    can_access_student_report,
    can_access_teacher_report,
    list_students_for_reports,
    list_teachers_for_reports,
    student_report_cards,
    teacher_report_cards,
    reports_summary,
    reports_completion_pct,
)
from app.services.report_export_service import (
    export_kpi_pdf,
    export_evaluation_pdf,
    export_monthly_evaluation_pdf,
    export_family_followup_pdf,
    export_teacher_followup_pdf,
    export_program_followup_pdf,
)
from app.services.identity_service import student_file_id, teacher_file_id


def _period_from_request():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month
    return year, month


@bp.route("/")
@login_required
def index():
    if not can_access_reports(current_user):
        abort(403)

    year, month = _period_from_request()
    tab = request.args.get("tab", "students")
    search_q = (request.args.get("q") or "").strip()
    grade_id = request.args.get("grade_id", type=int)
    class_id = request.args.get("class_id", type=int)
    status_filter = (request.args.get("status") or "all").strip()
    sid = resolve_followup_school_id(current_user)
    period_ctx = followup_period_context(year, month, sid)

    school_name = None
    if sid:
        school = School.query.get(sid)
        school_name = school.name_ar if school else None

    students = list_students_for_reports(current_user, search_q, grade_id, class_id)
    teachers = list_teachers_for_reports(current_user, search_q)

    show_teachers = bool(can_fill_teacher_surveys(current_user) or can_fill_program_surveys(current_user))
    show_family = can_view_family_surveys(current_user)
    allowed_tabs = []
    if show_family or students:
        allowed_tabs.append("students")
    if show_teachers:
        allowed_tabs.append("teachers")
    if tab not in allowed_tabs and allowed_tabs:
        tab = allowed_tabs[0]

    student_cards = (
        student_report_cards(students, year, month, status_filter)
        if tab == "students" else []
    )
    teacher_cards = (
        teacher_report_cards(teachers, year, month, status_filter)
        if tab == "teachers" else []
    )
    summary = reports_summary(students, teachers, year, month) if sid or students else None

    grades = []
    classes = []
    if sid:
        grades = Grade.query.filter_by(school_id=sid).order_by(Grade.level).all()
        class_query = Class.query.filter_by(school_id=sid)
        if grade_id:
            class_query = class_query.filter_by(grade_id=grade_id)
        classes = class_query.order_by(Class.name).all()

    is_student_view = current_user.is_student
    is_parent_view = current_user.is_parent

    return render_template(
        "reports/index.html",
        tab=tab,
        period_year=year,
        period_month=month,
        period_ctx=period_ctx,
        arabic_months=arabic_months(sid),
        search_q=search_q,
        selected_grade=grade_id,
        selected_class=class_id,
        grades=grades,
        classes=classes,
        sid=sid,
        student_cards=student_cards,
        teacher_cards=teacher_cards,
        summary=summary,
        school_name=school_name,
        status_filter=status_filter,
        reports_completion_pct=reports_completion_pct,
        student_count=len(student_cards) if tab == "students" else len(students),
        teacher_count=len(teacher_cards) if tab == "teachers" else len(teachers),
        show_teachers=show_teachers,
        show_family=show_family,
        is_student_view=is_student_view,
        is_parent_view=is_parent_view,
        can_fill_teacher=can_fill_teacher_surveys(current_user),
        can_fill_program=can_fill_program_surveys(current_user),
    )


def _require_student(student_id):
    student = Student.query.get_or_404(student_id)
    if not can_access_student_report(current_user, student):
        abort(403)
    return student


def _require_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    if not can_access_teacher_report(current_user, teacher):
        abort(403)
    return teacher


@bp.route("/student/<int:student_id>/kpi-pdf")
@login_required
def student_kpi_pdf(student_id):
    student = _require_student(student_id)
    scores, overall, _breakdown = get_student_kpi_display(student.id, "term")
    buffer = export_kpi_pdf(student, scores, overall)
    return send_file(
        buffer, as_attachment=True,
        download_name=f"kpi_{student_file_id(student)}.pdf",
        mimetype="application/pdf",
    )


@bp.route("/student/<int:student_id>/attendance-excel")
@login_required
def attendance_excel(student_id):
    student = _require_student(student_id)
    days = int(get_setting("kpi_period_days_term", student.school_id, 90))
    since = date.today() - timedelta(days=days)
    records = Attendance.query.filter(
        Attendance.student_id == student.id,
        Attendance.date >= since,
    ).order_by(Attendance.date).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"
    status_map = get_attendance_status_map(student.school_id)
    from app.services.config_service import get_report_labels
    report_labels = get_report_labels(student.school_id)
    ws.append([report_labels.get("date", "التاريخ"), "الفصل", report_labels.get("daily", "الحالة"), "ملاحظات"])
    for r in records:
        class_name = r.class_.name if r.class_ else "—"
        ws.append([
            str(r.date),
            class_name,
            status_map.get(r.status, {}).get("name_ar", r.status),
            r.notes or "",
        ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return send_file(
        buffer, as_attachment=True,
        download_name=f"attendance_{student_file_id(student)}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/student/<int:student_id>/evaluation-pdf")
@login_required
def evaluation_pdf(student_id):
    student = _require_student(student_id)
    evaluations = Evaluation.query.filter_by(student_id=student.id).order_by(
        Evaluation.date.desc()
    ).limit(30).all()
    buffer = export_evaluation_pdf(student, evaluations)
    return send_file(
        buffer, as_attachment=True,
        download_name=f"eval_{student_file_id(student)}.pdf",
        mimetype="application/pdf",
    )


@bp.route("/student/<int:student_id>/monthly-pdf")
@login_required
def monthly_pdf(student_id):
    student = _require_student(student_id)
    year = request.args.get("year", date.today().year, type=int)
    month = request.args.get("month", date.today().month, type=int)
    evaluation = MonthlyEvaluation.query.filter_by(
        student_id=student.id, period_year=year, period_month=month,
    ).first()
    buffer = export_monthly_evaluation_pdf(student, evaluation, year, month)
    return send_file(
        buffer, as_attachment=True,
        download_name=f"monthly_{student_file_id(student)}_{year}_{month}.pdf",
        mimetype="application/pdf",
    )


@bp.route("/student/<int:student_id>/family-followup-pdf")
@login_required
def family_followup_pdf(student_id):
    student = _require_student(student_id)
    year = request.args.get("year", date.today().year, type=int)
    month = request.args.get("month", date.today().month, type=int)
    buffer = export_family_followup_pdf(student, year, month)
    return send_file(
        buffer, as_attachment=True,
        download_name=f"family_followup_{student_file_id(student)}_{year}_{month}.pdf",
        mimetype="application/pdf",
    )


@bp.route("/teacher/<int:teacher_id>/teacher-followup-pdf")
@login_required
def teacher_followup_pdf(teacher_id):
    teacher = _require_teacher(teacher_id)
    year = request.args.get("year", date.today().year, type=int)
    month = request.args.get("month", date.today().month, type=int)
    buffer = export_teacher_followup_pdf(teacher, year, month)
    return send_file(
        buffer, as_attachment=True,
        download_name=f"teacher_followup_{teacher_file_id(teacher)}_{year}_{month}.pdf",
        mimetype="application/pdf",
    )


@bp.route("/teacher/<int:teacher_id>/program-followup-pdf")
@login_required
def program_followup_pdf(teacher_id):
    teacher = _require_teacher(teacher_id)
    year = request.args.get("year", date.today().year, type=int)
    month = request.args.get("month", date.today().month, type=int)
    buffer = export_program_followup_pdf(teacher, year, month)
    return send_file(
        buffer, as_attachment=True,
        download_name=f"program_followup_{teacher_file_id(teacher)}_{year}_{month}.pdf",
        mimetype="application/pdf",
    )
