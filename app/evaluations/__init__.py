from flask import Blueprint

bp = Blueprint("evaluations", __name__)

from app.evaluations import routes  # noqa: E402, F401
