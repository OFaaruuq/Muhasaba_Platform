from datetime import date

from flask import flash, redirect, render_template, request, url_for, abort
from flask_login import login_required, current_user

from app.followup_surveys import bp
from app.utils import permission_required
from app.models import (
    Student, Teacher, Grade, Class,
    FamilyFollowupSurvey, TeacherMonthlySurvey,
    EducationalProgramFollowupSurvey,
    StudentEducationalProgramFollowupSurvey,
)
from app.services.educational_program_service import (
    save_program_survey, save_student_program_survey,
    program_survey_status, student_program_survey_status,
    program_survey_progress,
    program_survey_checklist, program_index_rows, student_program_index_rows,
    student_program_entries_for_students,
    can_fill_program_surveys, can_fill_student_program_surveys,
    program_survey_sections, program_total_questions,
    program_survey_field_map, bool_label as program_bool_label,
    completion_percent as program_completion_percent,
    verify_all_fields_stored as verify_program_fields,
)
from app.services.followup_survey_service import (
    save_family_survey, save_teacher_survey,
    family_survey_status, teacher_survey_status,
    students_for_user, teachers_for_user,
    can_access_student, can_access_teacher,
    can_fill_family_surveys, can_fill_teacher_surveys,
    can_access_followup_surveys, can_view_family_surveys,
    default_followup_tab, resolve_followup_school_id,
    frequency_choices, frequency_label,
    weekly_meetings_choices, weekly_meetings_label, bool_label,
    family_survey_progress, teacher_survey_progress, survey_status_label,
    default_family_name, FAMILY_TOTAL_QUESTIONS, TEACHER_TOTAL_QUESTIONS,
    family_survey_field_map, teacher_survey_field_map,
    family_survey_checklist, teacher_survey_checklist,
    family_entries_for_students,
    followup_period_context, completion_percent,
    filter_grouped_entries, class_completion_summary, teacher_index_rows,
    matches_status_filter, matches_name_search,
    arabic_months, verify_all_fields_stored,
)
from app.services.followup_analytics_service import (
    school_analytics_summary, student_analytics_row, teacher_analytics_row,
    student_full_report, teacher_combined_report,
    completion_pct as analytics_completion_pct, period_label,
)
from app.services.teacher_student_service import students_for_teacher
from app.utils.school_context import get_active_school_id


def _period_from_request():
    today = date.today()
    year = request.args.get("year", request.form.get("year"), type=int) or today.year
    month = request.args.get("month", request.form.get("month"), type=int) or today.month
    return year, month


def _school_id():
    return resolve_followup_school_id(current_user)


def _redirect_after_family_save(student, year, month):
    return_teacher_id = request.form.get("return_teacher_id", type=int)
    if return_teacher_id:
        if current_user.teacher_profile and can_fill_teacher_surveys(current_user):
            return redirect(url_for(
                "followup_surveys.teacher_form",
                year=year, month=month, tab="family",
            ))
        return redirect(url_for(
            "followup_surveys.teacher_form_admin",
            teacher_id=return_teacher_id, year=year, month=month, tab="family",
        ))
    return redirect(url_for(
        "followup_surveys.index",
        tab="family", year=year, month=month,
    ))


def _redirect_after_student_program_save(student, year, month):
    return_teacher_id = request.form.get("return_teacher_id", type=int)
    if return_teacher_id:
        if current_user.teacher_profile and can_fill_teacher_surveys(current_user):
            return redirect(url_for(
                "followup_surveys.teacher_form",
                year=year, month=month, tab="student_program",
            ))
        return redirect(url_for(
            "followup_surveys.teacher_form_admin",
            teacher_id=return_teacher_id, year=year, month=month, tab="student_program",
        ))
    return redirect(url_for(
        "followup_surveys.index",
        tab="student_program", year=year, month=month,
    ))


