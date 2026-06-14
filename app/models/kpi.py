from datetime import datetime, timezone

from app.extensions import db


class KPI(db.Model):
    __tablename__ = "kpis"

    SOURCE_ATTENDANCE = "attendance"
    SOURCE_HOMEWORK = "homework"
    SOURCE_READING = "reading"
    SOURCE_EXAMS = "exams"
    SOURCE_BEHAVIOR = "behavior"
    SOURCE_PARTICIPATION = "participation"
    SOURCE_ISLAMIC_ETHICS = "islamic_ethics"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"))
    code = db.Column(db.String(50), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    weight = db.Column(db.Float, nullable=False, default=10.0)
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)

    school = db.relationship("School", backref="kpis")
    student_scores = db.relationship("StudentKPI", backref="kpi", lazy="dynamic")

    def __repr__(self):
        return f"<KPI {self.name_ar}>"


class StudentKPI(db.Model):
    __tablename__ = "student_kpis"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    kpi_id = db.Column(db.Integer, db.ForeignKey("kpis.id"), nullable=False)
    score = db.Column(db.Float, nullable=False, default=0.0)
    period = db.Column(db.String(20))  # daily, weekly, monthly, term
    period_start = db.Column(db.Date)
    period_end = db.Column(db.Date)
    notes = db.Column(db.Text)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "kpi_id", "period", "period_start",
            name="uq_student_kpi_period",
        ),
    )
