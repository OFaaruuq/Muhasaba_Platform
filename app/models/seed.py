from datetime import date, timedelta

from app.extensions import db
from app.models.user import Role, User
from app.models.school import School, AcademicYear, Grade, Class, Subject
from app.models.student import Student, Parent
from app.models.teacher import Teacher, TeacherClass
from app.models.kpi import KPI, StudentKPI
from app.models.attendance import Attendance
from app.models.questionnaire import Questionnaire, Question
from app.models.exam import Exam, ExamQuestion
from app.models.notification import Notification


def _demo_category(school_id):
    from app.services.config_service import get_default_questionnaire_category
    return get_default_questionnaire_category(school_id)


def _demo_exam_type(school_id):
    from app.services.config_service import get_config_choices
    choices = get_config_choices("exam_type", school_id)
    return choices[0][0] if choices else "quiz"


def _demo_exam_question_type(school_id):
    from app.services.config_service import get_default_exam_question_type
    return get_default_exam_question_type(school_id)


def _demo_gender(school_id):
    from app.services.config_service import get_gender_choices
    choices = get_gender_choices(school_id)
    return choices[0][0] if choices else "male"


def _demo_attendance_codes(school_id):
    from app.services.config_service import get_default_attendance_status, get_attendance_statuses
    present = get_default_attendance_status(school_id)
    late = present
    for s in get_attendance_statuses(school_id):
        if s.code != present and not s.counts_as_present:
            late = s.code
            break
    if late == present:
        statuses = get_attendance_statuses(school_id)
        if len(statuses) > 1:
            late = statuses[1].code
    return present, late


