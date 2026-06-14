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

    db.session.commit()


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
