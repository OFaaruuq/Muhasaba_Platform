from datetime import date, datetime, timezone

from app.extensions import db
from app.models import KPI, StudentKPI, Student
from app.kpi.calculator import calculate_kpi_score, get_period_range


def get_active_kpis(school_id=None):
    query = KPI.query.filter_by(is_active=True)
    if school_id:
        query = query.filter((KPI.school_id == school_id) | (KPI.school_id.is_(None)))
    return query.order_by(KPI.weight.desc()).all()


def recalculate_student_kpis(student_id, period="term"):
    """Sync StudentKPI cache from live data."""
    student = Student.query.get(student_id)
    if not student:
        return []

    kpis = get_active_kpis(student.school_id)
    start, end = get_period_range(student, period)
    results = []

    for kpi in kpis:
        score, detail = calculate_kpi_score(student_id, kpi.code, period)
        sk = StudentKPI.query.filter_by(
            student_id=student_id,
            kpi_id=kpi.id,
            period=period,
        ).first()

        if not sk:
            sk = StudentKPI(
                student_id=student_id,
                kpi_id=kpi.id,
                period=period,
                period_start=start,
                period_end=end,
            )
            db.session.add(sk)

        sk.score = score
        sk.period_end = end
        sk.notes = f"{detail.get('source', '')}: {detail.get('detail', '')}"
        sk.updated_at = datetime.now(timezone.utc)
        results.append({"kpi": kpi, "score": score, "detail": detail})

    db.session.commit()
    return results


def recalculate_school_kpis(school_id, period="term"):
    students = Student.query.filter_by(school_id=school_id, is_active=True).all()
    for student in students:
        recalculate_student_kpis(student.id, period)
    return len(students)


def get_student_kpi_display(student_id, period="term", auto_sync=True):
    """Return scores for display; optionally sync first."""
    student = Student.query.get(student_id)
    if not student:
        return [], 0.0, []

    if auto_sync:
        recalculate_student_kpis(student_id, period)

    from app.kpi.calculator import calculate_overall
    overall, breakdown = calculate_overall(student_id, period, student.school_id)

    scores = StudentKPI.query.filter_by(student_id=student_id, period=period).all()
    return scores, overall, breakdown
