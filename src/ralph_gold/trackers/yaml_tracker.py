"""YAML-based task tracker with native parallel grouping support."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

from ..prd import SelectedTask, TaskId


@dataclass
class YamlTracker:
    """YAML-based task tracker with native parallel grouping.

    Supports the YAML task format with version, metadata, and tasks.
    Tasks can declare a "group" field for parallel scheduling.
    """

    prd_path: Path
    data: Dict[str, Any]

    def __init__(self, prd_path: Path):
        """Initialize YamlTracker and load/validate YAML file.

        Args:
            prd_path: Path to the tasks.yaml file

        Raises:
            ValueError: If YAML is invalid or doesn't match schema
            FileNotFoundError: If YAML file doesn't exist
        """
        self.prd_path = prd_path
        self.data = self._load_and_validate()

    @property
    def kind(self) -> str:
        """Return tracker kind identifier."""
        return "yaml"

    def _load_and_validate(self) -> Dict[str, Any]:
        """Load YAML and validate against schema.

        Returns:
            Parsed YAML data as dictionary

        Raises:
            ValueError: If YAML is invalid or doesn't match schema
            FileNotFoundError: If file doesn't exist
        """
        if not self.prd_path.exists():
            raise FileNotFoundError(f"YAML file not found: {self.prd_path}")

        try:
            with open(self.prd_path, "r") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML syntax: {e}")

        if not isinstance(data, dict):
            raise ValueError("YAML root must be a dictionary")

        # Validate version
        version = data.get("version")
        if version != 1:
            raise ValueError(f"Unsupported YAML version: {version} (expected 1)")

        # Validate tasks structure
        if "tasks" not in data:
            raise ValueError("YAML must have 'tasks' field")

        if not isinstance(data["tasks"], list):
            raise ValueError("YAML 'tasks' field must be a list")

        # Validate each task has required fields
        for i, task in enumerate(data["tasks"]):
            if not isinstance(task, dict):
                raise ValueError(f"Task at index {i} must be a dictionary")

            if "id" not in task:
                raise ValueError(f"Task at index {i} missing required 'id' field")

            if "title" not in task:
                raise ValueError(f"Task at index {i} missing required 'title' field")

        return data

    def _task_from_data(self, task_data: Dict[str, Any]) -> SelectedTask:
        """Convert YAML task data to SelectedTask.

        Args:
            task_data: Task dictionary from YAML

        Returns:
            SelectedTask instance
        """
        task_id = str(task_data["id"])
        title = str(task_data["title"])

        # Extract acceptance criteria
        acceptance = task_data.get("acceptance", [])
        if not isinstance(acceptance, list):
            acceptance = []
        acceptance = [str(item) for item in acceptance]

        # Extract dependencies (backward compatible - defaults to empty list)
        depends_on = task_data.get("depends_on", [])
        if not isinstance(depends_on, list):
            depends_on = []
        depends_on = [str(dep) for dep in depends_on]

        group = str(task_data.get("group", "default"))
        return SelectedTask(
            id=task_id,
            title=title,
            kind="yaml",
            acceptance=acceptance,
            depends_on=depends_on,
            group=group,
        )

    def select_next_task(
        self, exclude_ids: Optional[Set[str]] = None
    ) -> Optional[SelectedTask]:
        """Return the next available task without claiming it.

        Respects task dependencies - only returns tasks whose dependencies
        are all completed.

        Returns:
            Next uncompleted task with satisfied dependencies, or None if no tasks are ready
        """
        exclude = exclude_ids or set()

        # First pass: collect completed task IDs
        completed_ids: Set[str] = set()
        for task_data in self.data["tasks"]:
            if task_data.get("completed", False) or task_data.get("blocked", False):
                completed_ids.add(str(task_data.get("id")))

        # Second pass: find first task with satisfied dependencies
        for task_data in self.data["tasks"]:
            task_id = str(task_data.get("id"))
            if task_id in exclude:
                continue
            if task_data.get("completed", False) or task_data.get("blocked", False):
                continue

            # Check dependencies (backward compatible - no depends_on means no dependencies)
            depends_on = task_data.get("depends_on", [])
            if not isinstance(depends_on, list):
                depends_on = []

            # Check if all dependencies are satisfied
            if depends_on:
                all_deps_satisfied = all(
                    str(dep) in completed_ids for dep in depends_on
                )
                if not all_deps_satisfied:
                    continue

            return self._task_from_data(task_data)
        return None

    def peek_next_task(self) -> Optional[SelectedTask]:
        return self.select_next_task()

    def claim_next_task(self) -> Optional[SelectedTask]:
        """Claim the next available task.

        For YAML tracker, this is the same as peek_next_task since
        we don't modify the file on claim (only on completion).

        Returns:
            Next uncompleted task, or None if all tasks are done
        """
        return self.select_next_task()

    def counts(self) -> Tuple[int, int]:
        """Return (completed_count, total_count) for tasks.

        Returns:
            Tuple of (completed, total) task counts
        """
        tasks = self.data.get("tasks", [])
        total = len(tasks)
        completed = sum(1 for task in tasks if task.get("completed", False))
        return (completed, total)

    def all_done(self) -> bool:
        """Check if all tasks are completed.

        Returns:
            True if all tasks are marked as completed
        """
        tasks = self.data.get("tasks", [])
        if not tasks:
            return True
        return all(task.get("completed", False) for task in tasks)

    def all_blocked(self) -> bool:
        """Check if all remaining tasks are marked as blocked.

        Returns:
            True if all remaining tasks have status "blocked", False otherwise.
            Returns False if there are no remaining tasks (all done).
        """
        tasks = self.data.get("tasks", [])
        if not tasks:
            return False
        remaining = [t for t in tasks if not t.get("completed", False)]
        if not remaining:
            return False  # All done, not blocked
        return all(t.get("blocked", False) for t in remaining)

    def is_task_done(self, task_id: TaskId) -> bool:
        """Check if a specific task is marked done.

        Args:
            task_id: Task identifier to check

        Returns:
            True if task is marked as completed
        """
        for task in self.data.get("tasks", []):
            if str(task.get("id")) == str(task_id):
                return task.get("completed", False)
        return False

    def force_task_open(self, task_id: TaskId) -> bool:
        """Force a task to be marked as open (not completed).

        This modifies the YAML file to set completed=false for the task.

        Args:
            task_id: Task identifier to reopen

        Returns:
            True if task was found and reopened, False otherwise
        """
        found = False
        for task in self.data.get("tasks", []):
            if str(task.get("id")) == str(task_id):
                task["completed"] = False
                found = True
                break

        if found:
            # Write updated data back to file
            with open(self.prd_path, "w") as f:
                yaml.safe_dump(self.data, f, default_flow_style=False, sort_keys=False)

        return found

    def block_task(self, task_id: TaskId, reason: str) -> bool:
        found = False
        for task in self.data.get("tasks", []):
            if str(task.get("id")) == str(task_id):
                task["blocked"] = True
                if reason:
                    task["blocked_reason"] = reason
                found = True
                break
        if found:
            with open(self.prd_path, "w") as f:
                yaml.safe_dump(self.data, f, default_flow_style=False, sort_keys=False)
        return found

    def branch_name(self) -> Optional[str]:
        """Return the branch name from metadata, if specified.

        Returns:
            Branch name from metadata, or None if not specified
        """
        metadata = self.data.get("metadata", {})
        if isinstance(metadata, dict):
            branch = metadata.get("branch")
            if branch:
                return str(branch)
        return None

    def get_parallel_groups(self) -> Dict[str, List[SelectedTask]]:
        """Return tasks grouped by parallel group.

        Tasks are grouped by their "group" field. Tasks without a group
        field default to the "default" group.

        Only uncompleted tasks are included in the groups.

        Returns:
            Dictionary mapping group names to lists of SelectedTask instances
        """
        groups: Dict[str, List[SelectedTask]] = {}

        for task_data in self.data.get("tasks", []):
            # Skip completed tasks
            if task_data.get("completed", False):
                continue

            # Get group name (default to "default")
            group = str(task_data.get("group", "default"))

            # Convert to SelectedTask
            task = self._task_from_data(task_data)

            # Add to group
            if group not in groups:
                groups[group] = []
            groups[group].append(task)

        return groups
