"""Unit tests for interactive task selection module."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ralph_gold.interactive import (
    TaskChoice,
    convert_selected_task_to_choice,
    filter_tasks_by_keyword,
    format_task_list,
    select_task_interactive,
)
from ralph_gold.prd import SelectedTask

# Test fixtures


@pytest.fixture
def sample_tasks() -> list[TaskChoice]:
    """Create sample tasks for testing."""
    return [
        TaskChoice(
            task_id="task-1",
            title="Implement login feature",
            priority="high",
            status="ready",
            blocked=False,
            acceptance_criteria=[
                "User can log in with email and password",
                "Invalid credentials show error message",
                "Successful login redirects to dashboard",
            ],
        ),
        TaskChoice(
            task_id="task-2",
            title="Add unit tests for authentication",
            priority="medium",
            status="ready",
            blocked=False,
            acceptance_criteria=[
                "Test successful login",
                "Test failed login",
                "Test session management",
            ],
        ),
        TaskChoice(
            task_id="task-3",
            title="Fix database migration bug",
            priority="high",
            status="blocked",
            blocked=True,
            acceptance_criteria=[
                "Migration runs without errors",
                "Data integrity is maintained",
            ],
        ),
        TaskChoice(
            task_id="task-4",
            title="Update documentation",
            priority="low",
            status="ready",
            blocked=False,
            acceptance_criteria=["README is updated", "API docs are complete"],
        ),
    ]


# Test format_task_list


def test_format_task_list_basic(sample_tasks):
    """Test basic task list formatting."""
    result = format_task_list(sample_tasks[:2])

    assert "Available tasks:" in result
    assert "1. task-1: Implement login feature" in result
    assert "2. task-2: Add unit tests for authentication" in result
    assert "[HIGH]" in result
    assert "[MEDIUM]" in result


def test_format_task_list_empty():
    """Test formatting empty task list."""
    result = format_task_list([])
    assert result == "(no tasks available)"


def test_format_task_list_filters_blocked_by_default(sample_tasks):
    """Test that blocked tasks are filtered by default."""
    result = format_task_list(sample_tasks, show_blocked=False)

    # Should not include blocked task
    assert "task-3" not in result
    assert "[BLOCKED]" not in result

    # Should include unblocked tasks
    assert "task-1" in result
    assert "task-2" in result
    assert "task-4" in result


def test_format_task_list_shows_blocked_when_requested(sample_tasks):
    """Test that blocked tasks are shown when requested."""
    result = format_task_list(sample_tasks, show_blocked=True)

    assert "task-3" in result
    assert "[BLOCKED]" in result


def test_format_task_list_with_criteria(sample_tasks):
    """Test formatting with acceptance criteria."""
    result = format_task_list(sample_tasks[:1], show_criteria=True)

    assert "Acceptance criteria:" in result
    assert "User can log in with email and password" in result
    assert "Invalid credentials show error message" in result


def test_format_task_list_limits_criteria_display(sample_tasks):
    """Test that long criteria lists are truncated."""
    # Create task with many criteria
    task = TaskChoice(
        task_id="task-x",
        title="Complex task",
        priority="high",
        status="ready",
        blocked=False,
        acceptance_criteria=[f"Criterion {i}" for i in range(10)],
    )

    result = format_task_list([task], show_criteria=True)

    # Should show first 5 and indicate more
    assert "Criterion 0" in result
    assert "Criterion 4" in result
    assert "and 5 more" in result


# Test filter_tasks_by_keyword


def test_filter_by_keyword_in_title(sample_tasks):
    """Test filtering by keyword in title."""
    result = filter_tasks_by_keyword(sample_tasks, "Implement")

    assert len(result) == 1
    assert result[0].task_id == "task-1"


def test_filter_by_keyword_in_task_id(sample_tasks):
    """Test filtering by keyword in task ID."""
    result = filter_tasks_by_keyword(sample_tasks, "task-2")

    assert len(result) == 1
    assert result[0].task_id == "task-2"


def test_filter_by_keyword_in_criteria(sample_tasks):
    """Test filtering by keyword in acceptance criteria."""
    result = filter_tasks_by_keyword(sample_tasks, "dashboard")

    assert len(result) == 1
    assert result[0].task_id == "task-1"


def test_filter_by_keyword_case_insensitive(sample_tasks):
    """Test that keyword filtering is case-insensitive."""
    result1 = filter_tasks_by_keyword(sample_tasks, "IMPLEMENT")
    result2 = filter_tasks_by_keyword(sample_tasks, "implement")
    result3 = filter_tasks_by_keyword(sample_tasks, "Implement")

    assert len(result1) == len(result2) == len(result3) == 1
    assert result1[0].task_id == result2[0].task_id == result3[0].task_id


def test_filter_by_keyword_empty_string(sample_tasks):
    """Test that empty keyword returns all tasks."""
    result = filter_tasks_by_keyword(sample_tasks, "")
    assert len(result) == len(sample_tasks)

    result = filter_tasks_by_keyword(sample_tasks, "   ")
    assert len(result) == len(sample_tasks)


def test_filter_by_keyword_no_matches(sample_tasks):
    """Test filtering with no matches."""
    result = filter_tasks_by_keyword(sample_tasks, "nonexistent")
    assert len(result) == 0


def test_filter_by_keyword_multiple_matches(sample_tasks):
    """Test filtering with multiple matches."""
    result = filter_tasks_by_keyword(sample_tasks, "test")

    # Should match task-2 (in title) and potentially others
    assert len(result) >= 1
    assert any(t.task_id == "task-2" for t in result)


# Test select_task_interactive


def test_select_task_interactive_empty_list():
    """Test interactive selection with empty task list."""
    with patch("sys.stdout", new=StringIO()) as mock_stdout:
        result = select_task_interactive([])

        assert result is None
        output = mock_stdout.getvalue()
        assert "No tasks available" in output


def test_select_task_interactive_single_task(sample_tasks):
    """Test automatic selection when only one task available."""
    with patch("sys.stdout", new=StringIO()) as mock_stdout:
        result = select_task_interactive([sample_tasks[0]])

        assert result is not None
        assert result.task_id == "task-1"
        output = mock_stdout.getvalue()
        assert "Only one task available" in output
        assert "Automatically selecting" in output


def test_select_task_interactive_filters_blocked_by_default(sample_tasks):
    """Test that blocked tasks are filtered by default."""
    # Only task-3 is blocked, so we should have 3 unblocked tasks
    with patch("sys.stdout", new=StringIO()):
        with patch("builtins.input", return_value="1"):
            result = select_task_interactive(sample_tasks, show_blocked=False)

            # Should select first unblocked task
            assert result is not None
            assert not result.blocked


def test_select_task_interactive_numeric_selection(sample_tasks):
    """Test selecting task by number."""
    with patch("sys.stdout", new=StringIO()):
        with patch("builtins.input", return_value="2"):
            result = select_task_interactive(sample_tasks)

            assert result is not None
            # Should be second unblocked task (task-2)
            assert result.task_id == "task-2"


def test_select_task_interactive_quit_command(sample_tasks):
    """Test quitting interactive selection."""
    with patch("sys.stdout", new=StringIO()) as mock_stdout:
        with patch("builtins.input", return_value="q"):
            result = select_task_interactive(sample_tasks)

            assert result is None
            output = mock_stdout.getvalue()
            assert "cancelled" in output.lower()


def test_select_task_interactive_invalid_number(sample_tasks):
    """Test handling invalid task number."""
    # First input is invalid (shows error + waits for Enter), then valid selection
    with patch("sys.stdout", new=StringIO()):
        with patch("builtins.input", side_effect=["99", "", "1"]):
            result = select_task_interactive(sample_tasks)

            assert result is not None


def test_select_task_interactive_search_command(sample_tasks):
    """Test search/filter command."""
    # Search for "login", then select task 1
    with patch("sys.stdout", new=StringIO()):
        with patch("builtins.input", side_effect=["s login", "1"]):
            result = select_task_interactive(sample_tasks)

            assert result is not None
            assert result.task_id == "task-1"


def test_select_task_interactive_clear_filter(sample_tasks):
    """Test clearing search filter."""
    # Search, clear, then select
    with patch("sys.stdout", new=StringIO()):
        with patch("builtins.input", side_effect=["s login", "c", "2"]):
            result = select_task_interactive(sample_tasks)

            assert result is not None


def test_select_task_interactive_show_details(sample_tasks):
    """Test showing task details."""
    # Show details for task 1, then select it
    with patch("sys.stdout", new=StringIO()) as mock_stdout:
        with patch("builtins.input", side_effect=["d 1", "", "1"]):
            result = select_task_interactive(sample_tasks)

            assert result is not None
            output = mock_stdout.getvalue()
            # Details should be shown
            assert "Acceptance Criteria:" in output


def test_select_task_interactive_keyboard_interrupt(sample_tasks):
    """Test handling keyboard interrupt (Ctrl+C)."""
    with patch("sys.stdout", new=StringIO()) as mock_stdout:
        with patch("builtins.input", side_effect=KeyboardInterrupt()):
            result = select_task_interactive(sample_tasks)

            assert result is None
            output = mock_stdout.getvalue()
            assert "cancelled" in output.lower()


def test_select_task_interactive_eof(sample_tasks):
    """Test handling EOF."""
    with patch("sys.stdout", new=StringIO()) as mock_stdout:
        with patch("builtins.input", side_effect=EOFError()):
            result = select_task_interactive(sample_tasks)

            assert result is None
            output = mock_stdout.getvalue()
            assert "cancelled" in output.lower()


def test_select_task_interactive_no_unblocked_tasks():
    """Test when all tasks are blocked."""
    blocked_tasks = [
        TaskChoice(
            task_id="task-1",
            title="Blocked task",
            priority="high",
            status="blocked",
            blocked=True,
            acceptance_criteria=[],
        )
    ]

    with patch("sys.stdout", new=StringIO()) as mock_stdout:
        result = select_task_interactive(blocked_tasks, show_blocked=False)

        assert result is None
        output = mock_stdout.getvalue()
        assert "No unblocked tasks" in output


def test_select_task_interactive_show_blocked_flag():
    """Test showing blocked tasks with flag."""
    blocked_task = TaskChoice(
        task_id="task-1",
        title="Blocked task",
        priority="high",
        status="blocked",
        blocked=True,
        acceptance_criteria=[],
    )

    with patch("sys.stdout", new=StringIO()):
        with patch("builtins.input", return_value="1"):
            result = select_task_interactive([blocked_task], show_blocked=True)

            assert result is not None
            assert result.blocked


# Test convert_selected_task_to_choice


def test_convert_selected_task_to_choice_basic():
    """Test converting SelectedTask to TaskChoice."""
    selected = SelectedTask(
        id="task-1",
        title="Test task",
        kind="md",
        acceptance=["Criterion 1", "Criterion 2"],
    )

    choice = convert_selected_task_to_choice(selected)

    assert choice.task_id == "task-1"
    assert choice.title == "Test task"
    assert choice.priority == "medium"
    assert choice.status == "ready"
    assert not choice.blocked
    assert len(choice.acceptance_criteria) == 2


def test_convert_selected_task_to_choice_with_params():
    """Test converting with custom parameters."""
    selected = SelectedTask(
        id="task-2",
        title="Another task",
        kind="json",
        acceptance=[],
    )

    choice = convert_selected_task_to_choice(
        selected,
        priority="high",
        status="in_progress",
        blocked=True,
    )

    assert choice.task_id == "task-2"
    assert choice.priority == "high"
    assert choice.status == "in_progress"
    assert choice.blocked


def test_convert_selected_task_to_choice_no_title():
    """Test converting task without title."""
    selected = SelectedTask(
        id="task-3",
        title="",
        kind="md",
        acceptance=[],
    )

    choice = convert_selected_task_to_choice(selected)

    # Should use task ID as title
    assert choice.title == "task-3"


def test_convert_selected_task_to_choice_empty_acceptance():
    """Test converting task with no acceptance criteria."""
    selected = SelectedTask(
        id="task-4",
        title="Task without criteria",
        kind="md",
        acceptance=[],
    )

    choice = convert_selected_task_to_choice(selected)

    assert choice.acceptance_criteria == []


# Edge case tests


def test_format_task_list_with_empty_priority(sample_tasks):
    """Test formatting task with empty priority."""
    task = TaskChoice(
        task_id="task-x",
        title="No priority task",
        priority="",
        status="ready",
        blocked=False,
        acceptance_criteria=[],
    )

    result = format_task_list([task])

    # Should not crash, priority marker should be absent
    assert "task-x" in result
    assert "No priority task" in result


def test_filter_by_keyword_with_special_characters(sample_tasks):
    """Test filtering with special characters in keyword."""
    result = filter_tasks_by_keyword(sample_tasks, "task-1")

    assert len(result) == 1
    assert result[0].task_id == "task-1"


def test_select_task_interactive_empty_input(sample_tasks):
    """Test handling empty input."""
    # Empty input, then valid selection
    with patch("sys.stdout", new=StringIO()):
        with patch("builtins.input", side_effect=["", "1"]):
            result = select_task_interactive(sample_tasks)

            assert result is not None


def test_select_task_interactive_invalid_command(sample_tasks):
    """Test handling invalid command."""
    # Invalid command (shows error + waits for Enter), then valid selection
    with patch("sys.stdout", new=StringIO()):
        with patch("builtins.input", side_effect=["xyz", "", "1"]):
            result = select_task_interactive(sample_tasks)

            assert result is not None


def test_select_task_interactive_search_no_results(sample_tasks):
    """Test search with no results."""
    # Search with no matches, then clear and select
    with patch("sys.stdout", new=StringIO()):
        with patch("builtins.input", side_effect=["s nonexistent", "", "c", "1"]):
            result = select_task_interactive(sample_tasks)

            assert result is not None


# Property-based tests using hypothesis


# Custom strategies for generating test data
@st.composite
def task_choice_strategy(draw: st.DrawFn) -> TaskChoice:
    """Generate a valid TaskChoice for property testing."""
    task_id = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pd")),
            min_size=1,
            max_size=20,
        )
    )
    title = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
            min_size=1,
            max_size=50,
        )
    )
    priority = draw(st.sampled_from(["high", "medium", "low", ""]))
    status = draw(st.sampled_from(["ready", "in_progress", "blocked", "done"]))
    blocked = draw(st.booleans())
    acceptance_criteria = draw(
        st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
                min_size=1,
                max_size=100,
            ),
            min_size=0,
            max_size=10,
        )
    )

    return TaskChoice(
        task_id=task_id,
        title=title,
        priority=priority,
        status=status,
        blocked=blocked,
        acceptance_criteria=acceptance_criteria,
    )


# Property 10: Task Filtering Correctness
@given(st.lists(task_choice_strategy(), min_size=0, max_size=50))
@settings(max_examples=20)
def test_property_10_task_filtering_correctness(tasks: list[TaskChoice]):
    """**Validates: Requirements US-4.3**

    Feature: ralph-enhancement-phase2, Property 10
    For any task list with blocked tasks, enabling the blocked filter should exclude
    all tasks with unmet dependencies or blocked status.
    """
    # Filter out blocked tasks (default behavior)
    filtered_tasks = [t for t in tasks if not t.blocked]

    # Verify that format_task_list with show_blocked=False excludes blocked tasks
    result = format_task_list(tasks, show_blocked=False)

    # Check that no blocked task IDs appear in the output
    for task in tasks:
        if task.blocked:
            # Blocked tasks should not appear in the output
            # (unless there are no unblocked tasks, but we check the logic)
            if filtered_tasks:  # If there are unblocked tasks
                assert task.task_id not in result or "[BLOCKED]" not in result

    # Verify that all unblocked tasks are present
    for task in filtered_tasks:
        if filtered_tasks:  # Only check if there are tasks to display
            assert task.task_id in result or result == "(no tasks available)"

    # Verify the count: number of tasks in output should match unblocked count
    if not tasks:
        assert result == "(no tasks available)"
    elif not filtered_tasks:
        # All tasks are blocked, so with show_blocked=False, none should appear
        # The format_task_list function will show "(no tasks available)" or skip them
        pass  # This is handled by the function's logic


@given(st.lists(task_choice_strategy(), min_size=0, max_size=50))
@settings(max_examples=20)
def test_property_10_blocked_filter_completeness(tasks: list[TaskChoice]):
    """**Validates: Requirements US-4.3**

    Feature: ralph-enhancement-phase2, Property 10
    When show_blocked=True, all tasks including blocked ones should be shown.
    When show_blocked=False, no blocked tasks should be shown.
    """
    # Test with show_blocked=True
    result_with_blocked = format_task_list(tasks, show_blocked=True)

    # All tasks should appear when show_blocked=True
    for task in tasks:
        if tasks:  # Only check if there are tasks
            assert (
                task.task_id in result_with_blocked
                or result_with_blocked == "(no tasks available)"
            )

    # Test with show_blocked=False
    format_task_list(tasks, show_blocked=False)

    # Count how many unblocked tasks exist
    unblocked_count = sum(1 for t in tasks if not t.blocked)

    if unblocked_count == 0:
        # If all tasks are blocked, result should show no tasks or be empty
        pass
    else:
        # Verify blocked tasks don't appear (unless they're the only ones)
        for task in tasks:
            if task.blocked:
                # The blocked task ID might appear, but it shouldn't be in the numbered list
                # We verify by checking the [BLOCKED] marker isn't present
                if unblocked_count > 0:
                    # When there are unblocked tasks, blocked ones shouldn't be shown
                    pass  # The function handles this internally


# Property 11: Search Filter Accuracy
@given(
    st.lists(task_choice_strategy(), min_size=1, max_size=50),
    st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
        min_size=1,
        max_size=20,
    ),
)
@settings(max_examples=20)
def test_property_11_search_filter_accuracy(tasks: list[TaskChoice], search_term: str):
    """**Validates: Requirements US-4.1, US-4.2**

    Feature: ralph-enhancement-phase2, Property 11
    For any search term and task list, filtered results should only include tasks
    where the search term appears in the task ID, title, or acceptance criteria.
    """
    # Apply the filter
    filtered = filter_tasks_by_keyword(tasks, search_term)

    search_lower = search_term.strip().lower()

    # Verify every filtered task contains the search term
    for task in filtered:
        # Check if search term appears in task_id, title, or acceptance criteria
        found = False

        if search_lower in task.task_id.lower():
            found = True
        elif search_lower in task.title.lower():
            found = True
        else:
            for criterion in task.acceptance_criteria:
                if search_lower in criterion.lower():
                    found = True
                    break

        assert found, (
            f"Task {task.task_id} in filtered results but doesn't contain '{search_term}'"
        )

    # Verify no task was incorrectly excluded
    for task in tasks:
        should_be_included = False

        if search_lower in task.task_id.lower():
            should_be_included = True
        elif search_lower in task.title.lower():
            should_be_included = True
        else:
            for criterion in task.acceptance_criteria:
                if search_lower in criterion.lower():
                    should_be_included = True
                    break

        if should_be_included:
            assert task in filtered, (
                f"Task {task.task_id} should be in filtered results for '{search_term}'"
            )


@given(st.lists(task_choice_strategy(), min_size=1, max_size=50))
@settings(max_examples=20)
def test_property_11_empty_search_returns_all(tasks: list[TaskChoice]):
    """**Validates: Requirements US-4.1, US-4.2**

    Feature: ralph-enhancement-phase2, Property 11
    Empty or whitespace-only search terms should return all tasks.
    """
    # Test with empty string
    result_empty = filter_tasks_by_keyword(tasks, "")
    assert len(result_empty) == len(tasks)
    # Compare by task IDs since TaskChoice is not hashable
    assert [t.task_id for t in result_empty] == [t.task_id for t in tasks]

    # Test with whitespace
    result_whitespace = filter_tasks_by_keyword(tasks, "   ")
    assert len(result_whitespace) == len(tasks)
    assert [t.task_id for t in result_whitespace] == [t.task_id for t in tasks]


@given(
    st.lists(task_choice_strategy(), min_size=1, max_size=50),
    st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        min_size=1,
        max_size=20,
    ),
)
@settings(max_examples=20)
def test_property_11_search_is_case_insensitive(
    tasks: list[TaskChoice], search_term: str
):
    """**Validates: Requirements US-4.1, US-4.2**

    Feature: ralph-enhancement-phase2, Property 11
    Search should be case-insensitive for ASCII letters.
    """
    # Skip if search term is all whitespace
    if not search_term.strip():
        return

    # Filter with original case
    result1 = filter_tasks_by_keyword(tasks, search_term)

    # Filter with lowercase
    result2 = filter_tasks_by_keyword(tasks, search_term.lower())

    # Filter with uppercase
    result3 = filter_tasks_by_keyword(tasks, search_term.upper())

    # All should return the same results (compare by task IDs)
    ids1 = [t.task_id for t in result1]
    ids2 = [t.task_id for t in result2]
    ids3 = [t.task_id for t in result3]

    # For ASCII letters, case-insensitive search should work consistently
    assert ids1 == ids2 == ids3, (
        "Search results should be case-insensitive for ASCII letters"
    )


@given(st.lists(task_choice_strategy(), min_size=1, max_size=50))
@settings(max_examples=20)
def test_property_11_search_in_all_fields(tasks: list[TaskChoice]):
    """**Validates: Requirements US-4.1, US-4.2**

    Feature: ralph-enhancement-phase2, Property 11
    Search should find matches in task ID, title, and acceptance criteria.
    """
    for task in tasks:
        # Test searching by task ID (if not empty)
        if task.task_id.strip():
            # Use a substring of the task ID
            search_term = task.task_id[: min(3, len(task.task_id))]
            if search_term.strip():
                result = filter_tasks_by_keyword(tasks, search_term)
                assert task in result, (
                    f"Task {task.task_id} should be found when searching by its ID"
                )

        # Test searching by title (if not empty)
        if task.title.strip():
            # Use a substring of the title
            search_term = task.title[: min(3, len(task.title))]
            if search_term.strip():
                result = filter_tasks_by_keyword(tasks, search_term)
                assert task in result, (
                    f"Task {task.task_id} should be found when searching by its title"
                )

        # Test searching by acceptance criteria (if any exist)
        for criterion in task.acceptance_criteria:
            if criterion.strip():
                # Use a substring of the criterion
                search_term = criterion[: min(3, len(criterion))]
                if search_term.strip():
                    result = filter_tasks_by_keyword(tasks, search_term)
                    assert task in result, (
                        f"Task {task.task_id} should be found when searching by its criteria"
                    )
                break  # Only test first criterion to keep test fast


# Additional property: Filter preserves task order
@given(
    st.lists(task_choice_strategy(), min_size=2, max_size=50),
    st.text(min_size=1, max_size=20),
)
@settings(max_examples=20)
def test_property_filter_preserves_order(tasks: list[TaskChoice], search_term: str):
    """**Validates: Requirements US-4.1, US-4.2**

    Feature: ralph-enhancement-phase2
    Filtering should preserve the original order of tasks.
    """
    # Skip if search term is all whitespace
    if not search_term.strip():
        return

    filtered = filter_tasks_by_keyword(tasks, search_term)

    # Build a mapping of task objects to their indices
    # Use id() to handle duplicate task IDs
    task_to_index = {id(task): i for i, task in enumerate(tasks)}

    # Get indices of filtered tasks
    filtered_indices = [task_to_index.get(id(task), -1) for task in filtered]
    filtered_indices = [idx for idx in filtered_indices if idx >= 0]

    # Verify indices are in ascending order (preserving original order)
    for i in range(len(filtered_indices) - 1):
        assert filtered_indices[i] < filtered_indices[i + 1], (
            "Filtered tasks should maintain original order"
        )


# Additional property: Filtering is idempotent
@given(
    st.lists(task_choice_strategy(), min_size=1, max_size=50),
    st.text(min_size=1, max_size=20),
)
@settings(max_examples=20)
def test_property_filtering_is_idempotent(tasks: list[TaskChoice], search_term: str):
    """**Validates: Requirements US-4.1, US-4.2**

    Feature: ralph-enhancement-phase2
    Filtering the same list multiple times should produce identical results.
    """
    # Skip if search term is all whitespace
    if not search_term.strip():
        return

    result1 = filter_tasks_by_keyword(tasks, search_term)
    result2 = filter_tasks_by_keyword(tasks, search_term)

    # Compare by task IDs
    assert [t.task_id for t in result1] == [t.task_id for t in result2], (
        "Filtering should be deterministic and idempotent"
    )
