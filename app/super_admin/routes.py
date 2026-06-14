from datetime import date, timedelta

from flask import flash, redirect, render_template, request, url_for, jsonify
from app.services.message_service import flash_msg
from flask_login import login_required, current_user

from app.super_admin import bp
from app.extensions import db
from app.models import (
    User, Role, Permission, School, Student, Teacher,
    AuditLog, KPI, PlatformSetting,
)
from app.services.config_service import ensure_school_defaults, provision_school_kpis
from app.services.audit_service import log_action
from app.services.super_admin_service import build_dashboard_context, audit_action_label
from app.services.school_service import can_delete_school
from app.services.config_service import set_setting, sync_central_admin_role_label
from app.utils import permission_required
from app.utils.permissions import can_manage_user, can_assign_role
from app.services.user_account_service import create_user_by_super_admin, resend_verification_email
from app.services.user_profile_service import (
    provision_user_profiles,
    sync_user_profiles,
    school_structure_payload,
    user_profile_summary,
)
from app.services.permission_registry import (
    is_system_role, SYSTEM_ROLE_NAMES, permissions_by_module, sync_permissions,
    apply_default_role_permissions, ensure_system_roles, set_user_extra_permissions,
)
from app.utils.permissions import clear_permission_cache
import re


@bp.route("/")
@login_required
@permission_required("manage_system")
def index():
    ctx = build_dashboard_context()
    ctx["audit_action_label"] = audit_action_label
    return render_template("super_admin/index.html", **ctx)


@bp.route("/users")
@login_required
@permission_required("manage_system")
def users():
    role_filter = request.args.get("role")
    school_filter = request.args.get("school_id", type=int)
    query = User.query
    if role_filter:
        query = query.join(Role).filter(Role.name == role_filter)
    if school_filter:
        query = query.filter(User.school_id == school_filter)
    users_list = query.order_by(User.created_at.desc()).all()
    roles = Role.query.order_by(Role.name).all()
    schools = School.query.order_by(School.name_ar).all()
    return render_template(
        "super_admin/users.html",
        users=users_list,
        roles=roles,
        schools=schools,
        selected_role=role_filter,
        selected_school=school_filter,
    )


@bp.route("/users/create", methods=["GET", "POST"])
@login_required
@permission_required("manage_system")
def create_user():
    roles = Role.query.order_by(Role.name).all()
    schools = School.query.filter_by(is_active=True).order_by(School.name_ar).all()

    if request.method == "POST":
        username = request.form["username"].strip()
        role_id = int(request.form["role_id"])
        role = Role.query.get(role_id)
        if not role or not can_assign_role(current_user, role.name):
            flash_msg("users_role_not_allowed", "danger")
            return redirect(url_for("super_admin.create_user"))

        if User.query.filter_by(username=username).first():
            flash_msg("sa_username_taken", "danger")
            return redirect(url_for("super_admin.create_user"))

        try:
            school_id = request.form.get("school_id", type=int)
            user = create_user_by_super_admin(
                username=username,
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
            return redirect(url_for("super_admin.create_user"))

        log_action(
            "create_user", "users",
            f"Created {username} as {role.name} profiles={profiles}",
        )
        db.session.commit()
        if profiles:
            flash_msg("sa_user_created_profiles", "success", profiles=", ".join(profiles))
        else:
            flash_msg("sa_user_created", "success")
        return redirect(url_for("super_admin.users"))

    return render_template(
        "super_admin/create_user.html",
        roles=roles,
        schools=schools,
        role_names={r.id: r.name for r in roles},
    )


@bp.route("/api/school-data")
@login_required
@permission_required("manage_system")
def school_data():
    school_id = request.args.get("school_id", type=int)
    if not school_id:
        return jsonify({"error": "school_id required"}), 400
    school = School.query.get(school_id)
    if not school:
        return jsonify({"error": "not found"}), 404
    return jsonify(school_structure_payload(school_id))


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_system")
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    roles = Role.query.order_by(Role.name).all()
    schools = School.query.filter_by(is_active=True).order_by(School.name_ar).all()

    if request.method == "POST":
        new_role_id = int(request.form["role_id"])
        new_role = Role.query.get(new_role_id)
        if not new_role or not can_assign_role(current_user, new_role.name):
            flash_msg("users_role_not_allowed", "danger")
            return redirect(url_for("super_admin.edit_user", user_id=user_id))

        user.full_name_ar = request.form["full_name_ar"]
        user.full_name = request.form["full_name_ar"]
        user.email = request.form["email"]
        user.phone = request.form.get("phone")
        user.role_id = new_role_id
        user.school_id = request.form.get("school_id", type=int)
        if request.form.get("password"):
            user.set_password(request.form["password"])

        try:
            profile_changes = sync_user_profiles(user, request.form, new_role.name)
            set_user_extra_permissions(user, request.form.getlist("extra_permission_ids"))
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("super_admin.edit_user", user_id=user_id))

        log_action(
            "edit_user", "users",
            f"Updated user {user.username} profiles={profile_changes}",
        )
        db.session.commit()
        clear_permission_cache()
        flash_msg("sa_user_updated", "success")
        return redirect(url_for("super_admin.users"))

    teacher_classes = []
    if user.teacher_profile:
        teacher_classes = [tc.class_id for tc in user.teacher_profile.class_assignments.all()]

    return render_template(
        "super_admin/edit_user.html",
        user=user,
        roles=roles,
        schools=schools,
        role_names={r.id: r.name for r in roles},
        profile_summary=user_profile_summary(user),
        teacher_classes=teacher_classes,
        student_grade_id=user.student_profile.grade_id if user.student_profile else None,
        student_class_id=user.student_profile.class_id if user.student_profile else None,
        permissions_grouped=permissions_by_module(),
        user_extra_permission_ids={p.id for p in user.extra_permissions},
    )


