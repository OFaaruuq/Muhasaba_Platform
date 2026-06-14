"""Analytics for tarbiya monitoring dashboard (per guide)."""

from datetime import date, timedelta
from collections import defaultdict

from sqlalchemy import func

from app.extensions import db
from app.models import (
    Student, Class, Attendance, MonthlyEvaluation, MonthlyEvaluationDetail,
)
from app.services.config_service import (
    get_present_status_codes, get_performance_color, get_performance_label,
    get_monthly_strength_threshold, get_monthly_weakness_threshold,
    get_monthly_category_score_fields, get_recommendation_templates,
)


def _school_students(school_id):
    return Student.query.filter_by(school_id=school_id, is_active=True).all()


def average_performance(school_id, year=None, month=None):
    """Average monthly evaluation score for school."""
    year = year or date.today().year
    month = month or date.today().month
    result = db.session.query(func.avg(MonthlyEvaluation.overall_score)).filter(
        MonthlyEvaluation.school_id == school_id,
        MonthlyEvaluation.period_year == year,
        MonthlyEvaluation.period_month == month,
    ).scalar()
    return round(float(result), 1) if result else 0


def attendance_rate(school_id, since=None):
    since = since or (date.today() - timedelta(days=30))
    total = Attendance.query.filter(
        Attendance.school_id == school_id,
        Attendance.date >= since,
    ).count()
    present_codes = get_present_status_codes(school_id)
    present = Attendance.query.filter(
        Attendance.school_id == school_id,
        Attendance.date >= since,
        Attendance.status.in_(present_codes),
    ).count()
    return round((present / total * 100) if total else 0, 1)


def rank_groups(school_id, year=None, month=None, limit=5):
    """Rank classes (groups) by average monthly score."""
    year = year or date.today().year
    month = month or date.today().month
    classes = Class.query.filter_by(school_id=school_id).all()
    rankings = []
    for cls in classes:
        student_ids = [s.id for s in cls.students.filter_by(is_active=True).all()]
        if not student_ids:
            continue
        avg = db.session.query(func.avg(MonthlyEvaluation.overall_score)).filter(
            MonthlyEvaluation.student_id.in_(student_ids),
            MonthlyEvaluation.period_year == year,
            MonthlyEvaluation.period_month == month,
        ).scalar()
        if avg is not None:
            score = round(float(avg), 1)
            rankings.append({
                "group": cls,
                "name": cls.name + (f" - {cls.section}" if cls.section else ""),
                "score": score,
                "color": get_performance_color(score, school_id),
                "student_count": len(student_ids),
            })
    rankings.sort(key=lambda x: x["score"], reverse=True)
    strong = rankings[:limit]
    weak = list(reversed(rankings[-limit:])) if len(rankings) > limit else list(reversed(rankings))
    return strong, weak


def monthly_trends(school_id, months=6):
    """Monthly average scores for trend chart."""
    today = date.today()
    labels = []
    values = []
    for i in range(months - 1, -1, -1):
        d = today.replace(day=1)
        m = d.month - i
        y = d.year
        while m <= 0:
            m += 12
            y -= 1
        labels.append(f"{y}-{m:02d}")
        avg = db.session.query(func.avg(MonthlyEvaluation.overall_score)).filter(
            MonthlyEvaluation.school_id == school_id,
            MonthlyEvaluation.period_year == y,
            MonthlyEvaluation.period_month == m,
        ).scalar()
        values.append(round(float(avg), 1) if avg else 0)
    return labels, values


def weekly_attendance_summary(school_id, week_start=None):
    """Per-class attendance for a week."""
    if week_start is None:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    present_codes = get_present_status_codes(school_id)
    classes = Class.query.filter_by(school_id=school_id).all()
    summary = []
    for cls in classes:
        students = cls.students.filter_by(is_active=True).all()
        if not students:
            continue
        student_ids = [s.id for s in students]
        total = Attendance.query.filter(
            Attendance.student_id.in_(student_ids),
            Attendance.date >= week_start,
            Attendance.date <= week_end,
        ).count()
        present = Attendance.query.filter(
            Attendance.student_id.in_(student_ids),
            Attendance.date >= week_start,
            Attendance.date <= week_end,
            Attendance.status.in_(present_codes),
        ).count()
        rate = round((present / total * 100) if total else 0, 1)
        summary.append({
            "class": cls,
            "name": cls.name,
            "students": len(students),
            "present": present,
            "total": total,
            "rate": rate,
            "color": get_performance_color(rate, school_id),
        })
    summary.sort(key=lambda x: x["rate"], reverse=True)
    return summary, week_start, week_end


def build_monthly_report_text(details, school_id=None):
    """Generate strengths, weaknesses, recommendations from evaluation details."""
    strength_min = get_monthly_strength_threshold(school_id)
    weakness_max = get_monthly_weakness_threshold(school_id)
    strengths = []
    weaknesses = []
    for d in details:
        try:
            rating = int(d.rating)
        except (TypeError, ValueError):
            rating = 0
        label = d.criterion_ar or d.criterion
        if rating >= strength_min:
            strengths.append(f"{label} ({rating}/5)")
        elif rating <= weakness_max:
            weaknesses.append(f"{label} ({rating}/5)")

    templates = get_recommendation_templates(school_id)
    recs = []
    if weaknesses:
        weak_names = [
            d.criterion_ar or d.criterion for d in details
            if int(d.rating or 0) <= weakness_max
        ]
        recs.append(f"{templates['follow_up']} {', '.join(weak_names[:3])}")
        recs.append(templates["improvement_plan"])
    if not strengths and not weaknesses:
        recs.append(templates["complete_eval"])
    elif not weaknesses:
        recs.append(templates["good_performance"])

    return (
        "، ".join(strengths) if strengths else "—",
        "، ".join(weaknesses) if weaknesses else "—",
        "\n".join(recs),
    )


def monthly_evaluation_status(school_id, year=None, month=None):
    """Count students evaluated vs pending this month."""
    year = year or date.today().year
    month = month or date.today().month
    total = Student.query.filter_by(school_id=school_id, is_active=True).count()
    done = MonthlyEvaluation.query.filter_by(
        school_id=school_id, period_year=year, period_month=month,
    ).count()
    return {"total": total, "done": done, "pending": max(0, total - done)}
