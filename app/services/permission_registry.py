"""
Central registry for dynamic roles and permissions.

All platform permissions are defined here, synced to the database on startup,
and assigned to system roles by default. Super Admin can grant/revoke permissions
per role at runtime without code changes.
"""

from app.extensions import db
from app.models import Permission, Role

SYSTEM_ROLE_NAMES = frozenset({
    "super_admin",
    "ministry_admin",
    "school_manager",
    "teacher",
    "student",
    "parent",
})

# Built-in roles created automatically if missing (RBAC bootstrap)
SYSTEM_ROLE_DEFINITIONS = {
    "super_admin": ("المشرف الأعلى", "التحكم الكامل بالمنصة"),
    "ministry_admin": ("مسؤول الوزارة", "إدارة على مستوى الوزارة"),
    "school_manager": ("مدير المدرسة", "إدارة المدرسة"),
    "teacher": ("معلم", "تقييم الطلاب وإدارة الفصول"),
    "student": ("طالب", "عرض الأداء والمحاسبة الذاتية"),
    "parent": ("ولي أمر", "متابعة أداء الأبناء"),
}

# name -> (name_ar, module)
PERMISSIONS = {
    # System / platform
    "manage_system": ("إدارة النظام الكاملة", "system"),
    "manage_roles": ("إدارة الأدوار والصلاحيات", "system"),
    "view_audit_logs": ("عرض سجل التدقيق", "system"),
    "manage_global_config": ("إدارة الإعدادات العامة", "system"),
    # Schools & users
    "view_all_schools": ("عرض جميع المدارس", "schools"),
    "manage_school": ("إدارة المدرسة", "schools"),
    "manage_users": ("إدارة المستخدمين", "users"),
    "assign_administrator": ("تعيين دور المسؤول (مدير)", "users"),
    "create_users": ("إنشاء حسابات المستخدمين", "users"),
    "manage_platform_config": ("إعدادات المنصة", "admin"),
    # Staff & students
    "manage_teachers": ("إدارة المعلمين", "teachers"),
    "view_students": ("عرض الطلاب", "students"),
    "manage_students": ("إدارة الطلاب", "students"),
    "register_students": ("تسجيل الطلاب", "students"),
    # Attendance & evaluations
    "view_attendance": ("عرض الحضور", "attendance"),
    "record_attendance": ("تسجيل الحضور", "attendance"),
    "manage_evaluations": ("إدارة المحاسبة والتقييم", "evaluations"),
    "self_assess": ("المحاسبة الذاتية", "evaluations"),
    # KPI & exams
    "view_kpi": ("عرض مؤشرات الأداء", "kpi"),
    "manage_kpi": ("إدارة مؤشرات الأداء", "kpi"),
    "manage_exams": ("إدارة الاختبارات", "exams"),
    "take_exams": ("أداء الاختبارات", "exams"),
    # Surveys & follow-up
    "manage_questionnaires": ("إدارة الاستبيانات", "questionnaires"),
    "take_questionnaires": ("الإجابة على الاستبيانات", "questionnaires"),
    "manage_followup_surveys": ("إدارة المتابعة الشهرية", "followup"),
    "view_followup_surveys": ("عرض المتابعة الشهرية", "followup"),
    # Reports & AI
    "view_reports": ("عرض التقارير", "reports"),
    "view_children_kpi": ("متابعة أداء الأبناء", "parents"),
    "view_own_kpi": ("عرض مؤشرات الأداء الشخصية", "students"),
    "view_ai_assistant": ("المساعد الذكي", "ai"),
}

# Default permissions for built-in roles (synced on seed / upgrade)
DEFAULT_ROLE_PERMISSIONS = {
    "super_admin": list(PERMISSIONS.keys()),
    "ministry_admin": [
        "view_all_schools", "manage_school", "manage_users", "create_users",
        "assign_administrator",
        "manage_platform_config", "manage_global_config",
        "manage_teachers", "view_students", "manage_students", "register_students",
        "view_attendance", "record_attendance", "manage_evaluations",
        "view_kpi", "manage_kpi", "manage_exams",
        "manage_questionnaires", "take_questionnaires",
        "manage_followup_surveys", "view_followup_surveys",
        "view_reports", "view_ai_assistant",
    ],
    "school_manager": [
        "manage_school", "manage_users", "create_users", "assign_administrator",
        "manage_platform_config",
        "manage_teachers", "view_students", "manage_students", "register_students",
        "view_attendance", "record_attendance", "manage_evaluations",
        "view_kpi", "manage_kpi", "manage_exams",
        "manage_questionnaires", "take_questionnaires",
        "manage_followup_surveys", "view_followup_surveys",
        "view_reports", "view_ai_assistant",
    ],
    "teacher": [
        "view_students", "view_attendance", "record_attendance",
        "manage_evaluations", "view_kpi", "manage_exams",
        "take_questionnaires", "manage_followup_surveys", "view_followup_surveys",
        "view_reports", "view_ai_assistant",
    ],
    "student": [
        "self_assess", "take_exams", "take_questionnaires",
        "view_own_kpi", "view_followup_surveys",
    ],
    "parent": [
        "view_children_kpi", "view_reports", "take_questionnaires",
        "view_followup_surveys",
    ],
}

