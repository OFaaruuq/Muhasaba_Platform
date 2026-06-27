"""Analytics and full reports for monthly follow-up surveys."""

from app.models import (
    FamilyFollowupSurvey,
    TeacherMonthlySurvey,
    EducationalProgramFollowupSurvey,
    StudentEducationalProgramFollowupSurvey,
)
from app.services.educational_program_service import (
    program_survey_sections,
    program_total_questions,
    program_survey_progress,
    bool_label as program_bool_label,
)
from app.services.followup_survey_service import (
    FAMILY_BOOL_FIELDS,
    FAMILY_TOTAL_QUESTIONS,
    TEACHER_RATING_FIELDS,
    TEACHER_TOTAL_QUESTIONS,
    bool_label,
    family_survey_field_map,
    teacher_survey_field_map,
    family_survey_progress,
    frequency_label,
    survey_status_label,
    teacher_survey_progress,
    weekly_meetings_label,
)
from app.services.teacher_student_service import students_for_teacher
from app.services.survey_config_service import get_arabic_month_name, get_education_stage_map
from app.services.identity_service import person_display_label


def iter_periods(end_year, end_month, count=6):
    """Return (year, month) tuples from end period going backwards."""
    periods = []
    year, month = end_year, end_month
    for _ in range(count):
        periods.append((year, month))
        if month == 1:
            year, month = year - 1, 12
        else:
            month -= 1
    return list(reversed(periods))


def period_label(year, month, school_id=None):
    return f"{get_arabic_month_name(month, school_id)} {year}"


def _family_field_display(survey, field, school_id=None):
    sid = school_id or (survey.school_id if survey else None)
    if not survey:
        return "—"
    if field == "family_name":
        return survey.family_name or "—"
    if field == "stage":
        stage_map = get_education_stage_field_labels(sid)
        stages = []
        if survey.stage_primary:
            stages.append(stage_map.get("stage_primary", "—"))
        if survey.stage_middle:
            stages.append(stage_map.get("stage_middle", "—"))
        if survey.stage_secondary:
            stages.append(stage_map.get("stage_secondary", "—"))
        return "، ".join(stages) if stages else "—"
    if field == "weekly_meetings_count":
        return weekly_meetings_label(survey.weekly_meetings_count, sid)
    if field in FAMILY_BOOL_FIELDS:
        return bool_label(getattr(survey, field), sid)
    val = getattr(survey, field, None)
    if isinstance(val, bool):
        return bool_label(val, sid)
    return val.strip() if val and str(val).strip() else "—"


def get_education_stage_field_labels(school_id=None):
    from app.services.survey_config_service import get_education_stage_field_map
    return get_education_stage_field_map(school_id)


def family_survey_report_sections(survey, school_id=None):
    """Full family survey answers from dynamic field map."""
    sid = school_id or (survey.school_id if survey else None)
    rows = []
    for fields, label in family_survey_field_map(sid):
        if fields == "stage_primary,stage_middle,stage_secondary":
            value = _family_field_display(survey, "stage", sid)
            rows.append({"label": label, "value": value, "answered": value != "—"})
            continue
        for field in fields.split(","):
            value = _family_field_display(survey, field.strip(), sid)
            rows.append({"label": label, "value": value, "answered": value != "—"})
    return [{"title": "استبيان الأسرة", "rows": rows}]


def _teacher_field_display(survey, field, school_id=None):
    sid = school_id or (survey.school_id if survey else None)
    if not survey:
        return "—"
    if field in TEACHER_RATING_FIELDS:
        val = getattr(survey, field, None)
        return frequency_label(val, sid) if val else "—"
    val = getattr(survey, field, None)
    return val.strip() if val and str(val).strip() else "—"


def teacher_survey_report_rows(survey, school_id=None):
    """Full teacher survey answers."""
    sid = school_id or (survey.school_id if survey else None)
    rows = []
    for field, label in teacher_survey_field_map(sid):
        value = _teacher_field_display(survey, field, sid)
        rows.append({
            "label": label,
            "value": value,
            "answered": value != "—",
            "is_rating": field in TEACHER_RATING_FIELDS,
        })
    return rows


