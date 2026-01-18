"""Property-based tests for the stats module.

This module contains property-based tests using hypothesis to verify
correctness properties across a wide range of inputs.
"""

from __future__ import annotations

import csv
import statistics
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from hypothesis import given, settings
from hypothesis import strategies as st

from ralph_gold.stats import calculate_stats, export_stats_csv


# Custom strategies for generating test data
@st.composite
def iteration_entry(draw: st.DrawFn) -> Dict[str, Any]:
    """Generate a valid iteration history entry."""
    return {
        "iteration": draw(st.integers(min_value=1, max_value=10000)),
        "duration_seconds": draw(st.floats(min_value=0.0, max_value=10000.0)),
        "gates_ok": draw(st.booleans()),
        "blocked": draw(st.booleans()),
        "story_id": draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
                min_size=1,
                max_size=20,
            )
        ),
    }


@st.composite
def state_with_history(
    draw: st.DrawFn, min_size: int = 1, max_size: int = 100
) -> Dict[str, Any]:
    """Generate a state dict with valid history."""
    history = draw(st.lists(iteration_entry(), min_size=min_size, max_size=max_size))
    return {"history": history}


# Property 5: Statistical Calculation Correctness
@given(
    st.lists(
        st.floats(
            min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False
        ),
        min_size=1,
        max_size=100,
    )
)
@settings(max_examples=20)
def test_property_5_statistical_calculation_correctness(durations: List[float]):
    """**Validates: Requirements 2.1**

    Feature: ralph-enhancement-phase2, Property 5
    For any set of iteration history data, calculated statistics (average, min, max,
    success rate) should be mathematically correct according to standard statistical formulas.
    """
    # Create mock history with the given durations
    history = [
        {
            "iteration": i + 1,
            "duration_seconds": d,
            "gates_ok": True,
            "blocked": False,
            "story_id": f"task-{i % 3}",  # Distribute across 3 tasks
        }
        for i, d in enumerate(durations)
    ]

    state = {"history": history}

    # Calculate stats
    stats = calculate_stats(state)

    # Verify statistical correctness
    expected_avg = statistics.mean(durations)
    expected_min = min(durations)
    expected_max = max(durations)
    expected_total = len(durations)

    # Use approximate equality for floating point comparisons
    assert abs(stats.avg_duration_seconds - expected_avg) < 1e-9, (
        f"Average mismatch: {stats.avg_duration_seconds} != {expected_avg}"
    )
    assert abs(stats.min_duration_seconds - expected_min) < 1e-9, (
        f"Min mismatch: {stats.min_duration_seconds} != {expected_min}"
    )
    assert abs(stats.max_duration_seconds - expected_max) < 1e-9, (
        f"Max mismatch: {stats.max_duration_seconds} != {expected_max}"
    )
    assert stats.total_iterations == expected_total, (
        f"Total iterations mismatch: {stats.total_iterations} != {expected_total}"
    )

    # All iterations have gates_ok=True and blocked=False, so all should be successful
    assert stats.successful_iterations == expected_total
    assert stats.failed_iterations == 0
    assert stats.success_rate == 1.0


@given(state_with_history(min_size=1, max_size=50))
@settings(max_examples=20)
def test_property_5_success_rate_calculation(state: Dict[str, Any]):
    """**Validates: Requirements 2.1**

    Feature: ralph-enhancement-phase2, Property 5
    Success rate should be calculated as successful_iterations / total_iterations.
    """
    stats = calculate_stats(state)

    # Verify success rate formula
    if stats.total_iterations > 0:
        expected_rate = stats.successful_iterations / stats.total_iterations
        assert abs(stats.success_rate - expected_rate) < 1e-9, (
            f"Success rate mismatch: {stats.success_rate} != {expected_rate}"
        )
    else:
        assert stats.success_rate == 0.0


