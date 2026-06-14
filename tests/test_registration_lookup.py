"""Tests for registration lookup APIs and quick-create."""

from app.models import Grade, Class, Teacher, School


from tests.auth_helpers import login_session


def _login_manager(client):
    return login_session(client, "manager")


def test_api_grades_for_manager(client, app):
    _login_manager(client)
    with app.app_context():
        school = School.query.filter_by(is_active=True).first()
    resp = client.get(f"/academic/api/grades?school_id={school.id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_api_classes_requires_grade(client, app):
    _login_manager(client)
    with app.app_context():
        school = School.query.filter_by(is_active=True).first()
        grade = Grade.query.filter_by(school_id=school.id).first()
    resp = client.get(
        f"/academic/api/classes?school_id={school.id}&grade_id={grade.id}"
    )
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_api_teachers_for_manager(client, app):
    _login_manager(client)
    with app.app_context():
        school = School.query.filter_by(is_active=True).first()
    resp = client.get(f"/academic/api/teachers?school_id={school.id}")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_quick_create_grade_class_teacher(client, app):
    _login_manager(client)
    with app.app_context():
        school = School.query.filter_by(is_active=True).first()
        school_id = school.id
        before_grades = Grade.query.filter_by(school_id=school_id).count()

    grade_resp = client.post(
        "/academic/api/grade",
        json={"school_id": school_id, "name_ar": "صف تجريبي", "level": 99},
    )
    assert grade_resp.status_code == 200
    grade_id = grade_resp.get_json()["id"]

    class_resp = client.post(
        "/academic/api/class",
        json={
            "school_id": school_id,
            "grade_id": grade_id,
            "name": "مجموعة تجريبية",
            "section": "ت",
        },
    )
    assert class_resp.status_code == 200

    teacher_resp = client.post(
        "/academic/api/teacher",
        json={"school_id": school_id, "full_name_ar": "مسؤول تجريبي"},
    )
    assert teacher_resp.status_code == 200

    with app.app_context():
        assert Grade.query.filter_by(school_id=school_id).count() == before_grades + 1
        assert Class.query.filter_by(grade_id=grade_id, name="مجموعة تجريبية").first()
        assert Teacher.query.filter_by(full_name_ar="مسؤول تجريبي").first()


def test_api_subjects_for_manager(client, app):
    _login_manager(client)
    with app.app_context():
        school = School.query.filter_by(is_active=True).first()
    resp = client.get(f"/academic/api/subjects?school_id={school.id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_api_create_subject(client, app):
    _login_manager(client)
    with app.app_context():
        from app.models import Subject
        school = School.query.filter_by(is_active=True).first()
        school_id = school.id

    resp = client.post(
        "/academic/api/subject",
        json={"school_id": school_id, "name_ar": "مادة تجريبية", "code": "TST"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name_ar"] == "مادة تجريبية"

    with app.app_context():
        assert Subject.query.filter_by(school_id=school_id, name_ar="مادة تجريبية").first()


def test_teacher_create_edit_show_subject_select(client, app):
    with app.app_context():
        from app.models import Subject, Teacher
        school = School.query.filter_by(is_active=True).first()
        subject = Subject.query.filter_by(school_id=school.id).first()
        teacher = Teacher.query.filter_by(is_active=True).first()
        tid = teacher.id
        subject_id = subject.id
        subject_name_ar = subject.name_ar
        username = teacher.user.username if teacher.user else ""
        form_data = {
            "full_name_ar": teacher.full_name_ar,
            "full_name": teacher.full_name or teacher.full_name_ar,
            "employee_id": teacher.employee_id,
            "subject_id": subject_id,
            "username": username,
        }

    from tests.auth_helpers import login_session; login_session(client, "manager", "admin123")
    create_resp = client.get("/teachers/create")
    assert create_resp.status_code == 200
    assert "subjectSelect" in create_resp.get_data(as_text=True)
    assert "إضافة مادة" in create_resp.get_data(as_text=True)

    edit_resp = client.get(f"/teachers/{tid}/edit")
    assert edit_resp.status_code == 200
    assert "subjectSelect" in edit_resp.get_data(as_text=True)

    update_resp = client.post(
        f"/teachers/{tid}/edit",
        data=form_data,
        follow_redirects=True,
    )
    assert update_resp.status_code == 200
    with app.app_context():
        updated = Teacher.query.get(tid)
        assert updated.specialization == subject_name_ar

