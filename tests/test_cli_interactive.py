"""Tests for interactive CLI flag integration."""

import json
from pathlib import Path
from unittest.mock import patch


def test_interactive_flag_in_help(tmp_path: Path):
    """Test that --interactive flag appears in help text."""
    from ralph_gold.cli import build_parser

    parser = build_parser()

    # Get help for the step subcommand specifically
    import io
    import sys

    # Capture help output for step command
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        parser.parse_args(["step", "--help"])
    except SystemExit:
        pass  # --help causes SystemExit

    help_text = sys.stdout.getvalue()
    sys.stdout = old_stdout

    assert "--interactive" in help_text
    assert "Interactively select which task to work on" in help_text


def test_interactive_mode_calls_selector(tmp_path: Path, monkeypatch):
    """Test that interactive mode calls the task selector."""
    import argparse

    from ralph_gold.cli import cmd_step

    # Setup test environment
    monkeypatch.chdir(tmp_path)

    # Initialize a minimal Ralph project
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config
    config_path = ralph_dir / "ralph.toml"
    config_path.write_text(
        """
[runners.codex]
argv = ["echo", "test"]

[loop]
max_iterations = 1

[gates]
commands = []

[files]
prd = "tasks.md"
"""
    )

    # Create minimal PRD
    prd_path = tmp_path / "tasks.md"
    prd_path.write_text(
        """
## Tasks

- [ ] Task 1: First task
  - Acceptance: Do something
"""
    )

    # Create state.json
    state_path = ralph_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "createdAt": "2024-01-01T00:00:00Z",
                "history": [],
                "invocations": [],
                "noProgressStreak": 0,
                "task_attempts": {},
                "blocked_tasks": {},
                "session_id": "",
            }
        )
    )

    # Initialize git repo
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
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
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Mock the interactive selection to return None (cancelled)
    with patch(
        "ralph_gold.interactive.select_task_interactive", return_value=None
    ) as mock_select:
        # Create args with interactive flag
        args = argparse.Namespace(
            agent="codex",
            prompt_file=None,
            prd_file=None,
            dry_run=False,
            interactive=True,
        )

        # Run cmd_step
        result = cmd_step(args)

        # Verify interactive selection was called
        assert mock_select.called
        assert mock_select.call_count == 1

        # Verify it returns 0 when cancelled
        assert result == 0


def test_non_interactive_mode_skips_selector(tmp_path: Path, monkeypatch):
    """Test that non-interactive mode doesn't call the task selector."""
    import argparse

    from ralph_gold.cli import cmd_step

    # Setup test environment
    monkeypatch.chdir(tmp_path)

    # Initialize a minimal Ralph project
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config
    config_path = ralph_dir / "ralph.toml"
    config_path.write_text(
        """
[runners.codex]
argv = ["echo", "test"]

[loop]
max_iterations = 1
no_progress_limit = 10

[gates]
commands = []

[files]
prd = "tasks.md"
"""
    )

    # Create minimal PRD
    prd_path = tmp_path / "tasks.md"
    prd_path.write_text(
        """
## Tasks

- [ ] Task 1: First task
"""
    )

    # Create state.json
    state_path = ralph_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "createdAt": "2024-01-01T00:00:00Z",
                "history": [],
                "invocations": [],
                "noProgressStreak": 0,
                "task_attempts": {},
                "blocked_tasks": {},
                "session_id": "",
            }
        )
    )

    # Initialize git repo
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
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
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    with patch("ralph_gold.interactive.select_task_interactive") as mock_select:
        # Create args WITHOUT interactive flag
        args = argparse.Namespace(
            agent="codex",
            prompt_file=None,
            prd_file=None,
            dry_run=False,
            interactive=False,
        )

        # Run cmd_step - this will actually run, but that's okay
        # We just want to verify the selector wasn't called
        result = cmd_step(args)

        # Verify interactive selection was NOT called
        assert not mock_select.called
