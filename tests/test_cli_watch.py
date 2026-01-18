"""Tests for ralph watch CLI command."""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_watch_command_exists() -> None:
    """Test that watch command is available in CLI."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "watch" in result.stdout


def test_watch_command_help() -> None:
    """Test that watch command has help text."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "watch", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--gates-only" in result.stdout
    assert "--auto-commit" in result.stdout
    assert "ralph watch" in result.stdout


def test_watch_command_requires_enabled_config(tmp_path: Path) -> None:
    """Test that watch command fails when watch mode is not enabled."""
    # Create minimal ralph setup
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create config with watch disabled
    config_content = """
[files]
prd = "PRD.md"

[watch]
enabled = false

[gates]
commands = []

[loop]
max_iterations = 1

[runners.codex]
argv = ["echo", "test"]
"""
    (ralph_dir / "ralph.toml").write_text(config_content)

    # Create minimal PRD
    (ralph_dir / "PRD.md").write_text("## Tasks\n- [ ] Test task\n")

    # Try to run watch command
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "watch"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    # Should fail with exit code 2
    assert result.returncode == 2
    # Check for error message in either stdout or stderr
    output = result.stdout + result.stderr
    assert "Watch mode is not enabled" in output
