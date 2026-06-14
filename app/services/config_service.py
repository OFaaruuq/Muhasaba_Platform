import json

from sqlalchemy import or_

from app.extensions import db
from app.models import (
    PlatformSetting, EvaluationCriterion, RatingLevel,
    AttendanceStatusConfig, ConfigOption, KPI,
)

DEFAULT_SETTINGS = {
    "platform_name_ar": ("منصة المحاسبة التعليمية", "general", "اسم المنصة"),
    "platform_tagline_ar": ("قياس الأداء، تطوير السلوك، وبناء مستقبل أفضل", "general", "الشعار"),
    "org_central_name_ar": ("الوزارة", "general", "اسم الجهة المركزية (بديل: الإدارة المركزية، المؤسسة…)"),
    "org_central_admin_role_ar": ("مسؤول الوزارة", "general", "تسمية دور المسؤول المركزي"),
    "org_central_dashboard_title_ar": ("لوحة تحكم الإدارة المركزية", "general", "عنوان لوحة المسؤول المركزي"),
    "grade_a_min": ("90", "grading", "حد الدرجة A"),
    "grade_b_min": ("80", "grading", "حد الدرجة B"),
    "grade_c_min": ("70", "grading", "حد الدرجة C"),
    "grade_d_min": ("60", "grading", "حد الدرجة D"),
    "default_class_capacity": ("30", "general", "سعة الفصل الافتراضية"),
    "kpi_period_days_term": ("90", "kpi", "أيام الفترة الفصلية"),
    "kpi_period_days_weekly": ("7", "kpi", "أيام فترة KPI الأسبوعية"),
    "kpi_period_days_monthly": ("30", "kpi", "أيام فترة KPI الشهرية"),
    "perf_green_min": ("80", "performance", "حد اللون الأخضر %"),
    "perf_yellow_min": ("60", "performance", "حد اللون الأصفر %"),
    "monthly_strength_min": ("4", "performance", "حد نقاط القوة (1-5)"),
    "monthly_weakness_max": ("2", "performance", "حد نقاط الضعف (1-5)"),
    "show_demo_logins": ("true", "general", "عرض حسابات تجريبية في الدخول"),
    "perf_label_success": ("ممتاز", "performance", "تسمية الأداء الأخضر"),
    "perf_label_warning": ("متوسط", "performance", "تسمية الأداء الأصفر"),
    "perf_label_danger": ("يحتاج متابعة", "performance", "تسمية الأداء الأحمر"),
    "default_exam_total_marks": ("100", "general", "الدرجة الكاملة الافتراضية للاختبار"),
    "default_exam_passing_marks": ("50", "general", "درجة النجاح الافتراضية"),
    "default_exam_duration": ("60", "general", "مدة الاختبار بالدقائق"),
    "reading_lesson_score": ("75", "scoring", "درجة إنجاز قراءة الدرس"),
    "ui_not_evaluated": ("لم يُقيَّم", "ui", "تسمية: غير مُقيَّم"),
    "ui_active": ("نشط", "ui", "تسمية: نشط"),
    "ui_inactive": ("معطّل", "ui", "تسمية: معطّل"),
    "ui_yes": ("نعم", "ui", "تسمية: نعم"),
    "ui_no": ("لا", "ui", "تسمية: لا"),
    "ui_complete": ("مكتمل", "ui", "تسمية: مكتمل"),
    "ui_partial": ("جزئي", "ui", "تسمية: جزئي"),
    "ui_new": ("جديد", "ui", "تسمية: جديد"),
    "ui_not_started": ("لم يبدأ", "ui", "تسمية: لم يبدأ"),
    "ui_not_submitted": ("لم يُقدَّم", "ui", "تسمية: لم يُقدَّم"),
    "ui_active_feminine": ("نشطة", "ui", "تسمية: نشطة (مؤنث)"),
    "ui_inactive_feminine": ("معطّلة", "ui", "تسمية: معطّلة (مؤنث)"),
    "ui_optional": ("اختياري", "ui", "تسمية: اختياري"),
    "ui_expired": ("منتهٍ", "ui", "تسمية: منتهٍ"),
    "ui_unspecified": ("غير محدد", "ui", "تسمية: غير محدد"),
    "ui_no_records": ("لا سجلات", "ui", "تسمية: لا سجلات"),
    "ui_no_evaluations": ("لا تقييمات", "ui", "تسمية: لا تقييمات"),
    "ui_due_date": ("استحقاق", "ui", "تسمية: استحقاق"),
    "ui_monthly_eval_done": ("تقييم شهري مكتمل", "ui", "تسمية: تقييم شهري مكتمل"),
    "demo_login_password": ("admin123", "general", "كلمة مرور الحسابات التجريبية"),
    "report_kpi_title": ("تقرير مؤشرات الأداء", "reports", "عنوان تقرير KPI"),
    "report_eval_title": ("تقرير التقييم", "reports", "عنوان تقرير التقييم"),
    "report_monthly_title": ("التقرير الشهري", "reports", "عنوان التقرير الشهري"),
    "report_strengths_header": ("نقاط القوة", "reports", "عنوان نقاط القوة"),
    "report_weaknesses_header": ("نقاط الضعف", "reports", "عنوان نقاط الضعف"),
    "report_recommendations_header": ("التوصيات", "reports", "عنوان التوصيات"),
    "rec_follow_up": ("يُنصح بمتابعة:", "recommendations", "بداية توصية المتابعة"),
    "rec_improvement_plan": ("وضع خطة تحسين أسبوعية مع المسؤول.", "recommendations", "توصية خطة التحسين"),
    "rec_complete_eval": ("أكمل التقييم الشهري لإنشاء التوصيات.", "recommendations", "توصية إكمال التقييم"),
    "rec_good_performance": ("أداء جيد — استمر في المتابعة والتشجيع.", "recommendations", "توصية الأداء الجيد"),
    "ui_not_answered": ("لم يُجب", "ui", "تسمية: لم يُجب"),
    "ui_survey_not_filled": ("لم يُعبَّأ", "ui", "تسمية: لم يُعبَّأ"),
    "ui_survey_partial": ("جزئي ({answered}/{total})", "ui", "تسمية: استبيان جزئي"),
    "ui_show_inactive": ("عرض المعطّلين", "ui", "تسمية: عرض المعطّلين"),
    "ui_no_active_students": ("لا يوجد طلاب نشطون في هذه المجموعة.", "ui", "تسمية: لا طلاب نشطين"),
    "kpi_active_indicators": ("المؤشرات النشطة", "kpi", "تسمية المؤشرات النشطة"),
    "kpi_avg_performance": ("متوسط الأداء %", "kpi", "تسمية متوسط الأداء في الرسوم"),
    "kpi_monthly_avg_detail": ("متوسط {count} شهر", "kpi", "تفاصيل KPI الشهري"),
    "ui_counts_as_present": ("يُحسب حاضر", "ui", "تسمية: يُحسب حاضر"),
    "kpi_period_term_label": ("فصلي", "kpi", "تسمية فترة KPI: فصلي"),
    "kpi_period_monthly_label": ("شهري", "kpi", "تسمية فترة KPI: شهري"),
    "kpi_period_weekly_label": ("أسبوعي", "kpi", "تسمية فترة KPI: أسبوعي"),
    "kpi_period_daily_label": ("يومي", "kpi", "تسمية فترة KPI: يومي"),
    "exam_types_with_options": ("mcq", "general", "أنواع أسئلة الاختبار التي تحتاج خيارات"),
    "notify_monthly_title": ("تقييم شهري", "notifications", "عنوان إشعار التقييم الشهري"),
    "notify_monthly_message": ("تم تقييم {student} لشهر {month}/{year}: {score}%", "notifications", "رسالة التقييم الشهري"),
    "notify_daily_title": ("تقييم محاسبة يومي", "notifications", "عنوان التقييم اليومي"),
    "notify_daily_message": ("تم تقييم {student} اليوم: {score}%", "notifications", "رسالة التقييم اليومي"),
    "notify_behavior_title": ("سجل سلوك", "notifications", "عنوان إشعار السلوك"),
    "notify_behavior_message": ("تم تسجيل ملاحظة سلوكية لـ {student}", "notifications", "رسالة إشعار السلوك"),
    "notify_exam_title": ("نتيجة اختبار", "notifications", "عنوان نتيجة الاختبار"),
    "notify_exam_message": ("حصل {student} على {score}% في {exam}", "notifications", "رسالة نتيجة الاختبار"),
    "report_student_label": ("الطالب", "reports", "تسمية الطالب في التقارير"),
    "report_id_label": ("الرقم", "reports", "تسمية الرقم في التقارير"),
    "report_date_label": ("التاريخ", "reports", "تسمية التاريخ في التقارير"),
    "report_overall_kpi": ("المؤشر الكلي", "reports", "تسمية المؤشر الكلي"),
    "report_overall_score": ("الدرجة الكلية", "reports", "تسمية الدرجة الكلية"),
    "report_daily_label": ("اليومي", "reports", "تسمية التقييم اليومي"),
    "report_criteria_details": ("تفاصيل المعايير", "reports", "عنوان تفاصيل المعايير"),
    "report_no_monthly": ("لا يوجد تقييم شهري لهذه الفترة", "reports", "رسالة عدم وجود تقييم شهري"),
    "report_period_label": ("الفترة", "reports", "تسمية الفترة"),
    "student_registration_fields": (
        '{"mode":"concise","fields":{"full_name_ar":{"visible":true,"required":true},"gender":{"visible":true,"required":true},"responsible_teacher_id":{"visible":true,"required":false}}}',
        "registration",
        "حقول تسجيل الطلاب (JSON)",
    ),
    "attendance_time_enabled": ("true", "attendance", "تفعيل قواعد الوقت للحضور"),
    "attendance_session_start": ("08:00", "attendance", "وقت بداية اللقاء"),
    "attendance_on_time_until": ("08:15", "attendance", "حاضر حتى"),
    "attendance_late_until": ("08:45", "attendance", "متأخر حتى"),
    "attendance_absent_after": ("08:46", "attendance", "غائب بعد"),
    "attendance_auto_suggest": ("true", "attendance", "اقتراح الحالة تلقائياً من الوقت"),
    "attendance_record_time": ("true", "attendance", "تسجيل وقت الحضور"),
}

