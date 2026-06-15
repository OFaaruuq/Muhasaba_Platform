"""Weekly class limits, per-class attendance gates, and management approvals."""

from datetime import date, datetime, timedelta, timezone

from app.extensions import db
from app.models import Attendance, AttendanceEntryApproval, Student, Teacher
from app.services.config_service import (
    get_attendance_statuses,
    get_present_status_codes,
    get_setting,
    set_setting,
)
from app.utils.permissions import user_has_any_permission


def _truthy(value):
    return str(value).lower() in ("true", "1", "yes", "on")


def week_start_for(on_date):
    return on_date - timedelta(days=on_date.weekday())


def get_attendance_weekly_settings(school_id=None):
    return {
        "enabled": _truthy(get_setting("attendance_weekly_limit_enabled", school_id, "true")),
        "student_classes": int(get_setting("attendance_weekly_classes_student", school_id, 3)),
        "teacher_classes": int(get_setting("attendance_weekly_classes_teacher", school_id, 12)),
        "absence_deny": int(get_setting("attendance_weekly_absence_deny", school_id, 2)),
    }


def save_attendance_weekly_settings(school_id, form):
    pairs = [
        ("attendance_weekly_limit_enabled", "on" if form.get("attendance_weekly_limit_enabled") else "false"),
        ("attendance_weekly_classes_student", form.get("attendance_weekly_classes_student")),
        ("attendance_weekly_classes_teacher", form.get("attendance_weekly_classes_teacher")),
        ("attendance_weekly_absence_deny", form.get("attendance_weekly_absence_deny")),
    ]
    labels = {
        "attendance_weekly_limit_enabled": "تفعيل حد الحصص الأسبوعية",
        "attendance_weekly_classes_student": "عدد حصص الطالب الأسبوعية",
        "attendance_weekly_classes_teacher": "عدد حصص المعلم الأسبوعية",
        "attendance_weekly_absence_deny": "غيابات قبل منع الدخول",
    }
    for key, val in pairs:
        if val is not None and str(val).strip() != "":
            set_setting(key, str(val).strip(), school_id, "attendance", labels[key])
    return len(pairs)


def is_limit_enabled(school_id):
    return get_attendance_weekly_settings(school_id)["enabled"]


def get_student_weekly_limit(student):
    if student.weekly_class_limit is not None:
        return student.weekly_class_limit
    return get_attendance_weekly_settings(student.school_id)["student_classes"]


def get_teacher_weekly_limit(teacher):
    if teacher.weekly_class_limit is not None:
        return teacher.weekly_class_limit
    return get_attendance_weekly_settings(teacher.school_id)["teacher_classes"]


def get_absence_deny_threshold(school_id):
    return get_attendance_weekly_settings(school_id)["absence_deny"]


def parse_weekly_limit(value):
    if value is None or str(value).strip() == "":
        return None
    limit = int(value)
    if limit < 1:
        raise ValueError("حد الحصص الأسبوعية يجب أن يكون 1 على الأقل.")
    return limit


def student_week_attendance_stats(student, week_start):
    week_end = week_start + timedelta(days=6)
    records = Attendance.query.filter(
        Attendance.student_id == student.id,
        Attendance.date >= week_start,
        Attendance.date <= week_end,
    ).all()
    present_codes = get_present_status_codes(student.school_id)
    present = sum(1 for r in records if r.status in present_codes)
    absences = sum(1 for r in records if r.status not in present_codes)
    return {
        "sessions": len(records),
        "present": present,
        "absences": absences,
        "records": records,
    }


def has_approval_for_session(student_id, class_id, on_date):
    return AttendanceEntryApproval.query.filter_by(
        student_id=student_id,
        class_id=class_id,
        session_date=on_date,
        status=AttendanceEntryApproval.STATUS_APPROVED,
    ).first() is not None


def is_student_denied_entry(student, class_id, on_date, proposed_status=None):
    """Return (denied: bool, reason_code: str|None)."""
    if not is_limit_enabled(student.school_id):
        return False, None
    if has_approval_for_session(student.id, class_id, on_date):
        return False, None

    ws = week_start_for(on_date)
    stats = student_week_attendance_stats(student, ws)
    present_codes = get_present_status_codes(student.school_id)
    threshold = get_absence_deny_threshold(student.school_id)

    existing = Attendance.query.filter_by(
        student_id=student.id,
        class_id=class_id,
        date=on_date,
    ).first()

    marking_present = (
        proposed_status in present_codes
        if proposed_status
        else existing is None or existing.status in present_codes
    )

    if stats["absences"] >= threshold and marking_present:
        return True, "absence_threshold"

    limit = get_student_weekly_limit(student)
    would_add_present = (
        proposed_status in present_codes
        and (not existing or existing.status not in present_codes)
    )
    if would_add_present and stats["present"] >= limit:
        return True, "weekly_limit"

    return False, None


