"""Business logic for family and teacher follow-up surveys."""

from sqlalchemy import or_

from app.extensions import db
from app.models import FamilyFollowupSurvey, TeacherMonthlySurvey, Student, Parent, Teacher
from app.services.teacher_student_service import students_for_teacher
from app.services.survey_config_service import (
    get_frequency_choices,
    get_frequency_label,
    get_weekly_meetings_choices,
    get_weekly_meetings_label,
    get_survey_field_map,
    get_arabic_months_map,
    get_arabic_month_name,
    get_survey_status_label,
    get_survey_bool_label,
)


def frequency_choices(school_id=None):
    return get_frequency_choices(school_id)


def frequency_label(code, school_id=None):
    return get_frequency_label(code, school_id)


def weekly_meetings_choices(school_id=None):
    return get_weekly_meetings_choices(school_id)


def weekly_meetings_label(code, school_id=None):
    return get_weekly_meetings_label(code, school_id)


def bool_label(value, school_id=None):
    return get_survey_bool_label(value, school_id)


def survey_status_label(answered, total, school_id=None):
    return get_survey_status_label(answered, total, school_id)


def family_survey_field_map(school_id=None):
    return get_survey_field_map("family", school_id)


def teacher_survey_field_map(school_id=None):
    return get_survey_field_map("teacher", school_id)


def arabic_months(school_id=None):
    return get_arabic_months_map(school_id)


def parse_bool(value):
    if value is None or value == "":
        return None
    return str(value).lower() in ("1", "true", "yes", "on")



FAMILY_BOOL_FIELDS = (
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
)

FAMILY_TOTAL_QUESTIONS = (
    1  # family_name
    + 1  # education stages
    + 1  # weekly_meetings_count
    + len(FAMILY_BOOL_FIELDS)
    + 6  # text fields: one_reason, other, meeting_notes, curriculum_notes, obstacles, riyadh_progress
)

TEACHER_RATING_FIELDS = (
    "attendance_punctuality",
    "lesson_preparation",
    "student_punctuality",
    "student_comprehension",
    "family_role_rating",
)

TEACHER_TEXT_FIELDS = (
    "main_obstacles",
    "student_preparation_percentage",
    "student_notes",
    "family_role_message",
    "session_suggestions",
)

TEACHER_TOTAL_QUESTIONS = len(TEACHER_RATING_FIELDS) + len(TEACHER_TEXT_FIELDS)


def _text_answered(value):
    return bool(value and str(value).strip())


def family_survey_progress(survey):
    """Return (answered_count, total_questions) for a family survey."""
    if not survey:
        return 0, FAMILY_TOTAL_QUESTIONS

    answered = 0
    if _text_answered(survey.family_name):
        answered += 1
    if survey.stage_primary or survey.stage_middle or survey.stage_secondary:
        answered += 1
    if survey.weekly_meetings_count:
        answered += 1
    for field in FAMILY_BOOL_FIELDS:
        if getattr(survey, field) is not None:
            answered += 1
    for field in (
        "weekly_meetings_one_reason",
        "weekly_meetings_other",
        "family_meeting_notes",
        "curriculum_notes",
        "curricula_obstacles",
        "riyadh_progress",
    ):
        if _text_answered(getattr(survey, field)):
            answered += 1
    return answered, FAMILY_TOTAL_QUESTIONS


def teacher_survey_progress(survey):
    """Return (answered_count, total_questions) for a teacher survey."""
    if not survey:
        return 0, TEACHER_TOTAL_QUESTIONS

    answered = 0
    for field in TEACHER_RATING_FIELDS:
        if getattr(survey, field):
            answered += 1
    for field in TEACHER_TEXT_FIELDS:
        if _text_answered(getattr(survey, field)):
            answered += 1
    return answered, TEACHER_TOTAL_QUESTIONS


