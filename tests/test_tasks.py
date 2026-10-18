from datetime import date, timedelta

import pytest

from app import create_app
from app.models import Task


@pytest.fixture()
def app(tmp_path):
    database_path = (tmp_path / "tasks.db").as_posix()
    return create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "DATABASE_URL": f"sqlite:///{database_path}",
            "SEED_SAMPLE_DATA": False,
        }
    )


@pytest.fixture()
def client(app):
    client = app.test_client()
    response = client.post(
        "/register",
        data={
            "email": "student@example.com",
            "password": "correct-horse-battery",
            "password_confirmation": "correct-horse-battery",
        },
    )
    assert response.status_code == 302
    return client


def task_form(**overrides):
    values = {
        "title": "Finish lab report",
        "course": "Chemistry 101",
        "deadline": (date.today() + timedelta(days=3)).isoformat(),
        "urgency": "high",
        "estimated_minutes": "90",
        "notes": "Check the results section.",
    }
    values.update(overrides)
    return values


def test_create_and_view_task(client):
    response = client.post("/tasks/new", data=task_form(), follow_redirects=True)

    assert response.status_code == 200
    assert b"Finish lab report" in response.data
    assert b"Chemistry 101" in response.data
    assert b">High<" in response.data
    assert b"Why:" in response.data
    assert b"Urgency" in response.data
    assert b"0%" in response.data
    assert b"aria-label=\"Task completion progress\"" in response.data


def test_dashboard_progress_uses_pending_and_completed_counts(client, app):
    client.post("/tasks/new", data=task_form(title="Pending task"))
    client.post("/tasks/new", data=task_form(title="Completed task"))
    with app.extensions["database_session_factory"]() as session:
        task = session.query(Task).filter_by(title="Completed task").one()
        task_id = task.id

    client.post(f"/tasks/{task_id}/toggle")
    response = client.get("/")

    assert response.status_code == 200
    assert b">50%<" in response.data
    assert b">1<" in response.data
    assert b"pending" in response.data
    assert b"completed" in response.data


def test_dashboard_progress_handles_zero_tasks(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b">0%<" in response.data
    assert b">0<" in response.data


def test_edit_task(client, app):
    client.post("/tasks/new", data=task_form())
    with app.extensions["database_session_factory"]() as session:
        task = session.query(Task).one()
        task_id = task.id

    response = client.post(
        f"/tasks/{task_id}/edit",
        data=task_form(title="Revised lab report", course="Chemistry 102"),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Revised lab report" in response.data
    assert b"Chemistry 102" in response.data
    assert b"Finish lab report" not in response.data


def test_complete_task(client, app):
    client.post("/tasks/new", data=task_form())
    with app.extensions["database_session_factory"]() as session:
        task_id = session.query(Task).one().id

    response = client.post(f"/tasks/{task_id}/toggle", follow_redirects=True)

    assert response.status_code == 200
    assert b"Completed" in response.data
    with app.extensions["database_session_factory"]() as session:
        assert session.get(Task, task_id).completed is True


def test_delete_task(client, app):
    client.post("/tasks/new", data=task_form())
    with app.extensions["database_session_factory"]() as session:
        task_id = session.query(Task).one().id

    response = client.post(f"/tasks/{task_id}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Finish lab report" not in response.data
    with app.extensions["database_session_factory"]() as session:
        assert session.get(Task, task_id) is None


def test_invalid_task_is_rejected(client):
    response = client.post("/tasks/new", data=task_form(deadline="not-a-date", estimated_minutes="0"))

    assert response.status_code == 400
    assert b"Enter a valid deadline" in response.data
    assert b"between 1 and 1440 minutes" in response.data


def test_tasks_persist_after_application_restart(tmp_path):
    database_path = (tmp_path / "persistent.db").as_posix()
    config = {
        "TESTING": True,
        "DATABASE_URL": f"sqlite:///{database_path}",
        "SEED_SAMPLE_DATA": False,
    }
    first_app = create_app({**config, "WTF_CSRF_ENABLED": False})
    first_client = first_app.test_client()
    first_client.post("/register", data={"email": "student@example.com", "password": "correct-horse-battery", "password_confirmation": "correct-horse-battery"})
    first_client.post("/tasks/new", data=task_form())

    restarted_app = create_app({**config, "WTF_CSRF_ENABLED": False})
    restarted_client = restarted_app.test_client()
    restarted_client.post("/login", data={"email": "student@example.com", "password": "correct-horse-battery"})
    response = restarted_client.get("/")

    assert response.status_code == 200
    assert b"Finish lab report" in response.data


def test_sample_tasks_are_added_once_when_database_is_empty(tmp_path):
    database_path = (tmp_path / "samples.db").as_posix()
    config = {
        "TESTING": True,
        "DATABASE_URL": f"sqlite:///{database_path}",
        "SEED_SAMPLE_DATA": True,
    }

    first_app = create_app({**config, "WTF_CSRF_ENABLED": False})
    with first_app.extensions["database_session_factory"]() as session:
        assert session.query(Task).count() == 0

    first_client = first_app.test_client()
    first_client.post("/register", data={"email": "student@example.com", "password": "correct-horse-battery", "password_confirmation": "correct-horse-battery"})

    second_app = create_app({**config, "WTF_CSRF_ENABLED": False})
    with second_app.extensions["database_session_factory"]() as session:
        assert session.query(Task).count() == 3
