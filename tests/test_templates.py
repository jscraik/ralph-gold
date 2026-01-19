"""Unit tests for task template management."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ralph_gold.templates import (
    TaskTemplate,
    TemplateError,
    create_task_from_template,
    list_templates,
    load_builtin_templates,
    load_custom_templates,
)

# Test template loading


def test_load_builtin_templates():
    """Test that built-in templates are loaded correctly."""
    templates = load_builtin_templates()

    # Should have 3 built-in templates
    assert len(templates) == 3
    assert "bug-fix" in templates
    assert "feature" in templates
    assert "refactor" in templates

    # Check bug-fix template
    bug_fix = templates["bug-fix"]
    assert bug_fix.name == "bug-fix"
    assert bug_fix.description == "Template for bug fixes"
    assert bug_fix.title_template == "Fix: {title}"
    assert bug_fix.priority == "high"
    assert "title" in bug_fix.variables
    assert len(bug_fix.acceptance_criteria) == 4

    # Check feature template
    feature = templates["feature"]
    assert feature.name == "feature"
    assert feature.priority == "medium"
    assert feature.title_template == "Feature: {title}"

    # Check refactor template
    refactor = templates["refactor"]
    assert refactor.name == "refactor"
    assert refactor.priority == "low"
    assert refactor.title_template == "Refactor: {title}"


def test_load_custom_templates_no_directory(tmp_path: Path):
    """Test loading custom templates when directory doesn't exist."""
    templates = load_custom_templates(tmp_path)
    assert templates == {}


def test_load_custom_templates_empty_directory(tmp_path: Path):
    """Test loading custom templates from empty directory."""
    templates_dir = tmp_path / ".ralph" / "templates"
    templates_dir.mkdir(parents=True)

    templates = load_custom_templates(tmp_path)
    assert templates == {}


def test_load_custom_templates_valid(tmp_path: Path):
    """Test loading valid custom templates."""
    templates_dir = tmp_path / ".ralph" / "templates"
    templates_dir.mkdir(parents=True)

    # Create a custom template
    custom_template = {
        "name": "custom-task",
        "description": "Custom task template",
        "title_template": "Custom: {title}",
        "acceptance_criteria": ["Criterion 1", "Criterion 2"],
        "priority": "high",
        "variables": ["title"],
        "metadata": {"author": "test"},
    }

    template_file = templates_dir / "custom-task.json"
    template_file.write_text(json.dumps(custom_template), encoding="utf-8")

    templates = load_custom_templates(tmp_path)

    assert len(templates) == 1
    assert "custom-task" in templates

    template = templates["custom-task"]
    assert template.name == "custom-task"
    assert template.description == "Custom task template"
    assert template.title_template == "Custom: {title}"
    assert template.priority == "high"
    assert len(template.acceptance_criteria) == 2
    assert template.variables == ["title"]
    assert template.metadata == {"author": "test"}


def test_load_custom_templates_with_defaults(tmp_path: Path):
    """Test loading custom template with default values."""
    templates_dir = tmp_path / ".ralph" / "templates"
    templates_dir.mkdir(parents=True)

    # Create template with minimal fields (no priority, variables, metadata)
    minimal_template = {
        "name": "minimal",
        "description": "Minimal template",
        "title_template": "{title}",
        "acceptance_criteria": ["Done"],
    }

    template_file = templates_dir / "minimal.json"
    template_file.write_text(json.dumps(minimal_template), encoding="utf-8")

    templates = load_custom_templates(tmp_path)

    template = templates["minimal"]
    assert template.priority == "medium"  # Default
    assert template.variables == []  # Default
    assert template.metadata == {}  # Default


def test_load_custom_templates_missing_required_field(tmp_path: Path):
    """Test that loading template with missing required field raises error."""
    templates_dir = tmp_path / ".ralph" / "templates"
    templates_dir.mkdir(parents=True)

    # Missing 'title_template' field
    invalid_template = {
        "name": "invalid",
        "description": "Invalid template",
        "acceptance_criteria": ["Done"],
    }

    template_file = templates_dir / "invalid.json"
    template_file.write_text(json.dumps(invalid_template), encoding="utf-8")

    with pytest.raises(TemplateError, match="missing required fields"):
        load_custom_templates(tmp_path)


