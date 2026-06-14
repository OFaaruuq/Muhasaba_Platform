from flask import flash, redirect, render_template, request, session, url_for
from flask_login import login_required, current_user

from app.admin import bp
from app.extensions import db
from app.models import (
    PlatformSetting, EvaluationCriterion, RatingLevel,
    AttendanceStatusConfig, ConfigOption, KPI, School,
)
from app.services.message_service import flash_msg
from app.services.config_service import (
    ensure_school_defaults, get_criteria_grouped, get_monthly_criteria_grouped,
    get_rating_choices, get_monthly_rating_choices,
    get_attendance_statuses, get_setting, set_setting, provision_school_kpis,
    get_config_options, get_config_map, get_monthly_category_labels,
    get_kpi_source_options, get_ui_labels, get_ui_label_schema,
    get_org_labels, get_all_settings_grouped, get_admin_config_sections,
    get_setting_category_labels, get_rating_levels, save_settings_bulk,
    add_platform_setting, SETTING_CATEGORY_LABELS,     get_nav_labels, get_page_labels, get_registration_section_labels,
)
from app.services.content_seeds import NAV_LABELS_SEED, PAGE_LABELS_SEED, dumps_json
from app.services.message_service import get_messages, MESSAGE_GROUPS, MESSAGES_SEED
from app.services.survey_config_service import (
    admin_family_survey_rows, admin_teacher_survey_rows, admin_program_survey_rows,
    save_family_survey_fields_admin, save_teacher_survey_fields_admin,
    save_program_survey_sections_admin,
    parse_family_survey_admin_form, parse_teacher_survey_admin_form,
    parse_program_survey_admin_form, FAMILY_SECTION_CODES, SURVEY_FIELD_TYPES,
)
from app.services.audit_service import log_action
from app.services.registration_field_service import (
    admin_field_rows, save_registration_config, apply_preset,
    save_registration_labels,
)
from app.services.attendance_time_service import get_attendance_time_settings, save_attendance_time_settings
from app.utils import permission_required
from app.utils.school_context import get_active_school_id, set_active_school_id, get_schools_for_picker


def _school_id():
    sid = get_active_school_id()
    if not sid and current_user.is_platform_admin:
        school = School.query.filter_by(is_active=True).first()
        if school:
            set_active_school_id(school.id)
            return school.id
    return sid


