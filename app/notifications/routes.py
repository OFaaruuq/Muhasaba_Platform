from flask import jsonify, render_template
from flask_login import login_required, current_user

from app.notifications import bp
from app.extensions import db
from app.models import Notification


@bp.route("/")
@login_required
def index():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).all()
    return render_template("notifications/index.html", notifications=notifications)


@bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        return jsonify({"error": "غير مصرح"}), 403
    notification.is_read = True
    db.session.commit()
    return jsonify({"success": True})
