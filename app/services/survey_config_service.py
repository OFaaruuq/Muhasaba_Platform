"""Dynamic survey configuration — all labels and field maps from DB."""

import json

from app.extensions import db
from app.models import ConfigOption
from app.services.config_service import get_setting, set_setting, get_config_choices, get_config_map, get_ui_label
from app.services.content_seeds import (
    SURVEY_FREQUENCY_SEED,
    SURVEY_WEEKLY_MEETINGS_SEED,
    EDUCATION_STAGE_SEED,
    ARABIC_MONTHS_SEED,
    FAMILY_SURVEY_FIELDS_SEED,
    FAMILY_FIELD_SECTION_DEFAULTS,
    TEACHER_SURVEY_FIELDS_SEED,
    PROGRAM_SURVEY_SECTIONS_SEED,
    dumps_json,
)


def _load_json_setting(key, school_id=None):
    raw = get_setting(key, school_id)
    if not raw:
        return None
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def ensure_survey_config(school_id=None):
    """Seed survey-related ConfigOption rows and JSON settings."""
    option_seeds = {
        "survey_frequency": SURVEY_FREQUENCY_SEED,
        "survey_weekly_meetings": SURVEY_WEEKLY_MEETINGS_SEED,
        "education_stage": EDUCATION_STAGE_SEED,
        "arabic_month": ARABIC_MONTHS_SEED,
    }
    for option_type, options in option_seeds.items():
        for i, (code, name_ar) in enumerate(options):
            exists = ConfigOption.query.filter_by(
                school_id=school_id, option_type=option_type, code=code,
            ).first()
            if not exists:
                db.session.add(ConfigOption(
                    school_id=school_id, option_type=option_type,
                    code=code, name_ar=name_ar, order=i,
                ))

    json_seeds = {
        "family_survey_fields_json": FAMILY_SURVEY_FIELDS_SEED,
        "teacher_survey_fields_json": TEACHER_SURVEY_FIELDS_SEED,
        "program_survey_sections_json": PROGRAM_SURVEY_SECTIONS_SEED,
    }
    for key, value in json_seeds.items():
        if not get_setting(key, school_id):
            set_setting(key, dumps_json(value), school_id=school_id, category="surveys", label_ar=key)

    _patch_family_survey_sections(school_id)

    db.session.commit()


def _patch_family_survey_sections(school_id=None):
    """Add section keys to legacy family_survey_fields_json rows."""
    raw = get_setting("family_survey_fields_json", school_id)
    if not raw:
        return
    data = json.loads(raw) if isinstance(raw, str) else raw
    changed = False
    for item in data:
        if item.get("section"):
            continue
        fields = item.get("fields", "")
        first = str(fields).split(",")[0].strip()
        section = FAMILY_FIELD_SECTION_DEFAULTS.get(first)
        if section:
            item["section"] = section
            changed = True
    if changed:
        set_setting(
            "family_survey_fields_json", dumps_json(data),
            school_id=school_id, category="surveys", label_ar="family_survey_fields_json",
        )


def get_frequency_choices(school_id=None):
    return get_config_choices("survey_frequency", school_id)


def get_frequency_label(code, school_id=None):
    return get_config_map("survey_frequency", school_id).get(code, code or "—")


def get_weekly_meetings_choices(school_id=None):
    return get_config_choices("survey_weekly_meetings", school_id)


def get_weekly_meetings_label(code, school_id=None):
    return get_config_map("survey_weekly_meetings", school_id).get(code, code or "—")


def get_education_stage_choices(school_id=None):
    return get_config_choices("education_stage", school_id)


def get_education_stage_map(school_id=None):
    return get_config_map("education_stage", school_id)


def get_education_stage_field_map(school_id=None):
    """Map DB boolean field names to display labels."""
    stages = get_education_stage_choices(school_id)
    field_names = ("stage_primary", "stage_middle", "stage_secondary")
    return {
        field_names[i]: label
        for i, (_code, label) in enumerate(stages[: len(field_names)])
    }


