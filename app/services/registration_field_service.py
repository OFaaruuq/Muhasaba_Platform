"""Dynamic student registration form fields — visible/required per school."""

import json

from app.models import School
from app.services.config_service import (
    get_setting, set_setting, get_registration_section_labels,
    get_registration_field_definitions,
)

SETTING_KEY = "student_registration_fields"

FIELD_DEFINITIONS = [
    {"key": "full_name_ar", "label": "الاسم بالعربية", "section": "personal", "input": "text"},
    {"key": "full_name", "label": "الاسم بالإنجليزية", "section": "personal", "input": "text"},
    {"key": "student_id", "label": "رقم الطالب", "section": "personal", "input": "text",
     "placeholder": "يُولّد تلقائياً إن تُرك فارغاً"},
    {"key": "gender", "label": "الجنس", "section": "personal", "input": "gender"},
    {"key": "date_of_birth", "label": "تاريخ الميلاد", "section": "personal", "input": "date"},
    {"key": "enrollment_date", "label": "تاريخ التسجيل", "section": "personal", "input": "date"},
    {"key": "phone", "label": "الهاتف", "section": "personal", "input": "text", "placeholder": "+252-..."},
    {"key": "region", "label": "المنطقة / المدينة", "section": "location", "input": "text"},
    {"key": "district", "label": "الحي / المقاطعة", "section": "location", "input": "text"},
    {"key": "address", "label": "العنوان التفصيلي", "section": "location", "input": "textarea"},
    {"key": "responsible_teacher_id", "label": "المسؤول (Mas'uulka)", "section": "academic", "input": "teacher"},
    {"key": "create_account", "label": "إنشاء حساب للطالب", "section": "account", "input": "account"},
]

ACADEMIC_CORE_KEYS = frozenset({"school_id", "grade_id", "class_id"})

PRESET_CONCISE = {
    "full_name_ar": {"visible": True, "required": True},
    "gender": {"visible": True, "required": True},
    "responsible_teacher_id": {"visible": True, "required": False},
    "full_name": {"visible": False, "required": False},
    "student_id": {"visible": False, "required": False},
    "date_of_birth": {"visible": False, "required": False},
    "enrollment_date": {"visible": False, "required": False},
    "phone": {"visible": False, "required": False},
    "region": {"visible": False, "required": False},
    "district": {"visible": False, "required": False},
    "address": {"visible": False, "required": False},
    "create_account": {"visible": False, "required": False},
}

PRESET_FULL = {
    "full_name_ar": {"visible": True, "required": True},
    "full_name": {"visible": True, "required": False},
    "student_id": {"visible": True, "required": False},
    "gender": {"visible": True, "required": True},
    "date_of_birth": {"visible": True, "required": False},
    "enrollment_date": {"visible": True, "required": False},
    "phone": {"visible": True, "required": False},
    "region": {"visible": True, "required": True},
    "district": {"visible": True, "required": True},
    "address": {"visible": True, "required": True},
    "responsible_teacher_id": {"visible": True, "required": False},
    "create_account": {"visible": True, "required": False},
}

PRESETS = {
    "concise": PRESET_CONCISE,
    "full": PRESET_FULL,
}


def _default_config():
    return {"mode": "concise", "fields": dict(PRESET_CONCISE)}


def _load_raw_config(school_id=None):
    raw = get_setting(SETTING_KEY, school_id)
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None


def get_registration_config(school_id=None):
    """Return merged field config: mode + resolved field list with visible/required."""
    stored = _load_raw_config(school_id) or _default_config()
    mode = stored.get("mode", "concise")
    fields_map = stored.get("fields") or {}

    if mode in PRESETS and not fields_map:
        fields_map = dict(PRESETS[mode])
    elif mode in PRESETS:
        base = dict(PRESETS[mode])
        base.update(fields_map)
        fields_map = base

    resolved = []
    field_defs = get_registration_field_definitions(school_id)
    for defn in field_defs:
        key = defn["key"]
        state = fields_map.get(key, {"visible": False, "required": False})
        resolved.append({
            **defn,
            "visible": bool(state.get("visible")),
            "required": bool(state.get("required")),
        })

    visible_sections = {f["section"] for f in resolved if f["visible"]}
    return {
        "mode": mode,
        "fields": resolved,
        "fields_map": {f["key"]: f for f in resolved},
        "visible_sections": visible_sections,
        "section_labels": get_registration_section_labels(school_id),
        "is_concise": mode == "concise",
    }