@given(state_with_history(min_size=1, max_size=50))
@settings(max_examples=20)
def test_property_5_task_stats_aggregation(state: Dict[str, Any]):
    """**Validates: Requirements 2.2**

    Feature: ralph-enhancement-phase2, Property 5
    Per-task statistics should correctly aggregate data for each task.
    """
    stats = calculate_stats(state)

    # Manually calculate expected task stats
    task_data: Dict[str, List[Dict[str, Any]]] = {}
    for entry in state["history"]:
        task_id = entry.get("story_id") or entry.get("task_id", "unknown")
        if task_id not in task_data:
            task_data[task_id] = []
        task_data[task_id].append(entry)

    # Verify each task's statistics
    for task_id, entries in task_data.items():
        assert task_id in stats.task_stats, f"Task {task_id} missing from stats"

        task_stats = stats.task_stats[task_id]

        # Verify attempts count
        assert task_stats.attempts == len(entries), (
            f"Task {task_id} attempts mismatch: {task_stats.attempts} != {len(entries)}"
        )

        # Verify duration calculations
        durations = [float(e.get("duration_seconds", 0.0)) for e in entries]
        expected_avg = statistics.mean(durations) if durations else 0.0
        expected_total = sum(durations)

        assert abs(task_stats.avg_duration_seconds - expected_avg) < 1e-9, (
            f"Task {task_id} avg duration mismatch"
        )
        assert abs(task_stats.total_duration_seconds - expected_total) < 1e-9, (
            f"Task {task_id} total duration mismatch"
        )

        # Verify success/failure counts
        successes = sum(
            1
            for e in entries
            if e.get("gates_ok") is True and not e.get("blocked", False)
        )
        failures = len(entries) - successes

        assert task_stats.successes == successes, (
            f"Task {task_id} successes mismatch: {task_stats.successes} != {successes}"
        )
        assert task_stats.failures == failures, (
            f"Task {task_id} failures mismatch: {task_stats.failures} != {failures}"
        )


# Property 6: Duration Tracking Persistence
@given(state_with_history(min_size=1, max_size=50))
@settings(max_examples=20)
def test_property_6_duration_tracking_persistence(state: Dict[str, Any]):
    """**Validates: Requirements 2.1**

    Feature: ralph-enhancement-phase2, Property 6
    For any completed iteration, the state.json file should contain a duration_seconds
    field with a non-negative value.
    """
    # Verify all history entries have duration_seconds
    for entry in state["history"]:
        assert "duration_seconds" in entry or entry.get("duration_seconds", 0.0) >= 0, (
            "History entry missing or has negative duration_seconds"
        )

    # Calculate stats and verify all durations are non-negative
    stats = calculate_stats(state)

    assert stats.avg_duration_seconds >= 0.0, "Average duration is negative"
    assert stats.min_duration_seconds >= 0.0, "Min duration is negative"
    assert stats.max_duration_seconds >= 0.0, "Max duration is negative"

    # Verify per-task durations are non-negative
    for task_stats in stats.task_stats.values():
        assert task_stats.avg_duration_seconds >= 0.0, (
            f"Task {task_stats.task_id} has negative avg duration"
        )
        assert task_stats.total_duration_seconds >= 0.0, (
            f"Task {task_stats.task_id} has negative total duration"
        )


@given(
    st.lists(
        st.floats(
            min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False
        ),
        min_size=1,
        max_size=50,
    )
)
@settings(max_examples=20)
def test_property_6_missing_duration_defaults_to_zero(durations: List[float]):
    """**Validates: Requirements 2.1**

    Feature: ralph-enhancement-phase2, Property 6
    Missing duration_seconds fields should default to 0.0.
    """
    # Create history with some entries missing duration_seconds
    history = []
    for i, d in enumerate(durations):
        entry: Dict[str, Any] = {
            "iteration": i + 1,
            "gates_ok": True,
            "blocked": False,
            "story_id": f"task-{i}",
        }
        # Only include duration for even indices
        if i % 2 == 0:
            entry["duration_seconds"] = d
        history.append(entry)

    state = {"history": history}
    stats = calculate_stats(state)

    # Stats should be calculated with 0.0 for missing durations
    # This should not raise an error
    assert stats.total_iterations == len(durations)
    assert stats.avg_duration_seconds >= 0.0
    assert stats.min_duration_seconds >= 0.0