def get_or_create_family_survey(student, year, month, entered_by_id):
    survey = FamilyFollowupSurvey.query.filter_by(
        school_id=student.school_id,
        student_id=student.id,
        period_year=year,
        period_month=month,
    ).first()
    if not survey:
        parent = student.parents[0] if student.parents else None
        family_name = ""
        if parent:
            family_name = parent.full_name_ar or parent.full_name
        if not family_name:
            family_name = student.full_name_ar or student.full_name
        survey = FamilyFollowupSurvey(
            school_id=student.school_id,
            student_id=student.id,
            parent_id=parent.id if parent else None,
            entered_by_id=entered_by_id,
            period_year=year,
            period_month=month,
            family_name=family_name,
        )
        db.session.add(survey)
        db.session.flush()
    return survey


def default_family_name(student):
    parent = student.parents[0] if student.parents else None
    if parent:
        return parent.full_name_ar or parent.full_name
    return student.full_name_ar or student.full_name


def save_family_survey(student, year, month, entered_by_id, form):
    survey = get_or_create_family_survey(student, year, month, entered_by_id)

    family_name = (form.get("family_name") or "").strip()
    survey.family_name = family_name or default_family_name(student)
    survey.stage_primary = "stage_primary" in form
    survey.stage_middle = "stage_middle" in form
    survey.stage_secondary = "stage_secondary" in form

    survey.has_regular_family_meeting = parse_bool(form.get("has_regular_family_meeting"))
    survey.weekly_meetings_count = form.get("weekly_meetings_count") or None
    survey.weekly_meetings_one_reason = (form.get("weekly_meetings_one_reason") or "").strip()
    survey.weekly_meetings_other = (form.get("weekly_meetings_other") or "").strip()
    survey.family_meeting_notes = (form.get("family_meeting_notes") or "").strip()

    survey.received_curriculum_book = parse_bool(form.get("received_curriculum_book"))
    survey.read_curriculum_book = parse_bool(form.get("read_curriculum_book"))
    survey.studied_curriculum_at_home = parse_bool(form.get("studied_curriculum_at_home"))
    survey.curriculum_notes = (form.get("curriculum_notes") or "").strip()

    survey.hadith_at_home = parse_bool(form.get("hadith_at_home"))
    survey.fiqh_at_home = parse_bool(form.get("fiqh_at_home"))
    survey.curricula_obstacles = (form.get("curricula_obstacles") or "").strip()

    survey.listens_riyadh_saliheen = parse_bool(form.get("listens_riyadh_saliheen"))
    survey.riyadh_progress = (form.get("riyadh_progress") or "").strip()

    survey.received_approved_films = parse_bool(form.get("received_approved_films"))
    survey.watches_approved_only = parse_bool(form.get("watches_approved_only"))
    survey.outdoor_entertainment = parse_bool(form.get("outdoor_entertainment"))

    survey.entered_by_id = entered_by_id

    raw_parent_id = form.get("parent_id")
    parent_id = int(raw_parent_id) if raw_parent_id else None
    if parent_id:
        parent = Parent.query.get(parent_id)
        if parent and parent in student.parents:
            survey.parent_id = parent.id

    db.session.commit()
    return survey


def get_or_create_teacher_survey(teacher, year, month):
    survey = TeacherMonthlySurvey.query.filter_by(
        teacher_id=teacher.id,
        period_year=year,
        period_month=month,
    ).first()
    if not survey:
        survey = TeacherMonthlySurvey(
            school_id=teacher.school_id,
            teacher_id=teacher.id,
            period_year=year,
            period_month=month,
        )
        db.session.add(survey)
        db.session.flush()
    return survey


def save_teacher_survey(teacher, year, month, form):
    survey = get_or_create_teacher_survey(teacher, year, month)

    survey.attendance_punctuality = form.get("attendance_punctuality") or None
    survey.lesson_preparation = form.get("lesson_preparation") or None
    survey.main_obstacles = (form.get("main_obstacles") or "").strip()
    survey.student_punctuality = form.get("student_punctuality") or None
    survey.student_preparation_percentage = (
        (form.get("student_preparation_percentage") or "").strip()
    )
    survey.student_comprehension = form.get("student_comprehension") or None
    survey.student_notes = (form.get("student_notes") or "").strip()
    survey.family_role_rating = form.get("family_role_rating") or None
    survey.family_role_message = (form.get("family_role_message") or "").strip()
    survey.session_suggestions = (form.get("session_suggestions") or "").strip()

    db.session.commit()
    return survey


