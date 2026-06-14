from datetime import datetime, timezone

from app.extensions import db


class Teacher(db.Model):
    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    employee_id = db.Column(db.String(20), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    full_name_ar = db.Column(db.String(150))
    specialization = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    hire_date = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref=db.backref("teacher_profile", uselist=False))
    school = db.relationship("School", backref="teachers")
    class_assignments = db.relationship("TeacherClass", backref="teacher", lazy="dynamic")

    def __repr__(self):
        return f"<Teacher {self.full_name_ar or self.full_name}>"


class TeacherClass(db.Model):
    __tablename__ = "teacher_classes"

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"))
    academic_year_id = db.Column(db.Integer, db.ForeignKey("academic_years.id"))

    class_ = db.relationship("Class", backref="teacher_assignments")
    subject = db.relationship("Subject", backref="teacher_assignments")
    academic_year = db.relationship("AcademicYear", backref="teacher_assignments")
