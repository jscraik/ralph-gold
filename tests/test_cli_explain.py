"""Integration tests for the explain CLI command."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _write_minimal_prd(tmp_path: Path) -> None:
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    (ralph_dir / "PRD.md").write_text(
        """# PRD

## Tasks

- [x] 1. Done task
- [ ] 2. Open task
  - Depends on: 1
- [-] 3. Blocked task
""",
        encoding="utf-8",
    )


def test_explain_command_exists() -> None:
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "explain" in result.stdout


def test_explain_command_outputs_reasoning(tmp_path: Path) -> None:
    _write_minimal_prd(tmp_path)

    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "explain"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Explainability Summary" in result.stdout
    assert "Why this task was chosen:" in result.stdout
    assert "Why blocked:" in result.stdout
    assert "What to do next:" in result.stdout


def test_explain_json_output(tmp_path: Path) -> None:
    _write_minimal_prd(tmp_path)

    (tmp_path / ".ralph" / "ralph.toml").write_text(
        """
[output]
format = "json"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "explain"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["cmd"] == "explain"
    assert "explain" in payload
    assert "why_selected" in payload["explain"]
    assert "next_actions" in payload["explain"]
