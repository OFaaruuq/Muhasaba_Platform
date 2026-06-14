from flask import flash, redirect, render_template, request, url_for
from app.services.message_service import flash_msg
from flask_login import login_required, current_user

from app.users import bp
from app.extensions import db
from app.models import User, School, Role
from app.utils import permission_required
from app.utils.permissions import (
    assignable_roles, can_manage_user, can_assign_role, is_platform_admin,
    can_create_users, is_administrator_role, ADMINISTRATOR_ROLE_NAMES,
)
from app.services.audit_service import log_action
from app.services.user_account_service import create_user_by_admin


def _role_label(role):
    if role.name in ADMINISTRATOR_ROLE_NAMES:
        return f"{role.name_ar} — مسؤول"
    return role.name_ar


@bp.route("/")
@login_required
@permission_required("manage_users")
def index():
    query = User.query
    if not is_platform_admin(current_user):
        query = query.filter_by(school_id=current_user.school_id)
    users = query.order_by(User.role_id, User.full_name_ar).all()
    return render_template(
        "users/index.html",
        users=users,
        role_label=_role_label,
        is_administrator_role=is_administrator_role,
    )


@bp.route("/create", methods=["GET", "POST"])
@login_required
@permission_required("manage_users", "create_users")
def create():
    if not can_create_users(current_user):
        flash_msg("users_create_denied", "danger")
        return redirect(url_for("users.index"))

    roles = assignable_roles(current_user)
    schools = (
        School.query.filter_by(is_active=True).order_by(School.name_ar).all()
        if is_platform_admin(current_user) else []
    )
    default_school_id = current_user.school_id if not is_platform_admin(current_user) else None

    if request.method == "POST":
        role_id = int(request.form["role_id"])
        role = Role.query.get(role_id)
        if not role or not can_assign_role(current_user, role.name):
            flash_msg("users_role_not_allowed", "danger")
            return redirect(url_for("users.create"))

        school_id = request.form.get("school_id", type=int) or default_school_id
        try:
            user = create_user_by_admin(
                current_user,
                username=request.form["username"].strip(),
                email=request.form["email"],
                full_name_ar=request.form["full_name_ar"],
                password=request.form["password"],
                role_id=role_id,
                school_id=school_id,
                phone=request.form.get("phone"),
                is_active=request.form.get("is_active") == "on",
            )
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("users.create"))

        log_action("create_user", "users", f"Created {user.username} as {role.name}")
        db.session.commit()
        if is_administrator_role(role.name):
            flash_msg("users_created_admin", "success", role=role.name_ar)
        else:
            flash_msg("users_created", "success")
        return redirect(url_for("users.index"))

    return render_template(
        "users/create.html",
        roles=roles,
        schools=schools,
        default_school_id=default_school_id,
        role_label=_role_label,
        is_administrator_role=is_administrator_role,
        can_assign_admin=any(is_administrator_role(r.name) for r in roles),
    )


@bp.route("/<int:user_id>/toggle", methods=["POST"])
@login_required
@permission_required("manage_users")
def toggle_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash_msg("users_cannot_deactivate_self", "danger")
        return redirect(url_for("users.index"))
    if not can_manage_user(current_user, user):
        flash_msg("permission_denied", "danger")
        return redirect(url_for("users.index"))
    if not user.is_active and not user.email_verified:
        flash_msg("sa_activate_requires_email", "danger")
        return redirect(url_for("users.index"))
    user.is_active = not user.is_active
    log_action("toggle_user", "users", f"{user.username} active={user.is_active}")
    db.session.commit()
    flash_msg("users_status_updated", "success")
    return redirect(url_for("users.index"))


@bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_users")
def edit(user_id):
    user = User.query.get_or_404(user_id)
    if not can_manage_user(current_user, user):
        flash_msg("permission_denied", "danger")
        return redirect(url_for("users.index"))

    roles = assignable_roles(current_user)
    schools = School.query.filter_by(is_active=True).all() if is_platform_admin(current_user) else []

    if request.method == "POST":
        new_role_id = int(request.form["role_id"])
        new_role = next((r for r in roles if r.id == new_role_id), None)
        if not new_role or not can_assign_role(current_user, new_role.name):
            flash_msg("users_role_not_allowed", "danger")
            return redirect(url_for("users.edit", user_id=user_id))

        user.full_name_ar = request.form["full_name_ar"]
        user.full_name = request.form["full_name_ar"]
        user.email = request.form["email"]
        user.phone = request.form.get("phone")
        user.role_id = new_role_id
        if is_platform_admin(current_user):
            user.school_id = request.form.get("school_id", type=int)
        if request.form.get("password"):
            user.set_password(request.form["password"])
        log_action("edit_user", "users", f"Updated {user.username} role={new_role.name}")
        db.session.commit()
        if is_administrator_role(new_role.name):
            flash_msg("users_assigned_admin", "success", role=new_role.name_ar)
        else:
            flash_msg("users_updated", "success")
        return redirect(url_for("users.index"))

    return render_template(
        "users/edit.html",
        user=user,
        roles=roles,
        schools=schools,
        role_label=_role_label,
        is_administrator_role=is_administrator_role,
    )