def family_survey_status(school_id, year, month, student_ids):
    """Return completion counts for family surveys (complete / partial / not started)."""
    if not student_ids:
        return _empty_status_counts()

    surveys = FamilyFollowupSurvey.query.filter(
        FamilyFollowupSurvey.school_id == school_id,
        FamilyFollowupSurvey.student_id.in_(student_ids),
        FamilyFollowupSurvey.period_year == year,
        FamilyFollowupSurvey.period_month == month,
    ).all()
    survey_map = {s.student_id: s for s in surveys}
    return _count_survey_states(student_ids, survey_map, family_survey_progress)


def teacher_survey_status(school_id, year, month, teacher_ids):
    if not teacher_ids:
        return _empty_status_counts()

    surveys = TeacherMonthlySurvey.query.filter(
        TeacherMonthlySurvey.school_id == school_id,
        TeacherMonthlySurvey.teacher_id.in_(teacher_ids),
        TeacherMonthlySurvey.period_year == year,
        TeacherMonthlySurvey.period_month == month,
    ).all()
    survey_map = {s.teacher_id: s for s in surveys}
    return _count_survey_states(teacher_ids, survey_map, teacher_survey_progress)


def students_for_user(user, grade_id=None, class_id=None):
    """Students the current user can enter family surveys for."""
    from app.utils.school_context import get_active_school_id
    from app.services.permission_registry import has_student_capabilities

    if user.is_parent and user.parent_profile:
        child_ids = [c.id for c in user.parent_profile.children]
        if not child_ids:
            return []
        query = Student.query.filter(
            Student.is_active == True,  # noqa: E712
            Student.id.in_(child_ids),
        )
    elif user.is_teacher and user.teacher_profile:
        students = students_for_teacher(
            user.teacher_profile, grade_id=grade_id, class_id=class_id,
        )
        if user.student_profile and has_student_capabilities(user):
            own = user.student_profile
            if own.is_active:
                ids = {s.id for s in students}
                if own.id not in ids:
                    if (not grade_id or own.grade_id == grade_id) and (
                        not class_id or own.class_id == class_id
                    ):
                        students = list(students) + [own]
        return students
    elif user.is_student and user.student_profile:
        query = Student.query.filter(
            Student.is_active == True,  # noqa: E712
            Student.id == user.student_profile.id,
        )
    elif user.is_school_manager and user.school_id:
        query = Student.query.filter_by(school_id=user.school_id, is_active=True)
    elif user.is_platform_admin or user.is_super_admin:
        sid = get_active_school_id() or user.school_id
        if sid:
            query = Student.query.filter_by(school_id=sid, is_active=True)
        elif user.is_super_admin:
            query = Student.query.filter(Student.is_active == True)  # noqa: E712
        else:
            return []
    else:
        return []

    if grade_id:
        query = query.filter_by(grade_id=grade_id)
    if class_id:
        query = query.filter_by(class_id=class_id)

    return query.order_by(Student.grade_id, Student.class_id, Student.full_name_ar).all()


def teachers_for_user(user):
    """Teachers the current user can view/fill monthly surveys for."""
    from app.utils.school_context import get_active_school_id

    if user.is_teacher and user.teacher_profile:
        return [user.teacher_profile]

    sid = get_active_school_id() or user.school_id
    if user.is_school_manager and sid:
        return Teacher.query.filter_by(school_id=sid, is_active=True).order_by(
            Teacher.full_name_ar
        ).all()

    if user.is_platform_admin or user.is_super_admin:
        if sid:
            return Teacher.query.filter_by(school_id=sid, is_active=True).order_by(
                Teacher.full_name_ar
            ).all()
        if user.is_super_admin:
            return Teacher.query.filter_by(is_active=True).order_by(
                Teacher.full_name_ar
            ).all()
    return []


def resolve_followup_school_id(user):
    """School scope for follow-up survey lists and stats."""
    from app.utils.school_context import get_active_school_id

    sid = get_active_school_id() or user.school_id
    if sid:
        return sid
    if user.is_student and user.student_profile:
        return user.student_profile.school_id
    if user.is_parent and user.parent_profile:
        children = user.parent_profile.children
        if children:
            return children[0].school_id
    return None


