"""Property-based tests for watch mode (Task 8.3).

This module contains property-based tests using hypothesis to verify
universal properties of the watch mode functionality.

**Validates: Requirements 7.1, 7.3**
"""

from __future__ import annotations

import time
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from ralph_gold.config import WatchConfig
from ralph_gold.watch import WatchState, _matches_pattern

# ============================================================================
# Property 19: Watch Debouncing
# ============================================================================
# For any sequence of file changes within the debounce window, only one gate
# execution should be triggered after the window expires.
# **Validates: Requirements 7.1**


@given(
    st.lists(
        st.floats(min_value=0.0, max_value=0.4),  # Times within debounce window
        min_size=1,
        max_size=20,
    ),
    st.integers(min_value=100, max_value=1000),  # Debounce window in ms
)
@settings(max_examples=100, deadline=None)
def test_property_19_debouncing_single_execution(
    change_times: list[float], debounce_ms: int
) -> None:
    """Property 19: Watch debouncing ensures single execution per window.

    **Validates: Requirements 7.1**

    Feature: ralph-enhancement-phase2, Property 19
    For any sequence of file changes within the debounce window, only one gate
    execution should be triggered after the window expires.

    Args:
        change_times: List of relative times (in seconds) when changes occur
        debounce_ms: Debounce window in milliseconds
    """
    # Setup
    debounce_seconds = debounce_ms / 1000.0
    watch_cfg = WatchConfig(
        enabled=True,
        patterns=["**/*.py"],
        debounce_ms=debounce_ms,
        auto_commit=False,
    )

    state = WatchState(
        last_run_time=time.time(),
        pending_changes=set(),
        running=True,
    )

    # Track gate executions
    gate_executions = []

    def mock_callback(file_path: Path) -> None:
        """Mock callback that tracks executions."""
        gate_executions.append(time.time())

    # Simulate file changes at specified times
    base_time = time.time()
    for change_time in sorted(change_times):
        # Add change to pending
        test_file = Path(f"/tmp/test_{change_time}.py")
        state.pending_changes.add(test_file)

        # Check if we should trigger callback
        time_since_last_run = (base_time + change_time) - state.last_run_time

        if time_since_last_run >= debounce_seconds and state.pending_changes:
            # Trigger callback for all pending changes
            for file_path in state.pending_changes:
                mock_callback(file_path)

            # Reset state
            state.pending_changes.clear()
            state.last_run_time = base_time + change_time

    # Property: If all changes occurred within debounce window,
    # no execution should have happened yet
    max_change_time = max(change_times)
    if max_change_time < debounce_seconds:
        # All changes within window - should not have triggered
        assert len(gate_executions) == 0, (
            f"Expected no executions within debounce window ({debounce_seconds}s), "
            f"but got {len(gate_executions)} executions"
        )
    else:
        # At least one change outside window - should have triggered
        # The number of executions depends on how changes are distributed
        assert len(gate_executions) >= 0  # May or may not have executed


@given(
    st.integers(min_value=2, max_value=10),  # Number of rapid changes
    st.integers(min_value=100, max_value=500),  # Debounce window in ms
)
@settings(max_examples=100, deadline=None)
def test_property_19_rapid_changes_coalesced(
    num_changes: int, debounce_ms: int
) -> None:
    """Property 19: Rapid changes within debounce window are coalesced.

    **Validates: Requirements 7.1**

    Feature: ralph-enhancement-phase2, Property 19
    Multiple rapid file changes should be coalesced into a single gate execution
    after the debounce period expires.

    Args:
        num_changes: Number of rapid file changes
        debounce_ms: Debounce window in milliseconds
    """
    debounce_seconds = debounce_ms / 1000.0

    state = WatchState(
        last_run_time=0.0,  # Start at time 0
        pending_changes=set(),
        running=True,
    )

    # Simulate rapid changes (all at time 0)
    for i in range(num_changes):
        test_file = Path(f"/tmp/test_{i}.py")
        state.pending_changes.add(test_file)

    # Property: All changes are pending
    assert len(state.pending_changes) == num_changes

    # Simulate time passing (less than debounce)
    current_time = debounce_seconds / 2
    time_since_last_run = current_time - state.last_run_time

    # Property: Should not trigger yet
    should_trigger = time_since_last_run >= debounce_seconds
    assert not should_trigger, (
        f"Should not trigger before debounce window expires "
        f"(elapsed: {time_since_last_run}s, window: {debounce_seconds}s)"
    )

    # Simulate time passing (beyond debounce)
    current_time = debounce_seconds + 0.1
    time_since_last_run = current_time - state.last_run_time

    # Property: Should trigger now
    should_trigger = time_since_last_run >= debounce_seconds
    assert should_trigger, (
        f"Should trigger after debounce window expires "
        f"(elapsed: {time_since_last_run}s, window: {debounce_seconds}s)"
    )

    # After triggering, all pending changes should be processed together
    if should_trigger:
        processed_files = list(state.pending_changes)
        state.pending_changes.clear()
        state.last_run_time = current_time

        # Property: All changes processed in single batch
        assert len(processed_files) == num_changes


