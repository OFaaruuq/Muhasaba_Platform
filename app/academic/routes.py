"""Shared JSON API for dynamic grade / class / teacher lookups (DB-driven)."""

from flask import jsonify, request

from app.academic import bp
from app.utils.api_auth import api_auth_required, api_user
from app.services.registration_lookup_service import (
    registration_school_allowed,
    list_grades,
    list_classes,
    list_teachers,
    create_grade,
    create_class,
    create_teacher,
    create_school,
)
from app.services.subject_service import list_subjects, create_subject

_LOOKUP_PERMS = ("register_students", "manage_students", "manage_school", "view_all_schools")
_MANAGE_PERMS = ("register_students", "manage_students", "manage_school", "view_all_schools")
_TEACHER_PERMS = ("register_students", "manage_students", "manage_teachers", "manage_school", "view_all_schools")


@bp.route("/grades")
@api_auth_required(*_LOOKUP_PERMS)
def api_grades():
    user = api_user()
    school_id = request.args.get("school_id", type=int)
    if not school_id or not registration_school_allowed(user, school_id):
        return jsonify([])
    grades = list_grades(school_id)
    return jsonify([{"id": g.id, "name_ar": g.name_ar, "level": g.level} for g in grades])


@bp.route("/classes")
@api_auth_required(*_LOOKUP_PERMS)
def api_classes():
    user = api_user()
    school_id = request.args.get("school_id", type=int)
    grade_id = request.args.get("grade_id", type=int)
    if not school_id or not grade_id or not registration_school_allowed(user, school_id):
        return jsonify([])
    classes = list_classes(school_id, grade_id)
    return jsonify([{"id": c.id, "name": c.name, "section": c.section or ""} for c in classes])


@bp.route("/teachers")
@api_auth_required(*_TEACHER_PERMS)
def api_teachers():
    user = api_user()
    school_id = request.args.get("school_id", type=int)
    if not school_id or not registration_school_allowed(user, school_id):
        return jsonify([])
    teachers = list_teachers(school_id)
    return jsonify([
        {"id": t.id, "full_name_ar": t.full_name_ar or t.full_name, "employee_id": t.employee_id}
        for t in teachers
    ])


@bp.route("/grade", methods=["POST"])
@api_auth_required(*_MANAGE_PERMS)
def api_create_grade():
    user = api_user()
    data = request.get_json(silent=True) or {}
    try:
        school_id = int(data.get("school_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "معرّف المدرسة مطلوب."}), 400
    if not registration_school_allowed(user, school_id):
        return jsonify({"error": "غير مصرح"}), 403
    try:
        grade = create_grade(
            school_id,
            name_ar=data.get("name_ar", ""),
            level=data.get("level"),
            name=data.get("name"),
        )
        return jsonify({"id": grade.id, "name_ar": grade.name_ar, "level": grade.level})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.route("/class", methods=["POST"])
@api_auth_required(*_MANAGE_PERMS)
def api_create_class():
    user = api_user()
    data = request.get_json(silent=True) or {}
    try:
        school_id = int(data.get("school_id"))
        grade_id = int(data.get("grade_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "المدرسة والمستوى مطلوبان."}), 400
    if not registration_school_allowed(user, school_id):
        return jsonify({"error": "غير مصرح"}), 403
    try:
        class_ = create_class(
            school_id,
            grade_id,
            name=data.get("name", ""),
            section=data.get("section"),
            capacity=data.get("capacity"),
        )
        return jsonify({"id": class_.id, "name": class_.name, "section": class_.section or ""})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.route("/teacher", methods=["POST"])
@api_auth_required(*_TEACHER_PERMS)
def api_create_teacher():
    user = api_user()
    data = request.get_json(silent=True) or {}
    try:
        school_id = int(data.get("school_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "معرّف المدرسة مطلوب."}), 400
    if not registration_school_allowed(user, school_id):
        return jsonify({"error": "غير مصرح"}), 403
    try:
        teacher = create_teacher(
            school_id,
            full_name_ar=data.get("full_name_ar", ""),
            full_name=data.get("full_name"),
            employee_id=data.get("employee_id"),
        )
        return jsonify({
            "id": teacher.id,
            "full_name_ar": teacher.full_name_ar or teacher.full_name,
            "employee_id": teacher.employee_id,
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


_SUBJECT_PERMS = ("manage_teachers", "manage_school", "register_students", "view_all_schools")


@bp.route("/subjects")
@api_auth_required(*_SUBJECT_PERMS)
def api_subjects():
    user = api_user()
    school_id = request.args.get("school_id", type=int)
    if not school_id or not registration_school_allowed(user, school_id):
        return jsonify([])
    return jsonify([
        {"id": s.id, "name_ar": s.name_ar, "name": s.name, "code": s.code or ""}
        for s in list_subjects(school_id)
    ])


@bp.route("/subject", methods=["POST"])
@api_auth_required(*_SUBJECT_PERMS)
def api_create_subject():
    user = api_user()
    data = request.get_json(silent=True) or {}
    try:
        school_id = int(data.get("school_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "معرّف المدرسة مطلوب."}), 400
    if not registration_school_allowed(user, school_id):
        return jsonify({"error": "غير مصرح"}), 403
    try:
        subject = create_subject(
            school_id,
            name_ar=data.get("name_ar", ""),
            name=data.get("name"),
            code=data.get("code"),
        )
        return jsonify({
            "id": subject.id,
            "name_ar": subject.name_ar,
            "name": subject.name,
            "code": subject.code or "",
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.route("/school", methods=["POST"])
@api_auth_required("view_all_schools")
def api_create_school():
    data = request.get_json(silent=True) or {}
    try:
        school = create_school(
            name_ar=data.get("name_ar", ""),
            code=data.get("code", ""),
            name=data.get("name"),
            region=data.get("region"),
            district=data.get("district"),
            address=data.get("address"),
        )
        return jsonify({"id": school.id, "name_ar": school.name_ar, "code": school.code})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