@bp.route("/users/<int:user_id>/resend-verification", methods=["POST"])
@login_required
@permission_required("manage_system")
def resend_user_verification(user_id):
    user = User.query.get_or_404(user_id)
    try:
        resend_verification_email(user)
        log_action("resend_verification", "users", user.username)
        flash_msg("sa_verification_sent", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    return redirect(url_for("super_admin.users"))


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@permission_required("manage_system")
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash_msg("sa_cannot_deactivate_self", "danger")
        return redirect(url_for("super_admin.users"))
    if not user.is_active and not user.email_verified:
        flash_msg("sa_activate_requires_email", "danger")
        return redirect(url_for("super_admin.users"))
    user.is_active = not user.is_active
    log_action("toggle_user", "users", f"{user.username} active={user.is_active}")
    db.session.commit()
    flash_msg("users_status_updated", "success")
    return redirect(url_for("super_admin.users"))


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@permission_required("manage_system")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash_msg("sa_cannot_delete_self", "danger")
        return redirect(url_for("super_admin.users"))
    username = user.username
    db.session.delete(user)
    log_action("delete_user", "users", f"Deleted {username}")
    db.session.commit()
    flash_msg("sa_user_deleted", "success")
    return redirect(url_for("super_admin.users"))


@bp.route("/roles", methods=["GET", "POST"])
@login_required
@permission_required("manage_roles")
def roles():
    if request.method == "POST":
        role_id = request.form.get("role_id", type=int)
        permission_id = request.form.get("permission_id", type=int)
        action = request.form.get("action")
        role = Role.query.get_or_404(role_id)
        perm = Permission.query.get_or_404(permission_id)
        if action == "grant" and perm not in role.permissions:
            role.permissions.append(perm)
            log_action("grant_permission", "roles", f"{perm.name} -> {role.name}")
        elif action == "revoke" and perm in role.permissions:
            role.permissions.remove(perm)
            log_action("revoke_permission", "roles", f"{perm.name} x {role.name}")
        db.session.commit()
        clear_permission_cache()
        flash_msg("sa_permissions_updated", "success")
        return redirect(url_for("super_admin.roles"))

    roles_list = Role.query.order_by(Role.name).all()
    permissions = Permission.query.order_by(Permission.module, Permission.name).all()
    return render_template(
        "super_admin/roles.html",
        roles=roles_list,
        permissions=permissions,
        permissions_grouped=permissions_by_module(),
        is_system_role=is_system_role,
        system_role_names=SYSTEM_ROLE_NAMES,
    )


@bp.route("/roles/create", methods=["POST"])
@login_required
@permission_required("manage_roles")
def create_role():
    name = (request.form.get("name") or "").strip().lower()
    name_ar = (request.form.get("name_ar") or "").strip()
    description = (request.form.get("description") or "").strip()

    if not re.match(r"^[a-z][a-z0-9_]{1,48}$", name):
        flash_msg("sa_role_id_invalid", "danger")
        return redirect(url_for("super_admin.roles"))
    if name in SYSTEM_ROLE_NAMES:
        flash_msg("sa_role_id_reserved", "danger")
        return redirect(url_for("super_admin.roles"))
    if not name_ar:
        flash_msg("sa_role_name_required", "danger")
        return redirect(url_for("super_admin.roles"))
    if Role.query.filter_by(name=name).first():
        flash_msg("sa_role_id_taken", "danger")
        return redirect(url_for("super_admin.roles"))

    role = Role(name=name, name_ar=name_ar, description=description or None)
    db.session.add(role)
    log_action("create_role", "roles", f"Created role {name}")
    db.session.commit()
    flash_msg("sa_role_created", "success", name=name_ar)
    return redirect(url_for("super_admin.roles"))


@bp.route("/roles/<int:role_id>/delete", methods=["POST"])
@login_required
@permission_required("manage_roles")
def delete_role(role_id):
    role = Role.query.get_or_404(role_id)
    if is_system_role(role):
        flash_msg("sa_role_system_delete", "danger")
        return redirect(url_for("super_admin.roles"))
    if User.query.filter_by(role_id=role.id).count():
        flash_msg("sa_role_has_users", "danger")
        return redirect(url_for("super_admin.roles"))
    label, slug = role.name_ar, role.name
    db.session.delete(role)
    log_action("delete_role", "roles", f"Deleted role {slug}")
    db.session.commit()
    flash_msg("sa_role_deleted", "success", name=label)
    return redirect(url_for("super_admin.roles"))


@bp.route("/roles/<int:role_id>/update", methods=["POST"])
@login_required
@permission_required("manage_roles")
def update_role(role_id):
    role = Role.query.get_or_404(role_id)
    name_ar = (request.form.get("name_ar") or "").strip()
    description = (request.form.get("description") or "").strip()
    if not name_ar:
        flash_msg("sa_role_name_empty", "danger")
        return redirect(url_for("super_admin.roles"))

    role.name_ar = name_ar
    role.description = description or None
    if role.name == "ministry_admin":
        sync_central_admin_role_label(name_ar, None)
    log_action("update_role", "roles", f"{role.name} -> {name_ar}")
    db.session.commit()
    flash_msg("sa_role_updated", "success", name=name_ar)
    return redirect(url_for("super_admin.roles"))


@bp.route("/schools")
@login_required
@permission_required("manage_system")
def schools():
    schools_list = School.query.order_by(School.name_ar).all()
    return render_template(
        "super_admin/schools.html",
        schools=schools_list,
        can_delete_school=can_delete_school,
    )


@bp.route("/schools/<int:school_id>/toggle", methods=["POST"])
@login_required
@permission_required("manage_system")
def toggle_school(school_id):
    school = School.query.get_or_404(school_id)
    school.is_active = not school.is_active
    log_action("toggle_school", "schools", f"{school.code} active={school.is_active}")
    db.session.commit()
    flash_msg("sa_school_status_updated", "success")
    return redirect(url_for("super_admin.schools"))


@bp.route("/schools/provision-all", methods=["POST"])
@login_required
@permission_required("manage_system")
def provision_all():
    count = 0
    for school in School.query.filter_by(is_active=True).all():
        ensure_school_defaults(school.id)
        provision_school_kpis(school.id)
        count += 1
    log_action("provision_all_schools", "system", f"Provisioned {count} schools")
    db.session.commit()
    flash_msg("sa_schools_provisioned", "success", count=count)
    return redirect(url_for("super_admin.index"))


@bp.route("/system/defaults", methods=["POST"])
@login_required
@permission_required("manage_system")
def reset_global_defaults():
    ensure_school_defaults(None)
    log_action("reset_global_defaults", "system", "Global defaults refreshed")
    db.session.commit()
    flash_msg("sa_settings_updated", "success")
    return redirect(url_for("super_admin.index"))


@bp.route("/permissions/sync", methods=["POST"])
@login_required
@permission_required("manage_roles")
def sync_permissions_route():
    ensure_system_roles()
    clear_permission_cache()
    log_action("sync_permissions", "roles", "Registry synced to database")
    db.session.commit()
    flash_msg("sa_permissions_synced", "success")
    return redirect(url_for("super_admin.roles"))


@bp.route("/audit")
@login_required
@permission_required("view_audit_logs")
def audit():
    since = date.today() - timedelta(days=30)
    logs = AuditLog.query.filter(AuditLog.created_at >= since).order_by(
        AuditLog.created_at.desc()
    ).limit(200).all()
    return render_template(
        "super_admin/audit.html",
        logs=logs,
        since=since,
        audit_action_label=audit_action_label,
    )