def get_arabic_months_map(school_id=None):
    result = {}
    for code, name_ar in get_config_choices("arabic_month", school_id):
        try:
            result[int(code)] = name_ar
        except (TypeError, ValueError):
            continue
    return result


def get_arabic_month_name(month, school_id=None):
    return get_arabic_months_map(school_id).get(month, str(month))


def get_survey_field_map(kind, school_id=None):
    """Return list of (fields, label) tuples for family or teacher surveys."""
    key = f"{kind}_survey_fields_json"
    data = _load_json_setting(key, school_id) or []
    return [(item["fields"], item["label"]) for item in data]


def get_survey_field_label_dict(kind, school_id=None):
    """Map field name(s) -> label for dynamic templates."""
    result = {}
    for fields, label in get_survey_field_map(kind, school_id):
        for name in str(fields).split(","):
            name = name.strip()
            if name:
                result[name] = label
    return result


TEACHER_RATING_FIELD_NAMES = frozenset({
    "attendance_punctuality",
    "lesson_preparation",
    "student_punctuality",
    "student_comprehension",
    "family_role_rating",
})

FAMILY_YES_NO_FIELDS = frozenset({
    "has_regular_family_meeting",
    "received_curriculum_book",
    "read_curriculum_book",
    "studied_curriculum_at_home",
    "hadith_at_home",
    "fiqh_at_home",
    "listens_riyadh_saliheen",
    "received_approved_films",
    "watches_approved_only",
    "outdoor_entertainment",
})

FAMILY_TEXTAREA_FIELDS = frozenset({
    "family_meeting_notes",
    "curriculum_notes",
    "curricula_obstacles",
})


def _family_field_type(fields_str, explicit_type=None):
    if explicit_type:
        return explicit_type
    names = [n.strip() for n in str(fields_str).split(",") if n.strip()]
    if len(names) > 1 and all(n.startswith("stage_") for n in names):
        return "stages"
    name = names[0] if names else ""
    if name in FAMILY_YES_NO_FIELDS:
        return "yes_no"
    if name == "weekly_meetings_count":
        return "radio"
    if name in FAMILY_TEXTAREA_FIELDS:
        return "textarea"
    return "text"


def _family_field_section(item):
    if item.get("section"):
        return item["section"]
    first = str(item.get("fields", "")).split(",")[0].strip()
    return FAMILY_FIELD_SECTION_DEFAULTS.get(first, "data")


def get_family_survey_render_fields(school_id=None):
    """Family survey fields with render metadata for dynamic forms."""
    data = _load_json_setting("family_survey_fields_json", school_id) or []
    rows = []
    for item in data:
        fields = item.get("fields", "")
        names = [n.strip() for n in str(fields).split(",") if n.strip()]
        rows.append({
            "fields": fields,
            "names": names,
            "name": names[0] if len(names) == 1 else fields,
            "label": item.get("label", ""),
            "section": _family_field_section(item),
            "type": _family_field_type(fields, item.get("type")),
        })
    return rows


def get_family_survey_sections_render(school_id=None):
    """Group family fields by section with titles from page_labels."""
    from app.services.config_service import get_page_label

    sections = []
    current_code = None
    for field in get_family_survey_render_fields(school_id):
        if field["section"] != current_code:
            current_code = field["section"]
            title_key = f"family_section_{current_code}"
            sections.append({
                "code": current_code,
                "title": get_page_label(title_key, school_id, current_code),
                "fields": [],
            })
        sections[-1]["fields"].append(field)
    return sections


def get_teacher_survey_render_fields(school_id=None):
    """Teacher survey fields with render type for dynamic forms."""
    rows = []
    data = _load_json_setting("teacher_survey_fields_json", school_id) or []
    for item in data:
        fields = item.get("fields", "")
        label = item.get("label", "")
        explicit = item.get("type")
        inferred = "rating" if fields in TEACHER_RATING_FIELD_NAMES else "text"
        rows.append({
            "name": fields,
            "label": label,
            "type": explicit if explicit and explicit != "auto" else inferred,
        })
    return rows


