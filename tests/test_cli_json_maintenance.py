"""JSON output tests for maintenance-style CLI commands."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_clean_json_output_has_totals(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "ralph_gold.cli",
            "--format",
            "json",
            "clean",
            "--dry-run",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["cmd"] == "clean"
    assert payload["schema_version"] == "ralph.cli.v1"
    assert payload["dry_run"] is True
    assert "totals" in payload
    assert "details" in payload


def test_sync_json_output_reports_removed_ids(tmp_path: Path) -> None:
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    (tmp_path / "ralph.toml").write_text(
        """
[files]
prd = ".ralph/PRD.md"

[loop]
max_iterations = 1
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (ralph_dir / "PRD.md").write_text(
        "# PRD\n\n## Tasks\n\n- [x] Task 1\n- [ ] Task 2\n",
        encoding="utf-8",
    )
    (ralph_dir / "state.json").write_text(
        json.dumps(
            {
                "blocked_tasks": {"1": {"reason": "timeout", "attempts": 1}},
                "task_attempts": {"1": 1},
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "ralph_gold.cli",
            "--format",
            "json",
            "sync",
            "--clean-attempts",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["cmd"] == "sync"
    assert payload["schema_version"] == "ralph.cli.v1"
    assert payload["removed_count"] == 1
    assert payload["removed_ids"] == ["1"]
    assert payload["clean_attempts"] is True


def test_interventions_global_json_when_disabled(tmp_path: Path) -> None:
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    (ralph_dir / "ralph.toml").write_text(
        """
[files]
prd = ".ralph/PRD.md"

[interventions]
enabled = false
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (ralph_dir / "PRD.md").write_text("# PRD\n\n## Tasks\n\n- [ ] Task 1\n", encoding="utf-8")

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "ralph_gold.cli",
            "--format",
            "json",
            "interventions",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["cmd"] == "interventions"
    assert payload["schema_version"] == "ralph.cli.v1"
    assert payload["enabled"] is False
    assert payload["recommendations"] == []
