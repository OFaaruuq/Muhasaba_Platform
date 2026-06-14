from sqlalchemy import inspect, text

from app.extensions import db

KPI_CODE_MAP = {
    "Attendance": "attendance",
    "Homework": "homework",
    "Reading": "reading",
    "Exams": "exams",
    "Behavior": "behavior",
    "Participation": "participation",
    "Islamic Ethics": "islamic_ethics",
}


def upgrade_student_schema():
    """Add new student columns to existing databases (SQLite / PostgreSQL)."""
    inspector = inspect(db.engine)
    if "students" not in inspector.get_table_names():
        return

    columns = {c["name"] for c in inspector.get_columns("students")}
    alters = []

    if "grade_id" not in columns:
        alters.append("ALTER TABLE students ADD COLUMN grade_id INTEGER")
    if "region" not in columns:
        alters.append("ALTER TABLE students ADD COLUMN region VARCHAR(100)")
    if "district" not in columns:
        alters.append("ALTER TABLE students ADD COLUMN district VARCHAR(100)")
    if "address" not in columns:
        alters.append("ALTER TABLE students ADD COLUMN address TEXT")
    if "phone" not in columns:
        alters.append("ALTER TABLE students ADD COLUMN phone VARCHAR(20)")

    with db.engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))

        if alters or "grade_id" in columns:
            conn.execute(text("""
                UPDATE students
                SET grade_id = (
                    SELECT grade_id FROM classes WHERE classes.id = students.class_id
                )
                WHERE grade_id IS NULL AND class_id IS NOT NULL
            """))
            from app.services.config_service import DEFAULT_SETTINGS
            unspecified = DEFAULT_SETTINGS["ui_unspecified"][0]
            conn.execute(
                text("UPDATE students SET region = :val WHERE region IS NULL OR region = ''"),
                {"val": unspecified},
            )
            conn.execute(
                text("UPDATE students SET district = :val WHERE district IS NULL OR district = ''"),
                {"val": unspecified},
            )
            conn.execute(
                text("UPDATE students SET address = :val WHERE address IS NULL OR address = ''"),
                {"val": unspecified},
            )


def upgrade_kpi_schema():
    """Add code column to KPIs and backfill."""
    inspector = inspect(db.engine)
    if "kpis" not in inspector.get_table_names():
        return

    columns = {c["name"] for c in inspector.get_columns("kpis")}
    with db.engine.begin() as conn:
        if "code" not in columns:
            conn.execute(text("ALTER TABLE kpis ADD COLUMN code VARCHAR(50)"))
            for name, code in KPI_CODE_MAP.items():
                conn.execute(
                    text("UPDATE kpis SET code = :code WHERE name = :name"),
                    {"code": code, "name": name},
                )
            conn.execute(text("""
                UPDATE kpis SET code = LOWER(REPLACE(name, ' ', '_'))
                WHERE code IS NULL OR code = ''
            """))


def upgrade_config_schema():
    """Add dynamic config columns to existing databases."""
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    with db.engine.begin() as conn:
        if "attendance_status_config" in tables:
            columns = {c["name"] for c in inspector.get_columns("attendance_status_config")}
            if "badge_class" not in columns:
                conn.execute(text(
                    "ALTER TABLE attendance_status_config ADD COLUMN badge_class VARCHAR(30)"
                ))
                from app.services.config_service import DEFAULT_ATTENDANCE_STATUSES
                for row in DEFAULT_ATTENDANCE_STATUSES:
                    conn.execute(
                        text(
                            "UPDATE attendance_status_config SET badge_class = :badge WHERE code = :code"
                        ),
                        {"badge": row[4], "code": row[0]},
                    )

        if "student_self_assessments" in tables:
            columns = {c["name"] for c in inspector.get_columns("student_self_assessments")}
            if "answers" not in columns:
                conn.execute(text(
                    "ALTER TABLE student_self_assessments ADD COLUMN answers TEXT"
                ))

        if "students" in tables:
            columns = {c["name"] for c in inspector.get_columns("students")}
            if "responsible_teacher_id" not in columns:
                conn.execute(text(
                    "ALTER TABLE students ADD COLUMN responsible_teacher_id INTEGER"
                ))

        if "evaluation_criteria" in tables:
            columns = {c["name"] for c in inspector.get_columns("evaluation_criteria")}
            if "evaluation_type" not in columns:
                conn.execute(text(
                    "ALTER TABLE evaluation_criteria ADD COLUMN evaluation_type VARCHAR(20)"
                ))
                conn.execute(text(
                    "UPDATE evaluation_criteria SET evaluation_type = 'daily' WHERE evaluation_type IS NULL"
                ))

        if "rating_levels" in tables:
            columns = {c["name"] for c in inspector.get_columns("rating_levels")}
            if "scale_type" not in columns:
                conn.execute(text(
                    "ALTER TABLE rating_levels ADD COLUMN scale_type VARCHAR(20)"
                ))
                conn.execute(text(
                    "UPDATE rating_levels SET scale_type = 'qualitative' WHERE scale_type IS NULL"
                ))