def can_access_followup_surveys(user):
    from app.utils.permissions import user_has_any_permission
    return (
        user.is_authenticated
        and user.is_active
        and user_has_any_permission(user, "manage_followup_surveys", "view_followup_surveys")
    )


def can_view_family_surveys(user):
    from app.utils.permissions import user_has_any_permission
    if not user.is_authenticated:
        return False
    return can_fill_family_surveys(user) or user_has_any_permission(user, "view_followup_surveys")


def default_followup_tab(user):
    from app.services.permission_registry import has_teacher_capabilities
    if has_teacher_capabilities(user):
        return "teacher"
    if user.is_student or user.is_parent:
        return "family"
    return "family"


def can_fill_family_surveys(user):
    from app.utils.permissions import user_has_permission
    if not user.is_authenticated:
        return False
    return user_has_permission(user, "manage_followup_surveys")


def can_fill_teacher_surveys(user):
    from app.utils.permissions import user_has_permission
    if not user.is_authenticated:
        return False
    return user_has_permission(user, "manage_followup_surveys")


def can_access_student(user, student):
    """Check whether user may fill/view a family survey for this student."""
    from app.services.teacher_student_service import teacher_can_access_student

    if user.is_super_admin:
        return True
    if user.is_student and user.student_profile:
        return student.id == user.student_profile.id
    if user.is_school_manager and user.school_id == student.school_id:
        return True
    if user.is_platform_admin:
        from app.utils.school_context import get_active_school_id
        sid = get_active_school_id() or user.school_id
        return not sid or student.school_id == sid
    if user.teacher_profile and teacher_can_access_student(user, student):
        return True
    allowed_ids = {s.id for s in students_for_user(user)}
    return student.id in allowed_ids


def can_access_teacher(user, teacher):
    """Check whether user may fill/view a teacher monthly survey."""
    if user.is_super_admin:
        return True
    if user.is_teacher and user.teacher_profile:
        return teacher.id == user.teacher_profile.id
    if user.is_school_manager and user.school_id:
        return teacher.school_id == user.school_id
    if user.is_platform_admin:
        from app.utils.school_context import get_active_school_id
        sid = get_active_school_id() or user.school_id
        return not sid or teacher.school_id == sid
    return False


def verify_all_fields_stored(school_id=None):
    """Ensure every printed question maps to a model column."""
    family_cols = {c.name for c in FamilyFollowupSurvey.__table__.columns}
    teacher_cols = {c.name for c in TeacherMonthlySurvey.__table__.columns}
    missing_family = []
    missing_teacher = []
    family_map = family_survey_field_map(school_id)
    teacher_map = teacher_survey_field_map(school_id)

    for fields, _label in family_map:
        for field in fields.split(","):
            if field not in family_cols:
                missing_family.append(field)

    for field, _label in teacher_map:
        if field not in teacher_cols:
            missing_teacher.append(field)

    return {
        "family_ok": len(missing_family) == 0,
        "teacher_ok": len(missing_teacher) == 0,
        "missing_family": missing_family,
        "missing_teacher": missing_teacher,
        "family_questions": len(family_map),
        "teacher_questions": len(teacher_map),
    }


def _family_field_answered(survey, field):
    if not survey:
        return False
    if field == "stage_primary,stage_middle,stage_secondary":
        return survey.stage_primary or survey.stage_middle or survey.stage_secondary
    if field in FAMILY_BOOL_FIELDS:
        return getattr(survey, field) is not None
    val = getattr(survey, field, None)
    return _text_answered(val) if isinstance(val, str) or val is None else bool(val)


def family_survey_checklist(survey, school_id=None):
    """Printed family form questions with answered status."""
    sid = school_id or (survey.school_id if survey else None)
    return [
        {"label": label, "answered": _family_field_answered(survey, fields)}
        for fields, label in family_survey_field_map(sid)
    ]


def _teacher_field_answered(survey, field):
    if not survey:
        return False
    if field in TEACHER_RATING_FIELDS:
        return bool(getattr(survey, field))
    return _text_answered(getattr(survey, field))


