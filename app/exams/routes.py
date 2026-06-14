from datetime import date, datetime, timezone

from flask import flash, redirect, render_template, request, url_for
from app.services.message_service import flash_msg
from flask_login import login_required, current_user

from app.exams import bp
from app.extensions import db
from app.models import Exam, ExamQuestion, ExamResult, Class, Subject, Student
from app.utils import permission_required
from app.utils.notifications import notify_parent_of_student
from app.kpi.hooks import sync_kpis_for_student
from app.services.config_service import (
    get_grade_letter, get_config_choices, get_config_map, get_default_exam_total_marks,
    get_default_exam_passing_marks, get_default_exam_duration, get_default_exam_question_type,
    get_exam_types_with_options, get_notification_content,
)
from app.utils.school_context import get_active_school_id
from app.services.audit_service import log_action
from app.utils.student_context import require_linked_student


def _auto_grade(question, answer):
    if question.question_type in ("mcq", "true_false", "fill_blank"):
        correct = (question.correct_answer or "").strip().lower()
        given = (answer or "").strip().lower()
        return question.marks if correct == given else 0
    return None


@bp.route("/")
@login_required
def index():
    if current_user.is_student and current_user.student_profile:
        student = current_user.student_profile
        published = Exam.query.filter_by(
            class_id=student.class_id, is_published=True
        ).all()
        results = {r.exam_id: r for r in ExamResult.query.filter_by(student_id=student.id).all()}
        sid = student.school_id
        return render_template(
            "exams/student.html",
            exams=published,
            results=results,
            exam_type_labels=get_config_map("exam_type", sid),
        )

    sid = get_active_school_id() or current_user.school_id
    query = Exam.query
    if sid:
        query = query.filter_by(school_id=sid)
    exams = query.order_by(Exam.exam_date.desc()).all()
    return render_template(
        "exams/index.html",
        exams=exams,
        exam_type_labels=get_config_map("exam_type", sid),
    )


@bp.route("/create", methods=["GET", "POST"])
@login_required
@permission_required("manage_exams")
def create():
    from app.models import Teacher
    teacher = current_user.teacher_profile
    if not teacher and current_user.is_school_manager:
        teacher = Teacher.query.filter_by(school_id=current_user.school_id, is_active=True).first()
    classes = Class.query.filter_by(school_id=current_user.school_id).all()
    subjects = Subject.query.filter_by(school_id=current_user.school_id).all()

    if request.method == "POST":
        if not teacher:
            flash_msg("teacher_no_profile", "danger")
            return redirect(url_for("exams.create"))
        exam = Exam(
            school_id=current_user.school_id,
            class_id=int(request.form["class_id"]),
            subject_id=int(request.form["subject_id"]),
            teacher_id=teacher.id,
            title=request.form["title"],
            title_ar=request.form.get("title_ar", request.form["title"]),
            exam_type=request.form["exam_type"],
            total_marks=float(request.form.get("total_marks") or get_default_exam_total_marks(current_user.school_id)),
            passing_marks=float(request.form.get("passing_marks") or get_default_exam_passing_marks(current_user.school_id)),
            exam_date=date.fromisoformat(request.form["exam_date"]) if request.form.get("exam_date") else None,
            duration_minutes=int(request.form.get("duration_minutes") or get_default_exam_duration(current_user.school_id)),
            is_published=request.form.get("is_published") == "on",
        )
        db.session.add(exam)
        db.session.flush()

        q_texts = request.form.getlist("question_text[]")
        q_types = request.form.getlist("question_type[]")
        q_marks = request.form.getlist("question_marks[]")
        q_answers = request.form.getlist("correct_answer[]")
        q_options = request.form.getlist("options[]")

        for i, text in enumerate(q_texts):
            if not text.strip():
                continue
            opts = None
            if q_types[i] in get_exam_types_with_options(current_user.school_id) and i < len(q_options) and q_options[i]:
                opts = [o.strip() for o in q_options[i].split("|") if o.strip()]
            db.session.add(ExamQuestion(
                exam_id=exam.id,
                text=text,
                text_ar=text,
                question_type=q_types[i] if i < len(q_types) else get_default_exam_question_type(current_user.school_id),
                marks=float(q_marks[i]) if i < len(q_marks) else 1,
                correct_answer=q_answers[i] if i < len(q_answers) else None,
                options=opts,
                order=i,
            ))
        db.session.commit()
        flash_msg("exam_created", "success", sid)
        return redirect(url_for("exams.detail", exam_id=exam.id))

    sid = get_active_school_id() or current_user.school_id
    return render_template(
        "exams/create.html",
        classes=classes,
        subjects=subjects,
        exam_types=get_config_choices("exam_type", sid),
        question_types=get_config_choices("exam_question_type", sid),
        default_total_marks=get_default_exam_total_marks(sid),
        default_passing_marks=get_default_exam_passing_marks(sid),
        default_duration=get_default_exam_duration(sid),
    )


