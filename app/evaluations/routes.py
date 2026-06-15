from datetime import date

from flask import flash, jsonify, redirect, render_template, request, url_for
from app.services.message_service import flash_msg
from flask_login import login_required, current_user

from app.evaluations import bp
from app.extensions import db
from app.models import (
    Evaluation, EvaluationDetail, Student, StudentSelfAssessment,
    ReadingAssessment, BehaviorRecord, MonthlyEvaluation,
    Grade, Class, Teacher,
)
from app.services.config_service import (
    get_criteria_grouped, get_rating_choices, get_rating_scores,
    get_behavior_categories, get_config_choices, get_reading_aspects,
    get_self_assessment_items, get_criterion_category_labels,
    get_default_rating_code, get_config_map,
    get_monthly_criteria_grouped, get_monthly_rating_choices,
    get_monthly_category_labels, get_default_monthly_rating,
    get_performance_color, get_daily_category_field_map, get_mid_rating_score,
    get_behavior_type_scores, get_default_behavior_score, get_default_behavior_type,
    get_performance_label, get_monthly_scale_summary, get_unspecified_label,
    build_reading_assessment, get_notification_content,
    get_reading_overall_aspect_code, parse_reading_aspect_scores,
)
from app.services.monthly_evaluation import save_monthly_evaluation
from app.services.monitoring_analytics import monthly_evaluation_status
from app.utils.notifications import notify_parent_of_student
from app.kpi.hooks import sync_kpis_for_student
from app.students.registration import (
    registration_template_context, process_registration,
)
from app.academic.routes import (
    api_grades as academic_api_grades,
    api_classes as academic_api_classes,
    api_teachers as academic_api_teachers,
    api_create_grade as academic_api_create_grade,
    api_create_class as academic_api_create_class,
    api_create_teacher as academic_api_create_teacher,
    api_create_school as academic_api_create_school,
)
from app.utils import permission_required
from app.utils.school_context import get_active_school_id
from app.utils.student_context import require_linked_student
from app.services.audit_service import log_action
from app.services.teacher_student_service import students_for_teacher, classes_for_teacher


@bp.route("/")
@login_required
def index():
    if current_user.is_student:
        return redirect(url_for("evaluations.self_assess"))

    today = date.today()
    mode = request.args.get("mode", "daily")
    period_year = request.args.get("year", today.year, type=int)
    period_month = request.args.get("month", today.month, type=int)
    grade_id = request.args.get("grade_id", type=int)
    class_id = request.args.get("class_id", type=int)

    evaluations = []
    students = []
    grouped = {}
    grades = []
    classes = []

    if current_user.is_teacher and current_user.teacher_profile:
        teacher = current_user.teacher_profile
        evaluations = Evaluation.query.filter_by(
            teacher_id=teacher.id
        ).order_by(Evaluation.date.desc()).limit(20).all()

        students = students_for_teacher(teacher, grade_id=grade_id, class_id=class_id)
        teacher_classes = classes_for_teacher(teacher)
        teacher_class_ids = [c.id for c in teacher_classes]
        if teacher_class_ids:
            grades = Grade.query.join(Class).filter(
                Class.id.in_(teacher_class_ids)
            ).distinct().order_by(Grade.level).all()
            class_query = Class.query.filter(Class.id.in_(teacher_class_ids))
            if grade_id:
                class_query = class_query.filter_by(grade_id=grade_id)
            classes = class_query.order_by(Class.name).all()

    elif current_user.is_school_manager or current_user.is_platform_admin:
        query = Evaluation.query
        if not current_user.is_platform_admin:
            query = query.filter_by(school_id=current_user.school_id)
        evaluations = query.order_by(Evaluation.date.desc()).limit(20).all()

        sid = get_active_school_id() or current_user.school_id
        if sid:
            grades = Grade.query.filter_by(school_id=sid).order_by(Grade.level).all()
            student_query = Student.query.filter_by(school_id=sid, is_active=True)
            if grade_id:
                student_query = student_query.filter_by(grade_id=grade_id)
            if class_id:
                student_query = student_query.filter_by(class_id=class_id)
            students = student_query.order_by(Student.grade_id, Student.class_id).all()
            class_query = Class.query.filter_by(school_id=sid)
            if grade_id:
                class_query = class_query.filter_by(grade_id=grade_id)
            classes = class_query.order_by(Class.name).all()

    period_evals = {}
    if students:
        student_ids = [s.id for s in students]
        if mode == "monthly":
            for ev in MonthlyEvaluation.query.filter(
                MonthlyEvaluation.student_id.in_(student_ids),
                MonthlyEvaluation.period_year == period_year,
                MonthlyEvaluation.period_month == period_month,
            ).all():
                period_evals[ev.student_id] = ev
        else:
            for ev in Evaluation.query.filter(
                Evaluation.student_id.in_(student_ids),
                Evaluation.date == today,
            ).all():
                period_evals[ev.student_id] = ev

    ctx_school_id = students[0].school_id if students else (get_active_school_id() or current_user.school_id)
    unspecified = get_unspecified_label(ctx_school_id)
    for student in students:
        level_key = student.grade.name_ar if student.grade else unspecified
        class_key = student.class_.name if student.class_ else unspecified
        ev = period_evals.get(student.id)
        score = None
        if ev:
            score = ev.overall_score if mode == "monthly" else ev.daily_score
        grouped.setdefault(level_key, {}).setdefault(class_key, []).append({
            "student": student,
            "evaluated": student.id in period_evals,
            "score": score,
            "color": get_performance_color(score, student.school_id) if score else None,
            "perf_label": get_performance_label(score, student.school_id) if score else None,
        })

    can_register = current_user.is_platform_admin or current_user.is_school_manager
    sid = get_active_school_id() or current_user.school_id
    month_status = monthly_evaluation_status(sid, period_year, period_month) if sid else None

    return render_template(
        "evaluations/index.html",
        evaluations=evaluations,
        grouped=grouped,
        grades=grades,
        classes=classes,
        selected_grade=grade_id,
        selected_class=class_id,
        today=today,
        mode=mode,
        period_year=period_year,
        period_month=period_month,
        month_status=month_status,
        can_register=can_register,
        monthly_scale_summary=get_monthly_scale_summary(sid),
    )