def program_survey_report_sections(survey, school_id=None):
    """Full program survey answers grouped by section."""
    sid = school_id or (survey.school_id if survey else None)
    sections = []
    for _code, title, subtitle, fields in program_survey_sections(sid):
        rows = []
        for field, label in fields:
            val = getattr(survey, field, None) if survey else None
            display = program_bool_label(val, sid) if val is not None else "—"
            rows.append({
                "label": label,
                "value": display,
                "answered": val is not None or (isinstance(val, str) and val.strip()),
            })
        sections.append({"title": title, "subtitle": subtitle, "rows": rows})
    if survey:
        notes = survey.latecomers_notes
        sections.append({
            "title": "ملاحظات المتأخرين",
            "subtitle": None,
            "rows": [{
                "label": "ملاحظات إضافية",
                "value": notes.strip() if notes and notes.strip() else "—",
                "answered": bool(notes and notes.strip()),
            }],
        })
    return sections


def program_section_scores(survey, school_id=None):
    """Yes/no percentage per program section."""
    sid = school_id or (survey.school_id if survey else None)
    if not survey:
        return []
    scores = []
    for _code, title, _subtitle, fields in program_survey_sections(sid):
        yes = no = unanswered = 0
        for field, _label in fields:
            val = getattr(survey, field)
            if val is True:
                yes += 1
            elif val is False:
                no += 1
            else:
                unanswered += 1
        total = len(fields)
        scores.append({
            "title": title,
            "yes": yes,
            "no": no,
            "unanswered": unanswered,
            "total": total,
            "yes_percent": int(round(yes * 100 / total)) if total else 0,
        })
    return scores


def _load_family_surveys(student_ids, periods):
    if not student_ids:
        return {}
    years = {y for y, _m in periods}
    months = {m for _y, m in periods}
    surveys = FamilyFollowupSurvey.query.filter(
        FamilyFollowupSurvey.student_id.in_(student_ids),
        FamilyFollowupSurvey.period_year.in_(years),
        FamilyFollowupSurvey.period_month.in_(months),
    ).all()
    result = {}
    for s in surveys:
        result[(s.student_id, s.period_year, s.period_month)] = s
    return result


def student_survey_history(student, end_year, end_month, months=6):
    """Monthly completion history for one student."""
    periods = iter_periods(end_year, end_month, months)
    survey_map = _load_family_surveys([student.id], periods)
    history = []
    for year, month in periods:
        survey = survey_map.get((student.id, year, month))
        answered, total = family_survey_progress(survey)
        status_text, status_class = survey_status_label(answered, total)
        history.append({
            "year": year,
            "month": month,
            "label": period_label(year, month),
            "survey": survey,
            "answered": answered,
            "total": total,
            "percent": int(round(answered * 100 / total)) if total else 0,
            "status_text": status_text,
            "status_class": status_class,
        })
    return history


def family_bool_trends(surveys_by_period, school_id=None):
    """Aggregate bool field yes-rates across surveys list."""
    sid = school_id
    if not sid and surveys_by_period:
        first = next((s for s in surveys_by_period if s), None)
        sid = first.school_id if first else None
    field_map = {f.split(",")[0]: lbl for f, lbl in family_survey_field_map(sid)}
    trends = []
    for field in FAMILY_BOOL_FIELDS:
        label = field_map.get(field, field)
        yes = no = empty = 0
        for survey in surveys_by_period:
            if not survey:
                empty += 1
                continue
            val = getattr(survey, field)
            if val is True:
                yes += 1
            elif val is False:
                no += 1
            else:
                empty += 1
        total = len(surveys_by_period)
        trends.append({
            "field": field,
            "label": label,
            "yes": yes,
            "no": no,
            "empty": empty,
            "yes_percent": int(round(yes * 100 / total)) if total else 0,
        })
    return trends


