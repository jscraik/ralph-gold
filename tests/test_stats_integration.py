"""Integration tests for stats module with real state.json format."""

from __future__ import annotations

from pathlib import Path

from ralph_gold.stats import calculate_stats, export_stats_csv, format_stats_report


def test_stats_with_realistic_state_data(tmp_path: Path):
    """Test stats calculation with realistic state.json structure."""
    # Create a realistic state.json structure based on loop.py format
    state = {
        "createdAt": "2024-01-01T00:00:00Z",
        "session_id": "20240101-120000",
        "invocations": [1704110400.0],
        "noProgressStreak": 0,
        "history": [
            {
                "ts": "2024-01-01T12:00:00Z",
                "iteration": 1,
                "agent": "codex",
                "branch": "main",
                "story_id": "task-setup-database",
                "duration_seconds": 145.23,
                "return_code": 0,
                "exit_signal_raw": False,
                "exit_signal_effective": False,
                "repo_clean": True,
                "gates_ok": True,
                "judge_ok": None,
                "judge_enabled": False,
                "judge_agent": "",
                "judge_ran": False,
                "judge_return_code": None,
                "judge_duration_seconds": None,
                "judge_signal_raw": None,
                "judge_signal_effective": None,
                "review_ok": None,
                "blocked": False,
                "attempt_id": "20240101-120000-iter0001",
                "receipts_dir": ".ralph/receipts/task-setup-database/20240101-120000-iter0001",
                "context_dir": ".ralph/context/task-setup-database/20240101-120000-iter0001",
                "timed_out": False,
                "commit_action": "auto",
                "commit_return_code": 0,
                "gate_results": [
                    {
                        "cmd": "pytest",
                        "return_code": 0,
                        "duration_seconds": 12.5,
                    }
                ],
            },
            {
                "ts": "2024-01-01T12:05:00Z",
                "iteration": 2,
                "agent": "codex",
                "branch": "main",
                "story_id": "task-setup-database",
                "duration_seconds": 89.45,
                "return_code": 1,
                "exit_signal_raw": False,
                "exit_signal_effective": False,
                "repo_clean": False,
                "gates_ok": False,  # Failed gates
                "judge_ok": None,
                "judge_enabled": False,
                "judge_agent": "",
                "judge_ran": False,
                "judge_return_code": None,
                "judge_duration_seconds": None,
                "judge_signal_raw": None,
                "judge_signal_effective": None,
                "review_ok": None,
                "blocked": False,
                "attempt_id": "20240101-120500-iter0002",
                "receipts_dir": ".ralph/receipts/task-setup-database/20240101-120500-iter0002",
                "context_dir": ".ralph/context/task-setup-database/20240101-120500-iter0002",
                "timed_out": False,
                "commit_action": "skip",
                "commit_return_code": None,
                "gate_results": [
                    {
                        "cmd": "pytest",
                        "return_code": 1,
                        "duration_seconds": 8.2,
                    }
                ],
            },
            {
                "ts": "2024-01-01T12:10:00Z",
                "iteration": 3,
                "agent": "codex",
                "branch": "main",
                "story_id": "task-add-api-endpoint",
                "duration_seconds": 203.67,
                "return_code": 0,
                "exit_signal_raw": False,
                "exit_signal_effective": False,
                "repo_clean": True,
                "gates_ok": True,
                "judge_ok": None,
                "judge_enabled": False,
                "judge_agent": "",
                "judge_ran": False,
                "judge_return_code": None,
                "judge_duration_seconds": None,
                "judge_signal_raw": None,
                "judge_signal_effective": None,
                "review_ok": None,
                "blocked": False,
                "attempt_id": "20240101-121000-iter0003",
                "receipts_dir": ".ralph/receipts/task-add-api-endpoint/20240101-121000-iter0003",
                "context_dir": ".ralph/context/task-add-api-endpoint/20240101-121000-iter0003",
                "timed_out": False,
                "commit_action": "auto",
                "commit_return_code": 0,
                "gate_results": [
                    {
                        "cmd": "pytest",
                        "return_code": 0,
                        "duration_seconds": 15.3,
                    }
                ],
            },
        ],
        "task_attempts": {},
        "blocked_tasks": {},
    }

    # Calculate stats
    stats = calculate_stats(state)

    # Verify overall statistics
    assert stats.total_iterations == 3
    assert stats.successful_iterations == 2  # Iterations 1 and 3
    assert stats.failed_iterations == 1  # Iteration 2
    assert stats.success_rate == 2 / 3

    # Verify duration statistics
    expected_avg = (145.23 + 89.45 + 203.67) / 3
    assert abs(stats.avg_duration_seconds - expected_avg) < 0.01
    assert stats.min_duration_seconds == 89.45
    assert stats.max_duration_seconds == 203.67

    # Verify per-task statistics
    assert len(stats.task_stats) == 2

    # Task: task-setup-database (2 attempts, 1 success, 1 failure)
    task1 = stats.task_stats["task-setup-database"]
    assert task1.attempts == 2
    assert task1.successes == 1
    assert task1.failures == 1
    assert task1.success_rate == 0.5
    expected_task1_avg = (145.23 + 89.45) / 2
    assert abs(task1.avg_duration_seconds - expected_task1_avg) < 0.01
    assert abs(task1.total_duration_seconds - (145.23 + 89.45)) < 0.01

    # Task: task-add-api-endpoint (1 attempt, 1 success, 0 failures)
    task2 = stats.task_stats["task-add-api-endpoint"]
    assert task2.attempts == 1
    assert task2.successes == 1
    assert task2.failures == 0
    assert task2.success_rate == 1.0
    assert task2.avg_duration_seconds == 203.67
    assert task2.total_duration_seconds == 203.67

    # Test report formatting
    report = format_stats_report(stats, by_task=True)
    assert "Total Iterations:      3" in report
    assert "Successful:            2" in report
    assert "Failed:                1" in report
    assert "task-setup-database" in report
    assert "task-add-api-endpoint" in report

    # Test CSV export
    csv_path = tmp_path / "integration_stats.csv"
    export_stats_csv(stats, csv_path)
    assert csv_path.exists()

    # Verify CSV content
    csv_content = csv_path.read_text()
    assert "Overall Statistics" in csv_content
    assert "Per-Task Statistics" in csv_content
    assert "task-setup-database" in csv_content
    assert "task-add-api-endpoint" in csv_content


