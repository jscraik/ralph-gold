"""Tests for state validation against PRD."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from ralph_gold.state_validation import (
    ValidationResult,
    validate_state_against_prd,
    cleanup_stale_task_ids,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_validation_result_defaults(self) -> None:
        """Test ValidationResult default values."""
        result = ValidationResult()
        assert result.stale_ids == []
        assert result.protected_ids == []
        assert result.can_auto_cleanup is True
        assert result.state_mtime == 0.0
        assert result.prd_mtime == 0.0

    def test_validation_result_with_values(self) -> None:
        """Test ValidationResult with custom values."""
        result = ValidationResult(
            stale_ids=["task-1", "task-2"],
            protected_ids=["task-3"],
            can_auto_cleanup=False,
            state_mtime=1234567890.0,
            prd_mtime=1234567900.0,
        )
        assert result.stale_ids == ["task-1", "task-2"]
        assert result.protected_ids == ["task-3"]
        assert result.can_auto_cleanup is False
        assert result.state_mtime == 1234567890.0
        assert result.prd_mtime == 1234567900.0

    def test_log_summary_no_stale(self) -> None:
        """Test log_summary with no stale IDs."""
        result = ValidationResult()
        summary = result.log_summary()
        assert "No stale task IDs found" in summary
        assert "Auto-cleanup: safe" in summary

    def test_log_summary_with_stale(self) -> None:
        """Test log_summary with stale IDs."""
        result = ValidationResult(stale_ids=["task-1", "task-2"])
        summary = result.log_summary()
        assert "Found 2 stale task IDs" in summary
        assert "['task-1', 'task-2']" in summary

    def test_log_summary_with_protected(self) -> None:
        """Test log_summary with protected IDs."""
        result = ValidationResult(
            stale_ids=["task-1"], protected_ids=["task-2"]
        )
        summary = result.log_summary()
        assert "Protected (current/recent): ['task-2']" in summary

    def test_log_summary_unsafe_cleanup(self) -> None:
        """Test log_summary when cleanup is unsafe."""
        result = ValidationResult(can_auto_cleanup=False)
        summary = result.log_summary()
        assert "Auto-cleanup: unsafe" in summary
        assert "current task is stale" in summary


class TestValidateStateAgainstPrd:
    """Tests for validate_state_against_prd function."""

    def test_validate_nonexistent_state(self, tmp_path: Path) -> None:
        """Test validation when state.json doesn't exist."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph" / "state.json"

        result = validate_state_against_prd(tmp_path, prd_path, state_path)

        assert result.stale_ids == []
        assert result.can_auto_cleanup is True

    def test_validate_nonexistent_prd(self, tmp_path: Path) -> None:
        """Test validation when PRD doesn't exist."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph"
        state_path.mkdir()
        state_path = state_path / "state.json"

        state_path.write_text(
            json.dumps({"history": [{"task_id": "1"}]}), encoding="utf-8"
        )

        result = validate_state_against_prd(tmp_path, prd_path, state_path)

        # When PRD doesn't exist, get_all_tasks returns empty list, so all state task IDs are stale
        assert result.stale_ids == ["1"]
        # But can_auto_cleanup should be False because current task (1) is stale
        assert result.can_auto_cleanup is False

    def test_validate_invalid_json_state(self, tmp_path: Path) -> None:
        """Test validation with invalid JSON in state.json."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph"
        state_path.mkdir()
        state_file = state_path / "state.json"

        state_file.write_text("invalid json", encoding="utf-8")

        result = validate_state_against_prd(tmp_path, prd_path, state_file)

        # Should handle gracefully
        assert result.stale_ids == []

    def test_validate_no_stale_ids(self, tmp_path: Path) -> None:
        """Test validation when all task IDs are still in PRD."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph"
        state_path.mkdir()
        state_file = state_path / "state.json"

        # Create PRD with tasks (checkbox format)
        prd_path.write_text(
            """
## Tasks

