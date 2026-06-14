from flask import render_template
from flask_login import login_required

from app.ai import bp
from app.utils import permission_required


@bp.route("/")
@login_required
@permission_required("view_ai_assistant")
def index():
    return render_template("ai/index.html")