def test_stats_with_minimal_state(tmp_path: Path):
    """Test stats with minimal state.json (just created)."""
    state = {
        "createdAt": "2024-01-01T00:00:00Z",
        "invocations": [],
        "noProgressStreak": 0,
        "history": [],
        "task_attempts": {},
        "blocked_tasks": {},
        "session_id": "",
    }

    stats = calculate_stats(state)

    assert stats.total_iterations == 0
    assert stats.successful_iterations == 0
    assert stats.failed_iterations == 0
    assert stats.success_rate == 0.0
    assert len(stats.task_stats) == 0

    # Should still be able to format and export
    report = format_stats_report(stats)
    assert "Total Iterations:      0" in report

    csv_path = tmp_path / "minimal_stats.csv"
    export_stats_csv(stats, csv_path)
    assert csv_path.exists()


def test_stats_handles_legacy_state_format(tmp_path: Path):
    """Test that stats handles older state.json without duration_seconds."""
    # Simulate old state format where duration_seconds might be missing
    state = {
        "history": [
            {
                "iteration": 1,
                # No duration_seconds field
                "gates_ok": True,
                "blocked": False,
                "story_id": "task-1",
            },
            {
                "iteration": 2,
                "duration_seconds": 100.0,  # This one has it
                "gates_ok": True,
                "blocked": False,
                "story_id": "task-2",
            },
        ]
    }

    stats = calculate_stats(state)

    # Should handle missing duration gracefully (defaults to 0.0)
    assert stats.total_iterations == 2
    assert stats.avg_duration_seconds == 50.0  # (0.0 + 100.0) / 2
    assert stats.min_duration_seconds == 0.0
    assert stats.max_duration_seconds == 100.0
