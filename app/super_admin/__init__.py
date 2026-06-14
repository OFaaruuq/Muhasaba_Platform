from flask import Blueprint

bp = Blueprint("super_admin", __name__)

from app.super_admin import routes  # noqa: E402, F401