def test_load_custom_templates_invalid_json(tmp_path: Path):
    """Test that loading invalid JSON raises error."""
    templates_dir = tmp_path / ".ralph" / "templates"
    templates_dir.mkdir(parents=True)

    template_file = templates_dir / "invalid.json"
    template_file.write_text("{ invalid json }", encoding="utf-8")

    with pytest.raises(TemplateError, match="Invalid JSON"):
        load_custom_templates(tmp_path)


def test_load_custom_templates_invalid_acceptance_criteria(tmp_path: Path):
    """Test that non-list acceptance_criteria raises error."""
    templates_dir = tmp_path / ".ralph" / "templates"
    templates_dir.mkdir(parents=True)

    invalid_template = {
        "name": "invalid",
        "description": "Invalid template",
        "title_template": "{title}",
        "acceptance_criteria": "Not a list",  # Should be a list
    }

    template_file = templates_dir / "invalid.json"
    template_file.write_text(json.dumps(invalid_template), encoding="utf-8")

    with pytest.raises(TemplateError, match="acceptance_criteria must be a list"):
        load_custom_templates(tmp_path)


def test_load_custom_templates_multiple_files(tmp_path: Path):
    """Test loading multiple custom templates."""
    templates_dir = tmp_path / ".ralph" / "templates"
    templates_dir.mkdir(parents=True)

    # Create two templates
    for i in range(1, 3):
        template = {
            "name": f"template-{i}",
            "description": f"Template {i}",
            "title_template": f"Task {i}: {{title}}",
            "acceptance_criteria": [f"Criterion {i}"],
        }
        template_file = templates_dir / f"template-{i}.json"
        template_file.write_text(json.dumps(template), encoding="utf-8")

    templates = load_custom_templates(tmp_path)

    assert len(templates) == 2
    assert "template-1" in templates
    assert "template-2" in templates


# Test variable substitution


def test_substitute_variables_simple():
    """Test simple variable substitution."""
    from ralph_gold.templates import _substitute_variables

    result = _substitute_variables("Fix: {title}", {"title": "Login bug"})
    assert result == "Fix: Login bug"


def test_substitute_variables_multiple():
    """Test multiple variable substitution."""
    from ralph_gold.templates import _substitute_variables

    result = _substitute_variables(
        "Fix {title} in {component}", {"title": "bug", "component": "auth"}
    )
    assert result == "Fix bug in auth"


def test_substitute_variables_no_variables():
    """Test text without variables."""
    from ralph_gold.templates import _substitute_variables

    result = _substitute_variables("Plain text", {})
    assert result == "Plain text"


def test_substitute_variables_unused_variables():
    """Test that unused variables don't affect result."""
    from ralph_gold.templates import _substitute_variables

    result = _substitute_variables("Fix: {title}", {"title": "bug", "extra": "unused"})
    assert result == "Fix: bug"


def test_substitute_variables_missing_variable():
    """Test that missing variables are left as placeholders."""
    from ralph_gold.templates import _substitute_variables

    result = _substitute_variables("Fix: {title}", {})
    assert result == "Fix: {title}"


# Test task creation for Markdown tracker


def test_create_task_from_template_markdown(tmp_path: Path):
    """Test creating a task from template with Markdown tracker."""
    # Create a Markdown PRD
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    prd_content = """# Project PRD

## Tasks

- [x] 1. Existing task
  **Acceptance Criteria:**
  - Done

"""
    prd_path = ralph_dir / "PRD.md"
    prd_path.write_text(prd_content, encoding="utf-8")

    # Create tracker directly
    from ralph_gold.trackers import FileTracker

    tracker = FileTracker(prd_path=prd_path)

    # Load template and create task
    templates = load_builtin_templates()
    bug_fix = templates["bug-fix"]

    variables = {"title": "Login fails on Safari"}
    task_id = create_task_from_template(bug_fix, variables, tracker)

    # Verify task was created
    assert task_id == "2"

    # Read PRD and verify content
    updated_content = prd_path.read_text(encoding="utf-8")
    assert "- [ ] 2. Fix: Login fails on Safari" in updated_content
    assert "Bug is reproducible with test case" in updated_content
    assert "Root cause is identified" in updated_content


