"""State validation against PRD to detect desynchronization.

Provides read-only validation and safe cleanup of stale task IDs
that no longer exist in the current PRD.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Set

from .prd import get_all_tasks

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of state validation against PRD.

    Attributes:
        stale_ids: List of task IDs that exist in state but not in PRD
        protected_ids: List of task IDs that are protected from cleanup
            (current task or recently completed tasks)
        can_auto_cleanup: bool - True if cleanup is safe, False if current task is stale
        state_mtime: Modification time of state.json
        prd_mtime: Modification time of PRD file
    """

    stale_ids: List[str] = field(default_factory=list)
    protected_ids: List[str] = field(default_factory=list)
    can_auto_cleanup: bool = True
    state_mtime: float = 0.0
    prd_mtime: float = 0.0

    def log_summary(self) -> str:
        """Generate a summary string for logging."""
        lines = []
        if self.stale_ids:
            lines.append(f"Found {len(self.stale_ids)} stale task IDs: {self.stale_ids}")
        else:
            lines.append("No stale task IDs found")

        if self.protected_ids:
            lines.append(f"Protected (current/recent): {self.protected_ids}")

        if self.can_auto_cleanup:
            lines.append("Auto-cleanup: safe")
        else:
            lines.append("Auto-cleanup: unsafe (current task is stale)")

        return "\n".join(lines)


def validate_state_against_prd(
    project_root: Path,
    prd_path: Path,
    state_path: Path,
    protect_recent_hours: int = 1,
) -> ValidationResult:
    """Validate state.json against current PRD to find stale task IDs.

    Args:
        project_root: Path to the project root directory
        prd_path: Path to the PRD file
        state_path: Path to the state.json file
        protect_recent_hours: Protect tasks completed in the last N hours

    Returns:
        ValidationResult with stale IDs, protected IDs, and cleanup safety status
    """
    result = ValidationResult()

    # Get file modification times
    if state_path.exists():
        result.state_mtime = state_path.stat().st_mtime
    if prd_path.exists():
        result.prd_mtime = prd_path.stat().st_mtime

    # Load state.json
    if not state_path.exists():
        return result  # No state, no stale IDs

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in {state_path}: {e}")
        return result
    except Exception as e:
        logger.warning(f"Error loading {state_path}: {e}")
        return result

    # Get current PRD tasks
    try:
        prd_tasks = get_all_tasks(prd_path) or []
        if not isinstance(prd_tasks, list):
            prd_tasks = []
        prd_task_ids = {str(task.get("id", "")) for task in prd_tasks if isinstance(task, dict)}
    except Exception as e:
        logger.warning(f"Error loading PRD tasks: {e}")
        # Treat failures (including missing PRD) as "no tasks in PRD" so that
        # state IDs are considered stale (caller can decide what to do next).
        prd_task_ids = set()

    # Get task IDs from state history
    history = state.get("history", [])
    state_task_ids: Set[str] = set()

    # Collect task IDs from history entries
    for entry in history:
        if not isinstance(entry, dict):
            continue
        task_id = entry.get("task_id")
        if task_id:
            state_task_ids.add(str(task_id))

    # Also check task_attempts and blocked_tasks
    for task_id in state.get("task_attempts", {}).keys():
        state_task_ids.add(str(task_id))
    for task_id in state.get("blocked_tasks", {}).keys():
        state_task_ids.add(str(task_id))

    # Find stale IDs (in state but not in PRD)
    stale_ids = state_task_ids - prd_task_ids
    result.stale_ids = sorted(list(stale_ids))

    if not stale_ids:
        return result

    # Protect current task (most recent in history that has a task_id)
    current_task_id = None
    for entry in reversed(history):
        if isinstance(entry, dict) and entry.get("task_id"):
            current_task_id = str(entry.get("task_id"))
            break

    # Protect recently completed tasks
    protected_ids = set()
    if current_task_id:
        protected_ids.add(current_task_id)

    if protect_recent_hours > 0:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=protect_recent_hours)
        for entry in history:
            if not isinstance(entry, dict):
                continue
            task_id = entry.get("task_id")
            timestamp = entry.get("timestamp")
            if task_id and timestamp:
                try:
                    entry_time = datetime.fromisoformat(timestamp)
                    if entry_time >= cutoff_time:
                        protected_ids.add(str(task_id))
                except (ValueError, TypeError):
                    continue

    result.protected_ids = sorted(list(protected_ids))

    # Check if current task is stale (unsafe for auto-cleanup)
    if current_task_id and current_task_id in stale_ids:
        result.can_auto_cleanup = False

    # Also unsafe if PRD was recently modified (possible concurrent edit)
    if result.prd_mtime > result.state_mtime + 60:  # PRD modified > 60s after state
        result.can_auto_cleanup = False

    return result


def cleanup_stale_task_ids(
    project_root: Path,
    prd_path: Path,
    state_path: Path,
    dry_run: bool = True,
) -> List[str]:
    """Remove stale task IDs from state.json with safety checks.

    Args:
        project_root: Path to the project root directory
        prd_path: Path to the PRD file
        state_path: Path to the state.json file
        dry_run: If True, show what would be removed without actually removing

    Returns:
        List of task IDs that were removed (or would be removed in dry-run mode)
    """
    validation = validate_state_against_prd(project_root, prd_path, state_path)

    if not validation.stale_ids:
        logger.info("No stale task IDs to clean up")
        return []

    # Filter out protected IDs
    ids_to_remove = [tid for tid in validation.stale_ids if tid not in validation.protected_ids]

    if dry_run:
        logger.info(f"[DRY RUN] Would remove {len(ids_to_remove)} stale task IDs: {ids_to_remove}")
        return ids_to_remove

    if not validation.can_auto_cleanup:
        logger.error("Cannot auto-cleanup: current task is stale or PRD was recently modified")
        logger.error("Run 'ralph state cleanup' manually to review and remove stale IDs")
        return []

    # Load and clean state.json
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to load state.json: {e}")
        return []

    # Remove stale task IDs from history
    cleaned_history = []
    for entry in state.get("history", []):
        if not isinstance(entry, dict):
            cleaned_history.append(entry)
            continue
        task_id = entry.get("task_id")
        if task_id and str(task_id) in ids_to_remove:
            # Remove task_id from this entry
            entry = {k: v for k, v in entry.items() if k != "task_id"}
        cleaned_history.append(entry)

    state["history"] = cleaned_history

    # Remove stale task IDs from task_attempts
    task_attempts = state.get("task_attempts", {})
    for task_id in ids_to_remove:
        task_attempts.pop(task_id, None)

    # Remove stale task IDs from blocked_tasks
    blocked_tasks = state.get("blocked_tasks", {})
    for task_id in ids_to_remove:
        blocked_tasks.pop(task_id, None)

    # Write cleaned state
    from .atomic_file import atomic_write_json

    atomic_write_json(state_path, state)
    logger.info(f"Removed {len(ids_to_remove)} stale task IDs: {ids_to_remove}")

    return ids_to_remove
