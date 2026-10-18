from datetime import date, timedelta

from app.models import Task
from app.priority import calculate_priority, prioritize_pending_tasks


TODAY = date(2026, 1, 15)


def make_task(task_id=1, **overrides):
    values = {
        "id": task_id,
        "title": "Study task",
        "course": "Course 101",
        "deadline": TODAY + timedelta(days=30),
        "urgency": "low",
        "estimated_minutes": 30,
        "notes": "",
        "completed": False,
    }
    values.update(overrides)
    return Task(**values)


def test_each_priority_label_is_deterministic():
    assert calculate_priority(make_task(deadline=TODAY - timedelta(days=1), urgency="high", estimated_minutes=180), TODAY).label == "Critical"
    assert calculate_priority(make_task(deadline=TODAY + timedelta(days=20), urgency="high", estimated_minutes=180), TODAY).label == "High"
    assert calculate_priority(make_task(deadline=TODAY, urgency="low", estimated_minutes=30), TODAY).label == "Medium"
    assert calculate_priority(make_task(deadline=TODAY + timedelta(days=30)), TODAY).label == "Low"


def test_overdue_task_gets_deadline_explanation():
    result = calculate_priority(make_task(deadline=TODAY - timedelta(days=2)), TODAY)

    assert result.score == 65
    assert result.label == "High"
    assert "overdue" in result.explanation


def test_same_day_deadline_gets_today_explanation():
    result = calculate_priority(make_task(deadline=TODAY, urgency="high"), TODAY)

    assert result.score == 85
    assert result.label == "Critical"
    assert "today" in result.explanation


def test_pending_tasks_use_earlier_deadline_as_a_tie_breaker():
    later = make_task(task_id=1, deadline=TODAY + timedelta(days=2))
    earlier = make_task(task_id=2, deadline=TODAY + timedelta(days=1))

    assert prioritize_pending_tasks([later, earlier], TODAY) == [earlier, later]


def test_id_is_final_stable_tie_breaker():
    first = make_task(task_id=1)
    second = make_task(task_id=2)

    assert prioritize_pending_tasks([second, first], TODAY) == [first, second]


def test_completed_tasks_are_not_prioritized():
    task = make_task(completed=True, deadline=TODAY - timedelta(days=10), urgency="high")

    result = calculate_priority(task, TODAY)

    assert result.score == 0
    assert result.label == "Completed"
    assert "not prioritized" in result.explanation
    assert prioritize_pending_tasks([task], TODAY) == []


def test_missing_deadline_is_safe_if_a_task_allows_one():
    result = calculate_priority(make_task(deadline=None), TODAY)

    assert result.score == 15
    assert result.label == "Low"
    assert "No deadline" in result.explanation
