# StudySprint Agent

StudySprint Agent is a beginner-friendly study planner for college students.
It organizes assignments, exams, and study sessions with SQLite-backed task
management, deterministic priorities, and a daily study planner.

## Requirements

- Python 3.12.7 (the expected version is recorded in `.python-version`)
- `pip`
- SQLite for local development and tests; managed PostgreSQL for production
- Optional: Docker

## Setup on Windows

Open PowerShell in the project folder and create a virtual environment:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --upgrade pip==26.2.1
python -m pip install -r requirements-dev.txt
```

If PowerShell blocks activation, run this once for the current PowerShell
window, then activate the environment again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Run the application

```powershell
python run.py
```

Open <http://127.0.0.1:5000/health>. A successful response is JSON containing
`"status": "ok"`.

## Authentication and existing databases

New students can create an account at `/register`, log in at `/login`, and
log out from the navigation. Every dashboard, task, and schedule request
requires authentication. Passwords are stored as Werkzeug password hashes,
never as plaintext. Flask-WTF protects all state-changing forms with CSRF
tokens, and production sessions require an environment-provided secret.

For any pre-authentication SQLite copy with task rows without owners, make a
backup and run the one-time migration below before starting the application.
The migration creates the users table, adds `owner_id`, creates the supplied
legacy owner account, and assigns every existing task to that account without
deleting or resetting task rows. The checked-in working database has already
been migrated and is not automatically changed by startup.

```powershell
Copy-Item studysprint.db studysprint.db.backup
$env:LEGACY_OWNER_EMAIL = "you@example.com"
$env:LEGACY_OWNER_PASSWORD = "use-a-strong-password"
python migrate_auth.py
```

The migration currently supports SQLite only. It is intentionally not run by
the application startup. If the old schema is detected, startup stops with a
clear migration message instead of silently dropping or exposing old tasks.

For production, set a strong random `SECRET_KEY`, use `APP_ENV=production`,
serve the app behind HTTPS, and use a managed PostgreSQL URL. Configure
`RATE_LIMIT_STORAGE_URI` with shared Redis storage; in-memory rate limits are
rejected in production because they do not work across multiple workers. Set
`TRUSTED_PROXY_HOPS` only to the number of trusted reverse proxies in front of
the app. Secure, HTTP-only, SameSite cookies, HSTS, security headers, and
proxy-aware HTTPS URLs are enabled by configuration. This project is not being
deployed by this change.

## Production WSGI and database preparation

The production WSGI entry point is `wsgi:app`. A hosting platform can run:

```text
gunicorn --bind 0.0.0.0:$PORT --workers ${WEB_CONCURRENCY:-2} --access-logfile - wsgi:app
```

`Procfile` contains the same command, and the Dockerfile uses Gunicorn. Local
development continues to use `python run.py`; do not use Flask's debug server
for public traffic.

### Safe SQLite-to-PostgreSQL migration path

Never let application startup migrate or overwrite the existing database.

1. Stop writes and create two verified copies of `studysprint.db` outside the
   repository. Record checksums, file size, task count, user count, and task ID
   samples.
2. Run `migrate_auth.py` against a copy, not the original. Verify that every
   task has an owner and that the legacy owner can log in.
3. Create a managed PostgreSQL database with TLS and restricted credentials.
   Load the verified migrated data using a separately reviewed export/import
   procedure. This application does not run that transfer automatically.
4. In staging, verify row counts, login, ownership isolation, CRUD, priority
   ordering, schedule limits, theme behavior, and backups.
5. Take a final pre-cutover backup, set production environment variables, and
   perform a controlled read/write cutover.
6. Roll back by stopping the new app and restoring the last verified backup or
   switching the connection back to the prior database after reviewing writes.
   Never overwrite a backup in place.

SQLite remains supported for local development and tests. Production startup
requires a PostgreSQL `DATABASE_URL` and shared rate-limit storage.

## Run the tests

```powershell
python -m pytest
```

Run the test suite from the project root so Python can import the `app`
package.

Check installed dependency consistency with:

```powershell
python -m pip check
```

`requirements.lock` records the resolved runtime dependency set.
`requirements-dev.txt` adds the pinned `pip-audit` release check. Run these
commands in CI or a release environment before publishing:

```powershell
python -m pip check
python -m pip_audit -r requirements.txt
python -m pip_audit
```

The first audit checks project dependencies from the requirements file; the
second checks the complete installed environment, including development tools.

## Task priority formula

Pending tasks receive a deterministic score made from three parts:

| Factor | Points |
| --- | --- |
| Deadline | Overdue: 60; today: 50; within 2 days: 40; within a week: 30; within 2 weeks: 20; later or missing: 10 |
| User urgency | Low: 0; medium: 15; high: 30 |
| Estimated study time | 1–30 minutes: 5; 31–60: 10; 61–120: 15; over 120: 20 |

The total is labelled **Critical** at 80 or more, **High** at 60–79,
**Medium** at 35–59, and **Low** below 35. Pending tasks are sorted by score
descending. Ties are resolved by earlier deadline, higher urgency, longer
estimated study time, and finally the smaller task ID. Completed tasks are
shown in their own section and are not prioritized. The task list also shows a
plain-language explanation of each pending task's score.

## Daily study scheduling

Open <http://127.0.0.1:5000/schedule>, enter available study time, choose
minutes or hours, and click **Generate schedule**. The application uses this
deterministic greedy algorithm:

1. Ignore completed tasks.
2. Sort pending tasks using the existing priority score, then earlier
   deadline, higher urgency, longer estimated study time, and task ID.
3. Visit tasks in that order.
4. Add a task only when its full estimated study duration fits in the
   remaining daily minutes. Subtract that duration from the remaining time.
5. Put tasks that do not fit into **Not scheduled today**, with an explanation
   of the remaining capacity.

This never allocates more than a task's estimate or more than the student's
available daily time. Overdue and due-today tasks naturally rise because the
existing priority formula gives them more points. If there are no pending
tasks, the schedule shows a clear empty state.

## Run with Docker

Build and start the container from the project root:

```powershell
docker build -t studysprint-agent .
docker run --rm -p 5000:5000 studysprint-agent
```

Then open <http://127.0.0.1:5000/health>.

## Project structure

```text
app/
  __init__.py       Flask application factory and health route
  auth.py            Flask-Login configuration and user loading
  security.py        Rate limiting, proxy handling, and security headers
  config.py         Environment-based configuration defaults
  models.py         SQLAlchemy User and owned Task models
  database.py       SQLite setup and sample-task helper
  validation.py     Safe task form validation
  routes.py         Task list and CRUD routes
  priority.py       Deterministic priority scoring and sorting
  scheduling.py     Daily schedule algorithm and time parsing
templates/
  base.html         Shared page layout
  index.html        Task list and task actions
  task_form.html    Add/edit task form
  auth_form.html     Shared registration/login form
  login.html         Login page
  register.html      Registration page
static/
  styles.css        Responsive application styles
  theme.js          Light/dark preference switcher
  theme-init.js     Pre-paint theme preference initialization
tests/
  test_health.py    Automated health-check test
  test_tasks.py     Task CRUD, validation, sample-data, and persistence tests
  test_priority.py  Priority scores, labels, ties, and edge-case tests
  test_scheduling.py Daily schedule order, limits, and edge-case tests
  test_auth.py       Authentication, CSRF, and ownership isolation tests
run.py              Local development entry point
migrate_auth.py     One-time legacy SQLite ownership migration
wsgi.py             Production WSGI entry point
Procfile            Hosting-platform Gunicorn command
requirements.txt    Direct pinned Python dependencies
requirements.lock   Fully resolved dependency lockfile
.python-version     Expected Python runtime version
.env.example        Safe example environment configuration
Dockerfile          Reproducible container setup
```