DEMO_USERNAMES = ("superadmin", "ministry", "manager", "teacher", "student", "parent")

READING_LEGACY_COLUMNS = frozenset({"fluency", "pronunciation", "understanding", "overall_rating"})

MONTHLY_CATEGORY_FIELD_MAP = {
    "individual_program": "individual_program_score",
    "pairs": "pairs_score",
    "meetings": "meetings_score",
    "discipline": "discipline_score",
    "behavior_followup": "behavior_followup_score",
}

CONFIG_SECTION_LABELS = {
    "exam_type": "أنواع الاختبارات",
    "exam_question_type": "أنواع أسئلة الاختبار",
    "questionnaire_category": "تصنيفات الاستبيان",
    "questionnaire_question_type": "أنواع أسئلة الاستبيان",
    "behavior_type": "أنواع السلوك (مع درجة KPI)",
    "self_assessment": "بنود المحاسبة الذاتية",
    "reading_aspect": "جوانب تقييم القراءة",
    "gender": "خيارات الجنس",
    "yes_no": "نعم / لا",
    "true_false": "صح / خطأ",
    "parent_relationship": "صلة القرابة (ولي الأمر)",
    "monthly_category": "تصنيفات التقييم الشهري",
    "criterion_category": "تصنيفات المعايير اليومية",
    "notification_type": "أنواع الإشعارات",
    "kpi_data_source": "مصادر بيانات KPI",
}

SETTING_CATEGORY_LABELS = {
    "general": "عام",
    "grading": "الدرجات الحرفية",
    "kpi": "مؤشرات الأداء",
    "performance": "عتبات الأداء",
    "scoring": "الدرجات الرقمية",
    "ui": "تسميات الواجهة",
    "reports": "التقارير",
    "notifications": "الإشعارات",
    "recommendations": "التوصيات",
    "attendance": "الحضور",
    "registration": "التسجيل",
}

DEFAULT_MONTHLY_CRITERIA = [
    ("individual_program", "quran", "القرآن", "reading"),
    ("individual_program", "adkaar", "الأذكار", "islamic_ethics"),
    ("individual_program", "wird", "الورد", "islamic_ethics"),
    ("individual_program", "mudaawama", "المذاكرة", "homework"),
    ("pairs", "pair_participation", "المشاركة", "participation"),
    ("pairs", "pair_interaction", "التفاعل", "participation"),
    ("meetings", "meeting_attendance", "الحضور", "attendance"),
    ("meetings", "meeting_participation", "المشاركة في اللقاء", "participation"),
    ("discipline", "time_keeping", "الالتزام بالوقت", "behavior"),
    ("discipline", "ethics", "الأخلاق", "islamic_ethics"),
    ("discipline", "monthly_respect", "الاحترام", "islamic_ethics"),
    ("behavior_followup", "educational_change", "التغيير التربوي", "behavior"),
    ("behavior_followup", "discipline_followup", "الانضباط", "behavior"),
]

DEFAULT_MONTHLY_RATINGS = [
    ("5", "ممتاز", 100),
    ("4", "جيد جدًا", 80),
    ("3", "جيد", 60),
    ("2", "ضعيف", 40),
    ("1", "ضعيف جدًا", 20),
]

