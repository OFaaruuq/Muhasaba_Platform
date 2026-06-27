import logging
import os

from flask import Flask
from flask_wtf.csrf import CSRFProtect

from config import Config
from app.extensions import db, migrate, login_manager, jwt, limiter

csrf = CSRFProtect()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder=os.path.join(basedir, "templates"),
        static_folder=os.path.join(basedir, "static"),
    )
    app.config.from_object(config_class)
    from config import finalize_app_config
    finalize_app_config(app)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["REPORTS_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    jwt.init_app(app)
    csrf.init_app(app)

    limiter.enabled = app.config.get("RATELIMIT_ENABLED", True) and not app.config.get("TESTING")
    limiter.init_app(app)

    if not app.config.get("TESTING"):
        with app.app_context():
            from app.utils.database import (
                validate_connection,
                database_label,
                get_dialect,
                init_database,
            )

            try:
                validate_connection()
                logging.getLogger(__name__).info(
                    "Database connected (%s): %s",
                    get_dialect(),
                    database_label(app),
                )
            except Exception as exc:
                logging.getLogger(__name__).error(
                    "Database connection failed (%s): %s — check .env DATABASE_URL / POSTGRES_*",
                    database_label(app),
                    exc,
                )
                raise
            init_database(seed=False)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.auth import bp as auth_bp
    from app.schools import bp as schools_bp
    from app.students import bp as students_bp
    from app.teachers import bp as teachers_bp
    from app.attendance import bp as attendance_bp
    from app.evaluations import bp as evaluations_bp
    from app.kpi import bp as kpi_bp
    from app.questionnaires import bp as questionnaires_bp
    from app.exams import bp as exams_bp
    from app.reports import bp as reports_bp
    from app.dashboards import bp as dashboards_bp
    from app.notifications import bp as notifications_bp
    from app.users import bp as users_bp
    from app.admin import bp as admin_bp
    from app.super_admin import bp as super_admin_bp
    from app.followup_surveys import bp as followup_surveys_bp
    from app.ai import bp as ai_bp
    from app.academic import bp as academic_bp
    from app.tenants import bp as tenants_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(schools_bp, url_prefix="/schools")
    app.register_blueprint(students_bp, url_prefix="/students")
    app.register_blueprint(teachers_bp, url_prefix="/teachers")
    app.register_blueprint(attendance_bp, url_prefix="/attendance")
    app.register_blueprint(evaluations_bp, url_prefix="/evaluations")
    app.register_blueprint(kpi_bp, url_prefix="/kpi")
    app.register_blueprint(questionnaires_bp, url_prefix="/questionnaires")
    app.register_blueprint(exams_bp, url_prefix="/exams")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(dashboards_bp, url_prefix="/dashboard")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(super_admin_bp, url_prefix="/super-admin")
    app.register_blueprint(followup_surveys_bp, url_prefix="/followup-surveys")
    app.register_blueprint(ai_bp, url_prefix="/ai")
    app.register_blueprint(academic_bp, url_prefix="/academic/api")
    app.register_blueprint(tenants_bp)

    csrf.exempt(app.view_functions["auth.api_token"])
    csrf.exempt(app.view_functions["auth.api_verify_otp"])

    from app.auth.routes import AUTH_PUBLIC_ENDPOINTS

    LICENSE_EXEMPT_ENDPOINTS = AUTH_PUBLIC_ENDPOINTS | {
        "static",
        "tenants.license_status",
        "auth.logout",
    }

    @app.before_request
    def enforce_active_verified_users():
        from flask import request, redirect, url_for
        from flask_login import current_user, logout_user

        if request.endpoint in LICENSE_EXEMPT_ENDPOINTS:
            return None
        if current_user.is_authenticated:
            if not current_user.is_active or not current_user.email_verified:
                logout_user()
                from app.services.message_service import flash_msg
                flash_msg("auth_account_inactive", "danger")
                return redirect(url_for("auth.login"))
        return None

    @app.before_request
    def enforce_tenant_license():
        from flask import request, redirect, url_for
        from flask_login import current_user
        from app.services.tenant_service import (
            get_user_tenant, tenant_has_active_license, get_platform_owner_tenant,
        )
        from app.services.message_service import flash_msg

        if request.endpoint in LICENSE_EXEMPT_ENDPOINTS:
            return None
        if not current_user.is_authenticated:
            return None
        if current_user.has_permission("manage_system"):
            return None
        tenant = get_user_tenant(current_user)
        if not tenant:
            return None
        owner = get_platform_owner_tenant()
        if owner and tenant.id == owner.id:
            return None
        if not tenant_has_active_license(tenant):
            flash_msg("license_expired", "warning")
            return redirect(url_for("tenants.license_status"))
        return None

    import json as _json

    @app.template_filter("fromjson")
    def fromjson_filter(value):
        if not value:
            return {}
        try:
            return _json.loads(value)
        except (TypeError, ValueError):
            return {}

    @app.template_filter("model_get")
    def model_get_filter(obj, attr):
        return getattr(obj, attr, None) if obj else None

    @app.template_filter("plabel")
    def plabel_filter(text, **kwargs):
        result = str(text or "")
        for key, val in kwargs.items():
            result = result.replace("{" + key + "}", str(val))
        return result

    @app.route("/")
    def index():
        from flask import redirect, url_for
        from flask_login import current_user

        if current_user.is_authenticated:
            return redirect(url_for("dashboards.index"))
        return redirect(url_for("auth.login"))

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not app.config.get("FLASK_DEBUG"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = csp
        return response

    @app.context_processor
    def inject_globals():
        from flask import session
        from flask_login import current_user
        from app.models import Notification
        from app.services.permission_registry import user_has_dual_teacher_student_profiles
        from app.services.config_service import (
            get_setting, get_kpi_source_description, get_attendance_status_map,
            get_gender_label, get_config_map, get_performance_label,
            get_gender_choices, get_config_choices, get_monthly_rating_choices,
            get_performance_thresholds, get_criterion_category_labels,
            get_monthly_category_labels, get_behavior_type_scores,
            get_ui_labels, get_config_map as _cfg_map,
            get_monthly_scale_summary, get_bool_choices, get_demo_accounts,
            get_report_labels, get_unspecified_label, get_kpi_period_choices,
            get_org_labels, get_role_labels, get_role_display, get_nav_labels,
            get_registration_section_labels, get_page_labels,
        )
        from app.services.survey_config_service import get_education_stage_field_map
        from app.utils.school_context import get_active_school_id, get_schools_for_picker
        from app.services.tenant_service import get_user_tenant, get_active_license, tenant_has_active_license

        unread = 0
        sid = None
        schools_picker = []
        if current_user.is_authenticated:
            unread = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()
            sid = get_active_school_id()
            schools_picker = get_schools_for_picker()

        name = get_setting("platform_name_ar", sid) or app.config["PLATFORM_NAME"]
        tagline = get_setting("platform_tagline_ar", sid) or app.config["PLATFORM_TAGLINE"]

        current_tenant = None
        tenant_license = None
        if current_user.is_authenticated:
            current_tenant = get_user_tenant(current_user)
            if current_tenant:
                if current_tenant.platform_name_ar:
                    name = current_tenant.platform_name_ar
                if current_tenant.platform_tagline_ar:
                    tagline = current_tenant.platform_tagline_ar
                tenant_license = get_active_license(current_tenant)

        return {
            "platform_name": name,
            "platform_tagline": tagline,
            "current_tenant": current_tenant,
            "tenant_license": tenant_license,
            "tenant_has_license": tenant_has_active_license(current_tenant) if current_tenant else True,
            "unread_notifications": unread,
            "active_school_id": sid,
            "schools_picker": schools_picker,
            "get_kpi_source_description": get_kpi_source_description,
            "attendance_status_map": get_attendance_status_map(sid),
            "get_gender_label": get_gender_label,
            "get_performance_label": get_performance_label,
            "gender_labels": get_config_map("gender", sid),
            "gender_choices": get_gender_choices(sid),
            "true_false_choices": get_config_choices("true_false", sid),
            "yes_no_choices": get_config_choices("yes_no", sid),
            "rating_scale_choices": get_monthly_rating_choices(sid),
            "show_demo_logins": str(get_setting("show_demo_logins", sid, "false")).lower() in ("true", "1", "yes"),
            "perf_thresholds": get_performance_thresholds(sid),
            "exam_type_labels": get_config_map("exam_type", sid),
            "criterion_category_labels": get_criterion_category_labels(sid),
            "monthly_category_labels": get_monthly_category_labels(sid),
            "behavior_type_scores": get_behavior_type_scores(sid),
            "default_class_capacity": get_setting("default_class_capacity", sid, 30),
            "ui_labels": get_ui_labels(sid),
            "exam_question_type_labels": _cfg_map("exam_question_type", sid),
            "questionnaire_category_labels": _cfg_map("questionnaire_category", sid),
            "monthly_scale_summary": get_monthly_scale_summary(sid),
            "bool_choices": get_bool_choices(sid),
            "demo_accounts": get_demo_accounts(sid) if str(get_setting("show_demo_logins", sid, "false")).lower() in ("true", "1", "yes") else [],
            "report_labels": get_report_labels(sid),
            "unspecified_label": get_unspecified_label(sid),
            "kpi_period_choices": get_kpi_period_choices(sid),
            "nav_labels": get_nav_labels(sid),
            "page_labels": get_page_labels(sid),
            "registration_section_labels": get_registration_section_labels(sid),
            "education_stage_fields": get_education_stage_field_map(sid),
            "org_labels": get_org_labels(sid),
            "role_labels": get_role_labels(),
            "get_role_display": get_role_display,
            "user_can": _user_can,
            "user_can_any": _user_can_any,
            "dual_teacher_student": (
                user_has_dual_teacher_student_profiles(current_user)
                if current_user.is_authenticated else False
            ),
            "dashboard_mode": session.get("dashboard_mode") if current_user.is_authenticated else None,
            "person_label": _person_label,
            "can_view_person_names": _can_view_person_names,
        }

    return app


def _user_can(permission_name):
    from flask_login import current_user
    if not current_user.is_authenticated:
        return False
    return current_user.has_permission(permission_name)


def _user_can_any(*permission_names):
    from flask_login import current_user
    if not current_user.is_authenticated:
        return False
    return current_user.has_any_permission(*permission_names)


def _person_label(subject):
    from flask_login import current_user
    from app.services.identity_service import person_display_label
    return person_display_label(subject, current_user)


def _can_view_person_names():
    from flask_login import current_user
    from app.services.identity_service import can_view_person_names
    return can_view_person_names(current_user)
