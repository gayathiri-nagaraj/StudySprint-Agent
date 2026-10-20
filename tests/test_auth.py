from datetime import date, timedelta

import pytest
from sqlalchemy import select
from werkzeug.middleware.proxy_fix import ProxyFix

from app import create_app, normalize_database_url
from app.models import Task, User
from app.security import init_security


PASSWORD = "correct-horse-battery"


@pytest.fixture()
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "DATABASE_URL": f"sqlite:///{(tmp_path / 'auth.db').as_posix()}",
            "SEED_SAMPLE_DATA": False,
        }
    )


def register(client, email):
    return client.post(
        "/register",
        data={"email": email, "password": PASSWORD, "password_confirmation": PASSWORD},
    )


def task_data(title):
    return {
        "title": title,
        "course": "Security 101",
        "deadline": (date.today() + timedelta(days=2)).isoformat(),
        "urgency": "high",
        "estimated_minutes": "30",
        "notes": "Private task",
    }


def test_registration_hashes_password_and_logs_user_in(app):
    client = app.test_client()

    response = register(client, "alice@example.com")

    assert response.status_code == 302
    assert response.location == "/"
    with app.extensions["database_session_factory"]() as session:
        user = session.scalar(select(User).where(User.email == "alice@example.com"))
        assert user is not None
        assert user.password_hash != PASSWORD
        assert user.password_hash.startswith("scrypt:") or user.password_hash.startswith("pbkdf2:")


def test_login_and_logout(app):
    client = app.test_client()
    register(client, "alice@example.com")
    client.post("/logout")

    login_response = client.post("/login", data={"email": "alice@example.com", "password": PASSWORD})
    logout_response = client.post("/logout")

    assert login_response.status_code == 302
    assert login_response.location == "/"
    assert logout_response.status_code == 302
    assert logout_response.location == "/login"


def test_dashboard_task_and_schedule_routes_require_authentication(app):
    client = app.test_client()

    for path in ["/", "/tasks/new", "/schedule"]:
        response = client.get(path)
        assert response.status_code == 302
        assert response.location.startswith("/login?next=")


def test_users_cannot_access_or_change_each_others_tasks(app):
    alice = app.test_client()
    bob = app.test_client()
    register(alice, "alice@example.com")
    alice.post("/tasks/new", data=task_data("Alice private task"))
    with app.extensions["database_session_factory"]() as session:
        alice_task = session.scalar(select(Task).where(Task.title == "Alice private task"))
        task_id = alice_task.id

    register(bob, "bob@example.com")
    dashboard = bob.get("/")
    schedule = bob.post("/schedule", data={"available_time": "60", "available_unit": "minutes"})

    assert b"Alice private task" not in dashboard.data
    assert b"Alice private task" not in schedule.data
    assert bob.get(f"/tasks/{task_id}/edit").status_code == 404
    assert bob.post(f"/tasks/{task_id}/toggle").status_code == 404
    assert bob.post(f"/tasks/{task_id}/delete").status_code == 404

    with app.extensions["database_session_factory"]() as session:
        assert session.get(Task, task_id) is not None


def test_csrf_rejects_state_change_without_token(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": True,
            "DATABASE_URL": f"sqlite:///{(tmp_path / 'csrf.db').as_posix()}",
            "SEED_SAMPLE_DATA": False,
        }
    )
    client = app.test_client()

    response = client.post("/register", data={"email": "alice@example.com", "password": PASSWORD, "password_confirmation": PASSWORD})

    assert response.status_code == 400
    assert b"CSRF token is missing" in response.data


def test_production_rejects_sqlite_and_memory_rate_limits(monkeypatch, tmp_path):
    import pytest

    monkeypatch.setenv("SECRET_KEY", "environment-production-secret")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_app(
            {
                "TESTING": True,
                "APP_ENV": "production",
                "SECRET_KEY": "environment-production-secret",
                "DATABASE_URL": f"sqlite:///{(tmp_path / 'production.db').as_posix()}",
                "SEED_SAMPLE_DATA": False,
                "WTF_CSRF_ENABLED": False,
                "RATE_LIMIT_STORAGE_URI": "redis://localhost:6379/0",
            }
        )

    with pytest.raises(RuntimeError, match="RATE_LIMIT_STORAGE_URI"):
        create_app(
            {
                "TESTING": True,
                "APP_ENV": "production",
                "SECRET_KEY": "environment-production-secret",
                "DATABASE_URL": "postgresql+psycopg2://user:pass@localhost/db",
                "SEED_SAMPLE_DATA": False,
                "WTF_CSRF_ENABLED": False,
                "RATE_LIMIT_STORAGE_URI": "memory://",
            }
        )


def test_security_headers_are_present(app):
    response = app.test_client().get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_configured_trusted_proxy_wraps_wsgi_app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "TRUSTED_PROXY_HOPS": 1,
            "DATABASE_URL": f"sqlite:///{(tmp_path / 'proxy.db').as_posix()}",
            "SEED_SAMPLE_DATA": False,
        }
    )

    assert isinstance(app.wsgi_app, ProxyFix)


def test_production_security_headers_include_hsts():
    from flask import Flask

    secure_app = Flask(__name__)
    secure_app.config.update(
        APP_ENV="production",
        RATELIMIT_ENABLED=False,
        RATE_LIMIT_STORAGE_URI="memory://",
    )
    init_security(secure_app)

    @secure_app.get("/")
    def secure_health():
        return "ok"

    response = secure_app.test_client().get("/")

    assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")


def test_render_postgres_urls_use_the_installed_psycopg2_driver():
    assert normalize_database_url("postgres://user:pass@host/db") == "postgresql+psycopg2://user:pass@host/db"
    assert normalize_database_url("postgresql://user:pass@host/db") == "postgresql+psycopg2://user:pass@host/db"
    assert normalize_database_url("postgresql+psycopg2://user:pass@host/db") == "postgresql+psycopg2://user:pass@host/db"
    assert normalize_database_url("sqlite:///studysprint.db") == "sqlite:///studysprint.db"


def test_login_rate_limit_returns_429_when_enabled(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": True,
            "RATE_LIMIT_STORAGE_URI": "memory://",
            "DATABASE_URL": f"sqlite:///{(tmp_path / 'rate-limit.db').as_posix()}",
            "SEED_SAMPLE_DATA": False,
        }
    )
    client = app.test_client()

    responses = [
        client.post("/login", data={"email": "unknown@example.com", "password": PASSWORD})
        for _ in range(11)
    ]

    assert responses[-1].status_code == 429
