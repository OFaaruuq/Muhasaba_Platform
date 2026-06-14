"""Business logic for educational program follow-up reports (متابعة البرنامج التربوي)."""

from app.extensions import db
from app.models import (
    EducationalProgramFollowupSurvey,
    StudentEducationalProgramFollowupSurvey,
    Teacher,
    Student,
)
from app.services.survey_config_service import (
    get_program_survey_sections,
    get_program_survey_field_map,
    get_survey_bool_label,
    get_survey_status_label,
)

PROGRAM_TEXT_FIELDS = ("latecomers_notes",)


def program_survey_sections(school_id=None):
    return get_program_survey_sections(school_id)


def program_survey_field_map(school_id=None):
    return get_program_survey_field_map(school_id)


def program_bool_fields(school_id=None):
    return tuple(field for field, _label in program_survey_field_map(school_id))


def program_total_questions(school_id=None):
    return len(program_bool_fields(school_id)) + len(PROGRAM_TEXT_FIELDS)


def parse_bool(value):
    if value is None or value == "":
        return None
    return str(value).lower() in ("1", "true", "yes", "on")


def bool_label(value, school_id=None):
    return get_survey_bool_label(value, school_id)


def _text_answered(value):
    return bool(value and str(value).strip())


def program_survey_progress(survey, school_id=None):
    sid = school_id or (survey.school_id if survey else None)
    total = program_total_questions(sid)
    if not survey:
        return 0, total
    answered = 0
    for field in program_bool_fields(sid):
        if getattr(survey, field) is not None:
            answered += 1
    if _text_answered(survey.latecomers_notes):
        answered += 1
    return answered, total


def survey_status_label(answered, total, school_id=None):
    return get_survey_status_label(answered, total, school_id)


def _apply_program_form(survey, school_id, form):
    for field in program_bool_fields(school_id):
        setattr(survey, field, parse_bool(form.get(field)))
    survey.latecomers_notes = (form.get("latecomers_notes") or "").strip()


def get_or_create_program_survey(teacher, year, month, entered_by_id):
    survey = EducationalProgramFollowupSurvey.query.filter_by(
        teacher_id=teacher.id,
        period_year=year,
        period_month=month,
    ).first()
    if not survey:
        survey = EducationalProgramFollowupSurvey(
            school_id=teacher.school_id,
            teacher_id=teacher.id,
            entered_by_id=entered_by_id,
            period_year=year,
            period_month=month,
        )
        db.session.add(survey)
        db.session.flush()
    return survey


def save_program_survey(teacher, year, month, entered_by_id, form):
    survey = get_or_create_program_survey(teacher, year, month, entered_by_id)
    _apply_program_form(survey, teacher.school_id, form)
    survey.entered_by_id = entered_by_id
    db.session.commit()
    return survey


def get_or_create_student_program_survey(student, year, month, entered_by_id):
    survey = StudentEducationalProgramFollowupSurvey.query.filter_by(
        student_id=student.id,
        period_year=year,
        period_month=month,
    ).first()
    if not survey:
        survey = StudentEducationalProgramFollowupSurvey(
            school_id=student.school_id,
            student_id=student.id,
            entered_by_id=entered_by_id,
            period_year=year,
            period_month=month,
        )
        db.session.add(survey)
        db.session.flush()
    return survey


def save_student_program_survey(student, year, month, entered_by_id, form):
    survey = get_or_create_student_program_survey(student, year, month, entered_by_id)
    _apply_program_form(survey, student.school_id, form)
    survey.entered_by_id = entered_by_id
    db.session.commit()
    return survey


def program_survey_status(school_id, year, month, teacher_ids):
    if not teacher_ids:
        return _empty_status_counts()
    surveys = EducationalProgramFollowupSurvey.query.filter(
        EducationalProgramFollowupSurvey.school_id == school_id,
        EducationalProgramFollowupSurvey.teacher_id.in_(teacher_ids),
        EducationalProgramFollowupSurvey.period_year == year,
        EducationalProgramFollowupSurvey.period_month == month,
    ).all()
    survey_map = {s.teacher_id: s for s in surveys}
    return _count_survey_states(teacher_ids, survey_map, program_survey_progress)


def student_program_survey_status(school_id, year, month, student_ids):
    if not student_ids:
        return _empty_status_counts()
    surveys = StudentEducationalProgramFollowupSurvey.query.filter(
        StudentEducationalProgramFollowupSurvey.school_id == school_id,
        StudentEducationalProgramFollowupSurvey.student_id.in_(student_ids),
        StudentEducationalProgramFollowupSurvey.period_year == year,
        StudentEducationalProgramFollowupSurvey.period_month == month,
    ).all()
    survey_map = {s.student_id: s for s in surveys}
    return _count_survey_states(student_ids, survey_map, program_survey_progress)