def seed_database():
    if Role.query.first():
        return

    roles = [
        Role(name="super_admin", name_ar="المشرف الأعلى", description="التحكم الكامل بالمنصة"),
        Role(name="ministry_admin", name_ar="مسؤول الوزارة", description="إدارة على مستوى الوزارة"),
        Role(name="school_manager", name_ar="مدير المدرسة", description="إدارة المدرسة"),
        Role(name="teacher", name_ar="معلم", description="تقييم الطلاب وإدارة الفصول"),
        Role(name="student", name_ar="طالب", description="عرض الأداء والمحاسبة الذاتية"),
        Role(name="parent", name_ar="ولي أمر", description="متابعة أداء الأبناء"),
    ]
    db.session.add_all(roles)
    db.session.flush()

    from app.services.permission_registry import apply_default_role_permissions
    apply_default_role_permissions(force=True)

    super_role = Role.query.filter_by(name="super_admin").first()
    ministry_role = Role.query.filter_by(name="ministry_admin").first()
    school_role = Role.query.filter_by(name="school_manager").first()
    teacher_role = Role.query.filter_by(name="teacher").first()
    student_role = Role.query.filter_by(name="student").first()
    parent_role = Role.query.filter_by(name="parent").first()

    default_kpis = [
        KPI(code="attendance", name="Attendance", name_ar="الحضور", weight=20.0, is_default=True, description="سجل الحضور"),
        KPI(code="homework", name="Homework", name_ar="الواجبات", weight=15.0, is_default=True, description="تقييم الواجبات اليومي"),
        KPI(code="reading", name="Reading", name_ar="القراءة", weight=15.0, is_default=True, description="تقييم القراءة"),
        KPI(code="exams", name="Exams", name_ar="الاختبارات", weight=20.0, is_default=True, description="نتائج الاختبارات"),
        KPI(code="behavior", name="Behavior", name_ar="السلوك", weight=10.0, is_default=True, description="المحاسبة + سجل السلوك"),
        KPI(code="participation", name="Participation", name_ar="المشاركة", weight=10.0, is_default=True, description="تقييم المشاركة الشخصية"),
        KPI(code="islamic_ethics", name="Islamic Ethics", name_ar="الأخلاق الإسلامية", weight=10.0, is_default=True, description="معايير الأخلاق من المحاسبة اليومية"),
    ]
    db.session.add_all(default_kpis)

    school = School(
        name="Mogadishu Primary School",
        name_ar="مدرسة مقديشو الابتدائية",
        code="MPS-001",
        district="Hodan",
        region="Banadir",
        address="شارع مكة المكرمة، مقديشو",
        phone="+252-61-0000001",
        email="info@mps.edu.so",
        principal_name="أحمد محمد علي",
    )
    db.session.add(school)
    db.session.flush()

    school2 = School(
        name="Hargeisa Secondary School",
        name_ar="مدرسة هرجيسا الثانوية",
        code="HSS-002",
        district="Central",
        region="Maroodi Jeex",
        address="وسط هرجيسا",
        phone="+252-63-0000002",
        email="info@hss.edu.so",
        principal_name="فاطمة حسن",
    )
    db.session.add(school2)
    db.session.flush()

    year = AcademicYear(
        school_id=school.id,
        name="2025-2026",
        start_date=date(2025, 9, 1),
        end_date=date(2026, 6, 30),
        is_current=True,
    )
    db.session.add(year)
    db.session.flush()

    grades = [
        Grade(school_id=school.id, name="Grade 5", name_ar="الصف الخامس", level=5),
        Grade(school_id=school.id, name="Grade 6", name_ar="الصف السادس", level=6),
    ]
    db.session.add_all(grades)
    db.session.flush()

    class_5a = Class(
        school_id=school.id,
        grade_id=grades[0].id,
        name="5-A",
        section="A",
        capacity=30,
        academic_year_id=year.id,
    )
    class_6a = Class(
        school_id=school.id,
        grade_id=grades[1].id,
        name="6-A",
        section="A",
        capacity=30,
        academic_year_id=year.id,
    )
    db.session.add_all([class_5a, class_6a])
    db.session.flush()

    subjects = [
        Subject(school_id=school.id, name="Mathematics", name_ar="الرياضيات", code="MATH"),
        Subject(school_id=school.id, name="Arabic", name_ar="اللغة العربية", code="ARAB"),
        Subject(school_id=school.id, name="Islamic Studies", name_ar="التربية الإسلامية", code="ISLM"),
        Subject(school_id=school.id, name="Science", name_ar="العلوم", code="SCI"),
    ]
    db.session.add_all(subjects)
    db.session.flush()

    def create_user(username, email, password, full_name_ar, role, school_id=None):
        user = User(
            username=username,
            email=email,
            full_name=full_name_ar,
            full_name_ar=full_name_ar,
            role_id=role.id,
            school_id=school_id,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        return user

    from app.services.config_service import get_setting
    demo_pw = get_setting("demo_login_password", None, "admin123")

    create_user(
        "superadmin", "superadmin@muhasaba.so", demo_pw,
        "المشرف الأعلى للمنصة", super_role,
    )
    ministry_user = create_user(
        "ministry", "ministry@edu.so", demo_pw,
        "مسؤول وزارة التربية", ministry_role,
    )
    manager_user = create_user(
        "manager", "manager@mps.edu.so", demo_pw,
        "أحمد محمد علي", school_role, school.id,
    )
    teacher_user = create_user(
        "teacher", "teacher@mps.edu.so", demo_pw,
        "عمر عبدالله", teacher_role, school.id,
    )
    student_user = create_user(
        "student", "student@mps.edu.so", demo_pw,
        "محمد أحمد حسن", student_role, school.id,
    )
    parent_user = create_user(
        "parent", "parent@mps.edu.so", demo_pw,
        "حسن أحمد محمد", parent_role, school.id,
    )

    teacher = Teacher(
        user_id=teacher_user.id,
        school_id=school.id,
        employee_id="T-001",
        full_name="Omar Abdullah",
        full_name_ar="عمر عبدالله",
        specialization="اللغة العربية",
        hire_date=date(2020, 9, 1),
    )
    db.session.add(teacher)
    db.session.flush()

    db.session.add(TeacherClass(
        teacher_id=teacher.id,
        class_id=class_5a.id,
        subject_id=subjects[1].id,
        academic_year_id=year.id,
    ))

    student = Student(
        user_id=student_user.id,
        school_id=school.id,
        grade_id=grades[0].id,
        class_id=class_5a.id,
        student_id="S-2025-001",
        full_name="Mohamed Ahmed Hassan",
        full_name_ar="محمد أحمد حسن",
        gender=_demo_gender(school.id),
        date_of_birth=date(2014, 3, 15),
        enrollment_date=date(2025, 9, 1),
        region="بنادر",
        district="هودان",
        address="شارع مكة المكرمة، بالقرب من مسجد النور",
        phone="+252-61-2222222",
        gpa=3.8,
        responsible_teacher_id=teacher.id,
    )
    db.session.add(student)
    db.session.flush()

    parent = Parent(
        user_id=parent_user.id,
        full_name="Hassan Ahmed Mohamed",
        full_name_ar="حسن أحمد محمد",
        phone="+252-61-1111111",
        email="parent@mps.edu.so",
        relationship_type="father",
    )
    db.session.add(parent)
    db.session.flush()
    parent.children.append(student)

    from app.kpi.hooks import sync_kpis_for_student

    today = date.today()
    present_code, late_code = _demo_attendance_codes(school.id)
    for i in range(5):
        d = today - timedelta(days=i)
        if d.weekday() < 5:
            db.session.add(Attendance(
                student_id=student.id,
                school_id=school.id,
                class_id=class_5a.id,
                date=d,
                status=present_code if i != 2 else late_code,
                recorded_by=teacher_user.id,
            ))

    questionnaire = Questionnaire(
        school_id=school.id,
        teacher_id=teacher.id,
        class_id=class_5a.id,
        title="Daily Reflection",
        title_ar="تأمل يومي",
        category=_demo_category(school.id),
        due_date=today,
    )
    db.session.add(questionnaire)
    db.session.flush()
    db.session.add(Question(
        questionnaire_id=questionnaire.id,
        text="What good deed did you do today?",
        text_ar="ما العمل الصالح الذي قمت به اليوم؟",
        question_type="text",
        order=0,
    ))
    db.session.add(Question(
        questionnaire_id=questionnaire.id,
        text="Did you complete your homework?",
        text_ar="هل أنجزت واجباتك اليوم؟",
        question_type="yes_no",
        order=1,
    ))
    q_rating = Question(
        questionnaire_id=questionnaire.id,
        text="Rate your effort today",
        text_ar="قيّم مجهودك اليوم (1-5)",
        question_type="rating",
        order=2,
    )
    db.session.add(q_rating)
    db.session.flush()
    q_mcq = Question(
        questionnaire_id=questionnaire.id,
        text="Best part of today",
        text_ar="أفضل جزء في يومك",
        question_type="multiple_choice",
        order=3,
    )
    db.session.add(q_mcq)
    db.session.flush()
    from app.models.questionnaire import Choice
    for i, opt in enumerate(["الحصص", "القراءة", "اللعب", "مساعدة الآخرين"]):
        db.session.add(Choice(question_id=q_mcq.id, text=opt, text_ar=opt, order=i))

    exam = Exam(
        school_id=school.id,
        class_id=class_5a.id,
        subject_id=subjects[1].id,
        teacher_id=teacher.id,
        title="Arabic Quiz",
        title_ar="اختبار العربية",
        exam_type=_demo_exam_type(school.id),
        exam_date=today,
        is_published=True,
    )
    db.session.add(exam)
    db.session.flush()
    db.session.add(ExamQuestion(
        exam_id=exam.id,
        text="What is the capital of Somalia?",
        text_ar="ما عاصمة الصومال؟",
        question_type=_demo_exam_question_type(school.id),
        marks=10,
        correct_answer="mogadishu",
        options=["Mogadishu", "Hargeisa", "Kismayo", "Baidoa"],
    ))

    from app.services.config_service import ensure_school_defaults, get_setting, get_notification_type_code
    ensure_school_defaults(school.id)
    db.session.add(Notification(
        user_id=parent_user.id,
        title=get_setting("platform_name_ar", school.id, "منصة المحاسبة"),
        message=get_setting("platform_tagline_ar", school.id, ""),
        notification_type=get_notification_type_code("general", school.id),
    ))

    from app.services.config_service import provision_school_kpis
    ensure_school_defaults(None)
    provision_school_kpis(school.id)

    db.session.commit()
    sync_kpis_for_student(student.id)
