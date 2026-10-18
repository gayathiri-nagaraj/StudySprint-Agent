"""Migrate a pre-authentication SQLite database without deleting its tasks.

Before running this script, make a file backup. It assigns every existing task
to the supplied legacy owner account so those records remain accessible after
authentication is enabled.
"""

import os
import sys

from sqlalchemy import create_engine, inspect, text
from werkzeug.security import generate_password_hash

from app.config import Config
from app.models import Base


def migrate() -> None:
    """Add the users table and owner_id column, preserving all task rows."""
    email = os.environ.get("LEGACY_OWNER_EMAIL", "").strip().lower()
    password = os.environ.get("LEGACY_OWNER_PASSWORD", "")
    if "@" not in email or len(email) > 255:
        raise SystemExit("Set a valid LEGACY_OWNER_EMAIL before running migration.")
    if len(password) < 8:
        raise SystemExit("LEGACY_OWNER_PASSWORD must be at least 8 characters.")
    if not Config.DATABASE_URL.startswith("sqlite:///"):
        raise SystemExit("migrate_auth.py currently supports SQLite databases only.")

    engine = create_engine(Config.DATABASE_URL, future=True)
    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        Base.metadata.create_all(engine)
        print("No legacy tasks table found; created the current schema.")
        return

    with engine.begin() as connection:
        Base.metadata.tables["users"].create(connection, checkfirst=True)
        task_columns = {column["name"] for column in inspect(connection).get_columns("tasks")}
        if "owner_id" not in task_columns:
            connection.execute(text("ALTER TABLE tasks ADD COLUMN owner_id INTEGER"))

        user_id = connection.execute(
            text("SELECT id FROM users WHERE email = :email"), {"email": email}
        ).scalar_one_or_none()
        if user_id is None:
            connection.execute(
                text("INSERT INTO users (email, password_hash) VALUES (:email, :password_hash)"),
                {"email": email, "password_hash": generate_password_hash(password)},
            )
            user_id = connection.execute(
                text("SELECT id FROM users WHERE email = :email"), {"email": email}
            ).scalar_one()

        connection.execute(
            text("UPDATE tasks SET owner_id = :owner_id WHERE owner_id IS NULL"),
            {"owner_id": user_id},
        )
        unowned = connection.execute(text("SELECT count(*) FROM tasks WHERE owner_id IS NULL")).scalar_one()
        if unowned:
            raise RuntimeError(f"Migration stopped: {unowned} tasks still have no owner.")

    print(f"Migrated SQLite database successfully. Existing tasks belong to {email}.")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as error:
        print(f"Migration failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
