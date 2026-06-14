"""Dynamic KPI score calculation from live platform data."""

from datetime import date, timedelta

from app.models import (
    Attendance, Evaluation, EvaluationDetail,
    ReadingAssessment, BehaviorRecord, ExamResult,
    AcademicYear, Student, EvaluationCriterion,
    MonthlyEvaluation, MonthlyEvaluationDetail,
)
from app.services.config_service import (
    get_rating_scores, get_monthly_rating_scores,
    get_present_status_codes, get_ethics_criterion_codes,
    get_homework_criterion_codes, get_reading_criterion_codes,
    get_personal_criterion_codes, get_setting, get_behavior_type_scores,
    get_kpi_source_description, get_mid_rating_score, get_default_behavior_score,
    get_reading_lesson_score, get_kpi_display_source, get_ui_label,
    get_reading_overall_aspect_code, parse_reading_aspect_scores,
    get_kpi_period_days, get_kpi_calculator_key, get_kpi_monthly_avg_detail,
)

_BUILTIN_CALCULATORS = {}


def _register_calculators():
    global _BUILTIN_CALCULATORS
    if _BUILTIN_CALCULATORS:
        return
    _BUILTIN_CALCULATORS = {
        "attendance": _calc_attendance,
        "homework": _calc_homework,
        "reading": _calc_reading,
        "exams": _calc_exams,
        "behavior": _calc_behavior,
        "participation": _calc_participation,
        "islamic_ethics": _calc_islamic_ethics,
        "monthly_eval": _calc_monthly_eval,
    }


def get_period_range(student, period="term"):
    today = date.today()
    sid = student.school_id if student else None
    if period == "daily":
        days = get_kpi_period_days("daily", sid)
        if days <= 1:
            return today, today
        return today - timedelta(days=days - 1), today
    if period == "weekly":
        days = get_kpi_period_days("weekly", sid)
        return today - timedelta(days=days), today
    if period == "monthly":
        days = get_kpi_period_days("monthly", sid)
        return today - timedelta(days=days), today

    year = AcademicYear.query.filter_by(
        school_id=student.school_id, is_current=True
    ).first()
    if year:
        return year.start_date, min(year.end_date, today)
    days = get_kpi_period_days("term", sid)
    return today - timedelta(days=days), today


def _kpi_source(kpi_code, school_id):
    return get_kpi_display_source(kpi_code, school_id)


def _no_records(school_id):
    return get_ui_label("no_records", school_id)


def _no_evaluations(school_id):
    return get_ui_label("no_evaluations", school_id)


def _ethics_detail_summary(school_id):
    codes = get_ethics_criterion_codes(school_id)
    if not codes:
        return _no_evaluations(school_id)
    criteria = EvaluationCriterion.query.filter(
        EvaluationCriterion.code.in_(codes),
        EvaluationCriterion.is_active == True,  # noqa: E712
    ).all()
    names = [c.name_ar for c in criteria][:4]
    return "، ".join(names) if names else _no_evaluations(school_id)


def calculate_kpi_score(student_id, kpi_code, period="term"):
    """Return (score, detail_dict) for one KPI."""
    student = Student.query.get(student_id)
    if not student:
        return 0.0, {"source": "—", "records": 0}

    start, end = get_period_range(student, period)
    _register_calculators()
    calc_key = get_kpi_calculator_key(kpi_code, student.school_id) or kpi_code
    calc = _BUILTIN_CALCULATORS.get(calc_key)
    if calc:
        return calc(student_id, start, end)
    return _calc_dynamic_kpi(student_id, start, end, kpi_code)


def _calc_attendance(student_id, start, end):
    student = Student.query.get(student_id)
    present_codes = get_present_status_codes(student.school_id if student else None)
    records = Attendance.query.filter(
        Attendance.student_id == student_id,
        Attendance.date >= start,
        Attendance.date <= end,
    ).all()
    sid = student.school_id if student else None
    if not records:
        return 0.0, {"source": _kpi_source("attendance", sid), "records": 0, "detail": _no_records(sid)}
    present = sum(1 for r in records if r.status in present_codes)
    score = round(present / len(records) * 100, 1)
    return score, {
        "source": _kpi_source("attendance", sid),
        "records": len(records),
        "detail": f"{present}/{len(records)}",
    }