def student_analytics_row(student, year, month):
    """Overview table row for one student."""
    survey = FamilyFollowupSurvey.query.filter_by(
        student_id=student.id, period_year=year, period_month=month,
    ).first()
    program_survey = StudentEducationalProgramFollowupSurvey.query.filter_by(
        student_id=student.id, period_year=year, period_month=month,
    ).first()
    answered, total = family_survey_progress(survey)
    status_text, status_class = survey_status_label(answered, total)
    p_answered, p_total = program_survey_progress(program_survey, student.school_id)
    p_status, p_class = survey_status_label(p_answered, p_total, student.school_id)
    teacher = student.responsible_teacher
    return {
        "student": student,
        "survey": survey,
        "program_survey": program_survey,
        "answered": answered,
        "total": total,
        "percent": int(round(answered * 100 / total)) if total else 0,
        "status_text": status_text,
        "status_class": status_class,
        "program_answered": p_answered,
        "program_total": p_total,
        "program_percent": int(round(p_answered * 100 / p_total)) if p_total else 0,
        "program_status": p_status,
        "program_status_class": p_class,
        "grade_name": student.grade.name_ar if student.grade else "—",
        "class_name": student.class_.name if student.class_ else "—",
        "teacher_name": person_display_label(teacher) if teacher else "—",
    }


def teacher_analytics_row(teacher, year, month):
    """Overview table row for one teacher (all three survey types)."""
    teacher_survey = TeacherMonthlySurvey.query.filter_by(
        teacher_id=teacher.id, period_year=year, period_month=month,
    ).first()
    program_survey = EducationalProgramFollowupSurvey.query.filter_by(
        teacher_id=teacher.id, period_year=year, period_month=month,
    ).first()

    t_answered, t_total = teacher_survey_progress(teacher_survey)
    t_status, t_class = survey_status_label(t_answered, t_total)
    p_answered, p_total = program_survey_progress(program_survey)
    p_status, p_class = survey_status_label(p_answered, p_total)

    students = students_for_teacher(teacher)
    fam_complete = fam_partial = 0
    for st in students:
        fs = FamilyFollowupSurvey.query.filter_by(
            student_id=st.id, period_year=year, period_month=month,
        ).first()
        fa, ft = family_survey_progress(fs)
        if fa >= ft:
            fam_complete += 1
        elif fa > 0:
            fam_partial += 1
    fam_total = len(students)

    return {
        "teacher": teacher,
        "teacher_survey": teacher_survey,
        "program_survey": program_survey,
        "teacher_answered": t_answered,
        "teacher_total": t_total,
        "teacher_status": t_status,
        "teacher_status_class": t_class,
        "teacher_percent": int(round(t_answered * 100 / t_total)) if t_total else 0,
        "program_answered": p_answered,
        "program_total": p_total,
        "program_status": p_status,
        "program_status_class": p_class,
        "program_percent": int(round(p_answered * 100 / p_total)) if p_total else 0,
        "family_total": fam_total,
        "family_complete": fam_complete,
        "family_partial": fam_partial,
        "family_pending": fam_total - fam_complete,
        "program_sections": program_section_scores(program_survey),
    }


def teacher_combined_report(teacher, year, month, history_months=6):
    """Full analytics payload for a teacher."""
    teacher_survey = TeacherMonthlySurvey.query.filter_by(
        teacher_id=teacher.id, period_year=year, period_month=month,
    ).first()
    program_survey = EducationalProgramFollowupSurvey.query.filter_by(
        teacher_id=teacher.id, period_year=year, period_month=month,
    ).first()
    students = students_for_teacher(teacher)
    family_entries = []
    for student in students:
        row = student_analytics_row(student, year, month)
        family_entries.append(row)

    periods = iter_periods(year, month, history_months)
    teacher_history = []
    program_history = []
    for py, pm in periods:
        ts = TeacherMonthlySurvey.query.filter_by(
            teacher_id=teacher.id, period_year=py, period_month=pm,
        ).first()
        ps = EducationalProgramFollowupSurvey.query.filter_by(
            teacher_id=teacher.id, period_year=py, period_month=pm,
        ).first()
        ta, tt = teacher_survey_progress(ts)
        pa, pt = program_survey_progress(ps)
        teacher_history.append({
            "year": py, "month": pm,
            "label": period_label(py, pm),
            "answered": ta, "total": tt,
            "percent": int(round(ta * 100 / tt)) if tt else 0,
        })
        program_history.append({
            "year": py, "month": pm,
            "label": period_label(py, pm),
            "answered": pa, "total": pt,
            "percent": int(round(pa * 100 / pt)) if pt else 0,
        })

    t_answered, t_total = teacher_survey_progress(teacher_survey)
    p_answered, p_total = program_survey_progress(program_survey)

    return {
        "teacher": teacher,
        "year": year,
        "month": month,
        "teacher_survey": teacher_survey,
        "program_survey": program_survey,
        "teacher_rows": teacher_survey_report_rows(teacher_survey),
        "program_sections": program_survey_report_sections(program_survey),
        "program_scores": program_section_scores(program_survey),
        "family_entries": family_entries,
        "teacher_history": teacher_history,
        "program_history": program_history,
        "teacher_answered": t_answered,
        "teacher_total": t_total,
        "program_answered": p_answered,
        "program_total": p_total,
        "teacher_status": survey_status_label(t_answered, t_total),
        "program_status": survey_status_label(p_answered, p_total),
    }


