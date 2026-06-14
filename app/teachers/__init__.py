from flask import Blueprint

bp = Blueprint("teachers", __name__)

from app.teachers import routes  # noqa: E402, F401
