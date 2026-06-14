"""School subjects (المادة) — dynamic list and create."""

from app.extensions import db
from app.models import Subject


def list_subjects(school_id):
    return Subject.query.filter_by(school_id=school_id).order_by(Subject.name_ar).all()


def create_subject(school_id, *, name_ar, name=None, code=None):
    if not str(name_ar or "").strip():
        raise ValueError("اسم المادة بالعربية مطلوب.")

    name_ar = name_ar.strip()
    code = (code or "").strip().upper() or None

    existing = Subject.query.filter_by(school_id=school_id, name_ar=name_ar).first()
    if existing:
        raise ValueError(f"المادة «{name_ar}» موجودة مسبقاً.")

    if code and Subject.query.filter_by(school_id=school_id, code=code).first():
        raise ValueError("رمز المادة مستخدم مسبقاً.")

    subject = Subject(
        school_id=school_id,
        name=name or name_ar,
        name_ar=name_ar,
        code=code,
    )
    db.session.add(subject)
    db.session.commit()
    return subject


def resolve_subject_from_form(school_id, form):
    """Return specialization text from subject_id or free-text fallback."""
    subject_id = form.get("subject_id")
    if subject_id:
        try:
            subject_id = int(subject_id)
        except (TypeError, ValueError):
            subject_id = None
    if subject_id:
        subject = Subject.query.filter_by(id=subject_id, school_id=school_id).first()
        if subject:
            return subject.name_ar
    text = (form.get("specialization") or "").strip()
    return text or None


def teacher_selected_subject_id(teacher):
    if not teacher.specialization:
        return None
    subject = Subject.query.filter_by(
        school_id=teacher.school_id,
        name_ar=teacher.specialization,
    ).first()
    return subject.id if subject else None


def teacher_subject_labels(teacher):
    """Subjects for display: assignments first, then specialization."""
    labels = []
    for assignment in teacher.class_assignments:
        if assignment.subject and assignment.subject.name_ar:
            name = assignment.subject.name_ar
            if name not in labels:
                labels.append(name)
    if not labels and teacher.specialization:
        labels.append(teacher.specialization)
    return labels