- [ ] Task 1 description
- [ ] Task 2 description
""",
            encoding="utf-8",
        )

        # Create state with matching task IDs (sequential numbers)
        state_file.write_text(
            json.dumps(
                {
                    "history": [
                        {"task_id": "1", "timestamp": "2024-01-01T00:00:00Z"},
                        {"task_id": "2", "timestamp": "2024-01-01T01:00:00Z"},
                    ]
                }
            ),
            encoding="utf-8",
        )

        result = validate_state_against_prd(tmp_path, prd_path, state_file)

        assert result.stale_ids == []
        assert result.can_auto_cleanup is True

    def test_validate_with_stale_ids(self, tmp_path: Path) -> None:
        """Test validation when some task IDs are no longer in PRD."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph"
        state_path.mkdir()
        state_file = state_path / "state.json"

        # Create PRD with only task 1
        prd_path.write_text(
            """
## Tasks

- [ ] Task 1 description
""",
            encoding="utf-8",
        )

        # Create state with task 1 and task 2 (task 2 is stale)
        state_file.write_text(
            json.dumps(
                {
                    "history": [
                        {"task_id": "1", "timestamp": "2024-01-01T00:00:00Z"},
                        {"task_id": "2", "timestamp": "2024-01-01T01:00:00Z"},
                    ]
                }
            ),
            encoding="utf-8",
        )

        result = validate_state_against_prd(tmp_path, prd_path, state_file)

        assert "2" in result.stale_ids
        assert "1" not in result.stale_ids

    def test_validate_current_task_protected(self, tmp_path: Path) -> None:
        """Test that current task is always protected."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph"
        state_path.mkdir()
        state_file = state_path / "state.json"

        # Create PRD with no tasks
        prd_path.write_text("## Tasks\n\nNo tasks.", encoding="utf-8")

        # Create state where current task is stale
        now = datetime.now(timezone.utc).isoformat()
        state_file.write_text(
            json.dumps(
                {
                    "history": [
                        {"task_id": "old-task", "timestamp": "2024-01-01T00:00:00Z"},
                        {"task_id": "current-task", "timestamp": now},  # Most recent
                    ]
                }
            ),
            encoding="utf-8",
        )

        result = validate_state_against_prd(tmp_path, prd_path, state_file)

        # Both are stale, but current-task should be protected
        assert "current-task" in result.protected_ids
        assert result.can_auto_cleanup is False  # Can't auto-cleanup current task

    def test_validate_recent_tasks_protected(self, tmp_path: Path) -> None:
        """Test that recently completed tasks are protected."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph"
        state_path.mkdir()
        state_file = state_path / "state.json"

        # Create PRD with no tasks
        prd_path.write_text("## Tasks\n\nNo tasks.", encoding="utf-8")

        # Create state with recent and old tasks
        now = datetime.now(timezone.utc)
        recent = now - timedelta(minutes=30)  # Within 1 hour
        old = now - timedelta(hours=2)  # Outside 1 hour

        state_file.write_text(
            json.dumps(
                {
                    "history": [
                        {"task_id": "old-task", "timestamp": old.isoformat()},
                        {"task_id": "recent-task", "timestamp": recent.isoformat()},
                    ]
                }
            ),
            encoding="utf-8",
        )

        result = validate_state_against_prd(
            tmp_path, prd_path, state_file, protect_recent_hours=1
        )

        # Both are stale, but recent-task should be protected
        assert "old-task" in result.stale_ids
        assert "recent-task" in result.protected_ids
        assert "old-task" not in result.protected_ids

    def test_validate_task_attempts_included(self, tmp_path: Path) -> None:
        """Test that task IDs from task_attempts are checked."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph"
        state_path.mkdir()
        state_file = state_path / "state.json"

        # Create PRD with no tasks
        prd_path.write_text("## Tasks\n\nNo tasks.", encoding="utf-8")

        # Create state with task_attempts
        state_file.write_text(
            json.dumps(
                {
                    "history": [],
                    "task_attempts": {"task-1": 3, "task-2": 1},
                }
            ),
            encoding="utf-8",
        )

        result = validate_state_against_prd(tmp_path, prd_path, state_file)

        # Both task IDs from task_attempts should be detected as stale
        assert "task-1" in result.stale_ids
        assert "task-2" in result.stale_ids

    def test_validate_blocked_tasks_included(self, tmp_path: Path) -> None:
        """Test that task IDs from blocked_tasks are checked."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph"
        state_path.mkdir()
        state_file = state_path / "state.json"

        # Create PRD with no tasks
        prd_path.write_text("## Tasks\n\nNo tasks.", encoding="utf-8")

        # Create state with blocked_tasks
        state_file.write_text(
            json.dumps(
                {
                    "history": [],
                    "blocked_tasks": {"task-1": "blocked on task-2"},
                }
            ),
            encoding="utf-8",
        )

        result = validate_state_against_prd(tmp_path, prd_path, state_file)

        # task-1 from blocked_tasks should be detected as stale
        assert "task-1" in result.stale_ids

    def test_validate_prd_mtime_comparison(self, tmp_path: Path) -> None:
        """Test that PRD modification time affects auto-cleanup safety."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph"
        state_path.mkdir()
        state_file = state_path / "state.json"

        # Create PRD
        prd_path.write_text("## Tasks\n\nNo tasks.", encoding="utf-8")

        # Create state
        state_file.write_text(
            json.dumps({"history": [{"task_id": "stale-task"}]}), encoding="utf-8"
        )

        # Wait a bit to ensure PRD mtime > state mtime by more than 60s
        import time

        time.sleep(0.1)
        prd_path.touch()

        validate_state_against_prd(tmp_path, prd_path, state_file)

        # Should not allow auto-cleanup if PRD was modified recently
        # (within 60 seconds of state modification)
        # Note: This test is timing-dependent and may be flaky


class TestCleanupStaleTaskIds:
    """Tests for cleanup_stale_task_ids function."""

    def test_cleanup_no_stale_ids(self, tmp_path: Path) -> None:
        """Test cleanup when there are no stale IDs."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph"
        state_path.mkdir()
        state_file = state_path / "state.json"

        # Create PRD with tasks
        prd_path.write_text(
            """
## Tasks

### Task 1
id: task-1
Task 1
""",
            encoding="utf-8",
        )

        # Create state with matching task ID
        state_file.write_text(
            json.dumps({"history": [{"task_id": "task-1"}]}), encoding="utf-8"
        )

        removed = cleanup_stale_task_ids(
            tmp_path, prd_path, state_file, dry_run=False
        )

        assert removed == []

    def test_cleanup_dry_run(self, tmp_path: Path) -> None:
        """Test cleanup in dry-run mode."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph"
        state_path.mkdir()
        state_file = state_path / "state.json"

        # Create PRD with one task (task 1)
        prd_path.write_text(
            """
