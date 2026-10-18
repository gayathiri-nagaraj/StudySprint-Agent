"""Deterministic priority scoring for pending study tasks.

The score is the sum of three independent parts:

* Deadline proximity: overdue 60, today 50, 1–2 days 40, 3–7 days 30,
  8–14 days 20, and later or missing 10 points.
* User urgency: low 0, medium 15, and high 30 points.
* Estimated study time: 1–30 minutes 5, 31–60 minutes 10, 61–120 minutes
  15, and more than 120 minutes 20 points.

Labels use the total score: Critical (80+), High (60–79), Medium (35–59),
and Low (below 35). Completed tasks receive score 0 and the label Completed.
"""

from dataclasses import dataclass
from datetime import date

from .models import Task


@dataclass(frozen=True)
class PriorityResult:
    """The score and explanation shown to a user for one task."""

    score: int
    label: str
    explanation: str


def _deadline_points(deadline: date | None, today: date) -> tuple[int, str]:
    if deadline is None:
        return 10, "No deadline is set"

    days_left = (deadline - today).days
    if days_left < 0:
        return 60, "The deadline is overdue"
    if days_left == 0:
        return 50, "The deadline is today"
    if days_left <= 2:
        return 40, "The deadline is within 2 days"
    if days_left <= 7:
        return 30, "The deadline is within a week"
    if days_left <= 14:
        return 20, "The deadline is within 2 weeks"
    return 10, "The deadline is more than 2 weeks away"


def _urgency_points(urgency: str | None) -> tuple[int, str]:
    points_by_urgency = {"low": 0, "medium": 15, "high": 30}
    normalized = (urgency or "low").lower()
    points = points_by_urgency.get(normalized, 0)
    return points, f"{normalized.capitalize()} user urgency"


def _study_time_points(minutes: int | None) -> tuple[int, str]:
    minutes = minutes or 0
    if minutes <= 30:
        return 5, "short study time"
    if minutes <= 60:
        return 10, "moderate study time"
    if minutes <= 120:
        return 15, "substantial study time"
    return 20, "long study time"


def calculate_priority(task: Task, today: date | None = None) -> PriorityResult:
    """Calculate a task's deterministic priority and a plain-language reason."""
    if task.completed:
        return PriorityResult(0, "Completed", "This task is completed and is not prioritized")

    today = today or date.today()
    deadline_points, deadline_reason = _deadline_points(task.deadline, today)
    urgency_points, urgency_reason = _urgency_points(task.urgency)
    time_points, time_reason = _study_time_points(task.estimated_minutes)
    score = deadline_points + urgency_points + time_points

    if score >= 80:
        label = "Critical"
    elif score >= 60:
        label = "High"
    elif score >= 35:
        label = "Medium"
    else:
        label = "Low"

    explanation = f"{deadline_reason}; {urgency_reason.lower()}; {time_reason}."
    return PriorityResult(score, label, explanation)


def task_sort_key(task: Task, today: date | None = None) -> tuple:
    """Return a stable key: score, deadline, urgency, time, then id."""
    result = calculate_priority(task, today)
    deadline = task.deadline or date.max
    urgency_rank = {"low": 0, "medium": 1, "high": 2}.get((task.urgency or "low").lower(), 0)
    return (-result.score, deadline, -urgency_rank, -(task.estimated_minutes or 0), task.id or 0)


def prioritize_pending_tasks(tasks: list[Task], today: date | None = None) -> list[Task]:
    """Sort only pending tasks; completed tasks are intentionally excluded."""
    return sorted((task for task in tasks if not task.completed), key=lambda task: task_sort_key(task, today))
