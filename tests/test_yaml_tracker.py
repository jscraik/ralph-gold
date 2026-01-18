"""Tests for YamlTracker implementation."""

import tempfile
from pathlib import Path

import pytest

from ralph_gold.trackers.yaml_tracker import YamlTracker


def test_yaml_tracker_load_valid():
    """Test loading a valid YAML file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
metadata:
  project: test-project
tasks:
  - id: 1
    title: First task
    completed: false
  - id: 2
    title: Second task
    completed: true
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        assert tracker.kind == "yaml"
        assert tracker.data["version"] == 1
        assert len(tracker.data["tasks"]) == 2
    finally:
        yaml_path.unlink()


def test_yaml_tracker_invalid_version():
    """Test that invalid version raises error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 2
tasks: []
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="Unsupported YAML version"):
            YamlTracker(yaml_path)
    finally:
        yaml_path.unlink()


def test_yaml_tracker_missing_tasks():
    """Test that missing tasks field raises error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
metadata:
  project: test
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="must have 'tasks' field"):
            YamlTracker(yaml_path)
    finally:
        yaml_path.unlink()


def test_yaml_tracker_peek_next_task():
    """Test peek_next_task returns first uncompleted task."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: true
  - id: 2
    title: Second task
    completed: false
  - id: 3
    title: Third task
    completed: false
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "2"
        assert task.title == "Second task"
        assert task.kind == "yaml"
    finally:
        yaml_path.unlink()


def test_yaml_tracker_counts():
    """Test counts returns correct completed/total."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: true
  - id: 2
    title: Second task
    completed: false
  - id: 3
    title: Third task
    completed: true
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        completed, total = tracker.counts()
        assert completed == 2
        assert total == 3
    finally:
        yaml_path.unlink()


def test_yaml_tracker_all_done():
    """Test all_done returns correct status."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: true
  - id: 2
    title: Second task
    completed: true
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        assert tracker.all_done() is True
    finally:
        yaml_path.unlink()


def test_yaml_tracker_is_task_done():
    """Test is_task_done checks specific task."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: true
  - id: 2
    title: Second task
    completed: false
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        assert tracker.is_task_done("1") is True
        assert tracker.is_task_done("2") is False
        assert tracker.is_task_done("999") is False
    finally:
        yaml_path.unlink()


def test_yaml_tracker_parallel_groups():
    """Test get_parallel_groups groups tasks correctly."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: Auth task
    group: auth
    completed: false
  - id: 2
    title: UI task
    group: ui
    completed: false
  - id: 3
    title: Another auth task
    group: auth
    completed: false
  - id: 4
    title: Default task
    completed: false
  - id: 5
    title: Completed task
    group: auth
    completed: true
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        groups = tracker.get_parallel_groups()

        assert "auth" in groups
        assert "ui" in groups
        assert "default" in groups

        assert len(groups["auth"]) == 2
        assert len(groups["ui"]) == 1
        assert len(groups["default"]) == 1

        # Verify completed tasks are excluded
        auth_ids = [task.id for task in groups["auth"]]
        assert "5" not in auth_ids
    finally:
        yaml_path.unlink()


def test_yaml_tracker_force_task_open():
    """Test force_task_open reopens a task."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: true
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        assert tracker.is_task_done("1") is True

        result = tracker.force_task_open("1")
        assert result is True

        # Reload to verify persistence
        tracker2 = YamlTracker(yaml_path)
        assert tracker2.is_task_done("1") is False
    finally:
        yaml_path.unlink()


def test_yaml_tracker_branch_name():
    """Test branch_name returns metadata branch."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
metadata:
  branch: feature/test-branch
tasks:
  - id: 1
    title: First task
    completed: false
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        assert tracker.branch_name() == "feature/test-branch"
    finally:
        yaml_path.unlink()


def test_yaml_tracker_acceptance_criteria():
    """Test that acceptance criteria are extracted."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: false
    acceptance:
      - User can log in
      - Token is returned
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        task = tracker.peek_next_task()
        assert task is not None
        assert len(task.acceptance) == 2
        assert "User can log in" in task.acceptance
        assert "Token is returned" in task.acceptance
    finally:
        yaml_path.unlink()


# Additional error case tests


def test_yaml_tracker_file_not_found():
    """Test that missing file raises FileNotFoundError."""
    yaml_path = Path("/nonexistent/path/tasks.yaml")
    with pytest.raises(FileNotFoundError, match="YAML file not found"):
        YamlTracker(yaml_path)


def test_yaml_tracker_invalid_yaml_syntax():
    """Test that malformed YAML raises ValueError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: "Unclosed quote
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="Invalid YAML syntax"):
            YamlTracker(yaml_path)
    finally:
        yaml_path.unlink()


