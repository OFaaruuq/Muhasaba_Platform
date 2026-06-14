"""Helpers for student-linked user accounts."""

from flask import flash, redirect, url_for
from flask_login import current_user


def get_linked_student():
    """Return the Student record linked to the current user, or None."""
    if not current_user.is_authenticated:
        return None
    return current_user.student_profile


def require_linked_student(redirect_endpoint="dashboards.index"):
    """
    Return linked Student or redirect with a flash message if missing.
    Use at the start of student-only views (self-assess, take exam, etc.).
    """
    student = get_linked_student()
    if not student and current_user.role and current_user.role.name == "student":
        from app.utils.db_upgrade import repair_student_user_links
        repair_student_user_links()
        student = get_linked_student()
    if student:
        return student, None
    flash(
        "لا يوجد ملف طالب مرتبط بحسابك. يرجى التواصل مع مدير المدرسة لربط الحساب.",
        "danger",
    )
    return None, redirect(url_for(redirect_endpoint))
