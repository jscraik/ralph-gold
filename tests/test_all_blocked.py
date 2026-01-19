"""Tests for all_blocked() functionality across all tracker types."""

import tempfile
from pathlib import Path

import pytest

from ralph_gold.trackers.yaml_tracker import YamlTracker
from ralph_gold.trackers import FileTracker
from ralph_gold.prd import all_blocked as prd_all_blocked


def test_all_blocked_when_all_blocked():
    """Test all_blocked returns True when all remaining tasks are blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ralph_dir = tmpdir / ".ralph"
        ralph_dir.mkdir()

        # Create MD PRD with all blocked tasks
        prd_content = """# PRD

## Tasks

- [-] Task 1 (depends on: nonexistent)
- [-] Task 2 (depends on: nonexistent)
"""
        (ralph_dir / "PRD.md").write_text(prd_content)

        # Test FileTracker
        tracker = FileTracker(prd_path=ralph_dir / "PRD.md")
        assert tracker.all_blocked() is True

        # Test prd_all_blocked function
        assert prd_all_blocked(ralph_dir / "PRD.md") is True


def test_all_blocked_when_mixed():
    """Test all_blocked returns False when there are mixed states."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ralph_dir = tmpdir / ".ralph"
        ralph_dir.mkdir()

        # Create MD PRD with mixed states
        prd_content = """# PRD

## Tasks

- [ ] Task 1
- [-] Task 2 (depends on: nonexistent)
- [x] Task 3
"""
        (ralph_dir / "PRD.md").write_text(prd_content)

        # Test FileTracker
        tracker = FileTracker(prd_path=ralph_dir / "PRD.md")
        assert tracker.all_blocked() is False

        # Test prd_all_blocked function
        assert prd_all_blocked(ralph_dir / "PRD.md") is False


def test_all_blocked_when_all_done():
    """Test all_blocked returns False when all tasks are done (not blocked)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ralph_dir = tmpdir / ".ralph"
        ralph_dir.mkdir()

        # Create MD PRD with all done tasks
        prd_content = """# PRD

## Tasks

- [x] Task 1
- [x] Task 2
"""
        (ralph_dir / "PRD.md").write_text(prd_content)

        # Test FileTracker
        tracker = FileTracker(prd_path=ralph_dir / "PRD.md")
        assert tracker.all_blocked() is False

        # Test prd_all_blocked function
        assert prd_all_blocked(ralph_dir / "PRD.md") is False


def test_all_blocked_empty_prd():
    """Test all_blocked returns False when PRD has no tasks (done, not blocked)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ralph_dir = tmpdir / ".ralph"
        ralph_dir.mkdir()

        # Create MD PRD with no tasks
        prd_content = """# PRD

## Tasks
"""
        (ralph_dir / "PRD.md").write_text(prd_content)

        # Test FileTracker
        tracker = FileTracker(prd_path=ralph_dir / "PRD.md")
        assert tracker.all_blocked() is False

        # Test prd_all_blocked function
        assert prd_all_blocked(ralph_dir / "PRD.md") is False


def test_yaml_tracker_all_blocked():
    """Test YamlTracker all_blocked implementation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ralph_dir = tmpdir / ".ralph"
        ralph_dir.mkdir()

        # Create YAML with all blocked tasks
        yaml_content = """version: 1
metadata:
  title: Test PRD
tasks:
  - id: 1
    title: Task 1
    completed: false
    blocked: true
  - id: 2
    title: Task 2
    completed: false
    blocked: true
"""
        (ralph_dir / "tasks.yaml").write_text(yaml_content)

        tracker = YamlTracker(prd_path=ralph_dir / "tasks.yaml")
        assert tracker.all_blocked() is True


def test_yaml_tracker_all_blocked_mixed():
    """Test YamlTracker all_blocked with mixed states."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ralph_dir = tmpdir / ".ralph"
        ralph_dir.mkdir()

        # Create YAML with mixed states
        yaml_content = """version: 1
metadata:
  title: Test PRD
tasks:
  - id: 1
    title: Task 1
    completed: false
    blocked: false
  - id: 2
    title: Task 2
    completed: false
    blocked: true
"""
        (ralph_dir / "tasks.yaml").write_text(yaml_content)

        tracker = YamlTracker(prd_path=ralph_dir / "tasks.yaml")
        assert tracker.all_blocked() is False


def test_yaml_tracker_all_blocked_when_all_done():
    """Test YamlTracker all_blocked returns False when all done (not blocked)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ralph_dir = tmpdir / ".ralph"
        ralph_dir.mkdir()

        # Create YAML with all done tasks
        yaml_content = """version: 1
metadata:
  title: Test PRD
tasks:
  - id: 1
    title: Task 1
    completed: true
    blocked: false
  - id: 2
    title: Task 2
    completed: true
    blocked: false
"""
        (ralph_dir / "tasks.yaml").write_text(yaml_content)

        tracker = YamlTracker(prd_path=ralph_dir / "tasks.yaml")
        assert tracker.all_blocked() is False


def test_file_tracker_all_blocked():
    """Test FileTracker all_blocked with MD PRD."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ralph_dir = tmpdir / ".ralph"
        ralph_dir.mkdir()

        # Create MD PRD with all blocked tasks
        prd_content = """# PRD

## Tasks

- [-] Task 1 (depends on: nonexistent)
- [-] Task 2 (depends on: nonexistent)
"""
        (ralph_dir / "PRD.md").write_text(prd_content)

        tracker = FileTracker(prd_path=ralph_dir / "PRD.md")
        assert tracker.all_blocked() is True


def test_file_tracker_all_blocked_json():
    """Test FileTracker all_blocked with JSON PRD."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ralph_dir = tmpdir / ".ralph"
        ralph_dir.mkdir()

        # Create JSON PRD with all blocked tasks
        json_content = """{
  "stories": [
    {"id": "1", "title": "Task 1", "status": "blocked"},
    {"id": "2", "title": "Task 2", "status": "blocked"}
  ]
}"""
        (ralph_dir / "PRD.json").write_text(json_content)

        tracker = FileTracker(prd_path=ralph_dir / "PRD.json")
        assert tracker.all_blocked() is True
