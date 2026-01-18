"""Integration tests for the stats CLI command."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_stats_command_exists():
    """Test that the stats command is registered."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "stats" in result.stdout


def test_stats_command_help():
    """Test that the stats command has help text."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "stats", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--by-task" in result.stdout
    assert "--export" in result.stdout
    assert "Show detailed per-task breakdown" in result.stdout


def test_stats_command_no_state(tmp_path: Path):
    """Test that the stats command handles missing state gracefully."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "stats"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "No state.json found" in result.stdout


def test_stats_command_with_state(tmp_path: Path):
    """Test that the stats command displays statistics."""
    # Create a minimal ralph project with state
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create state with some history
    state = {
        "createdAt": "2024-01-01T00:00:00Z",
        "session_id": "test",
        "history": [
            {
                "iteration": 1,
                "ts": "2024-01-01T00:00:00Z",
                "duration_seconds": 100.0,
                "story_id": "task-1",
                "gates_ok": True,
                "return_code": 0,
            },
            {
                "iteration": 2,
                "ts": "2024-01-01T00:05:00Z",
                "duration_seconds": 200.0,
                "story_id": "task-2",
                "gates_ok": False,
                "return_code": 1,
            },
        ],
    }
    (ralph_dir / "state.json").write_text(json.dumps(state))

    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "stats"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Ralph Gold - Iteration Statistics" in result.stdout
    assert "Total Iterations:" in result.stdout
    assert "Success Rate:" in result.stdout
    assert "Average:" in result.stdout


def test_stats_command_by_task(tmp_path: Path):
    """Test that the stats command shows per-task breakdown."""
    # Create a minimal ralph project with state
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create state with some history
    state = {
        "createdAt": "2024-01-01T00:00:00Z",
        "session_id": "test",
        "history": [
            {
                "iteration": 1,
                "ts": "2024-01-01T00:00:00Z",
                "duration_seconds": 100.0,
                "story_id": "task-1",
                "gates_ok": True,
                "return_code": 0,
            },
            {
                "iteration": 2,
                "ts": "2024-01-01T00:05:00Z",
                "duration_seconds": 200.0,
                "story_id": "task-2",
                "gates_ok": True,
                "return_code": 0,
            },
        ],
    }
    (ralph_dir / "state.json").write_text(json.dumps(state))

    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "stats", "--by-task"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Per-Task Statistics" in result.stdout
    assert "Task: task-1" in result.stdout
    assert "Task: task-2" in result.stdout
    assert "Attempts:" in result.stdout


def test_stats_command_export(tmp_path: Path):
    """Test that the stats command exports to CSV."""
    # Create a minimal ralph project with state
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create state with some history
    state = {
        "createdAt": "2024-01-01T00:00:00Z",
        "session_id": "test",
        "history": [
            {
                "iteration": 1,
                "ts": "2024-01-01T00:00:00Z",
                "duration_seconds": 100.0,
                "story_id": "task-1",
                "gates_ok": True,
                "return_code": 0,
            },
        ],
    }
    (ralph_dir / "state.json").write_text(json.dumps(state))

    export_path = tmp_path / "stats.csv"
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "ralph_gold.cli",
            "stats",
            "--export",
            str(export_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Statistics exported to:" in result.stdout
    assert export_path.exists()

    # Verify CSV content
    csv_content = export_path.read_text()
    assert "Overall Statistics" in csv_content
    assert "Per-Task Statistics" in csv_content
    assert "Total Iterations" in csv_content
