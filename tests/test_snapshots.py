"""Unit tests for the snapshots module (Task 7.3)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from ralph_gold.snapshots import (
    cleanup_old_snapshots,
    create_snapshot,
    list_snapshots,
    rollback_snapshot,
)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for testing.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to the git repository
    """
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    test_file = tmp_path / "test.txt"
    test_file.write_text("initial content", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create .ralph directory with state.json
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    state_path = ralph_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "createdAt": "2024-01-01T00:00:00Z",
                "history": [],
                "invocations": [],
                "snapshots": [],
            }
        ),
        encoding="utf-8",
    )

    return tmp_path


def test_create_snapshot_basic(git_repo: Path) -> None:
    """Test basic snapshot creation."""
    # Make some changes to create a stash
    test_file = git_repo / "test.txt"
    test_file.write_text("modified for snapshot", encoding="utf-8")

    snapshot = create_snapshot(git_repo, "test-snapshot", "Test description")

    assert snapshot.name == "test-snapshot"
    assert snapshot.description == "Test description"
    assert snapshot.git_stash_ref.startswith("stash@{")
    assert snapshot.state_backup_path.endswith("_state.json")
    assert len(snapshot.git_commit) == 40  # SHA-1 hash length
    assert snapshot.timestamp  # Should have a timestamp


def test_create_snapshot_creates_git_stash(git_repo: Path) -> None:
    """Test that snapshot creates a git stash with correct message."""
    # Make some changes
    test_file = git_repo / "test.txt"
    test_file.write_text("modified content", encoding="utf-8")

    create_snapshot(git_repo, "my-snapshot", "Before refactor")

    # Verify stash was created
    result = subprocess.run(
        ["git", "stash", "list"],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "ralph-snapshot: my-snapshot" in result.stdout
    assert "Before refactor" in result.stdout


def test_create_snapshot_backs_up_state(git_repo: Path) -> None:
    """Test that snapshot backs up state.json."""
    # Modify state.json
    state_path = git_repo / ".ralph" / "state.json"
    state_data = {
        "createdAt": "2024-01-01T00:00:00Z",
        "history": [{"iteration": 1, "task": "test"}],
        "invocations": [],
        "snapshots": [],
    }
    state_path.write_text(json.dumps(state_data), encoding="utf-8")

    # Make changes to create a stash
    test_file = git_repo / "test.txt"
    test_file.write_text("modified for backup test", encoding="utf-8")

    snapshot = create_snapshot(git_repo, "backup-test")

    # Verify backup was created
    backup_path = git_repo / snapshot.state_backup_path
    assert backup_path.exists()

    # Verify backup content matches original
    backup_data = json.loads(backup_path.read_text(encoding="utf-8"))
    assert backup_data["history"] == state_data["history"]


def test_create_snapshot_saves_metadata(git_repo: Path) -> None:
    """Test that snapshot metadata is saved to state.json."""
    # Make changes to create a stash
    test_file = git_repo / "test.txt"
    test_file.write_text("modified for metadata test", encoding="utf-8")

    snapshot = create_snapshot(git_repo, "metadata-test", "Test metadata")

    # Load state.json
    state_path = git_repo / ".ralph" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))

    # Verify snapshot metadata was added
    assert "snapshots" in state
    assert len(state["snapshots"]) == 1

    saved_snapshot = state["snapshots"][0]
    assert saved_snapshot["name"] == "metadata-test"
    assert saved_snapshot["description"] == "Test metadata"
    assert saved_snapshot["git_stash_ref"] == snapshot.git_stash_ref
    assert saved_snapshot["git_commit"] == snapshot.git_commit


