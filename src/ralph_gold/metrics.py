"""Metrics collection and tracking for Ralph Gold Loop.

This module provides:
- IterationMetrics: Data structure for tracking metrics per iteration
- MetricsCollector: Collects and aggregates metrics across iterations
- MetricsSnapshot: Immutable snapshot of current metrics state

Phase 4: Tracks write success rate and truncation rate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .atomic_file import atomic_write_json


@dataclass
class IterationMetrics:
    """Metrics collected during a single iteration.

    Attributes:
        iteration: The iteration number
        task_id: The task ID being executed (may be empty)
        files_written_count: Number of user files written
        no_files_written: Whether no files were written
        spec_chars_total: Total spec characters loaded
        spec_chars_truncated: Total spec characters truncated
        spec_files_included: Number of spec files included
        spec_files_excluded: Number of spec files excluded
        duration_seconds: How long the iteration took
        agent_return_code: The agent's exit code
        timestamp: ISO timestamp when iteration completed
    """
    iteration: int
    task_id: str = ""
    files_written_count: int = 0
    no_files_written: bool = False
    spec_chars_total: int = 0
    spec_chars_truncated: int = 0
    spec_files_included: int = 0
    spec_files_excluded: int = 0
    duration_seconds: float = 0.0
    agent_return_code: int = 0
    timestamp: str = ""


@dataclass
class MetricsSnapshot:
    """Immutable snapshot of metrics at a point in time.

    Attributes:
        total_iterations: Total number of iterations tracked
        write_success_rate: Ratio of iterations with files written (0-1)
        truncation_rate: Ratio of spec characters truncated (0-1)
        avg_duration_seconds: Average iteration duration
        total_files_written: Total count of files written across all iterations
        no_files_count: Number of iterations with no files written
    """
    total_iterations: int
    write_success_rate: float
    truncation_rate: float
    avg_duration_seconds: float
    total_files_written: int
    no_files_count: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary for serialization."""
        return {
            "total_iterations": self.total_iterations,
            "write_success_rate": round(self.write_success_rate, 4),
            "truncation_rate": round(self.truncation_rate, 4),
            "avg_duration_seconds": round(self.avg_duration_seconds, 2),
            "total_files_written": self.total_files_written,
            "no_files_count": self.no_files_count,
        }


