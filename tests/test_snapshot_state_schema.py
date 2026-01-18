"""Tests for state.json schema extensions for snapshots (Task 7.2)."""

import json
from pathlib import Path

from ralph_gold.loop import load_state


def test_load_state_includes_snapshots_array(tmp_path: Path) -> None:
    """Test that load_state initializes snapshots array for new state."""
    state_path = tmp_path / "state.json"

    # Load state when file doesn't exist
    state = load_state(state_path)

    assert "snapshots" in state
    assert isinstance(state["snapshots"], list)
    assert len(state["snapshots"]) == 0


def test_load_state_preserves_existing_snapshots(tmp_path: Path) -> None:
    """Test that load_state preserves existing snapshots in state.json."""
    state_path = tmp_path / "state.json"

    # Create state with snapshots
    existing_state = {
        "createdAt": "2024-01-01T00:00:00Z",
        "history": [],
        "invocations": [],
        "snapshots": [
            {
                "name": "test-snapshot",
                "timestamp": "2024-01-01T12:00:00Z",
                "git_stash_ref": "stash@{0}",
                "state_backup_path": ".ralph/snapshots/test-snapshot_state.json",
                "description": "Test snapshot",
                "git_commit": "abc123",
            }
        ],
    }
    state_path.write_text(json.dumps(existing_state), encoding="utf-8")

    # Load state
    state = load_state(state_path)

    assert "snapshots" in state
    assert len(state["snapshots"]) == 1
    assert state["snapshots"][0]["name"] == "test-snapshot"
    assert state["snapshots"][0]["git_stash_ref"] == "stash@{0}"


def test_load_state_adds_snapshots_to_old_state(tmp_path: Path) -> None:
    """Test that load_state adds snapshots array to old state files."""
    state_path = tmp_path / "state.json"

    # Create old state without snapshots
    old_state = {
        "createdAt": "2024-01-01T00:00:00Z",
        "history": [],
        "invocations": [],
    }
    state_path.write_text(json.dumps(old_state), encoding="utf-8")

    # Load state
    state = load_state(state_path)

    # Should add snapshots array with default value
    assert "snapshots" in state
    assert isinstance(state["snapshots"], list)
    assert len(state["snapshots"]) == 0


def test_snapshot_metadata_schema(tmp_path: Path) -> None:
    """Test that snapshot metadata has the correct schema."""
    state_path = tmp_path / "state.json"

    # Create state with snapshot metadata
    state = {
        "createdAt": "2024-01-01T00:00:00Z",
        "history": [],
        "invocations": [],
        "snapshots": [
            {
                "name": "my-snapshot",
                "timestamp": "2024-01-01T12:00:00Z",
                "git_stash_ref": "stash@{0}",
                "state_backup_path": ".ralph/snapshots/my-snapshot_state.json",
                "description": "Before refactor",
                "git_commit": "abc123def456",
            }
        ],
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")

    # Load and verify schema
    loaded_state = load_state(state_path)
    snapshot = loaded_state["snapshots"][0]

    # Verify all required fields are present
    assert "name" in snapshot
    assert "timestamp" in snapshot
    assert "git_stash_ref" in snapshot
    assert "state_backup_path" in snapshot
    assert "description" in snapshot
    assert "git_commit" in snapshot

    # Verify field types
    assert isinstance(snapshot["name"], str)
    assert isinstance(snapshot["timestamp"], str)
    assert isinstance(snapshot["git_stash_ref"], str)
    assert isinstance(snapshot["state_backup_path"], str)
    assert isinstance(snapshot["description"], str)
    assert isinstance(snapshot["git_commit"], str)


def test_multiple_snapshots_in_state(tmp_path: Path) -> None:
    """Test that state can track multiple snapshots."""
    state_path = tmp_path / "state.json"

    # Create state with multiple snapshots
    state = {
        "createdAt": "2024-01-01T00:00:00Z",
        "history": [],
        "invocations": [],
        "snapshots": [
            {
                "name": "snapshot-1",
                "timestamp": "2024-01-01T10:00:00Z",
                "git_stash_ref": "stash@{1}",
                "state_backup_path": ".ralph/snapshots/snapshot-1_state.json",
                "description": "First snapshot",
                "git_commit": "abc123",
            },
            {
                "name": "snapshot-2",
                "timestamp": "2024-01-01T11:00:00Z",
                "git_stash_ref": "stash@{0}",
                "state_backup_path": ".ralph/snapshots/snapshot-2_state.json",
                "description": "Second snapshot",
                "git_commit": "def456",
            },
        ],
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")

    # Load and verify
    loaded_state = load_state(state_path)

    assert len(loaded_state["snapshots"]) == 2
    assert loaded_state["snapshots"][0]["name"] == "snapshot-1"
    assert loaded_state["snapshots"][1]["name"] == "snapshot-2"
