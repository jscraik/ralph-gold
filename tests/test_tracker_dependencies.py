"""Integration tests for dependency support across all tracker types."""

import json
import tempfile
from pathlib import Path

from ralph_gold.trackers import FileTracker
from ralph_gold.trackers.yaml_tracker import YamlTracker


def test_json_tracker_dependencies():
    """Test that JSON tracker respects task dependencies."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        prd = {
            "stories": [
                {"id": "task-1", "title": "First task", "depends_on": []},
                {
                    "id": "task-2",
                    "title": "Second task",
                    "depends_on": ["task-1"],
                },
                {
                    "id": "task-3",
                    "title": "Third task",
                    "depends_on": ["task-2"],
                },
            ]
        }
        json.dump(prd, f)
        f.flush()
        json_path = Path(f.name)

    try:
        tracker = FileTracker(prd_path=json_path)

        # Only task-1 should be available
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "task-1"
        assert task.depends_on == []

        # Mark task-1 as done
        prd["stories"][0]["passes"] = True
        json_path.write_text(json.dumps(prd))

        # Now task-2 should be available
        tracker = FileTracker(prd_path=json_path)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "task-2"
        assert task.depends_on == ["task-1"]

        # Mark task-2 as done
        prd["stories"][1]["passes"] = True
        json_path.write_text(json.dumps(prd))

        # Now task-3 should be available
        tracker = FileTracker(prd_path=json_path)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "task-3"
        assert task.depends_on == ["task-2"]
    finally:
        json_path.unlink()


def test_markdown_tracker_dependencies():
    """Test that Markdown tracker respects task dependencies."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""# Test PRD

## Tasks

- [ ] First task
- [ ] Second task
  - Depends on: 1
- [ ] Third task
  - Depends on: 2
""")
        f.flush()
        md_path = Path(f.name)

    try:
        tracker = FileTracker(prd_path=md_path)

        # Only task 1 should be available (task 2 depends on 1, task 3 depends on 2)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "1"

        # Mark task 1 as done
        content = md_path.read_text()
        content = content.replace("- [ ] First task", "- [x] First task")
        md_path.write_text(content)

        # Now task 2 should be available
        tracker = FileTracker(prd_path=md_path)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "2"

        # Mark task 2 as done
        content = md_path.read_text()
        content = content.replace("- [ ] Second task", "- [x] Second task")
        md_path.write_text(content)

        # Now task 3 should be available
        tracker = FileTracker(prd_path=md_path)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "3"
    finally:
        md_path.unlink()


def test_yaml_tracker_dependencies():
    """Test that YAML tracker respects task dependencies."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: task-1
    title: First task
    completed: false
    depends_on: []
  - id: task-2
    title: Second task
    completed: false
    depends_on: ["task-1"]
  - id: task-3
    title: Third task
    completed: false
    depends_on: ["task-2"]
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)

        # Only task-1 should be available
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "task-1"
        assert task.depends_on == []

        # Mark task-1 as done
        tracker.data["tasks"][0]["completed"] = True

        # Now task-2 should be available
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "task-2"
        assert task.depends_on == ["task-1"]

        # Mark task-2 as done
        tracker.data["tasks"][1]["completed"] = True

        # Now task-3 should be available
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "task-3"
        assert task.depends_on == ["task-2"]
    finally:
        yaml_path.unlink()


def test_backward_compatibility_no_depends_on():
    """Test that tasks without depends_on field work correctly (backward compatible)."""
    # JSON format
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        prd = {
            "stories": [
                {"id": "task-1", "title": "First task"},
                {"id": "task-2", "title": "Second task"},
            ]
        }
        json.dump(prd, f)
        f.flush()
        json_path = Path(f.name)

    try:
        tracker = FileTracker(prd_path=json_path)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.depends_on == []
    finally:
        json_path.unlink()

    # Markdown format
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""# Test PRD

## Tasks

- [ ] First task
- [ ] Second task
""")
        f.flush()
        md_path = Path(f.name)

    try:
        tracker = FileTracker(prd_path=md_path)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.depends_on == []
    finally:
        md_path.unlink()

    # YAML format
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: task-1
    title: First task
    completed: false
  - id: task-2
    title: Second task
    completed: false
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.depends_on == []
    finally:
        yaml_path.unlink()


def test_multiple_dependencies_all_formats():
    """Test that tasks with multiple dependencies work in all formats."""
    # JSON format
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        prd = {
            "stories": [
                {"id": "task-1", "title": "First task"},
                {"id": "task-2", "title": "Second task"},
                {
                    "id": "task-3",
                    "title": "Third task",
                    "depends_on": ["task-1", "task-2"],
                },
            ]
        }
        json.dump(prd, f)
        f.flush()
        json_path = Path(f.name)

    try:
        tracker = FileTracker(prd_path=json_path)

        # Task 1 or 2 should be available
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id in ["task-1", "task-2"]

        # Mark both task-1 and task-2 as done
        prd["stories"][0]["passes"] = True
        prd["stories"][1]["passes"] = True
        json_path.write_text(json.dumps(prd))

        # Now task-3 should be available
        tracker = FileTracker(prd_path=json_path)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "task-3"
        assert set(task.depends_on) == {"task-1", "task-2"}
    finally:
        json_path.unlink()

    # YAML format
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: 1
tasks:
  - id: task-1
    title: First task
    completed: false
  - id: task-2
    title: Second task
    completed: false
  - id: task-3
    title: Third task
    completed: false
    depends_on: ["task-1", "task-2"]
""")
        f.flush()
        yaml_path = Path(f.name)

    try:
        tracker = YamlTracker(yaml_path)

        # Task 1 or 2 should be available
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id in ["task-1", "task-2"]

        # Mark both tasks as done
        tracker.data["tasks"][0]["completed"] = True
        tracker.data["tasks"][1]["completed"] = True

        # Now task-3 should be available
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "task-3"
        assert set(task.depends_on) == {"task-1", "task-2"}
    finally:
        yaml_path.unlink()


def test_markdown_tracker_with_subsection_headings():
    """Test that Markdown tracker handles ### subheadings within Tasks section.

    This is a regression test for the bug where ### Phase: subheadings
    caused the parser to stop scanning for tasks prematurely.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""# Test PRD

## Tasks

### Phase: Foundation

- [ ] First task
  - Acceptance criterion 1
- [ ] Second task
  - Depends on: 1

### Phase: Advanced

- [ ] Third task
  - Depends on: 2
  - Acceptance criterion 3

## Other Section
This should not be parsed as tasks.
""")
        f.flush()
        md_path = Path(f.name)

    try:
        tracker = FileTracker(prd_path=md_path)

        # All three tasks should be found (not stopped by ### headings)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "1"
        assert task.title == "First task"

        # Mark task 1 as done
        content = md_path.read_text()
        content = content.replace("- [ ] First task", "- [x] First task")
        md_path.write_text(content)

        # Now task 2 should be available
        tracker = FileTracker(prd_path=md_path)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "2"
        assert task.title == "Second task"

        # Mark task 2 as done
        content = md_path.read_text()
        content = content.replace("- [ ] Second task", "- [x] Second task")
        md_path.write_text(content)

        # Now task 3 should be available (it's after ### Phase: Advanced)
        tracker = FileTracker(prd_path=md_path)
        task = tracker.peek_next_task()
        assert task is not None
        assert task.id == "3"
        assert task.title == "Third task"

        # Verify acceptance criteria were captured (for task 3)
        assert "Acceptance criterion 3" in task.acceptance
    finally:
        md_path.unlink()