@bp.route("/register", methods=["GET", "POST"])
@login_required
@permission_required("register_students")
def register():
    register_url = url_for("evaluations.register")

    if request.method == "POST":
        return process_registration(request.form, register_url)

    return render_template(
        "evaluations/register.html",
        **registration_template_context(),
    )


@bp.route("/api/grades")
def api_grades():
    return academic_api_grades()


@bp.route("/api/classes")
def api_classes():
    return academic_api_classes()


@bp.route("/api/teachers")
def api_teachers():
    return academic_api_teachers()


@bp.route("/api/grade", methods=["POST"])
def api_create_grade():
    return academic_api_create_grade()


@bp.route("/api/class", methods=["POST"])
def api_create_class():
    return academic_api_create_class()


@bp.route("/api/teacher", methods=["POST"])
def api_create_teacher():
    return academic_api_create_teacher()


@bp.route("/api/school", methods=["POST"])
def api_create_school():
    return academic_api_create_school()


@bp.route("/monthly/<int:student_id>", methods=["GET", "POST"])
@login_required
@permission_required("manage_evaluations")
def monthly(student_id):
    student = Student.query.get_or_404(student_id)
    teacher = _resolve_evaluation_teacher(student)
    if not teacher:
        flash_msg("teacher_no_profile", "danger")
        return redirect(url_for("evaluations.index", mode="monthly"))

    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)

    if request.method == "POST":
        evaluation = save_monthly_evaluation(student, teacher, year, month, request.form)
        log_action(
            "save_monthly_evaluation", "evaluations",
            f"student={student_id} {year}-{month} score={evaluation.overall_score}",
        )
        sync_kpis_for_student(student_id)
        title, message, ntype = get_notification_content(
            "monthly", student.school_id,
            student=student.full_name_ar, month=month, year=year, score=evaluation.overall_score,
        )
        notify_parent_of_student(
            student, title, message, ntype,
            url_for("students.profile", student_id=student.id),
        )
        db.session.commit()
        flash_msg("eval_monthly_saved", "success", student.school_id)
        return redirect(url_for("evaluations.index", mode="monthly", year=year, month=month))

    evaluation = MonthlyEvaluation.query.filter_by(
        student_id=student_id, period_year=year, period_month=month,
    ).first()
    existing = {}
    if evaluation:
        for detail in evaluation.details:
            existing[detail.criterion] = detail.rating

    sid = student.school_id
    criteria_tpl = {
        cat: [(c.code, c.name_ar) for c in items]
        for cat, items in get_monthly_criteria_grouped(sid).items()
    }
    return render_template(
        "evaluations/monthly.html",
        student=student,
        criteria=criteria_tpl,
        ratings=get_monthly_rating_choices(sid),
        category_labels=get_monthly_category_labels(sid),
        default_rating=get_default_monthly_rating(sid),
        existing=existing,
        evaluation=evaluation,
        period_year=year,
        period_month=month,
    )


