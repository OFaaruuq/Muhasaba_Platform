"""Multi-tenant licensing and platform owner helpers."""

import re
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models import School, User
from app.models.tenant import Tenant, TenantLicense, LicenseRequest


def _slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:80] or "tenant"


def _unique_slug(base):
    slug = _slugify(base)
    candidate = slug
    n = 2
    while Tenant.query.filter_by(slug=candidate).first():
        candidate = f"{slug}-{n}"
        n += 1
    return candidate


def get_platform_owner_tenant():
    slug = current_app.config.get("PLATFORM_OWNER_SLUG", "netrich")
    return Tenant.query.filter_by(is_platform_owner=True).first() or Tenant.query.filter_by(
        slug=slug
    ).first()


def ensure_platform_owner_tenant():
    owner = get_platform_owner_tenant()
    if owner:
        if not owner.is_platform_owner:
            owner.is_platform_owner = True
        return owner

    slug = current_app.config.get("PLATFORM_OWNER_SLUG", "netrich")
    name = current_app.config.get("PLATFORM_OWNER_NAME", "Netrich")
    name_ar = current_app.config.get("PLATFORM_OWNER_NAME_AR", "نيتريش")
    owner = Tenant(
        slug=slug,
        name=name,
        name_ar=name_ar,
        platform_name_ar=current_app.config.get("PLATFORM_NAME"),
        platform_tagline_ar=current_app.config.get("PLATFORM_TAGLINE"),
        is_platform_owner=True,
        is_active=True,
    )
    db.session.add(owner)
    db.session.flush()

    lic = TenantLicense(
        tenant_id=owner.id,
        plan_name="owner",
        status=TenantLicense.STATUS_ACTIVE,
        max_schools=9999,
        max_users=99999,
        starts_at=datetime.now(timezone.utc),
        expires_at=None,
    )
    db.session.add(lic)
    return owner


def assign_schools_to_platform_owner():
    owner = ensure_platform_owner_tenant()
    School.query.filter(School.tenant_id.is_(None)).update(
        {"tenant_id": owner.id},
        synchronize_session=False,
    )


def get_user_tenant(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if not user.school_id:
        return None
    school = School.query.get(user.school_id)
    if not school or not school.tenant_id:
        return None
    return Tenant.query.get(school.tenant_id)


def get_active_license(tenant):
    if not tenant:
        return None
    if tenant.is_platform_owner:
        return tenant.licenses.order_by(TenantLicense.created_at.desc()).first()
    now = datetime.now(timezone.utc)
    for lic in tenant.licenses.order_by(TenantLicense.created_at.desc()):
        if lic.status != TenantLicense.STATUS_ACTIVE:
            continue
        if lic.expires_at:
            expires = lic.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if now > expires:
                continue
        return lic
    return None


def tenant_has_active_license(tenant):
    if not tenant:
        return True
    if tenant.is_platform_owner:
        return True
    return get_active_license(tenant) is not None


def tenant_stats(tenant):
    school_ids = [s.id for s in School.query.filter_by(tenant_id=tenant.id).all()]
    users_count = User.query.filter(User.school_id.in_(school_ids)).count() if school_ids else 0
    lic = get_active_license(tenant)
    return {
        "schools": len(school_ids),
        "users": users_count,
        "license": lic,
        "has_license": lic is not None,
    }


def submit_license_request(*, organization_name, organization_name_ar, contact_name, email, phone=None, message=None):
    req = LicenseRequest(
        organization_name=organization_name.strip(),
        organization_name_ar=organization_name_ar.strip(),
        contact_name=contact_name.strip(),
        email=email.strip().lower(),
        phone=(phone or "").strip() or None,
        message=(message or "").strip() or None,
        status=LicenseRequest.STATUS_PENDING,
    )
    db.session.add(req)
    db.session.commit()
    return req


def approve_license_request(
    request_id,
    admin_user_id,
    *,
    plan_name="standard",
    max_schools=5,
    max_users=100,
    duration_days=365,
    admin_notes=None,
):
    req = LicenseRequest.query.get(request_id)
    if not req or req.status != LicenseRequest.STATUS_PENDING:
        raise ValueError("طلب الترخيص غير موجود أو تمت معالجته مسبقاً.")

    slug_base = req.organization_name or req.organization_name_ar
    tenant = Tenant(
        slug=_unique_slug(slug_base),
        name=req.organization_name,
        name_ar=req.organization_name_ar,
        contact_email=req.email,
        contact_phone=req.phone,
        is_active=True,
    )
    db.session.add(tenant)
    db.session.flush()

    now = datetime.now(timezone.utc)
    lic = TenantLicense(
        tenant_id=tenant.id,
        plan_name=plan_name,
        status=TenantLicense.STATUS_ACTIVE,
        max_schools=max_schools,
        max_users=max_users,
        starts_at=now,
        expires_at=now + timedelta(days=duration_days) if duration_days else None,
        notes=admin_notes,
        approved_by_id=admin_user_id,
        approved_at=now,
    )
    db.session.add(lic)

    req.status = LicenseRequest.STATUS_APPROVED
    req.tenant_id = tenant.id
    req.reviewed_by_id = admin_user_id
    req.reviewed_at = now
    req.admin_notes = admin_notes
    db.session.commit()
    return tenant


def reject_license_request(request_id, admin_user_id, admin_notes=None):
    req = LicenseRequest.query.get(request_id)
    if not req or req.status != LicenseRequest.STATUS_PENDING:
        raise ValueError("طلب الترخيص غير موجود أو تمت معالجته مسبقاً.")
    req.status = LicenseRequest.STATUS_REJECTED
    req.reviewed_by_id = admin_user_id
    req.reviewed_at = datetime.now(timezone.utc)
    req.admin_notes = admin_notes
    db.session.commit()
    return req