def _rating_score(rating, school_id):
    return get_rating_scores(school_id).get(rating, get_mid_rating_score(school_id))


def _calc_homework(student_id, start, end):
    student = Student.query.get(student_id)
    sid = student.school_id if student else None
    hw_codes = get_homework_criterion_codes(sid)
    detail_query = EvaluationDetail.query.join(Evaluation).filter(
        Evaluation.student_id == student_id,
        Evaluation.date >= start,
        Evaluation.date <= end,
    )
    if hw_codes:
        detail_query = detail_query.filter(EvaluationDetail.criterion.in_(hw_codes))
    details = detail_query.all()
    if not details:
        evals = Evaluation.query.filter(
            Evaluation.student_id == student_id,
            Evaluation.date >= start,
            Evaluation.date <= end,
            Evaluation.academic_score.isnot(None),
        ).all()
        if evals:
            score = round(sum(e.academic_score for e in evals) / len(evals), 1)
            return score, {
                "source": _kpi_source("homework", sid),
                "records": len(evals),
                "detail": f"{len(evals)}",
            }
        return 0.0, {"source": _kpi_source("homework", sid), "records": 0, "detail": _no_evaluations(sid)}

    scores = [d.score or _rating_score(d.rating, sid) for d in details]
    score = round(sum(scores) / len(scores), 1)
    return score, {
        "source": _kpi_source("homework", sid),
        "records": len(details),
        "detail": f"{len(details)}",
    }


def _calc_reading(student_id, start, end):
    student = Student.query.get(student_id)
    sid = student.school_id if student else None
    rating_scores = get_rating_scores(sid)
    records = ReadingAssessment.query.filter(
        ReadingAssessment.student_id == student_id,
        ReadingAssessment.date >= start,
        ReadingAssessment.date <= end,
    ).all()
    if not records:
        reading_codes = get_reading_criterion_codes(sid)
        rq = EvaluationDetail.query.join(Evaluation).filter(
            Evaluation.student_id == student_id,
            Evaluation.date >= start,
            Evaluation.date <= end,
        )
        if reading_codes:
            rq = rq.filter(EvaluationDetail.criterion.in_(reading_codes))
        details = rq.all()
        if details:
            scores = [d.score or _rating_score(d.rating, sid) for d in details]
            return round(sum(scores) / len(scores), 1), {
                "source": _kpi_source("reading", sid),
                "records": len(details),
                "detail": f"{len(details)}",
            }
        return 0.0, {"source": _kpi_source("reading", sid), "records": 0, "detail": _no_records(sid)}

    overall_code = get_reading_overall_aspect_code(sid)
    scores = []
    for r in records:
        aspects = parse_reading_aspect_scores(r)
        overall = aspects.get(overall_code) or r.overall_rating
        if overall:
            scores.append(rating_scores.get(overall, get_mid_rating_score(sid)))
        elif aspects:
            aspect_vals = [
                rating_scores.get(v, get_mid_rating_score(sid))
                for k, v in aspects.items() if k != overall_code and v
            ]
            if aspect_vals:
                scores.append(round(sum(aspect_vals) / len(aspect_vals), 1))
        elif r.read_lesson:
            scores.append(get_reading_lesson_score(sid))
    score = round(sum(scores) / len(scores), 1) if scores else 0.0
    return score, {
        "source": _kpi_source("reading", sid),
        "records": len(records),
        "detail": f"{len(records)}",
    }