DEFAULT_CRITERIA = [
    ("academic", "homework", "إنجاز الواجبات", "homework"),
    ("academic", "understanding", "فهم الدرس", "homework"),
    ("academic", "reading", "القراءة", "reading"),
    ("behavior", "respect", "الاحترام", "islamic_ethics"),
    ("behavior", "discipline", "الانضباط", "behavior"),
    ("behavior", "honesty", "الصدق", "islamic_ethics"),
    ("behavior", "cooperation", "التعاون", "islamic_ethics"),
    ("personal", "responsibility", "المسؤولية", "participation"),
    ("personal", "leadership", "القيادة", "participation"),
    ("personal", "initiative", "المبادرة", "participation"),
]

DEFAULT_RATINGS = [
    ("excellent", "ممتاز", 100),
    ("good", "جيد", 75),
    ("average", "متوسط", 50),
    ("needs_improvement", "يحتاج تحسين", 25),
]

DEFAULT_ATTENDANCE_STATUSES = [
    ("present", "حاضر", True, False, "success", None, "08:15"),
    ("late", "متأخر", True, True, "warning", "08:16", "08:45"),
    ("absent", "غائب", False, True, "danger", "08:46", None),
    ("excused", "غياب بعذر", True, False, "info", None, None),
]

DEFAULT_CONFIG_OPTIONS = {
    "exam_type": [
        ("quiz", "قصير"),
        ("midterm", "نصفي"),
        ("final", "نهائي"),
    ],
    "exam_question_type": [
        ("mcq", "اختيار من متعدد"),
        ("true_false", "صح / خطأ"),
        ("fill_blank", "ملء فراغ"),
        ("essay", "مقالي"),
    ],
    "questionnaire_category": [
        ("academic", "أكاديمي"),
        ("personal", "شخصي"),
        ("behavioral", "سلوكي"),
    ],
    "questionnaire_question_type": [
        ("text", "نص"),
        ("yes_no", "نعم / لا"),
        ("rating", "تقييم 1-5"),
        ("multiple_choice", "اختيار متعدد"),
    ],
    "behavior_type": [
        ("positive", "إيجابي"),
        ("negative", "سلبي"),
        ("neutral", "محايد"),
    ],
    "self_assessment": [
        ("attended_classes", "هل حضرت جميع الحصص؟"),
        ("completed_homework", "هل أنجزت الواجبات؟"),
        ("helped_classmates", "هل ساعدت زملاءك؟"),
        ("respected_teachers", "هل احترمت المعلمين؟"),
    ],
    "criterion_category": [
        ("academic", "الأداء الأكاديمي"),
        ("behavior", "السلوك"),
        ("personal", "التطوير الشخصي"),
    ],
    "monthly_category": [
        ("individual_program", "البرنامج الفردي"),
        ("pairs", "الثنائيات"),
        ("meetings", "اللقاءات"),
        ("discipline", "الانضباط"),
        ("behavior_followup", "السلوك والمتابعة"),
    ],
    "reading_aspect": [
        ("fluency", "الطلاقة"),
        ("pronunciation", "النطق"),
        ("understanding", "الفهم"),
        ("overall_rating", "التقييم العام"),
    ],
    "gender": [
        ("male", "ذكر"),
        ("female", "أنثى"),
    ],
    "true_false": [
        ("true", "صح"),
        ("false", "خطأ"),
    ],
    "yes_no": [
        ("yes", "نعم"),
        ("no", "لا"),
    ],
    "parent_relationship": [
        ("father", "أب"),
        ("mother", "أم"),
        ("guardian", "ولي أمر"),
    ],
    "notification_type": [
        ("general", "عام"),
        ("behavior", "سلوك"),
        ("grade", "درجات"),
        ("attendance", "حضور"),
        ("evaluation", "تقييم"),
    ],
    "kpi_data_source": [
        ("attendance", "سجل الحضور"),
        ("homework", "تقييم الواجبات اليومي"),
        ("reading", "تقييم القراءة"),
        ("exams", "نتائج الاختبارات"),
        ("behavior", "المحاسبة + سجل السلوك"),
        ("participation", "تقييم المشاركة الشخصية"),
        ("islamic_ethics", "معايير الأخلاق من المحاسبة اليومية"),
        ("monthly_eval", "التقييم الشهري الشامل"),
    ],
}

BEHAVIOR_TYPE_SCORES = {
    "positive": 90,
    "negative": 30,
    "neutral": 60,
}

KPI_SOURCE_DESCRIPTIONS = {
    "attendance": "سجل الحضور",
    "homework": "تقييم الواجبات اليومي",
    "reading": "تقييم القراءة",
    "exams": "نتائج الاختبارات",
    "behavior": "المحاسبة + سجل السلوك",
    "participation": "تقييم المشاركة الشخصية",
    "islamic_ethics": "معايير الأخلاق من المحاسبة اليومية",
}