def test_create_task_from_template_markdown_no_tasks_section(tmp_path: Path):
    """Test that creating task fails if no Tasks section exists."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    prd_content = """# Project PRD

## Overview

This is a project.
"""
    prd_path = ralph_dir / "PRD.md"
    prd_path.write_text(prd_content, encoding="utf-8")

    from ralph_gold.trackers import FileTracker

    tracker = FileTracker(prd_path=prd_path)

    templates = load_builtin_templates()
    bug_fix = templates["bug-fix"]

    with pytest.raises(TemplateError, match="Could not find '## Tasks' section"):
        create_task_from_template(bug_fix, {"title": "Test"}, tracker)


# Test task creation for JSON tracker


def test_create_task_from_template_json(tmp_path: Path):
    """Test creating a task from template with JSON tracker."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    prd_content = {
        "stories": [
            {
                "id": "task-1",
                "title": "Existing task",
                "status": "done",
                "priority": "high",
                "acceptance": ["Done"],
            }
        ]
    }
    prd_path = ralph_dir / "prd.json"
    prd_path.write_text(json.dumps(prd_content, indent=2), encoding="utf-8")

    from ralph_gold.trackers import FileTracker

    tracker = FileTracker(prd_path=prd_path)

    templates = load_builtin_templates()
    feature = templates["feature"]

    variables = {"title": "User authentication"}
    task_id = create_task_from_template(feature, variables, tracker)

    assert task_id == "task-2"

    # Read PRD and verify content
    updated_data = json.loads(prd_path.read_text(encoding="utf-8"))
    assert len(updated_data["stories"]) == 2

    new_task = updated_data["stories"][1]
    assert new_task["id"] == "task-2"
    assert new_task["title"] == "Feature: User authentication"
    assert new_task["status"] == "open"
    assert new_task["priority"] == "medium"
    assert "Requirements are documented" in new_task["acceptance"]


def test_create_task_from_template_json_empty_stories(tmp_path: Path):
    """Test creating task in JSON PRD with no existing stories."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    prd_content = {"stories": []}
    prd_path = ralph_dir / "prd.json"
    prd_path.write_text(json.dumps(prd_content), encoding="utf-8")

    from ralph_gold.trackers import FileTracker

    tracker = FileTracker(prd_path=prd_path)

    templates = load_builtin_templates()
    bug_fix = templates["bug-fix"]

    task_id = create_task_from_template(bug_fix, {"title": "First task"}, tracker)

    assert task_id == "task-1"

    updated_data = json.loads(prd_path.read_text(encoding="utf-8"))
    assert len(updated_data["stories"]) == 1
    assert updated_data["stories"][0]["id"] == "task-1"


def test_create_task_from_template_json_no_stories_key(tmp_path: Path):
    """Test creating task in JSON PRD without stories key."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    prd_content = {}
    prd_path = ralph_dir / "prd.json"
    prd_path.write_text(json.dumps(prd_content), encoding="utf-8")

    from ralph_gold.trackers import FileTracker

    tracker = FileTracker(prd_path=prd_path)

    templates = load_builtin_templates()
    bug_fix = templates["bug-fix"]

    task_id = create_task_from_template(bug_fix, {"title": "First task"}, tracker)

    assert task_id == "task-1"

    updated_data = json.loads(prd_path.read_text(encoding="utf-8"))
    assert "stories" in updated_data
    assert len(updated_data["stories"]) == 1


# Test template validation