def _calc_exams(student_id, start, end):
    results = ExamResult.query.join(ExamResult.exam).filter(
        ExamResult.student_id == student_id,
        ExamResult.is_graded == True,  # noqa: E712
    ).all()
    filtered = [r for r in results if r.exam and r.exam.exam_date and start <= r.exam.exam_date <= end]
    if not filtered:
        filtered = [r for r in results if r.is_graded]
    if not filtered:
        student = Student.query.get(student_id)
        sid = student.school_id if student else None
        return 0.0, {"source": _kpi_source("exams", sid), "records": 0, "detail": _no_records(sid)}

    student = Student.query.get(student_id)
    sid = student.school_id if student else None
    score = round(sum(r.percentage or 0 for r in filtered) / len(filtered), 1)
    return score, {
        "source": _kpi_source("exams", sid),
        "records": len(filtered),
        "detail": f"{len(filtered)}",
    }


def _calc_behavior(student_id, start, end):
    evals = Evaluation.query.filter(
        Evaluation.student_id == student_id,
        Evaluation.date >= start,
        Evaluation.date <= end,
        Evaluation.behavior_score.isnot(None),
    ).all()
    behaviors = BehaviorRecord.query.filter(
        BehaviorRecord.student_id == student_id,
        BehaviorRecord.date >= start,
        BehaviorRecord.date <= end,
    ).all()

    scores = []
    if evals:
        scores.extend([e.behavior_score for e in evals])
    student = Student.query.get(student_id)
    type_scores = get_behavior_type_scores(student.school_id if student else None)
    if behaviors:
        for b in behaviors:
            if b.score is not None:
                scores.append(b.score)
            else:
                scores.append(type_scores.get(
                    b.behavior_type,
                    get_default_behavior_score(student.school_id, b.behavior_type),
                ))

    sid = student.school_id if student else None
    if not scores:
        return 0.0, {"source": _kpi_source("behavior", sid), "records": 0, "detail": _no_records(sid)}

    score = round(sum(scores) / len(scores), 1)
    return score, {
        "source": _kpi_source("behavior", sid),
        "records": len(evals) + len(behaviors),
        "detail": f"{len(evals)}+{len(behaviors)}",
    }


def _calc_participation(student_id, start, end):
    student = Student.query.get(student_id)
    sid = student.school_id if student else None
    evals = Evaluation.query.filter(
        Evaluation.student_id == student_id,
        Evaluation.date >= start,
        Evaluation.date <= end,
        Evaluation.personal_score.isnot(None),
    ).all()
    if not evals:
        personal_codes = get_personal_criterion_codes(sid)
        detail_query = EvaluationDetail.query.join(Evaluation).filter(
            Evaluation.student_id == student_id,
            Evaluation.date >= start,
            Evaluation.date <= end,
        )
        if personal_codes:
            detail_query = detail_query.filter(EvaluationDetail.criterion.in_(personal_codes))
        details = detail_query.all()
        if details:
            scores = [d.score or _rating_score(d.rating, sid) for d in details]
            return round(sum(scores) / len(scores), 1), {
                "source": _kpi_source("participation", sid),
                "records": len(details),
                "detail": f"{len(details)}",
            }
        return 0.0, {"source": _kpi_source("participation", sid), "records": 0, "detail": _no_evaluations(sid)}

    score = round(sum(e.personal_score for e in evals) / len(evals), 1)
    return score, {
        "source": _kpi_source("participation", sid),
        "records": len(evals),
        "detail": f"{len(evals)}",
    }


def _calc_islamic_ethics(student_id, start, end):
    student = Student.query.get(student_id)
    sid = student.school_id if student else None
    criteria = get_ethics_criterion_codes(sid)
    details = EvaluationDetail.query.join(Evaluation).filter(
        Evaluation.student_id == student_id,
        Evaluation.date >= start,
        Evaluation.date <= end,
        EvaluationDetail.criterion.in_(criteria),
    ).all()
    if not details:
        return 0.0, {
            "source": _kpi_source("islamic_ethics", sid),
            "records": 0,
            "detail": _no_evaluations(sid),
        }

    scores = [d.score or _rating_score(d.rating, sid) for d in details]
    score = round(sum(scores) / len(scores), 1)
    return score, {
        "source": _kpi_source("islamic_ethics", sid),
        "records": len(details),
        "detail": _ethics_detail_summary(sid),
    }


