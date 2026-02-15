"""Integration tests for the unblock CLI command."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_unblock_command_unblocks_numeric_task_id(tmp_path: Path) -> None:
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    (ralph_dir / "PRD.md").write_text(
        """# PRD

## Tasks

- [x] Done task
- [-] Blocked task
""",
        encoding="utf-8",
    )

    state = {
        "blocked_tasks": {
            "2": {
                "blocked_at": "2026-02-12T23:48:44.230405+00:00",
                "attempts": 1,
                "reason": "runner failed",
                "attempt_id": "20260212-234842-iter0062",
            }
        },
        "task_attempts": {"2": 1},
    }
    (ralph_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "ralph_gold.cli",
            "unblock",
            "2",
            "--reason",
            "retry after runner fix",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Unblocked task 2" in result.stdout

    prd_text = (ralph_dir / "PRD.md").read_text(encoding="utf-8")
    assert "- [ ] Blocked task" in prd_text

    new_state = json.loads((ralph_dir / "state.json").read_text(encoding="utf-8"))
    assert "2" not in new_state.get("blocked_tasks", {})
    assert new_state.get("task_attempts", {}).get("2") == 0