def test_create_task_missing_required_variables():
    """Test that creating task with missing variables raises error."""
    templates = load_builtin_templates()
    bug_fix = templates["bug-fix"]

    # Mock tracker
    class MockTracker:
        kind = "json"

    tracker = MockTracker()

    # Missing 'title' variable
    with pytest.raises(TemplateError, match="Missing required variables"):
        create_task_from_template(bug_fix, {}, tracker)


def test_create_task_unsupported_tracker():
    """Test that creating task with unsupported tracker raises error."""
    templates = load_builtin_templates()
    bug_fix = templates["bug-fix"]

    # Mock tracker with unsupported type
    class MockTracker:
        kind = "github"

    tracker = MockTracker()

    with pytest.raises(
        TemplateError, match="Creating tasks from templates is not supported"
    ):
        create_task_from_template(bug_fix, {"title": "Test"}, tracker)


# Test list_templates


def test_list_templates_builtin_only(tmp_path: Path):
    """Test listing templates with only built-in templates."""
    templates = list_templates(tmp_path)

    assert len(templates) == 3
    names = [t.name for t in templates]
    assert "bug-fix" in names
    assert "feature" in names
    assert "refactor" in names


def test_list_templates_with_custom(tmp_path: Path):
    """Test listing templates with custom templates."""
    templates_dir = tmp_path / ".ralph" / "templates"
    templates_dir.mkdir(parents=True)

    custom_template = {
        "name": "custom",
        "description": "Custom template",
        "title_template": "Custom: {title}",
        "acceptance_criteria": ["Done"],
    }

    template_file = templates_dir / "custom.json"
    template_file.write_text(json.dumps(custom_template), encoding="utf-8")

    templates = list_templates(tmp_path)

    assert len(templates) == 4
    names = [t.name for t in templates]
    assert "custom" in names


def test_list_templates_custom_overrides_builtin(tmp_path: Path):
    """Test that custom template overrides built-in with same name."""
    templates_dir = tmp_path / ".ralph" / "templates"
    templates_dir.mkdir(parents=True)

    # Create custom template with same name as built-in
    custom_bug_fix = {
        "name": "bug-fix",
        "description": "Custom bug fix template",
        "title_template": "CUSTOM: {title}",
        "acceptance_criteria": ["Custom criterion"],
        "priority": "low",
    }

    template_file = templates_dir / "bug-fix.json"
    template_file.write_text(json.dumps(custom_bug_fix), encoding="utf-8")

    templates = list_templates(tmp_path)

    # Should still have 3 templates (custom overrides built-in)
    assert len(templates) == 3

    bug_fix = next(t for t in templates if t.name == "bug-fix")
    assert bug_fix.description == "Custom bug fix template"
    assert bug_fix.title_template == "CUSTOM: {title}"
    assert bug_fix.priority == "low"


def test_list_templates_sorted_by_name(tmp_path: Path):
    """Test that templates are sorted by name."""
    templates_dir = tmp_path / ".ralph" / "templates"
    templates_dir.mkdir(parents=True)

    # Create templates with names that would sort differently
    for name in ["zebra", "alpha", "beta"]:
        template = {
            "name": name,
            "description": f"{name} template",
            "title_template": f"{name}: {{title}}",
            "acceptance_criteria": ["Done"],
        }
        template_file = templates_dir / f"{name}.json"
        template_file.write_text(json.dumps(template), encoding="utf-8")

    templates = list_templates(tmp_path)
    names = [t.name for t in templates]

    # Should be sorted alphabetically
    assert names == sorted(names)


def test_list_templates_handles_load_error(tmp_path: Path):
    """Test that list_templates handles custom template load errors gracefully."""
    templates_dir = tmp_path / ".ralph" / "templates"
    templates_dir.mkdir(parents=True)

    # Create invalid template
    template_file = templates_dir / "invalid.json"
    template_file.write_text("{ invalid }", encoding="utf-8")

    # Should still return built-in templates
    templates = list_templates(tmp_path)
    assert len(templates) == 3


