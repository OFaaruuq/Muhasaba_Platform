from datetime import datetime, timezone

from app.extensions import db

FREQUENCY_RATINGS = ("always", "usually", "sometimes", "rarely")
WEEKLY_MEETINGS_CHOICES = ("one", "two", "other")


class FamilyFollowupSurvey(db.Model):
    """استبيان متابعة الأسرة — يُجمع شهرياً عبر مسؤولي المجموعات."""

    __tablename__ = "family_followup_surveys"
    __table_args__ = (
        db.UniqueConstraint(
            "school_id", "student_id", "period_year", "period_month",
            name="uq_family_survey_student_period",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("parents.id"))
    entered_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    period_year = db.Column(db.Integer, nullable=False)
    period_month = db.Column(db.Integer, nullable=False)

    family_name = db.Column(db.String(150), nullable=False)
    stage_primary = db.Column(db.Boolean, default=False)
    stage_middle = db.Column(db.Boolean, default=False)
    stage_secondary = db.Column(db.Boolean, default=False)

    has_regular_family_meeting = db.Column(db.Boolean)
    weekly_meetings_count = db.Column(db.String(20))
    weekly_meetings_one_reason = db.Column(db.Text)
    weekly_meetings_other = db.Column(db.String(100))
    family_meeting_notes = db.Column(db.Text)

    received_curriculum_book = db.Column(db.Boolean)
    read_curriculum_book = db.Column(db.Boolean)
    studied_curriculum_at_home = db.Column(db.Boolean)
    curriculum_notes = db.Column(db.Text)

    hadith_at_home = db.Column(db.Boolean)
    fiqh_at_home = db.Column(db.Boolean)
    curricula_obstacles = db.Column(db.Text)

    listens_riyadh_saliheen = db.Column(db.Boolean)
    riyadh_progress = db.Column(db.Text)

    received_approved_films = db.Column(db.Boolean)
    watches_approved_only = db.Column(db.Boolean)
    outdoor_entertainment = db.Column(db.Boolean)

    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    school = db.relationship("School", backref="family_followup_surveys")
    student = db.relationship("Student", backref="family_followup_surveys")
    parent = db.relationship("Parent", backref="family_followup_surveys")
    entered_by = db.relationship("User", backref="family_surveys_entered")


class TeacherMonthlySurvey(db.Model):
    """استبيان شهري للمعلم حول لقاءات التلاميذ."""

    __tablename__ = "teacher_monthly_surveys"
    __table_args__ = (
        db.UniqueConstraint(
            "teacher_id", "period_year", "period_month",
            name="uq_teacher_survey_period",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    period_year = db.Column(db.Integer, nullable=False)
    period_month = db.Column(db.Integer, nullable=False)

    attendance_punctuality = db.Column(db.String(20))
    lesson_preparation = db.Column(db.String(20))
    main_obstacles = db.Column(db.Text)
    student_punctuality = db.Column(db.String(20))
    student_preparation_percentage = db.Column(db.String(100))
    student_comprehension = db.Column(db.String(20))
    student_notes = db.Column(db.Text)
    family_role_rating = db.Column(db.String(20))
    family_role_message = db.Column(db.Text)
    session_suggestions = db.Column(db.Text)

    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    school = db.relationship("School", backref="teacher_monthly_surveys")
    teacher = db.relationship("Teacher", backref="monthly_surveys")


class ProgramFollowupFieldsMixin:
    """Shared fields for teacher and student educational program follow-up surveys."""

    # المجال الفردي
    has_daily_individual_program = db.Column(db.Boolean)
    daily_includes_quran_dhikr = db.Column(db.Boolean)
    program_regular_scheduled = db.Column(db.Boolean)
    persistence_and_makeup = db.Column(db.Boolean)

    # الثنائيات
    binary_meeting_biweekly = db.Column(db.Boolean)
    binary_meeting_full_agenda = db.Column(db.Boolean)
    binary_reform_quarterly = db.Column(db.Boolean)

    # مسؤول المجموعة — أثناء اللقاء
    go_during_punctual_attendance = db.Column(db.Boolean)
    go_during_good_preparation = db.Column(db.Boolean)
    go_during_programs_on_time = db.Column(db.Boolean)
    go_during_summarize_points = db.Column(db.Boolean)
    go_during_evaluate_meeting = db.Column(db.Boolean)
    go_during_extended_monthly_meeting = db.Column(db.Boolean)

    # مسؤول المجموعة — خارج اللقاء
    go_outside_educate_members = db.Column(db.Boolean)
    go_outside_close_living = db.Column(db.Boolean)
    go_outside_reminder_meetings = db.Column(db.Boolean)
    go_outside_special_care_difficulties = db.Column(db.Boolean)

    # دور مسؤولي الواحات ومسؤولي المجموعة
    oasis_weekly_meeting = db.Column(db.Boolean)
    oasis_assess_program_benefit = db.Column(db.Boolean)

    # البرنامج الدراسي التأسيسي
    foundational_monthly_faith_meeting_week4 = db.Column(db.Boolean)

    # جلسات الأعمام
    uncle_platforms_created = db.Column(db.Boolean)

    # التعامل مع المتأخرين
    latecomers_commitment_enforced = db.Column(db.Boolean)
    latecomers_session_starts_730 = db.Column(db.Boolean)
    latecomers_entry_bar_after_745 = db.Column(db.Boolean)
    latecomers_three_absences_rule = db.Column(db.Boolean)
    latecomers_notes = db.Column(db.Text)

    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class EducationalProgramFollowupSurvey(ProgramFollowupFieldsMixin, db.Model):
    """متابعة تقرير البرنامج التربوي — شهرياً لكل مسؤول/معلم."""

    __tablename__ = "educational_program_followup_surveys"
    __table_args__ = (
        db.UniqueConstraint(
            "teacher_id", "period_year", "period_month",
            name="uq_program_followup_teacher_period",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    entered_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    period_year = db.Column(db.Integer, nullable=False)
    period_month = db.Column(db.Integer, nullable=False)

    school = db.relationship("School", backref="educational_program_followup_surveys")
    teacher = db.relationship("Teacher", backref="program_followup_surveys")
    entered_by = db.relationship("User", backref="program_followup_surveys_entered")


class StudentEducationalProgramFollowupSurvey(ProgramFollowupFieldsMixin, db.Model):
    """متابعة تقرير البرنامج التربوي — شهرياً لكل طالب."""

    __tablename__ = "student_educational_program_followup_surveys"
    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "period_year", "period_month",
            name="uq_student_program_followup_period",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    entered_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    period_year = db.Column(db.Integer, nullable=False)
    period_month = db.Column(db.Integer, nullable=False)

    school = db.relationship("School", backref="student_educational_program_followup_surveys")
    student = db.relationship("Student", backref="program_followup_surveys")
    entered_by = db.relationship("User", backref="student_program_followup_surveys_entered")