@bp.route("/<int:exam_id>")
@login_required
def detail(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    questions = exam.questions.order_by(ExamQuestion.order).all()
    results = exam.results.all() if not current_user.is_student else []
    sid = exam.school_id
    return render_template(
        "exams/detail.html",
        exam=exam,
        questions=questions,
        results=results,
        exam_type_labels=get_config_map("exam_type", sid),
        question_type_labels=get_config_map("exam_question_type", sid),
    )


@bp.route("/<int:exam_id>/take", methods=["GET", "POST"])
@login_required
@permission_required("take_exams")
def take(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    student, redirect_resp = require_linked_student()
    if redirect_resp:
        return redirect_resp
    if not exam.is_published:
        flash_msg("exam_not_published", "danger")
        return redirect(url_for("exams.index"))

    existing = ExamResult.query.filter_by(exam_id=exam.id, student_id=student.id).first()
    if existing and existing.is_graded:
        flash_msg("exam_already_taken", "info")
        return redirect(url_for("exams.index"))

    questions = exam.questions.order_by(ExamQuestion.order).all()

    if request.method == "POST":
        answers = {}
        total_score = 0
        needs_manual = False

        for q in questions:
            ans = request.form.get(f"q_{q.id}", "")
            answers[str(q.id)] = ans
            auto = _auto_grade(q, ans)
            if auto is not None:
                total_score += auto
            else:
                needs_manual = True

        pct = round(total_score / exam.total_marks * 100, 1) if exam.total_marks else 0

        if existing:
            result = existing
        else:
            result = ExamResult(exam_id=exam.id, student_id=student.id)
            db.session.add(result)

        result.score = total_score
        result.percentage = pct
        result.grade_letter = get_grade_letter(pct, student.school_id)
        result.answers = answers
        result.is_graded = not needs_manual
        result.submitted_at = datetime.now(timezone.utc)
        if not needs_manual:
            result.graded_at = datetime.now(timezone.utc)

        log_action(
            "submit_exam", "exams",
            f"exam={exam.id} student={student.id} score={pct}%",
        )
        db.session.commit()
        sync_kpis_for_student(student.id)

        title, message, ntype = get_notification_content(
            "exam", student.school_id,
            student=student.full_name_ar, score=pct, exam=exam.title_ar or exam.title,
        )
        notify_parent_of_student(student, title, message, ntype, url_for("exams.index"))
        db.session.commit()

        flash_msg("exam_submitted", "success", pct=pct)
        return redirect(url_for("exams.index"))

    return render_template("exams/take.html", exam=exam, questions=questions)


@bp.route("/<int:exam_id>/grade/<int:result_id>", methods=["POST"])
@login_required
@permission_required("manage_exams")
def grade_essay(exam_id, result_id):
    result = ExamResult.query.get_or_404(result_id)
    exam = Exam.query.get_or_404(exam_id)
    essay_score = float(request.form.get("essay_score", 0))
    result.score = (result.score or 0) + essay_score
    result.percentage = round(result.score / exam.total_marks * 100, 1)
    result.grade_letter = get_grade_letter(result.percentage, result.student.school_id)
    result.is_graded = True
    result.graded_at = datetime.now(timezone.utc)
    log_action(
        "grade_exam", "exams",
        f"exam={exam_id} result={result_id} score={result.percentage}%",
    )
    db.session.commit()
    sync_kpis_for_student(result.student_id)
    flash_msg("exam_graded", "success", sid)
    return redirect(url_for("exams.detail", exam_id=exam.id))
