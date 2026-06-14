"""Dynamic KPI index page: school summaries, student rows, filters."""

from app.models import Class, Student
from app.services.teacher_student_service import students_for_teacher, classes_for_teacher


def classes_for_kpi_filter(user, school_id):
    if user.is_teacher and user.teacher_profile:
        return classes_for_teacher(user.teacher_profile, school_id=school_id)
    if not school_id:
        return []
    return Class.query.filter_by(school_id=school_id).order_by(Class.name).all()


def students_for_kpi_index(user, school_id, class_id=None, search=None):
    if user.is_teacher and user.teacher_profile:
        return students_for_teacher(
            user.teacher_profile,
            class_id=class_id,
            search=search,
        )

    if user.is_student and user.student_profile:
        return [user.student_profile]

    if not school_id:
        return []

    query = Student.query.filter_by(school_id=school_id, is_active=True)
    if class_id:
        query = query.filter_by(class_id=class_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            Student.full_name_ar.ilike(term) | Student.student_id.ilike(term)
        )
    return query.order_by(Student.full_name_ar).all()


def build_students_kpi_rows(students, kpis, period):
    from app.kpi.calculator import calculate_overall

    rows = []
    for student in students:
        overall, breakdown = calculate_overall(student.id, period, student.school_id)
        by_code = {item["kpi"].code: item for item in breakdown}
        rows.append({
            "student": student,
            "overall": overall,
            "kpi_scores": {kpi.code: by_code.get(kpi.code) for kpi in kpis},
        })
    return rows


def build_kpi_summaries(rows, kpis):
    summaries = []
    for kpi in kpis:
        scores = []
        for row in rows:
            item = row["kpi_scores"].get(kpi.code)
            if item and item.get("has_data"):
                scores.append(item["score"])
        avg = round(sum(scores) / len(scores), 1) if scores else None
        summaries.append({
            "kpi": kpi,
            "average": avg,
            "students_with_data": len(scores),
            "total_students": len(rows),
        })
    return summaries
