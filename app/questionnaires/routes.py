from datetime import date

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user

from app.questionnaires import bp
from app.extensions import db
from app.models import (
    Questionnaire, Question, Choice, StudentAnswer, Class, Student,
)
from app.utils import permission_required
from app.utils.school_context import get_active_school_id
from app.services.config_service import (
    get_config_choices, get_config_map, get_default_questionnaire_category,
)
from app.services.questionnaire_service import (
    questionnaires_for_school,
    questionnaires_for_student,
    get_completion,
    can_student_take,
    response_summary,
    analyze_question,
    format_answer,
    eligible_students,
    save_questions_from_form,
)


def _school_id():
    return get_active_school_id() or current_user.school_id


def _check_access(questionnaire):
    if current_user.is_platform_admin:
        return None
    if current_user.school_id and questionnaire.school_id != current_user.school_id:
        flash("ليس لديك صلاحية لهذا الاستبيان.", "danger")
        return redirect(url_for("questionnaires.index"))
    return None


def _can_manage(questionnaire):
    if not current_user.has_permission("manage_questionnaires"):
        return False
    if current_user.is_platform_admin or current_user.is_school_manager:
        return True
    if current_user.is_teacher and current_user.teacher_profile:
        return questionnaire.teacher_id == current_user.teacher_profile.id
    return current_user.has_permission("manage_questionnaires")


@bp.route("/")
@login_required
def index():
    sid = _school_id()

    if current_user.is_student and current_user.student_profile:
        student = current_user.student_profile
        questionnaires = questionnaires_for_student(student).all()
        completion_map = {q.id: get_completion(student.id, q) for q in questionnaires}
        return render_template(
            "questionnaires/student.html",
            questionnaires=questionnaires,
            completion_map=completion_map,
            category_labels=get_config_map("questionnaire_category", student.school_id),
        )

    if current_user.is_parent and current_user.parent_profile:
        children = current_user.parent_profile.children
        children_data = []
        for child in children:
            qs = questionnaires_for_student(child).all()
            children_data.append({
                "student": child,
                "questionnaires": [
                    {"q": q, "completion": get_completion(child.id, q)}
                    for q in qs
                ],
            })
        return render_template(
            "questionnaires/parent.html",
            children_data=children_data,
            category_labels=get_config_map("questionnaire_category", sid),
        )

    questionnaires = questionnaires_for_school(sid, active_only=False).all()
    summaries = {q.id: response_summary(q) for q in questionnaires}
    return render_template(
        "questionnaires/index.html",
        questionnaires=questionnaires,
        summaries=summaries,
        category_labels=get_config_map("questionnaire_category", sid),
        can_manage_fn=_can_manage,
        today=date.today(),
    )


@bp.route("/create", methods=["GET", "POST"])
@login_required
@permission_required("manage_questionnaires")
def create():
    from app.models import Teacher
    sid = _school_id() or current_user.school_id
    teacher = current_user.teacher_profile
    if not teacher and (current_user.is_school_manager or current_user.is_ministry_admin):
        teacher = Teacher.query.filter_by(school_id=sid, is_active=True).first()
    if not teacher:
        flash("لا يوجد معلم مرتبط.", "danger")
        return redirect(url_for("questionnaires.index"))

    classes = Class.query.filter_by(school_id=sid).order_by(Class.name).all()

    if request.method == "POST":
        q = Questionnaire(
            school_id=sid,
            teacher_id=teacher.id,
            class_id=request.form.get("class_id", type=int) or None,
            title=request.form["title"],
            title_ar=request.form.get("title_ar") or request.form["title"],
            description=request.form.get("description"),
            category=request.form.get("category") or get_default_questionnaire_category(sid),
            due_date=date.fromisoformat(request.form["due_date"]) if request.form.get("due_date") else None,
            is_active=request.form.get("is_active", "on") == "on",
        )
        db.session.add(q)
        db.session.flush()
        save_questions_from_form(q, request.form)
        db.session.commit()
        flash("تم إنشاء الاستبيان.", "success")
        return redirect(url_for("questionnaires.detail", questionnaire_id=q.id))

    return render_template(
        "questionnaires/create.html",
        classes=classes,
        categories=get_config_choices("questionnaire_category", sid),
        question_types=get_config_choices("questionnaire_question_type", sid),
        questionnaire=None,
    )


@bp.route("/<int:questionnaire_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_questionnaires")
def edit(questionnaire_id):
    q = Questionnaire.query.get_or_404(questionnaire_id)
    denied = _check_access(q)
    if denied:
        return denied
    if not _can_manage(q):
        flash("ليس لديك صلاحية التعديل.", "danger")
        return redirect(url_for("questionnaires.detail", questionnaire_id=q.id))

    classes = Class.query.filter_by(school_id=q.school_id).order_by(Class.name).all()

    if request.method == "POST":
        q.title = request.form["title"]
        q.title_ar = request.form.get("title_ar") or q.title
        q.description = request.form.get("description")
        q.category = request.form.get("category", q.category)
        q.class_id = request.form.get("class_id", type=int) or None
        q.due_date = date.fromisoformat(request.form["due_date"]) if request.form.get("due_date") else None
        q.is_active = request.form.get("is_active", "on") == "on"

        for question in q.questions.all():
            StudentAnswer.query.filter_by(question_id=question.id).delete()
            Choice.query.filter_by(question_id=question.id).delete()
            db.session.delete(question)
        db.session.flush()

        save_questions_from_form(q, request.form)
        db.session.commit()
        flash("تم تحديث الاستبيان.", "success")
        return redirect(url_for("questionnaires.detail", questionnaire_id=q.id))

    questions = q.questions.order_by(Question.order).all()
    questions_data = []
    for qn in questions:
        choices_text = " | ".join(
            c.text_ar or c.text for c in qn.choices.order_by(Choice.order).all()
        )
        questions_data.append({
            "text": qn.text_ar or qn.text,
            "type": qn.question_type,
            "required": qn.is_required,
            "choices": choices_text,
        })
    return render_template(
        "questionnaires/create.html",
        classes=classes,
        categories=get_config_choices("questionnaire_category", q.school_id),
        question_types=get_config_choices("questionnaire_question_type", q.school_id),
        questionnaire=q,
        questions_data=questions_data,
    )


