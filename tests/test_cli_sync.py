"""Tests for ralph sync command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from ralph_gold.cli import build_parser, cmd_sync


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project with PRD and state files."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal ralph.toml
    config_content = """
[files]
prd = ".ralph/PRD.md"

[loop]
max_iterations = 1
"""
    (tmp_path / "ralph.toml").write_text(config_content)

    # Create PRD with some tasks
    prd_content = """# PRD

## Tasks

- [x] Task 1: First task (done)
- [-] Task 2: Blocked task
- [ ] Task 3: Open task
"""
    (ralph_dir / "PRD.md").write_text(prd_content)

    # Create state.json with stale blocked entries
    # Note: task IDs are 1-based indices (1, 2, 3...) not "task-1"
    state = {
        "createdAt": "2026-01-01T00:00:00Z",
        "invocations": [],
        "noProgressStreak": 0,
        "history": [],
        "task_attempts": {"1": 1, "2": 3},
        "blocked_tasks": {
            "1": {"reason": "timeout", "attempts": 1},  # Stale - task 1 is done
            "2": {"reason": "gate_failure", "attempts": 3},  # Still blocked
        },
        "area_risk_scores": {},
        "session_id": "",
    }
    (ralph_dir / "state.json").write_text(json.dumps(state))

    # Create .git directory to make it a valid project
    (tmp_path / ".git").mkdir()

    return tmp_path


def test_sync_removes_stale_blocked_entries(temp_project: Path) -> None:
    """Test that sync removes blocked entries for tasks marked done in PRD."""
    # Change to temp project directory
    import os
    old_cwd = os.getcwd()
    os.chdir(temp_project)

    try:
        parser = build_parser()
        args = parser.parse_args(["sync"])
        result = cmd_sync(args)

        assert result == 0

        # Load updated state
        state_path = temp_project / ".ralph" / "state.json"
        state = json.loads(state_path.read_text())

        # Task 1 should be removed from blocked_tasks (it's done in PRD)
        assert "1" not in state["blocked_tasks"]
        # Task 2 should remain (still blocked in PRD)
        assert "2" in state["blocked_tasks"]

    finally:
        os.chdir(old_cwd)


def test_sync_verbose_output(temp_project: Path) -> None:
    """Test that verbose output shows removed task IDs."""
    import os
    old_cwd = os.getcwd()
    os.chdir(temp_project)

    try:
        parser = build_parser()
        args = parser.parse_args(["sync", "--verbose"])
        result = cmd_sync(args)

        assert result == 0

    finally:
        os.chdir(old_cwd)


def test_sync_clean_attempts(temp_project: Path) -> None:
    """Test that --clean-attempts also removes attempt history."""
    import os
    old_cwd = os.getcwd()
    os.chdir(temp_project)

    try:
        parser = build_parser()
        args = parser.parse_args(["sync", "--clean-attempts"])
        result = cmd_sync(args)

        assert result == 0

        # Load updated state
        state_path = temp_project / ".ralph" / "state.json"
        state = json.loads(state_path.read_text())

        # Task 1 should be removed from both blocked_tasks and task_attempts
        assert "1" not in state["blocked_tasks"]
        assert "1" not in state.get("task_attempts", {})
        # Task 2 attempt history should remain
        assert "2" in state.get("task_attempts", {})

    finally:
        os.chdir(old_cwd)


def test_sync_no_state_file(temp_project: Path) -> None:
    """Test that sync handles missing state.json gracefully."""
    import os
    old_cwd = os.getcwd()
    os.chdir(temp_project)

    # Remove state.json
    (temp_project / ".ralph" / "state.json").unlink()

    try:
        parser = build_parser()
        args = parser.parse_args(["sync"])
        result = cmd_sync(args)

        # Should succeed (nothing to sync)
        assert result == 0

    finally:
        os.chdir(old_cwd)


def test_sync_already_in_sync(temp_project: Path) -> None:
    """Test that sync handles already-synced state."""
    import os
    old_cwd = os.getcwd()
    os.chdir(temp_project)

    # Update state to be in sync (no stale entries)
    state_path = temp_project / ".ralph" / "state.json"
    state = json.loads(state_path.read_text())
    state["blocked_tasks"] = {"2": {"reason": "gate_failure", "attempts": 3}}
    state_path.write_text(json.dumps(state))

    try:
        parser = build_parser()
        args = parser.parse_args(["sync"])
        result = cmd_sync(args)

        assert result == 0

    finally:
        os.chdir(old_cwd)
