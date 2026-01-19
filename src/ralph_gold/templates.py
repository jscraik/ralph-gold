"""Task template management for Ralph Gold.

This module provides functionality for creating tasks from reusable templates.
Supports both built-in templates (bug-fix, feature, refactor) and custom
user-defined templates stored in .ralph/templates/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .trackers import Tracker


class TemplateError(Exception):
    """Error during template operations."""

    pass


@dataclass
class TaskTemplate:
    """A reusable task template.

    Templates define a structure for common task types with placeholders
    for variable content like title, component names, etc.

    Attributes:
        name: Unique template identifier (e.g., "bug-fix")
        description: Human-readable description of the template
        title_template: Template string for task title with {variable} placeholders
        acceptance_criteria: List of acceptance criteria (may contain {variable} placeholders)
        priority: Default priority for tasks created from this template
        variables: List of variable names that can be substituted
        metadata: Optional additional metadata (author, version, etc.)
    """

    name: str
    description: str
    title_template: str
    acceptance_criteria: list[str]
    priority: str = "medium"
    variables: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def load_builtin_templates() -> dict[str, TaskTemplate]:
    """Load built-in task templates.

    Returns:
        Dictionary mapping template names to TaskTemplate objects

    Examples:
        >>> templates = load_builtin_templates()
        >>> bug_fix = templates['bug-fix']
        >>> bug_fix.priority
        'high'
    """
    return {
        "bug-fix": TaskTemplate(
            name="bug-fix",
            description="Template for bug fixes",
            title_template="Fix: {title}",
            acceptance_criteria=[
                "Bug is reproducible with test case",
                "Root cause is identified",
                "Fix is implemented and tested",
                "Regression test added",
            ],
            priority="high",
            variables=["title"],
            metadata={"version": "1.0", "builtin": True},
        ),
        "feature": TaskTemplate(
            name="feature",
            description="Template for new features",
            title_template="Feature: {title}",
            acceptance_criteria=[
                "Requirements are documented",
                "Implementation is complete",
                "Tests are passing",
                "Documentation is updated",
            ],
            priority="medium",
            variables=["title"],
            metadata={"version": "1.0", "builtin": True},
        ),
        "refactor": TaskTemplate(
            name="refactor",
            description="Template for refactoring tasks",
            title_template="Refactor: {title}",
            acceptance_criteria=[
                "Code is cleaner and more maintainable",
                "All existing tests still pass",
                "No functional changes",
                "Performance is maintained or improved",
            ],
            priority="low",
            variables=["title"],
            metadata={"version": "1.0", "builtin": True},
        ),
    }


def load_custom_templates(project_root: Path) -> dict[str, TaskTemplate]:
    """Load custom templates from .ralph/templates/ directory.

    Custom templates are JSON files following the TaskTemplate schema.
    They can override built-in templates by using the same name.

    Args:
        project_root: Root directory of the Ralph project

    Returns:
        Dictionary mapping template names to TaskTemplate objects

    Raises:
        TemplateError: If a template file is malformed

    Examples:
        >>> templates = load_custom_templates(Path('/project'))
        >>> custom = templates.get('my-template')
    """
    templates: dict[str, TaskTemplate] = {}
    templates_dir = project_root / ".ralph" / "templates"

    if not templates_dir.exists():
        return templates

    for template_file in templates_dir.glob("*.json"):
        try:
            data = json.loads(template_file.read_text(encoding="utf-8"))

            # Validate required fields
            required_fields = [
                "name",
                "description",
                "title_template",
                "acceptance_criteria",
            ]
            missing = [f for f in required_fields if f not in data]
            if missing:
                raise TemplateError(
                    f"Template {template_file.name} missing required fields: {', '.join(missing)}"
                )

            # Validate acceptance_criteria is a list
            if not isinstance(data["acceptance_criteria"], list):
                raise TemplateError(
                    f"Template {template_file.name}: acceptance_criteria must be a list"
                )

            # Create template with defaults for optional fields
            template = TaskTemplate(
                name=data["name"],
                description=data["description"],
                title_template=data["title_template"],
                acceptance_criteria=data["acceptance_criteria"],
                priority=data.get("priority", "medium"),
                variables=data.get("variables", []),
                metadata=data.get("metadata", {}),
            )

            templates[template.name] = template

        except json.JSONDecodeError as e:
            raise TemplateError(f"Invalid JSON in template {template_file.name}: {e}")
        except Exception as e:
            raise TemplateError(f"Error loading template {template_file.name}: {e}")

    return templates


def _substitute_variables(text: str, variables: dict[str, str]) -> str:
    """Substitute {variable} placeholders in text.

    Args:
        text: Text containing {variable} placeholders
        variables: Dictionary mapping variable names to values

    Returns:
        Text with all variables substituted

    Examples:
        >>> _substitute_variables("Fix: {title}", {"title": "Login bug"})
        'Fix: Login bug'
    """
    result = text
    for var_name, var_value in variables.items():
        placeholder = f"{{{var_name}}}"
        result = result.replace(placeholder, var_value)
    return result


def create_task_from_template(
    template: TaskTemplate,
    variables: dict[str, str],
    tracker: Tracker,
) -> str:
    """Create a new task from a template.

    Substitutes variables in the template and adds the task to the tracker.

    Args:
        template: The template to use
        variables: Dictionary mapping variable names to values
        tracker: The task tracker to add the task to

    Returns:
        The ID of the newly created task

    Raises:
        TemplateError: If required variables are missing or tracker operation fails

    Examples:
        >>> template = load_builtin_templates()['bug-fix']
        >>> variables = {'title': 'Login fails on Safari'}
        >>> task_id = create_task_from_template(template, variables, tracker)
    """
    # Validate that all required variables are provided
    missing_vars = [v for v in template.variables if v not in variables]
    if missing_vars:
        raise TemplateError(
            f"Missing required variables for template '{template.name}': {', '.join(missing_vars)}"
        )

    # Substitute variables in title
    title = _substitute_variables(template.title_template, variables)

    # Substitute variables in acceptance criteria
    acceptance_criteria = [
        _substitute_variables(criterion, variables)
        for criterion in template.acceptance_criteria
    ]

    # Create task based on tracker type
    # Import here to avoid circular dependency
    from .trackers import FileTracker

    tracker_kind = getattr(tracker, "kind", None)

    if tracker_kind in {"md", "markdown"}:
        # For Markdown trackers, we need to append to the PRD file
        if not isinstance(tracker, FileTracker):
            raise TemplateError("Expected FileTracker for Markdown PRD")
        task_id = _add_task_to_markdown(
            tracker, title, acceptance_criteria, template.priority
        )
    elif tracker_kind == "json":
        # For JSON trackers, we need to add to the stories array
        if not isinstance(tracker, FileTracker):
            raise TemplateError("Expected FileTracker for JSON PRD")
        task_id = _add_task_to_json(
            tracker, title, acceptance_criteria, template.priority
        )
    elif tracker_kind in {"yaml", "yml"}:
        # For YAML trackers, similar to JSON
        task_id = _add_task_to_yaml(
            tracker, title, acceptance_criteria, template.priority
        )
    else:
        # For other trackers (Beads, GitHub Issues), we can't directly add tasks
        raise TemplateError(
            f"Creating tasks from templates is not supported for tracker type: {tracker_kind}"
        )

    return task_id


def _add_task_to_markdown(
    tracker: Tracker,
    title: str,
    acceptance_criteria: list[str],
    priority: str,
) -> str:
    """Add a task to a Markdown PRD file.

    Args:
        tracker: The Markdown tracker
        title: Task title
        acceptance_criteria: List of acceptance criteria
        priority: Task priority

    Returns:
        The generated task ID

    Raises:
        TemplateError: If the PRD file cannot be modified
    """
    from .trackers import FileTracker

    # Type guard - we already checked this in create_task_from_template
    assert isinstance(tracker, FileTracker)

    prd_path = tracker.prd_path

    try:
        lines = prd_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except Exception as e:
        raise TemplateError(f"Failed to read PRD file: {e}")

    # Find the ## Tasks section
    tasks_section_idx = None
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("## tasks"):
            tasks_section_idx = i
            break

    if tasks_section_idx is None:
        raise TemplateError("Could not find '## Tasks' section in Markdown PRD")

    # Find the next task ID by looking at existing tasks
    task_num = 1
    for line in lines[tasks_section_idx:]:
        # Look for task IDs like "- [ ] 1.", "- [x] 2.", etc.
        import re

        match = re.match(r"^\s*-\s+\[[^\]]\]\s+(\d+)\.", line)
        if match:
            num = int(match.group(1))
            task_num = max(task_num, num + 1)

    task_id = str(task_num)

    # Build the task entry
    task_lines = [f"\n- [ ] {task_id}. {title}\n"]
    if acceptance_criteria:
        task_lines.append("  **Acceptance Criteria:**\n")
        for criterion in acceptance_criteria:
            task_lines.append(f"  - {criterion}\n")

    # Insert after the Tasks heading (skip any blank lines)
    insert_idx = tasks_section_idx + 1
    while insert_idx < len(lines) and lines[insert_idx].strip() == "":
        insert_idx += 1

    # Insert the new task
    lines[insert_idx:insert_idx] = task_lines

    # Write back to file
    try:
        prd_path.write_text("".join(lines), encoding="utf-8")
    except Exception as e:
        raise TemplateError(f"Failed to write PRD file: {e}")

    return task_id


def _add_task_to_json(
    tracker: Tracker,
    title: str,
    acceptance_criteria: list[str],
    priority: str,
) -> str:
    """Add a task to a JSON PRD file.

    Args:
        tracker: The JSON tracker
        title: Task title
        acceptance_criteria: List of acceptance criteria
        priority: Task priority

    Returns:
        The generated task ID

    Raises:
        TemplateError: If the PRD file cannot be modified
    """
    from .trackers import FileTracker

    # Type guard - we already checked this in create_task_from_template
    assert isinstance(tracker, FileTracker)

    prd_path = tracker.prd_path

    try:
        prd_data = json.loads(prd_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise TemplateError(f"Failed to read JSON PRD file: {e}")

    # Ensure stories array exists
    if "stories" not in prd_data:
        prd_data["stories"] = []

    stories = prd_data["stories"]

    # Find the next task ID
    task_num = 1
    for story in stories:
        if isinstance(story, dict) and "id" in story:
            story_id = str(story["id"])
            # Try to extract numeric part
            import re

            match = re.search(r"(\d+)", story_id)
            if match:
                num = int(match.group(1))
                task_num = max(task_num, num + 1)

    task_id = f"task-{task_num}"

    # Create the new story
    new_story = {
        "id": task_id,
        "title": title,
        "status": "open",
        "priority": priority,
        "acceptance": acceptance_criteria,
    }

    # Add to stories array
    stories.append(new_story)

    # Write back to file
    try:
        prd_path.write_text(json.dumps(prd_data, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        raise TemplateError(f"Failed to write JSON PRD file: {e}")

    return task_id


def _add_task_to_yaml(
    tracker: Tracker,
    title: str,
    acceptance_criteria: list[str],
    priority: str,
) -> str:
    """Add a task to a YAML PRD file.

    Args:
        tracker: The YAML tracker
        title: Task title
        acceptance_criteria: List of acceptance criteria
        priority: Task priority

    Returns:
        The generated task ID

    Raises:
        TemplateError: If the PRD file cannot be modified
    """
    # Import yaml here to avoid requiring it as a dependency if not used
    try:
        import yaml
    except ImportError:
        raise TemplateError("PyYAML is required for YAML tracker support")

    try:
        from .trackers.yaml_tracker import YamlTracker
    except ImportError:
        raise TemplateError("YAML tracker not available")

    # Type guard
    if not isinstance(tracker, YamlTracker):
        raise TemplateError("Expected YamlTracker for YAML PRD")

    prd_path = tracker.prd_path

    try:
        prd_data = yaml.safe_load(prd_path.read_text(encoding="utf-8"))
        if prd_data is None:
            prd_data = {}
    except Exception as e:
        raise TemplateError(f"Failed to read YAML PRD file: {e}")

    # Ensure tasks array exists
    if "tasks" not in prd_data:
        prd_data["tasks"] = []

    tasks = prd_data["tasks"]

    # Find the next task ID
    task_num = 1
    for task in tasks:
        if isinstance(task, dict) and "id" in task:
            task_id_str = str(task["id"])
            # Try to extract numeric part
            import re

            match = re.search(r"(\d+)", task_id_str)
            if match:
                num = int(match.group(1))
                task_num = max(task_num, num + 1)

    task_id = f"task-{task_num}"

    # Create the new task
    new_task = {
        "id": task_id,
        "title": title,
        "status": "open",
        "priority": priority,
        "acceptance": acceptance_criteria,
    }

    # Add to tasks array
    tasks.append(new_task)

    # Write back to file
    try:
        prd_path.write_text(
            yaml.dump(prd_data, default_flow_style=False), encoding="utf-8"
        )
    except Exception as e:
        raise TemplateError(f"Failed to write YAML PRD file: {e}")

    return task_id


def list_templates(project_root: Path) -> list[TaskTemplate]:
    """List all available templates (built-in and custom).

    Custom templates override built-in templates with the same name.

    Args:
        project_root: Root directory of the Ralph project

    Returns:
        List of all available TaskTemplate objects

    Examples:
        >>> templates = list_templates(Path('/project'))
        >>> for t in templates:
        ...     print(f"{t.name}: {t.description}")
    """
    # Start with built-in templates
    all_templates = load_builtin_templates()

    # Load and merge custom templates (overriding built-ins if same name)
    try:
        custom_templates = load_custom_templates(project_root)
        all_templates.update(custom_templates)
    except TemplateError:
        # If custom templates fail to load, just use built-ins
        pass

    # Return as sorted list
    return sorted(all_templates.values(), key=lambda t: t.name)