def test_yaml_tracker_non_dict_root():
    """Test that non-dict root raises ValueError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("- item1\n- item2\n")
        f.flush()
        yaml_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="YAML root must be a dictionary"):
            YamlTracker(yaml_path)
    finally:
        yaml_path.unlink()


def test_yaml_tracker_tasks_not_list():
    """Test that non-list tasks field raises ValueError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks: "not a list"
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="'tasks' field must be a list"):
            YamlTracker(yaml_path)
    finally:
        yaml_path.unlink()


def test_yaml_tracker_task_not_dict():
    """Test that non-dict task raises ValueError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - "not a dict"
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="Task at index 0 must be a dictionary"):
            YamlTracker(yaml_path)
    finally:
        yaml_path.unlink()


def test_yaml_tracker_task_missing_id():
    """Test that task without id raises ValueError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - title: Task without ID
    completed: false
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        with pytest.raises(
            ValueError, match="Task at index 0 missing required 'id' field"
        ):
            YamlTracker(yaml_path)
    finally:
        yaml_path.unlink()


def test_yaml_tracker_task_missing_title():
    """Test that task without title raises ValueError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    completed: false
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        with pytest.raises(
            ValueError, match="Task at index 0 missing required 'title' field"
        ):
            YamlTracker(yaml_path)
    finally:
        yaml_path.unlink()


# Edge case tests


def test_yaml_tracker_empty_tasks():
    """Test tracker with empty tasks list."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks: []
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        assert tracker.peek_next_task() is None
        assert tracker.claim_next_task() is None
        assert tracker.all_done() is True
        assert tracker.counts() == (0, 0)
        assert tracker.get_parallel_groups() == {}
    finally:
        yaml_path.unlink()


def test_yaml_tracker_all_tasks_completed():
    """Test peek_next_task returns None when all tasks completed."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: true
  - id: 2
    title: Second task
    completed: true
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        assert tracker.peek_next_task() is None
        assert tracker.claim_next_task() is None
        assert tracker.all_done() is True
    finally:
        yaml_path.unlink()


def test_yaml_tracker_claim_same_as_peek():
    """Test that claim_next_task returns same task as peek_next_task."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: false
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        peeked = tracker.peek_next_task()
        claimed = tracker.claim_next_task()

        assert peeked is not None
        assert claimed is not None
        assert peeked.id == claimed.id
        assert peeked.title == claimed.title
    finally:
        yaml_path.unlink()


def test_yaml_tracker_force_task_open_nonexistent():
    """Test force_task_open returns False for nonexistent task."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: true
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        result = tracker.force_task_open("999")
        assert result is False
    finally:
        yaml_path.unlink()


def test_yaml_tracker_branch_name_no_metadata():
    """Test branch_name returns None when metadata is missing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: false
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        assert tracker.branch_name() is None
    finally:
        yaml_path.unlink()


def test_yaml_tracker_branch_name_no_branch_field():
    """Test branch_name returns None when branch field is missing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
metadata:
  project: test-project
tasks:
  - id: 1
    title: First task
    completed: false
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        assert tracker.branch_name() is None
    finally:
        yaml_path.unlink()


def test_yaml_tracker_task_without_acceptance():
    """Test task without acceptance criteria has empty list."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: false
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.acceptance == []
    finally:
        yaml_path.unlink()


def test_yaml_tracker_acceptance_not_list():
    """Test that non-list acceptance field is handled gracefully."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: false
    acceptance: "not a list"
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.acceptance == []
    finally:
        yaml_path.unlink()


def test_yaml_tracker_duplicate_task_ids():
    """Test tracker handles duplicate task IDs (last one wins for is_task_done)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: true
  - id: 1
    title: Duplicate task
    completed: false
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        # is_task_done should return the first match
        assert tracker.is_task_done("1") is True

        # peek_next_task should return the second one (first uncompleted)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.title == "Duplicate task"
    finally:
        yaml_path.unlink()


def test_yaml_tracker_parallel_groups_empty_when_all_completed():
    """Test get_parallel_groups returns empty dict when all tasks completed."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    group: auth
    completed: true
  - id: 2
    title: Second task
    group: ui
    completed: true
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        groups = tracker.get_parallel_groups()
        assert groups == {}
    finally:
        yaml_path.unlink()


def test_yaml_tracker_counts_with_missing_completed_field():
    """Test counts handles tasks without completed field (defaults to False)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
  - id: 2
    title: Second task
    completed: true
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        completed, total = tracker.counts()
        assert completed == 1
        assert total == 2
    finally:
        yaml_path.unlink()


def test_yaml_tracker_all_done_with_missing_completed_field():
    """Test all_done returns False when tasks lack completed field."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        assert tracker.all_done() is False
    finally:
        yaml_path.unlink()


def test_yaml_tracker_numeric_task_ids():
    """Test tracker handles numeric task IDs correctly."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 42
    title: Numeric ID task
    completed: false
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "42"
        assert tracker.is_task_done(42) is False
        assert tracker.is_task_done("42") is False
    finally:
        yaml_path.unlink()


