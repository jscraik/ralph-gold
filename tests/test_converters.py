"""Tests for PRD to YAML converters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ralph_gold.converters import (
    convert_json_to_yaml,
    convert_markdown_to_yaml,
    convert_to_yaml,
    save_yaml,
)


@pytest.fixture
def tmp_json_prd(tmp_path: Path) -> Path:
    """Create a temporary JSON PRD file."""
    prd = {
        "project": "test-project",
        "branchName": "feature/test",
        "stories": [
            {
                "id": 1,
                "title": "Implement user authentication",
                "description": "Add JWT-based authentication",
                "priority": 1,
                "acceptance": [
                    "User can log in with email/password",
                    "JWT token is returned on successful login",
                ],
                "passes": False,
            },
            {
                "id": 2,
                "title": "Create user profile UI",
                "description": "Build profile page",
                "priority": 2,
                "acceptance": [
                    "Profile page displays user info",
                    "User can edit profile fields",
                ],
                "status": "open",
            },
            {
                "id": 3,
                "title": "Add password reset",
                "priority": 3,
                "acceptance": ["User can request password reset"],
                "passes": True,
            },
        ],
    }

    path = tmp_path / "prd.json"
    path.write_text(json.dumps(prd, indent=2))
    return path


@pytest.fixture
def tmp_md_prd(tmp_path: Path) -> Path:
    """Create a temporary Markdown PRD file."""
    content = """# Test Project

Project: test-project
Branch: feature/test

## Tasks

- [ ] Implement user authentication
  - User can log in with email/password
  - JWT token is returned on successful login

- [ ] Create user profile UI
  - Profile page displays user info
  - User can edit profile fields

- [x] Add password reset
  - User can request password reset