def ensure_school_defaults(school_id=None):
    """Seed default config for a school (or global if school_id is None)."""
    for key, (value, category, label_ar) in DEFAULT_SETTINGS.items():
        exists = PlatformSetting.query.filter_by(school_id=school_id, key=key).first()
        if not exists:
            db.session.add(PlatformSetting(
                school_id=school_id, key=key, value=value,
                category=category, label_ar=label_ar,
            ))

    for i, (cat, code, name_ar, kpi_src) in enumerate(DEFAULT_CRITERIA):
        exists = EvaluationCriterion.query.filter_by(
            school_id=school_id, code=code, evaluation_type="daily",
        ).first()
        if not exists and not EvaluationCriterion.query.filter_by(
            school_id=school_id, code=code,
        ).filter(
            or_(EvaluationCriterion.evaluation_type == "daily",
                EvaluationCriterion.evaluation_type.is_(None))
        ).first():
            db.session.add(EvaluationCriterion(
                school_id=school_id, category=cat, code=code,
                name_ar=name_ar, order=i, kpi_source=kpi_src,
                evaluation_type="daily",
            ))

    for i, (cat, code, name_ar, kpi_src) in enumerate(DEFAULT_MONTHLY_CRITERIA):
        exists = EvaluationCriterion.query.filter_by(
            school_id=school_id, code=code, evaluation_type="monthly",
        ).first()
        if not exists:
            db.session.add(EvaluationCriterion(
                school_id=school_id, category=cat, code=code,
                name_ar=name_ar, order=i, kpi_source=kpi_src,
                evaluation_type="monthly",
            ))

    for i, (code, name_ar, score) in enumerate(DEFAULT_RATINGS):
        exists = RatingLevel.query.filter_by(
            school_id=school_id, code=code, scale_type="qualitative",
        ).first()
        if not exists:
            db.session.add(RatingLevel(
                school_id=school_id, code=code, name_ar=name_ar,
                score=score, order=i, scale_type="qualitative",
            ))

    for i, (code, name_ar, score) in enumerate(DEFAULT_MONTHLY_RATINGS):
        exists = RatingLevel.query.filter_by(
            school_id=school_id, code=code, scale_type="numeric_5",
        ).first()
        if not exists:
            db.session.add(RatingLevel(
                school_id=school_id, code=code, name_ar=name_ar,
                score=score, order=i, scale_type="numeric_5",
            ))

    for i, row in enumerate(DEFAULT_ATTENDANCE_STATUSES):
        code, name_ar, present, notify, badge = row[:5]
        time_from = row[5] if len(row) > 5 else None
        time_to = row[6] if len(row) > 6 else None
        exists = AttendanceStatusConfig.query.filter_by(school_id=school_id, code=code).first()
        if not exists:
            db.session.add(AttendanceStatusConfig(
                school_id=school_id, code=code, name_ar=name_ar,
                counts_as_present=present, notify_parent=notify,
                badge_class=badge, time_from=time_from, time_to=time_to, order=i,
            ))

    for option_type, options in DEFAULT_CONFIG_OPTIONS.items():
        for i, (code, name_ar) in enumerate(options):
            exists = ConfigOption.query.filter_by(
                school_id=school_id, option_type=option_type, code=code,
            ).first()
            if not exists:
                meta = None
                if option_type == "behavior_type" and code in BEHAVIOR_TYPE_SCORES:
                    meta = json.dumps({"score": BEHAVIOR_TYPE_SCORES[code]})
                elif option_type == "kpi_data_source":
                    meta = json.dumps({"builtin": True, "calculator": code})
                db.session.add(ConfigOption(
                    school_id=school_id, option_type=option_type,
                    code=code, name_ar=name_ar, order=i,
                    metadata_json=meta,
                ))

    db.session.commit()

    from app.services.content_seeds import (
        NAV_LABELS_SEED, REGISTRATION_SECTION_LABELS_SEED, dumps_json,
    )
    from app.services.survey_config_service import ensure_survey_config

    ensure_survey_config(school_id)

    if not get_setting("nav_labels_json", school_id):
        set_setting(
            "nav_labels_json", dumps_json(NAV_LABELS_SEED),
            school_id=school_id, category="ui", label_ar="تسميات القائمة الرئيسية",
        )
    if not get_setting("registration_section_labels_json", school_id):
        set_setting(
            "registration_section_labels_json", dumps_json(REGISTRATION_SECTION_LABELS_SEED),
            school_id=school_id, category="registration", label_ar="تسميات أقسام التسجيل",
        )
    if not get_setting("registration_field_definitions_json", school_id):
        from app.services.registration_field_service import FIELD_DEFINITIONS
        set_setting(
            "registration_field_definitions_json", dumps_json(FIELD_DEFINITIONS),
            school_id=school_id, category="registration", label_ar="تعريف حقول التسجيل",
        )
    if not get_setting("registration_academic_labels_json", school_id):
        from app.services.registration_lookup_service import ACADEMIC_LOOKUP_DEFAULTS
        set_setting(
            "registration_academic_labels_json", dumps_json(ACADEMIC_LOOKUP_DEFAULTS),
            school_id=school_id, category="registration", label_ar="تسميات الحقول الدراسية",
        )


def provision_school_kpis(school_id):
    """Copy default KPIs to a new school."""
    defaults = KPI.query.filter_by(is_default=True, school_id=None).all()
    if not defaults:
        defaults = KPI.query.filter_by(school_id=None, is_active=True).all()
    for kpi in defaults:
        exists = KPI.query.filter_by(school_id=school_id, code=kpi.code).first()
        if not exists:
            db.session.add(KPI(
                school_id=school_id,
                code=kpi.code,
                name=kpi.name,
                name_ar=kpi.name_ar,
                weight=kpi.weight,
                description=kpi.description,
                is_default=False,
            ))
    db.session.commit()


def get_setting(key, school_id=None, default=None):
    if school_id:
        s = PlatformSetting.query.filter_by(school_id=school_id, key=key).first()
        if s:
            return _cast(s.value, s.value_type)
    s = PlatformSetting.query.filter_by(school_id=None, key=key).first()
    if s:
        return _cast(s.value, s.value_type)
    if key in DEFAULT_SETTINGS:
        return DEFAULT_SETTINGS[key][0]
    return default


def set_setting(key, value, school_id=None, category="general", label_ar="", value_type=None):
    s = PlatformSetting.query.filter_by(school_id=school_id, key=key).first()
    if not s:
        s = PlatformSetting(
            school_id=school_id,
            key=key,
            category=category,
            label_ar=label_ar,
            value_type=value_type or infer_setting_value_type(key, value),
        )
        db.session.add(s)
    s.value = str(value) if not isinstance(value, str) else value
    if value_type:
        s.value_type = value_type
    if label_ar:
        s.label_ar = label_ar
    if category:
        s.category = category
    db.session.commit()


def add_platform_setting(key, value, school_id=None, category="general", label_ar="", value_type=None):
    key = (key or "").strip()
    if not key:
        raise ValueError("مفتاح الإعداد مطلوب")
    exists = PlatformSetting.query.filter_by(school_id=school_id, key=key).first()
    if exists:
        raise ValueError(f"المفتاح «{key}» موجود مسبقاً")
    row = PlatformSetting(
        school_id=school_id,
        key=key,
        value=str(value),
        category=category or "general",
        label_ar=label_ar or key,
        value_type=value_type or infer_setting_value_type(key, value),
    )
    db.session.add(row)
    db.session.commit()
    return row


def get_criteria_grouped(school_id=None, evaluation_type="daily"):
    query = EvaluationCriterion.query.filter_by(is_active=True)
    if evaluation_type == "daily":
        query = query.filter(
            or_(EvaluationCriterion.evaluation_type == "daily",
                EvaluationCriterion.evaluation_type.is_(None))
        )
    else:
        query = query.filter_by(evaluation_type=evaluation_type)
    if school_id:
        school_items = query.filter_by(school_id=school_id).order_by(EvaluationCriterion.order).all()
        if school_items:
            return _group_criteria(school_items)
    global_items = query.filter_by(school_id=None).order_by(EvaluationCriterion.order).all()
    return _group_criteria(global_items)


def get_monthly_criteria_grouped(school_id=None):
    return get_criteria_grouped(school_id, evaluation_type="monthly")


def _group_criteria(items):
    grouped = {}
    for c in items:
        grouped.setdefault(c.category, []).append(c)
    return grouped


