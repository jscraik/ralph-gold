"""Blocked task management and unblock operations for RALPH.

This module provides:
- BlockedTaskInfo: Data structure for blocked task metadata
- BlockedTaskManager: Manage, list, and unblock tasks
- suggest_unblock_strategy(): Recommend approach based on block reason
- unblock_task(): Unblock a task for retry with optional new timeout

Phase 5: Adaptive Timeout & Unblock mechanism.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .adaptive_timeout import (
    AdaptiveTimeoutConfig,
    calculate_adaptive_timeout,
    estimate_task_complexity,
)
from .config import load_config
from .trackers import Tracker, make_tracker

logger = logging.getLogger(__name__)


class BlockReason(Enum):
    """Common reasons for task blocking."""
    TIMEOUT = "timeout"
    NO_FILES = "no_files"
    GATE_FAILURE = "gate_failure"
    ATTEMPT_LIMIT = "attempt_limit"
    DEPENDENCY = "dependency"
    MANUAL = "manual"


@dataclass
class BlockedTaskInfo:
    """Information about a blocked task.

    Attributes:
        task_id: The blocked task ID
        title: Task title
        blocked_at: ISO timestamp when task was blocked
        attempts: Number of attempts before blocking
        reason: Primary reason for blocking
        block_reason_detail: Detailed block reason
        suggested_timeout: Suggested timeout for retry (seconds)
        complexity_level: Detected complexity level
        metadata: Additional metadata about the block
    """
    task_id: str
    title: str
    blocked_at: str
    attempts: int
    reason: str
    block_reason_detail: str
    suggested_timeout: int
    complexity_level: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "title": self.title,
            "blocked_at": self.blocked_at,
            "attempts": self.attempts,
            "reason": self.reason,
            "block_reason_detail": self.block_reason_detail,
            "suggested_timeout": self.suggested_timeout,
            "complexity_level": self.complexity_level,
            "metadata": self.metadata,
        }


@dataclass
class UnblockResult:
    """Result of an unblock operation.

    Attributes:
        success: Whether the unblock succeeded
        task_id: The task that was unblocked
        previous_attempts: Number of attempts before unblock
        new_timeout: Timeout to use for retry (0 if unchanged)
        message: Human-readable result message
    """
    success: bool
    task_id: str
    previous_attempts: int
    new_timeout: int
    message: str


class BlockedTaskManager:
    """Manage blocked tasks and unblock operations.

    Usage:
        manager = BlockedTaskManager(project_root)
        blocked = manager.list_blocked_tasks()
        for task_info in blocked:
            print(f"{task_info.task_id}: {task_info.reason}")

        # Unblock with suggested timeout
        result = manager.unblock_task(
            task_id="task-22",
            reason="Increasing timeout for UI task",
            new_timeout=1800,
        )
    """

    def __init__(self, project_root: Path, tracker: Optional[Tracker] = None):
        """Initialize the blocked task manager.

        Args:
            project_root: Path to the project root directory
            tracker: Optional TaskTracker instance (will load from .ralph if not provided)
        """
        self.project_root = project_root
        self.ralph_dir = project_root / ".ralph"
        self.state_file = self.ralph_dir / "state.json"
        self.tracker = tracker

    def list_blocked_tasks(self) -> List[BlockedTaskInfo]:
        """List all blocked tasks with metadata.

        Reads from:
        1. state.json blocked_tasks section
        2. Task attempt counts
        3. Task metadata from PRD

        Returns:
            List of blocked task info objects
        """
        blocked: List[BlockedTaskInfo] = []

        if not self.state_file.exists():
            return blocked

        try:
            state_data = json.loads(self.state_file.read_text())
        except (json.JSONDecodeError, OSError):
            return blocked

        # Get blocked_tasks from state
        blocked_tasks_raw = state_data.get("blocked_tasks", {})

        # Get attempt counts
        task_attempts = state_data.get("task_attempts", {})

        # Load tracker if not provided
        if self.tracker is None:
            cfg = load_config(self.project_root)
            self.tracker = make_tracker(self.project_root, cfg)

        # Build blocked task list by looking up each blocked task individually
        # (Tracker protocol doesn't have all_tasks(), so we get each by ID)
        for task_id, block_info in blocked_tasks_raw.items():
            try:
                task = self.tracker.get_task_by_id(task_id)
            except (json.JSONDecodeError, OSError) as e:
                logger.debug("Failed to load task %s: %s", task_id, e)
                continue
            
            if not task:
                continue

            # Get attempt count
            attempts_data = task_attempts.get(task_id, {})
            if isinstance(attempts_data, dict) and "count" in attempts_data:
                attempts = attempts_data["count"]
            elif isinstance(attempts_data, int):
                attempts = attempts_data
            else:
                attempts = 0

            # Determine reason from block_info
            reason_raw = block_info.get("reason", "Unknown")
            if "timeout" in reason_raw.lower():
                reason = BlockReason.TIMEOUT.value
            elif "no_files" in reason_raw.lower():
                reason = BlockReason.NO_FILES.value
            elif "gate" in reason_raw.lower():
                reason = BlockReason.GATE_FAILURE.value
            elif "attempt" in reason_raw.lower():
                reason = BlockReason.ATTEMPT_LIMIT.value
            elif "depend" in reason_raw.lower():
                reason = BlockReason.DEPENDENCY.value
            else:
                reason = BlockReason.MANUAL.value

            # Calculate suggested timeout based on complexity
            config = AdaptiveTimeoutConfig()  # Use defaults
            suggested_timeout = calculate_adaptive_timeout(
                task=task,
                previous_failures=attempts,
                config=config,
                mode_timeout=120,  # speed mode default
            )

            # Get complexity level
            complexity = estimate_task_complexity(task)

            blocked.append(
                BlockedTaskInfo(
                    task_id=task_id,
                    title=task.title,
                    blocked_at=block_info.get("blocked_at", ""),
                    attempts=attempts,
                    reason=reason,
                    block_reason_detail=reason_raw,
                    suggested_timeout=suggested_timeout,
                    complexity_level=complexity.level.value,
                    metadata={
                        "kind": str(task.kind),
                        "acceptance_count": len(task.acceptance),
                    },
                )
            )

        return blocked

    def suggest_unblock_strategy(self, task_info: BlockedTaskInfo) -> str:
        """Suggest unblock strategy based on block reason and metadata.

        Args:
            task_info: The blocked task info

        Returns:
            Strategy recommendation as formatted string
        """
        if task_info.reason == BlockReason.TIMEOUT.value:
            return (
                f"Strategy: Increase timeout for this {task_info.complexity_level} task.\n"
                f"  Current attempts: {task_info.attempts}\n"
                f"  Suggested timeout: {task_info.suggested_timeout}s "
                f"({task_info.suggested_timeout // 60} minutes)\n"
                f"  Command: ralph unblock {task_info.task_id} --timeout {task_info.suggested_timeout}"
            )

        if task_info.reason == BlockReason.NO_FILES.value:
            return (
                "Strategy: Investigate why agent wrote no files.\n"
                "  Check logs: .ralph/logs/iteration-*.log\n"
                "  Check receipts: .ralph/receipts/no_files_written.json\n"
                "  May need: Clarified task acceptance criteria or prompt adjustment"
            )

        if task_info.reason == BlockReason.GATE_FAILURE.value:
            return (
                "Strategy: Fix failing gates before retry.\n"
                "  Run: ralph gates\n"
                "  Or temporarily disable: gates.commands = [] in .ralph/ralph.toml\n"
                "  Document why gates cannot be fixed in .ralph/progress.md"
            )

        if task_info.reason == BlockReason.ATTEMPT_LIMIT.value:
            return (
                f"Strategy: Task failed {task_info.attempts} times.\n"
                f"  Consider: Breaking task into smaller subtasks\n"
                f"  Or: Increase max_attempts_per_task in .ralph/ralph.toml\n"
                f"  Or: Manual review and implementation"
            )

        if task_info.reason == BlockReason.DEPENDENCY.value:
            return (
                f"Strategy: Resolve task dependencies first.\n"
                f"  Dependencies: {task_info.block_reason_detail}\n"
                f"  Complete blocking tasks, then retry."
            )

        return (
            "Strategy: Review task and determine appropriate action.\n"
            "  Manual intervention may be required."
        )

    def unblock_task(
        self,
        task_id: str,
        reason: str,
        new_timeout: Optional[int] = None,
    ) -> UnblockResult:
        """Unblock a task for retry with optional new timeout.

        Updates:
        1. PRD tracker (changes status from blocked to open)
        2. state.json (removes from blocked_tasks, resets attempts)
        3. Records unblock in attempt history

        Args:
            task_id: The task ID to unblock
            reason: Human-readable reason for unblocking
            new_timeout: Optional new timeout for retry (seconds)

        Returns:
            UnblockResult with success status and details
        """
        # Load state
        if not self.state_file.exists():
            return UnblockResult(
                success=False,
                task_id=task_id,
                previous_attempts=0,
                new_timeout=0,
                message="State file not found",
            )

        try:
            state_data = json.loads(self.state_file.read_text())
        except (json.JSONDecodeError, OSError) as e:
            return UnblockResult(
                success=False,
                task_id=task_id,
                previous_attempts=0,
                new_timeout=0,
                message=f"Failed to read state: {e}",
            )

        # Check if task is blocked
        blocked_tasks = state_data.get("blocked_tasks", {})
        if task_id not in blocked_tasks:
            return UnblockResult(
                success=False,
                task_id=task_id,
                previous_attempts=0,
                new_timeout=0,
                message="Task is not currently blocked",
            )

        # Get attempt count
        task_attempts = state_data.get("task_attempts", {})
        attempts_data = task_attempts.get(task_id, {})
        if isinstance(attempts_data, dict) and "count" in attempts_data:
            previous_attempts = attempts_data["count"]
        elif isinstance(attempts_data, int):
            previous_attempts = attempts_data
        else:
            previous_attempts = 0

        # Load tracker
        if self.tracker is None:
            cfg = load_config(self.project_root)
            self.tracker = make_tracker(self.project_root, cfg)

        # Unblock in tracker
        try:
            self.tracker.force_task_open(task_id)
        except Exception as e:
            return UnblockResult(
                task_id=task_id,
                previous_attempts=previous_attempts,
                new_timeout=new_timeout or 0,
                message=f"Failed to unblock in tracker: {e}",
                success=False,
            )

        # Update state: remove from blocked_tasks
        del state_data["blocked_tasks"][task_id]

        # Optional: Reset attempts for clean retry
        if "task_attempts" in state_data and task_id in state_data["task_attempts"]:
            if isinstance(state_data["task_attempts"][task_id], dict):
                state_data["task_attempts"][task_id]["count"] = 0
            else:
                state_data["task_attempts"][task_id] = {"count": 0}

        # Record unblock in attempt history
        if "attempt_history" not in state_data:
            state_data["attempt_history"] = []

        state_data["attempt_history"].append({
            "task_id": task_id,
            "action": "unblocked",
            "reason": reason,
            "unblocked_at": datetime.utcnow().isoformat() + "Z",
            "previous_attempts": previous_attempts,
            "new_timeout": new_timeout,
        })

        # Write state back
        self.state_file.write_text(json.dumps(state_data, indent=2))

        # Update progress log
        progress_file = self.project_root / ".ralph" / "progress.md"
        if progress_file.exists():
            with progress_file.open("a") as f:
                f.write(
                    f"[{datetime.utcnow().isoformat()}Z] UNBLOCKED task {task_id} "
                    f"({previous_attempts} attempts): {reason}\n"
                )

        return UnblockResult(
            success=True,
            task_id=task_id,
            previous_attempts=previous_attempts,
            new_timeout=new_timeout or 0,
            message=f"Unblocked task {task_id}",
        )

    def batch_unblock(
        self,
        filter_reason: Optional[str] = None,
        filter_complexity: Optional[str] = None,
        min_attempts: Optional[int] = None,
        new_timeout_multiplier: float = 1.0,
    ) -> List[UnblockResult]:
        """Batch unblock multiple tasks with filtering.

        Args:
            filter_reason: Only unblock tasks with this reason (e.g., "timeout")
            filter_complexity: Only unblock tasks with this complexity level
            min_attempts: Only unblock tasks with at least this many attempts
            new_timeout_multiplier: Multiply suggested timeout by this factor

        Returns:
            List of unblock results
        """
        blocked = self.list_blocked_tasks()
        results: List[UnblockResult] = []

        for task_info in blocked:
            # Apply filters
            if filter_reason and task_info.reason != filter_reason:
                continue

            if filter_complexity and task_info.complexity_level != filter_complexity:
                continue

            if min_attempts and task_info.attempts < min_attempts:
                continue

            # Calculate new timeout
            new_timeout = int(task_info.suggested_timeout * new_timeout_multiplier)

            # Unblock
            result = self.unblock_task(
                task_id=task_info.task_id,
                reason=f"Batch unblock ({task_info.reason}, {task_info.attempts} attempts)",
                new_timeout=new_timeout,
            )
            results.append(result)

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about blocked tasks.

        Returns:
            Dictionary with blocked task statistics
        """
        blocked = self.list_blocked_tasks()

        if not blocked:
            return {
                "total_blocked": 0,
                "by_reason": {},
                "by_complexity": {},
                "avg_attempts": 0,
            }

        # Count by reason
        by_reason: Dict[str, int] = {}
        for task in blocked:
            by_reason[task.reason] = by_reason.get(task.reason, 0) + 1

        # Count by complexity
        by_complexity: Dict[str, int] = {}
        for task in blocked:
            level = task.complexity_level
            by_complexity[level] = by_complexity.get(level, 0) + 1

        # Average attempts
        avg_attempts = sum(t.attempts for t in blocked) / len(blocked)

        return {
            "total_blocked": len(blocked),
            "by_reason": by_reason,
            "by_complexity": by_complexity,
            "avg_attempts": avg_attempts,
            "total_wasted_iterations": sum(t.attempts for t in blocked),
        }