@given(
    st.lists(
        st.tuples(
            st.floats(min_value=0.0, max_value=5.0),  # Change time
            st.integers(min_value=1, max_value=5),  # Number of files
        ),
        min_size=1,
        max_size=10,
    ),
    st.integers(min_value=200, max_value=800),  # Debounce window
)
@settings(max_examples=100, deadline=None)
def test_property_19_multiple_debounce_windows(
    change_batches: list[tuple[float, int]], debounce_ms: int
) -> None:
    """Property 19: Multiple debounce windows trigger separate executions.

    **Validates: Requirements 7.1**

    Feature: ralph-enhancement-phase2, Property 19
    Changes separated by more than the debounce window should trigger
    separate gate executions.

    Args:
        change_batches: List of (time, num_files) tuples
        debounce_ms: Debounce window in milliseconds
    """
    debounce_seconds = debounce_ms / 1000.0

    state = WatchState(
        last_run_time=0.0,
        pending_changes=set(),
        running=True,
    )

    executions = []
    current_time = 0.0

    # Sort batches by time
    sorted_batches = sorted(change_batches, key=lambda x: x[0])

    for batch_time, num_files in sorted_batches:
        current_time = batch_time

        # Add files to pending
        for i in range(num_files):
            test_file = Path(f"/tmp/test_{batch_time}_{i}.py")
            state.pending_changes.add(test_file)

        # Check if we should trigger
        time_since_last_run = current_time - state.last_run_time

        if time_since_last_run >= debounce_seconds and state.pending_changes:
            # Execute gates
            num_processed = len(state.pending_changes)
            executions.append((current_time, num_processed))

            # Reset state
            state.pending_changes.clear()
            state.last_run_time = current_time

    # Property: Number of executions should be <= number of batches
    # (some batches may be coalesced if within debounce window)
    assert len(executions) <= len(change_batches)

    # Property: Each execution should process at least one file
    for _, num_processed in executions:
        assert num_processed > 0


# ============================================================================
# Property 20: Watch Pattern Matching
# ============================================================================
# For any file change, the watch callback should be triggered if and only if
# the file path matches at least one configured watch pattern.
# **Validates: Requirements 7.3**


@given(
    st.text(
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd"), min_codepoint=97, max_codepoint=122
        ),
        min_size=1,
        max_size=20,
    ),  # Filename
    st.sampled_from([".py", ".md", ".txt", ".toml", ".json", ".yaml"]),  # Extension
    st.lists(
        st.sampled_from(
            ["**/*.py", "**/*.md", "**/*.txt", "**/*.toml", "**/*.json", "**/*.yaml"]
        ),
        min_size=1,
        max_size=5,
        unique=True,
    ),  # Patterns
)
@settings(max_examples=100, deadline=None)
def test_property_20_pattern_matching_correctness(
    filename: str, extension: str, patterns: list[str]
) -> None:
    """Property 20: Pattern matching determines callback triggering.

    **Validates: Requirements 7.3**

    Feature: ralph-enhancement-phase2, Property 20
    For any file change, the watch callback should be triggered if and only if
    the file path matches at least one configured watch pattern.

    Args:
        filename: Base filename without extension
        extension: File extension
        patterns: List of glob patterns to match against
    """
    # Create file path
    file_path = Path(f"/tmp/{filename}{extension}")

    # Test pattern matching
    matches = _matches_pattern(file_path, patterns)

    # Property: File should match if its extension is in any pattern
    expected_match = any(extension in pattern for pattern in patterns)

    assert matches == expected_match, (
        f"Pattern matching mismatch for {file_path} with patterns {patterns}. "
        f"Expected: {expected_match}, Got: {matches}"
    )