def _rating_query(school_id=None, scale_type="qualitative"):
    query = RatingLevel.query.filter_by(is_active=True)
    if scale_type == "qualitative":
        query = query.filter(
            or_(RatingLevel.scale_type == "qualitative", RatingLevel.scale_type.is_(None))
        )
    else:
        query = query.filter_by(scale_type=scale_type)
    if school_id:
        items = query.filter_by(school_id=school_id).order_by(RatingLevel.order).all()
        if items:
            return items
    return query.filter_by(school_id=None).order_by(RatingLevel.order).all()


def get_rating_choices(school_id=None):
    return [(r.code, r.name_ar) for r in _rating_query(school_id, "qualitative")]


def get_rating_scores(school_id=None):
    return {r.code: r.score for r in _rating_query(school_id, "qualitative")}


def get_monthly_rating_choices(school_id=None):
    items = _rating_query(school_id, "numeric_5")
    return [(r.code, r.name_ar) for r in sorted(items, key=lambda x: -int(x.code))]


def get_monthly_rating_scores(school_id=None):
    return {r.code: r.score for r in _rating_query(school_id, "numeric_5")}


def get_attendance_statuses(school_id=None):
    query = AttendanceStatusConfig.query.filter_by(is_active=True)
    if school_id:
        items = query.filter_by(school_id=school_id).order_by(AttendanceStatusConfig.order).all()
        if items:
            return items
    return query.filter_by(school_id=None).order_by(AttendanceStatusConfig.order).all()


def get_present_status_codes(school_id=None):
    statuses = get_attendance_statuses(school_id)
    return [s.code for s in statuses if s.counts_as_present]


def get_notify_status_codes(school_id=None):
    statuses = get_attendance_statuses(school_id)
    return [s.code for s in statuses if s.notify_parent]


def get_grade_letter(percentage, school_id=None):
    pct = float(percentage)
    if pct >= float(get_setting("grade_a_min", school_id, 90)):
        return "A"
    if pct >= float(get_setting("grade_b_min", school_id, 80)):
        return "B"
    if pct >= float(get_setting("grade_c_min", school_id, 70)):
        return "C"
    if pct >= float(get_setting("grade_d_min", school_id, 60)):
        return "D"
    return "F"


def get_criterion_codes_by_kpi_source(kpi_source, school_id=None):
    query = EvaluationCriterion.query.filter_by(is_active=True, kpi_source=kpi_source)
    if school_id:
        items = query.filter_by(school_id=school_id).all()
        if items:
            return [c.code for c in items]
    return [c.code for c in query.filter_by(school_id=None).all()]


def get_ethics_criterion_codes(school_id=None):
    codes = get_criterion_codes_by_kpi_source("islamic_ethics", school_id)
    return codes or [code for cat, code, _, src in DEFAULT_CRITERIA if src == "islamic_ethics"]


def get_homework_criterion_codes(school_id=None):
    codes = get_criterion_codes_by_kpi_source("homework", school_id)
    return codes or [code for cat, code, _, src in DEFAULT_CRITERIA if src == "homework"]


def get_reading_criterion_codes(school_id=None):
    codes = get_criterion_codes_by_kpi_source("reading", school_id)
    if codes:
        return codes
    grouped = get_criteria_grouped(school_id)
    found = []
    for items in grouped.values():
        for c in items:
            if c.kpi_source == "reading" or c.code == "reading":
                found.append(c.code)
    return found or ["reading"]


def get_personal_criterion_codes(school_id=None):
    grouped = get_criteria_grouped(school_id)
    personal = grouped.get("personal", [])
    if personal:
        return [c.code for c in personal]
    return [code for cat, code, _, _ in DEFAULT_CRITERIA if cat == "personal"]


def get_config_options(option_type, school_id=None):
    query = ConfigOption.query.filter_by(option_type=option_type, is_active=True)
    if school_id:
        items = query.filter_by(school_id=school_id).order_by(ConfigOption.order).all()
        if items:
            return items
    return query.filter_by(school_id=None).order_by(ConfigOption.order).all()


def get_config_choices(option_type, school_id=None):
    return [(o.code, o.name_ar) for o in get_config_options(option_type, school_id)]


def get_config_map(option_type, school_id=None):
    return {o.code: o.name_ar for o in get_config_options(option_type, school_id)}


def get_behavior_categories(school_id=None):
    grouped = get_criteria_grouped(school_id)
    behavior = grouped.get("behavior", [])
    if behavior:
        return [(c.code, c.name_ar) for c in behavior]
    return [(code, name_ar) for cat, code, name_ar, _ in DEFAULT_CRITERIA if cat == "behavior"]


def get_criterion_category_labels(school_id=None):
    labels = get_config_map("criterion_category", school_id)
    if labels:
        return labels
    return dict(DEFAULT_CONFIG_OPTIONS["criterion_category"])


def get_monthly_category_labels(school_id=None):
    labels = get_config_map("monthly_category", school_id)
    if labels:
        return labels
    return dict(DEFAULT_CONFIG_OPTIONS["monthly_category"])


def get_performance_color(score, school_id=None):
    """Traffic-light color from admin-configured thresholds."""
    pct = float(score or 0)
    green = float(get_setting("perf_green_min", school_id, 80))
    yellow = float(get_setting("perf_yellow_min", school_id, 60))
    if pct >= green:
        return "success"
    if pct >= yellow:
        return "warning"
    return "danger"


def get_performance_label(score, school_id=None):
    color = get_performance_color(score, school_id)
    labels = {
        "success": get_setting("perf_label_success", school_id, "ممتاز"),
        "warning": get_setting("perf_label_warning", school_id, "متوسط"),
        "danger": get_setting("perf_label_danger", school_id, "يحتاج متابعة"),
    }
    return labels.get(color, "—")


def get_performance_thresholds(school_id=None):
    return {
        "green_min": float(get_setting("perf_green_min", school_id, 80)),
        "yellow_min": float(get_setting("perf_yellow_min", school_id, 60)),
        "label_success": get_setting("perf_label_success", school_id, "ممتاز"),
        "label_warning": get_setting("perf_label_warning", school_id, "متوسط"),
        "label_danger": get_setting("perf_label_danger", school_id, "يحتاج متابعة"),
    }


def get_monthly_category_score_fields(school_id=None):
    """Map monthly_category codes to MonthlyEvaluation column names."""
    configured = get_monthly_category_labels(school_id)
    result = {}
    for code in configured:
        field = MONTHLY_CATEGORY_FIELD_MAP.get(code)
        if field:
            result[code] = field
    return result or dict(MONTHLY_CATEGORY_FIELD_MAP)


