"""Tests for metrics collection module (Phase 4).

Tests for:
- IterationMetrics dataclass
- MetricsSnapshot dataclass
- MetricsCollector class
- File save/load functionality
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ralph_gold.metrics import (
    IterationMetrics,
    MetricsSnapshot,
    MetricsCollector,
    create_metrics_from_iteration,
)


class TestIterationMetrics:
    """Tests for IterationMetrics dataclass."""

    def test_default_values(self) -> None:
        """Test IterationMetrics with minimal required fields."""
        metrics = IterationMetrics(iteration=1)

        assert metrics.iteration == 1
        assert metrics.task_id == ""
        assert metrics.files_written_count == 0
        assert metrics.no_files_written is False
        assert metrics.spec_chars_total == 0
        assert metrics.spec_chars_truncated == 0

    def test_with_values(self) -> None:
        """Test IterationMetrics with all fields populated."""
        metrics = IterationMetrics(
            iteration=5,
            task_id="task-123",
            files_written_count=3,
            no_files_written=False,
            spec_chars_total=50000,
            spec_chars_truncated=5000,
            spec_files_included=2,
            spec_files_excluded=1,
            duration_seconds=120.5,
            agent_return_code=0,
            timestamp="2025-01-20T10:00:00Z",
        )

        assert metrics.iteration == 5
        assert metrics.task_id == "task-123"
        assert metrics.files_written_count == 3
        assert metrics.no_files_written is False
        assert metrics.spec_chars_truncated == 5000


class TestMetricsSnapshot:
    """Tests for MetricsSnapshot dataclass."""

    def test_creation(self) -> None:
        """Test creating a MetricsSnapshot."""
        snapshot = MetricsSnapshot(
            total_iterations=10,
            write_success_rate=0.85,
            truncation_rate=0.05,
            avg_duration_seconds=90.0,
            total_files_written=25,
            no_files_count=2,
        )

        assert snapshot.total_iterations == 10
        assert snapshot.write_success_rate == 0.85
        assert snapshot.truncation_rate == 0.05
        assert snapshot.avg_duration_seconds == 90.0
        assert snapshot.total_files_written == 25
        assert snapshot.no_files_count == 2

    def test_to_dict(self) -> None:
        """Test converting snapshot to dictionary."""
        snapshot = MetricsSnapshot(
            total_iterations=10,
            write_success_rate=0.8567,
            truncation_rate=0.0543,
            avg_duration_seconds=90.123,
            total_files_written=25,
            no_files_count=2,
        )

        data = snapshot.to_dict()

        assert data["total_iterations"] == 10
        assert data["write_success_rate"] == 0.8567  # Not rounded in to_dict
        assert data["truncation_rate"] == 0.0543
        assert isinstance(data, dict)


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_empty_collector(self) -> None:
        """Test collector with no iterations."""
        collector = MetricsCollector()

        assert collector.iterations == []
        assert collector.get_write_success_rate() == 0.0
        assert collector.get_truncation_rate() == 0.0

    def test_record_single_iteration(self) -> None:
        """Test recording a single iteration."""
        collector = MetricsCollector()
        metrics = IterationMetrics(
            iteration=1,
            task_id="task-1",
            files_written_count=2,
            no_files_written=False,
        )

        collector.record_iteration(metrics)

        assert len(collector.iterations) == 1
        assert collector.get_write_success_rate() == 1.0

    def test_record_multiple_iterations(self) -> None:
        """Test recording multiple iterations."""
        collector = MetricsCollector()

        collector.record_iteration(
            IterationMetrics(iteration=1, files_written_count=2, no_files_written=False)
        )
        collector.record_iteration(
            IterationMetrics(iteration=2, files_written_count=0, no_files_written=True)
        )
        collector.record_iteration(
            IterationMetrics(iteration=3, files_written_count=1, no_files_written=False)
        )

        assert len(collector.iterations) == 3
        assert collector.get_write_success_rate() == pytest.approx(2/3)  # 2 out of 3

    def test_get_write_success_rate(self) -> None:
        """Test calculating write success rate."""
        collector = MetricsCollector()

        # 3 successful, 1 failed
        for i in range(3):
            collector.record_iteration(
                IterationMetrics(iteration=i, files_written_count=1, no_files_written=False)
            )
        collector.record_iteration(
            IterationMetrics(iteration=3, files_written_count=0, no_files_written=True)
        )

        rate = collector.get_write_success_rate()
        assert rate == pytest.approx(0.75)

    def test_get_truncation_rate(self) -> None:
        """Test calculating truncation rate."""
        collector = MetricsCollector()

        # 10000 total, 1000 truncated = 10% rate
        collector.record_iteration(
            IterationMetrics(
                iteration=1,
                spec_chars_total=10000,
                spec_chars_truncated=1000,
            )
        )

        rate = collector.get_truncation_rate()
        assert rate == pytest.approx(0.1)

    def test_get_truncation_rate_no_data(self) -> None:
        """Test truncation rate when no spec data."""
        collector = MetricsCollector()

        collector.record_iteration(
            IterationMetrics(iteration=1, spec_chars_total=0, spec_chars_truncated=0)
        )

        assert collector.get_truncation_rate() == 0.0

    def test_get_snapshot(self) -> None:
        """Test getting metrics snapshot."""
        collector = MetricsCollector()

        collector.record_iteration(
            IterationMetrics(
                iteration=1,
                files_written_count=2,
                duration_seconds=100.0,
                no_files_written=False,
            )
        )
        collector.record_iteration(
            IterationMetrics(
                iteration=2,
                files_written_count=0,
                duration_seconds=200.0,
                no_files_written=True,
            )
        )

        snapshot = collector.get_snapshot()

        assert snapshot.total_iterations == 2
        assert snapshot.write_success_rate == 0.5
        assert snapshot.avg_duration_seconds == 150.0
        assert snapshot.total_files_written == 2
        assert snapshot.no_files_count == 1

    def test_get_snapshot_empty(self) -> None:
        """Test getting snapshot from empty collector."""
        collector = MetricsCollector()
        snapshot = collector.get_snapshot()

        assert snapshot.total_iterations == 0
        assert snapshot.write_success_rate == 0.0
        assert snapshot.truncation_rate == 0.0

    def test_get_recent_iterations(self) -> None:
        """Test getting recent iterations."""
        collector = MetricsCollector()

        for i in range(10):
            collector.record_iteration(IterationMetrics(iteration=i))

        recent = collector.get_recent_iterations(count=3)

        assert len(recent) == 3
        # Should be most recent first (iterations 9, 8, 7)
        assert recent[0].iteration == 9
        assert recent[1].iteration == 8
        assert recent[2].iteration == 7

    def test_clear(self) -> None:
        """Test clearing all metrics."""
        collector = MetricsCollector()
        collector.record_iteration(IterationMetrics(iteration=1))

        collector.clear()

        assert collector.iterations == []
        assert len(collector.iterations) == 0


class TestMetricsPersistence:
    """Tests for metrics save/load functionality."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Test saving and loading metrics."""
        collector = MetricsCollector()
        collector.record_iteration(
            IterationMetrics(
                iteration=1,
                task_id="task-1",
                files_written_count=2,
                duration_seconds=100.0,
            )
        )

        metrics_file = tmp_path / "metrics.json"
        collector.save_to_file(metrics_file)

        loaded_collector = MetricsCollector.load_from_file(metrics_file)

        assert len(loaded_collector.iterations) == 1
        assert loaded_collector.iterations[0].iteration == 1
        assert loaded_collector.iterations[0].task_id == "task-1"

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading from nonexistent file returns empty collector."""
        collector = MetricsCollector.load_from_file(tmp_path / "nonexistent.json")

        assert collector.iterations == []

    def test_saved_file_has_schema(self, tmp_path: Path) -> None:
        """Test that saved file includes schema identifier."""
        collector = MetricsCollector()
        collector.record_iteration(IterationMetrics(iteration=1))

        metrics_file = tmp_path / "metrics.json"
        collector.save_to_file(metrics_file)

        content = json.loads(metrics_file.read_text())
        assert content["_schema"] == "ralph_gold.metrics.v1"

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test that save creates parent directories."""
        collector = MetricsCollector()
        metrics_file = tmp_path / "nested" / "dir" / "metrics.json"

        collector.save_to_file(metrics_file)

        assert metrics_file.exists()
        assert metrics_file.parent.is_dir()


