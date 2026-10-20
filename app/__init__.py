"""Application factory for the StudySprint Agent Flask app."""

import os

from flask import Flask
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import create_engine

from .config import Config
from .database import create_database, session_factory
from .auth import init_login
from .routes import register_routes
from .security import init_security


def normalize_database_url(database_url: str) -> str:
    """Use psycopg2 explicitly for Render/PostgreSQL URLs.

    Render commonly supplies DATABASE_URL as ``postgres://`` or
    ``postgresql://``. SQLAlchemy otherwise defaults those URLs to the
    psycopg2 dialect, so the production dependency and URL are kept aligned.
    SQLite URLs are returned unchanged for local development and tests.
    """
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg2://" + database_url.removeprefix("postgres://")
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + database_url.removeprefix("postgresql://")
    return database_url


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure a StudySprint Flask application."""
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(Config)

    if test_config is not None:
        app.config.update(test_config)

    if app.config["APP_ENV"] == "production" and not os.environ.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set through the environment in production.")
    if app.config["APP_ENV"] == "production" and app.config["RATE_LIMIT_STORAGE_URI"].startswith("memory://"):
        raise RuntimeError("RATE_LIMIT_STORAGE_URI must use shared storage in production.")
    if app.config["APP_ENV"] == "production" and not app.config["DATABASE_URL"].startswith(("postgres://", "postgresql://", "postgresql+psycopg2://")):
        raise RuntimeError("DATABASE_URL must point to PostgreSQL in production.")
    app.config["SESSION_COOKIE_SECURE"] = app.config["APP_ENV"] == "production"
    app.config["REMEMBER_COOKIE_SECURE"] = app.config["APP_ENV"] == "production"

    database_url = normalize_database_url(app.config["DATABASE_URL"])
    if database_url.startswith("sqlite:///"):
        database_path = database_url.removeprefix("sqlite:///")
        if database_path not in {":memory:", ""}:
            os.makedirs(os.path.dirname(database_path) or ".", exist_ok=True)

    engine = create_engine(database_url, future=True)
    create_database(engine, seed_samples=app.config.get("SEED_SAMPLE_DATA", True))
    app.extensions["database_engine"] = engine
    app.extensions["database_session_factory"] = session_factory(engine)
    CSRFProtect(app)
    init_login(app)
    app.extensions["rate_limiter"] = init_security(app)

    @app.get("/health")
    def health_check() -> tuple[dict[str, str], int]:
        """Return a small response that confirms the app is running."""
        return {"status": "ok", "service": "studysprint-agent"}, 200

    register_routes(app)
    return app
