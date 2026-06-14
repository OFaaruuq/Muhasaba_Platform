from datetime import datetime, timezone

from app.extensions import db


class Questionnaire(db.Model):
    __tablename__ = "questionnaires"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"))
    title = db.Column(db.String(200), nullable=False)
    title_ar = db.Column(db.String(200))
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # academic, personal, behavioral
    is_active = db.Column(db.Boolean, default=True)
    due_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    school = db.relationship("School", backref="questionnaires")
    teacher = db.relationship("Teacher", backref="questionnaires")
    class_ = db.relationship("Class", backref="questionnaires")
    questions = db.relationship("Question", backref="questionnaire", lazy="dynamic")


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    questionnaire_id = db.Column(db.Integer, db.ForeignKey("questionnaires.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    text_ar = db.Column(db.Text)
    question_type = db.Column(db.String(30), nullable=False)
    order = db.Column(db.Integer, default=0)
    is_required = db.Column(db.Boolean, default=True)

    choices = db.relationship("Choice", backref="question", lazy="dynamic")
    answers = db.relationship("StudentAnswer", backref="question", lazy="dynamic")


class Choice(db.Model):
    __tablename__ = "choices"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    text = db.Column(db.String(255), nullable=False)
    text_ar = db.Column(db.String(255))
    order = db.Column(db.Integer, default=0)


class StudentAnswer(db.Model):
    __tablename__ = "student_answers"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    choice_id = db.Column(db.Integer, db.ForeignKey("choices.id"))
    text_answer = db.Column(db.Text)
    rating_value = db.Column(db.Integer)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    student = db.relationship("Student", backref="questionnaire_answers")
    choice = db.relationship("Choice", backref="answers")
