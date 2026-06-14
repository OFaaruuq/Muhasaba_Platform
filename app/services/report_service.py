"""Reports hub — access control and listing helpers."""

from app.models import (
    FamilyFollowupSurvey,
    TeacherMonthlySurvey,
    EducationalProgramFollowupSurvey,
)
from app.services.followup_survey_service import (
    can_access_student,
    can_access_teacher,
    can_fill_teacher_surveys,
    can_view_family_surveys,
    students_for_user,
    teachers_for_user,
    family_survey_progress,
    teacher_survey_progress,
)
from app.services.educational_program_service import (
    can_fill_program_surveys,
    program_survey_progress,
)
from app.services.followup_analytics_service import student_analytics_row, teacher_analytics_row


def can_access_reports(user):
    from app.utils.permissions import user_has_any_permission
    return (
        user.is_authenticated
        and user.is_active
        and user_has_any_permission(
            user, "view_reports", "view_own_kpi", "view_children_kpi",
            "manage_followup_surveys", "view_followup_surveys",
        )
    )


def can_access_student_report(user, student):
    if user.is_super_admin:
        return True
    if user.is_student and user.student_profile:
        return student.id == user.student_profile.id
    if user.is_parent and user.parent_profile:
        return student.id in {c.id for c in user.parent_profile.children}
    if user.is_school_manager and user.school_id == student.school_id:
        return True
    if user.is_platform_admin:
        from app.utils.school_context import get_active_school_id
        sid = get_active_school_id() or user.school_id
        return not sid or student.school_id == sid
    if user.is_teacher:
        return can_access_student(user, student)
    return False


def can_access_teacher_report(user, teacher):
    return can_access_teacher(user, teacher)


def list_students_for_reports(user, search_q="", grade_id=None, class_id=None):
    students = students_for_user(user, grade_id, class_id)
    if search_q:
        q = search_q.strip().lower()
        students = [
            s for s in students
            if q in (s.full_name_ar or "").lower() or q in (s.full_name or "").lower()
        ]
    return students


def list_teachers_for_reports(user, search_q=""):
    if not (can_fill_teacher_surveys(user) or can_fill_program_surveys(user)):
        return []
    teachers = teachers_for_user(user)
    if search_q:
        q = search_q.strip().lower()
        teachers = [
            t for t in teachers
            if q in (t.full_name_ar or "").lower() or q in (t.full_name or "").lower()
        ]
    return teachers


def student_report_cards(students, year, month):
    """Build report hub rows for students with follow-up status."""
    cards = []
    for student in students:
        row = student_analytics_row(student, year, month)
        cards.append({
            "student": student,
            "grade_name": row["grade_name"],
            "class_name": row["class_name"],
            "followup": row,
        })
    return cards


def teacher_report_cards(teachers, year, month):
    cards = []
    for teacher in teachers:
        row = teacher_analytics_row(teacher, year, month)
        cards.append({"teacher": teacher, "followup": row})
    return cards


def reports_summary(students, teachers, year, month):
    fam_complete = fam_partial = fam_empty = 0
    for s in students:
        survey = FamilyFollowupSurvey.query.filter_by(
            student_id=s.id, period_year=year, period_month=month,
        ).first()
        a, t = family_survey_progress(survey)
        if a >= t:
            fam_complete += 1
        elif a > 0:
            fam_partial += 1
        else:
            fam_empty += 1

    t_complete = t_partial = 0
    p_complete = p_partial = 0
    for teacher in teachers:
        ts = TeacherMonthlySurvey.query.filter_by(
            teacher_id=teacher.id, period_year=year, period_month=month,
        ).first()
        ta, tt = teacher_survey_progress(ts)
        if ta >= tt:
            t_complete += 1
        elif ta > 0:
            t_partial += 1

        ps = EducationalProgramFollowupSurvey.query.filter_by(
            teacher_id=teacher.id, period_year=year, period_month=month,
        ).first()
        pa, pt = program_survey_progress(ps)
        if pa >= pt:
            p_complete += 1
        elif pa > 0:
            p_partial += 1

    return {
        "students_total": len(students),
        "family_complete": fam_complete,
        "family_partial": fam_partial,
        "family_empty": fam_empty,
        "teachers_total": len(teachers),
        "teacher_complete": t_complete,
        "teacher_partial": t_partial,
        "program_complete": p_complete,
        "program_partial": p_partial,
    }
