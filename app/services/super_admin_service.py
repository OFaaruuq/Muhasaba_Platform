"""Super admin dashboard data aggregation."""

from datetime import date, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models import (
    School, User, Student, Teacher, Role, AuditLog,
)


def _counts_by_school(model, active_only=False):
    query = db.session.query(model.school_id, func.count(model.id))
    if active_only and hasattr(model, "is_active"):
        query = query.filter(model.is_active == True)  # noqa: E712
    rows = query.group_by(model.school_id).all()
    return {school_id: count for school_id, count in rows}


def build_school_stats(schools):
    student_map = _counts_by_school(Student, active_only=True)
    teacher_map = _counts_by_school(Teacher, active_only=True)
    user_map = _counts_by_school(User)

    stats = []
    for school in schools:
        stats.append({
            "school": school,
            "students": student_map.get(school.id, 0),
            "teachers": teacher_map.get(school.id, 0),
            "users": user_map.get(school.id, 0),
        })
    return stats


def role_user_counts():
    rows = (
        db.session.query(Role.name_ar, Role.name, func.count(User.id))
        .outerjoin(User, User.role_id == Role.id)
        .group_by(Role.id, Role.name_ar, Role.name)
        .order_by(Role.name)
        .all()
    )
    return [{"name_ar": name_ar, "name": name, "count": count} for name_ar, name, count in rows]


def build_dashboard_context():
    from app.models import Tenant, LicenseRequest
    schools = School.query.order_by(School.name_ar).all()
    active_schools = sum(1 for s in schools if s.is_active)
    inactive_schools = len(schools) - active_schools

    users_count = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    inactive_users = users_count - active_users

    students_count = Student.query.filter_by(is_active=True).count()
    teachers_count = Teacher.query.filter_by(is_active=True).count()

    since = date.today() - timedelta(days=30)
    audit_30d = AuditLog.query.filter(AuditLog.created_at >= since).count()
    recent_audit = (
        AuditLog.query.order_by(AuditLog.created_at.desc()).limit(12).all()
    )

    return {
        "schools": schools,
        "schools_count": len(schools),
        "active_schools": active_schools,
        "inactive_schools": inactive_schools,
        "tenants_count": Tenant.query.count(),
        "pending_license_requests": LicenseRequest.query.filter_by(
            status=LicenseRequest.STATUS_PENDING
        ).count(),
        "users_count": users_count,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "students_count": students_count,
        "teachers_count": teachers_count,
        "roles_count": Role.query.count(),
        "role_counts": role_user_counts(),
        "school_stats": build_school_stats(schools),
        "recent_audit": recent_audit,
        "audit_30d": audit_30d,
    }


AUDIT_ACTION_LABELS = {
    "login": "تسجيل دخول",
    "logout": "تسجيل خروج",
    "create_user": "إنشاء مستخدم",
    "edit_user": "تعديل مستخدم",
    "delete_user": "حذف مستخدم",
    "toggle_user": "تبديل مستخدم",
    "toggle_school": "تبديل مدرسة",
    "grant_permission": "منح صلاحية",
    "revoke_permission": "سحب صلاحية",
    "provision_all_schools": "تهيئة المدارس",
    "reset_global_defaults": "تحديث الإعدادات",
    "save_settings": "حفظ إعدادات",
}


def audit_action_label(action):
    return AUDIT_ACTION_LABELS.get(action, action)
