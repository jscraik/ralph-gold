"""Integration tests for the status CLI command."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _write_minimal_prd(tmp_path: Path) -> None:
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    (ralph_dir / "PRD.md").write_text(
        """# PRD

## Tasks

- [x] Done task
- [ ] Open task
""",
        encoding="utf-8",
    )


def test_status_command_without_state_does_not_crash(tmp_path: Path) -> None:
    _write_minimal_prd(tmp_path)

    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "status"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "PRD: .ralph/PRD.md" in result.stdout
    assert "Next: id=2 title=Open task" in result.stdout


def test_status_command_with_state_shows_detailed_metrics(tmp_path: Path) -> None:
    _write_minimal_prd(tmp_path)

    state = {"history": []}
    (tmp_path / ".ralph" / "state.json").write_text(json.dumps(state), encoding="utf-8")

    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "status"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Detailed Progress Metrics:" in result.stdout
    assert "Total Tasks:" in result.stdout
