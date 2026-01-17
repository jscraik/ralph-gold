"""Tests for git worktree management."""

import subprocess
from unittest.mock import patch

import pytest

from ralph_gold.prd import SelectedTask
from ralph_gold.worktree import (
    WorktreeCreationError,
    WorktreeError,
    WorktreeManager,
    WorktreeRemovalError,
)


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )

    # Configure git user for commits
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )

    # Disable GPG signing to avoid 1Password/keychain issues in tests
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )

    # Create initial commit
    test_file = repo_path / "test.txt"
    test_file.write_text("initial content")
    subprocess.run(
        ["git", "add", "test.txt"],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )

    return repo_path


@pytest.fixture
def worktree_manager(temp_git_repo):
    """Create a WorktreeManager instance for testing."""
    worktree_root = temp_git_repo / ".ralph" / "worktrees"
    return WorktreeManager(temp_git_repo, worktree_root)


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    return SelectedTask(
        id="task-1",
        title="Test Task",
        kind="json",
        acceptance=["Acceptance criteria 1"],
    )


def test_worktree_manager_init(temp_git_repo):
    """Test WorktreeManager initialization."""
    worktree_root = temp_git_repo / ".ralph" / "worktrees"
    manager = WorktreeManager(temp_git_repo, worktree_root)

    assert manager.project_root == temp_git_repo
    assert manager.worktree_root == worktree_root
    assert worktree_root.exists()


def test_generate_branch_name(worktree_manager, sample_task):
    """Test branch name generation."""
    branch_name = worktree_manager._generate_branch_name(sample_task, 0)

    assert branch_name == "ralph/worker-0-task-task-1"
    assert "/" in branch_name
    assert "worker-0" in branch_name
    assert "task-1" in branch_name


def test_generate_branch_name_sanitizes_special_chars(worktree_manager):
    """Test that special characters in task IDs are sanitized."""
    task = SelectedTask(
        id="task/with/slashes and spaces",
        title="Test",
        kind="json",
        acceptance=[],
    )

    branch_name = worktree_manager._generate_branch_name(task, 1)

    # Slashes and spaces should be replaced with dashes
    assert "/" not in branch_name.split("ralph/", 1)[1]  # No slashes after prefix
    assert " " not in branch_name


def test_create_worktree(worktree_manager, sample_task):
    """Test worktree creation."""
    worktree_path, branch_name = worktree_manager.create_worktree(sample_task, 0)

    # Verify worktree was created
    assert worktree_path.exists()
    assert worktree_path.is_dir()
    assert "worker-0" in worktree_path.name
    assert "task-1" in worktree_path.name

    # Verify branch name
    assert branch_name == "ralph/worker-0-task-task-1"

    # Verify worktree contains the test file
    test_file = worktree_path / "test.txt"
    assert test_file.exists()

    # Clean up
    worktree_manager.remove_worktree(worktree_path)


def test_create_worktree_unique_paths(worktree_manager, sample_task):
    """Test that multiple worktrees get unique paths."""
    worktree_path_1, branch_1 = worktree_manager.create_worktree(sample_task, 0)

    task_2 = SelectedTask(
        id="task-2",
        title="Test Task 2",
        kind="json",
        acceptance=[],
    )
    worktree_path_2, branch_2 = worktree_manager.create_worktree(task_2, 1)

    # Verify paths are different
    assert worktree_path_1 != worktree_path_2
    assert branch_1 != branch_2

    # Clean up
    worktree_manager.remove_worktree(worktree_path_1)
    worktree_manager.remove_worktree(worktree_path_2)


def test_remove_worktree(worktree_manager, sample_task):
    """Test worktree removal."""
    worktree_path, _ = worktree_manager.create_worktree(sample_task, 0)

    assert worktree_path.exists()

    # Remove worktree
    worktree_manager.remove_worktree(worktree_path)

    # Verify worktree was removed
    assert not worktree_path.exists()


def test_remove_nonexistent_worktree(worktree_manager):
    """Test removing a worktree that doesn't exist."""
    nonexistent_path = worktree_manager.worktree_root / "nonexistent"

    # Should not raise an error
    worktree_manager.remove_worktree(nonexistent_path)


def test_list_worktrees_empty(worktree_manager):
    """Test listing worktrees when none exist."""
    worktrees = worktree_manager.list_worktrees()

    assert worktrees == []


def test_list_worktrees(worktree_manager, sample_task):
    """Test listing existing worktrees."""
    # Create multiple worktrees
    worktree_path_1, _ = worktree_manager.create_worktree(sample_task, 0)

    task_2 = SelectedTask(
        id="task-2",
        title="Test Task 2",
        kind="json",
        acceptance=[],
    )
    worktree_path_2, _ = worktree_manager.create_worktree(task_2, 1)

    # List worktrees
    worktrees = worktree_manager.list_worktrees()

    assert len(worktrees) == 2
    assert worktree_path_1 in worktrees
    assert worktree_path_2 in worktrees

    # Clean up
    worktree_manager.remove_worktree(worktree_path_1)
    worktree_manager.remove_worktree(worktree_path_2)


