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


def test_empty_md_prd_not_done():
    """Test that empty MD PRD returns False for all_done (not success)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ralph_dir = tmpdir / ".ralph"
        ralph_dir.mkdir()

        # Create MD PRD with no tasks
        prd_content = """# PRD

## Tasks
"""
        (ralph_dir / "PRD.md").write_text(prd_content)

        tracker = FileTracker(prd_path=ralph_dir / "PRD.md")
        assert tracker.all_done() is False, "Empty PRD should not be considered done"
        assert tracker.all_blocked() is False, "Empty PRD should not be considered blocked"


def test_empty_json_prd_not_done():
    """Test that empty JSON PRD returns False for all_done (not success)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ralph_dir = tmpdir / ".ralph"
        ralph_dir.mkdir()

        # Create JSON PRD with no stories
        json_content = """{"stories": []}"""
        (ralph_dir / "PRD.json").write_text(json_content)

        tracker = FileTracker(prd_path=ralph_dir / "PRD.json")
        assert tracker.all_done() is False, "Empty PRD should not be considered done"
        assert tracker.all_blocked() is False, "Empty PRD should not be considered blocked"


def test_empty_yaml_prd_not_done():
    """Test that empty YAML PRD returns False for all_done (not success)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ralph_dir = tmpdir / ".ralph"
        ralph_dir.mkdir()

        # Create YAML with no tasks
        yaml_content = """version: 1
metadata:
  title: Empty PRD
tasks: []
"""
        (ralph_dir / "tasks.yaml").write_text(yaml_content)

        tracker = YamlTracker(prd_path=ralph_dir / "tasks.yaml")
        assert tracker.all_done() is False, "Empty PRD should not be considered done"
        assert tracker.all_blocked() is False, "Empty PRD should not be considered blocked"


def test_empty_prd_consistency():
    """Test that all_done and all_blocked are consistent for empty PRDs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ralph_dir = tmpdir / ".ralph"
        ralph_dir.mkdir()

        # Test MD
        (ralph_dir / "PRD.md").write_text("# PRD\n\n## Tasks\n")
        tracker_md = FileTracker(prd_path=ralph_dir / "PRD.md")
        assert tracker_md.all_done() == tracker_md.all_blocked(), "MD: all_done and all_blocked should match"

        # Test JSON
        (ralph_dir / "PRD.json").write_text('{"stories": []}')
        tracker_json = FileTracker(prd_path=ralph_dir / "PRD.json")
        assert tracker_json.all_done() == tracker_json.all_blocked(), "JSON: all_done and all_blocked should match"

        # Test YAML
        (ralph_dir / "tasks.yaml").write_text("version: 1\nmetadata:\n  title: Empty\ntasks: []")
        tracker_yaml = YamlTracker(prd_path=ralph_dir / "tasks.yaml")
        assert tracker_yaml.all_done() == tracker_yaml.all_blocked(), "YAML: all_done and all_blocked should match"