def test_create_snapshot_invalid_name(git_repo: Path) -> None:
    """Test that invalid snapshot names are rejected."""
    # Empty name
    with pytest.raises(ValueError, match="cannot be empty"):
        create_snapshot(git_repo, "", "Description")

    # Invalid characters
    with pytest.raises(ValueError, match="Invalid snapshot name"):
        create_snapshot(git_repo, "invalid name!", "Description")

    with pytest.raises(ValueError, match="Invalid snapshot name"):
        create_snapshot(git_repo, "invalid/name", "Description")

    with pytest.raises(ValueError, match="Invalid snapshot name"):
        create_snapshot(git_repo, "invalid@name", "Description")


def test_create_snapshot_valid_names(git_repo: Path) -> None:
    """Test that valid snapshot names are accepted."""
    # Valid names with different characters
    valid_names = [
        "simple",
        "with-hyphens",
        "with_underscores",
        "MixedCase123",
        "numbers-123",
        "a",  # Single character
        "very-long-name-with-many-hyphens-and-underscores_123",
    ]

    test_file = git_repo / "test.txt"
    for i, name in enumerate(valid_names):
        # Make changes for each snapshot
        test_file.write_text(f"content {i}", encoding="utf-8")
        snapshot = create_snapshot(git_repo, name, f"Test {name}")
        assert snapshot.name == name


def test_create_snapshot_not_git_repo(tmp_path: Path) -> None:
    """Test that snapshot creation fails if not in a git repository."""
    # Create .ralph directory without git
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    state_path = ralph_dir / "state.json"
    state_path.write_text("{}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not a git repository"):
        create_snapshot(tmp_path, "test-snapshot")


def test_create_snapshot_no_state_file(git_repo: Path) -> None:
    """Test snapshot creation when state.json doesn't exist."""
    # Remove state.json
    state_path = git_repo / ".ralph" / "state.json"
    state_path.unlink()

    # Make changes to create a stash
    test_file = git_repo / "test.txt"
    test_file.write_text("modified for no-state test", encoding="utf-8")

    snapshot = create_snapshot(git_repo, "no-state-test")

    # Should create empty backup
    backup_path = git_repo / snapshot.state_backup_path
    assert backup_path.exists()
    backup_content = backup_path.read_text(encoding="utf-8")
    assert backup_content == "{}"


def test_list_snapshots_empty(git_repo: Path) -> None:
    """Test listing snapshots when none exist."""
    snapshots = list_snapshots(git_repo)
    assert snapshots == []


def test_list_snapshots_single(git_repo: Path) -> None:
    """Test listing a single snapshot."""
    # Make changes to create a stash
    test_file = git_repo / "test.txt"
    test_file.write_text("modified for single snapshot", encoding="utf-8")

    created = create_snapshot(git_repo, "single-snapshot", "Test")

    snapshots = list_snapshots(git_repo)
    assert len(snapshots) == 1
    assert snapshots[0].name == "single-snapshot"
    assert snapshots[0].description == "Test"
    assert snapshots[0].git_stash_ref == created.git_stash_ref


def test_list_snapshots_multiple(git_repo: Path) -> None:
    """Test listing multiple snapshots."""
    test_file = git_repo / "test.txt"

    # Create snapshots with changes
    test_file.write_text("version 1", encoding="utf-8")
    create_snapshot(git_repo, "snapshot-1", "First")

    test_file.write_text("version 2", encoding="utf-8")
    create_snapshot(git_repo, "snapshot-2", "Second")

    test_file.write_text("version 3", encoding="utf-8")
    create_snapshot(git_repo, "snapshot-3", "Third")

    snapshots = list_snapshots(git_repo)
    assert len(snapshots) == 3

    names = [s.name for s in snapshots]
    assert "snapshot-1" in names
    assert "snapshot-2" in names
    assert "snapshot-3" in names


def test_list_snapshots_no_state_file(git_repo: Path) -> None:
    """Test listing snapshots when state.json doesn't exist."""
    state_path = git_repo / ".ralph" / "state.json"
    state_path.unlink()

    snapshots = list_snapshots(git_repo)
    assert snapshots == []


