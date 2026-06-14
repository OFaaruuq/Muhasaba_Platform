"""Questionnaire listing, eligibility, completion, and analytics."""

from collections import Counter, defaultdict

from sqlalchemy import or_

from app.extensions import db
from app.models import Questionnaire, Question, Student, StudentAnswer


def questionnaires_for_school(school_id, active_only=True):
    q = Questionnaire.query
    if active_only:
        q = q.filter_by(is_active=True)
    if school_id:
        q = q.filter_by(school_id=school_id)
    return q.order_by(Questionnaire.created_at.desc())


def questionnaires_for_student(student, active_only=True):
    q = Questionnaire.query.filter_by(school_id=student.school_id)
    if active_only:
        q = q.filter_by(is_active=True)
    q = q.filter(
        or_(Questionnaire.class_id.is_(None), Questionnaire.class_id == student.class_id)
    )
    return q.order_by(Questionnaire.due_date.desc().nullslast(), Questionnaire.created_at.desc())


def eligible_students(questionnaire):
    q = Student.query.filter_by(school_id=questionnaire.school_id, is_active=True)
    if questionnaire.class_id:
        q = q.filter_by(class_id=questionnaire.class_id)
    return q.order_by(Student.full_name_ar).all()


def get_completion(student_id, questionnaire):
    questions = questionnaire.questions.order_by(Question.order).all()
    if not questions:
        return {"total": 0, "answered": 0, "complete": False, "percent": 0}

    q_ids = [qn.id for qn in questions]
    answered = StudentAnswer.query.filter(
        StudentAnswer.student_id == student_id,
        StudentAnswer.question_id.in_(q_ids),
    ).count()
    total = len(q_ids)
    return {
        "total": total,
        "answered": answered,
        "complete": answered >= total,
        "percent": round(answered / total * 100) if total else 0,
    }


def can_student_take(student, questionnaire):
    if not questionnaire.is_active:
        return False, "الاستبيان غير متاح."
    if questionnaire.class_id and student.class_id != questionnaire.class_id:
        return False, "هذا الاستبيان مخصص لفصل آخر."
    completion = get_completion(student.id, questionnaire)
    if completion["complete"]:
        return False, "لقد أجبت على هذا الاستبيان مسبقاً."
    return True, None


def response_summary(questionnaire):
    students = eligible_students(questionnaire)
    questions = questionnaire.questions.order_by(Question.order).all()
    if not students or not questions:
        return {
            "eligible": len(students),
            "completed": 0,
            "rate": 0,
            "in_progress": 0,
        }

    q_ids = [qn.id for qn in questions]
    completed = 0
    in_progress = 0
    for s in students:
        count = StudentAnswer.query.filter(
            StudentAnswer.student_id == s.id,
            StudentAnswer.question_id.in_(q_ids),
        ).count()
        if count >= len(q_ids):
            completed += 1
        elif count > 0:
            in_progress += 1

    eligible = len(students)
    return {
        "eligible": eligible,
        "completed": completed,
        "in_progress": in_progress,
        "rate": round(completed / eligible * 100) if eligible else 0,
    }


def analyze_question(question, yes_no_labels=None, rating_labels=None):
    """Build display-ready stats for a single question."""
    answers = question.answers.all()
    yes_no_labels = yes_no_labels or {}
    rating_labels = rating_labels or {}

    if question.question_type == "yes_no":
        counts = Counter(a.text_answer for a in answers if a.text_answer)
        total = sum(counts.values())
        breakdown = []
        if yes_no_labels:
            for code, label in yes_no_labels.items():
                cnt = counts.get(code, 0)
                breakdown.append({
                    "label": label,
                    "code": code,
                    "count": cnt,
                    "percent": round(cnt / total * 100) if total else 0,
                })
        else:
            for code, cnt in counts.items():
                breakdown.append({
                    "label": code,
                    "code": code,
                    "count": cnt,
                    "percent": round(cnt / total * 100) if total else 0,
                })
        return {"type": "yes_no", "total": total, "breakdown": breakdown, "answers": answers}

    if question.question_type == "rating":
        values = [a.rating_value for a in answers if a.rating_value is not None]
        total = len(values)
        dist = Counter(values)
        breakdown = []
        for val in sorted(dist.keys()):
            cnt = dist[val]
            breakdown.append({
                "label": rating_labels.get(str(val), str(val)),
                "code": str(val),
                "count": cnt,
                "percent": round(cnt / total * 100) if total else 0,
            })
        avg = round(sum(values) / total, 2) if total else 0
        return {
            "type": "rating",
            "total": total,
            "average": avg,
            "breakdown": breakdown,
            "answers": answers,
        }

    if question.question_type == "multiple_choice":
        counts = Counter(a.choice_id for a in answers if a.choice_id)
        total = sum(counts.values())
        breakdown = []
        for choice in question.choices.order_by("order"):
            cnt = counts.get(choice.id, 0)
            breakdown.append({
                "label": choice.text_ar or choice.text,
                "code": str(choice.id),
                "count": cnt,
                "percent": round(cnt / total * 100) if total else 0,
            })
        return {"type": "multiple_choice", "total": total, "breakdown": breakdown, "answers": answers}

    return {"type": "text", "total": len(answers), "breakdown": [], "answers": answers}


def format_answer(answer, question, yes_no_map=None, rating_map=None):
    if not answer:
        return "—"
    if question.question_type == "multiple_choice" and answer.choice:
        return answer.choice.text_ar or answer.choice.text
    if question.question_type == "rating" and answer.rating_value is not None:
        label = (rating_map or {}).get(str(answer.rating_value))
        return f"{answer.rating_value}" + (f" — {label}" if label else "")
    if question.question_type == "yes_no" and answer.text_answer:
        return (yes_no_map or {}).get(answer.text_answer, answer.text_answer)
    return answer.text_answer or "—"


def parse_choice_options(form, index):
    """Parse multiple-choice options from form (pipe-separated, parallel choices[] array)."""
    raw_list = form.getlist("choices[]")
    if index < len(raw_list) and raw_list[index]:
        return [x.strip() for x in raw_list[index].split("|") if x.strip()]
    legacy = form.getlist(f"choices_{index}[]")
    opts = []
    for part in legacy:
        opts.extend([x.strip() for x in part.split("|") if x.strip()])
    return opts


def save_questions_from_form(questionnaire, form):
    """Create questions and choices from create/edit form data."""
    questions_text = form.getlist("question_text[]")
    question_types = form.getlist("question_type[]")
    required_flags = form.getlist("question_required[]")

    for i, text in enumerate(questions_text):
        if not text.strip():
            continue
        qtype = question_types[i] if i < len(question_types) else "text"
        required = required_flags[i] == "1" if i < len(required_flags) else True
        question = Question(
            questionnaire_id=questionnaire.id,
            text=text,
            text_ar=text,
            question_type=qtype,
            order=i,
            is_required=required,
        )
        db.session.add(question)
        db.session.flush()

        if qtype == "multiple_choice":
            for j, opt in enumerate(parse_choice_options(form, i)):
                db.session.add(Choice(
                    question_id=question.id,
                    text=opt,
                    text_ar=opt,
                    order=j,
                ))
