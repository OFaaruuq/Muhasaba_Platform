"""Tests for student self-edit and follow-up survey access."""

from app.models import Student, User


def _login(client, username):
    return client.post(
        "/auth/login",
        data={"username": username, "password": "admin123"},
        follow_redirects=True,
    )


def test_student_self_edit_page(client, app):
    with app.app_context():
        user = User.query.filter_by(username="student").first()
        student = user.student_profile
        assert student is not None

    _login(client, "student")
    resp = client.get(f"/students/{student.id}/self-edit")
    assert resp.status_code == 200
    assert "تعديل بياناتي" in resp.get_data(as_text=True)


def test_teacher_followup_hub(client, app):
    _login(client, "teacher")
    resp = client.get("/followup-surveys/teacher")
    assert resp.status_code == 200


def test_teacher_can_open_family_form_for_class_student(client, app):
    with app.app_context():
        teacher = User.query.filter_by(username="teacher").first()
        tp = teacher.teacher_profile
        class_ids = [tc.class_id for tc in tp.class_assignments]
        student = Student.query.filter(
            Student.responsible_teacher_id == tp.id
        ).first()
        if not student and class_ids:
            student = Student.query.filter(Student.class_id.in_(class_ids)).first()
        assert student is not None

    _login(client, "teacher")
    resp = client.get(f"/followup-surveys/family/{student.id}")
    assert resp.status_code == 200


def test_student_can_view_family_survey(client, app):
    with app.app_context():
        user = User.query.filter_by(username="student").first()
        student = user.student_profile

    _login(client, "student")
    resp = client.get(f"/followup-surveys/family/{student.id}/view")
    assert resp.status_code == 200


def test_manager_student_program_tab_and_form(client, app):
    with app.app_context():
        student = Student.query.filter_by(is_active=True).first()
        sid = student.id

    _login(client, "manager")
    index_resp = client.get("/followup-surveys/?tab=student_program")
    assert index_resp.status_code == 200
    text = index_resp.get_data(as_text=True)
    assert "البرنامج التربوي — طلاب" in text

    form_resp = client.get(f"/followup-surveys/program/student/{sid}")
    assert form_resp.status_code == 200
    assert "متابعة البرنامج التربوي" in form_resp.get_data(as_text=True)

    save_resp = client.post(
        f"/followup-surveys/program/student/{sid}",
        data={"has_daily_individual_program": "1", "year": 2026, "month": 6},
        follow_redirects=True,
    )
    assert save_resp.status_code == 200
    with app.app_context():
        from app.models import StudentEducationalProgramFollowupSurvey
        survey = StudentEducationalProgramFollowupSurvey.query.filter_by(
            student_id=sid, period_year=2026, period_month=6,
        ).first()
        assert survey is not None
        assert survey.has_daily_individual_program is True