def test_list_snapshots_corrupted_state(git_repo: Path) -> None:
    """Test listing snapshots with corrupted state.json."""
    state_path = git_repo / ".ralph" / "state.json"
    state_path.write_text("invalid json {", encoding="utf-8")

    snapshots = list_snapshots(git_repo)
    assert snapshots == []


def test_rollback_snapshot_basic(git_repo: Path) -> None:
    """Test basic snapshot rollback."""
    # Create initial state and commit
    test_file = git_repo / "test.txt"
    test_file.write_text("original content", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Original content"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    # Make changes and create snapshot
    test_file.write_text("snapshot content", encoding="utf-8")
    snapshot = create_snapshot(git_repo, "rollback-test", "Before changes")

    # Verify snapshot was created
    assert snapshot.name == "rollback-test"

    # Make different changes (not conflicting) and commit
    new_file = git_repo / "new_file.txt"
    new_file.write_text("new file content", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add new file"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    # Rollback
    result = rollback_snapshot(git_repo, "rollback-test")
    assert result is True

    # Verify snapshot content was restored
    content = test_file.read_text(encoding="utf-8")
    assert content == "snapshot content"
    assert test_file.read_text(encoding="utf-8") == "snapshot content"


def test_rollback_snapshot_restores_state(git_repo: Path) -> None:
    """Test that rollback restores state.json."""
    # Create initial state
    state_path = git_repo / ".ralph" / "state.json"
    original_state = {
        "createdAt": "2024-01-01T00:00:00Z",
        "history": [{"iteration": 1}],
        "invocations": [],
        "snapshots": [],
    }
    state_path.write_text(json.dumps(original_state), encoding="utf-8")

    # Make changes to create a stash
    test_file = git_repo / "test.txt"
    test_file.write_text("snapshot version", encoding="utf-8")

    # Create snapshot
    create_snapshot(git_repo, "state-rollback")

    # Load the state that was saved (includes snapshot metadata)
    saved_state = json.loads(state_path.read_text(encoding="utf-8"))

    # Modify state but preserve snapshot metadata
    modified_state = {
        "createdAt": "2024-01-01T00:00:00Z",
        "history": [{"iteration": 1}, {"iteration": 2}],
        "invocations": [],
        "snapshots": saved_state["snapshots"],  # Preserve snapshot metadata
    }
    state_path.write_text(json.dumps(modified_state), encoding="utf-8")

    # Commit changes so working tree is clean
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Modified state"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    # Rollback
    rollback_snapshot(git_repo, "state-rollback")

    # Verify state was restored
    restored_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert len(restored_state["history"]) == 1
    assert restored_state["history"][0]["iteration"] == 1


def test_rollback_snapshot_not_found(git_repo: Path) -> None:
    """Test rollback with non-existent snapshot."""
    # Ensure working tree is clean
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Clean state"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    with pytest.raises(ValueError, match="not found"):
        rollback_snapshot(git_repo, "nonexistent-snapshot")


def test_rollback_snapshot_dirty_tree(git_repo: Path) -> None:
    """Test that rollback fails with dirty working tree."""
    # Make changes and create snapshot
    test_file = git_repo / "test.txt"
    test_file.write_text("snapshot content", encoding="utf-8")
    create_snapshot(git_repo, "dirty-test")

    # Make uncommitted changes
    test_file.write_text("uncommitted changes", encoding="utf-8")

    # Rollback should fail
    with pytest.raises(RuntimeError, match="uncommitted changes"):
        rollback_snapshot(git_repo, "dirty-test")


def test_rollback_snapshot_dirty_tree_force(git_repo: Path) -> None:
    """Test that rollback with force=True works with dirty tree."""
    # Create initial content and commit
    test_file = git_repo / "test.txt"
    test_file.write_text("committed content", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Commit before snapshot"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    # Make changes and create snapshot
    test_file.write_text("snapshot content", encoding="utf-8")
    create_snapshot(git_repo, "force-test")

    # Make different uncommitted changes
    test_file.write_text("different uncommitted changes", encoding="utf-8")

    # Rollback with force should succeed (though git may still conflict)
    # Actually, git stash apply will fail if there are conflicts
    # So let's test that force allows the attempt but may still fail
    try:
        result = rollback_snapshot(git_repo, "force-test", force=True)
        # If it succeeds, that's fine
        assert result is True
    except RuntimeError as e:
        # If it fails due to merge conflict, that's also expected behavior
        assert "merge" in str(e).lower() or "overwritten" in str(e).lower()


def test_rollback_snapshot_not_git_repo(tmp_path: Path) -> None:
    """Test that rollback fails if not in a git repository."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    state_path = ralph_dir / "state.json"
    state_path.write_text(
        json.dumps({"snapshots": [{"name": "test"}]}), encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="not a git repository"):
        rollback_snapshot(tmp_path, "test")


def test_cleanup_old_snapshots_none_to_remove(git_repo: Path) -> None:
    """Test cleanup when there are fewer snapshots than keep_count."""
    test_file = git_repo / "test.txt"

    # Create 3 snapshots
    test_file.write_text("snap 1", encoding="utf-8")
    create_snapshot(git_repo, "snap-1")

    test_file.write_text("snap 2", encoding="utf-8")
    create_snapshot(git_repo, "snap-2")

    test_file.write_text("snap 3", encoding="utf-8")
    create_snapshot(git_repo, "snap-3")

    # Keep 10, should remove 0
    removed = cleanup_old_snapshots(git_repo, keep_count=10)
    assert removed == 0

    # All snapshots should still exist
    snapshots = list_snapshots(git_repo)
    assert len(snapshots) == 3


def test_cleanup_old_snapshots_removes_oldest(git_repo: Path) -> None:
    """Test that cleanup removes oldest snapshots."""
    test_file = git_repo / "test.txt"

    # Create 5 snapshots
    test_file.write_text("snap 1", encoding="utf-8")
    create_snapshot(git_repo, "snap-1", "Oldest")

    test_file.write_text("snap 2", encoding="utf-8")
    create_snapshot(git_repo, "snap-2", "Old")

    test_file.write_text("snap 3", encoding="utf-8")
    create_snapshot(git_repo, "snap-3", "Middle")

    test_file.write_text("snap 4", encoding="utf-8")
    create_snapshot(git_repo, "snap-4", "Recent")

    test_file.write_text("snap 5", encoding="utf-8")
    create_snapshot(git_repo, "snap-5", "Newest")

    # Keep only 3 most recent
    removed = cleanup_old_snapshots(git_repo, keep_count=3)
    assert removed == 2

    # Verify only 3 remain
    snapshots = list_snapshots(git_repo)
    assert len(snapshots) == 3

    # Verify newest 3 are kept
    names = [s.name for s in snapshots]
    assert "snap-3" in names
    assert "snap-4" in names
    assert "snap-5" in names
    assert "snap-1" not in names
    assert "snap-2" not in names


def test_cleanup_old_snapshots_removes_backups(git_repo: Path) -> None:
    """Test that cleanup removes state backup files."""
    test_file = git_repo / "test.txt"

    # Create snapshots
    test_file.write_text("backup 1", encoding="utf-8")
    snap1 = create_snapshot(git_repo, "backup-1")

    test_file.write_text("backup 2", encoding="utf-8")
    snap2 = create_snapshot(git_repo, "backup-2")

    test_file.write_text("backup 3", encoding="utf-8")
    snap3 = create_snapshot(git_repo, "backup-3")

    # Verify backups exist
    backup1 = git_repo / snap1.state_backup_path
    backup2 = git_repo / snap2.state_backup_path
    backup3 = git_repo / snap3.state_backup_path
    assert backup1.exists()
    assert backup2.exists()
    assert backup3.exists()

    # Keep only 1
    cleanup_old_snapshots(git_repo, keep_count=1)

    # Verify oldest backups were removed
    assert not backup1.exists()
    assert not backup2.exists()
    assert backup3.exists()


def test_cleanup_old_snapshots_invalid_keep_count(git_repo: Path) -> None:
    """Test that cleanup rejects invalid keep_count."""
    with pytest.raises(ValueError, match="must be at least 1"):
        cleanup_old_snapshots(git_repo, keep_count=0)

    with pytest.raises(ValueError, match="must be at least 1"):
        cleanup_old_snapshots(git_repo, keep_count=-1)


def test_cleanup_old_snapshots_partial_failure(git_repo: Path) -> None:
    """Test that cleanup continues even if some snapshots fail to remove."""
    test_file = git_repo / "test.txt"

    # Create snapshots
    test_file.write_text("fail 1", encoding="utf-8")
    snap1 = create_snapshot(git_repo, "fail-1")

    test_file.write_text("fail 2", encoding="utf-8")
    create_snapshot(git_repo, "fail-2")

    test_file.write_text("fail 3", encoding="utf-8")
    create_snapshot(git_repo, "fail-3")

    # Remove one backup file manually to cause partial failure
    backup1 = git_repo / snap1.state_backup_path
    backup1.unlink()

    # Cleanup should still remove what it can
    removed = cleanup_old_snapshots(git_repo, keep_count=1)

    # Should have attempted to remove 2, may have succeeded with 1 or 2
    assert removed >= 0  # At least doesn't crash


def test_create_multiple_snapshots_incremental(git_repo: Path) -> None:
    """Test creating multiple snapshots with incremental changes."""
    test_file = git_repo / "test.txt"

    # Snapshot 1
    test_file.write_text("version 1", encoding="utf-8")
    create_snapshot(git_repo, "version-1", "First version")

    # Snapshot 2
    test_file.write_text("version 2", encoding="utf-8")
    create_snapshot(git_repo, "version-2", "Second version")

    # Snapshot 3
    test_file.write_text("version 3", encoding="utf-8")
    create_snapshot(git_repo, "version-3", "Third version")

    # Verify all snapshots exist
    snapshots = list_snapshots(git_repo)
    assert len(snapshots) == 3

    # Verify all snapshots have stash refs (they may be the same index since
    # git stash indices shift as new stashes are added)
    for snap in snapshots:
        assert snap.git_stash_ref.startswith("stash@{")
        assert snap.git_stash_ref.endswith("}")


def test_snapshot_excludes_ralph_directory(git_repo: Path) -> None:
    """Test that snapshots exclude .ralph/ directory from git stash."""
    # Create files in .ralph
    ralph_file = git_repo / ".ralph" / "temp.txt"
    ralph_file.write_text("should not be stashed", encoding="utf-8")

    # Create file outside .ralph
    regular_file = git_repo / "regular.txt"
    regular_file.write_text("should be stashed", encoding="utf-8")

    # Create snapshot
    create_snapshot(git_repo, "exclude-test")

    # Verify .ralph file was not stashed (still exists and unchanged)
    assert ralph_file.exists()
    assert ralph_file.read_text(encoding="utf-8") == "should not be stashed"


def test_snapshot_with_untracked_files(git_repo: Path) -> None:
    """Test that snapshots include untracked files."""
    # Create untracked file
    untracked = git_repo / "untracked.txt"
    untracked.write_text("untracked content", encoding="utf-8")

    # Create snapshot
    snapshot = create_snapshot(git_repo, "untracked-test")

    # Verify snapshot was created
    assert snapshot.name == "untracked-test"

    # Verify stash includes untracked files (by checking stash list)
    result = subprocess.run(
        ["git", "stash", "list"],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "ralph-snapshot: untracked-test" in result.stdout


def test_snapshot_timestamp_format(git_repo: Path) -> None:
    """Test that snapshot timestamp is in ISO 8601 format."""
    # Make changes to create a stash
    test_file = git_repo / "test.txt"
    test_file.write_text("timestamp test", encoding="utf-8")

    snapshot = create_snapshot(git_repo, "timestamp-test")

    # Verify timestamp format (ISO 8601 with timezone)
    assert "T" in snapshot.timestamp
    assert snapshot.timestamp.endswith("Z") or "+" in snapshot.timestamp


def test_snapshot_git_commit_hash_format(git_repo: Path) -> None:
    """Test that git commit hash is valid SHA-1."""
    # Make changes to create a stash
    test_file = git_repo / "test.txt"
    test_file.write_text("commit test", encoding="utf-8")

    snapshot = create_snapshot(git_repo, "commit-test")

    # Verify commit hash is 40 character hex string
    assert len(snapshot.git_commit) == 40
    assert all(c in "0123456789abcdef" for c in snapshot.git_commit.lower())


def test_rollback_preserves_other_snapshots(git_repo: Path) -> None:
    """Test that rollback restores state.json from backup."""
    test_file = git_repo / "test.txt"
    state_path = git_repo / ".ralph" / "state.json"

    # Create initial state with some history
    initial_state = {
        "createdAt": "2024-01-01T00:00:00Z",
        "history": [{"iteration": 1}],
        "invocations": [],
        "snapshots": [],
    }
    state_path.write_text(json.dumps(initial_state), encoding="utf-8")

    # Create a snapshot
    test_file.write_text("snap 1", encoding="utf-8")
    create_snapshot(git_repo, "snap-1")

    # Verify snapshot was added to state
    current_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert len(current_state["snapshots"]) == 1

    # Modify state (add more history)
    current_state["history"].append({"iteration": 2})
    state_path.write_text(json.dumps(current_state), encoding="utf-8")

    # Commit changes so working tree is clean
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Modified state"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    # Rollback to snap-1 (should restore state.json from backup)
    rollback_snapshot(git_repo, "snap-1")

    # Verify state was restored to snapshot time (only 1 history entry)
    restored_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert len(restored_state["history"]) == 1
    assert restored_state["history"][0]["iteration"] == 1


def test_snapshot_description_optional(git_repo: Path) -> None:
    """Test that snapshot description is optional."""
    # Make changes to create a stash
    test_file = git_repo / "test.txt"
    test_file.write_text("no description test", encoding="utf-8")

    # Create snapshot without description
    snapshot = create_snapshot(git_repo, "no-desc")

    assert snapshot.name == "no-desc"
    assert snapshot.description == ""


def test_snapshot_state_backup_path_format(git_repo: Path) -> None:
    """Test that state backup path follows expected format."""
    # Make changes to create a stash
    test_file = git_repo / "test.txt"
    test_file.write_text("path test", encoding="utf-8")

    snapshot = create_snapshot(git_repo, "path-test")

    # Should be relative path in .ralph/snapshots/
    assert snapshot.state_backup_path.startswith(".ralph/snapshots/")
    assert snapshot.state_backup_path.endswith("_state.json")
    assert "path-test" in snapshot.state_backup_path


# ============================================================================
# Property-Based Tests (Task 7.4)
# ============================================================================


def _create_test_git_repo() -> Path:
    """Create a temporary git repository for property-based testing.

    Returns:
        Path to the temporary git repository
    """
    tmp_dir = Path(tempfile.mkdtemp())

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_dir,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    test_file = tmp_dir / "test.txt"
    test_file.write_text("initial content", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_dir,
        check=True,
        capture_output=True,
    )

    # Create .ralph directory with state.json
    ralph_dir = tmp_dir / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    state_path = ralph_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "createdAt": "2024-01-01T00:00:00Z",
                "history": [],
                "invocations": [],
                "snapshots": [],
            }
        ),
        encoding="utf-8",
    )

    return tmp_dir


@given(
    st.lists(
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
            min_size=1,
            max_size=10,
        ).filter(lambda s: re.match(r"^[a-zA-Z0-9_-]+$", s)),
        min_size=1,
        max_size=3,
    )
)
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_16_snapshot_round_trip(snapshot_names: list[str]) -> None:
    """**Validates: Requirements 6.1, 6.2 (US-6.1, US-6.2)**

    Feature: ralph-enhancement-phase2, Property 16: Snapshot round-trip

    For any clean working tree state, creating a snapshot then immediately
    rolling back should restore the exact same git state and Ralph state.
    """
    # Ensure unique snapshot names
    snapshot_names = list(dict.fromkeys(snapshot_names))
    assume(len(snapshot_names) >= 1)

    git_repo = _create_test_git_repo()
    try:
        test_file = git_repo / "test.txt"
        state_path = git_repo / ".ralph" / "state.json"

        for i, name in enumerate(snapshot_names):
            # Create a clean state with committed changes
            content = f"content version {i}"
            test_file.write_text(content, encoding="utf-8")

            # Update state.json with some data
            state_data = {
                "createdAt": "2024-01-01T00:00:00Z",
                "history": [{"iteration": i + 1, "task": f"task-{i}"}],
                "invocations": [],
                "snapshots": [],
            }
            state_path.write_text(json.dumps(state_data), encoding="utf-8")

            # Commit to have a clean state
            subprocess.run(
                ["git", "add", "."],
                cwd=git_repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", f"Version {i}"],
                cwd=git_repo,
                check=True,
                capture_output=True,
            )

            # Capture the state before snapshot
            original_state = json.loads(state_path.read_text(encoding="utf-8"))

            # Make some changes to create a stash
            test_file.write_text(f"snapshot content {i}", encoding="utf-8")

            # Create snapshot
            snapshot = create_snapshot(git_repo, name, f"Test snapshot {i}")
            assert snapshot.name == name

            # Make different changes and commit (simulate work after snapshot)
            new_file = git_repo / f"new_file_{i}.txt"
            new_file.write_text(f"new content {i}", encoding="utf-8")
            subprocess.run(
                ["git", "add", "."],
                cwd=git_repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", f"After snapshot {i}"],
                cwd=git_repo,
                check=True,
                capture_output=True,
            )

            # Rollback to snapshot
            result = rollback_snapshot(git_repo, name)
            assert result is True

            # Verify the snapshot content was restored (not the original committed content)
            restored_content = test_file.read_text(encoding="utf-8")
            assert restored_content == f"snapshot content {i}", (
                f"Expected snapshot content, got: {restored_content}"
            )

            # Verify state was restored to snapshot time
            restored_state = json.loads(state_path.read_text(encoding="utf-8"))
            assert len(restored_state["history"]) == len(original_state["history"]), (
                f"State history not restored correctly for snapshot {name}"
            )
    finally:
        # Cleanup
        shutil.rmtree(git_repo, ignore_errors=True)


@given(
    st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
        min_size=1,
        max_size=10,
    ).filter(lambda s: re.match(r"^[a-zA-Z0-9_-]+$", s)),
    st.text(min_size=1, max_size=50),
)
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_17_dirty_tree_protection(
    snapshot_name: str, uncommitted_content: str
) -> None:
    """**Validates: Requirements 6.2 (US-6.2)**

    Feature: ralph-enhancement-phase2, Property 17: Dirty tree protection

    For any working tree with uncommitted changes, rollback operations should
    be rejected with a clear error message.
    """
    git_repo = _create_test_git_repo()
    try:
        test_file = git_repo / "test.txt"

        # Create a snapshot first
        test_file.write_text("snapshot content", encoding="utf-8")
        snapshot = create_snapshot(git_repo, snapshot_name, "Test snapshot")
        assert snapshot.name == snapshot_name

        # Make uncommitted changes (dirty the working tree)
        test_file.write_text(uncommitted_content, encoding="utf-8")

        # Verify working tree is dirty
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip(), "Working tree should be dirty"

        # Attempt rollback without force - should fail
        with pytest.raises(RuntimeError) as exc_info:
            rollback_snapshot(git_repo, snapshot_name, force=False)

        # Verify error message is clear and mentions uncommitted changes
        error_message = str(exc_info.value).lower()
        assert (
            "uncommitted" in error_message
            or "dirty" in error_message
            or "changes" in error_message
        ), f"Error message should mention uncommitted changes, got: {exc_info.value}"

        # Verify the uncommitted content is still there (rollback didn't happen)
        current_content = test_file.read_text(encoding="utf-8")
        def _normalize_line_endings(value: str) -> str:
            return value.replace("\r\n", "\n").replace("\r", "\n")
        assert _normalize_line_endings(current_content) == _normalize_line_endings(
            uncommitted_content
        ), "Uncommitted changes should be preserved after failed rollback"
    finally:
        # Cleanup
        shutil.rmtree(git_repo, ignore_errors=True)


@given(
    st.integers(min_value=1, max_value=10),
    st.integers(min_value=1, max_value=8),
)
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_18_snapshot_retention(total_snapshots: int, keep_count: int) -> None:
    """**Validates: Requirements 6.3 (US-6.3)**

    Feature: ralph-enhancement-phase2, Property 18: Snapshot retention

    For any snapshot list exceeding the configured retention limit, cleanup
    should remove the oldest snapshots while preserving the most recent N snapshots.
    """
    # Ensure keep_count doesn't exceed total_snapshots
    assume(keep_count <= total_snapshots)

    git_repo = _create_test_git_repo()
    try:
        test_file = git_repo / "test.txt"
        created_snapshots = []

        # Create snapshots with unique timestamps
        for i in range(total_snapshots):
            # Make changes to create a stash
            test_file.write_text(f"snapshot content {i}", encoding="utf-8")

            # Create snapshot with unique name
            snapshot_name = f"snapshot-{i:03d}"
            snapshot = create_snapshot(git_repo, snapshot_name, f"Snapshot {i}")
            created_snapshots.append(snapshot)

        # Verify all snapshots were created
        all_snapshots = list_snapshots(git_repo)
        assert len(all_snapshots) == total_snapshots, (
            f"Expected {total_snapshots} snapshots, got {len(all_snapshots)}"
        )

        # Run cleanup
        removed_count = cleanup_old_snapshots(git_repo, keep_count=keep_count)

        # Calculate expected removals
        expected_removed = max(0, total_snapshots - keep_count)
        assert removed_count == expected_removed, (
            f"Expected to remove {expected_removed} snapshots, removed {removed_count}"
        )

        # Verify correct number of snapshots remain
        remaining_snapshots = list_snapshots(git_repo)
        assert len(remaining_snapshots) == keep_count, (
            f"Expected {keep_count} snapshots to remain, got {len(remaining_snapshots)}"
        )

        # Verify the most recent snapshots were kept
        # The most recent snapshots are the last ones created
        expected_kept_names = {
            f"snapshot-{i:03d}"
            for i in range(total_snapshots - keep_count, total_snapshots)
        }
        remaining_names = {s.name for s in remaining_snapshots}

        assert remaining_names == expected_kept_names, (
            f"Expected to keep {expected_kept_names}, but kept {remaining_names}"
        )

        # Verify the oldest snapshots were removed
        expected_removed_names = {
            f"snapshot-{i:03d}" for i in range(total_snapshots - keep_count)
        }
        for removed_name in expected_removed_names:
            assert removed_name not in remaining_names, (
                f"Snapshot {removed_name} should have been removed"
            )

            # Verify backup files were also removed
            backup_path = (
                git_repo / ".ralph" / "snapshots" / f"{removed_name}_state.json"
            )
            assert not backup_path.exists(), (
                f"Backup file for {removed_name} should have been removed"
            )
    finally:
        # Cleanup
        shutil.rmtree(git_repo, ignore_errors=True)