# Test edge cases


def test_create_task_with_special_characters_in_title(tmp_path: Path):
    """Test creating task with special characters in title."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    prd_content = {"stories": []}
    prd_path = ralph_dir / "prd.json"
    prd_path.write_text(json.dumps(prd_content), encoding="utf-8")

    from ralph_gold.trackers import FileTracker

    tracker = FileTracker(prd_path=prd_path)

    templates = load_builtin_templates()
    bug_fix = templates["bug-fix"]

    # Title with special characters
    variables = {"title": 'User\'s "login" & <logout> issues'}
    task_id = create_task_from_template(bug_fix, variables, tracker)

    updated_data = json.loads(prd_path.read_text(encoding="utf-8"))
    new_task = updated_data["stories"][0]
    assert 'Fix: User\'s "login" & <logout> issues' in new_task["title"]


def test_create_task_with_empty_acceptance_criteria(tmp_path: Path):
    """Test creating task with template that has empty acceptance criteria."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    prd_content = {"stories": []}
    prd_path = ralph_dir / "prd.json"
    prd_path.write_text(json.dumps(prd_content), encoding="utf-8")

    from ralph_gold.trackers import FileTracker

    tracker = FileTracker(prd_path=prd_path)

    # Create template with no acceptance criteria
    template = TaskTemplate(
        name="minimal",
        description="Minimal template",
        title_template="{title}",
        acceptance_criteria=[],
        priority="medium",
        variables=["title"],
    )

    task_id = create_task_from_template(template, {"title": "Test"}, tracker)

    updated_data = json.loads(prd_path.read_text(encoding="utf-8"))
    new_task = updated_data["stories"][0]
    assert new_task["acceptance"] == []


def test_markdown_task_id_increments_correctly(tmp_path: Path):
    """Test that Markdown task IDs increment correctly with gaps."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # PRD with non-sequential task IDs
    prd_content = """# Project PRD

## Tasks

- [x] 1. First task
- [x] 5. Fifth task
- [ ] 10. Tenth task

"""
    prd_path = ralph_dir / "PRD.md"
    prd_path.write_text(prd_content, encoding="utf-8")

    from ralph_gold.trackers import FileTracker

    tracker = FileTracker(prd_path=prd_path)

    templates = load_builtin_templates()
    bug_fix = templates["bug-fix"]

    task_id = create_task_from_template(bug_fix, {"title": "New task"}, tracker)

    # Should be 11 (max + 1)
    assert task_id == "11"


def test_json_task_id_extracts_number_correctly(tmp_path: Path):
    """Test that JSON task ID extraction handles various formats."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    prd_content = {
        "stories": [
            {"id": "task-5", "title": "Task 5"},
            {"id": "feature-10", "title": "Feature 10"},
            {"id": "bug-3", "title": "Bug 3"},
        ]
    }
    prd_path = ralph_dir / "prd.json"
    prd_path.write_text(json.dumps(prd_content), encoding="utf-8")

    from ralph_gold.trackers import FileTracker

    tracker = FileTracker(prd_path=prd_path)

    templates = load_builtin_templates()
    bug_fix = templates["bug-fix"]

    task_id = create_task_from_template(bug_fix, {"title": "New"}, tracker)

    # Should be task-11 (max number 10 + 1)
    assert task_id == "task-11"


# Property-based tests using hypothesis

from hypothesis import given, settings
from hypothesis import strategies as st

# Property 28: Template variable substitution
# **Validates: Requirements 10.1**


