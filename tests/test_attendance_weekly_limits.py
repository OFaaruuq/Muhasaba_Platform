"""Weekly class limits and attendance entry denial."""

from datetime import date, timedelta

from app.models import Attendance, Student, User
from app.services.attendance_limit_service import (
    can_mark_student_status,
    get_student_weekly_limit,
    is_student_denied_entry,
    approve_student_entry,
    week_start_for,
)
from app.services.config_service import get_present_status_codes, get_default_attendance_status


def test_student_weekly_limit_from_default(app):
    with app.app_context():
        student = Student.query.filter_by(is_active=True).first()
        limit = get_student_weekly_limit(student)
        assert limit >= 1


def test_per_class_attendance_upsert(app):
    with app.app_context():
        student = Student.query.filter_by(is_active=True).first()
        today = date.today()
        Attendance.query.filter_by(
            student_id=student.id, class_id=student.class_id, date=today,
        ).delete()
        from app.extensions import db
        db.session.add(Attendance(
            student_id=student.id,
            school_id=student.school_id,
            class_id=student.class_id,
            date=today,
            status="present",
        ))
        db.session.commit()
        row = Attendance.query.filter_by(
            student_id=student.id, class_id=student.class_id, date=today,
        ).first()
        assert row is not None


def test_denied_after_absence_threshold(app):
    with app.app_context():
        student = Student.query.filter_by(is_active=True).first()
        ws = week_start_for(date.today())
        present = get_present_status_codes(student.school_id)[0]
        absent = "absent"
        Attendance.query.filter(
            Attendance.student_id == student.id,
            Attendance.date >= ws,
        ).delete()
        from app.extensions import db
        for i in range(2):
            db.session.add(Attendance(
                student_id=student.id,
                school_id=student.school_id,
                class_id=student.class_id,
                date=ws + timedelta(days=i),
                status=absent,
            ))
        db.session.commit()
        denied, reason = is_student_denied_entry(
            student, student.class_id, ws + timedelta(days=3), present,
        )
        assert denied is True
        assert reason == "absence_threshold"


def test_approval_allows_present(app):
    with app.app_context():
        student = Student.query.filter_by(is_active=True).first()
        manager = User.query.filter_by(username="manager").first()
        on_date = date.today()
        present = get_present_status_codes(student.school_id)[0]
        approve_student_entry(student, student.class_id, on_date, manager)
        from app.extensions import db
        db.session.commit()
        allowed, _ = can_mark_student_status(
            student, student.class_id, on_date, present, manager,
        )
        assert allowed is True


def test_record_blocks_denied_student(client, app):
    with app.app_context():
        student = Student.query.filter_by(is_active=True).first()
        user = User.query.filter_by(username="teacher").first()
        class_id = user.teacher_profile.class_assignments[0].class_id
        ws = week_start_for(date.today())
        Attendance.query.filter(
            Attendance.student_id == student.id,
            Attendance.date >= ws,
        ).delete()
        from app.extensions import db
        for i in range(2):
            db.session.add(Attendance(
                student_id=student.id,
                school_id=student.school_id,
                class_id=class_id,
                date=ws + timedelta(days=i),
                status="absent",
            ))
        db.session.commit()
        present = get_default_attendance_status(student.school_id)

    from tests.auth_helpers import login_session
    login_session(client, "teacher", "admin123")
    resp = client.post(
        f"/attendance/record/{class_id}",
        data={
            "date": date.today().isoformat(),
            f"status_{student.id}": present,
            f"manual_{student.id}": "1",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        row = Attendance.query.filter_by(
            student_id=student.id,
            class_id=class_id,
            date=date.today(),
        ).first()
        assert row is None or row.status == "absent"
