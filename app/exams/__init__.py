from flask import Blueprint

bp = Blueprint("exams", __name__)

from app.exams import routes  # noqa: E402, F401