# Property 7: CSV Export Round-Trip
@given(state_with_history(min_size=1, max_size=30))
@settings(max_examples=20)
def test_property_7_csv_export_round_trip(state: Dict[str, Any]):
    """**Validates: Requirements 2.3**

    Feature: ralph-enhancement-phase2, Property 7
    For any statistics data, exporting to CSV then parsing the CSV should preserve
    all numeric values within floating-point precision.
    """
    # Calculate stats
    stats = calculate_stats(state)

    # Export to CSV using temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        csv_path = Path(f.name)

    try:
        export_stats_csv(stats, csv_path)

        # Verify file was created
        assert csv_path.exists(), "CSV file was not created"

        # Parse CSV and verify data preservation
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Find and verify overall statistics
        metric_rows = {}
        in_overall_section = False
        for i, row in enumerate(rows):
            if row and row[0] == "Overall Statistics":
                in_overall_section = True
                continue
            if in_overall_section and len(row) >= 2 and row[0] and row[0] != "Metric":
                if row[0] == "":  # Empty row marks end of section
                    break
                metric_rows[row[0]] = row[1]

        # Verify numeric values are preserved (within floating point precision)
        assert int(metric_rows["Total Iterations"]) == stats.total_iterations
        assert int(metric_rows["Successful Iterations"]) == stats.successful_iterations
        assert int(metric_rows["Failed Iterations"]) == stats.failed_iterations

        # Parse percentage and compare
        success_rate_str = metric_rows["Success Rate"].rstrip("%")
        success_rate_csv = float(success_rate_str) / 100.0
        assert abs(success_rate_csv - stats.success_rate) < 0.01, (
            f"Success rate not preserved: {success_rate_csv} != {stats.success_rate}"
        )

        # Parse duration values
        avg_duration_csv = float(metric_rows["Average Duration (seconds)"])
        min_duration_csv = float(metric_rows["Min Duration (seconds)"])
        max_duration_csv = float(metric_rows["Max Duration (seconds)"])

        # Verify within floating point precision (0.01 seconds tolerance due to formatting)
        assert abs(avg_duration_csv - stats.avg_duration_seconds) < 0.01, (
            f"Average duration not preserved: {avg_duration_csv} != {stats.avg_duration_seconds}"
        )
        assert abs(min_duration_csv - stats.min_duration_seconds) < 0.01, (
            f"Min duration not preserved: {min_duration_csv} != {stats.min_duration_seconds}"
        )
        assert abs(max_duration_csv - stats.max_duration_seconds) < 0.01, (
            f"Max duration not preserved: {max_duration_csv} != {stats.max_duration_seconds}"
        )
    finally:
        # Cleanup
        if csv_path.exists():
            csv_path.unlink()


@given(state_with_history(min_size=1, max_size=30))
@settings(max_examples=20)
def test_property_7_csv_task_data_preservation(state: Dict[str, Any]):
    """**Validates: Requirements 2.3**

    Feature: ralph-enhancement-phase2, Property 7
    Per-task statistics should be preserved in CSV export.
    """
    # Calculate stats
    stats = calculate_stats(state)

    # Export to CSV using temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        csv_path = Path(f.name)

    try:
        export_stats_csv(stats, csv_path)

        # Parse CSV
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Find per-task statistics section
        task_header_idx = None
        for i, row in enumerate(rows):
            if row and row[0] == "Per-Task Statistics":
                task_header_idx = i
                break

        assert task_header_idx is not None, "Per-Task Statistics section not found"

        # Parse task rows (skip header row)
        task_rows = []
        for row in rows[
            task_header_idx + 2 :
        ]:  # +2 to skip section header and column headers
            if row and row[0] and row[0] not in ["Task ID", ""]:
                task_rows.append(row)

        # Verify we have the same number of tasks
        assert len(task_rows) == len(stats.task_stats), (
            f"Task count mismatch: {len(task_rows)} != {len(stats.task_stats)}"
        )

        # Verify each task's data
        for row in task_rows:
            task_id = row[0]
            assert task_id in stats.task_stats, (
                f"Task {task_id} not found in original stats"
            )

            task_stats = stats.task_stats[task_id]

            # Parse CSV values
            attempts_csv = int(row[1])
            successes_csv = int(row[2])
            failures_csv = int(row[3])
            avg_duration_csv = float(row[5])
            total_duration_csv = float(row[6])

            # Verify preservation
            assert attempts_csv == task_stats.attempts
            assert successes_csv == task_stats.successes
            assert failures_csv == task_stats.failures
            assert abs(avg_duration_csv - task_stats.avg_duration_seconds) < 0.01
            assert abs(total_duration_csv - task_stats.total_duration_seconds) < 0.01
    finally:
        # Cleanup
        if csv_path.exists():
            csv_path.unlink()


