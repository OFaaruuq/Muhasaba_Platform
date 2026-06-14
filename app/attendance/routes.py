from datetime import date

from flask import flash, redirect, render_template, request, url_for
from app.services.message_service import flash_msg
from flask_login import login_required, current_user

from app.attendance import bp
from app.extensions import db
from app.models import Attendance, Student, Class
from app.services.config_service import (
    get_attendance_statuses, get_notify_status_codes,
    get_attendance_status_map, get_default_attendance_status,
    get_notification_content,
)
from app.services.attendance_service import (
    can_record_class, attendance_teams_summary, records_for_user,
    weekly_summary_for_user,
)
from app.services.attendance_time_service import (
    get_attendance_time_settings, parse_hhmm, suggest_status_from_time,
    status_time_rules, format_hhmm,
)
from app.utils import permission_required
from app.utils.notifications import notify_parent_of_student
from app.kpi.hooks import sync_kpis_for_student
from app.utils.school_context import get_active_school_id
from app.services.audit_service import log_action


def _parse_date(value):
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return date.today()


@bp.route("/")
@login_required
@permission_required("view_attendance", "record_attendance")
def index():
    selected_date = _parse_date(request.args.get("date"))
    sid = get_active_school_id() or current_user.school_id
    teams = attendance_teams_summary(current_user, selected_date)
    records = records_for_user(current_user, selected_date)
    is_teacher_view = bool(current_user.is_teacher and current_user.teacher_profile)

    return render_template(
        "attendance/index.html",
        records=records,
        selected_date=selected_date.isoformat(),
        status_map=get_attendance_status_map(sid),
        teams=teams,
        is_teacher_view=is_teacher_view,
        can_record=current_user.has_permission("record_attendance"),
        time_settings=get_attendance_time_settings(sid),
    )


@bp.route("/weekly")
@login_required
@permission_required("view_attendance", "record_attendance")
def weekly():
    week_str = request.args.get("week")
    week_start = _parse_date(week_str) if week_str else None

    summary, start, end, present_label = weekly_summary_for_user(current_user, week_start)
    return render_template(
        "attendance/weekly.html",
        summary=summary,
        week_start=start,
        week_end=end,
        present_column_label=present_label,
        can_record=current_user.has_permission("record_attendance"),
    )


@bp.route("/record/<int:class_id>", methods=["GET", "POST"])
@login_required
@permission_required("record_attendance")
def record(class_id):
    class_ = Class.query.get_or_404(class_id)
    if not can_record_class(current_user, class_):
        flash_msg("permission_attendance_group", "danger")
        return redirect(url_for("attendance.index"))

    students = Student.query.filter_by(class_id=class_id, is_active=True).order_by(
        Student.full_name_ar
    ).all()
    today = _parse_date(request.args.get("date") or request.form.get("date"))

    time_settings = get_attendance_time_settings(class_.school_id)

    if request.method == "POST":
        statuses = get_attendance_statuses(class_.school_id)
        status_labels = {s.code: s.name_ar for s in statuses}
        notify_codes = get_notify_status_codes(class_.school_id)
        default_status = get_default_attendance_status(class_.school_id)
        for student in students:
            check_in = None
            if time_settings["record_time"]:
                check_in = parse_hhmm(request.form.get(f"time_{student.id}"))
            status = request.form.get(f"status_{student.id}", default_status)
            if (
                time_settings["auto_suggest"]
                and check_in
                and not request.form.get(f"manual_{student.id}")
            ):
                suggested = suggest_status_from_time(class_.school_id, check_in)
                if suggested:
                    status = suggested
            existing = Attendance.query.filter_by(student_id=student.id, date=today).first()
            if existing:
                existing.status = status
                existing.recorded_by = current_user.id
                existing.class_id = class_id
                existing.check_in_time = check_in
            else:
                db.session.add(Attendance(
                    student_id=student.id,
                    school_id=class_.school_id,
                    class_id=class_id,
                    date=today,
                    status=status,
                    check_in_time=check_in,
                    recorded_by=current_user.id,
                ))
            if status in notify_codes:
                time_note = f" — {format_hhmm(check_in)}" if check_in else ""
                title, message, ntype = get_notification_content(
                    "attendance",
                    class_.school_id,
                    student=student.full_name_ar,
                    status=status_labels.get(status, status),
                    time_note=time_note,
                    date=today,
                )
                notify_parent_of_student(
                    student,
                    title,
                    message,
                    ntype,
                    url_for("students.profile", student_id=student.id),
                )
        log_action(
            "record_attendance", "attendance",
            f"class={class_id} date={today} students={len(students)}",
        )
        db.session.commit()
        for student in students:
            sync_kpis_for_student(student.id)
        flash_msg("attendance_saved", "success", sid)
        return redirect(url_for("attendance.index", date=today.isoformat()))

    existing_records = {
        a.student_id: a
        for a in Attendance.query.filter_by(class_id=class_id, date=today).all()
    }
    existing = {sid: a.status for sid, a in existing_records.items()}
    existing_times = {
        sid: a.check_in_time.strftime("%H:%M") if a.check_in_time else ""
        for sid, a in existing_records.items()
    }
    statuses = get_attendance_statuses(class_.school_id)
    status_choices = [(s.code, s.name_ar) for s in statuses]
    team_status = attendance_teams_summary(current_user, today)
    row = next((r for r in team_status["rows"] if r["class"].id == class_id), None)

    return render_template(
        "attendance/record.html",
        class_=class_,
        students=students,
        existing=existing,
        existing_times=existing_times,
        today=today,
        statuses=status_choices,
        default_status=get_default_attendance_status(class_.school_id),
        team_status=row,
        time_settings=time_settings,
        status_time_rules=status_time_rules(class_.school_id),
    )