@bp.route("/daily/<int:student_id>", methods=["GET", "POST"])
@login_required
@permission_required("manage_evaluations")
def daily(student_id):
    student = Student.query.get_or_404(student_id)
    teacher = _resolve_evaluation_teacher(student)
    today = date.today()

    if request.method == "POST":
        if not teacher:
            flash_msg("teacher_no_profile", "danger")
            return redirect(url_for("evaluations.index"))
        evaluation = Evaluation.query.filter_by(student_id=student_id, date=today).first()
        if not evaluation:
            evaluation = Evaluation(
                student_id=student_id,
                teacher_id=teacher.id,
                school_id=student.school_id,
                date=today,
            )
            db.session.add(evaluation)
            db.session.flush()

        sid = student.school_id
        criteria_grouped = get_criteria_grouped(sid)
        rating_scores = get_rating_scores(sid)
        category_scores = {}
        for category, criteria_list in criteria_grouped.items():
            scores = []
            for crit in criteria_list:
                rating = request.form.get(
                    f"{category}_{crit.code}", get_default_rating_code(sid),
                )
                EvaluationDetail.query.filter_by(
                    evaluation_id=evaluation.id, criterion=crit.code
                ).delete()
                db.session.add(EvaluationDetail(
                    evaluation_id=evaluation.id,
                    category=category,
                    criterion=crit.code,
                    criterion_ar=crit.name_ar,
                    rating=rating,
                    score=rating_scores.get(rating, get_mid_rating_score(sid)),
                ))
                scores.append(rating_scores.get(rating, get_mid_rating_score(sid)))
            category_scores[category] = sum(scores) / len(scores) if scores else 0

        field_map = get_daily_category_field_map(sid)
        for cat, field in field_map.items():
            setattr(evaluation, field, category_scores.get(cat, 0))
        cat_values = [category_scores.get(c, 0) for c in field_map]
        evaluation.daily_score = round(
            sum(cat_values) / len(cat_values), 1
        ) if cat_values else 0
        evaluation.notes = request.form.get("notes", "")
        log_action(
            "save_daily_evaluation", "evaluations",
            f"student={student_id} score={evaluation.daily_score}",
        )
        db.session.commit()
        sync_kpis_for_student(student_id)
        title, message, ntype = get_notification_content(
            "daily", student.school_id,
            student=student.full_name_ar, score=evaluation.daily_score,
        )
        notify_parent_of_student(
            student, title, message, ntype,
            url_for("students.profile", student_id=student.id),
        )
        db.session.commit()
        flash_msg("eval_daily_saved", "success", sid)
        return redirect(url_for("evaluations.index"))

    evaluation = Evaluation.query.filter_by(student_id=student_id, date=today).first()
    existing = {}
    if evaluation:
        for detail in evaluation.details:
            existing[detail.criterion] = detail.rating

    sid = student.school_id
    criteria_tpl = {
        cat: [(c.code, c.name_ar) for c in items]
        for cat, items in get_criteria_grouped(sid).items()
    }
    return render_template(
        "evaluations/daily.html",
        student=student,
        criteria=criteria_tpl,
        ratings=get_rating_choices(sid),
        category_labels=get_criterion_category_labels(sid),
        default_rating=get_default_rating_code(sid),
        existing=existing,
        evaluation=evaluation,
        today=today,
    )


@bp.route("/self-assess", methods=["GET", "POST"])
@login_required
@permission_required("self_assess")
def self_assess():
    student, redirect_resp = require_linked_student()
    if redirect_resp:
        return redirect_resp
    today = date.today()

    if request.method == "POST":
        assessment = StudentSelfAssessment.query.filter_by(
            student_id=student.id, date=today
        ).first()
        if not assessment:
            assessment = StudentSelfAssessment(student_id=student.id, date=today)
            db.session.add(assessment)

        items = get_self_assessment_items(student.school_id)
        answers = {
            item.code: bool(request.form.get(item.code))
            for item in items
        }
        assessment.set_answers_dict(answers)
        assessment.reflection = request.form.get("reflection", "")
        assessment.improvement_plan = request.form.get("improvement_plan", "")

        checked = [v for v in answers.values() if v]
        total = len(answers) or 1
        assessment.self_score = round(len(checked) / total * 100, 1)
        db.session.commit()
        flash_msg("eval_self_saved", "success")
        return redirect(url_for("evaluations.self_assess"))

    assessment = StudentSelfAssessment.query.filter_by(
        student_id=student.id, date=today
    ).first()
    history = StudentSelfAssessment.query.filter_by(student_id=student.id).order_by(
        StudentSelfAssessment.date.desc()
    ).limit(7).all()

    items = get_self_assessment_items(student.school_id)
    answers = assessment.get_answers_dict() if assessment else {}

    return render_template(
        "evaluations/self_assess.html",
        student=student,
        assessment=assessment,
        self_assess_items=items,
        answers=answers,
        history=history,
        today=today,
    )