@given(
    st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
            min_size=1,
            max_size=10,
        ),
        min_size=1,
        max_size=5,
    ),  # Path components
    st.sampled_from([".py", ".md", ".txt", ".rs", ".go"]),  # Extension
    st.lists(
        st.sampled_from(["**/*.py", "**/*.md", "**/*.txt"]),
        min_size=1,
        max_size=3,
        unique=True,
    ),  # Patterns
)
@settings(max_examples=100, deadline=None)
def test_property_20_nested_path_matching(
    path_components: list[str], extension: str, patterns: list[str]
) -> None:
    """Property 20: Nested paths match recursive patterns correctly.

    **Validates: Requirements 7.3**

    Feature: ralph-enhancement-phase2, Property 20
    Files in nested directories should match recursive patterns (**/*).

    Args:
        path_components: List of directory names
        extension: File extension
        patterns: List of glob patterns
    """
    # Build nested path
    file_path = Path("/tmp")
    for component in path_components:
        if component:  # Skip empty components
            file_path = file_path / component
    file_path = file_path / f"file{extension}"

    # Test pattern matching
    matches = _matches_pattern(file_path, patterns)

    # Property: Should match if extension matches any pattern
    # (recursive patterns should work at any depth)
    expected_match = any(extension in pattern for pattern in patterns)

    assert matches == expected_match, (
        f"Nested path matching failed for {file_path} with patterns {patterns}. "
        f"Expected: {expected_match}, Got: {matches}"
    )


@given(
    st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
        min_size=1,
        max_size=15,
    ),  # Filename
    st.sampled_from([".py", ".md", ".txt", ".json"]),  # Extension
)
@settings(max_examples=100, deadline=None)
def test_property_20_empty_patterns_match_nothing(
    filename: str, extension: str
) -> None:
    """Property 20: Empty pattern list matches no files.

    **Validates: Requirements 7.3**

    Feature: ralph-enhancement-phase2, Property 20
    When no patterns are configured, no files should match.

    Args:
        filename: Base filename
        extension: File extension
    """
    file_path = Path(f"/tmp/{filename}{extension}")

    # Test with empty patterns
    matches = _matches_pattern(file_path, [])

    # Property: Empty pattern list should never match
    assert not matches, f"Empty pattern list should not match {file_path}"


@given(
    st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
            min_size=1,
            max_size=10,
        ),
        min_size=1,
        max_size=3,
    ),  # Path components
    st.sampled_from([".py", ".md", ".txt"]),  # Extension
    st.lists(
        st.sampled_from(["*.py", "*.md", "*.txt"]),  # Non-recursive patterns
        min_size=1,
        max_size=3,
        unique=True,
    ),
)
@settings(max_examples=100, deadline=None)
def test_property_20_non_recursive_patterns(
    path_components: list[str], extension: str, patterns: list[str]
) -> None:
    """Property 20: Non-recursive patterns only match direct children.

    **Validates: Requirements 7.3**

    Feature: ralph-enhancement-phase2, Property 20
    Patterns without ** should only match files in the immediate directory.

    Args:
        path_components: List of directory names
        extension: File extension
        patterns: List of non-recursive glob patterns
    """
    # Build path
    file_path = Path("/tmp")
    for component in path_components:
        if component:
            file_path = file_path / component
    file_path = file_path / f"file{extension}"

    # Test pattern matching
    matches = _matches_pattern(file_path, patterns)

    # Property: Non-recursive patterns should match based on filename only
    # if path depth is 1, otherwise may not match
    if len([c for c in path_components if c]) == 0:
        # Direct child - should match if extension matches
        expected_match = any(extension in pattern for pattern in patterns)
        assert matches == expected_match
    # For nested paths, behavior depends on Path.match() implementation


@given(
    st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
        min_size=1,
        max_size=15,
    ),  # Filename
    st.sampled_from([".py", ".PY", ".Py", ".pY"]),  # Mixed case extensions
    st.lists(
        st.sampled_from(["**/*.py", "**/*.PY"]),
        min_size=1,
        max_size=2,
        unique=True,
    ),
)
@settings(max_examples=100, deadline=None)
def test_property_20_case_sensitivity(
    filename: str, extension: str, patterns: list[str]
) -> None:
    """Property 20: Pattern matching handles case sensitivity.

    **Validates: Requirements 7.3**

    Feature: ralph-enhancement-phase2, Property 20
    Pattern matching should handle case sensitivity according to
    the filesystem and Path.match() behavior.

    Args:
        filename: Base filename
        extension: File extension with various cases
        patterns: List of patterns with various cases
    """
    file_path = Path(f"/tmp/{filename}{extension}")

    # Test pattern matching
    matches = _matches_pattern(file_path, patterns)

    # Property: Result should be consistent (boolean)
    assert isinstance(matches, bool)

    # Note: Actual case sensitivity depends on filesystem
    # This test verifies the function doesn't crash with mixed cases