def _teacher_hub_context(teacher, year, month, admin_entry=False):
    survey = TeacherMonthlySurvey.query.filter_by(
        teacher_id=teacher.id, period_year=year, period_month=month,
    ).first()
    answered, total = teacher_survey_progress(survey)
    students = students_for_teacher(teacher)
    family_entries = family_entries_for_students(students, year, month)
    student_program_entries = student_program_entries_for_students(students, year, month)
    family_pending = family_partial = family_complete = 0
    program_pending = program_partial = program_complete = 0
    for entry in family_entries:
        if entry["answered"] >= entry["total"]:
            family_complete += 1
        elif entry["answered"] > 0:
            family_partial += 1
        else:
            family_pending += 1
    for entry in student_program_entries:
        if entry["answered"] >= entry["total"]:
            program_complete += 1
        elif entry["answered"] > 0:
            program_partial += 1
        else:
            program_pending += 1
    sid = teacher.school_id
    active_tab = request.args.get("tab", "teacher")
    return {
        "teacher": teacher,
        "survey": survey,
        "period_year": year,
        "period_month": month,
        "frequency_choices": frequency_choices(sid),
        "answered": answered,
        "total": total,
        "teacher_total_questions": TEACHER_TOTAL_QUESTIONS,
        "teacher_field_map": teacher_survey_field_map(sid),
        "teacher_checklist": teacher_survey_checklist(survey, sid),
        "family_entries": family_entries,
        "student_program_entries": student_program_entries,
        "family_pending": family_pending,
        "family_partial": family_partial,
        "family_complete": family_complete,
        "program_pending": program_pending,
        "program_partial": program_partial,
        "program_complete": program_complete,
        "weekly_meetings_choices": weekly_meetings_choices(sid),
        "family_field_map": family_survey_field_map(sid),
        "admin_entry": admin_entry,
        "active_tab": active_tab,
        "return_teacher_id": teacher.id,
        "student_program_entries": student_program_entries,
        "program_sections": program_survey_sections(sid),
        "program_total_questions": program_total_questions(sid),
    }


def _can_access_student(student):
    return can_access_student(current_user, student)


def _can_access_teacher_survey(teacher):
    return can_access_teacher(current_user, teacher)