"""

    path = tmp_path / "PRD.md"
    path.write_text(content)
    return path


def test_convert_json_to_yaml_basic(tmp_json_prd: Path):
    """Test basic JSON to YAML conversion."""
    yaml_data = convert_json_to_yaml(tmp_json_prd, infer_groups=False)

    # Check structure
    assert yaml_data["version"] == 1
    assert "metadata" in yaml_data
    assert "tasks" in yaml_data

    # Check metadata
    assert yaml_data["metadata"]["project"] == "test-project"
    assert yaml_data["metadata"]["branch"] == "feature/test"

    # Check tasks
    tasks = yaml_data["tasks"]
    assert len(tasks) == 3

    # Check first task
    assert tasks[0]["id"] == 1
    assert tasks[0]["title"] == "Implement user authentication"
    assert tasks[0]["description"] == "Add JWT-based authentication"
    assert tasks[0]["priority"] == 1
    assert tasks[0]["completed"] is False
    assert len(tasks[0]["acceptance"]) == 2

    # Check completed task
    assert tasks[2]["id"] == 3
    assert tasks[2]["completed"] is True


def test_convert_json_to_yaml_with_groups(tmp_json_prd: Path):
    """Test JSON to YAML conversion with group inference."""
    yaml_data = convert_json_to_yaml(tmp_json_prd, infer_groups=True)

    tasks = yaml_data["tasks"]

    # Check that groups were inferred
    assert "group" in tasks[0]
    assert "group" in tasks[1]
    assert "group" in tasks[2]

    # Authentication task should be in auth group
    assert tasks[0]["group"] == "auth"

    # UI task should be in ui group
    assert tasks[1]["group"] == "ui"


def test_convert_markdown_to_yaml_basic(tmp_md_prd: Path):
    """Test basic Markdown to YAML conversion."""
    yaml_data = convert_markdown_to_yaml(tmp_md_prd, infer_groups=False)

    # Check structure
    assert yaml_data["version"] == 1
    assert "metadata" in yaml_data
    assert "tasks" in yaml_data

    # Check metadata
    assert yaml_data["metadata"]["project"] == "test-project"
    assert yaml_data["metadata"]["branch"] == "feature/test"

    # Check tasks
    tasks = yaml_data["tasks"]
    assert len(tasks) == 3

    # Check first task
    assert tasks[0]["id"] == 1
    assert tasks[0]["title"] == "Implement user authentication"
    assert tasks[0]["completed"] is False
    assert len(tasks[0]["acceptance"]) == 2
    assert "User can log in with email/password" in tasks[0]["acceptance"]

    # Check completed task
    assert tasks[2]["id"] == 3
    assert tasks[2]["completed"] is True


def test_convert_markdown_to_yaml_with_groups(tmp_md_prd: Path):
    """Test Markdown to YAML conversion with group inference."""
    yaml_data = convert_markdown_to_yaml(tmp_md_prd, infer_groups=True)

    tasks = yaml_data["tasks"]

    # Check that groups were inferred
    assert "group" in tasks[0]
    assert "group" in tasks[1]

    # Authentication task should be in auth group
    assert tasks[0]["group"] == "auth"

    # UI task should be in ui group
    assert tasks[1]["group"] == "ui"


def test_save_yaml(tmp_path: Path):
    """Test saving YAML data to file."""
    yaml_data = {
        "version": 1,
        "metadata": {"project": "test"},
        "tasks": [{"id": 1, "title": "Task 1", "completed": False}],
    }

    output_path = tmp_path / "output.yaml"
    save_yaml(yaml_data, output_path)

    # Check file was created
    assert output_path.exists()

    # Check content is valid YAML
    with open(output_path) as f:
        loaded = yaml.safe_load(f)

    assert loaded["version"] == 1
    assert loaded["metadata"]["project"] == "test"
    assert len(loaded["tasks"]) == 1


def test_convert_to_yaml_json(tmp_json_prd: Path, tmp_path: Path):
    """Test end-to-end JSON to YAML conversion."""
    output_path = tmp_path / "tasks.yaml"

    convert_to_yaml(tmp_json_prd, output_path, infer_groups=False)

    # Check file was created
    assert output_path.exists()

    # Load and validate
    with open(output_path) as f:
        data = yaml.safe_load(f)

    assert data["version"] == 1
    assert len(data["tasks"]) == 3


def test_convert_to_yaml_markdown(tmp_md_prd: Path, tmp_path: Path):
    """Test end-to-end Markdown to YAML conversion."""
    output_path = tmp_path / "tasks.yaml"

    convert_to_yaml(tmp_md_prd, output_path, infer_groups=False)

    # Check file was created
    assert output_path.exists()

    # Load and validate
    with open(output_path) as f:
        data = yaml.safe_load(f)

    assert data["version"] == 1
    assert len(data["tasks"]) == 3


def test_convert_to_yaml_with_groups(tmp_json_prd: Path, tmp_path: Path):
    """Test conversion with group inference."""
    output_path = tmp_path / "tasks.yaml"

    convert_to_yaml(tmp_json_prd, output_path, infer_groups=True)

    # Load and check groups
    with open(output_path) as f:
        data = yaml.safe_load(f)

    tasks = data["tasks"]
    assert all("group" in task for task in tasks)


def test_convert_to_yaml_missing_file(tmp_path: Path):
    """Test conversion with missing input file."""
    input_path = tmp_path / "missing.json"
    output_path = tmp_path / "output.yaml"

    with pytest.raises(FileNotFoundError):
        convert_to_yaml(input_path, output_path)


def test_convert_to_yaml_unsupported_format(tmp_path: Path):
    """Test conversion with unsupported file format."""
    input_path = tmp_path / "file.txt"
    input_path.write_text("some content")
    output_path = tmp_path / "output.yaml"

    with pytest.raises(ValueError, match="Unsupported input format"):
        convert_to_yaml(input_path, output_path)


def test_convert_empty_json(tmp_path: Path):
    """Test converting JSON with no stories."""
    prd = {"stories": []}

    path = tmp_path / "empty.json"
    path.write_text(json.dumps(prd))

    yaml_data = convert_json_to_yaml(path, infer_groups=False)

    assert yaml_data["version"] == 1
    assert len(yaml_data["tasks"]) == 0


def test_convert_empty_markdown(tmp_path: Path):
    """Test converting Markdown with no tasks."""
    content = """# Project

