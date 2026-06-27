"""Shared platform identity number on all person records."""

from app.extensions import db


class PlatformIdentityMixin:
    platform_uid = db.Column(db.String(20), unique=True, nullable=True, index=True)

    @property
    def display_name(self):
        from flask import has_request_context
        from flask_login import current_user
        from app.services.identity_service import person_display_label

        if has_request_context():
            return person_display_label(self, current_user)
        return self.platform_uid or self._fallback_name()

    def _fallback_name(self):
        return getattr(self, "full_name_ar", None) or getattr(self, "full_name", None) or "—"
