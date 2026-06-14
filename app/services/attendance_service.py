"""Attendance scoping and status helpers for teachers and staff."""

from datetime import date, timedelta

from app.models import Attendance, Class, Student
from app.services.teacher_student_service import teacher_assigned_class_ids
from app.services.config_service import (
    get_attendance_chart_labels,
    get_performance_color,
    get_present_status_codes,
)
from app.utils.permissions import user_has_permission
from app.utils.school_context import get_active_school_id


def teacher_class_ids(teacher):
    return teacher_assigned_class_ids(teacher)


def classes_for_attendance(user):
    """Classes the user may view/record attendance for."""
    if user.is_teacher and user.teacher_profile:
        class_ids = teacher_class_ids(user.teacher_profile)
        if not class_ids:
            return []
        return Class.query.filter(Class.id.in_(class_ids)).order_by(Class.name).all()

    sid = user.school_id or get_active_school_id()
    if user.is_platform_admin and not sid:
        return Class.query.order_by(Class.name).all()
    if sid:
        return Class.query.filter_by(school_id=sid).order_by(Class.name).all()
    return []


def can_record_class(user, class_):
    """Whether user may record attendance for this class."""
    if not user_has_permission(user, "record_attendance"):
        return False
    if user.is_super_admin:
        return True
    if user.is_platform_admin:
        sid = get_active_school_id() or user.school_id
        return not sid or class_.school_id == sid
    if user.school_id and class_.school_id != user.school_id:
        return False
    if user.is_teacher and user.teacher_profile:
        return class_.id in teacher_class_ids(user.teacher_profile)
    if user.is_school_manager:
        return True
    return False


def class_day_status(class_, on_date):
    """Today's attendance progress for one class/team."""
    students = Student.query.filter_by(class_id=class_.id, is_active=True).order_by(
        Student.full_name_ar
    ).all()
    student_ids = [s.id for s in students]
    recorded = 0
    if student_ids:
        recorded = Attendance.query.filter(
            Attendance.student_id.in_(student_ids),
            Attendance.date == on_date,
        ).count()
    total = len(students)
    return {
        "class": class_,
        "grade_name": class_.grade.name_ar if class_.grade else "—",
        "student_count": total,
        "recorded_count": recorded,
        "pending_count": max(0, total - recorded),
        "is_complete": total > 0 and recorded >= total,
        "has_students": total > 0,
    }


def attendance_teams_summary(user, on_date=None):
    """Per-class status rows for the attendance hub."""
    on_date = on_date or date.today()
    rows = [class_day_status(c, on_date) for c in classes_for_attendance(user)]
    complete = sum(1 for r in rows if r["is_complete"])
    pending = sum(1 for r in rows if r["has_students"] and not r["is_complete"])
    return {
        "date": on_date,
        "rows": rows,
        "team_count": len(rows),
        "complete_count": complete,
        "pending_count": pending,
        "all_complete": len(rows) > 0 and pending == 0,
    }


def records_for_user(user, on_date):
    """Attendance records visible on the index for the selected date."""
    query = Attendance.query.filter_by(date=on_date)
    if user.is_teacher and user.teacher_profile:
        class_ids = teacher_class_ids(user.teacher_profile)
        if not class_ids:
            return []
        query = query.filter(Attendance.class_id.in_(class_ids))
    elif not user.is_platform_admin:
        query = query.filter_by(school_id=user.school_id)
    else:
        sid = get_active_school_id() or user.school_id
        if sid:
            query = query.filter_by(school_id=sid)
    return query.order_by(Attendance.class_id, Attendance.student_id).all()


def weekly_summary_for_user(user, week_start=None):
    """Weekly attendance stats scoped to the user's classes."""
    if week_start is None:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    sid = user.school_id or get_active_school_id()
    present_codes = get_present_status_codes(sid) if sid else []
    summary = []

    for cls in classes_for_attendance(user):
        students = Student.query.filter_by(class_id=cls.id, is_active=True).all()
        if not students:
            continue
        student_ids = [s.id for s in students]
        total = Attendance.query.filter(
            Attendance.student_id.in_(student_ids),
            Attendance.date >= week_start,
            Attendance.date <= week_end,
        ).count()
        present = Attendance.query.filter(
            Attendance.student_id.in_(student_ids),
            Attendance.date >= week_start,
            Attendance.date <= week_end,
            Attendance.status.in_(present_codes),
        ).count() if present_codes else 0
        rate = round((present / total * 100) if total else 0, 1)
        summary.append({
            "class": cls,
            "name": cls.name,
            "grade_name": cls.grade.name_ar if cls.grade else "—",
            "students": len(students),
            "present": present,
            "total": total,
            "rate": rate,
            "color": get_performance_color(rate, sid or cls.school_id),
            "can_record": can_record_class(user, cls),
        })

    summary.sort(key=lambda x: x["rate"], reverse=True)
    present_label, _ = get_attendance_chart_labels(sid) if sid else ("حاضر", "غائب")
    return summary, week_start, week_end, present_label