def teacher_survey_checklist(survey, school_id=None):
    """Printed teacher form questions with answered status."""
    sid = school_id or (survey.school_id if survey else None)
    return [
        {"label": label, "answered": _teacher_field_answered(survey, field)}
        for field, label in teacher_survey_field_map(sid)
    ]


def family_entries_for_students(students, year, month):
    """Build template context for each student's family survey on the hub page."""
    entries = []
    for student in students:
        survey = FamilyFollowupSurvey.query.filter_by(
            student_id=student.id, period_year=year, period_month=month,
        ).first()
        answered, total = family_survey_progress(survey)
        status_text, status_class = survey_status_label(answered, total, student.school_id)
        entries.append({
            "student": student,
            "survey": survey,
            "answered": answered,
            "total": total,
            "status_text": status_text,
            "status_class": status_class,
            "checklist": family_survey_checklist(survey, student.school_id),
            "default_family_name": default_family_name(student),
            "parents": student.parents,
        })
    return entries


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


def followup_period_context(year, month, school_id=None):
    from datetime import date

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    today = date.today()
    month_name = get_arabic_month_name(month, school_id)
    return {
        "arabic_month": month_name,
        "period_label": f"{month_name} {year}",
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "is_current_period": year == today.year and month == today.month,
    }


def completion_percent(status):
    if not status or not status.get("total"):
        return 0
    return int(round(status["complete"] * 100 / status["total"]))


def matches_status_filter(answered, total, status_filter):
    if status_filter in (None, "", "all"):
        return True
    if status_filter == "complete":
        return answered >= total
    if status_filter == "partial":
        return 0 < answered < total
    if status_filter == "empty":
        return answered == 0
    return True


def matches_name_search(name_ar, name_en, query):
    if not query:
        return True
    q = query.strip().lower()
    for name in (name_ar, name_en):
        if name and q in name.lower():
            return True
    return False


def filter_grouped_entries(grouped, status_filter, search_q):
    """Filter grouped family entries; drop empty class/grade buckets."""
    filtered = {}
    for grade_name, classes in grouped.items():
        grade_classes = {}
        for class_name, entries in classes.items():
            rows = [
                entry for entry in entries
                if matches_status_filter(entry["answered"], entry["total"], status_filter)
                and matches_name_search(
                    entry["student"].full_name_ar,
                    entry["student"].full_name,
                    search_q,
                )
            ]
            if rows:
                grade_classes[class_name] = rows
        if grade_classes:
            filtered[grade_name] = grade_classes
    return filtered


def class_completion_summary(entries):
    complete = sum(1 for e in entries if e["answered"] >= e["total"])
    return complete, len(entries)


def teacher_index_rows(teachers, teacher_surveys, year, month):
    """Teacher list rows with teacher + family survey progress."""
    all_students = []
    teacher_student_map = {}
    for teacher in teachers:
        students = students_for_teacher(teacher)
        teacher_student_map[teacher.id] = students
        all_students.extend(students)

    student_ids = [s.id for s in all_students]
    family_map = {}
    if student_ids:
        for survey in FamilyFollowupSurvey.query.filter(
            FamilyFollowupSurvey.student_id.in_(student_ids),
            FamilyFollowupSurvey.period_year == year,
            FamilyFollowupSurvey.period_month == month,
        ).all():
            family_map[survey.student_id] = survey

    rows = []
    for teacher in teachers:
        survey = teacher_surveys.get(teacher.id)
        answered, total = teacher_survey_progress(survey)
        status_text, status_class = survey_status_label(answered, total)
        students = teacher_student_map.get(teacher.id, [])
        fam_complete = fam_partial = 0
        for student in students:
            fs = family_map.get(student.id)
            fa, ft = family_survey_progress(fs)
            if fa >= ft:
                fam_complete += 1
            elif fa > 0:
                fam_partial += 1
        fam_total = len(students)
        rows.append({
            "teacher": teacher,
            "survey": survey,
            "answered": answered,
            "total": total,
            "status_text": status_text,
            "status_class": status_class,
            "percent": int(round(answered * 100 / total)) if total else 0,
            "family_total": fam_total,
            "family_complete": fam_complete,
            "family_partial": fam_partial,
            "family_pending": fam_total - fam_complete,
        })
    return rows