def get_daily_category_field_map(school_id=None):
    """Map criterion_category codes to Evaluation score columns."""
    labels = get_criterion_category_labels(school_id)
    field_map = {
        "academic": "academic_score",
        "behavior": "behavior_score",
        "personal": "personal_score",
    }
    return {k: field_map[k] for k in labels if k in field_map}


def get_mid_rating_score(school_id=None):
    scores = list(get_rating_scores(school_id).values())
    return round(sum(scores) / len(scores), 1) if scores else 50.0


def get_default_behavior_score(school_id=None, behavior_type="positive"):
    scores = get_behavior_type_scores(school_id)
    return scores.get(behavior_type, scores.get("neutral", 60))


def get_default_exam_total_marks(school_id=None):
    return float(get_setting("default_exam_total_marks", school_id, 100))


def get_default_exam_passing_marks(school_id=None):
    return float(get_setting("default_exam_passing_marks", school_id, 50))


def get_default_exam_duration(school_id=None):
    return int(get_setting("default_exam_duration", school_id, 60))


def get_reading_lesson_score(school_id=None):
    return float(get_setting("reading_lesson_score", school_id, 75))


def get_default_behavior_type(school_id=None):
    choices = get_config_choices("behavior_type", school_id)
    return choices[0][0] if choices else "neutral"


def get_default_questionnaire_category(school_id=None):
    choices = get_config_choices("questionnaire_category", school_id)
    return choices[0][0] if choices else "academic"


def get_bool_choices(school_id=None):
    yes_map = get_config_map("yes_no", school_id)
    return [("1", yes_map.get("yes", "نعم")), ("0", yes_map.get("no", "لا"))]


def get_ui_label(key, school_id=None, default=None):
    setting_key = f"ui_{key}" if not key.startswith("ui_") else key
    fallback = DEFAULT_SETTINGS.get(setting_key, (default or "",))[0]
    return get_setting(setting_key, school_id, fallback)


def get_ui_labels(school_id=None):
    return {
        "not_evaluated": get_ui_label("not_evaluated", school_id),
        "active": get_ui_label("active", school_id),
        "inactive": get_ui_label("inactive", school_id),
        "yes": get_ui_label("yes", school_id),
        "no": get_ui_label("no", school_id),
        "complete": get_ui_label("complete", school_id),
        "partial": get_ui_label("partial", school_id),
        "new": get_ui_label("new", school_id),
        "not_started": get_ui_label("not_started", school_id),
        "not_submitted": get_ui_label("not_submitted", school_id),
        "active_feminine": get_ui_label("active_feminine", school_id),
        "inactive_feminine": get_ui_label("inactive_feminine", school_id),
        "optional": get_ui_label("optional", school_id),
        "expired": get_ui_label("expired", school_id),
        "unspecified": get_ui_label("unspecified", school_id),
        "no_records": get_ui_label("no_records", school_id),
        "no_evaluations": get_ui_label("no_evaluations", school_id),
        "due_date": get_ui_label("due_date", school_id),
        "monthly_eval_done": get_ui_label("monthly_eval_done", school_id),
        "read_lesson": get_ui_label("read_lesson", school_id),
        "counts_as_present": get_ui_label("counts_as_present", school_id),
        "not_answered": get_ui_label("not_answered", school_id),
        "survey_not_filled": get_ui_label("survey_not_filled", school_id),
        "show_inactive": get_ui_label("show_inactive", school_id),
    }


def get_nav_labels(school_id=None):
    from app.services.content_seeds import NAV_LABELS_SEED

    raw = get_setting("nav_labels_json", school_id)
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
    elif isinstance(raw, dict):
        data = raw
    else:
        data = {}
    return {**NAV_LABELS_SEED, **data}


def get_registration_section_labels(school_id=None):
    from app.services.content_seeds import REGISTRATION_SECTION_LABELS_SEED

    raw = get_setting("registration_section_labels_json", school_id)
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
    elif isinstance(raw, dict):
        data = raw
    else:
        data = {}
    return {**REGISTRATION_SECTION_LABELS_SEED, **data}


def get_registration_field_definitions(school_id=None):
    from app.services.registration_field_service import FIELD_DEFINITIONS

    raw = get_setting("registration_field_definitions_json", school_id)
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return FIELD_DEFINITIONS
    if isinstance(raw, list):
        return raw
    return FIELD_DEFINITIONS


def get_kpi_period_days(period, school_id=None):
    defaults = {"daily": 1, "weekly": 7, "monthly": 30, "term": 90}
    keys = {
        "daily": "kpi_period_days_daily",
        "weekly": "kpi_period_days_weekly",
        "monthly": "kpi_period_days_monthly",
        "term": "kpi_period_days_term",
    }
    key = keys.get(period)
    if not key:
        return defaults.get(period, 90)
    return int(get_setting(key, school_id, defaults.get(period, 90)))


def get_kpi_calculator_key(kpi_code, school_id=None):
    for opt in get_config_options("kpi_data_source", school_id):
        if opt.code != kpi_code:
            continue
        if opt.metadata_json:
            try:
                meta = json.loads(opt.metadata_json)
                if meta.get("calculator"):
                    return meta["calculator"]
                if meta.get("builtin"):
                    return kpi_code
            except (json.JSONDecodeError, TypeError):
                pass
        return kpi_code
    return None


def get_kpi_monthly_avg_detail(count, school_id=None):
    tpl = get_setting("kpi_monthly_avg_detail", school_id, "متوسط {count} شهر")
    return tpl.format(count=count)


def get_org_labels(school_id=None):
    """Dynamic labels for central organization (ministry or alternatives)."""
    central_name = get_setting("org_central_name_ar", school_id, "الوزارة")
    admin_role = get_setting("org_central_admin_role_ar", school_id, "مسؤول الوزارة")
    dashboard = get_setting(
        "org_central_dashboard_title_ar",
        school_id,
        f"لوحة تحكم {central_name}",
    )
    return {
        "central_name": central_name,
        "central_admin_role": admin_role,
        "central_dashboard_title": dashboard,
        "central_administration": f"إدارة {central_name}",
    }


def get_role_labels():
    from app.models import Role
    return {r.name: r.name_ar for r in Role.query.order_by(Role.name).all()}


def get_role_display(role_name, school_id=None):
    if role_name == "ministry_admin":
        return get_setting("org_central_admin_role_ar", school_id, "مسؤول الوزارة")
    from app.models import Role
    role = Role.query.filter_by(name=role_name).first()
    return role.name_ar if role else role_name


def sync_central_admin_role_label(label, school_id=None):
    """Keep ministry_admin role name aligned with org settings."""
    from app.models import Role
    set_setting(
        "org_central_admin_role_ar",
        label,
        school_id,
        "general",
        "تسمية دور المسؤول المركزي",
    )
    role = Role.query.filter_by(name="ministry_admin").first()
    if role:
        role.name_ar = label


