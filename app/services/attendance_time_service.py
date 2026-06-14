"""Dynamic attendance time rules and status suggestion."""

from datetime import time

from app.services.config_service import get_attendance_statuses, get_setting


DEFAULT_TIME_SETTINGS = {
    "attendance_time_enabled": "true",
    "attendance_session_start": "08:00",
    "attendance_on_time_until": "08:15",
    "attendance_late_until": "08:45",
    "attendance_absent_after": "08:46",
    "attendance_auto_suggest": "true",
    "attendance_record_time": "true",
}


def _truthy(value):
    return str(value).lower() in ("true", "1", "yes", "on")


def parse_hhmm(value):
    """Parse 'HH:MM' or datetime.time into time."""
    if value is None or value == "":
        return None
    if isinstance(value, time):
        return value
    parts = str(value).strip().split(":")
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time(hour, minute)
    except (TypeError, ValueError):
        return None
    return None


def format_hhmm(value):
    if not value:
        return "—"
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return str(value)


def get_attendance_time_settings(school_id=None):
    """School attendance time policy (admin-configurable)."""
    return {
        "enabled": _truthy(get_setting(
            "attendance_time_enabled", school_id, DEFAULT_TIME_SETTINGS["attendance_time_enabled"],
        )),
        "session_start": get_setting(
            "attendance_session_start", school_id, DEFAULT_TIME_SETTINGS["attendance_session_start"],
        ),
        "on_time_until": get_setting(
            "attendance_on_time_until", school_id, DEFAULT_TIME_SETTINGS["attendance_on_time_until"],
        ),
        "late_until": get_setting(
            "attendance_late_until", school_id, DEFAULT_TIME_SETTINGS["attendance_late_until"],
        ),
        "absent_after": get_setting(
            "attendance_absent_after", school_id, DEFAULT_TIME_SETTINGS["attendance_absent_after"],
        ),
        "auto_suggest": _truthy(get_setting(
            "attendance_auto_suggest", school_id, DEFAULT_TIME_SETTINGS["attendance_auto_suggest"],
        )),
        "record_time": _truthy(get_setting(
            "attendance_record_time", school_id, DEFAULT_TIME_SETTINGS["attendance_record_time"],
        )),
    }


def status_time_rules(school_id=None):
    """Per-status time windows for templates and suggestion."""
    rules = []
    for status in get_attendance_statuses(school_id):
        rules.append({
            "code": status.code,
            "name_ar": status.name_ar,
            "time_from": status.time_from or "",
            "time_to": status.time_to or "",
        })
    return rules


def _in_window(check_in, time_from, time_to):
    start = parse_hhmm(time_from) if time_from else time(0, 0)
    end = parse_hhmm(time_to) if time_to else time(23, 59, 59)
    return start <= check_in <= end


def suggest_status_from_time(school_id, check_in_value):
    """
    Suggest attendance status code from check-in time.
    Uses per-status windows first, then global on-time/late/absent thresholds.
    """
    settings = get_attendance_time_settings(school_id)
    if not settings["enabled"]:
        return None

    check_in = parse_hhmm(check_in_value)
    if not check_in:
        return None

    for status in get_attendance_statuses(school_id):
        if not status.time_from and not status.time_to:
            continue
        if _in_window(check_in, status.time_from, status.time_to):
            return status.code

    on_time_until = parse_hhmm(settings["on_time_until"])
    late_until = parse_hhmm(settings["late_until"])
    absent_after = parse_hhmm(settings["absent_after"])

    if on_time_until and check_in <= on_time_until:
        for status in get_attendance_statuses(school_id):
            if status.code == "present":
                return status.code
        return "present"

    if late_until and check_in <= late_until:
        for status in get_attendance_statuses(school_id):
            if status.code == "late":
                return status.code
        return "late"

    if absent_after and check_in >= absent_after:
        for status in get_attendance_statuses(school_id):
            if status.code == "absent":
                return status.code
        return "absent"

    return None


def save_attendance_time_settings(school_id, form):
    """Persist admin attendance time policy."""
    from app.services.config_service import set_setting

    set_setting(
        "attendance_time_enabled",
        "true" if form.get("attendance_time_enabled") == "on" else "false",
        school_id, "attendance", "تفعيل قواعد الوقت",
    )
    set_setting(
        "attendance_record_time",
        "true" if form.get("attendance_record_time") == "on" else "false",
        school_id, "attendance", "تسجيل وقت الحضور",
    )
    set_setting(
        "attendance_auto_suggest",
        "true" if form.get("attendance_auto_suggest") == "on" else "false",
        school_id, "attendance", "اقتراح الحالة تلقائياً",
    )
    for key in ("attendance_session_start", "attendance_on_time_until",
                "attendance_late_until", "attendance_absent_after"):
        val = (form.get(key) or "").strip()
        if val:
            set_setting(key, val, school_id, "attendance", key)
