from datetime import datetime, time, timezone

from app.extensions import db


class Attendance(db.Model):
    __tablename__ = "attendance"

    STATUS_PRESENT = "present"
    STATUS_ABSENT = "absent"
    STATUS_EXCUSED = "excused"
    STATUS_LATE = "late"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    check_in_time = db.Column(db.Time)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PRESENT)
    notes = db.Column(db.Text)
    recorded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    school = db.relationship("School", backref="attendance_records")
    class_ = db.relationship("Class", backref="attendance_records")
    recorder = db.relationship("User", backref="recorded_attendance")

    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "class_id", "date",
            name="uq_student_class_attendance_date",
        ),
    )
