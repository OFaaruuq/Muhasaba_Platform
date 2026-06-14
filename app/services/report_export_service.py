"""PDF/Excel export helpers for the reports module."""

import io
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.models import (
    FamilyFollowupSurvey,
    TeacherMonthlySurvey,
    EducationalProgramFollowupSurvey,
)
from app.services.config_service import get_setting, get_report_labels
from app.services.followup_analytics_service import (
    teacher_survey_report_rows,
    program_survey_report_sections,
    period_label,
    student_full_report,
)
from app.services.followup_survey_service import (
    family_survey_progress,
    teacher_survey_progress,
)
from app.services.educational_program_service import program_survey_progress


def wrap_text(text, max_len=80):
    words = (text or "").replace("\n", " ").split()
    lines = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 <= max_len:
            current = f"{current} {w}".strip()
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines or ["-"]


def _pdf_canvas():
    buffer = io.BytesIO()
    return buffer, canvas.Canvas(buffer, pagesize=A4)


def _ensure_space(c, y, min_y=60, height=A4[1]):
    if y < min_y:
        c.showPage()
        return height - 50
    return y


def _draw_lines(c, y, lines, x=50, line_height=14, font="Helvetica", size=10):
    c.setFont(font, size)
    height = A4[1]
    for line in lines:
        y = _ensure_space(c, y, height=height)
        c.drawString(x, y, line[:120])
        y -= line_height
    return y


def export_kpi_pdf(student, scores, overall):
    buffer, c = _pdf_canvas()
    width, height = A4
    labels = get_report_labels(student.school_id)
    platform = get_setting("platform_name_ar", student.school_id, "منصة المحاسبة")

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, f"{platform} - {labels['kpi_title']}")
    c.setFont("Helvetica", 12)
    y = height - 80
    c.drawString(50, y, f"{labels['student']}: {student.full_name_ar or student.full_name}")
    y -= 20
    c.drawString(50, y, f"{labels['id']}: {student.student_id}")
    y -= 20
    c.drawString(50, y, f"{labels['date']}: {date.today().isoformat()}")
    y -= 30

    for s in scores:
        c.drawString(50, y, f"{s.kpi.name}: {s.score}%")
        y -= 18

    c.drawString(50, y - 10, f"{labels['overall_kpi']}: {overall}%")
    c.save()
    buffer.seek(0)
    return buffer


def export_evaluation_pdf(student, evaluations, school_id=None):
    buffer, c = _pdf_canvas()
    width, height = A4
    labels = get_report_labels(school_id or student.school_id)
    from app.services.config_service import get_criterion_category_labels

    cat_labels = get_criterion_category_labels(student.school_id)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 50, f"{labels['eval_title']} - {student.full_name_ar or student.full_name}")
    y = height - 90
    acad = cat_labels.get("academic", "academic")
    beh = cat_labels.get("behavior", "behavior")
    for ev in evaluations:
        line = f"{ev.date} | {labels['daily']}:{ev.daily_score}% {acad}:{ev.academic_score}% {beh}:{ev.behavior_score}%"
        y = _ensure_space(c, y)
        c.setFont("Helvetica", 10)
        c.drawString(50, y, line)
        y -= 16
    c.save()
    buffer.seek(0)
    return buffer


def export_monthly_evaluation_pdf(student, evaluation, year, month):
    buffer, c = _pdf_canvas()
    width, height = A4
    labels = get_report_labels(student.school_id)
    y = height - 50

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, labels["monthly_title"])
    y -= 25
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"{labels['student']}: {student.full_name_ar or student.full_name}")
    y -= 18
    c.drawString(50, y, f"{labels['id']}: {student.student_id} | {labels['period']}: {month}/{year}")
    y -= 25

    if evaluation:
        c.drawString(50, y, f"{labels['overall_score']}: {evaluation.overall_score}%")
        y -= 30
        for header_key, attr in [
            ("strengths", "strengths"),
            ("weaknesses", "weaknesses"),
            ("recommendations", "recommendations"),
        ]:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(50, y, labels[header_key])
            y -= 16
            c.setFont("Helvetica", 10)
            for line in wrap_text(getattr(evaluation, attr) or "-"):
                y = _ensure_space(c, y)
                c.drawString(50, y, line)
                y -= 14
            y -= 8
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, labels["criteria_details"])
        y -= 16
        c.setFont("Helvetica", 9)
        for d in evaluation.details:
            y = _ensure_space(c, y)
            c.drawString(50, y, f"{d.criterion_ar or d.criterion}: {d.rating}/5")
            y -= 12
    else:
        c.drawString(50, y, labels["no_monthly"])

    c.save()
    buffer.seek(0)
    return buffer


