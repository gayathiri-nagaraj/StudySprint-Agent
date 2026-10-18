"""Flask-Login integration for StudySprint Agent."""

from flask import Flask
from flask_login import LoginManager

from .models import User


def init_login(app: Flask) -> LoginManager:
    """Configure Flask-Login and load users from the configured database."""
    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        try:
            numeric_id = int(user_id)
        except (TypeError, ValueError):
            return None
        with app.extensions["database_session_factory"]() as session:
            return session.get(User, numeric_id)

    return login_manager
