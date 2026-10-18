from datetime import date, timedelta

import pytest

from app.models import Task
from app.scheduling import generate_daily_schedule, parse_available_minutes


TODAY = date(2026, 1, 15)


def make_task(task_id: int, title: str, **overrides) -> Task:
    values = {
        "id": task_id,
        "title": title,
        "course": "Course 101",
        "deadline": TODAY + timedelta(days=10),
        "urgency": "low",
        "estimated_minutes": 30,
        "notes": "",
        "completed": False,
    }
    values.update(overrides)
    return Task(**values)


def test_schedule_uses_priority_order_and_deadlines():
    later_high = make_task(1, "Later high", urgency="high", estimated_minutes=30)
    due_today_low = make_task(2, "Due today", deadline=TODAY, estimated_minutes=30)

    schedule = generate_daily_schedule([later_high, due_today_low], 60, TODAY)

    assert [item.task.title for item in schedule.scheduled] == ["Due today", "Later high"]
    assert [item.priority.label for item in schedule.scheduled] == ["Medium", "Medium"]


def test_schedule_never_exceeds_available_time_or_task_estimate():
    first = make_task(1, "First", urgency="high", estimated_minutes=45)
    second = make_task(2, "Second", urgency="medium", estimated_minutes=45)

    schedule = generate_daily_schedule([first, second], 60, TODAY)

    assert schedule.used_minutes == 45
    assert schedule.remaining_minutes == 15
    assert all(item.allocated_minutes <= item.task.estimated_minutes for item in schedule.scheduled)


def test_completed_tasks_are_not_scheduled():
    completed = make_task(1, "Already done", completed=True, deadline=TODAY - timedelta(days=1), urgency="high")

    schedule = generate_daily_schedule([completed], 60, TODAY)

    assert schedule.scheduled == ()
    assert schedule.unscheduled == ()


def test_task_that_does_not_fit_is_explained_as_unscheduled():
    task = make_task(1, "Long reading", estimated_minutes=90)

    schedule = generate_daily_schedule([task], 60, TODAY)

    assert schedule.scheduled == ()
    assert schedule.unscheduled[0].task.title == "Long reading"
    assert "Needs 90 minutes" in schedule.unscheduled[0].reason
    assert "only 60 minutes" in schedule.unscheduled[0].reason


def test_overdue_task_is_scheduled_first_and_reason_is_preserved():
    overdue = make_task(1, "Overdue essay", deadline=TODAY - timedelta(days=1), estimated_minutes=30)
    future = make_task(2, "Future essay", deadline=TODAY + timedelta(days=5), estimated_minutes=30)

    schedule = generate_daily_schedule([future, overdue], 30, TODAY)

    assert schedule.scheduled[0].task.title == "Overdue essay"
    assert "overdue" in schedule.scheduled[0].priority.explanation
    assert schedule.unscheduled[0].task.title == "Future essay"


def test_available_time_accepts_minutes_and_hours():
    assert parse_available_minutes("90", "minutes") == 90
    assert parse_available_minutes("2", "hours") == 120


@pytest.mark.parametrize("value, unit", [("", "minutes"), ("0", "minutes"), ("2.5", "minutes"), ("25", "hours")])
def test_available_time_rejects_invalid_values(value, unit):
    with pytest.raises(ValueError):
        parse_available_minutes(value, unit)