def count_survey_questions(kind, school_id=None):
    """Count scorable questions from JSON field definitions."""
    if kind == "teacher":
        return len(get_survey_field_map("teacher", school_id))
    if kind == "family":
        labels = get_survey_field_label_dict("family", school_id)
        countable = {
            "family_name", "stage_primary", "weekly_meetings_count",
            "has_regular_family_meeting", "received_curriculum_book", "read_curriculum_book",
            "studied_curriculum_at_home", "hadith_at_home", "fiqh_at_home",
            "listens_riyadh_saliheen", "received_approved_films", "watches_approved_only",
            "outdoor_entertainment", "weekly_meetings_one_reason", "weekly_meetings_other",
            "family_meeting_notes", "curriculum_notes", "curricula_obstacles", "riyadh_progress",
        }
        return sum(1 for key in countable if key in labels or key.startswith("stage_"))
    return 0


def get_program_survey_sections(school_id=None):
    """Return program survey sections as (code, title, subtitle, fields) tuples."""
    data = _load_json_setting("program_survey_sections_json", school_id) or []
    sections = []
    for section in data:
        fields = [(f[0], f[1]) for f in section.get("fields", [])]
        sections.append((
            section.get("code", ""),
            section.get("title", ""),
            section.get("subtitle"),
            fields,
        ))
    return sections


def get_program_survey_field_map(school_id=None):
    return [
        (field, label)
        for _code, _title, _subtitle, fields in get_program_survey_sections(school_id)
        for field, label in fields
    ]


def get_survey_bool_label(value, school_id=None):
    if value is True:
        return get_ui_label("yes", school_id)
    if value is False:
        return get_ui_label("no", school_id)
    return "—"


def get_survey_status_label(answered, total, school_id=None):
    if answered == 0:
        return get_ui_label("survey_not_filled", school_id), "secondary"
    if answered >= total:
        return get_ui_label("complete", school_id), "success"
    partial_tpl = get_ui_label("survey_partial", school_id, "جزئي ({answered}/{total})")
    return partial_tpl.format(answered=answered, total=total), "warning"


def get_survey_status_pills(school_id=None):
    return [
        ("complete", get_ui_label("complete", school_id), "bi-check-circle"),
        ("partial", get_ui_label("partial", school_id), "bi-exclamation-circle"),
        ("empty", get_ui_label("survey_not_filled", school_id), "bi-dash-circle"),
    ]


FAMILY_SECTION_CODES = (
    "data", "meeting", "curriculum", "child_curricula", "riyadh", "entertainment",
)

SURVEY_FIELD_TYPES = (
    ("auto", "تلقائي"),
    ("text", "نص قصير"),
    ("textarea", "نص طويل"),
    ("yes_no", "نعم / لا"),
    ("radio", "اختيار واحد"),
    ("stages", "مراحل دراسية"),
    ("rating", "تقييم ترددي"),
)


def admin_family_survey_rows(school_id=None):
    """Rows for admin structured editor."""
    return [
        {
            "fields": item["fields"],
            "label": item["label"],
            "section": item.get("section") or _family_field_section(item),
            "type": item.get("type") or "auto",
        }
        for item in (_load_json_setting("family_survey_fields_json", school_id) or [])
    ]


def admin_teacher_survey_rows(school_id=None):
    return [
        {
            "fields": item["fields"],
            "label": item["label"],
            "type": item.get("type") or "auto",
        }
        for item in (_load_json_setting("teacher_survey_fields_json", school_id) or [])
    ]


def admin_program_survey_rows(school_id=None):
    """Flatten program sections for admin label editor."""
    rows = []
    data = _load_json_setting("program_survey_sections_json", school_id) or []
    for si, section in enumerate(data):
        rows.append({
            "kind": "section",
            "index": si,
            "code": section.get("code", ""),
            "title": section.get("title", ""),
            "subtitle": section.get("subtitle") or "",
        })
        for fi, field in enumerate(section.get("fields", [])):
            rows.append({
                "kind": "field",
                "section_index": si,
                "field_index": fi,
                "code": field[0] if field else "",
                "label": field[1] if len(field) > 1 else "",
            })
    return rows, data


