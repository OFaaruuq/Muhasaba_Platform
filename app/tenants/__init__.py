from flask import Blueprint

bp = Blueprint("tenants", __name__, url_prefix="/tenants")

from app.tenants import routes  # noqa: E402, F401
