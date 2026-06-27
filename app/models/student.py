from datetime import datetime, timezone

from app.models.identity_mixin import PlatformIdentityMixin
from app.extensions import db

parent_student = db.Table(
    "parent_student",
    db.Column("parent_id", db.Integer, db.ForeignKey("parents.id"), primary_key=True),
    db.Column("student_id", db.Integer, db.ForeignKey("students.id"), primary_key=True),
)


class Student(PlatformIdentityMixin, db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    grade_id = db.Column(db.Integer, db.ForeignKey("grades.id"), nullable=False)
    responsible_teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"))
    student_id = db.Column(db.String(20), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    full_name_ar = db.Column(db.String(150))
    gender = db.Column(db.String(10))
    date_of_birth = db.Column(db.Date)
    enrollment_date = db.Column(db.Date)
    region = db.Column(db.String(100), nullable=False)
    district = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text, nullable=False)
    phone = db.Column(db.String(20))
    gpa = db.Column(db.Float, default=0.0)
    weekly_class_limit = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref=db.backref("student_profile", uselist=False))
    school = db.relationship("School", backref="students")
    grade = db.relationship("Grade", backref="students")
    responsible_teacher = db.relationship("Teacher", foreign_keys=[responsible_teacher_id])
    parents = db.relationship("Parent", secondary=parent_student, backref="children")
    attendance_records = db.relationship("Attendance", backref="student", lazy="dynamic")
    kpi_scores = db.relationship("StudentKPI", backref="student", lazy="dynamic")
    evaluations = db.relationship("Evaluation", backref="student", lazy="dynamic")

    def __repr__(self):
        return f"<Student {self.full_name_ar or self.full_name}>"


class Parent(PlatformIdentityMixin, db.Model):
    __tablename__ = "parents"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True)
    full_name = db.Column(db.String(150), nullable=False)
    full_name_ar = db.Column(db.String(150))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    relationship_type = db.Column(db.String(30))  # father, mother, guardian
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref=db.backref("parent_profile", uselist=False))

    def __repr__(self):
        return f"<Parent {self.full_name_ar or self.full_name}>"
