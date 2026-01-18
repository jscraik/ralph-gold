"""Integration tests for the diagnose CLI command."""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_diagnose_command_exists():
    """Test that the diagnose command is registered."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "diagnose" in result.stdout


def test_diagnose_command_help():
    """Test that the diagnose command has help text."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "diagnose", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--test-gates" in result.stdout
    assert "Test each gate command individually" in result.stdout


def test_diagnose_command_runs(tmp_path: Path):
    """Test that the diagnose command runs successfully."""
    # Create a minimal ralph project
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config
    config_content = """
[files]
prd = ".ralph/prd.json"

[runners.codex]
argv = ["echo", "test"]

[gates]
commands = []
"""
    (ralph_dir / "ralph.toml").write_text(config_content)

    # Create minimal PRD
    prd_content = '{"stories": []}'
    (ralph_dir / "prd.json").write_text(prd_content)

    # Run diagnose command
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "diagnose"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Ralph Diagnostics Report" in result.stdout
    assert "Summary:" in result.stdout


def test_diagnose_with_test_gates_flag(tmp_path: Path):
    """Test that the --test-gates flag works."""
    # Create a minimal ralph project
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config with a gate command
    config_content = """
[files]
prd = ".ralph/prd.json"

[runners.codex]
argv = ["echo", "test"]

[gates]
commands = ["echo 'test gate'"]
"""
    (ralph_dir / "ralph.toml").write_text(config_content)

    # Create minimal PRD
    prd_content = '{"stories": []}'
    (ralph_dir / "prd.json").write_text(prd_content)

    # Run diagnose command with --test-gates
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "diagnose", "--test-gates"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Ralph Diagnostics Report" in result.stdout
    assert "gate" in result.stdout.lower()


def test_diagnose_detects_missing_config(tmp_path: Path):
    """Test that diagnose detects missing configuration."""
    # Run diagnose in a directory without .ralph
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "diagnose"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    # Missing config is a warning, not an error, so exit code is 0
    assert result.returncode == 0
    assert "Ralph Diagnostics Report" in result.stdout
    assert "WARNINGS:" in result.stdout
    assert "No ralph.toml configuration file found" in result.stdout