def format_blocked_table(blocked: List[BlockedTaskInfo]) -> str:
    """Format blocked tasks as a readable table.

    Args:
        blocked: List of blocked task info

    Returns:
        Formatted table string
    """
    if not blocked:
        return "No blocked tasks."

    lines = []
    lines.append("┌──────┬─────────────────────────────────────┬───────────┬─────────────┬──────────────┐")
    lines.append("│ ID   │ Title                             │ Reason    │ Attempts    │ Suggested    │")
    lines.append("│      │                                  │           │             │ Timeout      │")
    lines.append("├──────┼─────────────────────────────────────┼───────────┼─────────────┼──────────────┤")

    for task in blocked[:20]:  # Limit to 20 for readability
        id_short = task.task_id[:6].ljust(6)
        title_short = task.title[:33].ljust(33)
        reason = task.reason[:9].ljust(9)
        attempts = f"{task.attempts}x".ljust(11)
        timeout = f"{task.suggested_timeout}s".ljust(12)
        lines.append(f"│ {id_short}│ {title_short}│ {reason}│ {attempts}│ {timeout}│")

    if len(blocked) > 20:
        lines.append(f"│ ... │ ... {len(blocked) - 20} more tasks ... │")

    lines.append("└──────┴─────────────────────────────────────┴───────────┴─────────────┴──────────────┘")

    return "\n".join(lines)
