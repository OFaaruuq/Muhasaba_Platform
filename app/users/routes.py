from flask import flash, jsonify, redirect, render_template, request, url_for
from app.services.message_service import flash_msg
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.users import bp
from app.extensions import db
from app.models import User, School, Role
from app.utils import permission_required
from app.utils.permissions import (
    assignable_roles, can_manage_user, can_assign_role, is_platform_admin,
    can_create_users, is_administrator_role, ADMINISTRATOR_ROLE_NAMES,
    clear_permission_cache,
)
from app.services.audit_service import log_action
from app.services.user_account_service import (
    create_user_by_admin, update_user_by_admin, resend_verification_email,
)
from app.services.user_profile_service import (
    provision_user_profiles, sync_user_profiles, user_profile_summary,
    school_structure_payload,
)


def _role_label(role):
    if role.name in ADMINISTRATOR_ROLE_NAMES:
        return f"{role.name_ar} — مسؤول"
    return role.name_ar


def _users_query(actor):
    query = User.query
    if not is_platform_admin(actor):
        query = query.filter_by(school_id=actor.school_id)
    return query


@bp.route("/")
@login_required
@permission_required("manage_users")
def index():
    query = _users_query(current_user)

    role_filter = request.args.get("role_id", type=int)
    school_filter = request.args.get("school_id", type=int)
    status_filter = (request.args.get("status") or "").strip()
    search = (request.args.get("q") or "").strip()

    if role_filter:
        query = query.filter_by(role_id=role_filter)
    if school_filter and is_platform_admin(current_user):
        query = query.filter_by(school_id=school_filter)
    if status_filter == "active":
        query = query.filter_by(is_active=True)
    elif status_filter == "inactive":
        query = query.filter_by(is_active=False)
    elif status_filter == "unverified":
        query = query.filter_by(email_verified=False)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                User.username.ilike(like),
                User.email.ilike(like),
                User.full_name_ar.ilike(like),
                User.full_name.ilike(like),
                User.platform_uid.ilike(like),
            )
        )

    users = query.order_by(User.role_id, User.full_name_ar).all()
    roles = assignable_roles(current_user)
    schools = (
        School.query.filter_by(is_active=True).order_by(School.name_ar).all()
        if is_platform_admin(current_user) else []
    )
    manageable = {u.id: can_manage_user(current_user, u) for u in users}
    profiles = {u.id: user_profile_summary(u) for u in users}

    return render_template(
        "users/index.html",
        users=users,
        roles=roles,
        schools=schools,
        role_label=_role_label,
        is_administrator_role=is_administrator_role,
        manageable=manageable,
        profiles=profiles,
        selected_role=role_filter,
        selected_school=school_filter,
        selected_status=status_filter,
        search=search,
        is_platform_admin_view=is_platform_admin(current_user),
    )


@bp.route("/api/school-data")
@login_required
@permission_required("manage_users", "create_users")
def school_data():
    school_id = request.args.get("school_id", type=int)
    if not school_id:
        return jsonify({"error": "school_id required"}), 400
    if not is_platform_admin(current_user) and school_id != current_user.school_id:
        return jsonify({"error": "forbidden"}), 403
    school = School.query.get(school_id)
    if not school:
        return jsonify({"error": "not found"}), 404
    return jsonify(school_structure_payload(school_id))


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
            profiles = provision_user_profiles(user, request.form, role.name, school_id)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("users.create"))

        log_action(
            "create_user", "users",
            f"Created {user.username} as {role.name} profiles={profiles}",
        )
        db.session.commit()
        if profiles:
            flash_msg("sa_user_created_profiles", "success", profiles=", ".join(profiles))
        elif is_administrator_role(role.name):
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
        role_names={r.id: r.name for r in roles},
        create_teacher_checked=False,
        create_student_checked=False,
        employee_id="",
        specialization="",
        student_number="",
        teacher_classes=[],
        student_grade_id=None,
        student_class_id=None,
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


@bp.route("/<int:user_id>/resend-verification", methods=["POST"])
@login_required
@permission_required("manage_users")
def resend_verification(user_id):
    user = User.query.get_or_404(user_id)
    if not can_manage_user(current_user, user):
        flash_msg("permission_denied", "danger")
        return redirect(url_for("users.index"))
    try:
        resend_verification_email(user)
        log_action("resend_verification", "users", user.username)
        flash_msg("sa_verification_sent", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    return redirect(url_for("users.index"))


@bp.route("/<int:user_id>/delete", methods=["POST"])
@login_required
@permission_required("manage_users")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash_msg("sa_cannot_delete_self", "danger")
        return redirect(url_for("users.index"))
    if not can_manage_user(current_user, user):
        flash_msg("permission_denied", "danger")
        return redirect(url_for("users.index"))
    username = user.username
    db.session.delete(user)
    log_action("delete_user", "users", f"Deleted {username}")
    db.session.commit()
    flash_msg("sa_user_deleted", "success")
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
    schools = (
        School.query.filter_by(is_active=True).order_by(School.name_ar).all()
        if is_platform_admin(current_user) else []
    )

    if request.method == "POST":
        try:
            user, new_role = update_user_by_admin(current_user, user, request.form)
            profile_changes = sync_user_profiles(user, request.form, new_role.name)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("users.edit", user_id=user_id))

        log_action(
            "edit_user", "users",
            f"Updated {user.username} role={new_role.name} profiles={profile_changes}",
        )
        db.session.commit()
        clear_permission_cache()
        if is_administrator_role(new_role.name):
            flash_msg("users_assigned_admin", "success", role=new_role.name_ar)
        else:
            flash_msg("users_updated", "success")
        return redirect(url_for("users.index"))

    teacher_classes = []
    if user.teacher_profile:
        teacher_classes = [tc.class_id for tc in user.teacher_profile.class_assignments.all()]

    create_teacher_checked = bool(user.teacher_profile)
    create_student_checked = bool(user.student_profile)
    if user.role:
        if user.role.name == "teacher":
            create_teacher_checked = True
        if user.role.name == "student":
            create_student_checked = True

    return render_template(
        "users/edit.html",
        user=user,
        roles=roles,
        schools=schools,
        role_label=_role_label,
        is_administrator_role=is_administrator_role,
        role_names={r.id: r.name for r in roles},
        profile_summary=user_profile_summary(user),
        teacher_classes=teacher_classes,
        student_grade_id=user.student_profile.grade_id if user.student_profile else None,
        student_class_id=user.student_profile.class_id if user.student_profile else None,
        create_teacher_checked=create_teacher_checked,
        create_student_checked=create_student_checked,
        employee_id=user.teacher_profile.employee_id if user.teacher_profile else "",
        specialization=user.teacher_profile.specialization if user.teacher_profile else "",
        student_number=user.student_profile.student_id if user.student_profile else "",
        profile_platform_uid=user.platform_uid,
    )