@bp.route("/")
@login_required
@permission_required("manage_followup_surveys", "view_followup_surveys")
def index():
    if not can_access_followup_surveys(current_user):
        abort(403)

    can_fill_family = can_fill_family_surveys(current_user)
    can_fill_teacher = can_fill_teacher_surveys(current_user)
    can_fill_program = can_fill_program_surveys(current_user)
    can_fill_student_program = can_fill_student_program_surveys(current_user)
    can_view_family = can_view_family_surveys(current_user)

    year, month = _period_from_request()
    grade_id = request.args.get("grade_id", type=int)
    class_id = request.args.get("class_id", type=int)
    tab = request.args.get("tab") or default_followup_tab(current_user)
    allowed_tabs = []
    if can_view_family or can_fill_family:
        allowed_tabs.append("family")
    if can_fill_teacher:
        allowed_tabs.append("teacher")
    if can_fill_program:
        allowed_tabs.append("program")
    if can_fill_student_program:
        allowed_tabs.append("student_program")
    if tab not in allowed_tabs and allowed_tabs:
        tab = allowed_tabs[0]
    status_filter = request.args.get("status", "all")
    search_q = (request.args.get("q") or "").strip()
    sid = _school_id()
    period_ctx = followup_period_context(year, month, sid)

    students = students_for_user(current_user, grade_id, class_id)
    student_ids = [s.id for s in students]

    family_status = family_survey_status(sid, year, month, student_ids) if sid and student_ids else None
    student_program_status = student_program_survey_status(sid, year, month, student_ids) if sid and student_ids else None

    teachers = teachers_for_user(current_user)
    teacher_ids = [t.id for t in teachers]
    teacher_status = None
    program_status = None
    if sid and teacher_ids:
        teacher_status = teacher_survey_status(sid, year, month, teacher_ids)
        program_status = program_survey_status(sid, year, month, teacher_ids)

    family_surveys = {}
    if student_ids:
        for s in FamilyFollowupSurvey.query.filter(
            FamilyFollowupSurvey.student_id.in_(student_ids),
            FamilyFollowupSurvey.period_year == year,
            FamilyFollowupSurvey.period_month == month,
        ).all():
            family_surveys[s.student_id] = s

    teacher_surveys = {}
    if teacher_ids:
        for s in TeacherMonthlySurvey.query.filter(
            TeacherMonthlySurvey.teacher_id.in_(teacher_ids),
            TeacherMonthlySurvey.period_year == year,
            TeacherMonthlySurvey.period_month == month,
        ).all():
            teacher_surveys[s.teacher_id] = s

    program_surveys = {}
    student_program_surveys = {}
    if teacher_ids:
        for s in EducationalProgramFollowupSurvey.query.filter(
            EducationalProgramFollowupSurvey.teacher_id.in_(teacher_ids),
            EducationalProgramFollowupSurvey.period_year == year,
            EducationalProgramFollowupSurvey.period_month == month,
        ).all():
            program_surveys[s.teacher_id] = s
    if student_ids:
        for s in StudentEducationalProgramFollowupSurvey.query.filter(
            StudentEducationalProgramFollowupSurvey.student_id.in_(student_ids),
            StudentEducationalProgramFollowupSurvey.period_year == year,
            StudentEducationalProgramFollowupSurvey.period_month == month,
        ).all():
            student_program_surveys[s.student_id] = s

    grades = []
    classes = []
    if sid:
        grades = Grade.query.filter_by(school_id=sid).order_by(Grade.level).all()
        class_query = Class.query.filter_by(school_id=sid)
        if grade_id:
            class_query = class_query.filter_by(grade_id=grade_id)
        classes = class_query.order_by(Class.name).all()

    grouped = {}
    for student in students:
        grade_name = student.grade.name_ar if student.grade else "—"
        class_name = student.class_.name if student.class_ else "—"
        survey = family_surveys.get(student.id)
        answered, total = family_survey_progress(survey)
        status_text, status_class = survey_status_label(answered, total)
        grouped.setdefault(grade_name, {}).setdefault(class_name, []).append({
            "student": student,
            "survey": survey,
            "answered": answered,
            "total": total,
            "status_text": status_text,
            "status_class": status_class,
            "percent": int(round(answered * 100 / total)) if total else 0,
        })

    grouped_filtered = filter_grouped_entries(grouped, status_filter, search_q)

    grouped_student_program = {}
    for student in students:
        grade_name = student.grade.name_ar if student.grade else "—"
        class_name = student.class_.name if student.class_ else "—"
        survey = student_program_surveys.get(student.id)
        answered, total = program_survey_progress(survey, student.school_id)
        status_text, status_class = survey_status_label(answered, total, student.school_id)
        grouped_student_program.setdefault(grade_name, {}).setdefault(class_name, []).append({
            "student": student,
            "survey": survey,
            "answered": answered,
            "total": total,
            "status_text": status_text,
            "status_class": status_class,
            "percent": int(round(answered * 100 / total)) if total else 0,
        })
    grouped_student_program_filtered = filter_grouped_entries(
        grouped_student_program, status_filter, search_q,
    )

    teacher_rows = teacher_index_rows(teachers, teacher_surveys, year, month)
    if status_filter != "all" or search_q:
        teacher_rows = [
            row for row in teacher_rows
            if matches_status_filter(row["answered"], row["total"], status_filter)
            and matches_name_search(
                row["teacher"].full_name_ar,
                row["teacher"].full_name,
                search_q,
            )
        ]

    program_rows = program_index_rows(teachers, program_surveys, year, month)
    student_program_rows = student_program_index_rows(students, student_program_surveys, year, month)
    if status_filter != "all" or search_q:
        student_program_rows = [
            row for row in student_program_rows
            if matches_status_filter(row["answered"], row["total"], status_filter)
            and matches_name_search(
                row["student"].full_name_ar,
                row["student"].full_name,
                search_q,
            )
        ]
    if status_filter != "all" or search_q:
        program_rows = [
            row for row in program_rows
            if matches_status_filter(row["answered"], row["total"], status_filter)
            and matches_name_search(
                row["teacher"].full_name_ar,
                row["teacher"].full_name,
                search_q,
            )
        ]

    can_view_all = current_user.is_school_manager or current_user.is_platform_admin
    is_parent_view = current_user.is_parent

    return render_template(
        "followup_surveys/index.html",
        tab=tab,
        period_year=year,
        period_month=month,
        period_ctx=period_ctx,
        arabic_months=arabic_months(sid),
        grouped=grouped_filtered,
        grouped_all=grouped,
        grouped_student_program=grouped_student_program_filtered,
        grouped_student_program_all=grouped_student_program,
        grades=grades,
        classes=classes,
        selected_grade=grade_id,
        selected_class=class_id,
        status_filter=status_filter,
        search_q=search_q,
        family_status=family_status,
        student_program_status=student_program_status,
        teacher_status=teacher_status,
        family_completion_pct=completion_percent(family_status),
        student_program_completion_pct=program_completion_percent(student_program_status),
        teacher_completion_pct=completion_percent(teacher_status),
        teachers=teachers,
        teacher_rows=teacher_rows,
        teacher_surveys=teacher_surveys,
        program_status=program_status,
        program_completion_pct=program_completion_percent(program_status),
        program_rows=program_rows,
        student_program_rows=student_program_rows,
        program_surveys=program_surveys,
        student_program_surveys=student_program_surveys,
        program_survey_progress=program_survey_progress,
        class_completion_summary=class_completion_summary,
        can_view_all=can_view_all,
        is_parent_view=is_parent_view,
        can_fill_family=can_fill_family,
        can_fill_teacher=can_fill_teacher,
        can_fill_program=can_fill_program,
        can_fill_student_program=can_fill_student_program,
        can_view_family=can_view_family,
        is_student_view=current_user.is_student,
        sid=sid,
        teacher_survey_progress=teacher_survey_progress,
        survey_status_label=survey_status_label,
        family_total_questions=FAMILY_TOTAL_QUESTIONS,
        teacher_total_questions=TEACHER_TOTAL_QUESTIONS,
        program_total_questions=program_total_questions(sid),
        family_field_count=len(family_survey_field_map(sid)),
        teacher_field_count=len(teacher_survey_field_map(sid)),
        program_field_count=len(program_survey_field_map(sid)),
    )