@bp.route("/")
@login_required
@permission_required("manage_platform_config")
def index():
    sid = _school_id()
    schools = get_schools_for_picker()
    criteria = get_criteria_grouped(sid)
    monthly_criteria = get_monthly_criteria_grouped(sid)
    ratings = get_rating_choices(sid)
    monthly_ratings = get_monthly_rating_choices(sid)
    statuses = get_attendance_statuses(sid)
    kpis = KPI.query.filter(
        (KPI.school_id == sid) | (KPI.school_id.is_(None)) if sid else KPI.school_id.is_(None)
    ).filter_by(is_active=True).all()

    settings = PlatformSetting.query.filter(
        (PlatformSetting.school_id == sid) | (PlatformSetting.school_id.is_(None))
    ).order_by(PlatformSetting.category).all()

    config_sections, config_section_labels = get_admin_config_sections(sid)
    settings_grouped = get_all_settings_grouped(sid)
    rating_levels = get_rating_levels(sid, "qualitative")
    monthly_rating_levels = get_rating_levels(sid, "numeric_5")

    reg_fields, reg_mode = admin_field_rows(sid)
    family_survey_rows = admin_family_survey_rows(sid)
    teacher_survey_rows = admin_teacher_survey_rows(sid)
    program_survey_rows, program_sections_raw = admin_program_survey_rows(sid)
    flash_messages = get_messages(sid)
    registration_section_labels = get_registration_section_labels(sid)

    return render_template(
        "admin/index.html",
        schools=schools,
        active_school_id=sid,
        criteria=criteria,
        monthly_criteria=monthly_criteria,
        ratings=ratings,
        monthly_ratings=monthly_ratings,
        rating_levels=rating_levels,
        monthly_rating_levels=monthly_rating_levels,
        statuses=statuses,
        kpis=kpis,
        settings=settings,
        settings_grouped=settings_grouped,
        setting_category_labels=get_setting_category_labels(),
        setting_categories=sorted(
            settings_grouped.keys(),
            key=lambda c: list(SETTING_CATEGORY_LABELS.keys()).index(c)
            if c in SETTING_CATEGORY_LABELS else 99,
        ),
        config_sections=config_sections,
        criterion_categories=get_config_map("criterion_category", sid),
        monthly_categories=get_monthly_category_labels(sid),
        kpi_sources=get_kpi_source_options(sid),
        platform_name=get_setting("platform_name_ar", sid),
        platform_tagline=get_setting("platform_tagline_ar", sid),
        grade_a_min=get_setting("grade_a_min", sid, 90),
        grade_b_min=get_setting("grade_b_min", sid, 80),
        grade_c_min=get_setting("grade_c_min", sid, 70),
        grade_d_min=get_setting("grade_d_min", sid, 60),
        default_class_capacity=get_setting("default_class_capacity", sid, 30),
        perf_green_min=get_setting("perf_green_min", sid, 80),
        perf_yellow_min=get_setting("perf_yellow_min", sid, 60),
        monthly_strength_min=get_setting("monthly_strength_min", sid, 4),
        monthly_weakness_max=get_setting("monthly_weakness_max", sid, 2),
        show_demo_logins=str(get_setting("show_demo_logins", sid, "true")).lower() in ("true", "1", "yes"),
        perf_label_success=get_setting("perf_label_success", sid, "ممتاز"),
        perf_label_warning=get_setting("perf_label_warning", sid, "متوسط"),
        perf_label_danger=get_setting("perf_label_danger", sid, "يحتاج متابعة"),
        default_exam_total_marks=get_setting("default_exam_total_marks", sid, 100),
        default_exam_passing_marks=get_setting("default_exam_passing_marks", sid, 50),
        default_exam_duration=get_setting("default_exam_duration", sid, 60),
        reading_lesson_score=get_setting("reading_lesson_score", sid, 75),
        ui_labels=get_ui_labels(sid),
        ui_label_schema=get_ui_label_schema(),
        demo_login_password=get_setting("demo_login_password", sid, "admin123"),
        config_section_labels=config_section_labels,
        org_labels=get_org_labels(sid),
        org_central_name=get_setting("org_central_name_ar", sid, "الوزارة"),
        org_central_admin_role=get_setting("org_central_admin_role_ar", sid, "مسؤول الوزارة"),
        org_central_dashboard_title=get_setting(
            "org_central_dashboard_title_ar", sid, "لوحة تحكم الإدارة المركزية"
        ),
        registration_fields=reg_fields,
        registration_mode=reg_mode,
        attendance_time=get_attendance_time_settings(sid),
        nav_labels=get_nav_labels(sid),
        nav_label_keys=NAV_LABELS_SEED,
        page_labels=get_page_labels(sid),
        page_label_keys=PAGE_LABELS_SEED,
        family_survey_rows=family_survey_rows,
        teacher_survey_rows=teacher_survey_rows,
        program_sections_raw=program_sections_raw,
        family_section_codes=FAMILY_SECTION_CODES,
        survey_field_types=SURVEY_FIELD_TYPES,
        flash_messages=flash_messages,
        message_groups=MESSAGE_GROUPS,
        message_keys=MESSAGES_SEED,
        registration_section_labels=registration_section_labels,
    )


@bp.route("/school/select", methods=["POST"])
@login_required
@permission_required("manage_global_config", "manage_platform_config")
def select_school():
    school_id = request.form.get("school_id", type=int)
    if school_id:
        set_active_school_id(school_id)
        ensure_school_defaults(school_id)
        flash_msg("admin_school_selected", "success", sid)
    return redirect(request.referrer or url_for("admin.index"))