@bp.route("/reading")
@login_required
@permission_required("manage_evaluations")
def reading_index():
    query = ReadingAssessment.query
    if current_user.school_id:
        query = query.filter_by(school_id=current_user.school_id)
    if current_user.is_teacher and current_user.teacher_profile:
        query = query.filter_by(teacher_id=current_user.teacher_profile.id)
    records = query.order_by(ReadingAssessment.date.desc()).limit(50).all()
    students = _teacher_students()
    sid = _eval_school_id()
    overall_code = get_reading_overall_aspect_code(sid)
    record_rows = []
    for r in records:
        aspects = parse_reading_aspect_scores(r)
        overall_val = aspects.get(overall_code) or r.overall_rating
        record_rows.append({
            "record": r,
            "overall_display": dict(get_rating_choices(sid)).get(overall_val, overall_val or "—"),
        })
    return render_template(
        "evaluations/reading.html",
        records=record_rows,
        students=students,
        today=date.today(),
        rating_choices=get_rating_choices(sid),
        reading_aspects=get_reading_aspects(sid),
        rating_labels=dict(get_rating_choices(sid)),
    )


@bp.route("/reading/<int:student_id>", methods=["POST"])
@login_required
@permission_required("manage_evaluations")
def reading_record(student_id):
    student = Student.query.get_or_404(student_id)
    teacher = _resolve_evaluation_teacher(student)
    if not teacher:
        flash_msg("teacher_no_profile", "danger")
        return redirect(url_for("evaluations.reading_index"))
    db.session.add(build_reading_assessment(student, teacher, request.form))
    log_action("save_reading_assessment", "evaluations", f"student={student_id}")
    db.session.commit()
    sync_kpis_for_student(student_id)
    flash_msg("eval_reading_saved", "success", student.school_id)
    return redirect(url_for("evaluations.reading_index"))


@bp.route("/behavior")
@login_required
@permission_required("manage_evaluations")
def behavior_index():
    query = BehaviorRecord.query
    if current_user.school_id:
        query = query.filter_by(school_id=current_user.school_id)
    records = query.order_by(BehaviorRecord.date.desc()).limit(50).all()
    students = _teacher_students()
    sid = _eval_school_id()
    return render_template(
        "evaluations/behavior.html",
        records=records,
        students=students,
        today=date.today(),
        behavior_types=get_config_choices("behavior_type", sid),
        behavior_categories=get_behavior_categories(sid),
        behavior_type_labels=get_config_map("behavior_type", sid),
        category_labels=dict(get_behavior_categories(sid)),
        behavior_type_scores=get_behavior_type_scores(sid),
        default_behavior_score=get_default_behavior_score(sid),
    )


@bp.route("/behavior/<int:student_id>", methods=["POST"])
@login_required
@permission_required("manage_evaluations")
def behavior_record(student_id):
    student = Student.query.get_or_404(student_id)
    teacher = _resolve_evaluation_teacher(student)
    if not teacher:
        flash_msg("teacher_no_profile", "danger")
        return redirect(url_for("evaluations.behavior_index"))
    today = date.today()
    score = float(request.form.get("score", 0))
    db.session.add(BehaviorRecord(
        student_id=student.id,
        teacher_id=teacher.id,
        school_id=student.school_id,
        date=today,
        behavior_type=request.form.get("behavior_type") or get_default_behavior_type(student.school_id),
        category=request.form.get("category"),
        description=request.form.get("description"),
        score=score,
    ))
    log_action(
        "save_behavior_record", "evaluations",
        f"student={student_id} type={request.form.get('behavior_type')}",
    )
    db.session.commit()
    sync_kpis_for_student(student_id)
    title, message, ntype = get_notification_content(
        "behavior", student.school_id, student=student.full_name_ar,
    )
    notify_parent_of_student(student, title, message, ntype)
    db.session.commit()
    flash_msg("eval_behavior_saved", "success", student.school_id)
    return redirect(url_for("evaluations.behavior_index"))


def _resolve_evaluation_teacher(student):
    """Teacher for evaluation records when the logged-in user has no teacher profile."""
    teacher = current_user.teacher_profile
    if teacher:
        return teacher
    if student.responsible_teacher and student.responsible_teacher.is_active:
        return student.responsible_teacher
    return Teacher.query.filter_by(school_id=student.school_id, is_active=True).first()


def _eval_school_id():
    if current_user.school_id:
        return current_user.school_id
    return get_active_school_id()


def _teacher_students():
    if current_user.is_teacher and current_user.teacher_profile:
        return students_for_teacher(current_user.teacher_profile)
    if current_user.school_id:
        return Student.query.filter_by(school_id=current_user.school_id, is_active=True).all()
    return []