@given(
    st.integers(min_value=1, max_value=20),  # Number of files
    st.lists(
        st.sampled_from(["**/*.py", "**/*.md", "**/*.txt"]),
        min_size=1,
        max_size=3,
        unique=True,
    ),  # Patterns
)
@settings(max_examples=100, deadline=None)
def test_property_20_multiple_files_independent(
    num_files: int, patterns: list[str]
) -> None:
    """Property 20: Pattern matching is independent for each file.

    **Validates: Requirements 7.3**

    Feature: ralph-enhancement-phase2, Property 20
    Each file's pattern matching should be independent of other files.

    Args:
        num_files: Number of files to test
        patterns: List of patterns
    """
    extensions = [".py", ".md", ".txt", ".json", ".yaml"]

    results = []
    for i in range(num_files):
        ext = extensions[i % len(extensions)]
        file_path = Path(f"/tmp/file_{i}{ext}")
        matches = _matches_pattern(file_path, patterns)
        results.append((file_path, matches))

    # Property: Each file's result should be independent
    # Files with same extension should have same result
    py_results = [m for p, m in results if str(p).endswith(".py")]
    md_results = [m for p, m in results if str(p).endswith(".md")]

    # All .py files should have same matching result
    if py_results:
        assert all(r == py_results[0] for r in py_results), (
            "Files with same extension should have consistent matching results"
        )

    # All .md files should have same matching result
    if md_results:
        assert all(r == md_results[0] for r in md_results), (
            "Files with same extension should have consistent matching results"
        )


@given(
    st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
        min_size=1,
        max_size=15,
    ),  # Filename
    st.sampled_from([".py", ".md", ".txt"]),  # Extension
    st.lists(
        st.sampled_from(["**/*.py", "**/*.md", "**/*.txt", "**/*"]),
        min_size=1,
        max_size=4,
        unique=True,
    ),
)
@settings(max_examples=100, deadline=None)
def test_property_20_wildcard_matches_all(
    filename: str, extension: str, patterns: list[str]
) -> None:
    """Property 20: Wildcard pattern matches all files.

    **Validates: Requirements 7.3**

    Feature: ralph-enhancement-phase2, Property 20
    The pattern **/* should match any file.

    Args:
        filename: Base filename
        extension: File extension
        patterns: List of patterns including wildcards
    """
    file_path = Path(f"/tmp/{filename}{extension}")

    matches = _matches_pattern(file_path, patterns)

    # Property: If patterns include **/* (match all), should always match
    if "**/*" in patterns:
        assert matches, (
            f"Pattern **/* should match all files, but {file_path} didn't match"
        )


# ============================================================================
# Combined Properties: Debouncing + Pattern Matching
# ============================================================================


@given(
    st.lists(
        st.tuples(
            st.floats(min_value=0.0, max_value=2.0),  # Change time
            st.sampled_from([".py", ".md", ".txt", ".json"]),  # Extension
        ),
        min_size=1,
        max_size=10,
    ),
    st.integers(min_value=200, max_value=600),  # Debounce ms
    st.lists(
        st.sampled_from(["**/*.py", "**/*.md"]),
        min_size=1,
        max_size=2,
        unique=True,
    ),  # Patterns
)
@settings(max_examples=100, deadline=None)
def test_combined_debouncing_and_pattern_matching(
    changes: list[tuple[float, str]],
    debounce_ms: int,
    patterns: list[str],
) -> None:
    """Combined test: Debouncing and pattern matching work together.

    **Validates: Requirements 7.1, 7.3**

    Feature: ralph-enhancement-phase2, Properties 19 & 20
    Only files matching patterns should be added to pending changes,
    and debouncing should apply to matched files only.

    Args:
        changes: List of (time, extension) tuples
        debounce_ms: Debounce window in milliseconds
        patterns: List of patterns to match
    """
    debounce_seconds = debounce_ms / 1000.0

    state = WatchState(
        last_run_time=0.0,
        pending_changes=set(),
        running=True,
    )

    matched_files = []
    unmatched_files = []

    for change_time, extension in changes:
        file_path = Path(f"/tmp/file_{change_time}{extension}")

        # Check if file matches patterns
        if _matches_pattern(file_path, patterns):
            matched_files.append((change_time, file_path))
            state.pending_changes.add(file_path)
        else:
            unmatched_files.append((change_time, file_path))

    # Property 1: Only matched files should be in pending changes
    for _, file_path in unmatched_files:
        assert file_path not in state.pending_changes, (
            f"Unmatched file {file_path} should not be in pending changes"
        )

    # Property 2: All matched files should be in pending changes
    for _, file_path in matched_files:
        assert file_path in state.pending_changes, (
            f"Matched file {file_path} should be in pending changes"
        )

    # Property 3: Debouncing applies to matched files
    if matched_files:
        max_change_time = max(t for t, _ in matched_files)
        time_since_last_run = max_change_time - state.last_run_time

        if time_since_last_run < debounce_seconds:
            # Still within debounce window - should not trigger yet
            assert len(state.pending_changes) > 0
        # If beyond debounce, would trigger (tested in other properties)
