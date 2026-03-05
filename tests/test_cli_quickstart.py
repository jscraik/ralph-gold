"""Integration tests for the quickstart CLI command."""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_quickstart_command_exists() -> None:
    """Top-level help should include quickstart command."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "quickstart" in result.stdout


def test_quickstart_command_help() -> None:
    """Quickstart should expose profile and interactive options."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "quickstart", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--profile" in result.stdout
    assert "--interactive" in result.stdout
    assert "initialize ralph with recommended defaults" in result.stdout.lower()


def test_quickstart_creates_scaffold_with_simple_profile(tmp_path: Path) -> None:
    """Quickstart should initialize .ralph and set ux.mode to simple by default."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "quickstart"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    config_path = tmp_path / ".ralph" / "ralph.toml"
    assert config_path.exists()
    cfg = config_path.read_text(encoding="utf-8")
    assert "[ux]" in cfg
    assert 'mode = "simple"' in cfg
    assert "Recommended next step:" in result.stdout


def test_quickstart_sets_expert_profile(tmp_path: Path) -> None:
    """Quickstart should set ux.mode to expert when requested."""
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "ralph_gold.cli",
            "quickstart",
            "--profile",
            "expert",
            "--agent",
            "claude",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    cfg = (tmp_path / ".ralph" / "ralph.toml").read_text(encoding="utf-8")
    assert 'mode = "expert"' in cfg
    assert "ralph step --agent claude" in result.stdout
