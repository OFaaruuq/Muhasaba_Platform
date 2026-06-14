# منصة المحاسبة التعليمية | Muhasaba Platform

**قياس الأداء، تطوير السلوك، وبناء مستقبل أفضل**

منصة تعليمية متعددة المستأجرين (Multi-Tenant) لإدارة أداء الطلاب، السلوك، الحضور، مؤشرات الأداء (KPI)، والمحاسبة الذاتية — مستوحاة من مفهوم المحاسبة الإسلامية.

## Technology Stack

| Component      | Technology         |
| -------------- | ------------------ |
| Backend        | Python Flask       |
| Frontend       | Bootstrap 5 (RTL)  |
| Database       | SQLite (Phase 1)   |
| Authentication | Flask-Login + JWT  |
| ORM            | SQLAlchemy         |
| Migrations     | Flask-Migrate      |
| Reporting      | Pandas + ReportLab |
| Charts         | Chart.js           |
| Testing        | pytest             |

## User Roles & Dynamic Permissions

Access is **database-driven**. Super Admin can create custom roles and grant/revoke permissions at `/super-admin/roles` without code changes.

| Role            | Access Level                          |
| --------------- | ------------------------------------- |
| Super Admin     | Full platform control                 |
| Ministry Admin  | All schools, national statistics      |
| School Manager  | Own school only                       |
| Teacher         | Assigned classes and students         |
| Student         | Personal profile, self-assessment     |
| Parent          | Children's performance and attendance |

System roles are seeded with default permissions. Custom roles (e.g. counselor) inherit access when granted the same permissions. Use **مزامنة الصلاحيات** on the roles page to sync new permissions from the registry after upgrades.

## Quick Start

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment config (optional)
cp .env.example .env

# Run the application (creates DB + seed data)
python run.py
```

Open [http://localhost:5000](http://localhost:5000)

Environment variables from `.env` are loaded automatically via `python-dotenv`.

## Demo Accounts

| Username   | Password  | Role           |
| ---------- | --------- | -------------- |
| superadmin | admin123  | Super Admin (legacy) |
| superadmin1–4 | admin123 | Super Admin    |
| teacher1–7 | admin123  | Teacher        |
| student1–10 | admin123 | Student        |
| ministry   | admin123  | Ministry Admin |
| manager    | admin123  | School Manager |
| teacher    | admin123  | Teacher        |
| student    | admin123  | Student        |
| parent     | admin123  | Parent         |

## Project Structure

```
muhasaba_platform/
├── app/
│   ├── auth/              # Login, JWT API
│   ├── schools/           # School management
│   ├── students/          # Student profiles
│   ├── teachers/          # Teacher management
│   ├── attendance/        # Daily attendance
│   ├── evaluations/       # Muhasaba daily + self-assessment
│   ├── kpi/               # KPI tracking
│   ├── questionnaires/    # Surveys
│   ├── exams/             # Examinations
│   ├── reports/           # PDF/Excel reports
│   ├── dashboards/        # Role-based dashboards
│   ├── notifications/     # Notifications
│   ├── followup_surveys/  # Monthly follow-up surveys
│   ├── super_admin/       # Platform-wide admin
│   ├── admin/             # School/ministry config
│   └── ai/                # Phase 2: AI features (placeholder)
├── templates/             # RTL Arabic templates
├── static/                # CSS, JS
├── migrations/            # Flask-Migrate (Alembic)
├── tests/                 # Integration tests
├── uploads/
├── reports/
├── config.py
├── run.py
└── requirements.txt
```

## Database Migrations

For production or schema changes, use Flask-Migrate instead of relying only on `db.create_all()`:

```bash
export FLASK_APP=run:app

# First-time setup (already done in repo)
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# After model changes
flask db migrate -m "Describe change"
flask db upgrade
```

`run.py` still runs `db.create_all()` and `db_upgrade.py` patches for backward compatibility with existing SQLite databases.

## Dynamic Admin Configuration (`/admin/`)

All core behavior is **database-driven** and manageable by Ministry Admin / School Manager:

| Config Area | What Admin Controls |
|-------------|---------------------|
| **Platform Settings** | Name, tagline, grade thresholds (A/B/C/D), class capacity |
| **KPI Indicators** | Weights, names, auto-calculation from live data |
| **Muhasaba Criteria** | Academic/behavior/personal evaluation items |
| **Rating Scale** | ممتاز/جيد/متوسط/يحتاج تحسين + scores |
| **Attendance Statuses** | Present/absent/late + parent notification rules |
| **School Structure** | Grades, classes, subjects, years (per school) |
| **Users** | Create, edit, activate/deactivate |

New schools auto-provision default config + KPIs on creation.

Ministry Admin selects active school via dropdown in `/admin/`.

## Core Modules (Phase 1)

- **School Management** — Schools + CRUD for grades, classes, subjects, academic years
- **User Management** — 6 roles, user admin (create/toggle), JWT API
- **Student Registration** — `/evaluations/register` with level, class, location
- **Teacher Management** — Register teachers, assign classes/subjects
- **Attendance** — Record + parent notifications on absent/late
- **Muhasaba Evaluation** — Daily scoring hub at `/evaluations/`
- **Reading Progress** — `/evaluations/reading`
- **Behavior Records** — `/evaluations/behavior`
- **Self-Assessment** — Student daily reflection
- **Questionnaires** — Create, student respond, view results
- **Exams** — Create with auto-grading (MCQ/TF), student take
- **KPI Management** — View, update scores, admin manage indicators
- **Follow-up Surveys** — Family/teacher/program monthly surveys
- **Reports** — KPI PDF, attendance Excel, evaluation PDF
- **Notifications** — Inbox with unread badge, auto-triggers
- **Dashboards** — Role-based with Chart.js analytics
- **Audit Logging** — Core actions logged (attendance, evaluations, exams, admin)

## API Authentication (JWT)

Obtain a token:

```bash
curl -X POST http://localhost:5000/auth/api/token \
  -H "Content-Type: application/json" \
  -d '{"username": "teacher", "password": "admin123"}'
```

Use the token on protected JSON endpoints (JWT or session auth both work):

```bash
# Student KPI data
curl http://localhost:5000/kpi/api/student/1?period=term \
  -H "Authorization: Bearer <access_token>"

# Cascading grade dropdown (school manager / ministry)
curl "http://localhost:5000/evaluations/api/grades?school_id=1" \
  -H "Authorization: Bearer <access_token>"
```

Protected API routes:
- `GET /kpi/api/student/<id>`
- `GET /evaluations/api/grades`
- `GET /evaluations/api/classes`

## Running Tests

```bash
pytest
```

## Production Deployment

1. Set environment variables (see `.env.example`)
2. Use PostgreSQL or MySQL:
   - `DATABASE_URL=postgresql://user:pass@localhost/muhasaba`
   - `DATABASE_URL=mysql+pymysql://user:pass@localhost/muhasaba`
3. Set strong `SECRET_KEY` and `JWT_SECRET_KEY`
4. Run migrations: `flask db upgrade`
5. Deploy on Ubuntu with Gunicorn:

```bash
gunicorn -w 4 -b 0.0.0.0:8000 "run:app"
```

## Phase 2 Roadmap

- AI Teacher Assistant (`/ai/` — placeholder registered)
- AI Muhasaba Coach (improvement suggestions)
- Predictive analytics (at-risk students)
- SMS/Email notifications
- Full exam auto-grading
- Excel report export

## License

Educational platform for Ministry of Education — Somalia.
