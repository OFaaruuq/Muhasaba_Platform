"""Dual authentication for JSON API routes: JWT Bearer token or Flask-Login session."""

from functools import wraps

from flask import g, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask_login import current_user

from app.extensions import db
from app.models import User
from app.utils.permissions import (
    is_super_admin, user_has_any_permission, user_has_all_permissions,
)


def get_authenticated_user():
    """Return the active user from JWT or session, or None."""
    try:
        verify_jwt_in_request(optional=True)
        uid = get_jwt_identity()
        if uid:
            user = db.session.get(User, int(uid))
            if user and user.is_active:
                return user
    except Exception:
        pass
    if current_user.is_authenticated and current_user.is_active:
        return current_user
    return None


def api_auth_required(*permission_names, require_all=False):
    """Require JWT or session auth; optionally restrict to permission names."""

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user = get_authenticated_user()
            if not user:
                return jsonify({"error": "غير مصرح — يلزم تسجيل الدخول أو رمز JWT"}), 401
            if permission_names:
                ok = (
                    user_has_all_permissions(user, *permission_names)
                    if require_all
                    else (is_super_admin(user) or user_has_any_permission(user, *permission_names))
                )
                if not ok:
                    return jsonify({"error": "غير مصرح"}), 403
            g.api_user = user
            return f(*args, **kwargs)

        return wrapped

    return decorator


def api_user():
    """Current API user (JWT or session). Use inside @api_auth_required routes."""
    return g.get("api_user") or current_user
