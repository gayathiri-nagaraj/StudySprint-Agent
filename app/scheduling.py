"""Deterministic daily study schedule generation."""

from dataclasses import dataclass
from datetime import date

from .models import Task
from .priority import PriorityResult, calculate_priority, prioritize_pending_tasks


@dataclass(frozen=True)
class ScheduledTask:
    """One task selected for today's schedule."""

    task: Task
    allocated_minutes: int
    priority: PriorityResult


@dataclass(frozen=True)
class UnscheduledTask:
    """A pending task that could not fit in today's schedule."""

    task: Task
    priority: PriorityResult
    reason: str


@dataclass(frozen=True)
class DailySchedule:
    """The complete result of one schedule generation request."""

    available_minutes: int
    scheduled: tuple[ScheduledTask, ...]
    unscheduled: tuple[UnscheduledTask, ...]

    @property
    def used_minutes(self) -> int:
        return sum(item.allocated_minutes for item in self.scheduled)

    @property
    def remaining_minutes(self) -> int:
        return self.available_minutes - self.used_minutes


def generate_daily_schedule(
    tasks: list[Task], available_minutes: int, today: date | None = None
) -> DailySchedule:
    """Greedily schedule complete tasks in priority order.

    Completed tasks are ignored. Each pending task is either scheduled in full
    or placed in the unscheduled list; this avoids implying that a task is
    finished when only part of its estimate was allocated. A task that needs
    more time than the remaining daily capacity is skipped, and later tasks
    are evaluated against that same remaining capacity.
    """
    if available_minutes < 0:
        raise ValueError("available_minutes must not be negative")

    ordered_tasks = prioritize_pending_tasks(tasks, today)
    scheduled: list[ScheduledTask] = []
    unscheduled: list[UnscheduledTask] = []
    remaining = available_minutes

    for task in ordered_tasks:
        priority = calculate_priority(task, today)
        task_minutes = max(task.estimated_minutes or 0, 0)
        if task_minutes <= remaining:
            scheduled.append(ScheduledTask(task, task_minutes, priority))
            remaining -= task_minutes
        else:
            if remaining == 0:
                reason = "No study time remains today."
            else:
                reason = f"Needs {task_minutes} minutes, but only {remaining} minutes remain today."
            unscheduled.append(UnscheduledTask(task, priority, reason))

    return DailySchedule(available_minutes, tuple(scheduled), tuple(unscheduled))


def parse_available_minutes(value: str, unit: str) -> int:
    """Convert a user-entered number of minutes or hours to minutes."""
    try:
        amount = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Enter a valid available study time.") from error

    if amount <= 0:
        raise ValueError("Available study time must be greater than zero.")
    if unit == "hours":
        minutes = amount * 60
    elif unit == "minutes":
        minutes = amount
    else:
        raise ValueError("Choose minutes or hours.")

    if not minutes.is_integer() or minutes > 1440:
        raise ValueError("Available study time must be a whole number up to 1440 minutes.")
    return int(minutes)
