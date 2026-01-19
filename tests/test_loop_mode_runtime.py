from __future__ import annotations

import json
import subprocess
from pathlib import Path
from textwrap import dedent

import pytest

from ralph_gold.config import load_config
from ralph_gold.loop import load_state, run_iteration, run_loop
from ralph_gold.output import OutputConfig, get_output_config, set_output_config


def _init_git_repo(tmp_path: Path) -> Path:
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

    (tmp_path / "README.md").write_text("# Test Project\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return tmp_path


def _write_prd(project_root: Path) -> None:
    prd = {
        "stories": [
            {"id": "task-1", "title": "First task", "status": "todo"},
        ]
    }
    (project_root / "prd.json").write_text(json.dumps(prd, indent=2), encoding="utf-8")


def test_loop_mode_resolved_in_state_history(tmp_path: Path) -> None:
    project_root = _init_git_repo(tmp_path)
    (project_root / ".ralph").mkdir()

    config = dedent(
        """
        [loop]
        max_iterations = 5
        no_progress_limit = 3
        rate_limit_per_hour = 0
        sleep_seconds_between_iters = 0
        runner_timeout_seconds = 900
        max_attempts_per_task = 3
        skip_blocked_tasks = true
        mode = "quality"

        [loop.modes.quality]
        runner_timeout_seconds = 120
        max_attempts_per_task = 1
        skip_blocked_tasks = false

        [runners.codex]
        argv = ["echo", "mock-agent"]

        [files]
        prd = "prd.json"
        """
    ).strip() + "\n"

    (project_root / ".ralph" / "ralph.toml").write_text(config, encoding="utf-8")
    _write_prd(project_root)

    cfg = load_config(project_root)
    run_iteration(project_root, agent="codex", cfg=cfg, iteration=1)

    state = load_state(project_root / ".ralph" / "state.json")
    history = state.get("history", [])
    assert history, "Expected history to be recorded"

    entry = history[-1]
    loop_mode = entry.get("mode")
    assert loop_mode is not None
    assert loop_mode.get("name") == "quality"

    settings = loop_mode.get("settings")
    assert settings is not None
    assert settings.get("runner_timeout_seconds") == 120
    assert settings.get("max_attempts_per_task") == 1
    assert settings.get("skip_blocked_tasks") is False


def test_dry_run_output_includes_resolved_mode(tmp_path: Path, capsys) -> None:
    project_root = _init_git_repo(tmp_path)
    (project_root / ".ralph").mkdir()

    config = dedent(
        """
        [loop]
        max_iterations = 2
        mode = "exploration"

        [loop.modes.exploration]
        max_iterations = 1

        [runners.codex]
        argv = ["echo", "mock-agent"]

        [files]
        prd = "prd.json"
        """
    ).strip() + "\n"

    (project_root / ".ralph" / "ralph.toml").write_text(config, encoding="utf-8")
    _write_prd(project_root)

    previous_config = get_output_config()
    set_output_config(OutputConfig(verbosity="normal", format="text"))
    try:
        run_loop(project_root, agent="codex", max_iterations=1, dry_run=True)
    finally:
        set_output_config(previous_config)

    captured = capsys.readouterr()
    assert "Resolved loop mode: exploration" in captured.out


def test_mode_override_applies_to_loop_settings(tmp_path: Path, capsys) -> None:
    project_root = _init_git_repo(tmp_path)
    (project_root / ".ralph").mkdir()

    config = dedent(
        """
        [loop]
        max_iterations = 5
        mode = "exploration"

        [loop.modes.exploration]
        max_iterations = 1

        [runners.codex]
        argv = ["echo", "mock-agent"]

        [files]
        prd = "prd.json"
        """
    ).strip() + "\n"

    (project_root / ".ralph" / "ralph.toml").write_text(config, encoding="utf-8")
    _write_prd(project_root)

    previous_config = get_output_config()
    set_output_config(OutputConfig(verbosity="normal", format="text"))
    try:
        run_loop(project_root, agent="codex", dry_run=True)
    finally:
        set_output_config(previous_config)

    captured = capsys.readouterr()
    assert "up to 1 iterations" in captured.out
