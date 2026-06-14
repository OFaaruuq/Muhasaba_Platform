import json
from datetime import datetime, timezone

from app.extensions import db


class Evaluation(db.Model):
    """Daily Muhasaba evaluation by teacher."""

    __tablename__ = "evaluations"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    daily_score = db.Column(db.Float)
    academic_score = db.Column(db.Float)
    behavior_score = db.Column(db.Float)
    personal_score = db.Column(db.Float)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    teacher = db.relationship("Teacher", backref="evaluations")
    school = db.relationship("School", backref="evaluations")
    details = db.relationship("EvaluationDetail", backref="evaluation", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("student_id", "date", name="uq_student_evaluation_date"),
    )


class EvaluationDetail(db.Model):
    __tablename__ = "evaluation_details"

    id = db.Column(db.Integer, primary_key=True)
    evaluation_id = db.Column(db.Integer, db.ForeignKey("evaluations.id"), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # academic, behavior, personal
    criterion = db.Column(db.String(100), nullable=False)
    criterion_ar = db.Column(db.String(100))
    rating = db.Column(db.String(30), nullable=False)
    score = db.Column(db.Float)


class ReadingAssessment(db.Model):
    __tablename__ = "reading_assessments"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    read_lesson = db.Column(db.Boolean, default=False)
    fluency = db.Column(db.String(30))
    pronunciation = db.Column(db.String(30))
    understanding = db.Column(db.String(30))
    overall_rating = db.Column(db.String(30))
    aspect_scores = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    student = db.relationship("Student", backref="reading_assessments")
    teacher = db.relationship("Teacher", backref="reading_assessments")
    school = db.relationship("School", backref="reading_assessments")


class BehaviorRecord(db.Model):
    __tablename__ = "behavior_records"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    behavior_type = db.Column(db.String(50))  # positive, negative, neutral
    category = db.Column(db.String(50))  # respect, discipline, honesty, cooperation
    description = db.Column(db.Text)
    score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    student = db.relationship("Student", backref="behavior_records")
    teacher = db.relationship("Teacher", backref="behavior_records")
    school = db.relationship("School", backref="behavior_records")


class StudentSelfAssessment(db.Model):
    __tablename__ = "student_self_assessments"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    attended_classes = db.Column(db.Boolean)
    completed_homework = db.Column(db.Boolean)
    helped_classmates = db.Column(db.Boolean)
    respected_teachers = db.Column(db.Boolean)
    answers = db.Column(db.Text)
    reflection = db.Column(db.Text)
    improvement_plan = db.Column(db.Text)
    self_score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    student = db.relationship("Student", backref="self_assessments")

    __table_args__ = (
        db.UniqueConstraint("student_id", "date", name="uq_student_self_assessment_date"),
    )

    def get_answers_dict(self):
        if self.answers:
            return json.loads(self.answers)
        legacy = {
            "attended_classes": self.attended_classes,
            "completed_homework": self.completed_homework,
            "helped_classmates": self.helped_classmates,
            "respected_teachers": self.respected_teachers,
        }
        return {k: v for k, v in legacy.items() if v is not None}

    def set_answers_dict(self, data):
        self.answers = json.dumps(data)
        self.attended_classes = data.get("attended_classes")
        self.completed_homework = data.get("completed_homework")
        self.helped_classmates = data.get("helped_classmates")
        self.respected_teachers = data.get("respected_teachers")


class MonthlyEvaluation(db.Model):
    """Monthly tarbiya evaluation (التقييم_الشهري) — one per student per month."""

    __tablename__ = "monthly_evaluations"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    period_year = db.Column(db.Integer, nullable=False)
    period_month = db.Column(db.Integer, nullable=False)
    overall_score = db.Column(db.Float)
    individual_program_score = db.Column(db.Float)
    pairs_score = db.Column(db.Float)
    meetings_score = db.Column(db.Float)
    discipline_score = db.Column(db.Float)
    behavior_followup_score = db.Column(db.Float)
    strengths = db.Column(db.Text)
    weaknesses = db.Column(db.Text)
    recommendations = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    student = db.relationship("Student", backref="monthly_evaluations")
    teacher = db.relationship("Teacher", backref="monthly_evaluations")
    school = db.relationship("School", backref="monthly_evaluations")
    details = db.relationship("MonthlyEvaluationDetail", backref="evaluation", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "period_year", "period_month",
            name="uq_student_monthly_eval",
        ),
    )


class MonthlyEvaluationDetail(db.Model):
    __tablename__ = "monthly_evaluation_details"

    id = db.Column(db.Integer, primary_key=True)
    evaluation_id = db.Column(db.Integer, db.ForeignKey("monthly_evaluations.id"), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    criterion = db.Column(db.String(100), nullable=False)
    criterion_ar = db.Column(db.String(100))
    rating = db.Column(db.String(10), nullable=False)
    score = db.Column(db.Float)
