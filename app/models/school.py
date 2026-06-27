from datetime import datetime, timezone

from app.extensions import db


class School(db.Model):
    __tablename__ = "schools"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True, index=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    district = db.Column(db.String(100))
    region = db.Column(db.String(100))
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    principal_name = db.Column(db.String(150))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    academic_years = db.relationship("AcademicYear", backref="school", lazy="dynamic")
    grades = db.relationship("Grade", backref="school", lazy="dynamic")
    classes = db.relationship("Class", backref="school", lazy="dynamic")
    subjects = db.relationship("Subject", backref="school", lazy="dynamic")

    def __repr__(self):
        return f"<School {self.name_ar}>"


class AcademicYear(db.Model):
    __tablename__ = "academic_years"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_current = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<AcademicYear {self.name}>"


class Grade(db.Model):
    __tablename__ = "grades"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    name_ar = db.Column(db.String(50), nullable=False)
    level = db.Column(db.Integer, nullable=False)

    classes = db.relationship("Class", backref="grade", lazy="dynamic")

    def __repr__(self):
        return f"<Grade {self.name_ar}>"


class Class(db.Model):
    __tablename__ = "classes"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    grade_id = db.Column(db.Integer, db.ForeignKey("grades.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    section = db.Column(db.String(10))
    capacity = db.Column(db.Integer, default=30)
    academic_year_id = db.Column(db.Integer, db.ForeignKey("academic_years.id"))

    academic_year = db.relationship("AcademicYear", backref="classes")
    students = db.relationship("Student", backref="class_", lazy="dynamic")

    def __repr__(self):
        return f"<Class {self.name}>"


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20))

    def __repr__(self):
        return f"<Subject {self.name_ar}>"


class ClassSubject(db.Model):
    __tablename__ = "class_subjects"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"))

    class_ = db.relationship("Class", backref="class_subjects")
    subject = db.relationship("Subject", backref="class_subjects")
    teacher = db.relationship("Teacher", backref="class_subjects")