def save_family_survey_fields_admin(form_rows, school_id=None):
    """Persist family survey JSON from admin form rows."""
    rows = []
    for row in form_rows:
        fields = (row.get("fields") or "").strip()
        label = (row.get("label") or "").strip()
        section = (row.get("section") or "data").strip()
        field_type = (row.get("type") or "").strip()
        if fields and label:
            item = {"fields": fields, "label": label, "section": section}
            if field_type and field_type != "auto":
                item["type"] = field_type
            rows.append(item)
    set_setting(
        "family_survey_fields_json", dumps_json(rows),
        school_id=school_id, category="surveys", label_ar="حقول استبيان الأسرة",
    )
    return rows


def save_teacher_survey_fields_admin(form_rows, school_id=None):
    rows = []
    for row in form_rows:
        fields = (row.get("fields") or "").strip()
        label = (row.get("label") or "").strip()
        if fields and label:
            item = {"fields": fields, "label": label}
            field_type = (row.get("type") or "").strip()
            if field_type and field_type != "auto":
                item["type"] = field_type
            rows.append(item)
    set_setting(
        "teacher_survey_fields_json", dumps_json(rows),
        school_id=school_id, category="surveys", label_ar="حقول استبيان المعلم",
    )
    return rows


def save_program_survey_sections_admin(sections_data, school_id=None):
    set_setting(
        "program_survey_sections_json", dumps_json(sections_data),
        school_id=school_id, category="surveys", label_ar="أقسام استبيان البرنامج",
    )
    return sections_data


def parse_family_survey_admin_form(form):
    count = form.get("family_count", type=int) or 0
    rows = []
    for i in range(count):
        rows.append({
            "fields": form.get(f"family_fields_{i}", ""),
            "label": form.get(f"family_label_{i}", ""),
            "section": form.get(f"family_section_{i}", "data"),
            "type": form.get(f"family_type_{i}", "auto"),
        })
    new_fields = form.get("family_new_fields", "").strip()
    new_label = form.get("family_new_label", "").strip()
    new_section = form.get("family_new_section", "data")
    new_type = form.get("family_new_type", "auto")
    if new_fields and new_label:
        rows.append({
            "fields": new_fields, "label": new_label,
            "section": new_section, "type": new_type,
        })
    return rows


def parse_teacher_survey_admin_form(form):
    count = form.get("teacher_count", type=int) or 0
    rows = []
    for i in range(count):
        rows.append({
            "fields": form.get(f"teacher_fields_{i}", ""),
            "label": form.get(f"teacher_label_{i}", ""),
            "type": form.get(f"teacher_type_{i}", "auto"),
        })
    new_fields = form.get("teacher_new_fields", "").strip()
    new_label = form.get("teacher_new_label", "").strip()
    new_type = form.get("teacher_new_type", "auto")
    if new_fields and new_label:
        rows.append({
            "fields": new_fields, "label": new_label, "type": new_type,
        })
    return rows


def parse_program_survey_admin_form(form, existing_sections):
    """Update titles/labels from form; structure unchanged."""
    sections = []
    for si, section in enumerate(existing_sections):
        title = form.get(f"prog_title_{si}", section.get("title", ""))
        subtitle = form.get(f"prog_subtitle_{si}", section.get("subtitle") or "")
        fields = []
        for fi, field in enumerate(section.get("fields", [])):
            code = field[0]
            label = form.get(f"prog_field_{si}_{fi}", field[1] if len(field) > 1 else "")
            fields.append([code, label])
        sections.append({
            "code": section.get("code", ""),
            "title": title,
            "subtitle": subtitle or None,
            "fields": fields,
        })
    return sections
