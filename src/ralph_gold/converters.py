"""Converters for migrating PRD files to YAML format."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

import yaml

from .prd import _load_json_prd, _load_md_prd, is_markdown_prd


def _infer_group_from_title(title: str, index: int, total: int) -> str:
    """Infer a parallel group from task title patterns.

    This is a heuristic-based approach that looks for common patterns:
    - Tasks with similar prefixes (e.g., "API:", "UI:", "DB:")
    - Tasks mentioning specific components
    - Falls back to sequential grouping

    Args:
        title: Task title
        index: Task index (0-based)
        total: Total number of tasks

    Returns:
        Inferred group name
    """
    title_lower = title.lower()

    # Check for common prefixes
    prefix_patterns = [
        (r"^api[:\s]", "api"),
        (r"^ui[:\s]", "ui"),
        (r"^frontend[:\s]", "frontend"),
        (r"^backend[:\s]", "backend"),
        (r"^db[:\s]", "database"),
        (r"^database[:\s]", "database"),
        (r"^test[:\s]", "testing"),
        (r"^doc[:\s]", "docs"),
        (r"^documentation[:\s]", "docs"),
    ]

    for pattern, group in prefix_patterns:
        if re.match(pattern, title_lower):
            return group

    # Check for component mentions
    if "authentication" in title_lower or "auth" in title_lower:
        return "auth"
    if "database" in title_lower or "schema" in title_lower:
        return "database"
    if "ui" in title_lower or "interface" in title_lower or "frontend" in title_lower:
        return "ui"
    if "api" in title_lower or "endpoint" in title_lower:
        return "api"
    if "test" in title_lower:
        return "testing"

    # Default: all tasks in default group (sequential execution)
    return "default"


def convert_json_to_yaml(json_path: Path, infer_groups: bool = False) -> Dict[str, Any]:
    """Convert a JSON PRD file to YAML format.

    Args:
        json_path: Path to JSON PRD file
        infer_groups: Whether to infer parallel groups from task structure

    Returns:
        Dictionary representing YAML structure

    Raises:
        FileNotFoundError: If JSON file doesn't exist
        ValueError: If JSON is invalid
    """
    prd = _load_json_prd(json_path)

    # Extract metadata
    metadata: Dict[str, Any] = {}

    # Look for common metadata fields
    for key in [
        "project",
        "name",
        "description",
        "version",
        "author",
        "created",
        "branch",
        "branchName",
    ]:
        if key in prd and prd[key]:
            # Normalize branch field names
            if key in ["branch", "branchName"]:
                metadata["branch"] = prd[key]
            else:
                metadata[key] = prd[key]

    # Convert stories to tasks
    stories = prd.get("stories", [])
    if not isinstance(stories, list):
        stories = []

    tasks: List[Dict[str, Any]] = []
    for story in stories:
        if not isinstance(story, dict):
            continue

        task: Dict[str, Any] = {}

        # Required fields
        task["id"] = story.get("id", len(tasks) + 1)
        task["title"] = story.get("title", f"Task {task['id']}")

        # Optional fields
        if "description" in story and story["description"]:
            task["description"] = story["description"]

        if "priority" in story:
            task["priority"] = story["priority"]

        # Acceptance criteria
        acceptance = story.get("acceptance", [])
        if isinstance(acceptance, list) and acceptance:
            task["acceptance"] = [str(item) for item in acceptance if item]

        # Completion status
        completed = False
        if "passes" in story:
            completed = bool(story.get("passes"))
        elif "status" in story:
            status = str(story.get("status", "open")).lower()
            completed = status == "done"
        task["completed"] = completed

        # Infer group if requested
        if infer_groups:
            task["group"] = _infer_group_from_title(
                task["title"], len(tasks), len(stories)
            )

        tasks.append(task)

    # Build YAML structure
    yaml_data = {"version": 1, "metadata": metadata, "tasks": tasks}

    return yaml_data


def convert_markdown_to_yaml(
    md_path: Path, infer_groups: bool = False
) -> Dict[str, Any]:
    """Convert a Markdown PRD file to YAML format.

    Args:
        md_path: Path to Markdown PRD file
        infer_groups: Whether to infer parallel groups from task structure

    Returns:
        Dictionary representing YAML structure

    Raises:
        FileNotFoundError: If Markdown file doesn't exist
    """
    prd = _load_md_prd(md_path)

    # Extract metadata from markdown header
    metadata: Dict[str, Any] = {}

    # Look for metadata in the first few lines
    for line in prd.lines[:20]:
        # Look for key: value patterns
        m = re.match(r"^\s*([A-Za-z_]+)\s*:\s*(.+?)\s*$", line)
        if m:
            key = m.group(1).lower()
            value = m.group(2).strip()

            # Skip if it looks like a markdown heading
            if line.strip().startswith("#"):
                continue

            # Map common metadata fields
            if key in [
                "project",
                "name",
                "description",
                "author",
                "created",
                "branch",
                "branchname",
            ]:
                if key == "branchname":
                    metadata["branch"] = value
                else:
                    metadata[key] = value

    # Convert markdown tasks to YAML tasks
    tasks: List[Dict[str, Any]] = []
    for md_task in prd.tasks:
        task_id: Any = md_task.id
        if isinstance(task_id, str) and re.fullmatch(r"\d+", task_id.strip() or ""):
            task_id = int(task_id.strip())
        task: Dict[str, Any] = {
            "id": task_id,
            "title": md_task.title,
            "completed": md_task.status == "done",
        }
        if md_task.status == "blocked":
            task["blocked"] = True

        # Add acceptance criteria if present
        if md_task.acceptance:
            task["acceptance"] = md_task.acceptance

        # Infer group if requested
        if infer_groups:
            task["group"] = _infer_group_from_title(
                task["title"], len(tasks), len(prd.tasks)
            )

        tasks.append(task)

    # Build YAML structure
    yaml_data = {"version": 1, "metadata": metadata, "tasks": tasks}

    return yaml_data


def save_yaml(yaml_data: Dict[str, Any], output_path: Path) -> None:
    """Save YAML data to file with proper formatting.

    Args:
        yaml_data: Dictionary to save as YAML
        output_path: Path to output YAML file
    """
    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write YAML with nice formatting
    with open(output_path, "w") as f:
        yaml.safe_dump(
            yaml_data,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            indent=2,
        )


def convert_to_yaml(
    input_path: Path, output_path: Path, infer_groups: bool = False
) -> None:
    """Convert a PRD file (JSON or Markdown) to YAML format.

    Args:
        input_path: Path to input PRD file (JSON or Markdown)
        output_path: Path to output YAML file
        infer_groups: Whether to infer parallel groups from task structure

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If input format is not recognized or invalid
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Detect input format and convert
    if is_markdown_prd(input_path):
        yaml_data = convert_markdown_to_yaml(input_path, infer_groups=infer_groups)
    elif input_path.suffix.lower() == ".json":
        yaml_data = convert_json_to_yaml(input_path, infer_groups=infer_groups)
    else:
        raise ValueError(
            f"Unsupported input format: {input_path.suffix}. "
            "Supported formats: .json, .md, .markdown"
        )

    # Validate the generated YAML by attempting to load it
    # This ensures we're generating valid YAML that YamlTracker can read
    try:
        yaml_text = yaml.safe_dump(yaml_data, default_flow_style=False, sort_keys=False)
        yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise ValueError(f"Generated invalid YAML: {e}")

    # Save to output file
    save_yaml(yaml_data, output_path)