# Additional property: Stats calculation is deterministic
@given(state_with_history(min_size=1, max_size=50))
@settings(max_examples=20)
def test_property_stats_calculation_is_deterministic(state: Dict[str, Any]):
    """**Validates: Requirements 2.1**

    Feature: ralph-enhancement-phase2
    Calculating stats multiple times on the same state should produce identical results.
    """
    # Calculate stats twice
    stats1 = calculate_stats(state)
    stats2 = calculate_stats(state)

    # Verify all fields are identical
    assert stats1.total_iterations == stats2.total_iterations
    assert stats1.successful_iterations == stats2.successful_iterations
    assert stats1.failed_iterations == stats2.failed_iterations
    assert stats1.avg_duration_seconds == stats2.avg_duration_seconds
    assert stats1.min_duration_seconds == stats2.min_duration_seconds
    assert stats1.max_duration_seconds == stats2.max_duration_seconds
    assert stats1.success_rate == stats2.success_rate
    assert len(stats1.task_stats) == len(stats2.task_stats)

    # Verify task stats are identical
    for task_id in stats1.task_stats:
        assert task_id in stats2.task_stats
        t1 = stats1.task_stats[task_id]
        t2 = stats2.task_stats[task_id]
        assert t1.attempts == t2.attempts
        assert t1.successes == t2.successes
        assert t1.failures == t2.failures
        assert t1.avg_duration_seconds == t2.avg_duration_seconds
        assert t1.total_duration_seconds == t2.total_duration_seconds


# Additional property: Empty history produces zero stats
@given(st.just({"history": []}))
@settings(max_examples=10)
def test_property_empty_history_produces_zero_stats(state: Dict[str, Any]):
    """**Validates: Requirements 2.1**

    Feature: ralph-enhancement-phase2
    Empty history should produce all-zero statistics.
    """
    stats = calculate_stats(state)

    assert stats.total_iterations == 0
    assert stats.successful_iterations == 0
    assert stats.failed_iterations == 0
    assert stats.avg_duration_seconds == 0.0
    assert stats.min_duration_seconds == 0.0
    assert stats.max_duration_seconds == 0.0
    assert stats.success_rate == 0.0
    assert len(stats.task_stats) == 0


# Additional property: Blocked iterations are counted as failures
@given(
    st.lists(
        st.floats(
            min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False
        ),
        min_size=1,
        max_size=50,
    )
)
@settings(max_examples=20)
def test_property_blocked_iterations_are_failures(durations: List[float]):
    """**Validates: Requirements 2.1**

    Feature: ralph-enhancement-phase2
    Iterations with blocked=True should be counted as failures even if gates_ok=True.
    """
    # Create history where all iterations are blocked
    history = [
        {
            "iteration": i + 1,
            "duration_seconds": d,
            "gates_ok": True,  # Gates pass
            "blocked": True,  # But blocked
            "story_id": f"task-{i}",
        }
        for i, d in enumerate(durations)
    ]

    state = {"history": history}
    stats = calculate_stats(state)

    # All should be counted as failures
    assert stats.successful_iterations == 0, (
        "Blocked iterations should not be counted as successful"
    )
    assert stats.failed_iterations == len(durations), (
        "All blocked iterations should be counted as failures"
    )
    assert stats.success_rate == 0.0, (
        "Success rate should be 0.0 when all iterations are blocked"
    )
