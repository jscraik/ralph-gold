"""Statistics tracking and analysis for Ralph Gold iterations.

This module provides functionality to calculate, format, and export
iteration statistics including duration, success rate, and per-task metrics.
"""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class TaskStats:
    """Statistics for a specific task."""

    task_id: str
    attempts: int
    successes: int
    failures: int
    avg_duration_seconds: float
    total_duration_seconds: float

    @property
    def success_rate(self) -> float:
        """Calculate success rate for this task."""
        if self.attempts == 0:
            return 0.0
        return self.successes / self.attempts


@dataclass
class IterationStats:
    """Statistics for iterations."""

    total_iterations: int
    successful_iterations: int
    failed_iterations: int
    avg_duration_seconds: float
    min_duration_seconds: float
    max_duration_seconds: float
    success_rate: float
    task_stats: Dict[str, TaskStats] = field(default_factory=dict)


def calculate_stats(state: Dict[str, Any]) -> IterationStats:
    """Calculate statistics from state.json history.

    Args:
        state: The state dictionary loaded from state.json

    Returns:
        IterationStats object with calculated statistics

    Raises:
        ValueError: If state is invalid or missing required fields
    """
    history = state.get("history", [])
    if not isinstance(history, list):
        raise ValueError("state.history must be a list")

    if not history:
        # Return empty stats for no history
        return IterationStats(
            total_iterations=0,
            successful_iterations=0,
            failed_iterations=0,
            avg_duration_seconds=0.0,
            min_duration_seconds=0.0,
            max_duration_seconds=0.0,
            success_rate=0.0,
            task_stats={},
        )

    # Collect durations and success indicators
    durations: List[float] = []
    successful_count = 0
    failed_count = 0

    # Track per-task statistics
    task_data: Dict[str, Dict[str, Any]] = {}

    for entry in history:
        if not isinstance(entry, dict):
            continue

        # Extract duration (default to 0.0 if missing)
        duration = float(entry.get("duration_seconds", 0.0))
        durations.append(duration)

        # Determine success (gates passed and no blocking)
        gates_ok = entry.get("gates_ok")
        blocked = entry.get("blocked", False)
        success = gates_ok is True and not blocked

        if success:
            successful_count += 1
        else:
            failed_count += 1

        # Track per-task stats
        task_id = entry.get("story_id") or entry.get("task_id", "unknown")
        if task_id not in task_data:
            task_data[task_id] = {
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "durations": [],
            }

        task_data[task_id]["attempts"] += 1
        task_data[task_id]["durations"].append(duration)
        if success:
            task_data[task_id]["successes"] += 1
        else:
            task_data[task_id]["failures"] += 1

    # Calculate overall statistics
    total = len(history)
    avg_duration = statistics.mean(durations) if durations else 0.0
    min_duration = min(durations) if durations else 0.0
    max_duration = max(durations) if durations else 0.0
    success_rate = successful_count / total if total > 0 else 0.0

    # Build per-task statistics
    task_stats: Dict[str, TaskStats] = {}
    for task_id, data in task_data.items():
        task_durations = data["durations"]
        task_stats[task_id] = TaskStats(
            task_id=task_id,
            attempts=data["attempts"],
            successes=data["successes"],
            failures=data["failures"],
            avg_duration_seconds=(
                statistics.mean(task_durations) if task_durations else 0.0
            ),
            total_duration_seconds=sum(task_durations),
        )

    return IterationStats(
        total_iterations=total,
        successful_iterations=successful_count,
        failed_iterations=failed_count,
        avg_duration_seconds=avg_duration,
        min_duration_seconds=min_duration,
        max_duration_seconds=max_duration,
        success_rate=success_rate,
        task_stats=task_stats,
    )


def export_stats_csv(stats: IterationStats, output_path: Path) -> None:
    """Export statistics to CSV format.

    Creates a CSV file with two sections:
    1. Overall statistics
    2. Per-task statistics

    Args:
        stats: The IterationStats object to export
        output_path: Path where the CSV file should be written

    Raises:
        IOError: If the file cannot be written
    """
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Overall statistics section
        writer.writerow(["Overall Statistics"])
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Iterations", stats.total_iterations])
        writer.writerow(["Successful Iterations", stats.successful_iterations])
        writer.writerow(["Failed Iterations", stats.failed_iterations])
        writer.writerow(["Success Rate", f"{stats.success_rate:.2%}"])
        writer.writerow(
            ["Average Duration (seconds)", f"{stats.avg_duration_seconds:.2f}"]
        )
        writer.writerow(["Min Duration (seconds)", f"{stats.min_duration_seconds:.2f}"])
        writer.writerow(["Max Duration (seconds)", f"{stats.max_duration_seconds:.2f}"])
        writer.writerow([])  # Empty row separator

        # Per-task statistics section
        writer.writerow(["Per-Task Statistics"])
        writer.writerow(
            [
                "Task ID",
                "Attempts",
                "Successes",
                "Failures",
                "Success Rate",
                "Avg Duration (seconds)",
                "Total Duration (seconds)",
            ]
        )

        # Sort tasks by total duration (descending) to show slowest first
        sorted_tasks = sorted(
            stats.task_stats.values(),
            key=lambda t: t.total_duration_seconds,
            reverse=True,
        )

        for task in sorted_tasks:
            writer.writerow(
                [
                    task.task_id,
                    task.attempts,
                    task.successes,
                    task.failures,
                    f"{task.success_rate:.2%}",
                    f"{task.avg_duration_seconds:.2f}",
                    f"{task.total_duration_seconds:.2f}",
                ]
            )


def format_stats_report(stats: IterationStats, by_task: bool = False) -> str:
    """Format statistics as human-readable report.

    Args:
        stats: The IterationStats object to format
        by_task: If True, include detailed per-task breakdown

    Returns:
        Formatted string report
    """
    lines: List[str] = []

    # Header
    lines.append("=" * 60)
    lines.append("Ralph Gold - Iteration Statistics")
    lines.append("=" * 60)
    lines.append("")

    # Overall statistics
    lines.append("Overall Statistics:")
    lines.append(f"  Total Iterations:      {stats.total_iterations}")
    lines.append(f"  Successful:            {stats.successful_iterations}")
    lines.append(f"  Failed:                {stats.failed_iterations}")
    lines.append(f"  Success Rate:          {stats.success_rate:.1%}")
    lines.append("")

    lines.append("Duration Statistics:")
    lines.append(f"  Average:               {stats.avg_duration_seconds:.2f}s")
    lines.append(f"  Minimum:               {stats.min_duration_seconds:.2f}s")
    lines.append(f"  Maximum:               {stats.max_duration_seconds:.2f}s")
    lines.append("")

    # Per-task breakdown if requested
    if by_task and stats.task_stats:
        lines.append("=" * 60)
        lines.append("Per-Task Statistics (sorted by total duration):")
        lines.append("=" * 60)
        lines.append("")

        # Sort tasks by total duration (descending)
        sorted_tasks = sorted(
            stats.task_stats.values(),
            key=lambda t: t.total_duration_seconds,
            reverse=True,
        )

        for task in sorted_tasks:
            lines.append(f"Task: {task.task_id}")
            lines.append(f"  Attempts:              {task.attempts}")
            lines.append(f"  Successes:             {task.successes}")
            lines.append(f"  Failures:              {task.failures}")
            lines.append(f"  Success Rate:          {task.success_rate:.1%}")
            lines.append(f"  Avg Duration:          {task.avg_duration_seconds:.2f}s")
            lines.append(f"  Total Duration:        {task.total_duration_seconds:.2f}s")
            lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)
