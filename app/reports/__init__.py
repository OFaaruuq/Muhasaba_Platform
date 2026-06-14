from flask import Blueprint

bp = Blueprint("reports", __name__)

from app.reports import routes  # noqa: E402, F401
