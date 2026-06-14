from flask import Blueprint

bp = Blueprint("schools", __name__)

from app.schools import routes  # noqa: E402, F401
