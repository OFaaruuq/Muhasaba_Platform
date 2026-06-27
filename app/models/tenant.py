from datetime import datetime, timezone

from app.extensions import db


class Tenant(db.Model):
    __tablename__ = "tenants"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=False)
    platform_name_ar = db.Column(db.String(200))
    platform_tagline_ar = db.Column(db.String(300))
    contact_email = db.Column(db.String(120))
    contact_phone = db.Column(db.String(30))
    is_platform_owner = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    schools = db.relationship("School", backref="tenant", lazy="dynamic")
    licenses = db.relationship(
        "TenantLicense",
        backref="tenant",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Tenant {self.slug}>"


class TenantLicense(db.Model):
    __tablename__ = "tenant_licenses"

    STATUS_ACTIVE = "active"
    STATUS_SUSPENDED = "suspended"
    STATUS_EXPIRED = "expired"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    plan_name = db.Column(db.String(50), default="standard")
    status = db.Column(db.String(20), default=STATUS_ACTIVE, index=True)
    max_schools = db.Column(db.Integer, default=5)
    max_users = db.Column(db.Integer, default=100)
    starts_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    approved_by = db.relationship("User", foreign_keys=[approved_by_id])

    def __repr__(self):
        return f"<TenantLicense tenant={self.tenant_id} {self.status}>"


class LicenseRequest(db.Model):
    __tablename__ = "license_requests"

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    id = db.Column(db.Integer, primary_key=True)
    organization_name = db.Column(db.String(200), nullable=False)
    organization_name_ar = db.Column(db.String(200), nullable=False)
    contact_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30))
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default=STATUS_PENDING, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"))
    admin_notes = db.Column(db.Text)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    tenant = db.relationship("Tenant", backref="license_requests")
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    def __repr__(self):
        return f"<LicenseRequest {self.id} {self.status}>"