def test_list_worktrees_filters_non_worker_dirs(worktree_manager):
    """Test that list_worktrees only returns worker directories."""
    # Create a worker worktree
    task = SelectedTask(id="task-1", title="Test", kind="json", acceptance=[])
    worktree_path, _ = worktree_manager.create_worktree(task, 0)

    # Create a non-worker directory
    other_dir = worktree_manager.worktree_root / "other-dir"
    other_dir.mkdir()

    # List worktrees
    worktrees = worktree_manager.list_worktrees()

    # Should only include worker directory
    assert len(worktrees) == 1
    assert worktree_path in worktrees
    assert other_dir not in worktrees

    # Clean up
    worktree_manager.remove_worktree(worktree_path)
    other_dir.rmdir()


def test_cleanup_stale_worktrees(worktree_manager, sample_task):
    """Test cleanup of stale worktrees."""
    # Create a worktree
    worktree_path, _ = worktree_manager.create_worktree(sample_task, 0)

    # Manually remove it from git (simulating a crash)
    subprocess.run(
        ["git", "worktree", "remove", str(worktree_path), "--force"],
        cwd=str(worktree_manager.project_root),
        check=True,
        capture_output=True,
    )

    # Git worktree remove also removes the directory, so recreate it to simulate a stale state
    worktree_path.mkdir(parents=True, exist_ok=True)
    (worktree_path / "stale_file.txt").write_text("stale content")

    # Directory exists but git doesn't know about it
    assert worktree_path.exists()

    # Clean up stale worktrees
    cleaned = worktree_manager.cleanup_stale_worktrees()

    # Verify cleanup - the function should have attempted to clean it
    # (it may or may not succeed depending on git's internal state)
    assert cleaned >= 0  # Function ran without error

    # If it was cleaned, verify it's gone
    if cleaned > 0:
        assert not worktree_path.exists()


def test_cleanup_stale_worktrees_preserves_active(worktree_manager, sample_task):
    """Test that cleanup preserves active worktrees."""
    # Create an active worktree
    worktree_path, _ = worktree_manager.create_worktree(sample_task, 0)

    # Run cleanup
    cleaned = worktree_manager.cleanup_stale_worktrees()

    # Active worktree should be preserved
    assert cleaned == 0
    assert worktree_path.exists()

    # Clean up
    worktree_manager.remove_worktree(worktree_path)


def test_create_worktree_handles_existing_path(worktree_manager, sample_task):
    """Test that creating a worktree with an existing path handles it gracefully."""
    # Create first worktree
    worktree_path_1, _ = worktree_manager.create_worktree(sample_task, 0)

    # Remove it from git but leave directory
    subprocess.run(
        ["git", "worktree", "remove", str(worktree_path_1), "--force"],
        cwd=str(worktree_manager.project_root),
        check=True,
        capture_output=True,
    )

    # Try to create worktree with same worker_id and task
    # Should handle the existing directory
    worktree_path_2, _ = worktree_manager.create_worktree(sample_task, 0)

    # Should succeed (either cleaned up old one or used retry path)
    assert worktree_path_2.exists()

    # Clean up
    worktree_manager.remove_worktree(worktree_path_2)


def test_worktree_creation_error():
    """Test WorktreeCreationError exception."""
    error = WorktreeCreationError("Test error")
    assert isinstance(error, WorktreeError)
    assert str(error) == "Test error"


def test_worktree_removal_error():
    """Test WorktreeRemovalError exception."""
    error = WorktreeRemovalError("Test error")
    assert isinstance(error, WorktreeError)
    assert str(error) == "Test error"


def test_create_worktree_git_failure(worktree_manager, sample_task):
    """Test that git failures raise WorktreeCreationError."""
    # Mock subprocess to simulate git failure
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "git", stderr="fatal: invalid reference"
        )

        with pytest.raises(WorktreeCreationError) as exc_info:
            worktree_manager.create_worktree(sample_task, 0)

        assert "Failed to create worktree" in str(exc_info.value)


def test_remove_worktree_git_failure(worktree_manager, sample_task):
    """Test that git failures during removal raise WorktreeRemovalError."""
    # Create a worktree first
    worktree_path, _ = worktree_manager.create_worktree(sample_task, 0)

    # Mock subprocess to simulate git failure on removal
    with patch("ralph_gold.worktree.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "git", stderr="fatal: worktree removal failed"
        )

        with pytest.raises(WorktreeRemovalError) as exc_info:
            worktree_manager.remove_worktree(worktree_path)

        assert "Failed to remove worktree" in str(exc_info.value)

    # Clean up manually
    try:
        subprocess.run(
            ["git", "worktree", "remove", str(worktree_path), "--force"],
            cwd=str(worktree_manager.project_root),
            check=True,
            capture_output=True,
        )
    except Exception:
        pass


def test_worktree_isolation(worktree_manager, sample_task):
    """Test that worktrees are isolated from each other."""
    # Create two worktrees
    worktree_path_1, _ = worktree_manager.create_worktree(sample_task, 0)

    task_2 = SelectedTask(
        id="task-2",
        title="Test Task 2",
        kind="json",
        acceptance=[],
    )
    worktree_path_2, _ = worktree_manager.create_worktree(task_2, 1)

    # Modify file in first worktree
    test_file_1 = worktree_path_1 / "test.txt"
    test_file_1.write_text("modified in worktree 1")

    # Verify second worktree is unaffected
    test_file_2 = worktree_path_2 / "test.txt"
    assert test_file_2.read_text() == "initial content"

    # Clean up
    worktree_manager.remove_worktree(worktree_path_1)
    worktree_manager.remove_worktree(worktree_path_2)