@bp.route("/settings", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def save_settings():
    sid = _school_id()
    set_setting("platform_name_ar", request.form.get("platform_name_ar", ""), sid, "general", "اسم المنصة")
    set_setting("platform_tagline_ar", request.form.get("platform_tagline_ar", ""), sid, "general", "الشعار")
    central_name = request.form.get("org_central_name_ar", "").strip()
    central_role = request.form.get("org_central_admin_role_ar", "").strip()
    central_dashboard = request.form.get("org_central_dashboard_title_ar", "").strip()
    if central_name:
        set_setting("org_central_name_ar", central_name, sid, "general", "اسم الجهة المركزية")
    if central_role:
        from app.services.config_service import sync_central_admin_role_label
        sync_central_admin_role_label(central_role, sid)
    if central_dashboard:
        set_setting(
            "org_central_dashboard_title_ar",
            central_dashboard,
            sid,
            "general",
            "عنوان لوحة المسؤول المركزي",
        )
    set_setting("grade_a_min", request.form.get("grade_a_min", 90), sid, "grading", "حد A")
    set_setting("grade_b_min", request.form.get("grade_b_min", 80), sid, "grading", "حد B")
    set_setting("grade_c_min", request.form.get("grade_c_min", 70), sid, "grading", "حد C")
    set_setting("grade_d_min", request.form.get("grade_d_min", 60), sid, "grading", "حد D")
    set_setting("default_class_capacity", request.form.get("default_class_capacity", 30), sid, "general", "سعة الفصل")
    if request.form.get("default_exam_total_marks"):
        set_setting("default_exam_total_marks", request.form.get("default_exam_total_marks", 100), sid, "general", "درجة الاختبار")
    set_setting("perf_green_min", request.form.get("perf_green_min", 80), sid, "performance", "حد أخضر")
    set_setting("perf_yellow_min", request.form.get("perf_yellow_min", 60), sid, "performance", "حد أصفر")
    set_setting("monthly_strength_min", request.form.get("monthly_strength_min", 4), sid, "performance", "حد القوة")
    set_setting("monthly_weakness_max", request.form.get("monthly_weakness_max", 2), sid, "performance", "حد الضعف")
    set_setting("perf_label_success", request.form.get("perf_label_success", "ممتاز"), sid, "performance", "تسمية أخضر")
    set_setting("perf_label_warning", request.form.get("perf_label_warning", "متوسط"), sid, "performance", "تسمية أصفر")
    set_setting("perf_label_danger", request.form.get("perf_label_danger", "يحتاج متابعة"), sid, "performance", "تسمية أحمر")
    set_setting("default_exam_total_marks", request.form.get("default_exam_total_marks", 100), sid, "general", "درجة الاختبار")
    set_setting("default_exam_passing_marks", request.form.get("default_exam_passing_marks", 50), sid, "general", "درجة النجاح")
    set_setting("default_exam_duration", request.form.get("default_exam_duration", 60), sid, "general", "مدة الاختبار")
    set_setting("reading_lesson_score", request.form.get("reading_lesson_score", 75), sid, "scoring", "درجة القراءة")
    for ui_key, _label in get_ui_label_schema():
        val = request.form.get(f"ui_{ui_key}")
        if val is not None:
            set_setting(f"ui_{ui_key}", val, sid, "ui", f"تسمية {ui_key}")
    if request.form.get("demo_login_password"):
        set_setting("demo_login_password", request.form.get("demo_login_password"), sid, "general", "كلمة مرور تجريبية")
    show_demo = "true" if request.form.get("show_demo_logins") == "on" else "false"
    set_setting("show_demo_logins", show_demo, sid, "general", "حسابات تجريبية")
    log_action("save_settings", "admin", f"school={sid}")
    flash_msg("admin_settings_saved", "success", sid)
    return redirect(url_for("admin.index"))


@bp.route("/registration-fields", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def save_registration_fields():
    sid = _school_id()
    mode = request.form.get("registration_mode", "concise")
    if mode not in ("concise", "full", "custom"):
        mode = "concise"

    fields_form = {}
    if mode == "custom":
        from app.services.config_service import get_registration_field_definitions
        for defn in get_registration_field_definitions(sid):
            key = defn["key"]
            fields_form[key] = {
                "visible": request.form.get(f"reg_{key}_visible") == "on",
                "required": request.form.get(f"reg_{key}_required") == "on",
            }
    else:
        fields_form = apply_preset(mode)["fields"]

    save_registration_config(sid, mode, fields_form)

    label_updates = {}
    from app.services.config_service import get_registration_field_definitions
    for defn in get_registration_field_definitions(sid):
        val = request.form.get(f"reg_label_{defn['key']}")
        if val is not None:
            label_updates[defn["key"]] = val.strip()
    section_updates = {}
    for key in get_registration_section_labels(sid):
        val = request.form.get(f"reg_section_{key}")
        if val is not None:
            section_updates[key] = val.strip()
    if label_updates or section_updates:
        save_registration_labels(sid, label_updates, section_updates)

    log_action("save_registration_fields", "admin", f"mode={mode}, school={sid}")
    flash_msg("admin_registration_saved", "success", sid)
    return redirect(url_for("admin.index") + "#tab-registration")


@bp.route("/criteria", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def add_criterion():
    sid = _school_id()
    db.session.add(EvaluationCriterion(
        school_id=sid,
        category=request.form["category"],
        code=request.form["code"],
        name_ar=request.form["name_ar"],
        kpi_source=request.form.get("kpi_source"),
        order=request.form.get("order", 0, type=int),
        evaluation_type=request.form.get("evaluation_type", "daily"),
    ))
    db.session.commit()
    flash_msg("admin_criterion_added", "success", sid)
    return redirect(url_for("admin.index"))


@bp.route("/criteria/<int:criterion_id>/edit", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def edit_criterion(criterion_id):
    c = EvaluationCriterion.query.get_or_404(criterion_id)
    c.name_ar = request.form.get("name_ar", c.name_ar)
    c.kpi_source = request.form.get("kpi_source", c.kpi_source)
    c.order = request.form.get("order", c.order, type=int)
    db.session.commit()
    flash_msg("admin_criterion_updated", "success", _school_id())
    return redirect(url_for("admin.index"))


@bp.route("/criteria/<int:criterion_id>/toggle", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def toggle_criterion(criterion_id):
    c = EvaluationCriterion.query.get_or_404(criterion_id)
    c.is_active = not c.is_active
    db.session.commit()
    flash_msg("admin_criterion_updated", "success", _school_id())
    return redirect(url_for("admin.index"))


@bp.route("/ratings", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def add_rating():
    sid = _school_id()
    scale = request.form.get("scale_type", "qualitative")
    db.session.add(RatingLevel(
        school_id=sid,
        code=request.form["code"],
        name_ar=request.form["name_ar"],
        score=float(request.form["score"]),
        order=request.form.get("order", 0, type=int),
        scale_type=scale,
    ))
    db.session.commit()
    flash_msg("admin_rating_added", "success", sid)
    return redirect(url_for("admin.index"))


@bp.route("/ratings/<int:rating_id>/edit", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def edit_rating(rating_id):
    r = RatingLevel.query.get_or_404(rating_id)
    r.name_ar = request.form.get("name_ar", r.name_ar)
    r.score = float(request.form.get("score", r.score))
    r.order = request.form.get("order", r.order, type=int)
    db.session.commit()
    flash_msg("admin_rating_updated", "success", _school_id())
    return redirect(url_for("admin.index"))


@bp.route("/attendance-time", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def save_attendance_time():
    sid = _school_id()
    save_attendance_time_settings(sid, request.form)
    log_action("save_attendance_time", "admin", f"school={sid}")
    flash_msg("admin_attendance_time_saved", "success", sid)
    return redirect(url_for("admin.index") + "#tab-attendance")


@bp.route("/attendance-status/<int:status_id>/edit", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def edit_attendance_status(status_id):
    s = AttendanceStatusConfig.query.get_or_404(status_id)
    s.name_ar = request.form.get("name_ar", s.name_ar)
    s.badge_class = request.form.get("badge_class", s.badge_class)
    s.time_from = (request.form.get("time_from") or "").strip() or None
    s.time_to = (request.form.get("time_to") or "").strip() or None
    s.counts_as_present = request.form.get("counts_as_present") == "on"
    s.notify_parent = request.form.get("notify_parent") == "on"
    db.session.commit()
    flash_msg("admin_attendance_status_updated", "success", _school_id())
    return redirect(url_for("admin.index"))


@bp.route("/attendance-status", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def add_attendance_status():
    sid = _school_id()
    db.session.add(AttendanceStatusConfig(
        school_id=sid,
        code=request.form["code"],
        name_ar=request.form["name_ar"],
        counts_as_present=request.form.get("counts_as_present") == "on",
        notify_parent=request.form.get("notify_parent") == "on",
        time_from=(request.form.get("time_from") or "").strip() or None,
        time_to=(request.form.get("time_to") or "").strip() or None,
        order=request.form.get("order", 0, type=int),
    ))
    db.session.commit()
    flash_msg("admin_attendance_status_added", "success", sid)
    return redirect(url_for("admin.index"))


@bp.route("/kpi/<int:kpi_id>/edit", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def edit_kpi(kpi_id):
    kpi = KPI.query.get_or_404(kpi_id)
    kpi.name_ar = request.form.get("name_ar", kpi.name_ar)
    kpi.weight = float(request.form.get("weight", kpi.weight))
    kpi.description = request.form.get("description", kpi.description)
    db.session.commit()
    flash_msg("admin_kpi_updated", "success", _school_id())
    return redirect(url_for("admin.index"))


@bp.route("/config-option", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def add_config_option():
    import json as _json
    sid = _school_id()
    meta = None
    score = request.form.get("score")
    if score:
        meta = _json.dumps({"score": float(score)})
    db.session.add(ConfigOption(
        school_id=sid,
        option_type=request.form["option_type"],
        code=request.form["code"],
        name_ar=request.form["name_ar"],
        order=request.form.get("order", 0, type=int),
        metadata_json=meta,
    ))
    db.session.commit()
    flash_msg("admin_option_added", "success", sid)
    return redirect(url_for("admin.index"))


@bp.route("/ratings/<int:rating_id>/toggle", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def toggle_rating(rating_id):
    r = RatingLevel.query.get_or_404(rating_id)
    r.is_active = not r.is_active
    db.session.commit()
    flash_msg("admin_rating_updated", "success", _school_id())
    return redirect(request.referrer or url_for("admin.index"))


@bp.route("/config-option/<int:option_id>/edit", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def edit_config_option(option_id):
    import json as _json
    opt = ConfigOption.query.get_or_404(option_id)
    opt.name_ar = request.form.get("name_ar", opt.name_ar)
    opt.order = request.form.get("order", opt.order, type=int)
    score = request.form.get("score")
    if score and opt.option_type == "behavior_type":
        opt.metadata_json = _json.dumps({"score": float(score)})
    db.session.commit()
    flash_msg("admin_option_updated", "success", _school_id())
    anchor = request.form.get("anchor", "tab-options")
    return redirect((request.referrer or url_for("admin.index")) + f"#{anchor}")


@bp.route("/advanced-settings", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def save_advanced_settings():
    sid = _school_id()
    count = save_settings_bulk(request.form, sid)
    log_action("save_advanced_settings", "admin", f"updated={count}, school={sid}")
    flash_msg("admin_advanced_saved", "success", sid, count=count)
    return redirect(url_for("admin.index") + "#tab-advanced")


@bp.route("/platform-setting", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def create_platform_setting():
    sid = _school_id()
    try:
        add_platform_setting(
            key=request.form.get("key", ""),
            value=request.form.get("value", ""),
            school_id=sid,
            category=request.form.get("category", "general"),
            label_ar=request.form.get("label_ar", ""),
            value_type=request.form.get("value_type") or None,
        )
        log_action("add_platform_setting", "admin", f"key={request.form.get('key')}, school={sid}")
        flash_msg("admin_setting_added", "success", sid)
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("admin.index") + "#tab-advanced")


@bp.route("/config-option/<int:option_id>/toggle", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def toggle_config_option(option_id):
    opt = ConfigOption.query.get_or_404(option_id)
    opt.is_active = not opt.is_active
    db.session.commit()
    flash_msg("admin_option_updated", "success", _school_id())
    return redirect(url_for("admin.index"))


@bp.route("/content-labels", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def save_content_labels():
    sid = _school_id()
    nav = dict(get_nav_labels(sid))
    for key in NAV_LABELS_SEED:
        val = request.form.get(f"nav_{key}")
        if val is not None:
            nav[key] = val.strip()
    set_setting("nav_labels_json", dumps_json(nav), sid, "ui", "تسميات القائمة الرئيسية")

    pages = dict(get_page_labels(sid))
    for key in PAGE_LABELS_SEED:
        val = request.form.get(f"page_{key}")
        if val is not None:
            pages[key] = val.strip()
    set_setting("page_labels_json", dumps_json(pages), sid, "pages", "عناوين الصفحات والأقسام")

    log_action("save_content_labels", "admin", f"school={sid}")
    flash_msg("admin_content_labels_saved", "success", sid)
    return redirect(url_for("admin.index") + "#tab-content")


@bp.route("/provision-school/<int:school_id>", methods=["POST"])
@login_required
@permission_required("manage_global_config", "manage_platform_config")
def provision_school(school_id):
    ensure_school_defaults(school_id)
    provision_school_kpis(school_id)
    flash_msg("admin_school_provisioned", "success", school_id)
    return redirect(url_for("admin.index"))


@bp.route("/messages", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def save_messages():
    sid = _school_id()
    messages = dict(get_messages(sid))
    for key in MESSAGES_SEED:
        val = request.form.get(f"msg_{key}")
        if val is not None:
            messages[key] = val.strip()
    set_setting("flash_messages_json", dumps_json(messages), sid, "messages", "رسائل النظام")
    log_action("save_messages", "admin", f"school={sid}")
    flash_msg("admin_messages_saved", "success", sid)
    return redirect(url_for("admin.index") + "#tab-messages")


@bp.route("/survey-fields", methods=["POST"])
@login_required
@permission_required("manage_platform_config")
def save_survey_fields():
    sid = _school_id()
    family_rows = parse_family_survey_admin_form(request.form)
    teacher_rows = parse_teacher_survey_admin_form(request.form)
    save_family_survey_fields_admin(family_rows, sid)
    save_teacher_survey_fields_admin(teacher_rows, sid)

    _, program_sections_raw = admin_program_survey_rows(sid)
    program_sections = parse_program_survey_admin_form(request.form, program_sections_raw)
    save_program_survey_sections_admin(program_sections, sid)

    log_action("save_survey_fields", "admin", f"school={sid}")
    flash_msg("admin_surveys_saved", "success", sid)
    return redirect(url_for("admin.index") + "#tab-surveys")
