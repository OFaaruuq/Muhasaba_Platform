"""School management helpers — safe deletion and usage checks."""

from app.extensions import db
from app.models import (
    School, Grade, Class, Subject, AcademicYear, ClassSubject,
    PlatformSetting, EvaluationCriterion, RatingLevel,
    AttendanceStatusConfig, ConfigOption, KPI,
    FamilyFollowupSurvey, TeacherMonthlySurvey, EducationalProgramFollowupSurvey,
    StudentEducationalProgramFollowupSurvey,
    Student, Teacher, User, Exam,
)


def school_usage_counts(school_id):
    return {
        "students": Student.query.filter_by(school_id=school_id).count(),
        "teachers": Teacher.query.filter_by(school_id=school_id).count(),
        "users": User.query.filter_by(school_id=school_id).count(),
    }


def school_delete_blockers(school_id):
    """Return human-readable reasons why a school cannot be permanently deleted."""
    counts = school_usage_counts(school_id)
    blockers = []
    if counts["students"]:
        blockers.append(f'{counts["students"]} طالب/طلاب')
    if counts["teachers"]:
        blockers.append(f'{counts["teachers"]} معلم/معلمين')
    if counts["users"]:
        blockers.append(f'{counts["users"]} مستخدم/مستخدمين')
    return blockers


def can_delete_school(school_id):
    blockers = school_delete_blockers(school_id)
    return len(blockers) == 0, blockers


def subject_delete_blockers(subject_id):
    """Reasons a subject cannot be deleted."""
    blockers = []
    class_links = ClassSubject.query.filter_by(subject_id=subject_id).count()
    if class_links:
        blockers.append(f"مرتبطة بـ {class_links} فصل/فصول")
    exam_count = Exam.query.filter_by(subject_id=subject_id).count()
    if exam_count:
        blockers.append(f"مرتبطة بـ {exam_count} اختبار/اختبارات")
    return blockers


def can_delete_subject(subject_id):
    blockers = subject_delete_blockers(subject_id)
    return len(blockers) == 0, blockers


def delete_school_permanently(school):
    """Delete a school and its configuration when it has no people attached."""
    ok, blockers = can_delete_school(school.id)
    if not ok:
        raise ValueError(
            "لا يمكن حذف المدرسة لوجود: " + "، ".join(blockers)
            + ". استخدم «تعطيل» بدلاً من الحذف."
        )

    sid = school.id

    FamilyFollowupSurvey.query.filter_by(school_id=sid).delete(synchronize_session=False)
    TeacherMonthlySurvey.query.filter_by(school_id=sid).delete(synchronize_session=False)
    EducationalProgramFollowupSurvey.query.filter_by(school_id=sid).delete(synchronize_session=False)
    StudentEducationalProgramFollowupSurvey.query.filter_by(school_id=sid).delete(synchronize_session=False)

    class_ids = [c.id for c in Class.query.filter_by(school_id=sid).all()]
    if class_ids:
        ClassSubject.query.filter(ClassSubject.class_id.in_(class_ids)).delete(
            synchronize_session=False
        )

    Class.query.filter_by(school_id=sid).delete(synchronize_session=False)
    Grade.query.filter_by(school_id=sid).delete(synchronize_session=False)
    Subject.query.filter_by(school_id=sid).delete(synchronize_session=False)
    AcademicYear.query.filter_by(school_id=sid).delete(synchronize_session=False)

    PlatformSetting.query.filter_by(school_id=sid).delete(synchronize_session=False)
    EvaluationCriterion.query.filter_by(school_id=sid).delete(synchronize_session=False)
    RatingLevel.query.filter_by(school_id=sid).delete(synchronize_session=False)
    AttendanceStatusConfig.query.filter_by(school_id=sid).delete(synchronize_session=False)
    ConfigOption.query.filter_by(school_id=sid).delete(synchronize_session=False)
    KPI.query.filter_by(school_id=sid).delete(synchronize_session=False)

    db.session.delete(school)
    db.session.commit()
