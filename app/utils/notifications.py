from app.extensions import db
from app.models import Notification


def send_notification(user_id, title, message, notification_type="general", link=None):
    if not user_id:
        return
    db.session.add(Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link,
    ))


def notify_parent_of_student(student, title, message, notification_type="general", link=None):
    for parent in student.parents:
        if parent.user_id:
            send_notification(parent.user_id, title, message, notification_type, link)
