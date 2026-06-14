from flask import Blueprint

bp = Blueprint("academic", __name__)

from app.academic import routes  # noqa: E402, F401