def test_yaml_tracker_metadata_not_dict():
    """Test branch_name handles non-dict metadata gracefully."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
metadata: "not a dict"
tasks:
  - id: 1
    title: First task
    completed: false
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        assert tracker.branch_name() is None
    finally:
        yaml_path.unlink()


# Dependency support tests


def test_yaml_tracker_depends_on_field():
    """Test that depends_on field is extracted correctly."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: false
    depends_on: []
  - id: 2
    title: Second task
    completed: false
    depends_on: ["1"]
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)

        # First task should have no dependencies
        task1 = tracker.peek_next_task()
        assert task1 is not None
        assert task1.id == "1"
        assert task1.depends_on == []

        # Mark first task complete and check second task
        tracker.data["tasks"][0]["completed"] = True
        task2 = tracker.peek_next_task()
        assert task2 is not None
        assert task2.id == "2"
        assert task2.depends_on == ["1"]
    finally:
        yaml_path.unlink()


def test_yaml_tracker_depends_on_backward_compatible():
    """Test that tasks without depends_on field work correctly (backward compatible)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: false
  - id: 2
    title: Second task
    completed: false
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)

        # Both tasks should be available (no dependencies)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.depends_on == []
    finally:
        yaml_path.unlink()


def test_yaml_tracker_depends_on_blocks_task():
    """Test that tasks with unsatisfied dependencies are not selected."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: false
  - id: 2
    title: Second task (depends on 1)
    completed: false
    depends_on: ["1"]
  - id: 3
    title: Third task (depends on 2)
    completed: false
    depends_on: ["2"]
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)

        # Only task 1 should be available
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "1"

        # Mark task 1 complete
        tracker.data["tasks"][0]["completed"] = True

        # Now task 2 should be available
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "2"

        # Mark task 2 complete
        tracker.data["tasks"][1]["completed"] = True

        # Now task 3 should be available
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "3"
    finally:
        yaml_path.unlink()


def test_yaml_tracker_depends_on_multiple_dependencies():
    """Test that tasks with multiple dependencies wait for all to complete."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: false
  - id: 2
    title: Second task
    completed: false
  - id: 3
    title: Third task (depends on 1 and 2)
    completed: false
    depends_on: ["1", "2"]
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)

        # Task 1 or 2 should be available (both have no dependencies)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id in ["1", "2"]

        # Mark task 1 complete
        tracker.data["tasks"][0]["completed"] = True

        # Task 2 should be available, but not task 3 (still waiting for task 2)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "2"

        # Mark task 2 complete
        tracker.data["tasks"][1]["completed"] = True

        # Now task 3 should be available
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "3"
    finally:
        yaml_path.unlink()


def test_yaml_tracker_depends_on_invalid_type():
    """Test that invalid depends_on type is handled gracefully."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: false
    depends_on: "not-a-list"
  - id: 2
    title: Second task
    completed: false
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)

        # Task 1 should be available (invalid depends_on treated as empty)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "1"
        assert task.depends_on == []
    finally:
        yaml_path.unlink()


def test_yaml_tracker_depends_on_with_exclude():
    """Test that exclude_ids works correctly with dependencies."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: false
  - id: 2
    title: Second task
    completed: false
  - id: 3
    title: Third task (depends on 1)
    completed: false
    depends_on: ["1"]
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)

        # Exclude task 1, should get task 2
        task = tracker.select_next_task(exclude_ids={"1"})
        assert task is not None
        assert task.id == "2"

        # Exclude both 1 and 2, should get None (task 3 depends on 1 which is not complete)
        task = tracker.select_next_task(exclude_ids={"1", "2"})
        assert task is None
    finally:
        yaml_path.unlink()


def test_yaml_tracker_depends_on_nonexistent_dependency():
    """Test that tasks depending on nonexistent tasks are blocked."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: false
  - id: 2
    title: Second task (depends on nonexistent task)
    completed: false
    depends_on: ["999"]
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)

        # Only task 1 should be available (task 2 depends on nonexistent task)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "1"

        # Mark task 1 complete
        tracker.data["tasks"][0]["completed"] = True

        # Task 2 should still not be available (dependency never satisfied)
        task = tracker.peek_next_task()
        assert task is None
    finally:
        yaml_path.unlink()


def test_yaml_tracker_depends_on_blocked_task():
    """Test that blocked tasks count as completed for dependency purposes."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: false
    blocked: true
  - id: 2
    title: Second task (depends on 1)
    completed: false
    depends_on: ["1"]
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)

        # Task 2 should be available (task 1 is blocked, which counts as "done")
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "2"
    finally:
        yaml_path.unlink()


def test_yaml_tracker_depends_on_numeric_ids():
    """Test that numeric dependency IDs are handled correctly."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: 1
    title: First task
    completed: true
  - id: 2
    title: Second task
    completed: false
    depends_on: [1]
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)

        # Task 2 should be available (dependency satisfied)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "2"
        assert task.depends_on == ["1"]
    finally:
        yaml_path.unlink()
