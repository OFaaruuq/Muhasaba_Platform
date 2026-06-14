from flask import flash, redirect, render_template, request, url_for
from app.services.message_service import flash_msg
from flask_login import login_required, current_user

from app.users import bp
from app.extensions import db
from app.models import User, School
from app.utils import permission_required
from app.utils.permissions import (
    assignable_roles, can_manage_user, can_assign_role, is_platform_admin,
)
from app.services.audit_service import log_action


@bp.route("/")
@login_required
@permission_required("manage_users")
def index():
    query = User.query
    if not is_platform_admin(current_user):
        query = query.filter_by(school_id=current_user.school_id)
    users = query.order_by(User.role_id, User.full_name_ar).all()
    return render_template("users/index.html", users=users)


@bp.route("/create", methods=["GET", "POST"])
@login_required
@permission_required("manage_users")
def create():
    flash_msg("users_create_super_admin_only", "warning")
    return redirect(url_for("users.index"))


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
        user.email = request.form["email"]
        user.phone = request.form.get("phone")
        user.role_id = new_role_id
        if is_platform_admin(current_user):
            user.school_id = request.form.get("school_id", type=int)
        if request.form.get("password"):
            user.set_password(request.form["password"])
        log_action("edit_user", "users", f"Updated {user.username}")
        db.session.commit()
        flash_msg("users_updated", "success")
        return redirect(url_for("users.index"))

    return render_template("users/edit.html", user=user, roles=roles, schools=schools)
