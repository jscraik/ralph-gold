"""Progress visualization and metrics for Ralph Gold.

This module provides functionality to calculate progress metrics from task
tracker and history, format ASCII progress bars and burndown charts, and
calculate velocity for ETA estimation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .prd import status_counts
from .trackers import Tracker

logger = logging.getLogger(__name__)


@dataclass
class ProgressMetrics:
    """Progress tracking metrics."""

    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    blocked_tasks: int
    completion_percentage: float
    velocity_tasks_per_day: float
    estimated_completion_date: Optional[str]


def calculate_progress(
    tracker: Tracker,
    state: Dict[str, Any],
    prd_path: Optional[Path] = None,
) -> ProgressMetrics:
    """Calculate progress metrics from task tracker and history.

    Args:
        tracker: The task tracker to get current task counts
        state: The state dictionary loaded from state.json
        prd_path: Optional path to PRD file for detailed status counts.
                  If provided, blocked tasks are counted accurately.

    Returns:
        ProgressMetrics object with calculated progress information

    Raises:
        ValueError: If tracker or state is invalid
    """
    # Get task counts from tracker
    completed, total = tracker.counts()

    # Get detailed status counts if PRD path is provided
    if prd_path:
        try:
            done, blocked, open_count, total_from_prd = status_counts(prd_path)
            # Use detailed counts from PRD for accuracy
            blocked_tasks = blocked
            # Use tracker's count for consistency, or PRD count if available
            completed = done if total_from_prd > 0 else completed
            total = total_from_prd if total_from_prd > 0 else total
            # In progress is an estimate - assume 1 if any incomplete tasks
            incomplete = total - completed
            in_progress_tasks = 1 if (open_count > 0 and incomplete > 0) else 0
        except (OSError, ValueError) as e:
            logger.debug("Failed to get PRD status: %s", e)
            # Fallback to simple calculation
            incomplete = total - completed
            in_progress_tasks = 1 if incomplete > 0 else 0
            blocked_tasks = 0
    else:
        # Fallback: simple calculation without PRD parsing
        incomplete = total - completed
        in_progress_tasks = 1 if incomplete > 0 else 0
        blocked_tasks = 0  # Cannot determine without PRD

    # Calculate completion percentage
    completion_percentage = (completed / total * 100.0) if total > 0 else 0.0

    # Calculate velocity from history
    velocity = calculate_velocity(state.get("history", []))

    # Calculate ETA (based on incomplete tasks, not blocked)
    incomplete = total - completed
    estimated_completion_date = None
    if velocity > 0 and incomplete > 0:
        days_remaining = incomplete / velocity
        eta_date = datetime.now() + timedelta(days=days_remaining)
        estimated_completion_date = eta_date.strftime("%Y-%m-%d")

    return ProgressMetrics(
        total_tasks=total,
        completed_tasks=completed,
        in_progress_tasks=in_progress_tasks,
        blocked_tasks=blocked_tasks,
        completion_percentage=completion_percentage,
        velocity_tasks_per_day=velocity,
        estimated_completion_date=estimated_completion_date,
    )


def format_progress_bar(
    completed: int,
    total: int,
    width: int = 60,
) -> str:
    """Format ASCII progress bar.

    Args:
        completed: Number of completed tasks
        total: Total number of tasks
        width: Width of the progress bar in characters (default: 60)

    Returns:
        Formatted progress bar string

    Example:
        >>> format_progress_bar(12, 20, width=40)
        'Progress: [████████████░░░░░░░░░░░░░░░░] 60% (12/20 tasks)'
    """
    if total <= 0:
        return f"Progress: [{'░' * width}] 0% (0/0 tasks)"

    percentage = completed / total
    filled_width = int(width * percentage)
    empty_width = width - filled_width

    bar = "█" * filled_width + "░" * empty_width
    percentage_str = f"{percentage * 100:.0f}%"

    return f"Progress: [{bar}] {percentage_str} ({completed}/{total} tasks)"


def format_burndown_chart(
    history: List[Dict[str, Any]],
    width: int = 60,
    height: int = 20,
) -> str:
    """Format ASCII burndown chart.

    Args:
        history: List of iteration history entries from state.json
        width: Width of the chart in characters (default: 60)
        height: Height of the chart in lines (default: 20)

    Returns:
        Formatted ASCII burndown chart string

    Example:
        Tasks
        20 │ ●
           │  ●
        15 │   ●●
           │     ●
        10 │      ●●
           │        ●
         5 │         ●●
           │           ●
         0 └─────────────────
           Day 1  3  5  7  9
    """
    if not history:
        return "No history data available for burndown chart"

    # Extract task completion data over time
    # Group by day and count remaining tasks
    daily_data = _extract_daily_burndown(history)

    if not daily_data:
        return "Insufficient data for burndown chart"

    # Build the chart
    days = list(daily_data.keys())
    remaining_tasks = list(daily_data.values())

    if not remaining_tasks:
        return "No task data available"

    max_tasks = max(remaining_tasks) if remaining_tasks else 1
    min_tasks = min(remaining_tasks) if remaining_tasks else 0

    # Build chart lines
    lines: List[str] = []
    lines.append("Tasks")

    # Y-axis and data points
    for i in range(height):
        # Calculate the task count for this line (from top to bottom)
        line_value = max_tasks - (i * (max_tasks - min_tasks) / (height - 1))

        # Y-axis label
        if i % 4 == 0:  # Show label every 4 lines
            label = f"{int(line_value):3d} │"
        else:
            label = "    │"

        # Plot data points
        chart_line = " " * width
        for day_idx, remaining in enumerate(remaining_tasks):
            x_pos = (
                int((day_idx / (len(remaining_tasks) - 1)) * (width - 1))
                if len(remaining_tasks) > 1
                else 0
            )
            if abs(remaining - line_value) < (max_tasks - min_tasks) / (height * 2):
                chart_line = chart_line[:x_pos] + "●" + chart_line[x_pos + 1 :]

        lines.append(label + chart_line)

    # X-axis
    x_axis = "  0 └" + "─" * width
    lines.append(x_axis)

    # X-axis labels
    x_labels = "     "
    if len(days) > 1:
        for i in range(0, len(days), max(1, len(days) // 5)):
            x_labels += f"Day {i + 1}  "
    else:
        x_labels += "Day 1"
    lines.append(x_labels)

    return "\n".join(lines)


def calculate_velocity(history: List[Dict[str, Any]]) -> float:
    """Calculate tasks completed per day.

    Args:
        history: List of iteration history entries from state.json

    Returns:
        Velocity in tasks per day (0.0 if insufficient data)

    Example:
        >>> history = [
        ...     {"timestamp": "2024-01-01T10:00:00", "gates_ok": True},
        ...     {"timestamp": "2024-01-02T10:00:00", "gates_ok": True},
        ... ]
        >>> calculate_velocity(history)
        1.0
    """
    if not history:
        return 0.0

    # Filter successful iterations
    successful = [
        entry
        for entry in history
        if isinstance(entry, dict) and entry.get("gates_ok") is True
    ]

    if len(successful) < 2:
        return 0.0

    # Parse timestamps and calculate time span
    timestamps: List[datetime] = []
    for entry in successful:
        timestamp_str = entry.get("timestamp")
        if timestamp_str:
            try:
                dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                timestamps.append(dt)
            except (ValueError, AttributeError):
                continue

    if len(timestamps) < 2:
        return 0.0

    # Sort timestamps
    timestamps.sort()

    # Calculate time span in days
    time_span = (timestamps[-1] - timestamps[0]).total_seconds() / 86400.0

    if time_span <= 0:
        return 0.0

    # Calculate velocity
    tasks_completed = len(successful)
    velocity = tasks_completed / time_span

    return velocity


def _extract_daily_burndown(history: List[Dict[str, Any]]) -> Dict[int, int]:
    """Extract daily remaining task counts from history.

    Args:
        history: List of iteration history entries

    Returns:
        Dictionary mapping day number to remaining tasks count
    """
    if not history:
        return {}

    # Parse timestamps and track task completions
    daily_completions: Dict[str, int] = {}

    for entry in history:
        if not isinstance(entry, dict):
            continue

        timestamp_str = entry.get("timestamp")
        gates_ok = entry.get("gates_ok")

        if not timestamp_str or gates_ok is not True:
            continue

        try:
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            day_key = dt.strftime("%Y-%m-%d")
            daily_completions[day_key] = daily_completions.get(day_key, 0) + 1
        except (ValueError, AttributeError):
            continue

    if not daily_completions:
        return {}

    # Sort days and calculate cumulative remaining tasks
    sorted_days = sorted(daily_completions.keys())

    # Estimate total tasks (this is a simplification)
    total_completed = sum(daily_completions.values())

    # Build burndown data (day index -> remaining tasks)
    burndown: Dict[int, int] = {}
    cumulative = 0

    for idx, day in enumerate(sorted_days):
        cumulative += daily_completions[day]
        remaining = total_completed - cumulative
        burndown[idx] = max(0, remaining)

    return burndown
