from flask import Blueprint

bp = Blueprint("followup_surveys", __name__)

from app.followup_surveys import routes  # noqa: E402, F401
