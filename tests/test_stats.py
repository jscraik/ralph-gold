"""Unit tests for the stats module."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict

import pytest

from ralph_gold.stats import (
    IterationStats,
    TaskStats,
    calculate_stats,
    export_stats_csv,
    format_stats_report,
)


def test_task_stats_success_rate():
    """Test TaskStats success_rate property calculation."""
    task = TaskStats(
        task_id="task-1",
        attempts=10,
        successes=7,
        failures=3,
        avg_duration_seconds=45.5,
        total_duration_seconds=455.0,
    )
    assert task.success_rate == 0.7

    # Zero attempts edge case
    task_zero = TaskStats(
        task_id="task-2",
        attempts=0,
        successes=0,
        failures=0,
        avg_duration_seconds=0.0,
        total_duration_seconds=0.0,
    )
    assert task_zero.success_rate == 0.0


def test_calculate_stats_empty_history():
    """Test calculate_stats with empty history."""
    state = {"history": []}
    stats = calculate_stats(state)

    assert stats.total_iterations == 0
    assert stats.successful_iterations == 0
    assert stats.failed_iterations == 0
    assert stats.avg_duration_seconds == 0.0
    assert stats.min_duration_seconds == 0.0
    assert stats.max_duration_seconds == 0.0
    assert stats.success_rate == 0.0
    assert len(stats.task_stats) == 0


def test_calculate_stats_missing_history():
    """Test calculate_stats with missing history field."""
    state: Dict[str, Any] = {}
    stats = calculate_stats(state)

    assert stats.total_iterations == 0
    assert stats.successful_iterations == 0
    assert stats.failed_iterations == 0


def test_calculate_stats_invalid_history():
    """Test calculate_stats with invalid history type."""
    state = {"history": "not a list"}
    with pytest.raises(ValueError, match="state.history must be a list"):
        calculate_stats(state)


def test_calculate_stats_single_iteration():
    """Test calculate_stats with a single iteration."""
    state = {
        "history": [
            {
                "iteration": 1,
                "duration_seconds": 120.5,
                "gates_ok": True,
                "blocked": False,
                "story_id": "task-1",
            }
        ]
    }
    stats = calculate_stats(state)

    assert stats.total_iterations == 1
    assert stats.successful_iterations == 1
    assert stats.failed_iterations == 0
    assert stats.avg_duration_seconds == 120.5
    assert stats.min_duration_seconds == 120.5
    assert stats.max_duration_seconds == 120.5
    assert stats.success_rate == 1.0
    assert len(stats.task_stats) == 1
    assert "task-1" in stats.task_stats


def test_calculate_stats_multiple_iterations():
    """Test calculate_stats with multiple iterations."""
    state = {
        "history": [
            {
                "iteration": 1,
                "duration_seconds": 100.0,
                "gates_ok": True,
                "blocked": False,
                "story_id": "task-1",
            },
            {
                "iteration": 2,
                "duration_seconds": 200.0,
                "gates_ok": False,
                "blocked": False,
                "story_id": "task-1",
            },
            {
                "iteration": 3,
                "duration_seconds": 150.0,
                "gates_ok": True,
                "blocked": False,
                "story_id": "task-2",
            },
        ]
    }
    stats = calculate_stats(state)

    assert stats.total_iterations == 3
    assert stats.successful_iterations == 2
    assert stats.failed_iterations == 1
    assert stats.avg_duration_seconds == 150.0  # (100 + 200 + 150) / 3
    assert stats.min_duration_seconds == 100.0
    assert stats.max_duration_seconds == 200.0
    assert stats.success_rate == pytest.approx(2 / 3)


def test_calculate_stats_blocked_iterations():
    """Test that blocked iterations are counted as failures."""
    state = {
        "history": [
            {
                "iteration": 1,
                "duration_seconds": 100.0,
                "gates_ok": True,
                "blocked": True,  # Blocked despite gates passing
                "story_id": "task-1",
            },
            {
                "iteration": 2,
                "duration_seconds": 150.0,
                "gates_ok": True,
                "blocked": False,
                "story_id": "task-1",
            },
        ]
    }
    stats = calculate_stats(state)

    assert stats.total_iterations == 2
    assert stats.successful_iterations == 1  # Only iteration 2
    assert stats.failed_iterations == 1  # Iteration 1 is blocked
    assert stats.success_rate == 0.5


def test_calculate_stats_per_task_breakdown():
    """Test per-task statistics calculation."""
    state = {
        "history": [
            {
                "iteration": 1,
                "duration_seconds": 100.0,
                "gates_ok": True,
                "blocked": False,
                "story_id": "task-1",
            },
            {
                "iteration": 2,
                "duration_seconds": 200.0,
                "gates_ok": False,
                "blocked": False,
                "story_id": "task-1",
            },
            {
                "iteration": 3,
                "duration_seconds": 150.0,
                "gates_ok": True,
                "blocked": False,
                "story_id": "task-2",
            },
            {
                "iteration": 4,
                "duration_seconds": 180.0,
                "gates_ok": True,
                "blocked": False,
                "story_id": "task-2",
            },
        ]
    }
    stats = calculate_stats(state)

    assert len(stats.task_stats) == 2

    # Task 1: 2 attempts, 1 success, 1 failure
    task1 = stats.task_stats["task-1"]
    assert task1.task_id == "task-1"
    assert task1.attempts == 2
    assert task1.successes == 1
    assert task1.failures == 1
    assert task1.avg_duration_seconds == 150.0  # (100 + 200) / 2
    assert task1.total_duration_seconds == 300.0
    assert task1.success_rate == 0.5

    # Task 2: 2 attempts, 2 successes, 0 failures
    task2 = stats.task_stats["task-2"]
    assert task2.task_id == "task-2"
    assert task2.attempts == 2
    assert task2.successes == 2
    assert task2.failures == 0
    assert task2.avg_duration_seconds == 165.0  # (150 + 180) / 2
    assert task2.total_duration_seconds == 330.0
    assert task2.success_rate == 1.0


def test_calculate_stats_missing_duration():
    """Test that missing duration_seconds defaults to 0.0."""
    state = {
        "history": [
            {
                "iteration": 1,
                # duration_seconds missing
                "gates_ok": True,
                "blocked": False,
                "story_id": "task-1",
            }
        ]
    }
    stats = calculate_stats(state)

    assert stats.avg_duration_seconds == 0.0
    assert stats.min_duration_seconds == 0.0
    assert stats.max_duration_seconds == 0.0


def test_calculate_stats_unknown_task_id():
    """Test handling of entries without story_id or task_id."""
    state = {
        "history": [
            {
                "iteration": 1,
                "duration_seconds": 100.0,
                "gates_ok": True,
                "blocked": False,
                # No story_id or task_id
            }
        ]
    }
    stats = calculate_stats(state)

    assert len(stats.task_stats) == 1
    assert "unknown" in stats.task_stats


def test_export_stats_csv(tmp_path: Path):
    """Test CSV export functionality."""
    stats = IterationStats(
        total_iterations=5,
        successful_iterations=3,
        failed_iterations=2,
        avg_duration_seconds=125.5,
        min_duration_seconds=100.0,
        max_duration_seconds=200.0,
        success_rate=0.6,
        task_stats={
            "task-1": TaskStats(
                task_id="task-1",
                attempts=3,
                successes=2,
                failures=1,
                avg_duration_seconds=120.0,
                total_duration_seconds=360.0,
            ),
            "task-2": TaskStats(
                task_id="task-2",
                attempts=2,
                successes=1,
                failures=1,
                avg_duration_seconds=140.0,
                total_duration_seconds=280.0,
            ),
        },
    )

    output_path = tmp_path / "stats.csv"
    export_stats_csv(stats, output_path)

    assert output_path.exists()

    # Read and verify CSV content
    with open(output_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Check overall statistics section
    assert rows[0] == ["Overall Statistics"]
    assert rows[1] == ["Metric", "Value"]
    assert rows[2] == ["Total Iterations", "5"]
    assert rows[3] == ["Successful Iterations", "3"]
    assert rows[4] == ["Failed Iterations", "2"]
    assert rows[5] == ["Success Rate", "60.00%"]

    # Check per-task statistics section exists
    assert "Per-Task Statistics" in [row[0] for row in rows if row]

    # Verify task data is present (sorted by total duration)
    task_rows = [row for row in rows if row and row[0] in ["task-1", "task-2"]]
    assert len(task_rows) == 2
    # task-1 should come first (360.0 > 280.0)
    assert task_rows[0][0] == "task-1"
    assert task_rows[1][0] == "task-2"


def test_export_stats_csv_empty_tasks(tmp_path: Path):
    """Test CSV export with no task statistics."""
    stats = IterationStats(
        total_iterations=0,
        successful_iterations=0,
        failed_iterations=0,
        avg_duration_seconds=0.0,
        min_duration_seconds=0.0,
        max_duration_seconds=0.0,
        success_rate=0.0,
        task_stats={},
    )

    output_path = tmp_path / "stats_empty.csv"
    export_stats_csv(stats, output_path)

    assert output_path.exists()

    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Should still have headers even with no tasks
    assert "Overall Statistics" in content
    assert "Per-Task Statistics" in content


def test_format_stats_report_basic():
    """Test basic stats report formatting."""
    stats = IterationStats(
        total_iterations=10,
        successful_iterations=8,
        failed_iterations=2,
        avg_duration_seconds=125.5,
        min_duration_seconds=100.0,
        max_duration_seconds=200.0,
        success_rate=0.8,
        task_stats={},
    )

    report = format_stats_report(stats, by_task=False)

    assert "Ralph Gold - Iteration Statistics" in report
    assert "Total Iterations:      10" in report
    assert "Successful:            8" in report
    assert "Failed:                2" in report
    assert "Success Rate:          80.0%" in report
    assert "Average:               125.50s" in report
    assert "Minimum:               100.00s" in report
    assert "Maximum:               200.00s" in report


def test_format_stats_report_with_tasks():
    """Test stats report with per-task breakdown."""
    stats = IterationStats(
        total_iterations=5,
        successful_iterations=3,
        failed_iterations=2,
        avg_duration_seconds=125.5,
        min_duration_seconds=100.0,
        max_duration_seconds=200.0,
        success_rate=0.6,
        task_stats={
            "task-1": TaskStats(
                task_id="task-1",
                attempts=3,
                successes=2,
                failures=1,
                avg_duration_seconds=120.0,
                total_duration_seconds=360.0,
            ),
            "task-2": TaskStats(
                task_id="task-2",
                attempts=2,
                successes=1,
                failures=1,
                avg_duration_seconds=140.0,
                total_duration_seconds=280.0,
            ),
        },
    )

    report = format_stats_report(stats, by_task=True)

    # Check overall stats
    assert "Total Iterations:      5" in report
    assert "Success Rate:          60.0%" in report

    # Check per-task section
    assert "Per-Task Statistics" in report
    assert "Task: task-1" in report
    assert "Attempts:              3" in report
    assert "Successes:             2" in report
    assert "Failures:              1" in report
    assert "Avg Duration:          120.00s" in report
    assert "Total Duration:        360.00s" in report

    assert "Task: task-2" in report


def test_format_stats_report_without_tasks():
    """Test that by_task=False excludes task breakdown."""
    stats = IterationStats(
        total_iterations=5,
        successful_iterations=3,
        failed_iterations=2,
        avg_duration_seconds=125.5,
        min_duration_seconds=100.0,
        max_duration_seconds=200.0,
        success_rate=0.6,
        task_stats={
            "task-1": TaskStats(
                task_id="task-1",
                attempts=3,
                successes=2,
                failures=1,
                avg_duration_seconds=120.0,
                total_duration_seconds=360.0,
            ),
        },
    )

    report = format_stats_report(stats, by_task=False)

    # Should have overall stats
    assert "Total Iterations:      5" in report

    # Should NOT have per-task section
    assert "Per-Task Statistics" not in report
    assert "Task: task-1" not in report


def test_format_stats_report_empty():
    """Test report formatting with empty statistics."""
    stats = IterationStats(
        total_iterations=0,
        successful_iterations=0,
        failed_iterations=0,
        avg_duration_seconds=0.0,
        min_duration_seconds=0.0,
        max_duration_seconds=0.0,
        success_rate=0.0,
        task_stats={},
    )

    report = format_stats_report(stats, by_task=True)

    assert "Total Iterations:      0" in report
    assert "Success Rate:          0.0%" in report
    assert "Average:               0.00s" in report


def test_calculate_stats_gates_ok_none():
    """Test that gates_ok=None is treated as failure."""
    state = {
        "history": [
            {
                "iteration": 1,
                "duration_seconds": 100.0,
                "gates_ok": None,  # Not configured
                "blocked": False,
                "story_id": "task-1",
            }
        ]
    }
    stats = calculate_stats(state)

    assert stats.successful_iterations == 0
    assert stats.failed_iterations == 1


def test_calculate_stats_task_id_fallback():
    """Test that task_id is used when story_id is missing."""
    state = {
        "history": [
            {
                "iteration": 1,
                "duration_seconds": 100.0,
                "gates_ok": True,
                "blocked": False,
                "task_id": "fallback-task",
                # No story_id
            }
        ]
    }
    stats = calculate_stats(state)

    assert "fallback-task" in stats.task_stats


def test_csv_export_task_sorting(tmp_path: Path):
    """Test that CSV export sorts tasks by total duration (descending)."""
    stats = IterationStats(
        total_iterations=6,
        successful_iterations=4,
        failed_iterations=2,
        avg_duration_seconds=100.0,
        min_duration_seconds=50.0,
        max_duration_seconds=200.0,
        success_rate=0.67,
        task_stats={
            "fast-task": TaskStats(
                task_id="fast-task",
                attempts=2,
                successes=2,
                failures=0,
                avg_duration_seconds=50.0,
                total_duration_seconds=100.0,
            ),
            "slow-task": TaskStats(
                task_id="slow-task",
                attempts=2,
                successes=1,
                failures=1,
                avg_duration_seconds=150.0,
                total_duration_seconds=300.0,
            ),
            "medium-task": TaskStats(
                task_id="medium-task",
                attempts=2,
                successes=1,
                failures=1,
                avg_duration_seconds=100.0,
                total_duration_seconds=200.0,
            ),
        },
    )

    output_path = tmp_path / "sorted_stats.csv"
    export_stats_csv(stats, output_path)

    with open(output_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Find task rows
    task_rows = [
        row
        for row in rows
        if row and row[0] in ["fast-task", "slow-task", "medium-task"]
    ]

    # Should be sorted by total duration descending
    assert task_rows[0][0] == "slow-task"  # 300.0
    assert task_rows[1][0] == "medium-task"  # 200.0
    assert task_rows[2][0] == "fast-task"  # 100.0