def save_registration_config(school_id, mode, fields_form):
    """
    Persist registration field config.
    fields_form: dict key -> {visible: bool, required: bool}
    """
    fields = {}
    field_defs = get_registration_field_definitions(school_id)
    for defn in field_defs:
        key = defn["key"]
        if key in fields_form:
            fields[key] = {
                "visible": bool(fields_form[key].get("visible")),
                "required": bool(fields_form[key].get("required")),
            }
        elif mode in PRESETS:
            fields[key] = dict(PRESETS[mode].get(key, {"visible": False, "required": False}))

    payload = {"mode": mode, "fields": fields}
    set_setting(
        SETTING_KEY,
        json.dumps(payload, ensure_ascii=False),
        school_id,
        "registration",
        "حقول تسجيل الطلاب",
    )
    return payload


def apply_preset(mode):
    if mode not in PRESETS:
        mode = "concise"
    return {"mode": mode, "fields": dict(PRESETS[mode])}


def _school_defaults(school_id):
    school = School.query.get(school_id)
    if not school:
        return {"region": "—", "district": "—", "address": "—"}
    return {
        "region": (school.region or "—").strip() or "—",
        "district": (school.district or "—").strip() or "—",
        "address": (school.address or "—").strip() or "—",
    }


def validate_registration_fields(form, school_id=None):
    """Validate POST data against dynamic field config. Returns list of error strings."""
    config = get_registration_config(school_id)
    fields_map = config["fields_map"]
    errors = []

    if not form.get("full_name_ar", "").strip():
        errors.append("حقل الاسم بالعربية مطلوب.")

    for core_key, label in (
        ("school_id", "المدرسة"),
        ("grade_id", "المستوى الدراسي"),
        ("class_id", "الفصل"),
    ):
        if not str(form.get(core_key, "")).strip():
            errors.append(f"حقل {label} مطلوب.")

    for field in config["fields"]:
        if field["key"] == "full_name_ar":
            continue
        if not field["visible"] or not field["required"]:
            continue
        if field["key"] == "create_account":
            continue
        value = form.get(field["key"], "")
        if isinstance(value, str) and not value.strip():
            errors.append(f"حقل {field['label']} مطلوب.")

    if fields_map.get("create_account", {}).get("visible") and form.get("create_account") == "on":
        if fields_map.get("create_account", {}).get("required"):
            if not form.get("username", "").strip():
                errors.append("اسم المستخدم مطلوب لإنشاء حساب.")
            if not form.get("password", "").strip():
                errors.append("كلمة المرور مطلوبة لإنشاء حساب.")
        else:
            if form.get("username", "").strip() and not form.get("password", "").strip():
                errors.append("كلمة المرور مطلوبة عند إدخال اسم مستخدم.")

    return errors


def _form_str(form, key, default=""):
    val = form.get(key, default)
    return val.strip() if isinstance(val, str) else (val if val is not None else default)


def _form_int(form, key):
    val = form.get(key)
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def extract_registration_values(form, school_id):
    """Build student field values, applying school defaults for hidden location fields."""
    config = get_registration_config(school_id)
    fields_map = config["fields_map"]
    defaults = _school_defaults(school_id)

    def _visible(key):
        return fields_map.get(key, {}).get("visible", False)

    def _get(key, fallback=""):
        if _visible(key):
            return _form_str(form, key, fallback)
        return fallback

    return {
        "full_name_ar": _get("full_name_ar") or _form_str(form, "full_name_ar"),
        "full_name": _get("full_name") or _get("full_name_ar") or _form_str(form, "full_name_ar"),
        "gender": _get("gender") or None,
        "date_of_birth": _get("date_of_birth") or None,
        "enrollment_date": _get("enrollment_date") or None,
        "phone": _get("phone") or None,
        "region": _get("region") or defaults["region"],
        "district": _get("district") or defaults["district"],
        "address": _get("address") or defaults["address"],
        "responsible_teacher_id": _form_int(form, "responsible_teacher_id") if _visible("responsible_teacher_id") else None,
        "create_account": _visible("create_account") and form.get("create_account") == "on",
        "username": _form_str(form, "username") if _visible("create_account") else "",
        "password": _form_str(form, "password") if _visible("create_account") else "",
        "email": _form_str(form, "email") if _visible("create_account") else "",
        "student_id": _get("student_id") or "",
    }


def admin_field_rows(school_id=None):
    """Field definitions with current visible/required for admin UI."""
    config = get_registration_config(school_id)
    return config["fields"], config["mode"]