def _empty_status_counts():
    return {
        "total": 0,
        "done": 0,
        "pending": 0,
        "complete": 0,
        "partial": 0,
        "not_started": 0,
    }


def _count_survey_states(entity_ids, survey_map, progress_fn):
    total = len(entity_ids)
    complete = partial = 0
    for entity_id in entity_ids:
        survey = survey_map.get(entity_id)
        if not survey:
            continue
        answered, total_q = progress_fn(survey)
        if answered >= total_q:
            complete += 1
        elif answered > 0:
            partial += 1
    not_started = total - complete - partial
    return {
        "total": total,
        "complete": complete,
        "partial": partial,
        "not_started": not_started,
        "done": complete,
        "pending": total - complete,
    }


def completion_percent(status):
    if not status or not status.get("total"):
        return 0
    return int(round(status["complete"] * 100 / status["total"]))


def _field_answered(survey, field, school_id=None):
    if not survey:
        return False
    sid = school_id or survey.school_id
    if field in program_bool_fields(sid):
        return getattr(survey, field) is not None
    return _text_answered(getattr(survey, field))


def program_survey_checklist(survey, school_id=None):
    sid = school_id or (survey.school_id if survey else None)
    items = []
    for _code, title, subtitle, fields in program_survey_sections(sid):
        for field, label in fields:
            items.append({
                "section": title,
                "label": label,
                "answered": _field_answered(survey, field, sid),
            })
    latecomers_title = next(
        (title for code, title, _sub, _fields in program_survey_sections(sid) if code == "latecomers"),
        "التعامل مع المتأخرين",
    )
    items.append({
        "section": latecomers_title,
        "label": "ملاحظات إضافية حول التعامل مع المتأخرين",
        "answered": _field_answered(survey, "latecomers_notes", sid),
    })
    return items


def program_index_rows(teachers, program_surveys, year, month):
    rows = []
    for teacher in teachers:
        survey = program_surveys.get(teacher.id)
        answered, total = program_survey_progress(survey, teacher.school_id)
        status_text, status_class = survey_status_label(answered, total, teacher.school_id)
        rows.append({
            "teacher": teacher,
            "survey": survey,
            "answered": answered,
            "total": total,
            "status_text": status_text,
            "status_class": status_class,
            "percent": int(round(answered * 100 / total)) if total else 0,
        })
    return rows


def student_program_index_rows(students, program_surveys, year, month):
    rows = []
    for student in students:
        survey = program_surveys.get(student.id)
        answered, total = program_survey_progress(survey, student.school_id)
        status_text, status_class = survey_status_label(answered, total, student.school_id)
        rows.append({
            "student": student,
            "survey": survey,
            "answered": answered,
            "total": total,
            "status_text": status_text,
            "status_class": status_class,
            "percent": int(round(answered * 100 / total)) if total else 0,
        })
    return rows


def student_program_entries_for_students(students, year, month):
    """Build template context for each student's program survey on the teacher hub."""
    entries = []
    for student in students:
        survey = StudentEducationalProgramFollowupSurvey.query.filter_by(
            student_id=student.id, period_year=year, period_month=month,
        ).first()
        answered, total = program_survey_progress(survey, student.school_id)
        status_text, status_class = survey_status_label(answered, total, student.school_id)
        entries.append({
            "student": student,
            "survey": survey,
            "answered": answered,
            "total": total,
            "status_text": status_text,
            "status_class": status_class,
            "checklist": program_survey_checklist(survey, student.school_id),
        })
    return entries


def can_fill_program_surveys(user):
    from app.utils.permissions import user_has_permission
    if not user.is_authenticated:
        return False
    return user_has_permission(user, "manage_followup_surveys")


def can_fill_student_program_surveys(user):
    return can_fill_program_surveys(user)


def verify_all_fields_stored(school_id=None):
    cols = {c.name for c in EducationalProgramFollowupSurvey.__table__.columns}
    missing = []
    fields = program_bool_fields(school_id) + PROGRAM_TEXT_FIELDS
    for field in fields:
        if field not in cols:
            missing.append(field)
    student_cols = {c.name for c in StudentEducationalProgramFollowupSurvey.__table__.columns}
    for field in fields:
        if field not in student_cols:
            missing.append(f"student.{field}")
    return {
        "ok": len(missing) == 0,
        "missing": missing,
        "questions": program_total_questions(school_id),
        "sections": len(program_survey_sections(school_id)),
    }
