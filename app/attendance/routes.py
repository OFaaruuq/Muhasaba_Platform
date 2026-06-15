from datetime import date, timedelta

from flask import flash, redirect, render_template, request, url_for
from app.services.message_service import flash_msg
from flask_login import login_required, current_user

from app.attendance import bp
from app.extensions import db
from app.models import Attendance, Student, Class
from app.services.config_service import (
    get_attendance_statuses, get_notify_status_codes,
    get_attendance_status_map, get_default_attendance_status,
    get_notification_content, get_present_status_codes,
)
from app.services.attendance_service import (
    can_record_class, attendance_teams_summary, records_for_user,
    weekly_summary_for_user,
)
from app.services.attendance_time_service import (
    get_attendance_time_settings, parse_hhmm, suggest_status_from_time,
    status_time_rules, format_hhmm,
)
from app.services.attendance_limit_service import (
    can_mark_student_status, can_teacher_record_session,
    approve_student_entry, denied_students_for_school,
    student_entry_context, get_attendance_weekly_settings,
    week_start_for, is_limit_enabled,
)
from app.utils import permission_required
from app.utils.permissions import user_has_any_permission
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


def _school_id():
    return get_active_school_id() or current_user.school_id


def _can_manage_attendance(user):
    return user_has_any_permission(
        user, "manage_students", "manage_platform_config", "manage_global_config",
    )


@bp.route("/")
@login_required
@permission_required("view_attendance", "record_attendance")
def index():
    selected_date = _parse_date(request.args.get("date"))
    sid = _school_id()
    teams = attendance_teams_summary(current_user, selected_date)
    records = records_for_user(current_user, selected_date)
    is_teacher_view = bool(current_user.is_teacher and current_user.teacher_profile)
    denied_count = 0
    if _can_manage_attendance(current_user) and sid and is_limit_enabled(sid):
        denied_count = len(denied_students_for_school(sid))

    return render_template(
        "attendance/index.html",
        records=records,
        selected_date=selected_date.isoformat(),
        status_map=get_attendance_status_map(sid),
        teams=teams,
        is_teacher_view=is_teacher_view,
        can_record=current_user.has_permission("record_attendance"),
        time_settings=get_attendance_time_settings(sid),
        weekly_settings=get_attendance_weekly_settings(sid),
        denied_count=denied_count,
        can_manage_denied=_can_manage_attendance(current_user),
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


@bp.route("/approvals")
@login_required
@permission_required("manage_students", "manage_platform_config", "manage_global_config")
def approvals():
    sid = _school_id()
    if not sid:
        flash_msg("kpi_select_school", "danger")
        return redirect(url_for("attendance.index"))

    week_str = request.args.get("week")
    week_start = _parse_date(week_str) if week_str else week_start_for(date.today())
    denied_rows = denied_students_for_school(sid, week_start)
    settings = get_attendance_weekly_settings(sid)

    return render_template(
        "attendance/approvals.html",
        denied_rows=denied_rows,
        week_start=week_start,
        week_end=week_start + timedelta(days=6),
        settings=settings,
    )


@bp.route("/approve-entry", methods=["POST"])
@login_required
@permission_required("manage_students", "manage_platform_config", "manage_global_config")
def approve_entry():
    student = Student.query.get_or_404(request.form.get("student_id", type=int))
    class_id = request.form.get("class_id", type=int)
    on_date = _parse_date(request.form.get("session_date"))
    reason = (request.form.get("reason") or "").strip() or None

    if student.school_id != (_school_id() or student.school_id):
        flash_msg("permission_attendance_group", "danger")
        return redirect(url_for("attendance.approvals"))

    approve_student_entry(student, class_id, on_date, current_user, reason)
    log_action(
        "approve_attendance_entry", "attendance",
        f"student={student.id} class={class_id} date={on_date}",
    )
    db.session.commit()
    flash_msg("attendance_entry_approved", "success", student.school_id)
    return redirect(request.referrer or url_for("attendance.approvals"))


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
    weekly_settings = get_attendance_weekly_settings(class_.school_id)

    if request.method == "POST":
        teacher = current_user.teacher_profile if current_user.is_teacher else None
        if teacher:
            ok, reason = can_teacher_record_session(teacher, class_id, today)
            if not ok:
                flash_msg("attendance_teacher_weekly_limit", "danger", class_.school_id)
                return redirect(url_for("attendance.record", class_id=class_id, date=today.isoformat()))

        statuses = get_attendance_statuses(class_.school_id)
        status_labels = {s.code: s.name_ar for s in statuses}
        notify_codes = get_notify_status_codes(class_.school_id)
        default_status = get_default_attendance_status(class_.school_id)
        present_codes = get_present_status_codes(class_.school_id)
        blocked = 0
        saved = 0

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

            if status in present_codes:
                allowed, _ = can_mark_student_status(student, class_id, today, status, current_user)
                if not allowed:
                    blocked += 1
                    continue

            if _can_manage_attendance(current_user) and request.form.get(f"approve_{student.id}") == "1":
                approve_student_entry(student, class_id, today, current_user)

            existing = Attendance.query.filter_by(
                student_id=student.id,
                class_id=class_id,
                date=today,
            ).first()
            if existing:
                existing.status = status
                existing.recorded_by = current_user.id
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
            saved += 1

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
            f"class={class_id} date={today} saved={saved} blocked={blocked}",
        )
        db.session.commit()
        for student in students:
            sync_kpis_for_student(student.id)
        if blocked:
            flash_msg("attendance_entry_blocked", "warning", class_.school_id, count=blocked)
        if saved:
            flash_msg("attendance_saved", "success", class_.school_id)
        elif blocked:
            pass
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

    student_contexts = {
        s.id: student_entry_context(s, class_id, today, current_user)
        for s in students
    }

    teacher_limit_note = None
    if current_user.is_teacher and current_user.teacher_profile:
        ok, reason = can_teacher_record_session(current_user.teacher_profile, class_id, today)
        if not ok:
            teacher_limit_note = reason

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
        weekly_settings=weekly_settings,
        student_contexts=student_contexts,
        present_codes=get_present_status_codes(class_.school_id),
        can_manage=_can_manage_attendance(current_user),
        teacher_limit_note=teacher_limit_note,
    )
