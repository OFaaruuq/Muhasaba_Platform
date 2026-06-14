#!/usr/bin/env python3
"""One-off helper: replace hardcoded flash() with flash_msg() across route modules."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (filepath relative to ROOT, list of (old, new) exact string replacements)
FILES = {
    "app/__init__.py": [
        (
            '                flash(\n'
            '                    "حسابك غير مفعّل أو البريد غير مُحقَّق. تواصل مع المشرف الأعلى.",\n'
            '                    "danger",\n'
            '                )',
            '                from app.services.message_service import flash_msg\n'
            '                flash_msg("auth_account_inactive", "danger")',
        ),
    ],
    "app/utils/decorators.py": [
        ('flash("ليس لديك صلاحية للوصول إلى هذه الصفحة.", "danger")', 'flash_msg("permission_denied_page", "danger")'),
    ],
    "app/utils/student_context.py": [
        (
            '    flash(\n'
            '        "لا يوجد ملف طالب مرتبط بحسابك. يرجى التواصل مع مدير المدرسة لربط الحساب.",\n'
            '        "danger",\n'
            '    )',
            '    flash_msg("auth_no_student_profile", "danger")',
        ),
    ],
    "app/followup_surveys/routes.py": [
        ('flash("تم حفظ استبيان متابعة الأسرة بالكامل.", "success")', 'flash_msg("survey_family_saved_complete", "success", sid)'),
        ('flash(f"تم حفظ الإجابات ({answered} من {total} سؤال). يمكنك إكمال الباقي لاحقاً.", "success")', 'flash_msg("survey_family_saved_partial", "success", sid, answered=answered, total=total)'),
        ('flash("تم حفظ الاستبيان الشهري للمعلم بالكامل.", "success")', 'flash_msg("survey_teacher_saved_complete", "success", sid)'),
        ('flash("تم حفظ متابعة البرنامج التربوي بالكامل.", "success")', 'flash_msg("survey_program_saved_complete", "success", sid)'),
        ('flash(f"تم حفظ الإجابات ({answered} من {total}). يمكنك إكمال الباقي لاحقاً.", "success")', 'flash_msg("survey_program_saved_partial", "success", sid, answered=answered, total=total)'),
        ('flash("تم حفظ متابعة البرنامج التربوي للطالب بالكامل.", "success")', 'flash_msg("survey_student_program_saved_complete", "success", sid)'),
    ],
    "app/students/routes.py": [
        ('flash("ليس لديك صلاحية لتعديل هذا الطالب.", "danger")', 'flash_msg("permission_edit_student", "danger")'),
        ('flash("تم تحديث بيانات الطالب.", "success")', 'flash_msg("student_updated", "success", sid)'),
        ('flash("ليس لديك صلاحية لتعديل هذا الملف.", "danger")', 'flash_msg("permission_edit_profile", "danger")'),
        ('flash("تم تحديث بياناتك.", "success")', 'flash_msg("student_self_updated", "success")'),
        ('flash(f"تم تعطيل {count} طالب/طلاب.", "success")', 'flash_msg("student_deactivated_bulk", "success", sid, count=count)'),
        ('flash(f"تم تفعيل {count} طالب/طلاب.", "success")', 'flash_msg("student_activated_bulk", "success", sid, count=count)'),
        ('flash("ليس لديك صلاحية.", "danger")', 'flash_msg("permission_denied", "danger")'),
        ('flash("الطالب معطّل مسبقاً.", "info")', 'flash_msg("student_already_inactive", "info")'),
        ('flash("تم تعطيل الطالب. لن يظهر في القوائم النشطة.", "success")', 'flash_msg("student_deactivated", "success", sid)'),
        ('flash("تم تفعيل الطالب.", "success")', 'flash_msg("student_activated", "success", sid)'),
        ('flash("تم ربط ولي الأمر بالطالب.", "success")', 'flash_msg("student_parent_linked", "success", sid)'),
        ('flash("تم إلغاء الربط.", "success")', 'flash_msg("student_parent_unlinked", "success", sid)'),
    ],
    "app/students/registration.py": [
        ('flash("الفصل المحدد غير صالح لهذا المستوى والمدرسة.", "danger")', 'flash_msg("student_register_invalid_class", "danger", school_id)'),
        ('flash("رقم الطالب مستخدم مسبقاً.", "danger")', 'flash_msg("student_id_taken", "danger", school_id)'),
        ('flash(f"تم تسجيل الطالب {student.full_name_ar} بنجاح.", "success")', 'flash_msg("student_registered", "success", school_id, name=student.full_name_ar)'),
        ('flash("إنشاء حسابات الدخول متاح فقط للمشرف الأعلى.", "info")', 'flash_msg("student_register_account_info", "info")'),
    ],
    "app/teachers/routes.py": [
        ('flash("ليس لديك صلاحية.", "danger")', 'flash_msg("permission_denied", "danger")'),
        ('flash("الرقم الوظيفي مستخدم.", "danger")', 'flash_msg("teacher_employee_id_taken", "danger", sid)'),
        ('flash("تم تسجيل المعلم. لإنشاء حساب دخول، يجب على المشرف الأعلى إنشاء مستخدم وربطه بالمعلم.", "success")', 'flash_msg("teacher_registered", "success", sid)'),
        ('flash("تم تحديث بيانات المعلم.", "success")', 'flash_msg("teacher_updated", "success", sid)'),
        ('flash("المعلم معطّل مسبقاً.", "info")', 'flash_msg("teacher_already_inactive", "info")'),
        ('flash("تم تعطيل المعلم. لن يظهر في القائمة ولن يتمكن من تسجيل الدخول.", "success")', 'flash_msg("teacher_deactivated", "success", sid)'),
        ('flash("تم تفعيل المعلم.", "success")', 'flash_msg("teacher_activated", "success", sid)'),
        ('flash("هذا التعيين موجود مسبقاً.", "warning")', 'flash_msg("teacher_assignment_exists", "warning", sid)'),
        ('flash("تم تعيين الفصل للمعلم.", "success")', 'flash_msg("teacher_class_assigned", "success", sid)'),
        ('flash("تم إزالة التعيين.", "success")', 'flash_msg("teacher_assignment_removed", "success", sid)'),
    ],
    "app/attendance/routes.py": [
        ('flash("ليس لديك صلاحية لتسجيل حضور هذه المجموعة.", "danger")', 'flash_msg("permission_attendance_group", "danger")'),
        ('flash("تم تسجيل الحضور بنجاح.", "success")', 'flash_msg("attendance_saved", "success", sid)'),
    ],
    "app/evaluations/routes.py": [
        ('flash("لا يوجد معلم مرتبط.", "danger")', 'flash_msg("teacher_no_profile", "danger")'),
        ('flash("تم حفظ التقييم الشهري.", "success")', 'flash_msg("eval_monthly_saved", "success", sid)'),
        ('flash("تم حفظ تقييم المحاسبة اليومي.", "success")', 'flash_msg("eval_daily_saved", "success", sid)'),
        ('flash("تم حفظ محاسبتك الذاتية.", "success")', 'flash_msg("eval_self_saved", "success")'),
        ('flash("تم تسجيل تقييم القراءة.", "success")', 'flash_msg("eval_reading_saved", "success", sid)'),
        ('flash("تم تسجيل السلوك.", "success")', 'flash_msg("eval_behavior_saved", "success", sid)'),
    ],
    "app/exams/routes.py": [
        ('flash("لا يوجد معلم مرتبط.", "danger")', 'flash_msg("teacher_no_profile", "danger")'),
        ('flash("تم إنشاء الاختبار.", "success")', 'flash_msg("exam_created", "success", sid)'),
        ('flash("الاختبار غير منشور.", "danger")', 'flash_msg("exam_not_published", "danger")'),
        ('flash("لقد أجبت على هذا الاختبار مسبقاً.", "info")', 'flash_msg("exam_already_taken", "info")'),
        ('flash(f"تم تسليم الاختبار. درجتك: {pct}%", "success")', 'flash_msg("exam_submitted", "success", pct=pct)'),
        ('flash("تم تصحيح الاختبار.", "success")', 'flash_msg("exam_graded", "success", sid)'),
    ],
    "app/kpi/routes.py": [
        ('flash("تم إضافة مؤشر الأداء.", "success")', 'flash_msg("kpi_added", "success", sid)'),
        ('flash("تم تحديث الأوزان.", "success")', 'flash_msg("kpi_weights_updated", "success", sid)'),
        ('flash("تم تحديث حالة المؤشر.", "success")', 'flash_msg("kpi_status_updated", "success", sid)'),
        ('flash("تم تحديث مؤشرات الأداء ديناميكياً.", "success")', 'flash_msg("kpi_recalculated", "success", sid)'),
        ('flash("حدد مدرسة أولاً.", "danger")', 'flash_msg("kpi_select_school", "danger")'),
        ('flash(f"تم تحديث مؤشرات {count} طالب.", "success")', 'flash_msg("kpi_students_updated", "success", sid, count=count)'),
    ],
    "app/questionnaires/routes.py": [
        ('flash("ليس لديك صلاحية لهذا الاستبيان.", "danger")', 'flash_msg("permission_questionnaire", "danger")'),
        ('flash("لا يوجد معلم مرتبط.", "danger")', 'flash_msg("teacher_no_profile", "danger")'),
        ('flash("تم إنشاء الاستبيان.", "success")', 'flash_msg("questionnaire_created", "success", sid)'),
        ('flash("ليس لديك صلاحية التعديل.", "danger")', 'flash_msg("permission_questionnaire_edit", "danger")'),
        ('flash("تم تحديث الاستبيان.", "success")', 'flash_msg("questionnaire_updated", "success", sid)'),
        ('flash("ليس لديك صلاحية.", "danger")', 'flash_msg("permission_denied", "danger")'),
        ('flash("تم تحديث حالة الاستبيان.", "success")', 'flash_msg("questionnaire_status_updated", "success", sid)'),
        ('flash(f"يرجى الإجابة على: {question.text_ar or question.text}", "danger")', 'flash_msg("questionnaire_answer_required", "danger", question=question.text_ar or question.text)'),
        ('flash("تم إرسال إجاباتك.", "success")', 'flash_msg("questionnaire_submitted", "success")'),
    ],
    "app/users/routes.py": [
        ('flash("إنشاء المستخدمين متاح فقط للمشرف الأعلى من لوحة المشرف الأعلى.", "warning")', 'flash_msg("users_create_super_admin_only", "warning")'),
        ('flash("لا يمكن تعطيل حسابك.", "danger")', 'flash_msg("users_cannot_deactivate_self", "danger")'),
        ('flash("ليس لديك صلاحية.", "danger")', 'flash_msg("permission_denied", "danger")'),
        ('flash("تم تحديث حالة المستخدم.", "success")', 'flash_msg("users_status_updated", "success")'),
        ('flash("لا يمكن تعيين هذا الدور.", "danger")', 'flash_msg("users_role_not_allowed", "danger")'),
        ('flash("تم تحديث المستخدم.", "success")', 'flash_msg("users_updated", "success")'),
    ],
    "app/schools/routes.py": [
        ('flash("ليس لديك صلاحية.", "danger")', 'flash_msg("permission_denied", "danger")'),
        ('flash("تم تسجيل المدرسة بنجاح مع الإعدادات الافتراضية.", "success")', 'flash_msg("school_registered", "success")'),
        ('flash("رمز المدرسة مستخدم مسبقاً.", "danger")', 'flash_msg("school_code_taken", "danger")'),
        ('flash("تم تحديث المدرسة.", "success")', 'flash_msg("school_updated", "success", school.id)'),
        ('flash(f"تم {state} المدرسة.", "success")', 'flash_msg("school_state_changed", "success", school.id, state=state)'),
        ('flash("رمز التأكيد غير صحيح. اكتب رمز المدرسة للحذف النهائي.", "danger")', 'flash_msg("school_delete_code_wrong", "danger")'),
        ('flash(f"تم حذف المدرسة «{name_ar}» نهائياً.", "success")', 'flash_msg("school_deleted", "success", name=name_ar)'),
        ('flash("تم إضافة المستوى الدراسي.", "success")', 'flash_msg("grade_added", "success", school_id)'),
        ('flash("تم إضافة الفصل.", "success")', 'flash_msg("class_added", "success", school_id)'),
        ('flash("تم إضافة المادة.", "success")', 'flash_msg("subject_added", "success", school_id)'),
        ('flash("تم إضافة السنة الدراسية.", "success")', 'flash_msg("year_added", "success", school_id)'),
        ('flash("تم تحديث الصف.", "success")', 'flash_msg("grade_updated", "success", school_id)'),
        ('flash("لا يمكن حذف صف مرتبط بفصول.", "danger")', 'flash_msg("grade_delete_blocked", "danger")'),
        ('flash("تم حذف الصف.", "success")', 'flash_msg("grade_deleted", "success", school_id)'),
        ('flash("تم تحديث الفصل.", "success")', 'flash_msg("class_updated", "success", school_id)'),
        ('flash("لا يمكن حذف فصل يضم طلاباً.", "danger")', 'flash_msg("class_delete_blocked", "danger")'),
        ('flash("تم حذف الفصل.", "success")', 'flash_msg("class_deleted", "success", school_id)'),
        ('flash("تم تحديث المادة.", "success")', 'flash_msg("subject_updated", "success", school_id)'),
        ('flash("لا يمكن حذف المادة: " + "؛ ".join(blockers) + ".", "danger")', 'flash_msg("subject_delete_blocked", "danger", reason="؛ ".join(blockers))'),
        ('flash("تم حذف المادة.", "success")', 'flash_msg("subject_deleted", "success", school_id)'),
        ('flash("تم تحديث السنة الدراسية.", "success")', 'flash_msg("year_updated", "success", school_id)'),
        ('flash("لا يمكن حذف سنة مرتبطة بفصول.", "danger")', 'flash_msg("year_delete_blocked", "danger")'),
        ('flash("تم حذف السنة الدراسية.", "success")', 'flash_msg("year_deleted", "success", school_id)'),
    ],
    "app/super_admin/routes.py": [
        ('flash("لا يمكن تعيين هذا الدور.", "danger")', 'flash_msg("users_role_not_allowed", "danger")'),
        ('flash("اسم المستخدم موجود.", "danger")', 'flash_msg("sa_username_taken", "danger")'),
        ('flash("تم إنشاء المستخدم وإرسال رابط تفعيل البريد. فعّل الحساب من قائمة المستخدمين.", "success")', 'flash_msg("sa_user_created", "success")'),
        ('flash("تم تحديث المستخدم.", "success")', 'flash_msg("sa_user_updated", "success")'),
        ('flash("تم إرسال رابط تفعيل البريد.", "success")', 'flash_msg("sa_verification_sent", "success")'),
        ('flash("لا يمكن تعطيل حسابك.", "danger")', 'flash_msg("sa_cannot_deactivate_self", "danger")'),
        ('flash("لا يمكن تفعيل الحساب قبل تفعيل البريد الإلكتروني.", "danger")', 'flash_msg("sa_activate_requires_email", "danger")'),
        ('flash("تم تحديث حالة المستخدم.", "success")', 'flash_msg("users_status_updated", "success")'),
        ('flash("لا يمكن حذف حسابك.", "danger")', 'flash_msg("sa_cannot_delete_self", "danger")'),
        ('flash("تم حذف المستخدم.", "success")', 'flash_msg("sa_user_deleted", "success")'),
        ('flash("تم تحديث الصلاحيات.", "success")', 'flash_msg("sa_permissions_updated", "success")'),
        ('flash("معرّف الدور يجب أن يبدأ بحرف ويحتوي أحرفاً إنجليزية صغيرة وأرقام و _ فقط.", "danger")', 'flash_msg("sa_role_id_invalid", "danger")'),
        ('flash("هذا المعرّف محجوز لدور نظامي.", "danger")', 'flash_msg("sa_role_id_reserved", "danger")'),
        ('flash("اسم الدور بالعربية مطلوب.", "danger")', 'flash_msg("sa_role_name_required", "danger")'),
        ('flash("معرّف الدور موجود مسبقاً.", "danger")', 'flash_msg("sa_role_id_taken", "danger")'),
        ('flash(f"تم إنشاء دور «{name_ar}».", "success")', 'flash_msg("sa_role_created", "success", name=name_ar)'),
        ('flash("لا يمكن حذف الأدوار النظامية.", "danger")', 'flash_msg("sa_role_system_delete", "danger")'),
        ('flash("لا يمكن حذف دور مرتبط بمستخدمين.", "danger")', 'flash_msg("sa_role_has_users", "danger")'),
        ('flash(f"تم حذف دور «{label}».", "success")', 'flash_msg("sa_role_deleted", "success", name=label)'),
        ('flash("اسم الدور مطلوب.", "danger")', 'flash_msg("sa_role_name_empty", "danger")'),
        ('flash(f"تم تحديث دور «{name_ar}».", "success")', 'flash_msg("sa_role_updated", "success", name=name_ar)'),
        ('flash("تم تحديث حالة المدرسة.", "success")', 'flash_msg("sa_school_status_updated", "success")'),
        ('flash(f"تم تهيئة {count} مدرسة.", "success")', 'flash_msg("sa_schools_provisioned", "success", count=count)'),
        ('flash("تم تحديث الإعدادات العامة.", "success")', 'flash_msg("sa_settings_updated", "success")'),
        ('flash("تم مزامنة الصلاحيات من سجل النظام.", "success")', 'flash_msg("sa_permissions_synced", "success")'),
    ],
}

IMPORT_LINE = "from app.services.message_service import flash_msg\n"

for rel, reps in FILES.items():
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    for old, new in reps:
        if old not in text:
            print(f"MISSING in {rel}: {old[:60]}...")
        else:
            text = text.replace(old, new)
    if "flash_msg(" in text and "from app.services.message_service import flash_msg" not in text:
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("from flask import"):
                lines.insert(i + 1, IMPORT_LINE.rstrip())
                break
        text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    path.write_text(text, encoding="utf-8")
    print("OK", rel)

print("done")