def _criterion_codes_for_kpi(kpi_code, school_id):
    query = EvaluationCriterion.query.filter_by(is_active=True, kpi_source=kpi_code)
    if school_id:
        items = query.filter_by(school_id=school_id).all()
        if items:
            return [c.code for c in items]
    return [c.code for c in query.filter_by(school_id=None).all()]


def _calc_dynamic_kpi(student_id, start, end, kpi_code):
    """Score custom KPIs from linked evaluation criteria (daily + monthly)."""
    student = Student.query.get(student_id)
    if not student:
        return 0.0, {"source": kpi_code, "records": 0}
    sid = student.school_id
    codes = _criterion_codes_for_kpi(kpi_code, sid)
    if not codes:
        return 0.0, {
            "source": get_kpi_source_description(kpi_code, sid),
            "records": 0,
            "detail": _no_evaluations(sid),
        }

    scores = []
    daily = EvaluationDetail.query.join(Evaluation).filter(
        Evaluation.student_id == student_id,
        Evaluation.date >= start,
        Evaluation.date <= end,
        EvaluationDetail.criterion.in_(codes),
    ).all()
    for d in daily:
        scores.append(d.score or _rating_score(d.rating, sid))

    monthly = MonthlyEvaluationDetail.query.join(MonthlyEvaluation).filter(
        MonthlyEvaluation.student_id == student_id,
        MonthlyEvaluationDetail.criterion.in_(codes),
    ).all()
    monthly_scores = get_monthly_rating_scores(sid)
    for d in monthly:
        scores.append(d.score or monthly_scores.get(d.rating, float(d.rating or 0) * 20))

    if not scores:
        return 0.0, {
            "source": get_kpi_source_description(kpi_code, sid),
            "records": 0,
            "detail": _no_evaluations(sid),
        }
    return round(sum(scores) / len(scores), 1), {
        "source": get_kpi_source_description(kpi_code, sid),
        "records": len(scores),
        "detail": f"{len(daily)}+{len(monthly)}",
    }


def _calc_monthly_eval(student_id, start, end):
    evals = MonthlyEvaluation.query.filter(
        MonthlyEvaluation.student_id == student_id,
    ).all()
    student = Student.query.get(student_id)
    sid = student.school_id if student else None
    if not evals:
        return 0.0, {"source": _kpi_source("monthly_eval", sid), "records": 0, "detail": _no_evaluations(sid)}
    scores = [e.overall_score for e in evals if e.overall_score is not None]
    if not scores:
        return 0.0, {"source": _kpi_source("monthly_eval", sid), "records": 0, "detail": _no_records(sid)}
    return round(sum(scores) / len(scores), 1), {
        "source": _kpi_source("monthly_eval", sid),
        "records": len(scores),
        "detail": get_kpi_monthly_avg_detail(len(scores), sid),
    }


def calculate_overall(student_id, period="term", school_id=None):
    """Calculate weighted overall from active KPIs."""
    from app.models import KPI

    query = KPI.query.filter_by(is_active=True)
    if school_id:
        query = query.filter(
            (KPI.school_id == school_id) | (KPI.school_id.is_(None))
        )
    kpis = query.all()
    if not kpis:
        return 0.0, []

    breakdown = []
    weighted_sum = 0
    active_weight = 0

    for kpi in kpis:
        score, detail = calculate_kpi_score(student_id, kpi.code, period)
        has_data = detail.get("records", 0) > 0
        breakdown.append({
            "kpi": kpi,
            "score": score,
            "detail": detail,
            "has_data": has_data,
        })
        if has_data:
            active_weight += kpi.weight
            weighted_sum += score * kpi.weight

    overall = round(weighted_sum / active_weight, 1) if active_weight else 0.0
    return overall, breakdown
