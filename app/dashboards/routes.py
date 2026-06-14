from datetime import date, timedelta

from flask import render_template, session, redirect, url_for, request
from flask_login import login_required, current_user
from sqlalchemy import func

from app.dashboards import bp
from app.extensions import db
from app.models import (
    School, Student, Teacher, Attendance, Evaluation,
)
from app.kpi.service import get_student_kpi_display
from app.services.config_service import (
    get_present_status_codes, get_performance_color, get_performance_thresholds,
    get_attendance_chart_labels,
)
from app.services.monitoring_analytics import (
    average_performance, attendance_rate, rank_groups, monthly_trends,
    monthly_evaluation_status,
)
from app.services.teacher_tracking_service import build_teacher_tracking
from app.services.teacher_student_service import classes_for_teacher
from app.utils.school_context import get_active_school_id


@bp.route("/switch-mode", methods=["POST"])
@login_required
def switch_mode():
    from app.services.permission_registry import user_has_dual_teacher_student_profiles

    mode = request.form.get("mode")
    if mode in ("teacher", "student") and user_has_dual_teacher_student_profiles(current_user):
        session["dashboard_mode"] = mode
    return redirect(url_for("dashboards.index"))


@bp.route("/")
@login_required
def index():
    from app.services.permission_registry import dashboard_type_for_user

    dash = dashboard_type_for_user(current_user)
    if dash == "super_admin":
        from flask import redirect, url_for
        return redirect(url_for("super_admin.index"))
    if dash == "ministry":
        return _ministry_dashboard()
    if dash == "school_manager":
        return _school_dashboard()
    if dash == "teacher":
        return _teacher_dashboard()
    if dash == "student":
        return _student_dashboard()
    if dash == "parent":
        return _parent_dashboard()
    return render_template("dashboards/default.html")


def _ministry_dashboard():
    schools_count = School.query.filter_by(is_active=True).count()
    students_count = Student.query.filter_by(is_active=True).count()
    teachers_count = Teacher.query.filter_by(is_active=True).count()
    schools = School.query.filter_by(is_active=True).all()

    school_stats = []
    for school in schools:
        student_count = Student.query.filter_by(school_id=school.id, is_active=True).count()
        school_stats.append({"school": school, "students": student_count})

    return render_template(
        "dashboards/ministry.html",
        schools_count=schools_count,
        students_count=students_count,
        teachers_count=teachers_count,
        school_stats=school_stats,
    )


def _school_dashboard():
    school_id = current_user.school_id
    students_count = Student.query.filter_by(school_id=school_id, is_active=True).count()
    teachers_count = Teacher.query.filter_by(school_id=school_id, is_active=True).count()

    week_ago = date.today() - timedelta(days=7)
    att_rate = _attendance_rate(school_id, week_ago)
    avg_perf = average_performance(school_id)
    strong_groups, weak_groups = rank_groups(school_id)
    trend_labels, trend_values = monthly_trends(school_id)
    month_status = monthly_evaluation_status(school_id)

    present_label, absent_label = get_attendance_chart_labels(school_id)
    return render_template(
        "dashboards/school.html",
        students_count=students_count,
        teachers_count=teachers_count,
        attendance_rate=att_rate,
        avg_performance=avg_perf,
        perf_color=get_performance_color(avg_perf, school_id),
        strong_groups=strong_groups,
        weak_groups=weak_groups,
        trend_labels=trend_labels,
        trend_values=trend_values,
        month_status=month_status,
        perf_thresholds=get_performance_thresholds(school_id),
        attendance_present_label=present_label,
        attendance_absent_label=absent_label,
    )


def _teacher_dashboard():
    teacher = current_user.teacher_profile
    if not teacher:
        return render_template(
            "dashboards/teacher.html",
            classes=[],
            students_count=0,
            tracking=None,
        )

    classes = classes_for_teacher(teacher)
    tracking = build_teacher_tracking(teacher)

    return render_template(
        "dashboards/teacher.html",
        classes=classes,
        students_count=tracking["student_count"],
        teacher=teacher,
        tracking=tracking,
    )


def _student_dashboard():
    student = current_user.student_profile
    if not student:
        return render_template("dashboards/student.html", student=None)

    kpi_scores, overall_kpi, kpi_breakdown = get_student_kpi_display(student.id, "term")

    week_ago = date.today() - timedelta(days=30)
    present_codes = get_present_status_codes(student.school_id)
    present = Attendance.query.filter(
        Attendance.student_id == student.id,
        Attendance.date >= week_ago,
        Attendance.status.in_(present_codes),
    ).count()
    total = Attendance.query.filter(
        Attendance.student_id == student.id,
        Attendance.date >= week_ago,
    ).count()
    attendance_pct = round((present / total * 100) if total else 0, 1)

    recent_evaluations = Evaluation.query.filter_by(student_id=student.id).order_by(
        Evaluation.date.desc()
    ).limit(5).all()

    return render_template(
        "dashboards/student.html",
        student=student,
        kpi_scores=kpi_scores,
        kpi_breakdown=kpi_breakdown,
        overall_kpi=overall_kpi,
        attendance_pct=attendance_pct,
        recent_evaluations=recent_evaluations,
    )


def _parent_dashboard():
    parent = current_user.parent_profile
    children = parent.children if parent else []

    children_data = []
    for child in children:
        _, overall_kpi, _ = get_student_kpi_display(child.id, "term")
        children_data.append({"student": child, "overall_kpi": overall_kpi})

    return render_template("dashboards/parent.html", children_data=children_data)


def _attendance_rate(school_id, since):
    total = Attendance.query.filter(
        Attendance.school_id == school_id,
        Attendance.date >= since,
    ).count()
    present_codes = get_present_status_codes(school_id)
    present = Attendance.query.filter(
        Attendance.school_id == school_id,
        Attendance.date >= since,
        Attendance.status.in_(present_codes),
    ).count()
    return round((present / total * 100) if total else 0, 1)


