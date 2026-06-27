"""Dynamic flash / system messages — editable from admin without code changes."""

import json

from flask import flash

from app.services.config_service import get_setting, set_setting
from app.services.content_seeds import dumps_json

SETTING_KEY = "flash_messages_json"

MESSAGES_SEED = {
    # Permissions
    "permission_denied": "ليس لديك صلاحية.",
    "permission_denied_page": "ليس لديك صلاحية للوصول إلى هذه الصفحة.",
    "permission_edit_student": "ليس لديك صلاحية لتعديل هذا الطالب.",
    "permission_edit_profile": "ليس لديك صلاحية لتعديل هذا الملف.",
    "permission_attendance_group": "ليس لديك صلاحية لتسجيل حضور هذه المجموعة.",
    "permission_questionnaire": "ليس لديك صلاحية لهذا الاستبيان.",
    "permission_questionnaire_edit": "ليس لديك صلاحية التعديل.",
    # Auth
    "auth_login_invalid": "اسم المستخدم أو كلمة المرور غير صحيحة.",
    "auth_login_inactive": "حسابك غير مفعّل. تواصل مع المشرف الأعلى.",
    "auth_login_unverified": "يرجى تفعيل بريدك الإلكتروني قبل تسجيل الدخول.",
    "auth_login_no_email": "لا يوجد بريد إلكتروني مرتبط بالحساب. تواصل مع المشرف الأعلى.",
    "auth_otp_sent": "تم إرسال رمز التحقق (OTP) إلى بريدك الإلكتروني.",
    "auth_otp_send_failed": "تعذّر إرسال رمز التحقق. تحقق من إعدادات البريد أو تواصل مع الدعم.",
    "auth_otp_session_expired": "انتهت جلسة التحقق. سجّل الدخول مرة أخرى.",
    "auth_otp_invalid": "رمز التحقق غير صحيح أو منتهٍ.",
    "auth_welcome": "مرحباً {name}",
    "auth_verify_link_invalid": "رابط التفعيل غير صالح أو منتهٍ.",
    "auth_email_verified": "تم تفعيل بريدك الإلكتروني. بعد تفعيل حسابك من المشرف الأعلى يمكنك تسجيل الدخول.",
    "auth_resend_blocked": "لا يمكن إعادة إرسال رابط التفعيل.",
    "auth_user_not_found": "المستخدم غير موجود.",
    "auth_verification_sent": "تم إرسال رابط التفعيل إلى بريدك.",
    "auth_logout": "تم تسجيل الخروج بنجاح.",
    "auth_account_inactive": "حسابك غير مفعّل أو البريد غير مُحقَّق. تواصل مع المشرف الأعلى.",
    "auth_no_student_profile": "لا يوجد ملف طالب مرتبط بحسابك. يرجى التواصل مع مدير المدرسة لربط الحساب.",
    # Tenants / licenses
    "license_request_missing_fields": "يرجى تعبئة جميع الحقول المطلوبة.",
    "license_request_submitted": "تم إرسال طلب الترخيص. سيتواصل معك فريق نيتريش قريباً.",
    "license_expired": "انتهت صلاحية ترخيص مؤسستكم. تواصل مع مسؤول المنصة أو اطلب تجديد الترخيص.",
    "license_suspended": "تم تعليق ترخيص مؤسستكم. تواصل مع مسؤول المنصة.",
    "license_approved": "تمت الموافقة على طلب الترخيص.",
    "license_rejected": "تم رفض طلب الترخيص.",
    "tenant_updated": "تم تحديث بيانات المستأجر.",
    "tenant_license_updated": "تم تحديث الترخيص.",
    # Admin
    "admin_school_selected": "تم اختيار المدرسة.",
    "admin_settings_saved": "تم حفظ الإعدادات.",
    "admin_registration_saved": "تم حفظ إعدادات حقول التسجيل.",
    "admin_criterion_added": "تم إضافة المعيار.",
    "admin_criterion_updated": "تم تحديث المعيار.",
    "admin_rating_added": "تم إضافة مستوى التقييم.",
    "admin_rating_updated": "تم تحديث مستوى التقييم.",
    "admin_attendance_time_saved": "تم حفظ إعدادات وقت الحضور.",
    "admin_attendance_status_updated": "تم تحديث حالة الحضور.",
    "admin_attendance_status_added": "تم إضافة حالة الحضور.",
    "admin_attendance_weekly_saved": "تم حفظ حدود الحصص الأسبوعية.",
    "admin_kpi_updated": "تم تحديث المؤشر.",
    "admin_kpi_added": "تم إضافة المؤشر.",
    "admin_kpi_toggled": "تم تغيير حالة المؤشر.",
    "admin_kpi_deleted": "تم حذف المؤشر.",
    "admin_kpi_deactivated_has_scores": "المؤشر مرتبط بدرجات — تم تعطيله بدلاً من الحذف.",
    "admin_kpi_weights_saved": "تم حفظ أوزان المؤشرات.",
    "admin_kpi_period_saved": "تم حفظ إعدادات فترات KPI.",
    "admin_option_added": "تم إضافة الخيار.",
    "admin_option_updated": "تم تحديث الخيار.",
    "admin_advanced_saved": "تم حفظ {count} إعداد.",
    "admin_setting_added": "تم إضافة الإعداد.",
    "admin_content_labels_saved": "تم حفظ تسميات التنقل والصفحات.",
    "admin_school_provisioned": "تم تهيئة إعدادات المدرسة.",
    "admin_messages_saved": "تم حفظ رسائل النظام.",
    "admin_surveys_saved": "تم حفظ أسئلة الاستبيانات.",
    # Students
    "student_updated": "تم تحديث بيانات الطالب.",
    "student_self_updated": "تم تحديث بياناتك.",
    "student_deactivated_bulk": "تم تعطيل {count} طالب/طلاب.",
    "student_activated_bulk": "تم تفعيل {count} طالب/طلاب.",
    "student_already_inactive": "الطالب معطّل مسبقاً.",
    "student_deactivated": "تم تعطيل الطالب. لن يظهر في القوائم النشطة.",
    "student_activated": "تم تفعيل الطالب.",
    "student_parent_linked": "تم ربط ولي الأمر بالطالب.",
    "student_parent_unlinked": "تم إلغاء الربط.",
    "student_registered": "تم تسجيل الطالب {name} بنجاح.",
    "student_register_account_info": "إنشاء حسابات الدخول متاح فقط للمشرف الأعلى.",
    "student_register_invalid_class": "الفصل المحدد غير صالح لهذا المستوى والمدرسة.",
    "student_id_taken": "رقم الطالب مستخدم مسبقاً.",
    # Teachers
    "teacher_no_profile": "لا يوجد معلم مرتبط.",
    "teacher_employee_id_taken": "الرقم الوظيفي مستخدم.",
    "teacher_registered": "تم تسجيل المعلم. لإنشاء حساب دخول، يجب على المشرف الأعلى إنشاء مستخدم وربطه بالمعلم.",
    "teacher_updated": "تم تحديث بيانات المعلم.",
    "teacher_already_inactive": "المعلم معطّل مسبقاً.",
    "teacher_deactivated": "تم تعطيل المعلم. لن يظهر في القائمة ولن يتمكن من تسجيل الدخول.",
    "teacher_activated": "تم تفعيل المعلم.",
    "teacher_assignment_exists": "هذا التعيين موجود مسبقاً.",
    "teacher_class_assigned": "تم تعيين الفصل للمعلم.",
    "teacher_assignment_removed": "تم إزالة التعيين.",
    # Schools
    "school_registered": "تم تسجيل المدرسة بنجاح مع الإعدادات الافتراضية.",
    "school_code_taken": "رمز المدرسة مستخدم مسبقاً.",
    "school_updated": "تم تحديث المدرسة.",
    "school_state_changed": "تم {state} المدرسة.",
    "school_delete_code_wrong": "رمز التأكيد غير صحيح. اكتب رمز المدرسة للحذف النهائي.",
    "school_deleted": "تم حذف المدرسة «{name}» نهائياً.",
    "grade_added": "تم إضافة المستوى الدراسي.",
    "class_added": "تم إضافة الفصل.",
    "subject_added": "تم إضافة المادة.",
    "year_added": "تم إضافة السنة الدراسية.",
    "grade_updated": "تم تحديث الصف.",
    "grade_delete_blocked": "لا يمكن حذف صف مرتبط بفصول.",
    "grade_deleted": "تم حذف الصف.",
    "class_updated": "تم تحديث الفصل.",
    "class_delete_blocked": "لا يمكن حذف فصل يضم طلاباً.",
    "class_deleted": "تم حذف الفصل.",
    "subject_updated": "تم تحديث المادة.",
    "subject_delete_blocked": "لا يمكن حذف المادة: {reason}.",
    "subject_deleted": "تم حذف المادة.",
    "year_updated": "تم تحديث السنة الدراسية.",
    "year_delete_blocked": "لا يمكن حذف سنة مرتبطة بفصول.",
    "year_deleted": "تم حذف السنة الدراسية.",
    # Follow-up surveys
    "survey_family_saved_complete": "تم حفظ استبيان متابعة الأسرة بالكامل.",
    "survey_family_saved_partial": "تم حفظ الإجابات ({answered} من {total} سؤال). يمكنك إكمال الباقي لاحقاً.",
    "survey_teacher_saved_complete": "تم حفظ الاستبيان الشهري للمعلم بالكامل.",
    "survey_teacher_saved_partial": "تم حفظ الإجابات ({answered} من {total} سؤال). يمكنك إكمال الباقي لاحقاً.",
    "survey_program_saved_complete": "تم حفظ متابعة البرنامج التربوي بالكامل.",
    "survey_program_saved_partial": "تم حفظ الإجابات ({answered} من {total}). يمكنك إكمال الباقي لاحقاً.",
    "survey_student_program_saved_complete": "تم حفظ متابعة البرنامج التربوي للطالب بالكامل.",
    "survey_student_program_saved_partial": "تم حفظ الإجابات ({answered} من {total}). يمكنك إكمال الباقي لاحقاً.",
    # Evaluations
    "eval_monthly_saved": "تم حفظ التقييم الشهري.",
    "eval_daily_saved": "تم حفظ تقييم المحاسبة اليومي.",
    "eval_self_saved": "تم حفظ محاسبتك الذاتية.",
    "eval_reading_saved": "تم تسجيل تقييم القراءة.",
    "eval_behavior_saved": "تم تسجيل السلوك.",
    # Exams
    "exam_created": "تم إنشاء الاختبار.",
    "exam_not_published": "الاختبار غير منشور.",
    "exam_already_taken": "لقد أجبت على هذا الاختبار مسبقاً.",
    "exam_submitted": "تم تسليم الاختبار. درجتك: {pct}%",
    "exam_graded": "تم تصحيح الاختبار.",
    # Questionnaires
    "questionnaire_created": "تم إنشاء الاستبيان.",
    "questionnaire_updated": "تم تحديث الاستبيان.",
    "questionnaire_status_updated": "تم تحديث حالة الاستبيان.",
    "questionnaire_answer_required": "يرجى الإجابة على: {question}",
    "questionnaire_submitted": "تم إرسال إجاباتك.",
    # KPI
    "kpi_added": "تم إضافة مؤشر الأداء.",
    "kpi_weights_updated": "تم تحديث الأوزان.",
    "kpi_status_updated": "تم تحديث حالة المؤشر.",
    "kpi_recalculated": "تم تحديث مؤشرات الأداء ديناميكياً.",
    "kpi_select_school": "حدد مدرسة أولاً.",
    "kpi_students_updated": "تم تحديث مؤشرات {count} طالب.",
    # Attendance
    "attendance_saved": "تم تسجيل الحضور بنجاح.",
    "attendance_entry_blocked": "تم منع تسجيل حضور {count} طالب — يتطلب موافقة الإدارة.",
    "attendance_entry_approved": "تم السماح بدخول الطالب للحصة.",
    "attendance_teacher_weekly_limit": "تجاوزت الحد الأسبوعي لحصص المعلم.",
    # Users
    "users_create_super_admin_only": "إنشاء المستخدمين متاح فقط للمشرف الأعلى من لوحة المشرف الأعلى.",
    "users_create_denied": "ليس لديك صلاحية إنشاء المستخدمين.",
    "users_created": "تم إنشاء المستخدم وإرسال رابط تفعيل البريد.",
    "users_created_admin": "تم إنشاء المستخدم بدور مسؤول: {role}.",
    "users_assigned_admin": "تم تعيين دور المسؤول: {role}.",
    "users_cannot_deactivate_self": "لا يمكن تعطيل حسابك.",
    "users_updated": "تم تحديث المستخدم.",
    "users_status_updated": "تم تحديث حالة المستخدم.",
    "users_role_not_allowed": "لا يمكن تعيين هذا الدور.",
    # Super admin
    "sa_user_created": "تم إنشاء المستخدم وإرسال رابط تفعيل البريد. فعّل الحساب من قائمة المستخدمين.",
    "sa_user_created_profiles": "تم إنشاء المستخدم مع الملفات: {profiles}.",
    "sa_user_updated": "تم تحديث المستخدم.",
    "sa_username_taken": "اسم المستخدم موجود.",
    "sa_verification_sent": "تم إرسال رابط تفعيل البريد.",
    "sa_cannot_deactivate_self": "لا يمكن تعطيل حسابك.",
    "sa_activate_requires_email": "لا يمكن تفعيل الحساب قبل تفعيل البريد الإلكتروني.",
    "sa_cannot_delete_self": "لا يمكن حذف حسابك.",
    "sa_user_deleted": "تم حذف المستخدم.",
    "identity_backfill_done": "تم توليد {assigned} رقم هوية. المتبقي بدون رقم: {remaining}.",
    "identity_backfill_none": "جميع السجلات لديها أرقام هوية بالفعل.",
    "sa_permissions_updated": "تم تحديث الصلاحيات.",
    "sa_role_id_invalid": "معرّف الدور يجب أن يبدأ بحرف ويحتوي أحرفاً إنجليزية صغيرة وأرقام و _ فقط.",
    "sa_role_id_reserved": "هذا المعرّف محجوز لدور نظامي.",
    "sa_role_name_required": "اسم الدور بالعربية مطلوب.",
    "sa_role_id_taken": "معرّف الدور موجود مسبقاً.",
    "sa_role_created": "تم إنشاء دور «{name}».",
    "sa_role_system_delete": "لا يمكن حذف الأدوار النظامية.",
    "sa_role_has_users": "لا يمكن حذف دور مرتبط بمستخدمين.",
    "sa_role_deleted": "تم حذف دور «{name}».",
    "sa_role_name_empty": "اسم الدور مطلوب.",
    "sa_role_updated": "تم تحديث دور «{name}».",
    "sa_school_status_updated": "تم تحديث حالة المدرسة.",
    "sa_schools_provisioned": "تم تهيئة {count} مدرسة.",
    "sa_settings_updated": "تم تحديث الإعدادات العامة.",
    "sa_permissions_synced": "تم مزامنة الصلاحيات من سجل النظام.",
    "reg_error_name_ar_required": "حقل الاسم بالعربية مطلوب.",
    "reg_error_field_required": "حقل {label} مطلوب.",
    "reg_error_school_required": "حقل المدرسة مطلوب.",
    "reg_error_grade_required": "حقل المستوى الدراسي مطلوب.",
    "reg_error_class_required": "حقل الفصل مطلوب.",
    "reg_error_username_required": "اسم المستخدم مطلوب لإنشاء حساب.",
    "reg_error_password_required": "كلمة المرور مطلوبة لإنشاء حساب.",
    "reg_error_password_with_username": "كلمة المرور مطلوبة عند إدخال اسم مستخدم.",
}

