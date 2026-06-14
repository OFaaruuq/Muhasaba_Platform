"""Idempotent bulk registration: super admins, teachers, and students."""

from datetime import date

from app.extensions import db
from app.models import (
    Role, User, School, Grade, Class, Subject, AcademicYear,
    Student, Teacher, TeacherClass,
)
from app.kpi.hooks import sync_kpis_for_student
from app.services.config_service import get_setting


SUPER_ADMINS = [
    ("superadmin1", "المشرف الأعلى ١", "superadmin1@muhasaba.so"),
    ("superadmin2", "المشرف الأعلى ٢", "superadmin2@muhasaba.so"),
    ("superadmin3", "المشرف الأعلى ٣", "superadmin3@muhasaba.so"),
    ("superadmin4", "المشرف الأعلى ٤", "superadmin4@muhasaba.so"),
]

TEACHERS = [
    ("teacher1", "أحمد علي محمود", "T-101", "الرياضيات"),
    ("teacher2", "فاطمة حسن عمر", "T-102", "اللغة العربية"),
    ("teacher3", "عمر عبدالرحمن", "T-103", "التربية الإسلامية"),
    ("teacher4", "خديجة محمد", "T-104", "العلوم"),
    ("teacher5", "يوسف إبراهيم", "T-105", "اللغة الإنجليزية"),
    ("teacher6", "مريم أحمد", "T-106", "الدراسات الاجتماعية"),
    ("teacher7", "حسن عبدي", "T-107", "التربية البدنية"),
]

STUDENTS = [
    ("student1", "محمد أحمد حسن", "male"),
    ("student2", "عائشة علي محمد", "female"),
    ("student3", "عبدالله يوسف", "male"),
    ("student4", "زينب حسن", "female"),
    ("student5", "إبراهيم عمر", "male"),
    ("student6", "حليمة فاطمة", "female"),
    ("student7", "عثمان عبدالله", "male"),
    ("student8", "نورا أحمد", "female"),
    ("student9", "سعيد محمود", "male"),
    ("student10", "ليلى حسين", "female"),
]


def _demo_password():
    return get_setting("demo_login_password", None, "admin123")


def _school_context():
    school = School.query.filter_by(is_active=True).order_by(School.id).first()
    if not school:
        return None
    year = AcademicYear.query.filter_by(school_id=school.id, is_current=True).first()
    grades = Grade.query.filter_by(school_id=school.id).order_by(Grade.level).all()
    classes = Class.query.filter_by(school_id=school.id).order_by(Class.name).all()
    subjects = Subject.query.filter_by(school_id=school.id).all()
    return {
        "school": school,
        "year": year,
        "grades": grades,
        "classes": classes,
        "subjects": subjects,
    }


def _create_user(username, email, full_name_ar, role, school_id=None):
    if User.query.filter_by(username=username).first():
        return None
    user = User(
        username=username,
        email=email,
        full_name=full_name_ar,
        full_name_ar=full_name_ar,
        role_id=role.id,
        school_id=school_id,
    )
    user.set_password(_demo_password())
    db.session.add(user)
    db.session.flush()
    return user


def _next_student_number(school):
    year = date.today().year
    prefix = school.code or "STD"
    count = Student.query.filter(Student.student_id.like(f"{prefix}-{year}-%")).count() + 1
    while Student.query.filter_by(student_id=f"{prefix}-{year}-{count:03d}").first():
        count += 1
    return f"{prefix}-{year}-{count:03d}"


def seed_bulk_accounts():
    """
    Register up to 4 super admins, 7 teachers, and 10 students (skips existing usernames).
    Returns counts of newly created records.
    """
    super_role = Role.query.filter_by(name="super_admin").first()
    teacher_role = Role.query.filter_by(name="teacher").first()
    student_role = Role.query.filter_by(name="student").first()
    if not all([super_role, teacher_role, student_role]):
        return {"super_admins": 0, "teachers": 0, "students": 0}

    ctx = _school_context()
    created = {"super_admins": 0, "teachers": 0, "students": 0}

    for username, name_ar, email in SUPER_ADMINS:
        if _create_user(username, email, name_ar, super_role):
            created["super_admins"] += 1

    if not ctx:
        db.session.commit()
        return created

    school = ctx["school"]
    year = ctx["year"]
    grades = ctx["grades"]
    classes = ctx["classes"]
    subjects = ctx["subjects"]
    default_grade = grades[0] if grades else None
    class_5 = classes[0] if classes else None
    class_6 = classes[1] if len(classes) > 1 else class_5
    default_subject = subjects[0] if subjects else None
    class_teacher_map = {}

    for i, (username, name_ar, emp_id, spec) in enumerate(TEACHERS):
        if Teacher.query.filter_by(employee_id=emp_id).first():
            continue
        if User.query.filter_by(username=username).first():
            continue
        user = _create_user(username, f"{username}@mps.edu.so", name_ar, teacher_role, school.id)
        if not user:
            continue
        teacher = Teacher(
            user_id=user.id,
            school_id=school.id,
            employee_id=emp_id,
            full_name=name_ar,
            full_name_ar=name_ar,
            specialization=spec,
            hire_date=date(2022, 9, 1),
        )
        db.session.add(teacher)
        db.session.flush()
        target_class = class_5 if i < 4 else (class_6 or class_5)
        if year and target_class and default_subject:
            db.session.add(TeacherClass(
                teacher_id=teacher.id,
                class_id=target_class.id,
                subject_id=default_subject.id,
                academic_year_id=year.id,
            ))
            class_teacher_map.setdefault(target_class.id, teacher.id)
        created["teachers"] += 1

    for i, (username, name_ar, gender) in enumerate(STUDENTS):
        if User.query.filter_by(username=username).first():
            continue
        if Student.query.join(User).filter(User.username == username).first():
            continue
        target_class = class_5 if i < 5 else (class_6 or class_5)
        target_grade = default_grade
        if target_class and target_class.grade_id:
            target_grade = Grade.query.get(target_class.grade_id) or default_grade
        if not target_class or not target_grade:
            continue

        user = _create_user(username, f"{username}@mps.edu.so", name_ar, student_role, school.id)
        if not user:
            continue

        student = Student(
            user_id=user.id,
            school_id=school.id,
            grade_id=target_grade.id,
            class_id=target_class.id,
            student_id=_next_student_number(school),
            full_name=name_ar,
            full_name_ar=name_ar,
            gender=gender,
            date_of_birth=date(2013 + (i % 4), (i % 12) + 1, 10),
            enrollment_date=date(2025, 9, 1),
            region=school.region or "بنادر",
            district=school.district or "هودان",
            address=school.address or "مقديشو",
            phone=f"+252-61-{1000000 + i}",
            responsible_teacher_id=class_teacher_map.get(target_class.id) if target_class else None,
        )
        db.session.add(student)
        db.session.flush()
        sync_kpis_for_student(student.id)
        created["students"] += 1

    db.session.commit()
    return created