def student_full_report(student, year, month, history_months=6):
    """Full analytics payload for a student."""
    survey = FamilyFollowupSurvey.query.filter_by(
        student_id=student.id, period_year=year, period_month=month,
    ).first()
    program_survey = StudentEducationalProgramFollowupSurvey.query.filter_by(
        student_id=student.id, period_year=year, period_month=month,
    ).first()
    history = student_survey_history(student, year, month, history_months)
    history_surveys = [h["survey"] for h in history if h["survey"]]
    answered, total = family_survey_progress(survey)
    p_answered, p_total = program_survey_progress(program_survey, student.school_id)

    periods = iter_periods(year, month, history_months)
    program_history = []
    for py, pm in periods:
        ps = StudentEducationalProgramFollowupSurvey.query.filter_by(
            student_id=student.id, period_year=py, period_month=pm,
        ).first()
        pa, pt = program_survey_progress(ps, student.school_id)
        program_history.append({
            "year": py, "month": pm,
            "label": period_label(py, pm, student.school_id),
            "answered": pa, "total": pt,
            "percent": int(round(pa * 100 / pt)) if pt else 0,
        })

    responsible = student.responsible_teacher
    teacher_survey = None
    if responsible:
        teacher_survey = TeacherMonthlySurvey.query.filter_by(
            teacher_id=responsible.id, period_year=year, period_month=month,
        ).first()

    return {
        "student": student,
        "year": year,
        "month": month,
        "survey": survey,
        "program_survey": program_survey,
        "sections": family_survey_report_sections(survey, student.school_id),
        "program_sections": program_survey_report_sections(program_survey, student.school_id),
        "program_scores": program_section_scores(program_survey, student.school_id),
        "checklist": [
            {"label": lbl, "answered": _family_field_display(survey, fld.split(",")[0], student.school_id) != "—"}
            for fld, lbl in family_survey_field_map(student.school_id)
        ],
        "history": history,
        "program_history": program_history,
        "bool_trends": family_bool_trends(history_surveys or ([survey] if survey else []), student.school_id),
        "answered": answered,
        "total": total,
        "status": survey_status_label(answered, total),
        "program_answered": p_answered,
        "program_total": p_total,
        "program_status": survey_status_label(p_answered, p_total, student.school_id),
        "responsible_teacher": responsible,
        "teacher_survey": teacher_survey,
        "teacher_notes": (
            teacher_survey.student_notes if teacher_survey else None
        ),
        "teacher_family_rating": (
            frequency_label(teacher_survey.family_role_rating)
            if teacher_survey and teacher_survey.family_role_rating else None
        ),
    }