@bp.route("/<int:questionnaire_id>/toggle", methods=["POST"])
@login_required
@permission_required("manage_questionnaires")
def toggle(questionnaire_id):
    q = Questionnaire.query.get_or_404(questionnaire_id)
    denied = _check_access(q)
    if denied:
        return denied
    if not _can_manage(q):
        flash("ليس لديك صلاحية.", "danger")
        return redirect(url_for("questionnaires.index"))
    q.is_active = not q.is_active
    db.session.commit()
    flash("تم تحديث حالة الاستبيان.", "success")
    return redirect(url_for("questionnaires.index"))


@bp.route("/<int:questionnaire_id>")
@login_required
def detail(questionnaire_id):
    q = Questionnaire.query.get_or_404(questionnaire_id)
    denied = _check_access(q)
    if denied:
        return denied

    questions = q.questions.order_by(Question.order).all()
    summary = response_summary(q)
    type_labels = get_config_map("questionnaire_question_type", q.school_id)
    category_labels = get_config_map("questionnaire_category", q.school_id)

    student_completion = None
    if current_user.is_student and current_user.student_profile:
        student_completion = get_completion(current_user.student_profile.id, q)

    return render_template(
        "questionnaires/detail.html",
        questionnaire=q,
        questions=questions,
        summary=summary,
        type_labels=type_labels,
        category_labels=category_labels,
        student_completion=student_completion,
        can_manage=_can_manage(q),
    )


@bp.route("/<int:questionnaire_id>/take", methods=["GET", "POST"])
@login_required
@permission_required("take_questionnaires")
def take(questionnaire_id):
    q = Questionnaire.query.get_or_404(questionnaire_id)
    from app.utils.student_context import require_linked_student
    student, redirect_resp = require_linked_student("questionnaires.index")
    if redirect_resp:
        return redirect_resp
    ok, msg = can_student_take(student, q)
    if not ok:
        flash(msg, "warning" if "مسبقاً" in msg else "danger")
        return redirect(url_for("questionnaires.index"))

    questions = q.questions.order_by(Question.order).all()

    if request.method == "POST":
        for question in questions:
            if StudentAnswer.query.filter_by(
                student_id=student.id, question_id=question.id
            ).first():
                continue

            val = request.form.get(f"q_{question.id}")
            if question.is_required and not val:
                flash(f"يرجى الإجابة على: {question.text_ar or question.text}", "danger")
                return redirect(url_for("questionnaires.take", questionnaire_id=q.id))

            answer = StudentAnswer(student_id=student.id, question_id=question.id)
            if question.question_type == "multiple_choice":
                answer.choice_id = int(val) if val else None
            elif question.question_type == "rating":
                answer.rating_value = int(val) if val else None
            elif question.question_type == "yes_no":
                answer.text_answer = val
            else:
                answer.text_answer = val or ""
            db.session.add(answer)
        db.session.commit()
        flash("تم إرسال إجاباتك.", "success")
        return redirect(url_for("questionnaires.index"))

    answered_ids = {
        a.question_id
        for a in StudentAnswer.query.filter_by(student_id=student.id).all()
    }
    completion = get_completion(student.id, q)
    return render_template(
        "questionnaires/take.html",
        questionnaire=q,
        questions=questions,
        answered_ids=answered_ids,
        completion=completion,
    )


@bp.route("/<int:questionnaire_id>/results")
@login_required
@permission_required("manage_questionnaires")
def results(questionnaire_id):
    q = Questionnaire.query.get_or_404(questionnaire_id)
    denied = _check_access(q)
    if denied:
        return denied

    sid = q.school_id
    yes_no_map = get_config_map("yes_no", sid)
    from app.services.config_service import get_monthly_rating_choices
    rating_labels = {code: name for code, name in get_monthly_rating_choices(sid)}

    questions = q.questions.order_by(Question.order).all()
    results_data = []
    for question in questions:
        stats = analyze_question(question, yes_no_map, rating_labels)
        rows = []
        for ans in stats["answers"]:
            rows.append({
                "student": ans.student,
                "display": format_answer(ans, question, yes_no_map, rating_labels),
            })
        results_data.append({
            "question": question,
            "stats": stats,
            "rows": rows,
        })

    summary = response_summary(q)
    students = eligible_students(q)
    student_status = []
    for s in students:
        comp = get_completion(s.id, q)
        student_status.append({"student": s, "completion": comp})

    return render_template(
        "questionnaires/results.html",
        questionnaire=q,
        results_data=results_data,
        summary=summary,
        student_status=student_status,
        type_labels=get_config_map("questionnaire_question_type", sid),
        category_labels=get_config_map("questionnaire_category", sid),
    )
