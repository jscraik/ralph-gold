"""Tests for smart resume functionality."""

import json
from pathlib import Path

from ralph_gold.resume import (
    clear_interrupted_state,
    detect_interrupted_iteration,
    format_resume_prompt,
    should_resume,
)


def test_detect_no_interruption_when_no_state(tmp_path: Path) -> None:
    """Test that no interruption is detected when state.json doesn't exist."""
    result = detect_interrupted_iteration(tmp_path)
    assert result is None


def test_detect_no_interruption_when_completed_normally(tmp_path: Path) -> None:
    """Test that completed iterations are not detected as interrupted."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    state = {
        "history": [
            {
                "iteration": 1,
                "story_id": "task-1",
                "agent": "codex",
                "exit_signal": True,
                "return_code": 0,
                "gates_ok": True,
                "ts": "2024-01-01T12:00:00Z",
            }
        ]
    }

    (ralph_dir / "state.json").write_text(json.dumps(state))

    result = detect_interrupted_iteration(tmp_path)
    assert result is None


def test_detect_interruption_missing_exit_signal(tmp_path: Path) -> None:
    """Test that iterations without exit_signal are detected as interrupted."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    state = {
        "history": [
            {
                "iteration": 1,
                "story_id": "task-1",
                "task_title": "Fix bug",
                "agent": "codex",
                "gates_ok": True,
                "ts": "2024-01-01T12:00:00Z",
                "log_path": ".ralph/logs/iter0001.log",
            }
        ]
    }

    (ralph_dir / "state.json").write_text(json.dumps(state))

    result = detect_interrupted_iteration(tmp_path)
    assert result is not None
    assert result.iteration == 1
    assert result.task_id == "task-1"
    assert result.task_title == "Fix bug"
    assert result.agent == "codex"
    assert result.gates_passed is True
    assert result.interrupted is True


def test_detect_interruption_nonzero_return_code(tmp_path: Path) -> None:
    """Test that iterations with non-zero return codes are detected."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    state = {
        "history": [
            {
                "iteration": 1,
                "story_id": "task-1",
                "agent": "codex",
                "return_code": 1,
                "gates_ok": True,
                "ts": "2024-01-01T12:00:00Z",
            }
        ]
    }

    (ralph_dir / "state.json").write_text(json.dumps(state))

    result = detect_interrupted_iteration(tmp_path)
    assert result is not None
    assert result.interrupted is True


def test_no_interruption_when_gates_failed(tmp_path: Path) -> None:
    """Test that gate failures are not considered interruptions."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    state = {
        "history": [
            {
                "iteration": 1,
                "story_id": "task-1",
                "agent": "codex",
                "gates_ok": False,
                "return_code": 1,
                "ts": "2024-01-01T12:00:00Z",
            }
        ]
    }

    (ralph_dir / "state.json").write_text(json.dumps(state))

    result = detect_interrupted_iteration(tmp_path)
    # Gates failed legitimately, not an interruption
    assert result is None


def test_should_resume_when_gates_passed(tmp_path: Path) -> None:
    """Test that resume is recommended when gates passed."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    state = {
        "history": [
            {
                "iteration": 1,
                "story_id": "task-1",
                "agent": "codex",
                "gates_ok": True,
                "ts": "2024-01-01T12:00:00Z",
            }
        ]
    }

    (ralph_dir / "state.json").write_text(json.dumps(state))

    result = detect_interrupted_iteration(tmp_path)
    assert result is not None
    assert should_resume(result) is True


def test_should_resume_when_gates_not_run(tmp_path: Path) -> None:
    """Test that resume is recommended when gates weren't run yet."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    state = {
        "history": [
            {
                "iteration": 1,
                "story_id": "task-1",
                "agent": "codex",
                "gates_ok": None,
                "ts": "2024-01-01T12:00:00Z",
            }
        ]
    }

    (ralph_dir / "state.json").write_text(json.dumps(state))

    result = detect_interrupted_iteration(tmp_path)
    assert result is not None
    assert should_resume(result) is True


def test_format_resume_prompt(tmp_path: Path) -> None:
    """Test that resume prompt is formatted correctly."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    state = {
        "history": [
            {
                "iteration": 42,
                "story_id": "task-123",
                "task_title": "Implement feature X",
                "agent": "claude",
                "gates_ok": True,
                "ts": "2024-01-01T12:00:00Z",
                "log_path": ".ralph/logs/iter0042.log",
            }
        ]
    }

    (ralph_dir / "state.json").write_text(json.dumps(state))

    result = detect_interrupted_iteration(tmp_path)
    assert result is not None

    prompt = format_resume_prompt(result)
    assert "42" in prompt
    assert "task-123" in prompt
    assert "Implement feature X" in prompt
    assert "claude" in prompt
    assert "✓ PASSED" in prompt
    assert "2024-01-01T12:00:00Z" in prompt


def test_clear_interrupted_state(tmp_path: Path) -> None:
    """Test that interrupted state can be cleared."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    state = {
        "history": [
            {
                "iteration": 1,
                "story_id": "task-1",
                "agent": "codex",
                "gates_ok": True,
            },
            {
                "iteration": 2,
                "story_id": "task-2",
                "agent": "codex",
                "gates_ok": True,
            },
        ],
        "noProgressStreak": 2,
    }

    state_path = ralph_dir / "state.json"
    state_path.write_text(json.dumps(state))

    # Clear the interrupted state
    result = clear_interrupted_state(tmp_path)
    assert result is True

    # Verify state was updated
    updated_state = json.loads(state_path.read_text())
    assert len(updated_state["history"]) == 1
    assert updated_state["history"][0]["iteration"] == 1
    assert updated_state["noProgressStreak"] == 0


def test_clear_interrupted_state_no_history(tmp_path: Path) -> None:
    """Test that clearing with no history returns False."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    state = {"history": []}
    (ralph_dir / "state.json").write_text(json.dumps(state))

    result = clear_interrupted_state(tmp_path)
    assert result is False


def test_clear_interrupted_state_no_file(tmp_path: Path) -> None:
    """Test that clearing with no state file returns False."""
    result = clear_interrupted_state(tmp_path)
    assert result is False