class TestCreateMetricsFromIteration:
    """Tests for create_metrics_from_iteration helper function."""

    def test_basic_creation(self) -> None:
        """Test creating metrics with basic parameters."""
        metrics = create_metrics_from_iteration(
            iteration=1,
            task_id="task-1",
            files_written_count=2,
            no_files_written=False,
            spec_result=None,
            duration_seconds=100.0,
            agent_return_code=0,
        )

        assert metrics.iteration == 1
        assert metrics.task_id == "task-1"
        assert metrics.files_written_count == 2
        assert metrics.no_files_written is False

    def test_with_spec_result(self) -> None:
        """Test creating metrics with spec result."""
        from ralph_gold.spec_loader import SpecLoadResult

        spec_result = SpecLoadResult(
            included=[("spec1.md", 5000)],
            excluded=[],
            truncated=[("spec2.md", 15000, 10000)],
            total_chars=15000,
            warnings=[],
        )

        metrics = create_metrics_from_iteration(
            iteration=1,
            task_id="task-1",
            files_written_count=1,
            no_files_written=False,
            spec_result=spec_result,
        )

        assert metrics.spec_chars_total == 15000
        assert metrics.spec_chars_truncated == 5000
        assert metrics.spec_files_included == 1
        assert metrics.spec_files_excluded == 0
