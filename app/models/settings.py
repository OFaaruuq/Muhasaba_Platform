from datetime import datetime, timezone

from app.extensions import db


class PlatformSetting(db.Model):
    """Key-value settings: global (school_id=NULL) or per-school override."""

    __tablename__ = "platform_settings"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), index=True)
    key = db.Column(db.String(100), nullable=False, index=True)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(20), default="string")  # string, int, float, json, bool
    label_ar = db.Column(db.String(200))
    category = db.Column(db.String(50))  # general, grading, kpi, attendance
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    school = db.relationship("School", backref="settings")

    __table_args__ = (
        db.UniqueConstraint("school_id", "key", name="uq_school_setting_key"),
    )


class EvaluationCriterion(db.Model):
    """Admin-configurable Muhasaba evaluation criteria."""

    __tablename__ = "evaluation_criteria"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), index=True)
    category = db.Column(db.String(50), nullable=False)  # academic, behavior, personal
    code = db.Column(db.String(50), nullable=False)
    name_ar = db.Column(db.String(100), nullable=False)
    name_en = db.Column(db.String(100))
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    kpi_source = db.Column(db.String(50))  # links to KPI code for scoring
    evaluation_type = db.Column(db.String(20), default="daily")  # daily, monthly

    school = db.relationship("School", backref="evaluation_criteria")

    __table_args__ = (
        db.UniqueConstraint("school_id", "code", name="uq_school_criterion_code"),
    )


class RatingLevel(db.Model):
    """Admin-configurable rating scale."""

    __tablename__ = "rating_levels"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), index=True)
    code = db.Column(db.String(30), nullable=False)
    name_ar = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Float, nullable=False)
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    scale_type = db.Column(db.String(20), default="qualitative")  # qualitative, numeric_5

    school = db.relationship("School", backref="rating_levels")

    __table_args__ = (
        db.UniqueConstraint("school_id", "code", name="uq_school_rating_code"),
    )


class AttendanceStatusConfig(db.Model):
    """Admin-configurable attendance statuses."""

    __tablename__ = "attendance_status_config"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), index=True)
    code = db.Column(db.String(20), nullable=False)
    name_ar = db.Column(db.String(50), nullable=False)
    counts_as_present = db.Column(db.Boolean, default=True)
    notify_parent = db.Column(db.Boolean, default=False)
    badge_class = db.Column(db.String(30), default="secondary")
    time_from = db.Column(db.String(5))
    time_to = db.Column(db.String(5))
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    school = db.relationship("School", backref="attendance_statuses")

    __table_args__ = (
        db.UniqueConstraint("school_id", "code", name="uq_school_attendance_status"),
    )


class ConfigOption(db.Model):
    """Generic admin-configurable lookup options (exam types, behavior types, etc.)."""

    __tablename__ = "config_options"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), index=True)
    option_type = db.Column(db.String(50), nullable=False, index=True)
    code = db.Column(db.String(50), nullable=False)
    name_ar = db.Column(db.String(100), nullable=False)
    name_en = db.Column(db.String(100))
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    metadata_json = db.Column(db.Text)

    school = db.relationship("School", backref="config_options")

    __table_args__ = (
        db.UniqueConstraint("school_id", "option_type", "code", name="uq_school_config_option"),
    )
