"""Unit tests for the progress module."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

import pytest

from ralph_gold.progress import (
    ProgressMetrics,
    calculate_progress,
    calculate_velocity,
    format_burndown_chart,
    format_progress_bar,
)


# Mock tracker for testing
class MockTracker:
    """Mock tracker for testing progress calculations."""

    def __init__(self, completed: int, total: int):
        self._completed = completed
        self._total = total

    def counts(self) -> tuple[int, int]:
        """Return (completed, total) task counts."""
        return (self._completed, self._total)


def test_calculate_progress_basic():
    """Test basic progress calculation with simple data."""
    tracker = MockTracker(completed=5, total=10)
    state = {
        "history": [
            {
                "timestamp": "2024-01-01T10:00:00",
                "gates_ok": True,
            },
            {
                "timestamp": "2024-01-02T10:00:00",
                "gates_ok": True,
            },
        ]
    }

    metrics = calculate_progress(tracker, state)

    assert metrics.total_tasks == 10
    assert metrics.completed_tasks == 5
    assert metrics.completion_percentage == 50.0
    assert metrics.velocity_tasks_per_day > 0


def test_calculate_progress_no_tasks():
    """Test progress calculation with zero tasks."""
    tracker = MockTracker(completed=0, total=0)
    state = {"history": []}

    metrics = calculate_progress(tracker, state)

    assert metrics.total_tasks == 0
    assert metrics.completed_tasks == 0
    assert metrics.completion_percentage == 0.0
    assert metrics.velocity_tasks_per_day == 0.0
    assert metrics.estimated_completion_date is None


def test_calculate_progress_all_complete():
    """Test progress calculation when all tasks are complete."""
    tracker = MockTracker(completed=10, total=10)
    state = {"history": []}

    metrics = calculate_progress(tracker, state)

    assert metrics.total_tasks == 10
    assert metrics.completed_tasks == 10
    assert metrics.completion_percentage == 100.0
    assert metrics.estimated_completion_date is None  # No remaining tasks


def test_calculate_progress_with_velocity():
    """Test progress calculation includes velocity-based ETA."""
    tracker = MockTracker(completed=5, total=10)

    # Create history with 5 successful iterations over 5 days
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    history = []
    for i in range(5):
        timestamp = base_time + timedelta(days=i)
        history.append(
            {
                "timestamp": timestamp.isoformat(),
                "gates_ok": True,
            }
        )

    state = {"history": history}
    metrics = calculate_progress(tracker, state)

    assert metrics.velocity_tasks_per_day > 0
    assert metrics.estimated_completion_date is not None
    # With 5 tasks remaining and velocity ~1.25 tasks/day, ETA should be ~4 days from now


def test_calculate_progress_no_velocity():
    """Test progress calculation when velocity cannot be calculated."""
    tracker = MockTracker(completed=5, total=10)
    state = {"history": []}  # No history

    metrics = calculate_progress(tracker, state)

    assert metrics.velocity_tasks_per_day == 0.0
    assert metrics.estimated_completion_date is None


def test_calculate_progress_empty_state():
    """Test progress calculation with empty state dict."""
    tracker = MockTracker(completed=3, total=10)
    state: Dict[str, Any] = {}

    metrics = calculate_progress(tracker, state)

    assert metrics.total_tasks == 10
    assert metrics.completed_tasks == 3
    assert metrics.velocity_tasks_per_day == 0.0


def test_format_progress_bar_basic():
    """Test basic progress bar formatting."""
    bar = format_progress_bar(12, 20, width=40)

    assert "Progress:" in bar
    assert "60%" in bar
    assert "(12/20 tasks)" in bar
    assert "█" in bar  # Filled portion
    assert "░" in bar  # Empty portion


def test_format_progress_bar_empty():
    """Test progress bar with no progress."""
    bar = format_progress_bar(0, 10, width=40)

    assert "0%" in bar
    assert "(0/10 tasks)" in bar
    # Should be all empty blocks
    assert bar.count("░") == 40


def test_format_progress_bar_full():
    """Test progress bar at 100% completion."""
    bar = format_progress_bar(10, 10, width=40)

    assert "100%" in bar
    assert "(10/10 tasks)" in bar
    # Should be all filled blocks
    assert bar.count("█") == 40


def test_format_progress_bar_zero_total():
    """Test progress bar with zero total tasks."""
    bar = format_progress_bar(0, 0, width=40)

    assert "0%" in bar
    assert "(0/0 tasks)" in bar


def test_format_progress_bar_width_variations():
    """Test progress bar with different widths."""
    # Small width
    bar_small = format_progress_bar(5, 10, width=20)
    assert bar_small.count("█") + bar_small.count("░") == 20

    # Large width
    bar_large = format_progress_bar(5, 10, width=80)
    assert bar_large.count("█") + bar_large.count("░") == 80


def test_format_progress_bar_proportions():
    """Test that progress bar proportions are accurate."""
    # 50% completion
    bar = format_progress_bar(5, 10, width=60)
    filled = bar.count("█")
    empty = bar.count("░")

    assert filled == 30  # 50% of 60
    assert empty == 30
    assert filled + empty == 60


def test_calculate_velocity_basic():
    """Test basic velocity calculation."""
    history = [
        {
            "timestamp": "2024-01-01T10:00:00",
            "gates_ok": True,
        },
        {
            "timestamp": "2024-01-02T10:00:00",
            "gates_ok": True,
        },
        {
            "timestamp": "2024-01-03T10:00:00",
            "gates_ok": True,
        },
    ]

    velocity = calculate_velocity(history)

    # 3 tasks over 2 days = 1.5 tasks/day
    assert velocity == pytest.approx(1.5, rel=0.01)


def test_calculate_velocity_empty_history():
    """Test velocity calculation with empty history."""
    velocity = calculate_velocity([])
    assert velocity == 0.0


def test_calculate_velocity_single_entry():
    """Test velocity calculation with single history entry."""
    history = [
        {
            "timestamp": "2024-01-01T10:00:00",
            "gates_ok": True,
        }
    ]

    velocity = calculate_velocity(history)
    assert velocity == 0.0  # Need at least 2 entries


def test_calculate_velocity_filters_failures():
    """Test that velocity only counts successful iterations."""
    history = [
        {
            "timestamp": "2024-01-01T10:00:00",
            "gates_ok": True,
        },
        {
            "timestamp": "2024-01-02T10:00:00",
            "gates_ok": False,  # Failed
        },
        {
            "timestamp": "2024-01-03T10:00:00",
            "gates_ok": True,
        },
    ]

    velocity = calculate_velocity(history)

    # Only 2 successful tasks over 2 days = 1.0 tasks/day
    assert velocity == pytest.approx(1.0, rel=0.01)


def test_calculate_velocity_same_day():
    """Test velocity calculation when all tasks completed same day."""
    history = [
        {
            "timestamp": "2024-01-01T10:00:00",
            "gates_ok": True,
        },
        {
            "timestamp": "2024-01-01T11:00:00",
            "gates_ok": True,
        },
    ]

    velocity = calculate_velocity(history)

    # Time span is less than a day, but we have 2 tasks
    # Velocity should be very high (tasks per day)
    assert velocity > 0


def test_calculate_velocity_invalid_timestamps():
    """Test velocity calculation with invalid timestamps."""
    history = [
        {
            "timestamp": "invalid",
            "gates_ok": True,
        },
        {
            "timestamp": "also-invalid",
            "gates_ok": True,
        },
    ]

    velocity = calculate_velocity(history)
    assert velocity == 0.0  # Can't parse timestamps


def test_calculate_velocity_missing_timestamps():
    """Test velocity calculation with missing timestamps."""
    history = [
        {
            "gates_ok": True,
            # No timestamp
        },
        {
            "gates_ok": True,
            # No timestamp
        },
    ]

    velocity = calculate_velocity(history)
    assert velocity == 0.0


def test_calculate_velocity_mixed_valid_invalid():
    """Test velocity with mix of valid and invalid timestamps."""
    history = [
        {
            "timestamp": "2024-01-01T10:00:00",
            "gates_ok": True,
        },
        {
            "timestamp": "invalid",
            "gates_ok": True,
        },
        {
            "timestamp": "2024-01-02T10:00:00",
            "gates_ok": True,
        },
    ]

    velocity = calculate_velocity(history)

    # Should calculate based on 2 valid timestamps
    assert velocity > 0


def test_format_burndown_chart_empty_history():
    """Test burndown chart with empty history."""
    chart = format_burndown_chart([])
    assert "No history data available" in chart


def test_format_burndown_chart_basic():
    """Test basic burndown chart formatting."""
    history = [
        {
            "timestamp": "2024-01-01T10:00:00",
            "gates_ok": True,
        },
        {
            "timestamp": "2024-01-02T10:00:00",
            "gates_ok": True,
        },
        {
            "timestamp": "2024-01-03T10:00:00",
            "gates_ok": True,
        },
    ]

    chart = format_burndown_chart(history, width=60, height=20)

    assert "Tasks" in chart
    assert "│" in chart  # Y-axis
    assert "└" in chart  # X-axis corner
    assert "─" in chart  # X-axis line
    assert "Day" in chart  # X-axis labels


def test_format_burndown_chart_insufficient_data():
    """Test burndown chart with insufficient data."""
    history = [
        {
            "timestamp": "invalid",
            "gates_ok": True,
        }
    ]

    chart = format_burndown_chart(history)
    assert "Insufficient data" in chart or "No task data" in chart


def test_format_burndown_chart_custom_dimensions():
    """Test burndown chart with custom width and height."""
    history = [
        {
            "timestamp": "2024-01-01T10:00:00",
            "gates_ok": True,
        },
        {
            "timestamp": "2024-01-02T10:00:00",
            "gates_ok": True,
        },
    ]

    chart = format_burndown_chart(history, width=40, height=15)

    # Verify chart structure
    lines = chart.split("\n")
    assert len(lines) > 10  # Should have multiple lines


def test_format_burndown_chart_filters_failures():
    """Test that burndown chart only includes successful iterations."""
    history = [
        {
            "timestamp": "2024-01-01T10:00:00",
            "gates_ok": True,
        },
        {
            "timestamp": "2024-01-02T10:00:00",
            "gates_ok": False,  # Should be filtered out
        },
        {
            "timestamp": "2024-01-03T10:00:00",
            "gates_ok": True,
        },
    ]

    chart = format_burndown_chart(history)

    # Should still generate a chart (not fail)
    assert "Tasks" in chart


def test_progress_metrics_dataclass():
    """Test ProgressMetrics dataclass creation."""
    metrics = ProgressMetrics(
        total_tasks=20,
        completed_tasks=12,
        in_progress_tasks=1,
        blocked_tasks=2,
        completion_percentage=60.0,
        velocity_tasks_per_day=1.5,
        estimated_completion_date="2024-02-01",
    )

    assert metrics.total_tasks == 20
    assert metrics.completed_tasks == 12
    assert metrics.in_progress_tasks == 1
    assert metrics.blocked_tasks == 2
    assert metrics.completion_percentage == 60.0
    assert metrics.velocity_tasks_per_day == 1.5
    assert metrics.estimated_completion_date == "2024-02-01"


def test_calculate_progress_eta_calculation():
    """Test ETA calculation logic in calculate_progress."""
    tracker = MockTracker(completed=7, total=10)

    # Create history with known velocity (1 task per day)
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    history = []
    for i in range(7):
        timestamp = base_time + timedelta(days=i)
        history.append(
            {
                "timestamp": timestamp.isoformat(),
                "gates_ok": True,
            }
        )

    state = {"history": history}
    metrics = calculate_progress(tracker, state)

    # 3 tasks remaining, velocity ~1.17 tasks/day
    # ETA should be approximately 2-3 days from now
    assert metrics.estimated_completion_date is not None

    # Parse the ETA date
    eta_date = datetime.fromisoformat(metrics.estimated_completion_date)
    days_until_eta = (eta_date - datetime.now()).days

    # Should be reasonable (between 1 and 5 days)
    assert 1 <= days_until_eta <= 5


def test_calculate_velocity_with_timezone():
    """Test velocity calculation with timezone-aware timestamps."""
    history = [
        {
            "timestamp": "2024-01-01T10:00:00Z",
            "gates_ok": True,
        },
        {
            "timestamp": "2024-01-02T10:00:00Z",
            "gates_ok": True,
        },
    ]

    velocity = calculate_velocity(history)

    # Should handle timezone correctly
    # 2 tasks over 1 day = 2.0 tasks/day
    assert velocity == pytest.approx(2.0, rel=0.01)


def test_format_progress_bar_edge_cases():
    """Test progress bar with edge case percentages."""
    # Very small percentage (1% of 60 = 0.6, rounds to 0)
    bar = format_progress_bar(1, 100, width=60)
    assert "1%" in bar
    # At 1%, the filled width is 0 (int(60 * 0.01) = 0), so no filled blocks
    assert "(1/100 tasks)" in bar

    # 99% completion
    bar = format_progress_bar(99, 100, width=60)
    assert "99%" in bar
    filled = bar.count("█")
    assert filled >= 59  # Should be almost full


def test_calculate_velocity_non_dict_entries():
    """Test velocity calculation skips non-dict entries gracefully."""
    history: List[Any] = [
        {
            "timestamp": "2024-01-01T10:00:00",
            "gates_ok": True,
        },
        "invalid",  # Non-dict entry
        {
            "timestamp": "2024-01-02T10:00:00",
            "gates_ok": True,
        },
    ]

    velocity = calculate_velocity(history)

    # Should calculate based on valid entries only
    assert velocity > 0


def test_format_burndown_chart_single_day():
    """Test burndown chart with all tasks on single day."""
    history = [
        {
            "timestamp": "2024-01-01T10:00:00",
            "gates_ok": True,
        },
        {
            "timestamp": "2024-01-01T11:00:00",
            "gates_ok": True,
        },
        {
            "timestamp": "2024-01-01T12:00:00",
            "gates_ok": True,
        },
    ]

    chart = format_burndown_chart(history)

    # Should still generate a chart
    assert "Tasks" in chart
    assert "Day 1" in chart


def test_calculate_progress_in_progress_tasks():
    """Test that in_progress_tasks is set correctly."""
    # With incomplete tasks
    tracker = MockTracker(completed=5, total=10)
    state = {"history": []}
    metrics = calculate_progress(tracker, state)
    assert metrics.in_progress_tasks == 1  # Assumes 1 in progress

    # With all tasks complete
    tracker = MockTracker(completed=10, total=10)
    metrics = calculate_progress(tracker, state)
    assert metrics.in_progress_tasks == 0  # No tasks in progress


def test_calculate_progress_blocked_tasks():
    """Test that blocked_tasks is initialized."""
    tracker = MockTracker(completed=5, total=10)
    state = {"history": []}
    metrics = calculate_progress(tracker, state)

    # Currently always 0 (would need PRD parsing for actual blocked count)
    assert metrics.blocked_tasks == 0
