"""Seed content used only to populate PlatformSetting / ConfigOption on first run."""

import json

# Survey frequency & choices — seeded into ConfigOption, not used at runtime directly.
SURVEY_FREQUENCY_SEED = [
    ("always", "دائما"),
    ("usually", "غالبا"),
    ("sometimes", "أحيانا"),
    ("rarely", "نادرا"),
]

SURVEY_WEEKLY_MEETINGS_SEED = [
    ("one", "لقاء واحد (اذكر السبب أدناه)"),
    ("two", "لقائين"),
    ("other", "أخرى"),
]

EDUCATION_STAGE_SEED = [
    ("primary", "الابتدائي"),
    ("middle", "الإعدادي"),
    ("secondary", "الثانوي"),
]

ARABIC_MONTHS_SEED = [
    ("1", "يناير"), ("2", "فبراير"), ("3", "مارس"), ("4", "أبريل"),
    ("5", "مايو"), ("6", "يونيو"), ("7", "يوليو"), ("8", "أغسطس"),
    ("9", "سبتمبر"), ("10", "أكتوبر"), ("11", "نوفمبر"), ("12", "ديسمبر"),
]

FAMILY_SURVEY_FIELDS_SEED = [
    {"fields": "family_name", "label": "الاسم الكريم"},
    {"fields": "stage_primary,stage_middle,stage_secondary", "label": "أولادك في المرحلة الدراسية"},
    {"fields": "has_regular_family_meeting", "label": "هل هناك برنامج مستمر للقاء الأسري في بيتك؟"},
    {"fields": "weekly_meetings_count", "label": "عدد اللقاءات الأسبوعية"},
    {"fields": "weekly_meetings_one_reason", "label": "سبب لقاء واحد"},
    {"fields": "weekly_meetings_other", "label": "أخرى"},
    {"fields": "family_meeting_notes", "label": "ملاحظات حول التفاعل والاستفادة"},
    {"fields": "received_curriculum_book", "label": "هل وصلك كتاب منهج التربية؟"},
    {"fields": "read_curriculum_book", "label": "هل قرأته؟"},
    {"fields": "studied_curriculum_at_home", "label": "هل تدارستم الكتاب في البيت؟"},
    {"fields": "curriculum_notes", "label": "ملاحظاتك حول الاستفادة من المقرر"},
    {"fields": "hadith_at_home", "label": "هل يتم أخذ مقرر الحديث للأولاد في المنزل؟"},
    {"fields": "fiqh_at_home", "label": "هل يتم أخذ مقرر الفقه للأولاد في المنزل؟"},
    {"fields": "curricula_obstacles", "label": "هل توجد عوائق أو عقبات؟"},
    {"fields": "listens_riyadh_saliheen", "label": "هل تستمع مع أولادك إلى رياض الصالحين بشكل مستمر؟"},
    {"fields": "riyadh_progress", "label": "إلى أي تسجيل وصلت؟"},
    {"fields": "received_approved_films", "label": "هل وصلتك النسخة الصحيحة للأفلام المسموحة؟"},
    {"fields": "watches_approved_only", "label": "هل تلتزم بمشاهدة الأفلام المسموحة فقط؟"},
    {"fields": "outdoor_entertainment", "label": "هل يوجد برنامج ترفيهي للأولاد خارج البيت؟"},
]

TEACHER_SURVEY_FIELDS_SEED = [
    {"fields": "attendance_punctuality", "label": "هل تلتزم بحضور المواعيد الأسبوعية في وقتها؟"},
    {"fields": "lesson_preparation", "label": "هل تقوم بتحضير المادة الدراسية بشكل جيد قبل اللقاء؟"},
    {"fields": "main_obstacles", "label": "ما هي أهم العقبات التي تحول دون تحقيق تلك الفائدة؟"},
    {"fields": "student_punctuality", "label": "ما هو تقييمك لحضور تلاميذك الدروس في الوقت المحدد؟"},
    {"fields": "student_preparation_percentage", "label": "ما هي نسبة تلاميذك الذين يقومون بتحضير الدرس؟"},
    {"fields": "student_comprehension", "label": "ما هو تقييمك لمدى استيعاب تلاميذك لمحتوى المادة؟"},
    {"fields": "student_notes", "label": "ملاحظات تجاه مجموعة أو شخصية من تلاميذك"},
    {"fields": "family_role_rating", "label": "كيف هو تقييمك لدور الأسرة في أداء تلاميذك؟"},
    {"fields": "family_role_message", "label": "ما هي رسالتك للآباء والأمهات؟"},
    {"fields": "session_suggestions", "label": "ما هي اقتراحاتك لتحسين هذه الجلسات الأسبوعية؟"},
]