@given(
    st.dictionaries(
        keys=st.text(
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                min_codepoint=65,
                max_codepoint=122,
            ),
            min_size=1,
            max_size=20,
        ),
        values=st.text(min_size=0, max_size=100),
        min_size=1,
        max_size=5,
    )
)
@settings(max_examples=100)
def test_property_template_variable_substitution(variables: dict[str, str]):
    """
    **Validates: Requirements 10.1**

    Feature: ralph-enhancement-phase2, Property 28
    For any template with variables and provided values, all occurrences of
    {variable} in the template should be replaced with the corresponding value.
    """
    from ralph_gold.templates import _substitute_variables

    # Build a template string with all variables
    template_parts = []
    for var_name in variables.keys():
        template_parts.append(f"{{{var_name}}}")

    template_str = " ".join(template_parts)

    # Substitute variables
    result = _substitute_variables(template_str, variables)

    # Verify all variables were substituted
    for var_name, var_value in variables.items():
        # The placeholder should not appear in result
        placeholder = f"{{{var_name}}}"
        if placeholder in template_str:
            # If it was in the template, the value should be in the result
            assert var_value in result or placeholder not in result

        # The value should appear in the result
        assert var_value in result


@given(
    st.text(min_size=1, max_size=50),
    st.dictionaries(
        keys=st.text(
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                min_codepoint=65,
                max_codepoint=122,
            ),
            min_size=1,
            max_size=20,
        ),
        values=st.text(min_size=0, max_size=100),
        min_size=0,
        max_size=5,
    ),
)
@settings(max_examples=100)
def test_property_variable_substitution_idempotent(
    prefix: str, variables: dict[str, str]
):
    """
    **Validates: Requirements 10.1**

    Feature: ralph-enhancement-phase2, Property 28 (idempotency)
    Substituting variables twice should produce the same result as substituting once.
    """
    from ralph_gold.templates import _substitute_variables

    # Create template with prefix and variables
    template_parts = [prefix]
    for var_name in variables.keys():
        template_parts.append(f"{{{var_name}}}")

    template_str = " ".join(template_parts)

    # Substitute once
    result1 = _substitute_variables(template_str, variables)

    # Substitute again (should be idempotent if no placeholders remain)
    result2 = _substitute_variables(result1, variables)

    # Results should be the same (idempotent)
    assert result1 == result2


# Property 29: Template format validation
# **Validates: Requirements 10.2**


@given(
    st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"), min_codepoint=65, max_codepoint=122
        ),
        min_size=1,
        max_size=30,
    ),
    st.text(min_size=1, max_size=100),
    st.text(min_size=1, max_size=100),
    st.lists(st.text(min_size=1, max_size=100), min_size=1, max_size=5),
    st.sampled_from(["low", "medium", "high"]),
)
@settings(max_examples=100)
def test_property_template_format_validation_valid(
    name: str,
    description: str,
    title_template: str,
    acceptance_criteria: list[str],
    priority: str,
):
    """
    **Validates: Requirements 10.2**

    Feature: ralph-enhancement-phase2, Property 29
    For any valid template data, validation should accept it and create a
    TaskTemplate object.
    """
    # Create valid template data
    template_data = {
        "name": name,
        "description": description,
        "title_template": title_template,
        "acceptance_criteria": acceptance_criteria,
        "priority": priority,
        "variables": [],
        "metadata": {},
    }

    # Should be able to create TaskTemplate without error
    template = TaskTemplate(**template_data)

    # Verify fields are set correctly
    assert template.name == name
    assert template.description == description
    assert template.title_template == title_template
    assert template.acceptance_criteria == acceptance_criteria
    assert template.priority == priority


@given(
    st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"), min_codepoint=65, max_codepoint=122
        ),
        min_size=1,
        max_size=30,
    ),
    st.text(min_size=1, max_size=100),
    st.text(min_size=1, max_size=100),
    st.lists(st.text(min_size=1, max_size=100), min_size=1, max_size=5),
)
@settings(max_examples=100)
def test_property_template_json_roundtrip(
    name: str, description: str, title_template: str, acceptance_criteria: list[str]
):
    """
    **Validates: Requirements 10.2**

    Feature: ralph-enhancement-phase2, Property 29 (round-trip)
    For any valid template, serializing to JSON and deserializing should
    preserve all data.
    """
    # Create template
    original = TaskTemplate(
        name=name,
        description=description,
        title_template=title_template,
        acceptance_criteria=acceptance_criteria,
        priority="medium",
        variables=[],
        metadata={},
    )

    # Serialize to JSON
    template_dict = {
        "name": original.name,
        "description": original.description,
        "title_template": original.title_template,
        "acceptance_criteria": original.acceptance_criteria,
        "priority": original.priority,
        "variables": original.variables,
        "metadata": original.metadata,
    }

    json_str = json.dumps(template_dict)

    # Deserialize
    loaded_dict = json.loads(json_str)
    loaded = TaskTemplate(**loaded_dict)

    # Should be equal
    assert loaded.name == original.name
    assert loaded.description == original.description
    assert loaded.title_template == original.title_template
    assert loaded.acceptance_criteria == original.acceptance_criteria
    assert loaded.priority == original.priority


