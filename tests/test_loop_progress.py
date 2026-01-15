from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ralph_gold.config import load_config
from ralph_gold.loop import run_iteration


def _git(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _write_minimal_prd(prd_path: Path) -> None:
    prd_path.write_text(
        """# PRD\n\n## Tasks\n- [ ] First task\n""",
        encoding="utf-8",
    )


def _write_minimal_config(cfg_path: Path) -> None:
    cfg_path.write_text(
        """[loop]\nrunner_timeout_seconds = 5\n\n[files]\nprd = ".ralph/PRD.md"\nprogress = ".ralph/progress.md"\nprompt = ".ralph/PROMPT_build.md"\nagents = ".ralph/AGENTS.md"\nspecs_dir = ".ralph/specs"\n\n[runners.test]\nargv = ["true"]\n""",
        encoding="utf-8",
    )


def _write_minimal_prompt(prompt_path: Path) -> None:
    prompt_path.write_text("# Test Prompt\n", encoding="utf-8")


def _write_minimal_agents(agents_path: Path) -> None:
    agents_path.write_text("# Agents\n", encoding="utf-8")


def test_no_progress_streak_ignores_ralph_artifacts(tmp_path: Path) -> None:
    project_root = tmp_path

    _git(["git", "init"], cwd=project_root)
    _git(["git", "config", "user.email", "test@example.com"], cwd=project_root)
    _git(["git", "config", "user.name", "Test User"], cwd=project_root)

    ralph_dir = project_root / ".ralph"
    ralph_dir.mkdir()

    _write_minimal_prd(ralph_dir / "PRD.md")
    _write_minimal_prompt(ralph_dir / "PROMPT_build.md")
    _write_minimal_agents(ralph_dir / "AGENTS.md")
    _write_minimal_config(ralph_dir / "ralph.toml")

    # Ensure there's an initial commit so HEAD exists.
    _git(["git", "add", "."], cwd=project_root)
    _git(["git", "commit", "-m", "init"], cwd=project_root)

    cfg = load_config(project_root)
    res = run_iteration(project_root, agent="test", cfg=cfg, iteration=1)

    # Only .ralph/* changed; should count as no progress.
    state_path = project_root / ".ralph" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state.get("noProgressStreak") == 1
    assert res.progress_made is False