def can_mark_student_status(student, class_id, on_date, status, user=None):
    present_codes = get_present_status_codes(student.school_id)
    if status not in present_codes:
        return True, None

    if user and user_has_any_permission(
        user, "manage_students", "manage_platform_config", "manage_global_config"
    ):
        return True, "manager_override"

    denied, reason = is_student_denied_entry(student, class_id, on_date, status)
    if denied:
        return False, reason
    return True, None


def teacher_recorded_sessions(teacher, week_start):
    if not teacher.user_id:
        return set()
    week_end = week_start + timedelta(days=6)
    rows = (
        db.session.query(Attendance.class_id, Attendance.date)
        .filter(
            Attendance.recorded_by == teacher.user_id,
            Attendance.date >= week_start,
            Attendance.date <= week_end,
        )
        .distinct()
        .all()
    )
    return {(class_id, on_date) for class_id, on_date in rows}


def can_teacher_record_session(teacher, class_id, on_date):
    if not is_limit_enabled(teacher.school_id):
        return True, None
    ws = week_start_for(on_date)
    sessions = teacher_recorded_sessions(teacher, ws)
    key = (class_id, on_date)
    if key in sessions:
        return True, None
    limit = get_teacher_weekly_limit(teacher)
    if len(sessions) >= limit:
        return False, "teacher_weekly_limit"
    return True, None


def approve_student_entry(student, class_id, on_date, reviewer, reason=None):
    ws = week_start_for(on_date)
    row = AttendanceEntryApproval.query.filter_by(
        student_id=student.id,
        class_id=class_id,
        session_date=on_date,
    ).first()
    now = datetime.now(timezone.utc)
    if row:
        row.status = AttendanceEntryApproval.STATUS_APPROVED
        row.reviewed_by = reviewer.id
        row.reviewed_at = now
        if reason:
            row.reason = reason
    else:
        db.session.add(AttendanceEntryApproval(
            student_id=student.id,
            school_id=student.school_id,
            class_id=class_id,
            session_date=on_date,
            week_start=ws,
            status=AttendanceEntryApproval.STATUS_APPROVED,
            reason=reason,
            reviewed_by=reviewer.id,
            reviewed_at=now,
            requested_by=reviewer.id,
        ))
    return row


def denied_students_for_school(school_id, week_start=None):
    """Students blocked from present entry this week (no approval for today onward)."""
    if not is_limit_enabled(school_id):
        return []
    week_start = week_start or week_start_for(date.today())
    threshold = get_absence_deny_threshold(school_id)
    present_codes = get_present_status_codes(school_id)
    week_end = week_start + timedelta(days=6)

    students = Student.query.filter_by(school_id=school_id, is_active=True).all()
    denied = []
    for student in students:
        stats = student_week_attendance_stats(student, week_start)
        if stats["absences"] < threshold and stats["present"] < get_student_weekly_limit(student):
            continue
        reason = None
        if stats["absences"] >= threshold:
            reason = "absence_threshold"
        elif stats["present"] >= get_student_weekly_limit(student):
            reason = "weekly_limit"
        denied.append({
            "student": student,
            "stats": stats,
            "reason": reason,
            "limit": get_student_weekly_limit(student),
            "threshold": threshold,
            "class": student.class_,
            "week_start": week_start,
            "week_end": week_end,
            "present_codes": present_codes,
        })
    return denied


def student_entry_context(student, class_id, on_date, user=None):
    """UI context for one student row on the record form."""
    ws = week_start_for(on_date)
    stats = student_week_attendance_stats(student, ws)
    denied, reason = is_student_denied_entry(student, class_id, on_date)
    can_present, block_reason = can_mark_student_status(
        student, class_id, on_date,
        get_present_status_codes(student.school_id)[0] if get_present_status_codes(student.school_id) else "present",
        user,
    )
    approved = has_approval_for_session(student.id, class_id, on_date)
    return {
        "weekly_limit": get_student_weekly_limit(student),
        "week_stats": stats,
        "denied": denied and not can_present,
        "reason": reason or block_reason,
        "approved": approved,
        "can_manage": bool(
            user and user_has_any_permission(
                user, "manage_students", "manage_platform_config", "manage_global_config"
            )
        ),
    }
