"""Validation for task form values."""

from datetime import date


URGENCY_LEVELS = ("low", "medium", "high")


def validate_task_form(form: dict) -> tuple[dict | None, dict[str, str]]:
    """Return cleaned task values and user-friendly errors."""
    errors: dict[str, str] = {}
    title = form.get("title", "").strip()
    course = form.get("course", "").strip()
    deadline_text = form.get("deadline", "").strip()
    urgency = form.get("urgency", "").strip().lower()
    minutes_text = form.get("estimated_minutes", "").strip()
    notes = form.get("notes", "").strip()

    if not title:
        errors["title"] = "Enter a task title."
    elif len(title) > 200:
        errors["title"] = "The title must be 200 characters or fewer."

    if not course:
        errors["course"] = "Enter a course name."
    elif len(course) > 100:
        errors["course"] = "The course name must be 100 characters or fewer."

    try:
        deadline = date.fromisoformat(deadline_text)
    except ValueError:
        deadline = None
        errors["deadline"] = "Enter a valid deadline."

    if urgency not in URGENCY_LEVELS:
        errors["urgency"] = "Choose low, medium, or high urgency."

    try:
        estimated_minutes = int(minutes_text)
        if not 1 <= estimated_minutes <= 1440:
            raise ValueError
    except (TypeError, ValueError):
        estimated_minutes = None
        errors["estimated_minutes"] = "Study time must be between 1 and 1440 minutes."

    if errors:
        return None, errors

    return {
        "title": title,
        "course": course,
        "deadline": deadline,
        "urgency": urgency,
        "estimated_minutes": estimated_minutes,
        "notes": notes,
        "completed": form.get("completed") == "on",
    }, errors