def test_property_template_validation_rejects_invalid(tmp_path: Path):
    """
    **Validates: Requirements 10.2**

    Feature: ralph-enhancement-phase2, Property 29
    For any malformed template file, validation should reject it with a clear
    error message.
    """
    templates_dir = tmp_path / ".ralph" / "templates"
    templates_dir.mkdir(parents=True)

    # Test various invalid templates
    invalid_templates = [
        # Missing required field
        {
            "name": "invalid1",
            "description": "Missing title_template",
            "acceptance_criteria": ["Done"],
        },
        # acceptance_criteria not a list
        {
            "name": "invalid2",
            "description": "Bad acceptance_criteria",
            "title_template": "{title}",
            "acceptance_criteria": "Not a list",
        },
    ]

    for i, invalid_template in enumerate(invalid_templates):
        # Create a fresh directory for each test
        test_dir = tmp_path / f"test{i}"
        test_dir.mkdir()
        test_templates_dir = test_dir / ".ralph" / "templates"
        test_templates_dir.mkdir(parents=True)

        template_file = test_templates_dir / f"invalid{i}.json"
        template_file.write_text(json.dumps(invalid_template), encoding="utf-8")

        # Should raise TemplateError
        with pytest.raises(TemplateError):
            load_custom_templates(test_dir)


# Property 30: Tracker format compatibility
# **Validates: Requirements 10.1**


def test_property_tracker_format_compatibility_json(tmp_path: Path):
    """
    **Validates: Requirements 10.1**

    Feature: ralph-enhancement-phase2, Property 30
    For any task created from a template, it should be correctly formatted
    for the JSON tracker type.
    """
    from ralph_gold.trackers import FileTracker

    @given(
        st.text(min_size=1, max_size=50),
        st.lists(st.text(min_size=1, max_size=100), min_size=0, max_size=5),
        st.sampled_from(["low", "medium", "high"]),
    )
    @settings(max_examples=50)
    def run_test(title: str, acceptance_criteria: list[str], priority: str):
        # Create JSON PRD in a unique subdirectory
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir)
            ralph_dir = test_path / ".ralph"
            ralph_dir.mkdir()

            prd_content = {"stories": []}
            prd_path = ralph_dir / "prd.json"
            prd_path.write_text(json.dumps(prd_content), encoding="utf-8")

            tracker = FileTracker(prd_path=prd_path)

            # Create template
            template = TaskTemplate(
                name="test",
                description="Test template",
                title_template=title,
                acceptance_criteria=acceptance_criteria,
                priority=priority,
                variables=[],
            )

            # Create task from template
            task_id = create_task_from_template(template, {}, tracker)

            # Verify task was created and is valid JSON
            updated_data = json.loads(prd_path.read_text(encoding="utf-8"))

            # Should have stories array
            assert "stories" in updated_data
            assert isinstance(updated_data["stories"], list)
            assert len(updated_data["stories"]) == 1

            # Verify task structure
            task = updated_data["stories"][0]
            assert task["id"] == task_id
            assert task["title"] == title
            assert task["status"] == "open"
            assert task["priority"] == priority
            assert task["acceptance"] == acceptance_criteria

    run_test()


