"""Small database helpers for the Flask application."""

from datetime import date, timedelta

from sqlalchemy import Engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Task


class MigrationRequiredError(RuntimeError):
    """Raised when an existing pre-authentication database needs migration."""


def create_database(engine: Engine, seed_samples: bool = True) -> None:
    """Create a new schema, or stop safely before touching a legacy schema."""
    inspector = inspect(engine)
    if "tasks" in inspector.get_table_names():
        task_columns = {column["name"] for column in inspector.get_columns("tasks")}
        if "owner_id" not in task_columns:
            raise MigrationRequiredError(
                "This database predates authentication. Run migrate_auth.py with "
                "LEGACY_OWNER_EMAIL and LEGACY_OWNER_PASSWORD before starting the app."
            )

    Base.metadata.create_all(engine)


def seed_sample_tasks(session: Session, owner_id: int) -> None:
    """Add the familiar sample tasks once for a newly registered student."""
    if session.query(Task).filter(Task.owner_id == owner_id).count():
        return

    today = date.today()
    session.add_all(
        [
            Task(owner_id=owner_id, title="Read biology chapter 4", course="Biology 101", deadline=today + timedelta(days=2), urgency="high", estimated_minutes=60, notes="Review the diagrams before starting the quiz."),
            Task(owner_id=owner_id, title="Outline history essay", course="History 202", deadline=today + timedelta(days=5), urgency="medium", estimated_minutes=90, notes="Choose a primary source for the introduction."),
            Task(owner_id=owner_id, title="Practice calculus problems", course="Calculus II", deadline=today + timedelta(days=7), urgency="low", estimated_minutes=45, notes="Complete problems 1–12 from the review sheet."),
        ]
    )
    session.commit()


def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a session factory for the configured engine."""
    return sessionmaker(bind=engine, expire_on_commit=False)
