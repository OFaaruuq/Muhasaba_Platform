"""Dynamic permission checks backed by database role_permissions."""

from flask import g

PROTECTED_USER_ROLES = frozenset({"super_admin", "ministry_admin"})

# Roles considered "administrator" (can manage school / platform users)
ADMINISTRATOR_ROLE_NAMES = frozenset({"school_manager", "ministry_admin"})


def role_name(user):
    return user.role.name if user and user.is_authenticated and user.role else ""


def _permission_cache(user):
    cache = getattr(g, "_user_perm_cache", None)
    if cache and cache.get("user_id") == getattr(user, "id", None):
        return cache["names"]
    names = set()
    if user and user.is_authenticated:
        from app.services.permission_registry import effective_user_permissions
        names = effective_user_permissions(user)
    g._user_perm_cache = {"user_id": getattr(user, "id", None), "names": names}
    return names


def user_has_permission(user, permission_name):
    if not user or not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    if not permission_name:
        return True
    return permission_name in _permission_cache(user)


def user_has_any_permission(user, *permission_names):
    if not permission_names:
        return user_has_permission(user, None)
    return any(user_has_permission(user, p) for p in permission_names)


def user_has_all_permissions(user, *permission_names):
    return all(user_has_permission(user, p) for p in permission_names)


def is_super_admin(user):
    return user_has_permission(user, "manage_system")


def is_platform_admin(user):
    return user_has_permission(user, "view_all_schools")


def can_access_all_schools(user):
    return is_platform_admin(user)


def can_manage_user(actor, target):
    if not actor.is_authenticated:
        return False
    if is_super_admin(actor):
        return True
    if is_platform_admin(target):
        return False
    if user_has_permission(actor, "manage_users") and user_has_permission(actor, "manage_school"):
        return (
            target.school_id == actor.school_id
            and role_name(target) not in PROTECTED_USER_ROLES
        )
    return False


def assignable_roles(actor):
    from app.models import Role

    if is_super_admin(actor):
        return Role.query.order_by(Role.name).all()
    if is_platform_admin(actor):
        return Role.query.filter(Role.name != "super_admin").order_by(Role.name).all()
    if user_has_permission(actor, "manage_users"):
        return Role.query.filter(
            Role.name.in_(["school_manager", "teacher", "parent", "student"])
        ).order_by(Role.name).all()
    return []


def is_administrator_role(role_name_value):
    return role_name_value in ADMINISTRATOR_ROLE_NAMES


def can_create_users(actor):
    return user_has_permission(actor, "create_users") or user_has_permission(actor, "manage_users")


def can_assign_administrator_role(actor, role_name_value):
    if not is_administrator_role(role_name_value):
        return True
    if is_super_admin(actor):
        return True
    return user_has_permission(actor, "assign_administrator")


def resolve_new_user_school_id(actor, school_id):
    """School managers can only create users in their own school."""
    if is_super_admin(actor) or is_platform_admin(actor):
        return school_id
    if user_has_permission(actor, "manage_school"):
        return actor.school_id
    return school_id


def can_assign_role(actor, role_name_value):
    if not can_assign_administrator_role(actor, role_name_value):
        return False
    if is_super_admin(actor):
        return True
    if role_name_value == "super_admin":
        return False
    if is_platform_admin(actor):
        return role_name_value != "super_admin"
    return role_name_value in ("school_manager", "teacher", "parent", "student")


def user_matches_legacy_roles(user, *role_names):
    from app.services.permission_registry import user_matches_legacy_roles as _match
    return _match(user, *role_names)


def clear_permission_cache():
    if hasattr(g, "_user_perm_cache"):
        del g._user_perm_cache
