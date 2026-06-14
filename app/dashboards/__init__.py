from flask import Blueprint

bp = Blueprint("dashboards", __name__)

from app.dashboards import routes  # noqa: E402, F401
