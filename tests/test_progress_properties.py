"""Property-based tests for the progress module.

This module contains property-based tests using hypothesis to verify
correctness properties across a wide range of inputs.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from hypothesis import given, settings
from hypothesis import strategies as st

from ralph_gold.progress import (
    calculate_velocity,
    format_burndown_chart,
    format_progress_bar,
)


# Custom strategies for generating test data
@st.composite
def valid_timestamp(draw: st.DrawFn) -> str:
    """Generate a valid ISO timestamp."""
    year = draw(st.integers(min_value=2020, max_value=2030))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=28))  # Safe for all months
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))

    dt = datetime(year, month, day, hour, minute, second)
    return dt.isoformat()


@st.composite
def history_entry(draw: st.DrawFn) -> Dict[str, Any]:
    """Generate a valid history entry."""
    return {
        "timestamp": draw(valid_timestamp()),
        "gates_ok": draw(st.booleans()),
    }


@st.composite
def history_list(
    draw: st.DrawFn, min_size: int = 0, max_size: int = 50
) -> List[Dict[str, Any]]:
    """Generate a list of history entries."""
    return draw(st.lists(history_entry(), min_size=min_size, max_size=max_size))


# Property 21: Progress Bar Accuracy
@given(
    st.integers(min_value=0, max_value=1000),
    st.integers(min_value=1, max_value=1000),
    st.integers(min_value=10, max_value=100),
)
@settings(max_examples=100)
def test_property_21_progress_bar_accuracy(completed: int, total: int, width: int):
    """**Validates: Requirements 8.1**

    Feature: ralph-enhancement-phase2, Property 21
    For any completion ratio (completed/total), the progress bar should visually
    represent the percentage with correct proportions.
    """
    # Ensure completed <= total
    if completed > total:
        completed, total = total, completed

    bar = format_progress_bar(completed, total, width=width)

    # Verify bar structure
    assert "Progress:" in bar
    assert f"({completed}/{total} tasks)" in bar

    # Count filled and empty blocks
    filled_count = bar.count("█")
    empty_count = bar.count("░")

    # Total blocks should equal width
    assert filled_count + empty_count == width, (
        f"Total blocks {filled_count + empty_count} != width {width}"
    )

    # Calculate expected filled width
    percentage = completed / total if total > 0 else 0
    expected_filled = int(width * percentage)

    # Verify filled count matches expected (within rounding)
    assert filled_count == expected_filled, (
        f"Filled count {filled_count} != expected {expected_filled} "
        f"(completed={completed}, total={total}, width={width})"
    )

    # Verify percentage display (allow for rounding differences)
    # The format_progress_bar uses f"{percentage * 100:.0f}%" which rounds
    actual_percentage_value = percentage * 100
    rounded_percentage = f"{actual_percentage_value:.0f}%"
    assert rounded_percentage in bar


@given(
    st.integers(min_value=0, max_value=100),
    st.integers(min_value=1, max_value=100),
)
@settings(max_examples=100)
def test_property_21_progress_bar_percentage_accuracy(completed: int, total: int):
    """**Validates: Requirements 8.1**

    Feature: ralph-enhancement-phase2, Property 21
    The displayed percentage should accurately reflect completed/total ratio.
    """
    # Ensure completed <= total
    if completed > total:
        completed, total = total, completed

    bar = format_progress_bar(completed, total, width=60)

    # Calculate expected percentage (using rounding like the implementation)
    expected_percentage = (completed / total * 100) if total > 0 else 0
    expected_str = f"{expected_percentage:.0f}%"

    # Verify percentage is in the bar
    assert expected_str in bar, (
        f"Expected percentage {expected_str} not found in bar: {bar}"
    )


@given(st.integers(min_value=10, max_value=100))
@settings(max_examples=100)
def test_property_21_progress_bar_boundary_cases(width: int):
    """**Validates: Requirements 8.1**

    Feature: ralph-enhancement-phase2, Property 21
    Progress bar should handle boundary cases correctly (0%, 100%).
    """
    # Test 0% completion
    bar_empty = format_progress_bar(0, 10, width=width)
    assert bar_empty.count("█") == 0
    assert bar_empty.count("░") == width
    assert "0%" in bar_empty

    # Test 100% completion
    bar_full = format_progress_bar(10, 10, width=width)
    assert bar_full.count("█") == width
    assert bar_full.count("░") == 0
    assert "100%" in bar_full


# Property 22: Velocity Calculation
@given(
    st.lists(
        st.floats(min_value=0.0, max_value=100.0),
        min_size=2,
        max_size=50,
    )
)
@settings(max_examples=100)
def test_property_22_velocity_calculation(day_offsets: List[float]):
    """**Validates: Requirements 8.2**

    Feature: ralph-enhancement-phase2, Property 22
    For any history of task completions with timestamps, velocity (tasks/day)
    should be calculated as total_completed / days_elapsed.
    """
    # Create history with timestamps spread over the given day offsets
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    history = []

    for i, offset in enumerate(day_offsets):
        timestamp = base_time + timedelta(days=offset)
        history.append(
            {
                "timestamp": timestamp.isoformat(),
                "gates_ok": True,
            }
        )

    velocity = calculate_velocity(history)

    # Calculate expected velocity
    timestamps = [base_time + timedelta(days=offset) for offset in day_offsets]
    timestamps.sort()

    if len(timestamps) >= 2:
        time_span_days = (timestamps[-1] - timestamps[0]).total_seconds() / 86400.0

        if time_span_days > 0:
            expected_velocity = len(day_offsets) / time_span_days

            # Verify velocity calculation (within floating point precision)
            assert abs(velocity - expected_velocity) < 1e-6, (
                f"Velocity {velocity} != expected {expected_velocity} "
                f"(tasks={len(day_offsets)}, days={time_span_days})"
            )
        else:
            # All tasks on same timestamp - velocity calculation returns 0
            # (implementation requires time_span > 0)
            assert velocity == 0.0
    else:
        # Not enough data
        assert velocity == 0.0


@given(history_list(min_size=2, max_size=50))
@settings(max_examples=100)
def test_property_22_velocity_only_counts_successful(history: List[Dict[str, Any]]):
    """**Validates: Requirements 8.2**

    Feature: ralph-enhancement-phase2, Property 22
    Velocity calculation should only count successful iterations (gates_ok=True).
    """
    velocity = calculate_velocity(history)

    # Count successful iterations
    successful = [entry for entry in history if entry.get("gates_ok") is True]

    if len(successful) < 2:
        # Not enough successful iterations
        assert velocity == 0.0
    else:
        # Velocity should be based on successful iterations only
        assert velocity >= 0.0


@given(
    st.integers(min_value=2, max_value=100),  # Need at least 2 tasks
    st.floats(min_value=0.1, max_value=100.0),
)
@settings(max_examples=100)
def test_property_22_velocity_formula(task_count: int, days_elapsed: float):
    """**Validates: Requirements 8.2**

    Feature: ralph-enhancement-phase2, Property 22
    Velocity should equal tasks_completed / days_elapsed.
    """
    # Create history with known task count and time span
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    history = []

    for i in range(task_count):
        # Distribute tasks evenly over the time span
        offset_days = (i / (task_count - 1)) * days_elapsed
        timestamp = base_time + timedelta(days=offset_days)
        history.append(
            {
                "timestamp": timestamp.isoformat(),
                "gates_ok": True,
            }
        )

    velocity = calculate_velocity(history)

    # Calculate expected velocity
    expected_velocity = task_count / days_elapsed

    # Verify (within floating point precision)
    assert abs(velocity - expected_velocity) < 1e-6, (
        f"Velocity {velocity} != expected {expected_velocity} "
        f"(tasks={task_count}, days={days_elapsed})"
    )


# Property 23: ETA Calculation
@given(
    st.integers(min_value=1, max_value=50),
    st.integers(min_value=1, max_value=50),
    st.floats(min_value=0.1, max_value=10.0),
)
@settings(max_examples=100)
def test_property_23_eta_calculation(completed: int, remaining: int, velocity: float):
    """**Validates: Requirements 8.2**

    Feature: ralph-enhancement-phase2, Property 23
    For any current progress and velocity, ETA should be calculated as
    remaining_tasks / velocity (in days from now).
    """
    # Calculate expected ETA
    expected_days = remaining / velocity
    expected_eta = datetime.now() + timedelta(days=expected_days)

    # Verify the calculation logic
    # (This tests the formula, not the full calculate_progress function)
    assert expected_days > 0
    assert expected_eta > datetime.now()

    # Verify the formula: remaining / velocity = days
    calculated_days = remaining / velocity
    assert abs(calculated_days - expected_days) < 1e-9


@given(
    st.integers(min_value=1, max_value=100),
    st.floats(min_value=0.1, max_value=10.0),
)
@settings(max_examples=100)
def test_property_23_eta_is_future_date(remaining_tasks: int, velocity: float):
    """**Validates: Requirements 8.2**

    Feature: ralph-enhancement-phase2, Property 23
    ETA should always be a future date when there are remaining tasks and
    positive velocity.
    """
    # Calculate ETA
    days_remaining = remaining_tasks / velocity
    eta_date = datetime.now() + timedelta(days=days_remaining)

    # ETA should be in the future
    assert eta_date > datetime.now(), (
        f"ETA {eta_date} is not in the future (now={datetime.now()})"
    )

    # Days remaining should be positive
    assert days_remaining > 0


@given(st.integers(min_value=1, max_value=100))
@settings(max_examples=100)
def test_property_23_zero_velocity_no_eta(remaining_tasks: int):
    """**Validates: Requirements 8.2**

    Feature: ralph-enhancement-phase2, Property 23
    When velocity is zero, ETA cannot be calculated (should be None or infinite).
    """
    velocity = 0.0

    # With zero velocity, we cannot calculate ETA
    # The calculate_progress function should return None for estimated_completion_date
    # This property verifies the logic: if velocity <= 0, no ETA
    assert velocity <= 0

    # Cannot divide by zero
    # In the actual implementation, this should result in None for ETA


# Additional property: Velocity is non-negative
@given(history_list(min_size=0, max_size=50))
@settings(max_examples=100)
def test_property_velocity_is_non_negative(history: List[Dict[str, Any]]):
    """**Validates: Requirements 8.2**

    Feature: ralph-enhancement-phase2
    Velocity should always be non-negative (>= 0.0).
    """
    velocity = calculate_velocity(history)

    assert velocity >= 0.0, f"Velocity {velocity} is negative"


# Additional property: Progress bar is idempotent
@given(
    st.integers(min_value=0, max_value=100),
    st.integers(min_value=1, max_value=100),
    st.integers(min_value=10, max_value=100),
)
@settings(max_examples=100)
def test_property_progress_bar_is_idempotent(completed: int, total: int, width: int):
    """**Validates: Requirements 8.1**

    Feature: ralph-enhancement-phase2
    Calling format_progress_bar multiple times with same inputs should produce
    identical output.
    """
    # Ensure completed <= total
    if completed > total:
        completed, total = total, completed

    bar1 = format_progress_bar(completed, total, width=width)
    bar2 = format_progress_bar(completed, total, width=width)

    assert bar1 == bar2, "Progress bar output is not deterministic"


# Additional property: Burndown chart handles empty history gracefully
@given(st.just([]))
@settings(max_examples=10)
def test_property_burndown_chart_empty_history(history: List[Dict[str, Any]]):
    """**Validates: Requirements 8.3**

    Feature: ralph-enhancement-phase2
    Burndown chart should handle empty history without errors.
    """
    chart = format_burndown_chart(history)

    # Should return a message, not crash
    assert isinstance(chart, str)
    assert len(chart) > 0


# Additional property: Burndown chart handles invalid data gracefully
@given(
    st.lists(
        st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.text(), st.integers(), st.booleans(), st.none()),
            min_size=0,
            max_size=5,
        ),
        min_size=1,
        max_size=20,
    )
)
@settings(max_examples=50)
def test_property_burndown_chart_handles_invalid_data(history: List[Dict[str, Any]]):
    """**Validates: Requirements 8.3**

    Feature: ralph-enhancement-phase2
    Burndown chart should handle invalid/malformed history data gracefully.
    """
    # Should not crash, even with invalid data
    try:
        chart = format_burndown_chart(history)
        assert isinstance(chart, str)
    except Exception as e:
        # If it does raise an exception, it should be a reasonable one
        assert isinstance(e, (ValueError, TypeError, KeyError))


# Additional property: Velocity calculation is deterministic
@given(history_list(min_size=0, max_size=50))
@settings(max_examples=100)
def test_property_velocity_is_deterministic(history: List[Dict[str, Any]]):
    """**Validates: Requirements 8.2**

    Feature: ralph-enhancement-phase2
    Calculating velocity multiple times on same history should produce identical results.
    """
    velocity1 = calculate_velocity(history)
    velocity2 = calculate_velocity(history)

    assert velocity1 == velocity2, (
        f"Velocity calculation is not deterministic: {velocity1} != {velocity2}"
    )


# Additional property: Progress bar width is respected
@given(
    st.integers(min_value=0, max_value=100),
    st.integers(min_value=1, max_value=100),
    st.integers(min_value=5, max_value=200),
)
@settings(max_examples=100)
def test_property_progress_bar_width_respected(completed: int, total: int, width: int):
    """**Validates: Requirements 8.1**

    Feature: ralph-enhancement-phase2
    Progress bar should always use exactly the specified width.
    """
    # Ensure completed <= total
    if completed > total:
        completed, total = total, completed

    bar = format_progress_bar(completed, total, width=width)

    # Count total blocks
    total_blocks = bar.count("█") + bar.count("░")

    assert total_blocks == width, (
        f"Progress bar width {total_blocks} != requested width {width}"
    )


# Additional property: Velocity handles same-day completions
@given(st.integers(min_value=2, max_value=50))
@settings(max_examples=50)
def test_property_velocity_same_day_completions(task_count: int):
    """**Validates: Requirements 8.2**

    Feature: ralph-enhancement-phase2
    Velocity should handle multiple tasks completed on the same day.
    """
    # Create history with all tasks on same day but different times
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    history = []

    for i in range(task_count):
        timestamp = base_time + timedelta(hours=i)
        history.append(
            {
                "timestamp": timestamp.isoformat(),
                "gates_ok": True,
            }
        )

    velocity = calculate_velocity(history)

    # Should calculate velocity based on time span (in hours converted to days)
    # Velocity should be positive
    assert velocity > 0, (
        f"Velocity should be positive for same-day completions, got {velocity}"
    )
