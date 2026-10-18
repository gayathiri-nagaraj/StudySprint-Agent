from datetime import date, timedelta

from app import create_app


def task_data(title: str, **overrides):
    values = {
        "title": title,
        "course": "Course 101",
        "deadline": (date.today() + timedelta(days=2)).isoformat(),
        "urgency": "medium",
        "estimated_minutes": "30",
        "notes": "",
    }
    values.update(overrides)
    return values


def make_app(tmp_path, seed=False):
    return create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "DATABASE_URL": f"sqlite:///{(tmp_path / 'schedule-page.db').as_posix()}",
            "SEED_SAMPLE_DATA": seed,
            "WTF_CSRF_ENABLED": False,
        }
    )


def authenticated_client(app):
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


def test_schedule_page_renders_timeline_in_existing_schedule_order(tmp_path):
    app = make_app(tmp_path)
    client = authenticated_client(app)
    client.post("/tasks/new", data=task_data("Urgent reading", urgency="high", estimated_minutes="30"))
    client.post("/tasks/new", data=task_data("Long project", urgency="low", estimated_minutes="45"))

    response = client.post(
        "/schedule",
        data={"available_time": "60", "available_unit": "minutes"},
    )
    page = response.data

    assert response.status_code == 200
    assert b"study-timeline" in page
    assert b"Tasks are shown in priority order" in page
    assert page.index(b"Urgent reading") < page.index(b"Long project")
    assert b"30 min" in page
    assert b"Deadline" in page
    assert b"badge-high" in page
    assert b"Not scheduled today" in page
    assert b"Needs 45 minutes" in page
    assert b"Scheduled" in page and b"60 min" in page


def test_schedule_page_shows_empty_state_when_no_tasks_fit(tmp_path):
    app = make_app(tmp_path)
    response = authenticated_client(app).post(
        "/schedule",
        data={"available_time": "60", "available_unit": "minutes"},
    )

    assert response.status_code == 200
    assert b"No pending tasks to schedule" in response.data
    assert b"study-timeline" not in response.data