def test_property_tracker_format_compatibility_markdown(tmp_path: Path):
    """
    **Validates: Requirements 10.1**

    Feature: ralph-enhancement-phase2, Property 30
    For any task created from a template, it should be correctly formatted
    for the Markdown tracker type.
    """
    from ralph_gold.trackers import FileTracker

    @given(
        st.text(
            alphabet=st.characters(
                blacklist_characters="\r\n\t", blacklist_categories=("Cc", "Cs")
            ),
            min_size=1,
            max_size=50,
        ),
        st.lists(
            st.text(
                alphabet=st.characters(
                    blacklist_characters="\r\n\t", blacklist_categories=("Cc", "Cs")
                ),
                min_size=1,
                max_size=100,
            ),
            min_size=0,
            max_size=5,
        ),
        st.sampled_from(["low", "medium", "high"]),
    )
    @settings(max_examples=50)
    def run_test(title: str, acceptance_criteria: list[str], priority: str):
        # Create Markdown PRD in a unique subdirectory
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir)
            ralph_dir = test_path / ".ralph"
            ralph_dir.mkdir()

            prd_content = """# Project PRD

## Tasks

"""
            prd_path = ralph_dir / "PRD.md"
            prd_path.write_text(prd_content, encoding="utf-8")

            tracker = FileTracker(prd_path=prd_path)

            # Create template
            template = TaskTemplate(
                name="test",
                description="Test template",
                title_template=title,
                acceptance_criteria=acceptance_criteria,
                priority=priority,
                variables=[],
            )

            # Create task from template
            task_id = create_task_from_template(template, {}, tracker)

            # Verify task was created in Markdown format
            updated_content = prd_path.read_text(encoding="utf-8")

            # Should contain task with checkbox
            assert f"- [ ] {task_id}. {title}" in updated_content

            # Should contain acceptance criteria if provided
            if acceptance_criteria:
                assert "**Acceptance Criteria:**" in updated_content
                for criterion in acceptance_criteria:
                    assert criterion in updated_content

    run_test()


def test_property_tracker_format_consistency(tmp_path: Path):
    """
    **Validates: Requirements 10.1**

    Feature: ralph-enhancement-phase2, Property 30 (consistency)
    For any sequence of tasks created from templates, each should maintain
    consistent formatting and incrementing IDs.
    """
    from ralph_gold.trackers import FileTracker

    @given(
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=30),
                st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=3),
            ),
            min_size=1,
            max_size=5,
        )
    )
    @settings(max_examples=30)
    def run_test(tasks_data: list[tuple[str, list[str]]]):
        # Create JSON PRD in a unique subdirectory
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir)
            ralph_dir = test_path / ".ralph"
            ralph_dir.mkdir()

            prd_content = {"stories": []}
            prd_path = ralph_dir / "prd.json"
            prd_path.write_text(json.dumps(prd_content), encoding="utf-8")

            tracker = FileTracker(prd_path=prd_path)

            # Create multiple tasks
            task_ids = []
            for title, acceptance_criteria in tasks_data:
                template = TaskTemplate(
                    name="test",
                    description="Test",
                    title_template=title,
                    acceptance_criteria=acceptance_criteria,
                    priority="medium",
                    variables=[],
                )

                task_id = create_task_from_template(template, {}, tracker)
                task_ids.append(task_id)

            # Verify all tasks were created
            updated_data = json.loads(prd_path.read_text(encoding="utf-8"))
            assert len(updated_data["stories"]) == len(tasks_data)

            # Verify IDs are unique and sequential
            assert len(set(task_ids)) == len(task_ids)  # All unique

            # Extract numeric parts and verify they increment
            import re

            nums = []
            for task_id in task_ids:
                match = re.search(r"(\d+)", task_id)
                if match:
                    nums.append(int(match.group(1)))

            # Should be sequential
            if nums:
                assert nums == sorted(nums)
                # Should increment by 1
                for i in range(1, len(nums)):
                    assert nums[i] == nums[i - 1] + 1

    run_test()
