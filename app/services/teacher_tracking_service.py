"""Teacher-scoped student performance and follow-up survey tracking."""

from datetime import date

from app.kpi.calculator import calculate_overall
from app.models import FamilyFollowupSurvey, TeacherMonthlySurvey
from app.services.config_service import get_performance_color
from app.services.followup_survey_service import (
    family_survey_progress,
    survey_status_label,
    teacher_survey_progress,
    TEACHER_TOTAL_QUESTIONS,
    FAMILY_TOTAL_QUESTIONS,
)
from app.services.teacher_student_service import students_for_teacher


def teacher_student_ids(teacher):
    return [s.id for s in students_for_teacher(teacher)]


def build_teacher_tracking(teacher, year=None, month=None):
    """
    Performance + follow-up survey status for every student assigned to this teacher.
    Teachers must complete family follow-up surveys for each student monthly.
    """
    today = date.today()
    year = year or today.year
    month = month or today.month

    students = students_for_teacher(teacher)
    student_ids = [s.id for s in students]

    family_map = {}
    if student_ids:
        for survey in FamilyFollowupSurvey.query.filter(
            FamilyFollowupSurvey.student_id.in_(student_ids),
            FamilyFollowupSurvey.period_year == year,
            FamilyFollowupSurvey.period_month == month,
        ).all():
            family_map[survey.student_id] = survey

    rows = []
    family_complete = family_partial = family_pending = 0

    for student in students:
        survey = family_map.get(student.id)
        answered, total = family_survey_progress(survey)
        status_text, status_class = survey_status_label(answered, total)
        overall_kpi, _ = calculate_overall(student.id, "term", student.school_id)
        perf_color = get_performance_color(overall_kpi, student.school_id)

        if answered >= total:
            family_complete += 1
        elif answered > 0:
            family_partial += 1
        else:
            family_pending += 1

        rows.append({
            "student": student,
            "survey": survey,
            "answered": answered,
            "total": total,
            "percent": int(round(answered * 100 / total)) if total else 0,
            "status_text": status_text,
            "status_class": status_class,
            "overall_kpi": round(overall_kpi, 1),
            "perf_color": perf_color,
            "needs_survey": answered < total,
            "grade_name": student.grade.name_ar if student.grade else "—",
            "class_name": student.class_.name if student.class_ else "—",
        })

    teacher_survey = TeacherMonthlySurvey.query.filter_by(
        teacher_id=teacher.id, period_year=year, period_month=month,
    ).first()
    t_answered, t_total = teacher_survey_progress(teacher_survey)
    t_status, t_class = survey_status_label(t_answered, t_total)

    total_students = len(students)
    return {
        "rows": rows,
        "student_count": total_students,
        "period_year": year,
        "period_month": month,
        "family_complete": family_complete,
        "family_partial": family_partial,
        "family_pending": family_pending,
        "family_total": total_students,
        "family_questions": FAMILY_TOTAL_QUESTIONS,
        "teacher_survey": teacher_survey,
        "teacher_answered": t_answered,
        "teacher_total": t_total,
        "teacher_status_text": t_status,
        "teacher_status_class": t_class,
        "teacher_questions": TEACHER_TOTAL_QUESTIONS,
        "teacher_survey_done": t_answered >= t_total,
        "all_family_done": total_students > 0 and family_pending == 0 and family_partial == 0,
        "completion_pct": int(round(family_complete * 100 / total_students)) if total_students else 0,
    }


def tracking_by_student_id(teacher, year=None, month=None):
    """Map student_id -> tracking row for list views."""
    tracking = build_teacher_tracking(teacher, year, month)
    return {row["student"].id: row for row in tracking["rows"]}
