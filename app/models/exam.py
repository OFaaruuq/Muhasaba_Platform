from datetime import datetime, timezone

from app.extensions import db


class Exam(db.Model):
    __tablename__ = "exams"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    title_ar = db.Column(db.String(200))
    exam_type = db.Column(db.String(20), nullable=False)
    total_marks = db.Column(db.Float, default=100.0)
    passing_marks = db.Column(db.Float, default=50.0)
    exam_date = db.Column(db.Date)
    duration_minutes = db.Column(db.Integer, default=60)
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    school = db.relationship("School", backref="exams")
    class_ = db.relationship("Class", backref="exams")
    subject = db.relationship("Subject", backref="exams")
    teacher = db.relationship("Teacher", backref="exams")
    questions = db.relationship("ExamQuestion", backref="exam", lazy="dynamic")
    results = db.relationship("ExamResult", backref="exam", lazy="dynamic")


class ExamQuestion(db.Model):
    __tablename__ = "exam_questions"

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    text_ar = db.Column(db.Text)
    question_type = db.Column(db.String(20), nullable=False)
    marks = db.Column(db.Float, default=1.0)
    correct_answer = db.Column(db.Text)
    options = db.Column(db.JSON)  # for MCQ: ["A", "B", "C", "D"]
    order = db.Column(db.Integer, default=0)


class ExamResult(db.Model):
    __tablename__ = "exam_results"

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    score = db.Column(db.Float, default=0.0)
    percentage = db.Column(db.Float, default=0.0)
    grade_letter = db.Column(db.String(5))
    answers = db.Column(db.JSON)
    is_graded = db.Column(db.Boolean, default=False)
    submitted_at = db.Column(db.DateTime)
    graded_at = db.Column(db.DateTime)

    student = db.relationship("Student", backref="exam_results")

    __table_args__ = (
        db.UniqueConstraint("exam_id", "student_id", name="uq_exam_student_result"),
    )
