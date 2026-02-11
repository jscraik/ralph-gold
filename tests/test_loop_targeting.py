"""Tests for task-targeted iteration plumbing."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ralph_gold.config import load_config
from ralph_gold.loop import _resolve_target_task, run_iteration


def _init_minimal_repo(tmp_path: Path, prd_content: str) -> None:
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir(parents=True, exist_ok=True)
    (ralph_dir / "PRD.md").write_text(prd_content, encoding="utf-8")
    (ralph_dir / "progress.md").write_text("# Progress\n", encoding="utf-8")
    (ralph_dir / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    (ralph_dir / "PROMPT_build.md").write_text("# Prompt\n", encoding="utf-8")
    (ralph_dir / "ralph.toml").write_text(
        """[loop]
max_iterations = 1

[files]
prd = ".ralph/PRD.md"
progress = ".ralph/progress.md"
agents = ".ralph/AGENTS.md"
prompt = ".ralph/PROMPT_build.md"

[tracker]
kind = "markdown"

[git]
branch_strategy = "none"
auto_commit = false

[runners.test]
argv = ["echo", "EXIT_SIGNAL: true"]
""",
        encoding="utf-8",
    )

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
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )


def test_run_iteration_strict_target_missing(tmp_path: Path) -> None:
    _init_minimal_repo(
        tmp_path,
        """# PRD

## Tasks

- [ ] Existing task
""",
    )

    result = run_iteration(
        tmp_path,
        agent="test",
        iteration=1,
        target_task_id="999",
    )

    assert result.return_code == 2
    assert result.target_task_id == "999"
    assert result.target_status == "missing"
    assert result.target_failure_reason == "missing_target"
    assert result.targeting_policy == "strict"
    assert result.log_path.exists()

    state = json.loads((tmp_path / ".ralph" / "state.json").read_text(encoding="utf-8"))
    assert state["history"][-1]["target_failure_reason"] == "missing_target"


def test_run_iteration_allows_done_target_with_override(tmp_path: Path) -> None:
    _init_minimal_repo(
        tmp_path,
        """# PRD

## Tasks

- [x] Completed task
""",
    )

    result = run_iteration(
        tmp_path,
        agent="test",
        iteration=1,
        target_task_id="1",
        allow_done_target=True,
    )

    assert result.return_code == 0
    assert result.story_id == "1"
    assert result.target_task_id == "1"
    assert result.target_status == "done"
    assert result.target_failure_reason is None
    assert result.targeting_policy == "override"


def test_target_resolution_falls_back_when_tracker_lacks_lookup(tmp_path: Path) -> None:
    _init_minimal_repo(
        tmp_path,
        """# PRD

## Tasks

- [ ] Open task
""",
    )
    cfg = load_config(tmp_path)

    class LegacyTracker:
        kind = "legacy"

    task, status = _resolve_target_task(
        project_root=tmp_path,
        cfg=cfg,
        tracker=LegacyTracker(),
        target_task_id="1",
    )

    assert task is not None
    assert task.id == "1"
    assert status == "open"
