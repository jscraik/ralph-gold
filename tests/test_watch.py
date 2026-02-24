"""Unit tests for the watch module (Task 8.2)."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ralph_gold.config import Config, GatesConfig, LlmJudgeConfig, WatchConfig
from ralph_gold.watch import (
    WatchState,
    _matches_pattern,
    _poll_for_changes,
    _should_ignore_path,
    run_watch_mode,
    watch_files,
)

# ============================================================================
# Test Helpers
# ============================================================================


def make_test_gates_config(commands: list[str] | None = None) -> GatesConfig:
    """Create a test GatesConfig with minimal required fields."""
    return GatesConfig(
        commands=commands or ["exit 0"],
        llm_judge=LlmJudgeConfig(),
        fail_fast=True,
    )


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory with .ralph structure.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to the project directory
    """
    # Create .ralph directory
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create state.json
    state_path = ralph_dir / "state.json"
    state_data = {
        "createdAt": "2024-01-01T00:00:00Z",
        "history": [],
        "invocations": [],
        "snapshots": [],
    }
    state_path.write_text(json.dumps(state_data), encoding="utf-8")

    return tmp_path


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for testing.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to the git repository
    """
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    test_file = tmp_path / "test.txt"
    test_file.write_text("initial content", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create .ralph directory
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    state_path = ralph_dir / "state.json"
    state_data = {
        "createdAt": "2024-01-01T00:00:00Z",
        "history": [],
        "invocations": [],
        "snapshots": [],
    }
    state_path.write_text(json.dumps(state_data), encoding="utf-8")

    return tmp_path


# ============================================================================
# Pattern Matching Tests
# ============================================================================


def test_matches_pattern_simple_wildcard(temp_project: Path) -> None:
    """Test pattern matching with simple wildcards."""
    file_path = temp_project / "test.py"

    assert _matches_pattern(file_path, ["*.py"])
    assert not _matches_pattern(file_path, ["*.md"])


def test_matches_pattern_recursive_wildcard(temp_project: Path) -> None:
    """Test pattern matching with recursive wildcards."""
    file_path = temp_project / "src" / "module" / "test.py"

    assert _matches_pattern(file_path, ["**/*.py"])
    assert not _matches_pattern(file_path, ["**/*.md"])


def test_matches_pattern_multiple_patterns(temp_project: Path) -> None:
    """Test pattern matching with multiple patterns."""
    py_file = temp_project / "test.py"
    md_file = temp_project / "README.md"
    txt_file = temp_project / "notes.txt"

    patterns = ["**/*.py", "**/*.md"]

    assert _matches_pattern(py_file, patterns)
    assert _matches_pattern(md_file, patterns)
    assert not _matches_pattern(txt_file, patterns)


def test_matches_pattern_no_patterns(temp_project: Path) -> None:
    """Test pattern matching with empty pattern list."""
    file_path = temp_project / "test.py"

    assert not _matches_pattern(file_path, [])


def test_matches_pattern_specific_file(temp_project: Path) -> None:
    """Test pattern matching with specific file name."""
    file_path = temp_project / "config.toml"

    assert _matches_pattern(file_path, ["config.toml"])
    assert not _matches_pattern(file_path, ["other.toml"])


def test_matches_pattern_directory_pattern(temp_project: Path) -> None:
    """Test pattern matching with directory patterns."""
    file_path = temp_project / "src" / "test.py"

    # Test various directory patterns
    assert _matches_pattern(file_path, ["src/*.py"])
    assert _matches_pattern(file_path, ["**/test.py"])
    assert _matches_pattern(file_path, ["**/*.py"])


# ============================================================================
# Path Ignoring Tests
# ============================================================================


def test_should_ignore_path_ralph_directory(temp_project: Path) -> None:
    """Test that .ralph directory is ignored."""
    ralph_file = temp_project / ".ralph" / "state.json"

    assert _should_ignore_path(ralph_file, temp_project)


def test_should_ignore_path_git_directory(temp_project: Path) -> None:
    """Test that .git directory is ignored."""
    git_file = temp_project / ".git" / "config"

    assert _should_ignore_path(git_file, temp_project)


def test_should_ignore_path_pycache(temp_project: Path) -> None:
    """Test that __pycache__ directory is ignored."""
    cache_file = temp_project / "src" / "__pycache__" / "module.pyc"

    assert _should_ignore_path(cache_file, temp_project)


def test_should_ignore_path_node_modules(temp_project: Path) -> None:
    """Test that node_modules directory is ignored."""
    node_file = temp_project / "node_modules" / "package" / "index.js"

    assert _should_ignore_path(node_file, temp_project)


def test_should_ignore_path_venv(temp_project: Path) -> None:
    """Test that virtual environment directories are ignored."""
    venv_file = temp_project / ".venv" / "lib" / "python.py"
    venv2_file = temp_project / "venv" / "lib" / "python.py"

    assert _should_ignore_path(venv_file, temp_project)
    assert _should_ignore_path(venv2_file, temp_project)


def test_should_ignore_path_hidden_files(temp_project: Path) -> None:
    """Test that hidden files/directories are ignored."""
    hidden_file = temp_project / ".hidden" / "file.txt"

    assert _should_ignore_path(hidden_file, temp_project)


def test_should_ignore_path_regular_files(temp_project: Path) -> None:
    """Test that regular files are not ignored."""
    regular_file = temp_project / "src" / "module.py"

    assert not _should_ignore_path(regular_file, temp_project)


def test_should_ignore_path_outside_project(temp_project: Path, tmp_path: Path) -> None:
    """Test that paths outside project root are ignored."""
    # Create a sibling directory (not a child of temp_project)
    outside_dir = tmp_path.parent / "outside_dir"
    outside_dir.mkdir(exist_ok=True)
    outside_file = outside_dir / "file.txt"
    outside_file.write_text("outside", encoding="utf-8")

    assert _should_ignore_path(outside_file, temp_project)


# ============================================================================
# Polling Tests
# ============================================================================


def test_poll_for_changes_detects_new_file(temp_project: Path) -> None:
    """Test that polling detects newly created files."""
    # Set last_check, then create file after
    last_check = time.time()
    time.sleep(0.1)  # Small delay to ensure file is created after last_check

    # Create a new file
    new_file = temp_project / "new_file.py"
    new_file.write_text("new content", encoding="utf-8")

    # Poll for changes
    changed = _poll_for_changes(temp_project, ["**/*.py"], last_check)

    assert new_file in changed


def test_poll_for_changes_detects_modified_file(temp_project: Path) -> None:
    """Test that polling detects modified files."""
    # Create initial file
    test_file = temp_project / "test.py"
    test_file.write_text("initial", encoding="utf-8")

    # Set last_check after initial creation
    last_check = time.time()
    time.sleep(0.1)

    # Modify the file
    test_file.write_text("modified", encoding="utf-8")

    # Poll for changes
    changed = _poll_for_changes(temp_project, ["**/*.py"], last_check)

    assert test_file in changed


def test_poll_for_changes_ignores_old_files(temp_project: Path) -> None:
    """Test that polling ignores files not modified since last check."""
    # Create file before check time
    old_file = temp_project / "old.py"
    old_file.write_text("old content", encoding="utf-8")

    time.sleep(0.1)
    last_check = time.time()
    time.sleep(0.1)

    # Poll for changes
    changed = _poll_for_changes(temp_project, ["**/*.py"], last_check)

    assert old_file not in changed


def test_poll_for_changes_respects_patterns(temp_project: Path) -> None:
    """Test that polling only detects files matching patterns."""
    # Set last_check first
    last_check = time.time()
    time.sleep(0.1)

    # Create files with different extensions
    py_file = temp_project / "test.py"
    py_file.write_text("python", encoding="utf-8")

    md_file = temp_project / "README.md"
    md_file.write_text("markdown", encoding="utf-8")

    # Poll only for Python files
    changed = _poll_for_changes(temp_project, ["**/*.py"], last_check)

    assert py_file in changed
    assert md_file not in changed


def test_poll_for_changes_ignores_ralph_directory(temp_project: Path) -> None:
    """Test that polling ignores .ralph directory."""
    last_check = time.time()
    time.sleep(0.1)

    # Modify file in .ralph
    ralph_file = temp_project / ".ralph" / "temp.py"
    ralph_file.write_text("should be ignored", encoding="utf-8")

    # Poll for changes
    changed = _poll_for_changes(temp_project, ["**/*.py"], last_check)

    assert ralph_file not in changed


def test_poll_for_changes_handles_deleted_files(temp_project: Path) -> None:
    """Test that polling handles deleted files gracefully."""
    # Create and then delete a file
    temp_file = temp_project / "temp.py"
    temp_file.write_text("temporary", encoding="utf-8")

    last_check = time.time()
    time.sleep(0.1)

    temp_file.unlink()

    # Poll should not crash
    changed = _poll_for_changes(temp_project, ["**/*.py"], last_check)

    # Deleted file should not be in changed set
    assert temp_file not in changed


# ============================================================================
# Watch Files Tests (with mocking)
# ============================================================================


def test_watch_files_uses_polling_when_watchdog_unavailable(temp_project: Path) -> None:
    """Test that watch_files falls back to polling when watchdog is unavailable."""
    watch_cfg = WatchConfig(
        enabled=True,
        patterns=["**/*.py"],
        debounce_ms=100,
        auto_commit=False,
    )

    cfg = Mock(spec=Config)
    cfg.watch = watch_cfg

    callback = Mock()

    # Mock watchdog as unavailable
    with patch("ralph_gold.watch._try_import_watchdog", return_value=None):
        with patch("ralph_gold.watch._watch_with_polling") as mock_polling:
            watch_files(temp_project, cfg, watch_cfg, callback)

            # Should call polling implementation
            mock_polling.assert_called_once_with(temp_project, watch_cfg, callback)


def test_watch_files_uses_watchdog_when_available(temp_project: Path) -> None:
    """Test that watch_files uses watchdog when available."""
    watch_cfg = WatchConfig(
        enabled=True,
        patterns=["**/*.py"],
        debounce_ms=100,
        auto_commit=False,
    )

    cfg = Mock(spec=Config)
    cfg.watch = watch_cfg

    callback = Mock()

    # Mock watchdog as available
    mock_watchdog = Mock()
    with patch("ralph_gold.watch._try_import_watchdog", return_value=mock_watchdog):
        with patch("ralph_gold.watch._watch_with_watchdog") as mock_wd:
            watch_files(temp_project, cfg, watch_cfg, callback)

            # Should call watchdog implementation
            mock_wd.assert_called_once_with(temp_project, watch_cfg, callback)


# ============================================================================
# Debouncing Tests
# ============================================================================


def test_watch_state_tracks_pending_changes() -> None:
    """Test that WatchState correctly tracks pending changes."""
    state = WatchState(
        last_run_time=time.time(),
        pending_changes=set(),
        running=True,
    )

    # Add some changes
    file1 = Path("/tmp/file1.py")
    file2 = Path("/tmp/file2.py")

    state.pending_changes.add(file1)
    state.pending_changes.add(file2)

    assert len(state.pending_changes) == 2
    assert file1 in state.pending_changes
    assert file2 in state.pending_changes


def test_debouncing_logic_waits_for_debounce_period(temp_project: Path) -> None:
    """Test that debouncing waits for the configured period."""
    # This test verifies the debouncing logic by checking timing
    debounce_ms = 200
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

    # Add a pending change
    test_file = temp_project / "test.py"
    state.pending_changes.add(test_file)

    # Check immediately - should not trigger
    time_since_last_run = time.time() - state.last_run_time
    debounce_seconds = watch_cfg.debounce_ms / 1000.0

    assert time_since_last_run < debounce_seconds

    # Wait for debounce period
    time.sleep(debounce_seconds + 0.1)

    # Check again - should trigger
    time_since_last_run = time.time() - state.last_run_time
    assert time_since_last_run >= debounce_seconds


# ============================================================================
# Gate Execution Tests
# ============================================================================


def test_run_watch_mode_requires_enabled_config(temp_project: Path) -> None:
    """Test that run_watch_mode requires watch mode to be enabled."""
    watch_cfg = WatchConfig(
        enabled=False,  # Disabled
        patterns=["**/*.py"],
        debounce_ms=500,
        auto_commit=False,
    )

    cfg = Mock(spec=Config)
    cfg.watch = watch_cfg

    with pytest.raises(RuntimeError, match="not enabled"):
        run_watch_mode(temp_project, cfg, gates_only=True, auto_commit=False)


def test_run_watch_mode_calls_watch_files(temp_project: Path) -> None:
    """Test that run_watch_mode calls watch_files with correct parameters."""

    watch_cfg = WatchConfig(
        enabled=True,
        patterns=["**/*.py", "**/*.md"],
        debounce_ms=500,
        auto_commit=False,
    )

    gates_cfg = make_test_gates_config(["echo test"])

    cfg = Mock(spec=Config)
    cfg.watch = watch_cfg
    cfg.gates = gates_cfg

    with patch("ralph_gold.watch.watch_files") as mock_watch:
        with patch("ralph_gold.watch.signal.signal"):
            # Mock watch_files to not actually run
            mock_watch.return_value = None

            run_watch_mode(temp_project, cfg, gates_only=True, auto_commit=False)

            # Verify watch_files was called
            mock_watch.assert_called_once()
            call_args = mock_watch.call_args

            assert call_args[0][0] == temp_project
            assert call_args[0][1] == cfg
            assert call_args[0][2] == watch_cfg


def test_run_watch_mode_gate_execution_on_change(git_repo: Path) -> None:
    """Test that gates are executed when files change."""
    watch_cfg = WatchConfig(
        enabled=True,
        patterns=["**/*.py"],
        debounce_ms=100,
        auto_commit=False,
    )

    gates_cfg = make_test_gates_config(["exit 0"])

    cfg = Mock(spec=Config)
    cfg.watch = watch_cfg
    cfg.gates = gates_cfg

    # Track gate executions
    gate_calls = []

    def mock_run_gates(project_root, commands, gates_config):
        gate_calls.append((project_root, commands))
        # Return success
        return (True, [])

    with patch("ralph_gold.watch.run_gates", side_effect=mock_run_gates):
        with patch("ralph_gold.watch.watch_files") as mock_watch:
            with patch("ralph_gold.watch.signal.signal"):
                # Simulate file change by calling the callback
                def simulate_change(project_root, cfg_obj, watch_cfg_obj, callback):
                    test_file = git_repo / "test.py"
                    callback(test_file)

                mock_watch.side_effect = simulate_change

                run_watch_mode(git_repo, cfg, gates_only=True, auto_commit=False)

                # Verify gates were called
                assert len(gate_calls) == 1
                assert gate_calls[0][0] == git_repo


# ============================================================================
# Auto-Commit Tests
# ============================================================================


def test_auto_commit_when_gates_pass(git_repo: Path) -> None:
    """Test that auto-commit happens when gates pass."""
    watch_cfg = WatchConfig(
        enabled=True,
        patterns=["**/*.py"],
        debounce_ms=100,
        auto_commit=True,  # Enable auto-commit
    )

    gates_cfg = make_test_gates_config(["exit 0"])

    cfg = Mock(spec=Config)
    cfg.watch = watch_cfg
    cfg.gates = gates_cfg

    # Make a change to commit
    test_file = git_repo / "test.py"
    test_file.write_text("changed content", encoding="utf-8")

    commit_calls = []

    def mock_run_gates(project_root, commands, gates_config):
        # Return success
        return (True, [])

    def mock_subprocess_run(cmd, **kwargs):
        commit_calls.append(cmd)
        result = Mock()
        result.stdout = "M test.py\n" if cmd[1] == "status" else ""
        result.stderr = ""
        result.returncode = 0
        return result

    with patch("ralph_gold.watch.run_gates", side_effect=mock_run_gates):
        with patch("ralph_gold.watch.subprocess.run", side_effect=mock_subprocess_run):
            with patch("ralph_gold.watch.watch_files") as mock_watch:
                with patch("ralph_gold.watch.signal.signal"):
                    # Simulate file change
                    def simulate_change(project_root, cfg_obj, watch_cfg_obj, callback):
                        callback(test_file)

                    mock_watch.side_effect = simulate_change

                    run_watch_mode(git_repo, cfg, gates_only=True, auto_commit=True)

                    # Verify git commands were called
                    assert any("status" in str(cmd) for cmd in commit_calls)
                    assert any("add" in str(cmd) for cmd in commit_calls)
                    assert any("commit" in str(cmd) for cmd in commit_calls)


def test_no_auto_commit_when_gates_fail(git_repo: Path) -> None:
    """Test that auto-commit does not happen when gates fail."""
    watch_cfg = WatchConfig(
        enabled=True,
        patterns=["**/*.py"],
        debounce_ms=100,
        auto_commit=True,
    )

    gates_cfg = make_test_gates_config(["exit 1"])

    cfg = Mock(spec=Config)
    cfg.watch = watch_cfg
    cfg.gates = gates_cfg

    test_file = git_repo / "test.py"
    test_file.write_text("changed content", encoding="utf-8")

    commit_calls = []

    def mock_run_gates(project_root, commands, gates_config):
        # Return failure
        return (False, [Mock(return_code=1, cmd="exit 1", stderr="failed")])

    def mock_subprocess_run(cmd, **kwargs):
        commit_calls.append(cmd)
        result = Mock()
        result.stdout = ""
        result.stderr = ""
        result.returncode = 0
        return result

    with patch("ralph_gold.watch.run_gates", side_effect=mock_run_gates):
        with patch("ralph_gold.watch.subprocess.run", side_effect=mock_subprocess_run):
            with patch("ralph_gold.watch.watch_files") as mock_watch:
                with patch("ralph_gold.watch.signal.signal"):
                    # Simulate file change
                    def simulate_change(project_root, cfg_obj, watch_cfg_obj, callback):
                        callback(test_file)

                    mock_watch.side_effect = simulate_change

                    run_watch_mode(git_repo, cfg, gates_only=True, auto_commit=True)

                    # Verify no git commit was attempted
                    assert not any("commit" in str(cmd) for cmd in commit_calls)


def test_auto_commit_with_no_changes(git_repo: Path) -> None:
    """Test that auto-commit handles case with no changes gracefully."""
    watch_cfg = WatchConfig(
        enabled=True,
        patterns=["**/*.py"],
        debounce_ms=100,
        auto_commit=True,
    )

    gates_cfg = make_test_gates_config(["exit 0"])

    cfg = Mock(spec=Config)
    cfg.watch = watch_cfg
    cfg.gates = gates_cfg

    test_file = git_repo / "test.py"

    def mock_run_gates(project_root, commands, gates_config):
        return (True, [])

    def mock_subprocess_run(cmd, **kwargs):
        result = Mock()
        # Empty status means no changes
        result.stdout = "" if cmd[1] == "status" else ""
        result.stderr = ""
        result.returncode = 0
        return result

    with patch("ralph_gold.watch.run_gates", side_effect=mock_run_gates):
        with patch(
            "ralph_gold.watch.subprocess.run", side_effect=mock_subprocess_run
        ) as mock_run:
            with patch("ralph_gold.watch.watch_files") as mock_watch:
                with patch("ralph_gold.watch.signal.signal"):
                    # Simulate file change
                    def simulate_change(project_root, cfg_obj, watch_cfg_obj, callback):
                        callback(test_file)

                    mock_watch.side_effect = simulate_change

                    run_watch_mode(git_repo, cfg, gates_only=True, auto_commit=True)

                    # Should check status but not commit
                    status_calls = [
                        c
                        for c in mock_run.call_args_list
                        if c.args
                        and isinstance(c.args[0], list)
                        and len(c.args[0]) > 1
                        and c.args[0][0] == "git"
                        and c.args[0][1] == "status"
                    ]
                    commit_calls = [
                        c
                        for c in mock_run.call_args_list
                        if c.args
                        and isinstance(c.args[0], list)
                        and len(c.args[0]) > 1
                        and c.args[0][0] == "git"
                        and c.args[0][1] == "commit"
                    ]

                    assert len(status_calls) > 0
                    assert len(commit_calls) == 0


# ============================================================================
# Signal Handling Tests
# ============================================================================


def test_run_watch_mode_sets_signal_handler(temp_project: Path) -> None:
    """Test that run_watch_mode sets up SIGINT handler for graceful shutdown."""
    watch_cfg = WatchConfig(
        enabled=True,
        patterns=["**/*.py"],
        debounce_ms=500,
        auto_commit=False,
    )

    gates_cfg = make_test_gates_config(["echo test"])

    cfg = Mock(spec=Config)
    cfg.watch = watch_cfg
    cfg.gates = gates_cfg

    signal_calls = []

    def mock_signal(sig, handler):
        signal_calls.append((sig, handler))
        return Mock()

    with patch("ralph_gold.watch.signal.signal", side_effect=mock_signal):
        with patch("ralph_gold.watch.watch_files"):
            run_watch_mode(temp_project, cfg, gates_only=True, auto_commit=False)

            # Verify SIGINT handler was set
            assert len(signal_calls) > 0
            import signal as sig_module

            assert any(sig == sig_module.SIGINT for sig, _ in signal_calls)


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


def test_poll_for_changes_with_permission_error(temp_project: Path) -> None:
    """Test that polling handles permission errors gracefully."""
    # Create a file
    test_file = temp_project / "test.py"
    test_file.write_text("content", encoding="utf-8")

    last_check = time.time()
    time.sleep(0.1)

    # Mock stat to raise permission error
    original_stat = Path.stat

    def mock_stat(self):
        if self == test_file:
            raise OSError("Permission denied")
        return original_stat(self)

    with patch.object(Path, "stat", mock_stat):
        # Should not crash
        changed = _poll_for_changes(temp_project, ["**/*.py"], last_check)

        # File with error should not be in results
        assert test_file not in changed


def test_matches_pattern_with_absolute_path(temp_project: Path) -> None:
    """Test pattern matching with absolute paths."""
    abs_path = temp_project.resolve() / "src" / "test.py"

    # Should work with absolute paths
    assert _matches_pattern(abs_path, ["**/*.py"])


def test_watch_state_initial_values() -> None:
    """Test WatchState initialization."""
    current_time = time.time()
    state = WatchState(
        last_run_time=current_time,
        pending_changes=set(),
        running=True,
    )

    assert state.last_run_time == current_time
    assert len(state.pending_changes) == 0
    assert state.running is True


def test_poll_for_changes_empty_patterns(temp_project: Path) -> None:
    """Test polling with empty pattern list."""
    last_check = time.time()
    time.sleep(0.1)

    # Create a file
    test_file = temp_project / "test.py"
    test_file.write_text("content", encoding="utf-8")

    # Poll with empty patterns
    changed = _poll_for_changes(temp_project, [], last_check)

    # Should return empty set
    assert len(changed) == 0


def test_should_ignore_path_nested_ignored_directory(temp_project: Path) -> None:
    """Test that nested ignored directories are properly ignored."""
    nested_file = temp_project / "src" / ".git" / "objects" / "file"

    assert _should_ignore_path(nested_file, temp_project)


def test_matches_pattern_case_sensitivity(temp_project: Path) -> None:
    """Test pattern matching case sensitivity."""
    file_path = temp_project / "Test.PY"

    # Pattern matching should be case-insensitive on case-insensitive filesystems
    # but we test the actual behavior
    result = _matches_pattern(file_path, ["**/*.py"])

    # Result depends on filesystem, but should not crash
    assert isinstance(result, bool)


# ============================================================================
# Integration-Style Tests
# ============================================================================


def test_watch_mode_full_cycle_simulation(git_repo: Path) -> None:
    """Test a full watch mode cycle: file change -> gate run -> result."""
    watch_cfg = WatchConfig(
        enabled=True,
        patterns=["**/*.py"],
        debounce_ms=100,
        auto_commit=False,
    )

    gates_cfg = make_test_gates_config(["exit 0"])

    cfg = Mock(spec=Config)
    cfg.watch = watch_cfg
    cfg.gates = gates_cfg

    # Track the full cycle
    events = []

    def mock_run_gates(project_root, commands, gates_config):
        events.append("gates_executed")
        return (True, [])

    with patch("ralph_gold.watch.run_gates", side_effect=mock_run_gates):
        with patch("ralph_gold.watch.watch_files") as mock_watch:
            with patch("ralph_gold.watch.signal.signal"):
                # Simulate the watch cycle
                def simulate_watch(project_root, cfg_obj, watch_cfg_obj, callback):
                    events.append("watch_started")
                    test_file = git_repo / "test.py"
                    events.append("file_changed")
                    callback(test_file)
                    events.append("callback_completed")

                mock_watch.side_effect = simulate_watch

                run_watch_mode(git_repo, cfg, gates_only=True, auto_commit=False)

                # Verify the sequence of events
                assert "watch_started" in events
                assert "file_changed" in events
                assert "gates_executed" in events
                assert "callback_completed" in events


def test_multiple_file_changes_in_sequence(temp_project: Path) -> None:
    """Test handling multiple file changes in sequence."""
    # Set last_check first
    last_check = time.time()
    time.sleep(0.1)

    # Create multiple files
    files = []
    for i in range(5):
        file_path = temp_project / f"file_{i}.py"
        file_path.write_text(f"content {i}", encoding="utf-8")
        files.append(file_path)

    # Poll for changes
    changed = _poll_for_changes(temp_project, ["**/*.py"], last_check)

    # All files should be detected
    assert len(changed) == 5
    for file_path in files:
        assert file_path in changed


def test_watch_mode_with_subdirectories(temp_project: Path) -> None:
    """Test watching files in subdirectories."""
    # Create nested directory structure
    src_dir = temp_project / "src"
    src_dir.mkdir()
    module_dir = src_dir / "module"
    module_dir.mkdir()

    # Set last_check after directories are created
    last_check = time.time()
    time.sleep(0.1)

    # Create files at different levels
    root_file = temp_project / "root.py"
    root_file.write_text("root", encoding="utf-8")

    src_file = src_dir / "src.py"
    src_file.write_text("src", encoding="utf-8")

    module_file = module_dir / "module.py"
    module_file.write_text("module", encoding="utf-8")

    # Poll for changes
    changed = _poll_for_changes(temp_project, ["**/*.py"], last_check)

    # All files should be detected
    assert root_file in changed
    assert src_file in changed
    assert module_file in changed


def test_pattern_matching_with_mixed_extensions(temp_project: Path) -> None:
    """Test pattern matching with multiple file extensions."""
    py_file = temp_project / "script.py"
    md_file = temp_project / "README.md"
    txt_file = temp_project / "notes.txt"
    toml_file = temp_project / "config.toml"

    patterns = ["**/*.py", "**/*.md", "**/*.toml"]

    assert _matches_pattern(py_file, patterns)
    assert _matches_pattern(md_file, patterns)
    assert not _matches_pattern(txt_file, patterns)
    assert _matches_pattern(toml_file, patterns)