@dataclass
class MetricsCollector:
    """Collects and aggregates metrics across loop iterations.

    Usage:
        collector = MetricsCollector()
        collector.record_iteration(IterationMetrics(...))
        snapshot = collector.get_snapshot()
        rate = collector.get_write_success_rate()
    """

    iterations: List[IterationMetrics] = field(default_factory=list)

    def record_iteration(self, metrics: IterationMetrics) -> None:
        """Record metrics from a single iteration.

        Args:
            metrics: The IterationMetrics to record
        """
        self.iterations.append(metrics)

    def get_write_success_rate(self) -> float:
        """Calculate the rate of iterations where files were written.

        Returns:
            Float between 0 and 1 representing the success rate.
            Returns 0 if no iterations recorded.
        """
        if not self.iterations:
            return 0.0

        successful = sum(1 for m in self.iterations if not m.no_files_written)
        return successful / len(self.iterations)

    def get_truncation_rate(self) -> float:
        """Calculate the rate of spec characters that were truncated.

        Returns:
            Float between 0 and 1 representing the truncation rate.
            Returns 0 if no spec data available.
        """
        total_chars = sum(m.spec_chars_total for m in self.iterations)
        if total_chars == 0:
            return 0.0

        truncated_chars = sum(m.spec_chars_truncated for m in self.iterations)
        return truncated_chars / total_chars

    def get_snapshot(self) -> MetricsSnapshot:
        """Get current snapshot of all metrics.

        Returns:
            MetricsSnapshot with aggregated metrics
        """
        if not self.iterations:
            return MetricsSnapshot(
                total_iterations=0,
                write_success_rate=0.0,
                truncation_rate=0.0,
                avg_duration_seconds=0.0,
                total_files_written=0,
                no_files_count=0,
            )

        total_iterations = len(self.iterations)
        write_success_rate = self.get_write_success_rate()
        truncation_rate = self.get_truncation_rate()
        avg_duration = sum(m.duration_seconds for m in self.iterations) / total_iterations
        total_files = sum(m.files_written_count for m in self.iterations)
        no_files_count = sum(1 for m in self.iterations if m.no_files_written)

        return MetricsSnapshot(
            total_iterations=total_iterations,
            write_success_rate=write_success_rate,
            truncation_rate=truncation_rate,
            avg_duration_seconds=avg_duration,
            total_files_written=total_files,
            no_files_count=no_files_count,
        )

    def get_recent_iterations(self, count: int = 10) -> List[IterationMetrics]:
        """Get the most recent N iterations.

        Args:
            count: Maximum number of recent iterations to return

        Returns:
            List of recent IterationMetrics (most recent first)
        """
        return list(reversed(self.iterations[-count:]))

    def clear(self) -> None:
        """Clear all collected metrics."""
        self.iterations.clear()

    def save_to_file(self, path: Path) -> None:
        """Save metrics snapshot to file as JSON.

        Args:
            path: Path to save the metrics file
        """
        snapshot = self.get_snapshot()
        data = {
            "_schema": "ralph_gold.metrics.v1",
            "snapshot": snapshot.to_dict(),
            "iterations": [
                {
                    "iteration": m.iteration,
                    "task_id": m.task_id,
                    "files_written_count": m.files_written_count,
                    "no_files_written": m.no_files_written,
                    "spec_chars_total": m.spec_chars_total,
                    "spec_chars_truncated": m.spec_chars_truncated,
                    "duration_seconds": m.duration_seconds,
                    "agent_return_code": m.agent_return_code,
                    "timestamp": m.timestamp,
                }
                for m in self.iterations
            ],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path, data)

    @classmethod
    def load_from_file(cls, path: Path) -> "MetricsCollector":
        """Load metrics from file.

        Args:
            path: Path to the metrics file

        Returns:
            New MetricsCollector with loaded metrics
        """
        collector = cls()

        if not path.exists():
            return collector

        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return collector

        for item in data.get("iterations", []):
            metrics = IterationMetrics(
                iteration=item.get("iteration", 0),
                task_id=item.get("task_id", ""),
                files_written_count=item.get("files_written_count", 0),
                no_files_written=item.get("no_files_written", False),
                spec_chars_total=item.get("spec_chars_total", 0),
                spec_chars_truncated=item.get("spec_chars_truncated", 0),
                duration_seconds=item.get("duration_seconds", 0.0),
                agent_return_code=item.get("agent_return_code", 0),
                timestamp=item.get("timestamp", ""),
            )
            collector.record_iteration(metrics)

        return collector


def create_metrics_from_iteration(
    iteration: int,
    task_id: str,
    files_written_count: int,
    no_files_written: bool,
    spec_result: Optional[Any] = None,
    duration_seconds: float = 0.0,
    agent_return_code: int = 0,
) -> IterationMetrics:
    """Helper function to create IterationMetrics from common iteration data.

    Args:
        iteration: The iteration number
        task_id: The task ID being executed
        files_written_count: Number of files written
        no_files_written: Whether no files were written
        spec_result: Optional SpecLoadResult from spec_loader
        duration_seconds: Iteration duration
        agent_return_code: Agent's exit code

    Returns:
        IterationMetrics populated with provided data
    """
    spec_chars_total = 0
    spec_chars_truncated = 0
    spec_files_included = 0
    spec_files_excluded = 0

    if spec_result is not None:
        spec_chars_total = spec_result.total_chars
        # Calculate total truncated chars (original - truncated for each)
        spec_chars_truncated = sum(
            original - truncated
            for _, original, truncated in spec_result.truncated
        )
        spec_files_included = len(spec_result.included)
        spec_files_excluded = len(spec_result.excluded)

    from .receipts import iso_utc

    return IterationMetrics(
        iteration=iteration,
        task_id=task_id,
        files_written_count=files_written_count,
        no_files_written=no_files_written,
        spec_chars_total=spec_chars_total,
        spec_chars_truncated=spec_chars_truncated,
        spec_files_included=spec_files_included,
        spec_files_excluded=spec_files_excluded,
        duration_seconds=duration_seconds,
        agent_return_code=agent_return_code,
        timestamp=iso_utc(),
    )
