from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id"), primary_key=True),
)


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    name_ar = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    permissions = db.relationship("Permission", secondary=role_permissions, backref="roles")

    def __repr__(self):
        return f"<Role {self.name}>"


class Permission(db.Model):
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    name_ar = db.Column(db.String(150), nullable=False)
    module = db.Column(db.String(50))

    def __repr__(self):
        return f"<Permission {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    full_name_ar = db.Column(db.String(150))
    phone = db.Column(db.String(20))
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"))
    is_active = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    email_verification_token = db.Column(db.String(64), nullable=True, index=True)
    email_verification_sent_at = db.Column(db.DateTime, nullable=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    role = db.relationship("Role", backref="users")
    school = db.relationship("School", backref="users")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_permission(self, permission_name):
        from app.utils.permissions import user_has_permission
        return user_has_permission(self, permission_name)

    def has_any_permission(self, *permission_names):
        from app.utils.permissions import user_has_any_permission
        return user_has_any_permission(self, *permission_names)

    @property
    def is_super_admin(self):
        return self.has_permission("manage_system")

    @property
    def is_ministry_admin(self):
        if self.role and self.role.name == "ministry_admin":
            return True
        return self.has_permission("view_all_schools") and not self.has_permission("manage_system")

    @property
    def is_platform_admin(self):
        return self.has_permission("view_all_schools")

    @property
    def is_school_manager(self):
        if self.role and self.role.name == "school_manager":
            return True
        return self.has_permission("manage_school")

    @property
    def is_teacher(self):
        if not self.teacher_profile:
            return False
        from app.services.permission_registry import has_teacher_capabilities
        if self.role and self.role.name == "teacher":
            return True
        return has_teacher_capabilities(self)

    @property
    def is_student(self):
        if not self.student_profile:
            return False
        from app.services.permission_registry import has_student_capabilities
        if self.role and self.role.name == "student":
            return True
        return has_student_capabilities(self)

    @property
    def is_parent(self):
        from app.services.permission_registry import has_parent_capabilities
        if self.role and self.role.name == "parent":
            return True
        return has_parent_capabilities(self) and self.parent_profile is not None

    @property
    def role_name_ar(self):
        if not self.role:
            return ""
        if self.role.name == "ministry_admin":
            from app.services.config_service import get_setting
            return get_setting(
                "org_central_admin_role_ar",
                self.school_id,
                self.role.name_ar,
            )
        return self.role.name_ar

    def __repr__(self):
        return f"<User {self.username}>"
