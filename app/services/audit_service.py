from flask import request
from flask_login import current_user

from app.extensions import db
from app.models import AuditLog


def log_action(action, module=None, details=None, user_id=None):
    entry = AuditLog(
        user_id=user_id or (current_user.id if current_user.is_authenticated else None),
        action=action,
        module=module,
        details=details,
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(entry)