def get_ui_label_schema():
    return [
        (key.replace("ui_", ""), label_ar)
        for key, (_val, _cat, label_ar) in DEFAULT_SETTINGS.items()
        if key.startswith("ui_")
    ]


def get_unspecified_label(school_id=None):
    return get_ui_label("unspecified", school_id)


def get_attendance_chart_labels(school_id=None):
    statuses = get_attendance_statuses(school_id)
    present_codes = set(get_present_status_codes(school_id))
    present_names = [s.name_ar for s in statuses if s.code in present_codes]
    absent_names = [s.name_ar for s in statuses if s.code not in present_codes]
    return (
        " + ".join(present_names) if present_names else get_ui_label("yes", school_id),
        " + ".join(absent_names) if absent_names else get_ui_label("no", school_id),
    )


def get_report_labels(school_id=None):
    return {
        "kpi_title": get_setting("report_kpi_title", school_id, "تقرير مؤشرات الأداء"),
        "eval_title": get_setting("report_eval_title", school_id, "تقرير التقييم"),
        "monthly_title": get_setting("report_monthly_title", school_id, "التقرير الشهري"),
        "strengths": get_setting("report_strengths_header", school_id, "نقاط القوة"),
        "weaknesses": get_setting("report_weaknesses_header", school_id, "نقاط الضعف"),
        "recommendations": get_setting("report_recommendations_header", school_id, "التوصيات"),
        "student": get_setting("report_student_label", school_id, "الطالب"),
        "id": get_setting("report_id_label", school_id, "الرقم"),
        "date": get_setting("report_date_label", school_id, "التاريخ"),
        "overall_kpi": get_setting("report_overall_kpi", school_id, "المؤشر الكلي"),
        "overall_score": get_setting("report_overall_score", school_id, "الدرجة الكلية"),
        "daily": get_setting("report_daily_label", school_id, "اليومي"),
        "criteria_details": get_setting("report_criteria_details", school_id, "تفاصيل المعايير"),
        "no_monthly": get_setting("report_no_monthly", school_id, "لا يوجد تقييم شهري لهذه الفترة"),
        "period": get_setting("report_period_label", school_id, "الفترة"),
    }


def get_kpi_period_choices(school_id=None):
    return [
        ("term", get_setting("kpi_period_term_label", school_id, "فصلي")),
        ("monthly", get_setting("kpi_period_monthly_label", school_id, "شهري")),
        ("weekly", get_setting("kpi_period_weekly_label", school_id, "أسبوعي")),
        ("daily", get_setting("kpi_period_daily_label", school_id, "يومي")),
    ]


def get_notification_type_code(key, school_id=None):
    choices = get_config_choices("notification_type", school_id)
    valid = {code for code, _ in choices}
    return key if key in valid else (choices[0][0] if choices else "general")


def get_notification_content(key, school_id=None, **kwargs):
    title = get_setting(f"notify_{key}_title", school_id, "")
    message_tpl = get_setting(f"notify_{key}_message", school_id, "")
    message = message_tpl.format(**kwargs) if kwargs and message_tpl else message_tpl
    type_map = {"monthly": "evaluation", "daily": "evaluation", "behavior": "behavior", "exam": "grade"}
    ntype = get_notification_type_code(type_map.get(key, "general"), school_id)
    return title, message, ntype


def get_exam_types_with_options(school_id=None):
    raw = get_setting("exam_types_with_options", school_id, "mcq")
    codes = {c.strip() for c in str(raw).split(",") if c.strip()}
    return [code for code, _ in get_config_choices("exam_question_type", school_id) if code in codes]


def get_reading_overall_aspect_code(school_id=None):
    for code, _ in get_reading_aspects(school_id):
        if code == "overall_rating":
            return code
    aspects = get_reading_aspects(school_id)
    return aspects[-1][0] if aspects else "overall_rating"


def parse_reading_aspect_scores(record):
    import json as _json
    if getattr(record, "aspect_scores", None):
        try:
            return _json.loads(record.aspect_scores)
        except (_json.JSONDecodeError, TypeError):
            pass
    data = {}
    for col in READING_LEGACY_COLUMNS:
        val = getattr(record, col, None)
        if val:
            data[col] = val
    return data


def build_reading_assessment(student, teacher, form):
    """Create ReadingAssessment from POST form using dynamic reading_aspect config."""
    from datetime import date as _date
    from app.models.evaluation import ReadingAssessment
    import json as _json
    sid = student.school_id
    aspects = get_reading_aspects(sid)
    scores = {code: form.get(code) for code, _ in aspects if form.get(code)}
    record = ReadingAssessment(
        student_id=student.id,
        teacher_id=teacher.id,
        school_id=sid,
        date=_date.today(),
        read_lesson=form.get("read_lesson") == "on",
        notes=form.get("notes"),
    )
    if scores:
        record.aspect_scores = _json.dumps(scores, ensure_ascii=False)
    for code in READING_LEGACY_COLUMNS:
        if code in scores and hasattr(record, code):
            setattr(record, code, scores[code])
    return record


def get_recommendation_templates(school_id=None):
    return {
        "follow_up": get_setting("rec_follow_up", school_id, "يُنصح بمتابعة:"),
        "improvement_plan": get_setting("rec_improvement_plan", school_id, "وضع خطة تحسين أسبوعية مع المسؤول."),
        "complete_eval": get_setting("rec_complete_eval", school_id, "أكمل التقييم الشهري لإنشاء التوصيات."),
        "good_performance": get_setting("rec_good_performance", school_id, "أداء جيد — استمر في المتابعة والتشجيع."),
    }


def get_demo_accounts(school_id=None):
    from app.models import User
    password = get_setting("demo_login_password", school_id, "admin123")
    users = (
        User.query.filter(User.username.in_(DEMO_USERNAMES), User.is_active == True)  # noqa: E712
        .order_by(User.id)
        .all()
    )
    return [
        {
            "username": u.username,
            "password": password,
            "role": get_role_display(u.role.name, school_id) if u.role else "",
        }
        for u in users
    ]


def get_default_exam_question_type(school_id=None):
    choices = get_config_choices("exam_question_type", school_id)
    return choices[0][0] if choices else "mcq"


def _find_active_kpi(code, school_id=None):
    q = KPI.query.filter_by(code=code, is_active=True)
    if school_id:
        rows = q.filter((KPI.school_id == school_id) | (KPI.school_id.is_(None))).all()
        for row in rows:
            if row.school_id == school_id:
                return row
        return rows[0] if rows else None
    return q.filter(KPI.school_id.is_(None)).first()


def get_kpi_display_source(kpi_code, school_id=None):
    kpi = _find_active_kpi(kpi_code, school_id)
    if kpi:
        return kpi.name_ar
    return KPI_SOURCE_DESCRIPTIONS.get(kpi_code, kpi_code)


