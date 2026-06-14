from flask import session, request
from flask_login import current_user


def get_active_school_id():
    """Resolve school context: manager/teacher use their school; ministry uses session picker."""
    if not current_user.is_authenticated:
        return None
    if current_user.is_platform_admin:
        sid = session.get("active_school_id") or request.args.get("school_id", type=int)
        return sid
    return current_user.school_id


def set_active_school_id(school_id):
    session["active_school_id"] = school_id


def get_schools_for_picker():
    from app.models import School
    if current_user.is_platform_admin:
        return School.query.filter_by(is_active=True).order_by(School.name_ar).all()
    if current_user.school_id:
        from app.models import School
        return School.query.filter_by(id=current_user.school_id).all()
    return []
