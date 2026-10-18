"""Web routes for creating and managing tasks."""

from datetime import date

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from .database import seed_sample_tasks
from .models import Task, User
from .priority import calculate_priority, prioritize_pending_tasks
from .scheduling import DailySchedule, generate_daily_schedule, parse_available_minutes
from .validation import URGENCY_LEVELS, validate_task_form


def _session(app: Flask):
    """Open a database session using the app's configured session factory."""
    return app.extensions["database_session_factory"]()


def _owned_task(session, task_id: int) -> Task | None:
    """Return a task only when it belongs to the authenticated student."""
    return session.scalar(select(Task).where(Task.id == task_id, Task.owner_id == current_user.id))


def _form_values(task: Task | None = None) -> dict:
    """Build form values for a new or existing task."""
    if task is None:
        return {"urgency": "medium", "completed": False}
    return {
        "title": task.title,
        "course": task.course,
        "deadline": task.deadline.isoformat(),
        "urgency": task.urgency,
        "estimated_minutes": task.estimated_minutes,
        "notes": task.notes,
        "completed": task.completed,
    }


def register_routes(app: Flask) -> None:
    """Register task-management routes on the application."""
    limiter = app.extensions["rate_limiter"]

    @app.route("/register", methods=["GET", "POST"])
    @limiter.limit("5 per minute", methods=["POST"])
    def register():
        """Create a student account and sign the student in."""
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        values = {"email": ""}
        errors: list[str] = []
        if request.method == "POST":
            values = request.form.to_dict()
            email = values.get("email", "").strip().lower()
            password = values.get("password", "")
            confirmation = values.get("password_confirmation", "")
            if "@" not in email or len(email) > 255:
                errors.append("Enter a valid email address.")
            if len(password) < 8:
                errors.append("Password must be at least 8 characters.")
            if password != confirmation:
                errors.append("Passwords must match.")

            with _session(app) as session:
                if not errors and session.scalar(select(User).where(User.email == email)):
                    errors.append("An account with that email already exists.")
                if not errors:
                    user = User(email=email, password_hash=generate_password_hash(password))
                    session.add(user)
                    session.flush()
                    if app.config.get("SEED_SAMPLE_DATA", True):
                        seed_sample_tasks(session, user.id)
                    session.commit()
                    login_user(user)
                    flash("Welcome to StudySprint Agent.", "success")
                    return redirect(url_for("index"))

        return render_template("register.html", values=values, errors=errors), 400 if errors else 200

    @app.route("/login", methods=["GET", "POST"])
    @limiter.limit("10 per minute", methods=["POST"])
    def login():
        """Authenticate an existing student account."""
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        values = {"email": ""}
        error = None
        if request.method == "POST":
            values = request.form.to_dict()
            email = values.get("email", "").strip().lower()
            with _session(app) as session:
                user = session.scalar(select(User).where(User.email == email))
                if user and check_password_hash(user.password_hash, values.get("password", "")):
                    login_user(user)
                    return redirect(url_for("index"))
            error = "Email or password is incorrect."

        return render_template("login.html", values=values, error=error), 401 if error else 200

    @app.post("/logout")
    @login_required
    def logout():
        """End the current student's session."""
        logout_user()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def index():
        with _session(app) as session:
            tasks = session.scalars(select(Task).where(Task.owner_id == current_user.id)).all()
        pending_tasks = prioritize_pending_tasks(tasks)
        completed_tasks = sorted(
            (task for task in tasks if task.completed),
            key=lambda task: (task.deadline or date.max, task.id or 0),
        )
        priority_by_id = {task.id: calculate_priority(task) for task in tasks}
        total_tasks = len(tasks)
        completed_count = len(completed_tasks)
        pending_count = len(pending_tasks)
        completion_percentage = round((completed_count / total_tasks) * 100) if total_tasks else 0
        return render_template(
            "index.html",
            pending_tasks=pending_tasks,
            completed_tasks=completed_tasks,
            priority_by_id=priority_by_id,
            total_tasks=total_tasks,
            pending_count=pending_count,
            completed_count=completed_count,
            completion_percentage=completion_percentage,
        )

    @app.route("/schedule", methods=["GET", "POST"])
    @login_required
    def schedule():
        """Generate a daily schedule from the student's available time."""
        values = {
            "available_time": "",
            "available_unit": "minutes",
        }
        errors: list[str] = []
        daily_schedule: DailySchedule | None = None

        if request.method == "POST":
            values = request.form.to_dict()
            try:
                available_minutes = parse_available_minutes(
                    values.get("available_time", ""), values.get("available_unit", "")
                )
            except ValueError as error:
                errors.append(str(error))
            else:
                with _session(app) as session:
                    tasks = session.scalars(select(Task).where(Task.owner_id == current_user.id)).all()
                daily_schedule = generate_daily_schedule(tasks, available_minutes)

        return render_template(
            "schedule.html",
            values=values,
            errors=errors,
            daily_schedule=daily_schedule,
        ), 400 if errors else 200

    @app.route("/tasks/new", methods=["GET", "POST"])
    @login_required
    def create_task():
        values = request.form.to_dict() if request.method == "POST" else _form_values()
        errors: dict[str, str] = {}
        if request.method == "POST":
            task_values, errors = validate_task_form(request.form)
            if not errors and task_values is not None:
                with _session(app) as session:
                    session.add(Task(owner_id=current_user.id, **task_values))
                    session.commit()
                flash("Task created.", "success")
                return redirect(url_for("index"))

        return render_template(
            "task_form.html",
            page_title="Add task",
            submit_label="Add task",
            values=values,
            errors=errors,
            urgency_levels=URGENCY_LEVELS,
        ), 400 if errors else 200

    @app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_task(task_id: int):
        with _session(app) as session:
            task = _owned_task(session, task_id)
            if task is None:
                return "Task not found", 404

            values = request.form.to_dict() if request.method == "POST" else _form_values(task)
            errors: dict[str, str] = {}
            if request.method == "POST":
                task_values, errors = validate_task_form(request.form)
                if not errors and task_values is not None:
                    for field, value in task_values.items():
                        setattr(task, field, value)
                    session.commit()
                    flash("Task updated.", "success")
                    return redirect(url_for("index"))

        return render_template(
            "task_form.html",
            page_title="Edit task",
            submit_label="Save changes",
            values=values,
            errors=errors,
            urgency_levels=URGENCY_LEVELS,
        ), 400 if errors else 200

    @app.post("/tasks/<int:task_id>/toggle")
    @login_required
    def toggle_task(task_id: int):
        with _session(app) as session:
            task = _owned_task(session, task_id)
            if task is None:
                return "Task not found", 404
            task.completed = not task.completed
            session.commit()
        flash("Task marked as completed." if task.completed else "Task marked as pending.", "success")
        return redirect(url_for("index"))

    @app.post("/tasks/<int:task_id>/delete")
    @login_required
    def delete_task(task_id: int):
        with _session(app) as session:
            task = _owned_task(session, task_id)
            if task is None:
                return "Task not found", 404
            session.delete(task)
            session.commit()
        flash("Task deleted.", "success")
        return redirect(url_for("index"))