@bp.route("/family/<int:student_id>", methods=["GET", "POST"])
@login_required
def family_form(student_id):
    if not can_fill_family_surveys(current_user):
        abort(403)

    student = Student.query.get_or_404(student_id)
    if not _can_access_student(student):
        abort(403)

    year, month = _period_from_request()

    if request.method == "POST":
        survey = save_family_survey(student, year, month, current_user.id, request.form)
        answered, total = family_survey_progress(survey)
        if answered >= total:
            flash("تم حفظ استبيان متابعة الأسرة بالكامل.", "success")
        else:
            flash(f"تم حفظ الإجابات ({answered} من {total} سؤال). يمكنك إكمال الباقي لاحقاً.", "success")
        return _redirect_after_family_save(student, year, month)

    survey = FamilyFollowupSurvey.query.filter_by(
        student_id=student.id, period_year=year, period_month=month,
    ).first()
    answered, total = family_survey_progress(survey)
    sid = student.school_id

    return render_template(
        "followup_surveys/family_form.html",
        student=student,
        survey=survey,
        parents=student.parents,
        period_year=year,
        period_month=month,
        weekly_meetings_choices=weekly_meetings_choices(sid),
        default_family_name=default_family_name(student),
        answered=answered,
        total=total,
        family_total_questions=FAMILY_TOTAL_QUESTIONS,
        family_field_map=family_survey_field_map(sid),
        family_checklist=family_survey_checklist(survey, sid),
    )


@bp.route("/family/<int:student_id>/view")
@login_required
@permission_required("manage_followup_surveys", "view_followup_surveys")
def family_view(student_id):
    if not can_view_family_surveys(current_user):
        abort(403)
    student = Student.query.get_or_404(student_id)
    if not _can_access_student(student):
        abort(403)

    year, month = _period_from_request()
    survey = FamilyFollowupSurvey.query.filter_by(
        student_id=student.id, period_year=year, period_month=month,
    ).first()

    return render_template(
        "followup_surveys/family_view.html",
        student=student,
        survey=survey,
        period_year=year,
        period_month=month,
        bool_label=bool_label,
        weekly_meetings_label=weekly_meetings_label,
        can_fill_family=can_fill_family_surveys(current_user),
    )


