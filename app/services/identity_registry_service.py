"""Super-admin platform identity registry: stats, backfill, Excel export."""

import io
from openpyxl import Workbook
from sqlalchemy import or_

from app.extensions import db
from app.models import User, Student, Teacher, Parent, School
from app.models.platform_id_counter import PlatformIdCounter
from app.services.identity_service import backfill_platform_identities, person_full_name


PERSON_TYPE_LABELS = {
    "student": "طالب",
    "teacher": "معلم",
    "parent": "ولي أمر",
    "user": "مستخدم",
}


def _missing_uid_query(model):
    return model.query.filter(or_(model.platform_uid.is_(None), model.platform_uid == ""))


def _display_name(record):
    if isinstance(record, User):
        return person_full_name(record)
    return record.full_name_ar or record.full_name or "—"


def _active_label(record):
    if hasattr(record, "is_active"):
        return "نشط" if record.is_active else "معطّل"
    return "—"


def identity_summary():
    counter = db.session.get(PlatformIdCounter, 1)
    return {
        "students_total": Student.query.count(),
        "students_missing": _missing_uid_query(Student).count(),
        "teachers_total": Teacher.query.count(),
        "teachers_missing": _missing_uid_query(Teacher).count(),
        "parents_total": Parent.query.count(),
        "parents_missing": _missing_uid_query(Parent).count(),
        "users_total": User.query.count(),
        "users_missing": _missing_uid_query(User).count(),
        "missing_total": (
            _missing_uid_query(Student).count()
            + _missing_uid_query(Teacher).count()
            + _missing_uid_query(Parent).count()
            + _missing_uid_query(User).count()
        ),
        "counter_next": counter.next_value if counter else 1,
    }


def run_identity_backfill():
    before = identity_summary()
    backfill_platform_identities()
    db.session.commit()
    after = identity_summary()
    return {
        "before": before,
        "after": after,
        "assigned": before["missing_total"] - after["missing_total"],
    }


def _parent_school_name(parent):
    for child in parent.children or []:
        if child.school:
            return child.school.name_ar
    return "—"


def build_registry_rows(*, school_id=None, person_type=None, missing_only=False):
    """Flat registry rows for preview and Excel export."""
    rows = []

    def add_row(*, platform_uid, name, ptype, school_name, username, legacy_id, status, sort_key):
        if missing_only and platform_uid:
            return
        rows.append({
            "platform_uid": platform_uid or "—",
            "name": name,
            "person_type": PERSON_TYPE_LABELS.get(ptype, ptype),
            "person_type_key": ptype,
            "school_name": school_name or "—",
            "username": username or "—",
            "legacy_id": legacy_id or "—",
            "status": status,
            "_sort": sort_key,
        })

    if person_type in (None, "student"):
        query = Student.query
        if school_id:
            query = query.filter_by(school_id=school_id)
        for s in query.order_by(Student.full_name_ar, Student.full_name).all():
            add_row(
                platform_uid=s.platform_uid,
                name=_display_name(s),
                ptype="student",
                school_name=s.school.name_ar if s.school else "—",
                username=s.user.username if s.user else "—",
                legacy_id=s.student_id,
                status=_active_label(s),
                sort_key=(s.platform_uid or "zzz", s.full_name_ar or s.full_name),
            )

    if person_type in (None, "teacher"):
        query = Teacher.query
        if school_id:
            query = query.filter_by(school_id=school_id)
        for t in query.order_by(Teacher.full_name_ar, Teacher.full_name).all():
            add_row(
                platform_uid=t.platform_uid,
                name=_display_name(t),
                ptype="teacher",
                school_name=t.school.name_ar if t.school else "—",
                username=t.user.username if t.user else "—",
                legacy_id=t.employee_id,
                status=_active_label(t),
                sort_key=(t.platform_uid or "zzz", t.full_name_ar or t.full_name),
            )

    if person_type in (None, "parent") and not school_id:
        for p in Parent.query.order_by(Parent.full_name_ar, Parent.full_name).all():
            add_row(
                platform_uid=p.platform_uid,
                name=_display_name(p),
                ptype="parent",
                school_name=_parent_school_name(p),
                username=p.user.username if p.user else "—",
                legacy_id="—",
                status="—",
                sort_key=(p.platform_uid or "zzz", p.full_name_ar or p.full_name),
            )
    elif person_type in (None, "parent") and school_id:
        for p in Parent.query.order_by(Parent.full_name_ar).all():
            if not any(c.school_id == school_id for c in (p.children or [])):
                continue
            school = School.query.get(school_id)
            add_row(
                platform_uid=p.platform_uid,
                name=_display_name(p),
                ptype="parent",
                school_name=school.name_ar if school else "—",
                username=p.user.username if p.user else "—",
                legacy_id="—",
                status="—",
                sort_key=(p.platform_uid or "zzz", p.full_name_ar or p.full_name),
            )

    if person_type in (None, "user"):
        query = User.query
        if school_id:
            query = query.filter_by(school_id=school_id)
        for u in query.order_by(User.full_name_ar, User.username).all():
            if u.student_profile or u.teacher_profile or u.parent_profile:
                continue
            add_row(
                platform_uid=u.platform_uid,
                name=_display_name(u),
                ptype="user",
                school_name=u.school.name_ar if u.school else "—",
                username=u.username,
                legacy_id="—",
                status=_active_label(u),
                sort_key=(u.platform_uid or "zzz", u.full_name_ar or u.username),
            )

    rows.sort(key=lambda r: r["_sort"])
    for r in rows:
        r.pop("_sort", None)
    return rows


def export_identity_registry_excel(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "أرقام الهوية"
    headers = [
        "رقم الهوية",
        "الاسم",
        "النوع",
        "المدرسة",
        "اسم المستخدم",
        "رقم المدرسة / الوظيفي",
        "الحالة",
    ]
    ws.append(headers)
    for row in rows:
        ws.append([
            row["platform_uid"],
            row["name"],
            row["person_type"],
            row["school_name"],
            row["username"],
            row["legacy_id"],
            row["status"],
        ])
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def identity_page_context(*, school_id=None, person_type=None, missing_only=False, preview_limit=150):
    schools = School.query.order_by(School.name_ar).all()
    summary = identity_summary()
    rows = build_registry_rows(
        school_id=school_id,
        person_type=person_type or None,
        missing_only=missing_only,
    )
    return {
        "schools": schools,
        "selected_school": school_id,
        "selected_type": person_type or "",
        "missing_only": missing_only,
        "summary": summary,
        "registry_rows": rows[:preview_limit],
        "registry_total": len(rows),
        "preview_limit": preview_limit,
    }
