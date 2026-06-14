"""Super-admin user profiles: dynamic roles, teacher/student dual profiles."""

from app.extensions import db
from app.models import Class, Role, Student, Teacher, User
from tests.auth_helpers import login_session


def _csrf(client):
    import re
    page = client.get("/super-admin/users/create")
    m = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True))
    return m.group(1) if m else ""


def test_super_admin_create_teacher_with_profile(client, app):
    login_session(client, "superadmin")
    with app.app_context():
        role = Role.query.filter_by(name="teacher").first()
        school_id = 1
        class_ = Class.query.filter_by(school_id=school_id).first()
        assert class_ is not None
        class_id = class_.id
        grade_id = class_.grade_id

    resp = client.post(
        "/super-admin/users/create",
        data={
            "username": "dualteacher1",
            "full_name_ar": "معلم جديد",
            "email": "dualteacher1@test.so",
            "password": "Secret123!",
            "role_id": role.id,
            "school_id": school_id,
            "create_teacher_profile": "on",
            "employee_id": "EMP-DUAL-1",
            "teacher_class_ids": [class_id],
            "csrf_token": _csrf(client),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(username="dualteacher1").first()
        assert user is not None
        assert user.teacher_profile is not None
        assert user.teacher_profile.employee_id == "EMP-DUAL-1"
        assert len(user.teacher_profile.class_assignments.all()) >= 1


def test_super_admin_create_student_with_profile(client, app):
    login_session(client, "superadmin")
    with app.app_context():
        role = Role.query.filter_by(name="student").first()
        class_ = Class.query.filter_by(school_id=1).first()
        class_id = class_.id
        grade_id = class_.grade_id

    resp = client.post(
        "/super-admin/users/create",
        data={
            "username": "newstudent1",
            "full_name_ar": "طالب جديد",
            "email": "newstudent1@test.so",
            "password": "Secret123!",
            "role_id": role.id,
            "school_id": 1,
            "create_student_profile": "on",
            "grade_id": grade_id,
            "class_id": class_id,
            "csrf_token": _csrf(client),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(username="newstudent1").first()
        assert user.student_profile is not None
        assert user.student_profile.class_id == class_id


def test_dual_teacher_and_student_profiles(client, app):
    """Teacher-role user who is also a student in a different class."""
    login_session(client, "superadmin")
    with app.app_context():
        role = Role.query.filter_by(name="teacher").first()
        classes = Class.query.filter_by(school_id=1).limit(2).all()
        assert len(classes) >= 2
        teacher_class, student_class = classes[0], classes[1]

    resp = client.post(
        "/super-admin/users/create",
        data={
            "username": "dualuser1",
            "full_name_ar": "معلم وطالب",
            "email": "dualuser1@test.so",
            "password": "Secret123!",
            "role_id": role.id,
            "school_id": 1,
            "create_teacher_profile": "on",
            "create_student_profile": "on",
            "employee_id": "EMP-DUAL-2",
            "teacher_class_ids": [teacher_class.id],
            "grade_id": student_class.grade_id,
            "class_id": student_class.id,
            "is_active": "on",
            "csrf_token": _csrf(client),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(username="dualuser1").first()
        user.email_verified = True
        db.session.commit()
        assert user.is_teacher
        assert user.is_student
        assert user.teacher_profile.class_assignments.first().class_id == teacher_class.id
        assert user.student_profile.class_id == student_class.id
        from app.services.permission_registry import effective_user_permissions
        perms = effective_user_permissions(user)
        assert "record_attendance" in perms
        assert "self_assess" in perms