## Tasks

No tasks yet.
"""

    path = tmp_path / "empty.md"
    path.write_text(content)

    yaml_data = convert_markdown_to_yaml(path, infer_groups=False)

    assert yaml_data["version"] == 1
    assert len(yaml_data["tasks"]) == 0


def test_group_inference_patterns():
    """Test group inference with various title patterns."""
    from ralph_gold.converters import _infer_group_from_title

    # Test prefix patterns
    assert _infer_group_from_title("API: Add endpoint", 0, 1) == "api"
    assert _infer_group_from_title("UI: Create button", 0, 1) == "ui"
    assert _infer_group_from_title("DB: Add migration", 0, 1) == "database"
    assert _infer_group_from_title("Test: Add unit tests", 0, 1) == "testing"

    # Test component mentions
    assert _infer_group_from_title("Add authentication flow", 0, 1) == "auth"
    assert _infer_group_from_title("Update database schema", 0, 1) == "database"
    assert _infer_group_from_title("Fix UI bug", 0, 1) == "ui"

    # Test default group
    assert _infer_group_from_title("Some random task", 0, 1) == "default"


def test_yaml_tracker_can_load_converted_file(tmp_json_prd: Path, tmp_path: Path):
    """Test that YamlTracker can load a converted file."""
    from ralph_gold.trackers.yaml_tracker import YamlTracker

    output_path = tmp_path / "tasks.yaml"
    convert_to_yaml(tmp_json_prd, output_path, infer_groups=True)

    # Load with YamlTracker
    tracker = YamlTracker(output_path)

    # Verify tracker works
    assert tracker.kind == "yaml"
    done, total = tracker.counts()
    assert total == 3
    assert done == 1

    # Check parallel groups
    groups = tracker.get_parallel_groups()
    assert len(groups) >= 1

    # Check next task
    next_task = tracker.peek_next_task()
    assert next_task is not None
    assert next_task.id == "1"


def test_conversion_preserves_all_data(tmp_json_prd: Path, tmp_path: Path):
    """Test that conversion preserves all task data."""
    output_path = tmp_path / "tasks.yaml"
    convert_to_yaml(tmp_json_prd, output_path, infer_groups=False)

    # Load original JSON
    with open(tmp_json_prd) as f:
        original = json.load(f)

    # Load converted YAML
    with open(output_path) as f:
        converted = yaml.safe_load(f)

    # Check all stories were converted
    assert len(converted["tasks"]) == len(original["stories"])

    # Check each task preserves data
    for i, story in enumerate(original["stories"]):
        task = converted["tasks"][i]

        assert task["id"] == story["id"]
        assert task["title"] == story["title"]

        if "description" in story:
            assert task.get("description") == story["description"]

        if "priority" in story:
            assert task.get("priority") == story["priority"]

        if "acceptance" in story:
            assert task.get("acceptance") == story["acceptance"]


def test_yaml_output_is_readable(tmp_json_prd: Path, tmp_path: Path):
    """Test that generated YAML is human-readable."""
    output_path = tmp_path / "tasks.yaml"
    convert_to_yaml(tmp_json_prd, output_path, infer_groups=True)

    # Read as text
    content = output_path.read_text()

    # Check for readable formatting
    assert "version: 1" in content
    assert "metadata:" in content
    assert "tasks:" in content
    assert "- id:" in content
    assert "  title:" in content

    # Check no flow style (should be block style)
    assert "{" not in content or content.count("{") < 3  # Allow minimal flow style

    # Check proper indentation
    lines = content.split("\n")
    task_lines = [line for line in lines if line.strip().startswith("- id:")]
    assert len(task_lines) == 3  # Should have 3 tasks
