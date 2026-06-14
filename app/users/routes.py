from flask import flash, redirect, render_template, request, url_for
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
    roles = assignable_roles(current_user)
    schools = School.query.filter_by(is_active=True).all() if is_platform_admin(current_user) else []

    if request.method == "POST":
        username = request.form["username"].strip()
        if User.query.filter_by(username=username).first():
            flash("اسم المستخدم موجود.", "danger")
            return redirect(url_for("users.create"))

        role_id = int(request.form["role_id"])
        role = next((r for r in roles if r.id == role_id), None)
        if not role or not can_assign_role(current_user, role.name):
            flash("لا يمكن تعيين هذا الدور.", "danger")
            return redirect(url_for("users.create"))

        school_id = request.form.get("school_id", type=int) or current_user.school_id
        user = User(
            username=username,
            email=request.form["email"],
            full_name=request.form["full_name_ar"],
            full_name_ar=request.form["full_name_ar"],
            phone=request.form.get("phone"),
            role_id=role_id,
            school_id=school_id,
        )
        user.set_password(request.form["password"])
        db.session.add(user)
        log_action("create_user", "users", f"Created {username}")
        db.session.commit()
        flash("تم إنشاء المستخدم.", "success")
        return redirect(url_for("users.index"))

    return render_template("users/create.html", roles=roles, schools=schools)


@bp.route("/<int:user_id>/toggle", methods=["POST"])
@login_required
@permission_required("manage_users")
def toggle_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("لا يمكن تعطيل حسابك.", "danger")
        return redirect(url_for("users.index"))
    if not can_manage_user(current_user, user):
        flash("ليس لديك صلاحية.", "danger")
        return redirect(url_for("users.index"))
    user.is_active = not user.is_active
    log_action("toggle_user", "users", f"{user.username} active={user.is_active}")
    db.session.commit()
    flash("تم تحديث حالة المستخدم.", "success")
    return redirect(url_for("users.index"))


@bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_users")
def edit(user_id):
    user = User.query.get_or_404(user_id)
    if not can_manage_user(current_user, user):
        flash("ليس لديك صلاحية.", "danger")
        return redirect(url_for("users.index"))

    roles = assignable_roles(current_user)
    schools = School.query.filter_by(is_active=True).all() if is_platform_admin(current_user) else []

    if request.method == "POST":
        new_role_id = int(request.form["role_id"])
        new_role = next((r for r in roles if r.id == new_role_id), None)
        if not new_role or not can_assign_role(current_user, new_role.name):
            flash("لا يمكن تعيين هذا الدور.", "danger")
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
        flash("تم تحديث المستخدم.", "success")
        return redirect(url_for("users.index"))

    return render_template("users/edit.html", user=user, roles=roles, schools=schools)
