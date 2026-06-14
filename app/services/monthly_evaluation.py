"""Monthly evaluation save logic."""

from app.extensions import db
from app.models import MonthlyEvaluation, MonthlyEvaluationDetail
from app.services.config_service import (
    get_monthly_criteria_grouped, get_monthly_rating_scores,
    get_monthly_category_score_fields, get_default_monthly_rating,
)
from app.services.monitoring_analytics import build_monthly_report_text


def save_monthly_evaluation(student, teacher, year, month, form):
    """Persist monthly evaluation from POST form."""
    sid = student.school_id
    criteria_grouped = get_monthly_criteria_grouped(sid)
    rating_scores = get_monthly_rating_scores(sid)

    evaluation = MonthlyEvaluation.query.filter_by(
        student_id=student.id, period_year=year, period_month=month,
    ).first()
    if not evaluation:
        evaluation = MonthlyEvaluation(
            student_id=student.id,
            teacher_id=teacher.id,
            school_id=sid,
            period_year=year,
            period_month=month,
        )
        db.session.add(evaluation)
        db.session.flush()

    category_scores = {}
    all_details = []

    for category, criteria_list in criteria_grouped.items():
        scores = []
        for crit in criteria_list:
            rating = form.get(f"{category}_{crit.code}", get_default_monthly_rating(sid))
            MonthlyEvaluationDetail.query.filter_by(
                evaluation_id=evaluation.id, criterion=crit.code,
            ).delete()
            detail = MonthlyEvaluationDetail(
                evaluation_id=evaluation.id,
                category=category,
                criterion=crit.code,
                criterion_ar=crit.name_ar,
                rating=rating,
                score=rating_scores.get(
                    rating,
                    rating_scores.get(get_default_monthly_rating(sid), 60),
                ),
            )
            db.session.add(detail)
            all_details.append(detail)
            scores.append(detail.score)

        category_scores[category] = round(sum(scores) / len(scores), 1) if scores else 0

    for cat, field in get_monthly_category_score_fields(sid).items():
        setattr(evaluation, field, category_scores.get(cat, 0))

    all_scores = [v for v in category_scores.values() if v]
    evaluation.overall_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
    evaluation.notes = form.get("notes", "")

    strengths, weaknesses, recommendations = build_monthly_report_text(all_details, sid)
    evaluation.strengths = form.get("strengths") or strengths
    evaluation.weaknesses = form.get("weaknesses") or weaknesses
    evaluation.recommendations = form.get("recommendations") or recommendations

    db.session.commit()
    return evaluation
