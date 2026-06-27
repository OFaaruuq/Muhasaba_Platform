from flask import abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.services.message_service import flash_msg
from app.services.tenant_service import (
    get_user_tenant,
    submit_license_request,
    tenant_has_active_license,
    get_active_license,
)
from app.tenants import bp


@bp.route("/license-request", methods=["GET", "POST"])
@login_required
def license_request():
    if not current_user.has_permission("manage_system"):
        abort(404)
    if request.method == "POST":
        org_name = request.form.get("organization_name", "").strip()
        org_name_ar = request.form.get("organization_name_ar", "").strip()
        contact_name = request.form.get("contact_name", "").strip()
        email = request.form.get("email", "").strip()
        if not all([org_name, org_name_ar, contact_name, email]):
            flash_msg("license_request_missing_fields", "danger")
            return render_template("tenants/license_request.html")

        submit_license_request(
            organization_name=org_name,
            organization_name_ar=org_name_ar,
            contact_name=contact_name,
            email=email,
            phone=request.form.get("phone"),
            message=request.form.get("message"),
        )
        flash_msg("license_request_submitted", "success")
        return redirect(url_for("auth.login"))

    return render_template("tenants/license_request.html")


@bp.route("/license-status")
@login_required
def license_status():
    tenant = get_user_tenant(current_user)
    license_ = get_active_license(tenant) if tenant else None
    return render_template(
        "tenants/license_status.html",
        tenant=tenant,
        license=license_,
        has_license=tenant_has_active_license(tenant),
    )
