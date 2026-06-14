from flask import Blueprint

bp = Blueprint("kpi", __name__)

from app.kpi import routes  # noqa: E402, F401
