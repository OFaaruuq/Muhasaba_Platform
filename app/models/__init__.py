from app.models.user import Role, User, Permission, role_permissions
from app.models.school import School, AcademicYear, Grade, Class, Subject, ClassSubject
from app.models.student import Student, Parent, parent_student
from app.models.teacher import Teacher, TeacherClass
from app.models.attendance import Attendance
from app.models.kpi import KPI, StudentKPI
from app.models.evaluation import (
    Evaluation,
    EvaluationDetail,
    ReadingAssessment,
    BehaviorRecord,
    StudentSelfAssessment,
    MonthlyEvaluation,
    MonthlyEvaluationDetail,
)
from app.models.questionnaire import Questionnaire, Question, Choice, StudentAnswer
from app.models.followup_survey import (
    FamilyFollowupSurvey,
    TeacherMonthlySurvey,
    EducationalProgramFollowupSurvey,
    StudentEducationalProgramFollowupSurvey,
)
from app.models.exam import Exam, ExamQuestion, ExamResult
from app.models.notification import Notification, AuditLog
from app.models.settings import (
    PlatformSetting, EvaluationCriterion, RatingLevel, AttendanceStatusConfig,
    ConfigOption,
)
from app.models.seed import seed_database

__all__ = [
    "Role",
    "User",
    "Permission",
    "role_permissions",
    "School",
    "AcademicYear",
    "Grade",
    "Class",
    "Subject",
    "ClassSubject",
    "Student",
    "Parent",
    "parent_student",
    "Teacher",
    "TeacherClass",
    "Attendance",
    "KPI",
    "StudentKPI",
    "Evaluation",
    "EvaluationDetail",
    "ReadingAssessment",
    "BehaviorRecord",
    "StudentSelfAssessment",
    "MonthlyEvaluation",
    "MonthlyEvaluationDetail",
    "Questionnaire",
    "Question",
    "Choice",
    "StudentAnswer",
    "FamilyFollowupSurvey",
    "TeacherMonthlySurvey",
    "EducationalProgramFollowupSurvey",
    "StudentEducationalProgramFollowupSurvey",
    "Exam",
    "ExamQuestion",
    "ExamResult",
    "Notification",
    "AuditLog",
    "PlatformSetting",
    "EvaluationCriterion",
    "RatingLevel",
    "AttendanceStatusConfig",
    "ConfigOption",
    "seed_database",
]