def get_monthly_scale_summary(school_id=None):
    ratings = get_monthly_rating_choices(school_id)
    if not ratings:
        return "1–5"
    numeric = [int(c[0]) for c in ratings if str(c[0]).isdigit()]
    if numeric:
        return f"{min(numeric)}–{max(numeric)}"
    return "–".join(c[0] for c in ratings)


def _merged_config_section_labels(school_id=None):
    """Known option-type labels plus any types stored in the database."""
    labels = dict(CONFIG_SECTION_LABELS)
    query = ConfigOption.query.with_entities(ConfigOption.option_type).distinct()
    if school_id:
        query = query.filter(
            (ConfigOption.school_id == school_id) | (ConfigOption.school_id.is_(None))
        )
    else:
        query = query.filter(ConfigOption.school_id.is_(None))
    for (opt_type,) in query:
        if opt_type and opt_type not in labels:
            labels[opt_type] = opt_type.replace("_", " ")
    return labels


def get_config_section_labels(school_id=None):
    return _merged_config_section_labels(school_id)


def get_admin_config_sections(school_id=None):
    """All config option groups for the admin accordion."""
    labels = _merged_config_section_labels(school_id)
    sections = {
        key: get_config_options(key, school_id)
        for key in sorted(labels, key=lambda k: labels[k])
    }
    return sections, labels


def get_setting_category_labels():
    return dict(SETTING_CATEGORY_LABELS)


def get_rating_levels(school_id=None, scale_type="qualitative"):
    return _rating_query(school_id, scale_type)


def infer_setting_value_type(key, value):
    """Guess value_type for a new platform setting."""
    if key in DEFAULT_SETTINGS:
        seed = DEFAULT_SETTINGS[key][0]
        if seed in ("true", "false"):
            return "bool"
        if isinstance(seed, str) and seed.isdigit():
            return "int"
        if isinstance(seed, str) and seed.startswith("{"):
            return "json"
    text = str(value or "")
    if text in ("true", "false"):
        return "bool"
    if text.isdigit():
        return "int"
    if text.startswith("{") or text.startswith("["):
        return "json"
    return "string"


def save_settings_bulk(form_data, school_id=None):
    """Update platform settings from admin advanced tab (keys: ps_<id>)."""
    updated = 0
    for key, val in form_data.items():
        if not key.startswith("ps_"):
            continue
        try:
            setting_id = int(key[3:])
        except ValueError:
            continue
        row = PlatformSetting.query.get(setting_id)
        if not row:
            continue
        if row.school_id is not None and row.school_id != school_id:
            continue
        row.value = val
        updated += 1
    if updated:
        db.session.commit()
    return updated


def get_monthly_strength_threshold(school_id=None):
    return int(get_setting("monthly_strength_min", school_id, 4))


def get_monthly_weakness_threshold(school_id=None):
    return int(get_setting("monthly_weakness_max", school_id, 2))


def get_gender_choices(school_id=None):
    return get_config_choices("gender", school_id)


def get_gender_label(code, school_id=None):
    return get_config_map("gender", school_id).get(code, code or "—")


def get_behavior_type_scores(school_id=None):
    scores = dict(BEHAVIOR_TYPE_SCORES)
    for opt in get_config_options("behavior_type", school_id):
        if opt.metadata_json:
            try:
                meta = json.loads(opt.metadata_json)
                if "score" in meta:
                    scores[opt.code] = float(meta["score"])
            except (json.JSONDecodeError, TypeError):
                pass
    return scores


def get_kpi_source_options(school_id=None):
    """Dynamic KPI data sources from config, active KPIs, and evaluation criteria."""
    sources = {}
    for opt in get_config_options("kpi_data_source", school_id):
        sources[opt.code] = opt.name_ar

    kpi_query = KPI.query.filter_by(is_active=True)
    if school_id:
        kpi_query = kpi_query.filter(
            (KPI.school_id == school_id) | (KPI.school_id.is_(None))
        )
    for kpi in kpi_query.order_by(KPI.name_ar).all():
        sources.setdefault(kpi.code, kpi.name_ar)

    query = EvaluationCriterion.query.filter_by(is_active=True)
    if school_id:
        items = query.filter_by(school_id=school_id).all()
        if not items:
            items = query.filter_by(school_id=None).all()
    else:
        items = query.filter_by(school_id=None).all()
    for criterion in items:
        if criterion.kpi_source:
            sources.setdefault(
                criterion.kpi_source,
                get_kpi_source_description(criterion.kpi_source, school_id),
            )
    return sorted(sources.items(), key=lambda x: x[1])


def get_all_settings_grouped(school_id=None):
    """All platform settings for admin display."""
    rows = PlatformSetting.query.filter(
        (PlatformSetting.school_id == school_id) | (PlatformSetting.school_id.is_(None))
    ).order_by(PlatformSetting.category, PlatformSetting.key).all()
    grouped = {}
    for s in rows:
        grouped.setdefault(s.category or "general", []).append(s)
    return grouped


def get_default_monthly_rating(school_id=None):
    choices = get_monthly_rating_choices(school_id)
    for code, _ in choices:
        if code == "3":
            return "3"
    return choices[len(choices) // 2][0] if choices else "3"


def get_self_assessment_items(school_id=None):
    return get_config_options("self_assessment", school_id)


def get_reading_aspects(school_id=None):
    return get_config_choices("reading_aspect", school_id)


def get_attendance_status_map(school_id=None):
    statuses = get_attendance_statuses(school_id)
    return {
        s.code: {"name_ar": s.name_ar, "badge_class": s.badge_class or "secondary"}
        for s in statuses
    }


def get_default_rating_code(school_id=None):
    choices = get_rating_choices(school_id)
    if len(choices) >= 2:
        return choices[1][0]
    return choices[0][0] if choices else "good"


def get_default_attendance_status(school_id=None):
    statuses = get_attendance_statuses(school_id)
    for s in statuses:
        if s.counts_as_present:
            return s.code
    return statuses[0].code if statuses else "present"


def get_kpi_source_description(code, school_id=None):
    kpi = _find_active_kpi(code, school_id)
    if kpi:
        return kpi.description or kpi.name_ar
    for opt in get_config_options("kpi_data_source", school_id):
        if opt.code == code:
            return opt.name_ar
    return KPI_SOURCE_DESCRIPTIONS.get(code, "بيانات مرتبطة بالمعايير")


def _cast(value, value_type):
    if value_type == "int":
        return int(value)
    if value_type == "float":
        return float(value)
    if value_type == "bool":
        return value.lower() in ("true", "1", "yes")
    if value_type == "json":
        return json.loads(value)
    return value