def repair_student_user_links():
    """Link student-role users that have no Student profile (legacy DBs)."""
    from app.models import Role, User, Student

    inspector = inspect(db.engine)
    if "students" not in inspector.get_table_names():
        return

    student_role = Role.query.filter_by(name="student").first()
    if not student_role:
        return

    for user in User.query.filter_by(role_id=student_role.id, is_active=True).all():
        if Student.query.filter_by(user_id=user.id).first():
            continue
        candidate = Student.query.filter_by(
            school_id=user.school_id, is_active=True,
        ).filter(
            (Student.user_id.is_(None)) | (Student.user_id == 0)
        ).first() if user.school_id else None
        if not candidate and user.username == "student":
            candidate = Student.query.filter(
                Student.user_id.is_(None), Student.is_active == True  # noqa: E712
            ).first()
        if candidate:
            candidate.user_id = user.id
    db.session.commit()


def upgrade_permissions():
    """Sync permission registry and ensure system roles have default grants."""
    from app.services.permission_registry import sync_permissions, apply_default_role_permissions

    inspector = inspect(db.engine)
    if "permissions" not in inspector.get_table_names():
        return
    sync_permissions()
    apply_default_role_permissions(force=False)
    db.session.commit()


def ensure_super_admin_role():
    """Add super_admin role and default user to existing databases."""
    from app.models import Role, User
    from app.services.permission_registry import sync_permissions, apply_default_role_permissions

    inspector = inspect(db.engine)
    if "roles" not in inspector.get_table_names():
        return

    super_role = Role.query.filter_by(name="super_admin").first()
    if not super_role:
        super_role = Role(
            name="super_admin",
            name_ar="المشرف الأعلى",
            description="التحكم الكامل بالمنصة",
        )
        db.session.add(super_role)
        db.session.flush()

    sync_permissions()
    apply_default_role_permissions(force=False)

    if not User.query.filter_by(username="superadmin").first():
        user = User(
            username="superadmin",
            email="superadmin@muhasaba.so",
            full_name="Super Admin",
            full_name_ar="المشرف الأعلى للمنصة",
            role_id=super_role.id,
        )
        from app.services.config_service import get_setting, ensure_school_defaults
        ensure_school_defaults(None)
        user.set_password(get_setting("demo_login_password", None, "admin123"))
        db.session.add(user)

    db.session.commit()


def upgrade_attendance_schema():
    """Add check-in time and per-status time windows."""
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    with db.engine.begin() as conn:
        if "attendance" in tables:
            columns = {c["name"] for c in inspector.get_columns("attendance")}
            if "check_in_time" not in columns:
                conn.execute(text("ALTER TABLE attendance ADD COLUMN check_in_time TIME"))

        if "attendance_status_config" in tables:
            columns = {c["name"] for c in inspector.get_columns("attendance_status_config")}
            if "time_from" not in columns:
                conn.execute(text(
                    "ALTER TABLE attendance_status_config ADD COLUMN time_from VARCHAR(5)"
                ))
            if "time_to" not in columns:
                conn.execute(text(
                    "ALTER TABLE attendance_status_config ADD COLUMN time_to VARCHAR(5)"
                ))
            from app.services.config_service import DEFAULT_ATTENDANCE_STATUSES
            for row in DEFAULT_ATTENDANCE_STATUSES:
                code = row[0]
                time_from = row[5] if len(row) > 5 else None
                time_to = row[6] if len(row) > 6 else None
                conn.execute(
                    text("""
                        UPDATE attendance_status_config
                        SET time_from = COALESCE(time_from, :tf),
                            time_to = COALESCE(time_to, :tt)
                        WHERE code = :code
                    """),
                    {"tf": time_from, "tt": time_to, "code": code},
                )