PROGRAM_SURVEY_SECTIONS_SEED = [
    {
        "code": "individual",
        "title": "المجال الفردي",
        "subtitle": "من خلال مسؤولي المتابعة في الأحياء",
        "fields": [
            ["has_daily_individual_program", "هل لديك برنامج يومي فردي؟"],
            ["daily_includes_quran_dhikr", "تحديد حزب يومي من القرآن مع الذكر والاستغفار والدعاء والصلاة على النبي ﷺ"],
            ["program_regular_scheduled", "هل برنامجك منتظم ومجدول؟"],
            ["persistence_and_makeup", "هل الأصل فيه المداومة، وإذا فاتتك فقرة هل تقضيها على الكيفية المذكورة في تقرير اللجنة التربوية؟"],
        ],
    },
    {
        "code": "binary",
        "title": "المجال الثاني: الثنائيات",
        "subtitle": "من خلال مسؤولي المتابعة في الأحياء",
        "fields": [
            ["binary_meeting_biweekly", "هل ينعقد لقاء الثنائيات مرة كل أسبوعين؟"],
            ["binary_meeting_full_agenda", "هل بنود اللقاء تشمل الحديث حول التطبيق والتفاعل مع دروس اللقاءات الأسبوعية (قرآن، تربية إيمانية، تربية أسرية، وغيرها)، ومشاركة المشاعر والتعاون على تجاوز العوائق والتذكير بالله وباليوم الآخر؟"],
            ["binary_reform_quarterly", "هل تُعاد تشكيل الثنائيات كل ثلاثة أشهر، بحيث تُقام دورة الثنائيات أربع مرات خلال السنة؟"],
        ],
    },
    {
        "code": "during_meeting",
        "title": "المجال الثالث: أثناء اللقاء",
        "subtitle": "مسؤول المتابعة في الحي من خلال مسؤولي المجموعات — تحويل اللقاءات إلى لقاءات تربوية للتغيير",
        "fields": [
            ["go_during_punctual_attendance", "الحضور الدائم في الوقت المحدد لهذه اللقاءات"],
            ["go_during_good_preparation", "التحضير الجيد الذي لا يتم قراءة الموضوع مرة واحدة"],
            ["go_during_programs_on_time", "إيصال البرامج في وقتها المحدد دون تأخير"],
            ["go_during_summarize_points", "تلخيص النقاط العملية الأساسية التي يُراد تحويلها إلى تطبيق"],
            ["go_during_evaluate_meeting", "تقييم اللقاء بعد انتهائه للوقوف على نقاط القوة والقصور"],
            ["go_during_extended_monthly_meeting", "هل تم تطويل اللقاء الشهري من ظهر الجمعة حتى الساعة 9:30 مساءً يوم السبت؟"],
        ],
    },
    {
        "code": "outside_meeting",
        "title": "مسؤول المجموعة — خارج اللقاء",
        "subtitle": "مسؤول المتابعة في الحي من خلال مسؤولي المجموعات",
        "fields": [
            ["go_outside_educate_members", "هل يسهم في تثقيف وتربية أفراد مجموعته؟"],
            ["go_outside_close_living", "هل يعيش مع إخوانه معايشة قريبة؟"],
            ["go_outside_reminder_meetings", "هل يعقد لقاءات تذكيرية مع المقصرين؟"],
            ["go_outside_special_care_difficulties", "هل يعطي عناية خاصة للإخوة الذين لديهم صعوبات لغوية أو ثقافية؟"],
        ],
    },
    {
        "code": "oasis",
        "title": "دور مسؤولي الواحات ومسؤولي المجموعة",
        "subtitle": "مسؤول المتابعة في الحي من خلال مسؤولي الواحات",
        "fields": [
            ["oasis_weekly_meeting", "هل لهم لقاءٌ دوريٌّ مرّةً كلّ أسبوع؟"],
            ["oasis_assess_program_benefit", "هل يقيمون مدى استفادة الإخوة من البرامج التربوية المقدَّمة؟"],
        ],
    },
    {
        "code": "foundational",
        "title": "البرنامج الدراسي التأسيسي",
        "subtitle": "مسؤولي المتابعة في الحي من خلال إدارة الحي — للشباب والشابات الذين أنهوا السنة الأولى الجامعية ولم يلتحقوا بالبرنامج العام",
        "fields": [
            ["foundational_monthly_faith_meeting_week4", "هل تم عقد لقاء إيماني شهري موسع في الأسبوع الرابع؟"],
        ],
    },
    {
        "code": "uncles",
        "title": "جلسات الأعمام",
        "subtitle": None,
        "fields": [
            ["uncle_platforms_created", "هل تم إنشاء منصات دورية للأعمام؟"],
        ],
    },
    {
        "code": "latecomers",
        "title": "التعامل مع المتأخرين عن الجلسات التربوية",
        "subtitle": "الالتزام التام بالمواعيد والجلسات — موعد الجلسة 7:30 مساءً، من لم يحضر عند 7:45 يُمنع من الدخول، من تغيب ثلاث جلسات متتالية يلتقي بإدارة الحي",
        "fields": [
            ["latecomers_commitment_enforced", "هل يُطبَّق الالتزام التام بالمواعيد والجلسات؟"],
            ["latecomers_session_starts_730", "هل موعد الجلسة تمام الساعة 7:30 مساءً؟"],
            ["latecomers_entry_bar_after_745", "هل يُمنع دخول من لم يكن حاضراً عند الساعة 7:45؟"],
            ["latecomers_three_absences_rule", "هل يُطبَّق منع حضور من تغيب ثلاث جلسات متتالية حتى يلتقي بإدارة الحي؟"],
        ],
    },
]

NAV_LABELS_SEED = {
    "dashboard": "لوحة التحكم",
    "super_admin": "المشرف الأعلى",
    "schools": "المدارس",
    "students": "الطلاب",
    "teachers": "المعلمون",
    "attendance": "الحضور",
    "evaluations": "المحاسبة",
    "self_assess": "محاسبتي",
    "questionnaires": "الاستبيانات",
    "followup_surveys": "المتابعة الشهرية",
    "exams": "الاختبارات",
    "kpi": "مؤشرات الأداء",
    "more": "المزيد",
    "reading": "القراءة",
    "behavior": "السلوك",
    "ai_assistant": "المساعد الذكي",
    "reports": "التقارير",
    "admin": "إعدادات النظام",
    "notifications": "الإشعارات",
    "logout": "تسجيل الخروج",
    "profile": "الملف الشخصي",
}

REGISTRATION_SECTION_LABELS_SEED = {
    "personal": "المعلومات الشخصية",
    "location": "الموقع",
    "account": "حساب الدخول",
    "academic": "التصنيف الدراسي",
}


def dumps_json(data):
    return json.dumps(data, ensure_ascii=False)