def school_analytics_summary(students, teachers, year, month):
    """Aggregate completion stats for dashboard overview."""
    student_ids = [s.id for s in students]
    teacher_ids = [t.id for t in teachers]

    family_status = _aggregate_family(student_ids, year, month)
    student_program_status = _aggregate_student_program(student_ids, year, month)
    teacher_status = _aggregate_teacher(teacher_ids, year, month)
    program_status = _aggregate_program(teacher_ids, year, month)

    class_stats = _class_breakdown(students, year, month)

    surveys = []
    if student_ids:
        surveys = FamilyFollowupSurvey.query.filter(
            FamilyFollowupSurvey.student_id.in_(student_ids),
            FamilyFollowupSurvey.period_year == year,
            FamilyFollowupSurvey.period_month == month,
        ).all()
    bool_aggregates = family_bool_trends(surveys) if surveys else []

    return {
        "family": family_status,
        "student_program": student_program_status,
        "teacher": teacher_status,
        "program": program_status,
        "class_stats": class_stats,
        "bool_aggregates": bool_aggregates,
    }


def _aggregate_family(student_ids, year, month):
    if not student_ids:
        return _empty_counts()
    complete = partial = 0
    for sid in student_ids:
        survey = FamilyFollowupSurvey.query.filter_by(
            student_id=sid, period_year=year, period_month=month,
        ).first()
        answered, total = family_survey_progress(survey)
        if answered >= total:
            complete += 1
        elif answered > 0:
            partial += 1
    total = len(student_ids)
    return {
        "total": total,
        "complete": complete,
        "partial": partial,
        "not_started": total - complete - partial,
    }


def _aggregate_teacher(teacher_ids, year, month):
    if not teacher_ids:
        return _empty_counts()
    complete = partial = 0
    for tid in teacher_ids:
        survey = TeacherMonthlySurvey.query.filter_by(
            teacher_id=tid, period_year=year, period_month=month,
        ).first()
        answered, total = teacher_survey_progress(survey)
        if answered >= total:
            complete += 1
        elif answered > 0:
            partial += 1
    total = len(teacher_ids)
    return {
        "total": total,
        "complete": complete,
        "partial": partial,
        "not_started": total - complete - partial,
    }


def _aggregate_student_program(student_ids, year, month):
    if not student_ids:
        return _empty_counts()
    complete = partial = 0
    for sid in student_ids:
        survey = StudentEducationalProgramFollowupSurvey.query.filter_by(
            student_id=sid, period_year=year, period_month=month,
        ).first()
        answered, total = program_survey_progress(survey)
        if answered >= total:
            complete += 1
        elif answered > 0:
            partial += 1
    total = len(student_ids)
    return {
        "total": total,
        "complete": complete,
        "partial": partial,
        "not_started": total - complete - partial,
    }


def _aggregate_program(teacher_ids, year, month):
    if not teacher_ids:
        return _empty_counts()
    complete = partial = 0
    for tid in teacher_ids:
        survey = EducationalProgramFollowupSurvey.query.filter_by(
            teacher_id=tid, period_year=year, period_month=month,
        ).first()
        answered, total = program_survey_progress(survey)
        if answered >= total:
            complete += 1
        elif answered > 0:
            partial += 1
    total = len(teacher_ids)
    return {
        "total": total,
        "complete": complete,
        "partial": partial,
        "not_started": total - complete - partial,
    }


def _empty_counts():
    return {"total": 0, "complete": 0, "partial": 0, "not_started": 0}


def _class_breakdown(students, year, month):
    buckets = {}
    for student in students:
        grade = student.grade.name_ar if student.grade else "—"
        cls = student.class_.name if student.class_ else "—"
        key = (grade, cls)
        if key not in buckets:
            buckets[key] = {"grade": grade, "class": cls, "total": 0, "complete": 0}
        buckets[key]["total"] += 1
        survey = FamilyFollowupSurvey.query.filter_by(
            student_id=student.id, period_year=year, period_month=month,
        ).first()
        answered, total = family_survey_progress(survey)
        if answered >= total:
            buckets[key]["complete"] += 1
    rows = list(buckets.values())
    for row in rows:
        row["percent"] = (
            int(round(row["complete"] * 100 / row["total"])) if row["total"] else 0
        )
    return sorted(rows, key=lambda r: (r["grade"], r["class"]))


def completion_pct(status):
    if not status or not status.get("total"):
        return 0
    return int(round(status["complete"] * 100 / status["total"]))
