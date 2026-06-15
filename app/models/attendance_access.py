from datetime import datetime, timezone

from app.extensions import db


class AttendanceEntryApproval(db.Model):
    """Management approval allowing a denied student to attend a class session."""

    __tablename__ = "attendance_entry_approvals"

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DENIED = "denied"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    session_date = db.Column(db.Date, nullable=False, index=True)
    week_start = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_APPROVED)
    reason = db.Column(db.Text)
    requested_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    student = db.relationship("Student", backref="attendance_approvals")
    class_ = db.relationship("Class")
    requester = db.relationship("User", foreign_keys=[requested_by])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])

    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "class_id", "session_date",
            name="uq_attendance_entry_approval",
        ),
    )
