"""Platform-wide permanent identity numbers and privacy-aware display."""

from sqlalchemy import or_

from app.extensions import db

UID_PREFIX = "MP"
ADMIN_NAME_PERMISSIONS = (
    "manage_system",
    "manage_users",
    "manage_students",
    "manage_teachers",
    "manage_school",
    "view_all_schools",
)


def can_view_person_names(viewer):
    if not viewer or not getattr(viewer, "is_authenticated", False):
        return False
    return viewer.has_any_permission(*ADMIN_NAME_PERMISSIONS)


def _uid_taken(uid):
    from app.models import User, Student, Teacher, Parent

    return any(
        m.query.filter_by(platform_uid=uid).first()
        for m in (User, Student, Teacher, Parent)
    )


def allocate_platform_uid():
    from app.models.platform_id_counter import PlatformIdCounter

    for _ in range(20):
        counter = db.session.get(PlatformIdCounter, 1)
        if not counter:
            counter = PlatformIdCounter(id=1, next_value=1)
            db.session.add(counter)
            db.session.flush()
        uid = f"{UID_PREFIX}-{counter.next_value:08d}"
        counter.next_value += 1
        db.session.flush()
        if not _uid_taken(uid):
            return uid
    raise RuntimeError("تعذّر توليد رقم هوية فريد.")


def assign_platform_uid(record):
    if getattr(record, "platform_uid", None):
        return record.platform_uid
    uid = allocate_platform_uid()
    record.platform_uid = uid
    db.session.flush()
    return uid


def sync_identity_pair(primary, secondary):
    """Keep one UID when a User account links to a profile."""
    if not primary or not secondary:
        return assign_platform_uid(primary or secondary)
    p_uid = getattr(primary, "platform_uid", None)
    s_uid = getattr(secondary, "platform_uid", None)
    if p_uid and s_uid and p_uid != s_uid:
        secondary.platform_uid = p_uid
        return p_uid
    if p_uid:
        if not s_uid:
            secondary.platform_uid = p_uid
        return p_uid
    if s_uid:
        primary.platform_uid = s_uid
        return s_uid
    uid = allocate_platform_uid()
    primary.platform_uid = uid
    secondary.platform_uid = uid
    return uid


def ensure_identity_for_user(user):
    if not user:
        return None
    if user.platform_uid:
        if user.student_profile and not user.student_profile.platform_uid:
            user.student_profile.platform_uid = user.platform_uid
        if user.teacher_profile and not user.teacher_profile.platform_uid:
            user.teacher_profile.platform_uid = user.platform_uid
        if user.parent_profile and not user.parent_profile.platform_uid:
            user.parent_profile.platform_uid = user.platform_uid
        return user.platform_uid
    if user.student_profile:
        return sync_identity_pair(user, user.student_profile)
    if user.teacher_profile:
        return sync_identity_pair(user, user.teacher_profile)
    if user.parent_profile:
        return sync_identity_pair(user, user.parent_profile)
    return assign_platform_uid(user)


def ensure_identity_for_student(student):
    if not student:
        return None
    if student.user:
        return sync_identity_pair(student.user, student)
    if student.platform_uid:
        return student.platform_uid
    return assign_platform_uid(student)


def ensure_identity_for_teacher(teacher):
    if not teacher:
        return None
    if teacher.user:
        return sync_identity_pair(teacher.user, teacher)
    if teacher.platform_uid:
        return teacher.platform_uid
    return assign_platform_uid(teacher)


def ensure_identity_for_parent(parent):
    if not parent:
        return None
    if parent.user:
        return sync_identity_pair(parent.user, parent)
    if parent.platform_uid:
        return parent.platform_uid
    return assign_platform_uid(parent)


def resolve_platform_uid(subject):
    if not subject:
        return None
    uid = getattr(subject, "platform_uid", None)
    if uid:
        return uid
    if hasattr(subject, "student_profile") and subject.student_profile:
        return subject.student_profile.platform_uid
    if hasattr(subject, "teacher_profile") and subject.teacher_profile:
        return subject.teacher_profile.platform_uid
    if hasattr(subject, "parent_profile") and subject.parent_profile:
        return subject.parent_profile.platform_uid
    if hasattr(subject, "user") and subject.user:
        return subject.user.platform_uid
    return None


def person_full_name(subject):
    if not subject:
        return "—"
    return (
        getattr(subject, "full_name_ar", None)
        or getattr(subject, "full_name", None)
        or getattr(subject, "username", None)
        or "—"
    )


def person_display_label(subject, viewer=None):
    from flask_login import current_user

    viewer = viewer if viewer is not None else current_user
    uid = resolve_platform_uid(subject)
    if can_view_person_names(viewer):
        name = person_full_name(subject)
        if name and name != "—":
            return name
    return uid or "—"


def backfill_platform_identities():
    from app.models import User, Student, Teacher, Parent
    from app.models.platform_id_counter import PlatformIdCounter

    if not db.session.get(PlatformIdCounter, 1):
        db.session.add(PlatformIdCounter(id=1, next_value=1))
        db.session.flush()

    max_num = 0
    for model in (User, Student, Teacher, Parent):
        for row in model.query.filter(model.platform_uid.isnot(None)).all():
            parts = (row.platform_uid or "").split("-", 1)
            if len(parts) == 2 and parts[1].isdigit():
                max_num = max(max_num, int(parts[1]))

    counter = db.session.get(PlatformIdCounter, 1)
    counter.next_value = max(counter.next_value, max_num + 1)

    for student in Student.query.filter(or_(Student.platform_uid.is_(None), Student.platform_uid == "")).all():
        ensure_identity_for_student(student)
    for teacher in Teacher.query.filter(or_(Teacher.platform_uid.is_(None), Teacher.platform_uid == "")).all():
        ensure_identity_for_teacher(teacher)
    for parent in Parent.query.filter(or_(Parent.platform_uid.is_(None), Parent.platform_uid == "")).all():
        ensure_identity_for_parent(parent)
    for user in User.query.filter(or_(User.platform_uid.is_(None), User.platform_uid == "")).all():
        ensure_identity_for_user(user)

    db.session.flush()