MESSAGE_GROUPS = {
    "الصلاحيات": [
        "permission_denied", "permission_denied_page", "permission_edit_student",
        "permission_edit_profile", "permission_attendance_group",
        "permission_questionnaire", "permission_questionnaire_edit",
    ],
    "المصادقة": [
        "auth_login_invalid", "auth_login_inactive", "auth_login_unverified",
        "auth_login_no_email", "auth_otp_sent", "auth_otp_send_failed", "auth_otp_session_expired",
        "auth_otp_invalid", "auth_welcome", "auth_verify_link_invalid",
        "auth_email_verified", "auth_resend_blocked", "auth_user_not_found",
        "auth_verification_sent", "auth_logout", "auth_account_inactive",
        "auth_no_student_profile",
    ],
    "الإدارة": [
        "admin_school_selected", "admin_settings_saved", "admin_registration_saved",
        "admin_criterion_added", "admin_criterion_updated", "admin_rating_added",
        "admin_rating_updated", "admin_attendance_time_saved",
        "admin_attendance_status_updated", "admin_attendance_status_added",
        "admin_attendance_weekly_saved",
        "admin_kpi_updated", "admin_kpi_added", "admin_kpi_toggled",
        "admin_kpi_deleted", "admin_kpi_deactivated_has_scores",
        "admin_kpi_weights_saved", "admin_kpi_period_saved",
        "admin_option_added", "admin_option_updated",
        "admin_advanced_saved", "admin_setting_added", "admin_content_labels_saved",
        "admin_school_provisioned", "admin_messages_saved", "admin_surveys_saved",
    ],
    "الطلاب": [
        "student_updated", "student_self_updated", "student_deactivated_bulk",
        "student_activated_bulk", "student_already_inactive", "student_deactivated",
        "student_activated", "student_parent_linked", "student_parent_unlinked",
        "student_registered", "student_register_account_info",
        "student_register_invalid_class", "student_id_taken",
    ],
    "المعلمون": [
        "teacher_no_profile", "teacher_employee_id_taken", "teacher_registered",
        "teacher_updated", "teacher_already_inactive", "teacher_deactivated",
        "teacher_activated", "teacher_assignment_exists", "teacher_class_assigned",
        "teacher_assignment_removed",
    ],
    "المدارس": [
        "school_registered", "school_code_taken", "school_updated",
        "school_state_changed", "school_delete_code_wrong", "school_deleted",
        "grade_added", "class_added", "subject_added", "year_added",
        "grade_updated", "grade_delete_blocked", "grade_deleted",
        "class_updated", "class_delete_blocked", "class_deleted",
        "subject_updated", "subject_delete_blocked", "subject_deleted",
        "year_updated", "year_delete_blocked", "year_deleted",
    ],
    "المتابعة الشهرية": [
        "survey_family_saved_complete", "survey_family_saved_partial",
        "survey_teacher_saved_complete", "survey_teacher_saved_partial",
        "survey_program_saved_complete", "survey_program_saved_partial",
        "survey_student_program_saved_complete", "survey_student_program_saved_partial",
    ],
    "المحاسبة والتقييم": [
        "eval_monthly_saved", "eval_daily_saved", "eval_self_saved",
        "eval_reading_saved", "eval_behavior_saved",
    ],
    "الاختبارات والاستبيانات": [
        "exam_created", "exam_not_published", "exam_already_taken",
        "exam_submitted", "exam_graded", "questionnaire_created",
        "questionnaire_updated", "questionnaire_status_updated",
        "questionnaire_answer_required", "questionnaire_submitted",
    ],
    "مؤشرات الأداء والحضور": [
        "kpi_added", "kpi_weights_updated", "kpi_status_updated",
        "kpi_recalculated", "kpi_select_school", "kpi_students_updated",
        "attendance_saved",
        "attendance_entry_blocked", "attendance_entry_approved",
        "attendance_teacher_weekly_limit",
    ],
    "المستخدمون والمشرف الأعلى": [
        "users_create_super_admin_only", "users_create_denied", "users_created",
        "users_created_admin", "users_assigned_admin", "users_cannot_deactivate_self",
        "users_updated", "users_status_updated", "users_role_not_allowed",
        "sa_user_created", "sa_user_updated", "sa_username_taken",
        "sa_verification_sent", "sa_cannot_deactivate_self",
        "sa_activate_requires_email", "sa_cannot_delete_self", "sa_user_deleted",
        "sa_permissions_updated", "sa_role_id_invalid", "sa_role_id_reserved",
        "sa_role_name_required", "sa_role_id_taken", "sa_role_created",
        "sa_role_system_delete", "sa_role_has_users", "sa_role_deleted",
        "sa_role_name_empty", "sa_role_updated", "sa_school_status_updated",
        "sa_schools_provisioned", "sa_settings_updated", "sa_permissions_synced",
        "identity_backfill_done", "identity_backfill_none",
    ],
    "تسجيل الطلاب — التحقق": [
        "reg_error_name_ar_required", "reg_error_field_required",
        "reg_error_school_required", "reg_error_grade_required", "reg_error_class_required",
        "reg_error_username_required", "reg_error_password_required",
        "reg_error_password_with_username",
    ],
}


def ensure_messages(school_id=None):
    if not get_setting(SETTING_KEY, school_id):
        set_setting(
            SETTING_KEY, dumps_json(MESSAGES_SEED),
            school_id=school_id, category="messages", label_ar="رسائل النظام",
        )


def get_messages(school_id=None):
    raw = get_setting(SETTING_KEY, school_id)
    if not raw:
        return dict(MESSAGES_SEED)
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
    else:
        data = raw if isinstance(raw, dict) else {}
    return {**MESSAGES_SEED, **data}


def msg(key, school_id=None, **kwargs):
    template = get_messages(school_id).get(key, key)
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return template


def flash_msg(key, category="success", school_id=None, **kwargs):
    flash(msg(key, school_id, **kwargs), category)