# Legacy role names (role_required) map to capability permissions
ROLE_CAPABILITY_PERMISSIONS = {
    "ministry_admin": [
        "view_all_schools", "manage_global_config", "manage_platform_config",
    ],
    "school_manager": ["manage_school", "manage_users", "manage_platform_config"],
    "teacher": [
        "record_attendance", "manage_evaluations", "manage_exams", "view_kpi",
    ],
    "student": ["self_assess", "take_exams", "take_questionnaires", "view_own_kpi"],
    "parent": ["view_children_kpi", "view_reports"],
}


def is_system_role(role):
    return role.name in SYSTEM_ROLE_NAMES


def sync_permissions():
    """Ensure every registered permission exists in the database."""
    existing = {p.name: p for p in Permission.query.all()}
    for name, (name_ar, module) in PERMISSIONS.items():
        perm = existing.get(name)
        if perm:
            perm.name_ar = name_ar
            perm.module = module
        else:
            db.session.add(Permission(name=name, name_ar=name_ar, module=module))
    db.session.flush()


def ensure_system_roles():
    """Create any missing system roles and ensure default permission grants."""
    sync_permissions()
    for role_name, (name_ar, description) in SYSTEM_ROLE_DEFINITIONS.items():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            db.session.add(Role(name=role_name, name_ar=name_ar, description=description))
    db.session.flush()
    apply_default_role_permissions(force=False)


def effective_user_permissions(user):
    """Union of role, profile, and per-user extra permissions."""
    from app.services.user_profile_service import profile_permissions_for_user

    names = profile_permissions_for_user(user)
    if user and getattr(user, "extra_permissions", None):
        names.update(p.name for p in user.extra_permissions)
    return names


def set_user_extra_permissions(user, permission_ids):
    """Replace direct per-user permission grants (additive to role)."""
    from app.models import Permission

    ids = {int(pid) for pid in permission_ids if pid}
    perms = Permission.query.filter(Permission.id.in_(ids)).all() if ids else []
    user.extra_permissions = perms
    return perms


def apply_default_role_permissions(force=False):
    """Assign default permissions to system roles."""
    sync_permissions()
    by_name = {p.name: p for p in Permission.query.all()}
    for role_name, perm_names in DEFAULT_ROLE_PERMISSIONS.items():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            continue
        targets = [by_name[n] for n in perm_names if n in by_name]
        if force:
            role.permissions = targets
        else:
            existing = {p.name for p in role.permissions}
            for perm in targets:
                if perm.name not in existing:
                    role.permissions.append(perm)
    db.session.commit()


def role_has_capability(user, role_name):
    """True if user holds any permission associated with a legacy role capability."""
    from app.utils.permissions import user_has_any_permission

    perms = ROLE_CAPABILITY_PERMISSIONS.get(role_name, [])
    if not perms:
        return False
    return user_has_any_permission(user, *perms)


def user_matches_legacy_roles(user, *role_names):
    """Check role name or dynamic permissions for legacy @role_required decorators."""
    if not role_names:
        return True
    if user.role and user.role.name in role_names:
        return True
    return any(role_has_capability(user, rn) for rn in role_names)


def has_teacher_capabilities(user):
    from app.utils.permissions import user_has_any_permission
    return user_has_any_permission(
        user, "record_attendance", "manage_evaluations", "manage_exams",
    )


def has_student_capabilities(user):
    from app.utils.permissions import user_has_permission
    return user_has_permission(user, "self_assess") or (
        user.role and user.role.name == "student"
    )


def has_parent_capabilities(user):
    from app.utils.permissions import user_has_permission
    return user_has_permission(user, "view_children_kpi") or (
        user.role and user.role.name == "parent"
    )


def dashboard_type_for_user(user):
    """Resolve which dashboard view to show based on permissions and profiles."""
    from flask import session
    from app.utils.permissions import user_has_permission

    mode = session.get("dashboard_mode")
    if mode == "student" and user.student_profile and user.student_profile.is_active:
        return "student"
    if mode == "teacher" and user.is_teacher:
        return "teacher"

    if user_has_permission(user, "manage_system"):
        return "super_admin"
    if user.role and user.role.name == "ministry_admin":
        return "ministry"
    if user_has_permission(user, "view_all_schools") and user_has_permission(user, "manage_global_config"):
        return "ministry"
    if user_has_permission(user, "manage_school"):
        return "school_manager"
    if user.is_teacher:
        return "teacher"
    if user.student_profile and user.student_profile.is_active:
        return "student"
    if user.parent_profile:
        return "parent"
    return "default"


def user_has_dual_teacher_student_profiles(user):
    return bool(
        user.is_teacher
        and user.student_profile
        and user.student_profile.is_active
    )


def permissions_by_module():
    """Group permissions for admin UI."""
    grouped = {}
    for name, (name_ar, module) in PERMISSIONS.items():
        grouped.setdefault(module, []).append({
            "name": name,
            "name_ar": name_ar,
            "module": module,
        })
    return grouped