@bp.route("/teacher", methods=["GET", "POST"])
@login_required
def teacher_form():
    if not can_fill_teacher_surveys(current_user) or not current_user.teacher_profile:
        abort(403)

    teacher = current_user.teacher_profile
    year, month = _period_from_request()

    if request.method == "POST":
        survey = save_teacher_survey(teacher, year, month, request.form)
        answered, total = teacher_survey_progress(survey)
        if answered >= total:
            flash("تم حفظ الاستبيان الشهري للمعلم بالكامل.", "success")
        else:
            flash(f"تم حفظ الإجابات ({answered} من {total} سؤال). يمكنك إكمال الباقي لاحقاً.", "success")
        return redirect(url_for(
            "followup_surveys.teacher_form",
            year=year, month=month, tab="teacher",
        ))

    ctx = _teacher_hub_context(teacher, year, month, admin_entry=False)
    return render_template("followup_surveys/teacher_hub.html", **ctx)


@bp.route("/teacher/<int:teacher_id>", methods=["GET", "POST"])
@login_required
def teacher_form_admin(teacher_id):
    if not (
        current_user.is_school_manager
        or current_user.is_platform_admin
        or current_user.is_super_admin
    ):
        abort(403)

    teacher = Teacher.query.get_or_404(teacher_id)
    if not _can_access_teacher_survey(teacher):
        abort(403)

    year, month = _period_from_request()

    if request.method == "POST":
        survey = save_teacher_survey(teacher, year, month, request.form)
        answered, total = teacher_survey_progress(survey)
        if answered >= total:
            flash("تم حفظ الاستبيان الشهري للمعلم بالكامل.", "success")
        else:
            flash(f"تم حفظ الإجابات ({answered} من {total} سؤال). يمكنك إكمال الباقي لاحقاً.", "success")
        return redirect(url_for(
            "followup_surveys.teacher_form_admin",
            teacher_id=teacher.id, year=year, month=month, tab="teacher",
        ))

    ctx = _teacher_hub_context(teacher, year, month, admin_entry=True)
    return render_template("followup_surveys/teacher_hub.html", **ctx)