def export_family_followup_pdf(student, year, month):
    report = student_full_report(student, year, month, history_months=1)
    survey = report["survey"]
    answered, total = report["answered"], report["total"]
    buffer, c = _pdf_canvas()
    height = A4[1]
    platform = get_setting("platform_name_ar", student.school_id, "منصة المحاسبة")

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 50, f"{platform} - Family Follow-up Report")
    y = height - 75
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Student: {student.full_name_ar or student.full_name}")
    y -= 18
    c.drawString(50, y, f"Period: {period_label(year, month)} | Progress: {answered}/{total}")
    y -= 25

    if not survey:
        c.drawString(50, y, "No survey submitted for this period.")
    else:
        for section in report["sections"]:
            y = _ensure_space(c, y)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(50, y, section["title"])
            y -= 16
            c.setFont("Helvetica", 9)
            for row in section["rows"]:
                if row["value"] == "—":
                    continue
                for line in wrap_text(f"{row['label']}: {row['value']}", 90):
                    y = _ensure_space(c, y)
                    c.drawString(55, y, line)
                    y -= 12
            y -= 8

    c.save()
    buffer.seek(0)
    return buffer


def export_teacher_followup_pdf(teacher, year, month):
    survey = TeacherMonthlySurvey.query.filter_by(
        teacher_id=teacher.id, period_year=year, period_month=month,
    ).first()
    answered, total = teacher_survey_progress(survey)
    rows = teacher_survey_report_rows(survey)
    buffer, c = _pdf_canvas()
    height = A4[1]
    platform = get_setting("platform_name_ar", teacher.school_id, "منصة المحاسبة")

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 50, f"{platform} - Teacher Follow-up Report")
    y = height - 75
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Teacher: {teacher.full_name_ar or teacher.full_name}")
    y -= 18
    c.drawString(50, y, f"Period: {period_label(year, month)} | Progress: {answered}/{total}")
    y -= 25

    if not survey:
        c.drawString(50, y, "No survey submitted for this period.")
    else:
        for row in rows:
            if row["value"] == "—":
                continue
            y = _ensure_space(c, y)
            for line in wrap_text(f"{row['label']}: {row['value']}", 90):
                c.drawString(50, y, line)
                y -= 12
            y -= 4

    c.save()
    buffer.seek(0)
    return buffer


def export_program_followup_pdf(teacher, year, month):
    survey = EducationalProgramFollowupSurvey.query.filter_by(
        teacher_id=teacher.id, period_year=year, period_month=month,
    ).first()
    answered, total = program_survey_progress(survey)
    sections = program_survey_report_sections(survey)
    buffer, c = _pdf_canvas()
    height = A4[1]
    platform = get_setting("platform_name_ar", teacher.school_id, "منصة المحاسبة")

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 50, f"{platform} - Educational Program Report")
    y = height - 75
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Teacher: {teacher.full_name_ar or teacher.full_name}")
    y -= 18
    c.drawString(50, y, f"Period: {period_label(year, month)} | Progress: {answered}/{total}")
    y -= 25

    if not survey:
        c.drawString(50, y, "No survey submitted for this period.")
    else:
        for section in sections:
            y = _ensure_space(c, y)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(50, y, section["title"])
            y -= 16
            c.setFont("Helvetica", 9)
            for row in section["rows"]:
                if row["value"] == "—":
                    continue
                for line in wrap_text(f"{row['label']}: {row['value']}", 88):
                    y = _ensure_space(c, y)
                    c.drawString(55, y, line)
                    y -= 11
            y -= 6

    c.save()
    buffer.seek(0)
    return buffer