def upgrade_followup_survey_schema():
    """Add follow-up survey columns/tables to existing databases."""
    inspector = inspect(db.engine)
    if "teacher_monthly_surveys" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("teacher_monthly_surveys")}
    if "family_role_rating" not in columns:
        with db.engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE teacher_monthly_surveys ADD COLUMN family_role_rating VARCHAR(20)"
            ))

    if "student_educational_program_followup_surveys" not in inspector.get_table_names():
        from app.models.followup_survey import StudentEducationalProgramFollowupSurvey
        StudentEducationalProgramFollowupSurvey.__table__.create(db.engine)


def upgrade_reading_schema():
    """Add aspect_scores JSON column for dynamic reading aspects."""
    inspector = inspect(db.engine)
    if "reading_assessments" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("reading_assessments")}
    if "aspect_scores" not in columns:
        with db.engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE reading_assessments ADD COLUMN aspect_scores TEXT"
            ))


def upgrade_user_email_optional():
    """Allow NULL emails on users (optional contact for students/teachers)."""
    inspector = inspect(db.engine)
    if "users" not in inspector.get_table_names():
        return

    email_col = next(
        (c for c in inspector.get_columns("users") if c["name"] == "email"),
        None,
    )
    if email_col and email_col.get("nullable"):
        return

    dialect = db.engine.dialect.name
    with db.engine.begin() as conn:
        if dialect == "sqlite":
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.execute(text("""
                CREATE TABLE users__email_optional (
                    id INTEGER NOT NULL PRIMARY KEY,
                    username VARCHAR(80) NOT NULL,
                    email VARCHAR(120),
                    password_hash VARCHAR(256) NOT NULL,
                    full_name VARCHAR(150) NOT NULL,
                    full_name_ar VARCHAR(150),
                    phone VARCHAR(20),
                    role_id INTEGER NOT NULL,
                    school_id INTEGER,
                    is_active BOOLEAN,
                    last_login DATETIME,
                    created_at DATETIME,
                    FOREIGN KEY(role_id) REFERENCES roles (id),
                    FOREIGN KEY(school_id) REFERENCES schools (id)
                )
            """))
            conn.execute(text("""
                INSERT INTO users__email_optional (
                    id, username, email, password_hash, full_name, full_name_ar,
                    phone, role_id, school_id, is_active, last_login, created_at
                )
                SELECT
                    id, username, email, password_hash, full_name, full_name_ar,
                    phone, role_id, school_id, is_active, last_login, created_at
                FROM users
            """))
            conn.execute(text("DROP TABLE users"))
            conn.execute(text("ALTER TABLE users__email_optional RENAME TO users"))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"
            ))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"
            ))
            conn.execute(text("PRAGMA foreign_keys=ON"))
        else:
            conn.execute(text("ALTER TABLE users ALTER COLUMN email DROP NOT NULL"))


def upgrade_kpi_data_sources():
    """Seed configurable KPI data sources for existing databases."""
    inspector = inspect(db.engine)
    if "platform_settings" not in inspector.get_table_names():
        return

    from app.services.config_service import ensure_school_defaults
    from app.models import School

    ensure_school_defaults(None)
    for school in School.query.filter_by(is_active=True).all():
        ensure_school_defaults(school.id)


def apply_schema_upgrades():
    """Idempotent schema patches for existing databases (safe on every startup)."""
    if not inspect(db.engine).get_table_names():
        return

    # Structural patches first — data seeding below uses full ORM models.
    upgrade_user_email_optional()
    upgrade_student_schema()
    upgrade_kpi_schema()
    upgrade_config_schema()
    upgrade_attendance_schema()
    upgrade_reading_schema()
    upgrade_followup_survey_schema()
    upgrade_permissions()
    upgrade_kpi_data_sources()