@bp.route("/teacher/<int:teacher_id>/view")
@login_required
def teacher_view(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    if not _can_access_teacher_survey(teacher):
        abort(403)

    year, month = _period_from_request()
    survey = TeacherMonthlySurvey.query.filter_by(
        teacher_id=teacher.id, period_year=year, period_month=month,
    ).first()

    return render_template(
        "followup_surveys/teacher_view.html",
        teacher=teacher,
        survey=survey,
        period_year=year,
        period_month=month,
        frequency_label=frequency_label,
    )


@bp.route("/program", methods=["GET", "POST"])
@login_required
def program_form():
    if not can_fill_program_surveys(current_user) or not current_user.teacher_profile:
        abort(403)

    teacher = current_user.teacher_profile
    year, month = _period_from_request()

    if request.method == "POST":
        survey = save_program_survey(teacher, year, month, current_user.id, request.form)
        answered, total = program_survey_progress(survey)
        if answered >= total:
            flash("تم حفظ متابعة البرنامج التربوي بالكامل.", "success")
        else:
            flash(f"تم حفظ الإجابات ({answered} من {total}). يمكنك إكمال الباقي لاحقاً.", "success")
        return redirect(url_for("followup_surveys.program_form", year=year, month=month))

    return _render_program_form(teacher, year, month, admin_entry=False)


@bp.route("/program/<int:teacher_id>", methods=["GET", "POST"])
@login_required
def program_form_admin(teacher_id):
    if not (
        current_user.is_school_manager
        or current_user.is_platform_admin
        or current_user.is_super_admin
    ):
        abort(403)

    teacher = Teacher.query.get_or_404(teacher_id)
    if not _can_access_teacher_survey(teacher):
        abort(403)

    year, month = _period_from_request()

    if request.method == "POST":
        survey = save_program_survey(teacher, year, month, current_user.id, request.form)
        answered, total = program_survey_progress(survey)
        if answered >= total:
            flash("تم حفظ متابعة البرنامج التربوي بالكامل.", "success")
        else:
            flash(f"تم حفظ الإجابات ({answered} من {total}). يمكنك إكمال الباقي لاحقاً.", "success")
        return redirect(url_for(
            "followup_surveys.program_form_admin",
            teacher_id=teacher.id, year=year, month=month,
        ))

    return _render_program_form(teacher, year, month, admin_entry=True)


@bp.route("/program/<int:teacher_id>/view")
@login_required
def program_view(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    if not _can_access_teacher_survey(teacher):
        abort(403)

    year, month = _period_from_request()
    survey = EducationalProgramFollowupSurvey.query.filter_by(
        teacher_id=teacher.id, period_year=year, period_month=month,
    ).first_or_404()
    sid = teacher.school_id

    return render_template(
        "followup_surveys/program_view.html",
        teacher=teacher,
        survey=survey,
        period_year=year,
        period_month=month,
        program_sections=program_survey_sections(sid),
        bool_label=program_bool_label,
        answered=program_survey_progress(survey)[0],
        total=program_total_questions(sid),
    )


@bp.route("/program/student/<int:student_id>", methods=["GET", "POST"])
@login_required
def program_student_form(student_id):
    if not can_fill_student_program_surveys(current_user):
        abort(403)

    student = Student.query.get_or_404(student_id)
    if not _can_access_student(student):
        abort(403)

    year, month = _period_from_request()

    if request.method == "POST":
        survey = save_student_program_survey(student, year, month, current_user.id, request.form)
        answered, total = program_survey_progress(survey)
        if answered >= total:
            flash("تم حفظ متابعة البرنامج التربوي للطالب بالكامل.", "success")
        else:
            flash(f"تم حفظ الإجابات ({answered} من {total}). يمكنك إكمال الباقي لاحقاً.", "success")
        return _redirect_after_student_program_save(student, year, month)

    return _render_student_program_form(student, year, month, admin_entry=False)


@bp.route("/program/student/<int:student_id>/view")
@login_required
def program_student_view(student_id):
    student = Student.query.get_or_404(student_id)
    if not _can_access_student(student):
        abort(403)

    year, month = _period_from_request()
    survey = StudentEducationalProgramFollowupSurvey.query.filter_by(
        student_id=student.id, period_year=year, period_month=month,
    ).first_or_404()
    sid = student.school_id

    return render_template(
        "followup_surveys/student_program_view.html",
        student=student,
        survey=survey,
        period_year=year,
        period_month=month,
        program_sections=program_survey_sections(sid),
        bool_label=program_bool_label,
        answered=program_survey_progress(survey)[0],
        total=program_total_questions(sid),
    )


def _render_student_program_form(student, year, month, admin_entry=False):
    sid = student.school_id
    survey = StudentEducationalProgramFollowupSurvey.query.filter_by(
        student_id=student.id, period_year=year, period_month=month,
    ).first()
    answered, total = program_survey_progress(survey, sid)
    period_ctx = followup_period_context(year, month, sid)
    return render_template(
        "followup_surveys/student_program_form.html",
        student=student,
        survey=survey,
        period_year=year,
        period_month=month,
        period_ctx=period_ctx,
        program_sections=program_survey_sections(sid),
        program_checklist=program_survey_checklist(survey, sid),
        program_total_questions=program_total_questions(sid),
        program_field_count=len(program_survey_field_map(sid)),
        answered=answered,
        total=total,
        admin_entry=admin_entry,
    )


def _render_program_form(teacher, year, month, admin_entry=False):
    sid = teacher.school_id
    survey = EducationalProgramFollowupSurvey.query.filter_by(
        teacher_id=teacher.id, period_year=year, period_month=month,
    ).first()
    answered, total = program_survey_progress(survey)
    period_ctx = followup_period_context(year, month, sid)
    return render_template(
        "followup_surveys/program_form.html",
        teacher=teacher,
        survey=survey,
        period_year=year,
        period_month=month,
        period_ctx=period_ctx,
        program_sections=program_survey_sections(sid),
        program_checklist=program_survey_checklist(survey, sid),
        program_total_questions=program_total_questions(sid),
        program_field_count=len(program_survey_field_map(sid)),
        answered=answered,
        total=total,
        admin_entry=admin_entry,
    )


@bp.route("/analytics")
@login_required
def analytics_index():
    if not can_access_followup_surveys(current_user):
        abort(403)

    if current_user.is_student and current_user.student_profile:
        return redirect(url_for(
            "followup_surveys.analytics_student",
            student_id=current_user.student_profile.id,
            **{k: v for k, v in request.args.items()},
        ))

    year, month = _period_from_request()
    tab = request.args.get("tab", "overview")
    grade_id = request.args.get("grade_id", type=int)
    class_id = request.args.get("class_id", type=int)
    search_q = (request.args.get("q") or "").strip()
    status_filter = request.args.get("status", "all")
    sid = _school_id()
    period_ctx = followup_period_context(year, month, sid)

    students = students_for_user(current_user, grade_id, class_id)
    teachers = teachers_for_user(current_user)

    can_view_teachers = bool(
        can_fill_teacher_surveys(current_user) or can_fill_program_surveys(current_user)
    )
    allowed_tabs = ["overview"]
    if can_view_family_surveys(current_user) or can_fill_family_surveys(current_user):
        allowed_tabs.append("students")
    if can_view_teachers:
        allowed_tabs.append("teachers")
    if tab not in allowed_tabs:
        tab = allowed_tabs[0]

    summary = school_analytics_summary(students, teachers, year, month) if sid else None

    student_rows = [
        row for row in (student_analytics_row(s, year, month) for s in students)
        if matches_status_filter(row["answered"], row["total"], status_filter)
        and matches_name_search(
            row["student"].full_name_ar, row["student"].full_name, search_q,
        )
    ]

    teacher_rows = []
    if can_view_teachers:
        teacher_rows = [
            row for row in (teacher_analytics_row(t, year, month) for t in teachers)
            if matches_name_search(
                row["teacher"].full_name_ar, row["teacher"].full_name, search_q,
            )
        ]

    grades = []
    classes = []
    if sid:
        grades = Grade.query.filter_by(school_id=sid).order_by(Grade.level).all()
        class_query = Class.query.filter_by(school_id=sid)
        if grade_id:
            class_query = class_query.filter_by(grade_id=grade_id)
        classes = class_query.order_by(Class.name).all()

    return render_template(
        "followup_surveys/analytics/index.html",
        tab=tab,
        period_year=year,
        period_month=month,
        period_ctx=period_ctx,
        arabic_months=arabic_months(sid),
        summary=summary,
        student_rows=student_rows,
        teacher_rows=teacher_rows,
        grades=grades,
        classes=classes,
        selected_grade=grade_id,
        selected_class=class_id,
        search_q=search_q,
        status_filter=status_filter,
        sid=sid,
        can_view_teachers=can_view_teachers,
        show_students_tab=(
            can_view_family_surveys(current_user) or can_fill_family_surveys(current_user)
        ),
        can_fill_family=can_fill_family_surveys(current_user),
        family_total=FAMILY_TOTAL_QUESTIONS,
        teacher_total=TEACHER_TOTAL_QUESTIONS,
        program_total=program_total_questions(sid),
        analytics_completion_pct=analytics_completion_pct,
    )


@bp.route("/analytics/student/<int:student_id>")
@login_required
def analytics_student(student_id):
    if not can_access_followup_surveys(current_user):
        abort(403)

    student = Student.query.get_or_404(student_id)
    if not _can_access_student(student):
        abort(403)

    year, month = _period_from_request()
    months = request.args.get("months", 6, type=int)
    months = max(3, min(months, 12))
    sid = student.school_id
    period_ctx = followup_period_context(year, month, sid)
    report = student_full_report(student, year, month, months)

    return render_template(
        "followup_surveys/analytics/student_report.html",
        report=report,
        period_year=year,
        period_month=month,
        period_ctx=period_ctx,
        arabic_months=arabic_months(sid),
        months=months,
        period_label=period_label(year, month),
        bool_label=bool_label,
        frequency_label=frequency_label,
    )


@bp.route("/analytics/teacher/<int:teacher_id>")
@login_required
def analytics_teacher(teacher_id):
    if not can_access_followup_surveys(current_user):
        abort(403)

    teacher = Teacher.query.get_or_404(teacher_id)
    if not _can_access_teacher_survey(teacher):
        abort(403)

    year, month = _period_from_request()
    months = request.args.get("months", 6, type=int)
    months = max(3, min(months, 12))
    sid = teacher.school_id
    period_ctx = followup_period_context(year, month, sid)
    report = teacher_combined_report(teacher, year, month, months)

    return render_template(
        "followup_surveys/analytics/teacher_report.html",
        report=report,
        period_year=year,
        period_month=month,
        period_ctx=period_ctx,
        arabic_months=arabic_months(sid),
        months=months,
        period_label=period_label(year, month),
        can_fill_teacher=can_fill_teacher_surveys(current_user),
        can_fill_program=can_fill_program_surveys(current_user),
        frequency_label=frequency_label,
    )
