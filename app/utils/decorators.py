from functools import wraps

from flask import abort, flash, redirect, url_for
from flask_login import current_user

from app.utils.permissions import user_has_any_permission, user_has_all_permissions


def permission_required(*permission_names, require_all=False):
    """Require the user to hold at least one permission (or all if require_all=True)."""

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            ok = (
                user_has_all_permissions(current_user, *permission_names)
                if require_all
                else user_has_any_permission(current_user, *permission_names)
            )
            if not ok:
                flash("ليس لديك صلاحية للوصول إلى هذه الصفحة.", "danger")
                abort(403)
            return f(*args, **kwargs)

        return wrapped

    return decorator


def role_required(*roles):
    """Legacy role guard — also honors dynamic permissions mapped to those roles."""

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            from app.utils.permissions import is_super_admin, user_matches_legacy_roles

            if is_super_admin(current_user) or user_matches_legacy_roles(current_user, *roles):
                return f(*args, **kwargs)
            flash("ليس لديك صلاحية للوصول إلى هذه الصفحة.", "danger")
            abort(403)

        return wrapped

    return decorator


def school_scoped_query(query, model):
    """Filter query to current user's school unless platform admin."""
    from app.utils.permissions import is_platform_admin

    if is_platform_admin(current_user):
        return query
    if current_user.school_id:
        return query.filter(model.school_id == current_user.school_id)
    return query.filter(False)