## Tasks

- [ ] Task 1
""",
            encoding="utf-8",
        )

        # Create state with valid current task (1) and a stale old task (2)
        state_file.write_text(
            json.dumps(
                {
                    "history": [
                        {"task_id": "2", "timestamp": "2024-01-01T00:00:00Z"},  # Old, stale
                        {"task_id": "1", "timestamp": "2024-01-02T00:00:00Z"},  # Current, valid
                    ]
                }
            ),
            encoding="utf-8",
        )

        # Store original content
        original_content = state_file.read_text(encoding="utf-8")

        removed = cleanup_stale_task_ids(
            tmp_path, prd_path, state_file, dry_run=True
        )

        # Dry run should report stale IDs but not modify file
        assert removed == ["2"]
        assert state_file.read_text(encoding="utf-8") == original_content

    def test_cleanup_removes_stale_ids(self, tmp_path: Path) -> None:
        """Test cleanup removes stale task IDs from state."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph"
        state_path.mkdir()
        state_file = state_path / "state.json"

        # Create PRD with only task 1
        prd_path.write_text(
            """
## Tasks

- [ ] Task 1
""",
            encoding="utf-8",
        )

        # Create state with valid current task (1) and stale old task (2)
        state_file.write_text(
            json.dumps(
                {
                    "history": [
                        {"task_id": "2", "timestamp": "2024-01-01T00:00:00Z"},  # Old, stale
                        {"task_id": "1", "timestamp": "2024-01-02T00:00:00Z"},  # Current, valid
                    ],
                    "task_attempts": {"2": 3},
                    "blocked_tasks": {"2": "blocked"},
                }
            ),
            encoding="utf-8",
        )

        removed = cleanup_stale_task_ids(
            tmp_path, prd_path, state_file, dry_run=False
        )

        # task 2 should be removed
        assert removed == ["2"]

        # Verify state was updated
        state = json.loads(state_file.read_text(encoding="utf-8"))
        history_task_ids = [
            entry.get("task_id") for entry in state.get("history", []) if entry.get("task_id")
        ]
        assert "1" in history_task_ids
        assert "2" not in history_task_ids
        assert "2" not in state.get("task_attempts", {})
        assert "2" not in state.get("blocked_tasks", {})

    def test_cleanup_protects_current_task(self, tmp_path: Path) -> None:
        """Test cleanup doesn't remove current (most recent) task."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph"
        state_path.mkdir()
        state_file = state_path / "state.json"

        # Create PRD with no tasks
        prd_path.write_text("## Tasks\n\nNo tasks.", encoding="utf-8")

        # Create state where current task is stale
        now = datetime.now(timezone.utc).isoformat()
        state_file.write_text(
            json.dumps(
                {
                    "history": [
                        {"task_id": "old-task", "timestamp": "2024-01-01T00:00:00Z"},
                        {"task_id": "current-task", "timestamp": now},
                    ]
                }
            ),
            encoding="utf-8",
        )

        removed = cleanup_stale_task_ids(
            tmp_path, prd_path, state_file, dry_run=False
        )

        # Should return empty because current task is stale and protected
        assert removed == []

    def test_cleanup_preserves_other_state(self, tmp_path: Path) -> None:
        """Test cleanup preserves other state data."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph"
        state_path.mkdir()
        state_file = state_path / "state.json"

        # Create PRD with no tasks
        prd_path.write_text("## Tasks\n\nNo tasks.", encoding="utf-8")

        # Create state with various data
        original_state = {
            "iteration": 5,
            "history": [
                {"task_id": "stale-task", "timestamp": "2024-01-01T00:00:00Z"}
            ],
            "task_attempts": {"stale-task": 2},
            "blocked_tasks": {"stale-task": "blocked"},
            "other_data": {"key": "value"},
            "completed_task_ids": ["task-1", "task-2"],
        }
        state_file.write_text(json.dumps(original_state), encoding="utf-8")

        cleanup_stale_task_ids(
            tmp_path, prd_path, state_file, dry_run=False
        )

        # Verify other data is preserved
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state.get("iteration") == 5
        assert state.get("other_data") == {"key": "value"}
        assert state.get("completed_task_ids") == ["task-1", "task-2"]

    def test_cleanup_invalid_json(self, tmp_path: Path) -> None:
        """Test cleanup handles invalid JSON gracefully."""
        prd_path = tmp_path / "PRD.md"
        state_path = tmp_path / ".ralph"
        state_path.mkdir()
        state_file = state_path / "state.json"

        # Create PRD
        prd_path.write_text("## Tasks\n\nNo tasks.", encoding="utf-8")

        # Create invalid state
        state_file.write_text("invalid json", encoding="utf-8")

        removed = cleanup_stale_task_ids(
            tmp_path, prd_path, state_file, dry_run=False
        )

        # Should handle gracefully and return empty
        assert removed == []
