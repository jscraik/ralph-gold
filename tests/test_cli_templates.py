"""Integration tests for template CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ralph_gold.cli import main


def test_task_templates_command(tmp_path: Path, monkeypatch):
    """Test 'ralph task templates' command."""
    # Setup a minimal Ralph project
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config
    config = """
[files]
prd = ".ralph/prd.json"

[loop]
max_iterations = 10
"""
    (ralph_dir / "ralph.toml").write_text(config, encoding="utf-8")

    # Change to test directory
    monkeypatch.chdir(tmp_path)

    # Run command
    exit_code = main(["task", "templates"])

    # Should succeed
    assert exit_code == 0


def test_task_add_command_json(tmp_path: Path, monkeypatch, capsys):
    """Test 'ralph task add' command with JSON tracker."""
    # Setup a minimal Ralph project
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config
    config = """
[files]
prd = ".ralph/prd.json"

[loop]
max_iterations = 10

[tracker]
kind = "json"
"""
    (ralph_dir / "ralph.toml").write_text(config, encoding="utf-8")

    # Create empty PRD
    prd_content = {"stories": []}
    prd_path = ralph_dir / "prd.json"
    prd_path.write_text(json.dumps(prd_content), encoding="utf-8")

    # Change to test directory
    monkeypatch.chdir(tmp_path)

    # Run command
    exit_code = main(["task", "add", "--template", "bug-fix", "--title", "Test bug"])

    # Should succeed
    assert exit_code == 0

    # Verify task was added
    updated_data = json.loads(prd_path.read_text(encoding="utf-8"))
    assert len(updated_data["stories"]) == 1

    new_task = updated_data["stories"][0]
    assert new_task["title"] == "Fix: Test bug"
    assert new_task["priority"] == "high"
    assert "Bug is reproducible with test case" in new_task["acceptance"]

    # Check output
    captured = capsys.readouterr()
    assert "Created task" in captured.out
    assert "bug-fix" in captured.out


def test_task_add_command_markdown(tmp_path: Path, monkeypatch, capsys):
    """Test 'ralph task add' command with Markdown tracker."""
    # Setup a minimal Ralph project
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config
    config = """
[files]
prd = ".ralph/PRD.md"

[loop]
max_iterations = 10

[tracker]
kind = "markdown"
"""
    (ralph_dir / "ralph.toml").write_text(config, encoding="utf-8")

    # Create PRD with Tasks section
    prd_content = """# Project PRD

## Tasks

- [x] 1. Existing task
"""
    prd_path = ralph_dir / "PRD.md"
    prd_path.write_text(prd_content, encoding="utf-8")

    # Change to test directory
    monkeypatch.chdir(tmp_path)

    # Run command
    exit_code = main(
        ["task", "add", "--template", "feature", "--title", "User authentication"]
    )

    # Should succeed
    assert exit_code == 0

    # Verify task was added
    updated_content = prd_path.read_text(encoding="utf-8")
    assert "- [ ] 2. Feature: User authentication" in updated_content
    assert "Requirements are documented" in updated_content

    # Check output
    captured = capsys.readouterr()
    assert "Created task" in captured.out
    assert "feature" in captured.out


def test_task_add_command_invalid_template(tmp_path: Path, monkeypatch, capsys):
    """Test 'ralph task add' with invalid template name."""
    # Setup a minimal Ralph project
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config
    config = """
[files]
prd = ".ralph/prd.json"

[loop]
max_iterations = 10
"""
    (ralph_dir / "ralph.toml").write_text(config, encoding="utf-8")

    # Create empty PRD
    prd_content = {"stories": []}
    prd_path = ralph_dir / "prd.json"
    prd_path.write_text(json.dumps(prd_content), encoding="utf-8")

    # Change to test directory
    monkeypatch.chdir(tmp_path)

    # Run command with invalid template
    exit_code = main(
        ["task", "add", "--template", "nonexistent", "--title", "Test task"]
    )

    # Should fail
    assert exit_code == 2

    # Check error output
    captured = capsys.readouterr()
    assert (
        "Template 'nonexistent' not found" in captured.err
        or "Template 'nonexistent' not found" in captured.out
    )
    assert "Available templates:" in captured.out


def test_task_add_command_with_custom_template(tmp_path: Path, monkeypatch, capsys):
    """Test 'ralph task add' with custom template."""
    # Setup a minimal Ralph project
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config
    config = """
[files]
prd = ".ralph/prd.json"

[loop]
max_iterations = 10
"""
    (ralph_dir / "ralph.toml").write_text(config, encoding="utf-8")

    # Create empty PRD
    prd_content = {"stories": []}
    prd_path = ralph_dir / "prd.json"
    prd_path.write_text(json.dumps(prd_content), encoding="utf-8")

    # Create custom template
    templates_dir = ralph_dir / "templates"
    templates_dir.mkdir()

    custom_template = {
        "name": "custom",
        "description": "Custom template",
        "title_template": "Custom: {title}",
        "acceptance_criteria": ["Custom criterion 1", "Custom criterion 2"],
        "priority": "medium",
        "variables": ["title"],
    }

    template_file = templates_dir / "custom.json"
    template_file.write_text(json.dumps(custom_template), encoding="utf-8")

    # Change to test directory
    monkeypatch.chdir(tmp_path)

    # Run command with custom template
    exit_code = main(["task", "add", "--template", "custom", "--title", "Test task"])

    # Should succeed
    assert exit_code == 0

    # Verify task was added with custom template
    updated_data = json.loads(prd_path.read_text(encoding="utf-8"))
    assert len(updated_data["stories"]) == 1

    new_task = updated_data["stories"][0]
    assert new_task["title"] == "Custom: Test task"
    assert new_task["priority"] == "medium"
    assert "Custom criterion 1" in new_task["acceptance"]
    assert "Custom criterion 2" in new_task["acceptance"]


def test_task_add_command_missing_title(tmp_path: Path, monkeypatch, capsys):
    """Test 'ralph task add' without required --title flag."""
    # Setup a minimal Ralph project
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config
    config = """
[files]
prd = ".ralph/prd.json"

[loop]
max_iterations = 10
"""
    (ralph_dir / "ralph.toml").write_text(config, encoding="utf-8")

    # Change to test directory
    monkeypatch.chdir(tmp_path)

    # Run command without title
    with pytest.raises(SystemExit) as exc_info:
        main(["task", "add", "--template", "bug-fix"])

    # Should exit with error
    assert exc_info.value.code == 2
