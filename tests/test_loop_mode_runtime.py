from __future__ import annotations

import json
import subprocess
from pathlib import Path
from textwrap import dedent

from ralph_gold.loop import IterationResult, load_state, run_iteration, run_loop
from ralph_gold.config import load_config
from ralph_gold.output import OutputConfig, get_output_config, set_output_config
from ralph_gold.subprocess_helper import SubprocessResult


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


def test_run_iteration_respects_stream_flag(tmp_path: Path, monkeypatch) -> None:
    project_root = _init_git_repo(tmp_path)
    (project_root / ".ralph").mkdir()

    config = dedent(
        """
        [loop]
        max_iterations = 1
        no_progress_limit = 3
        rate_limit_per_hour = 0
        sleep_seconds_between_iters = 0
        runner_timeout_seconds = 900
        max_attempts_per_task = 3
        skip_blocked_tasks = true

        [runners.codex]
        argv = ["dummy-runner"]

        [files]
        prd = "prd.json"
        """
    ).strip() + "\n"

    (project_root / ".ralph" / "ralph.toml").write_text(config, encoding="utf-8")
    _write_prd(project_root)

    cfg = load_config(project_root)
    captured = {
        "live_called": 0,
        "batch_called": 0,
        "runner_live_called": 0,
        "runner_batch_called": 0,
    }

    def fake_run_subprocess_live(
        argv: list[str], *args, **kwargs
    ) -> SubprocessResult:
        captured["live_called"] += 1
        if str(argv[0]).endswith("dummy-runner") or argv[0] == "dummy-runner":
            captured["runner_live_called"] += 1
        return SubprocessResult(returncode=0, stdout="", stderr="")

    def fake_run_subprocess(
        argv: list[str], *args, **kwargs
    ) -> SubprocessResult:
        captured["batch_called"] += 1
        if str(argv[0]).endswith("dummy-runner") or argv[0] == "dummy-runner":
            captured["runner_batch_called"] += 1
        return SubprocessResult(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "ralph_gold.loop.run_subprocess_live", fake_run_subprocess_live
    )
    monkeypatch.setattr("ralph_gold.loop.run_subprocess", fake_run_subprocess)

    result_stream = run_iteration(
        project_root,
        agent="codex",
        cfg=cfg,
        iteration=1,
        stream=True,
    )
    assert result_stream.return_code == 0
    assert captured["live_called"] == 1
    assert captured["runner_live_called"] == 1
    assert captured["runner_batch_called"] == 0

    batch_root = tmp_path / "batch-repo"
    batch_root.mkdir()
    batch_root = _init_git_repo(batch_root)
    (batch_root / ".ralph").mkdir()
    (batch_root / ".ralph" / "ralph.toml").write_text(config, encoding="utf-8")
    _write_prd(batch_root)

    cfg_batch = load_config(batch_root)

    captured["live_called"] = 0
    captured["batch_called"] = 0
    captured["runner_live_called"] = 0
    captured["runner_batch_called"] = 0

    result_batch = run_iteration(
        batch_root,
        agent="codex",
        cfg=cfg_batch,
        iteration=1,
        stream=False,
    )
    assert result_batch.return_code == 0
    assert captured["live_called"] == 0
    assert captured["runner_live_called"] == 0
    assert captured["runner_batch_called"] >= 1


def test_stream_output_disabled_in_json_mode(tmp_path: Path, monkeypatch) -> None:
    project_root = _init_git_repo(tmp_path)
    (project_root / ".ralph").mkdir()

    config = dedent(
        """
        [loop]
        max_iterations = 1
        no_progress_limit = 3
        rate_limit_per_hour = 0
        sleep_seconds_between_iters = 0
        runner_timeout_seconds = 900
        max_attempts_per_task = 3
        skip_blocked_tasks = true

        [runners.codex]
        argv = ["dummy-runner"]

        [files]
        prd = "prd.json"
        """
    ).strip() + "\n"

    (project_root / ".ralph" / "ralph.toml").write_text(config, encoding="utf-8")
    _write_prd(project_root)

    cfg = load_config(project_root)

    previous_config = get_output_config()
    set_output_config(OutputConfig(verbosity="normal", format="json"))
    try:
        captured = {"forward_output": None}

        def fake_run_subprocess_live(
            argv: list[str], *args, forward_output: bool = False, **kwargs
        ) -> SubprocessResult:
            captured["forward_output"] = forward_output
            return SubprocessResult(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(
            "ralph_gold.loop.run_subprocess_live", fake_run_subprocess_live
        )

        result = run_iteration(
            project_root,
            agent="codex",
            cfg=cfg,
            iteration=1,
            stream=True,
        )
        assert result.return_code == 0
        assert captured["forward_output"] is False
    finally:
        set_output_config(previous_config)


def test_run_loop_stream_flag_is_forwarded_to_iteration(tmp_path: Path, monkeypatch) -> None:
    project_root = _init_git_repo(tmp_path)
    (project_root / ".ralph").mkdir()

    config = dedent(
        """
        [loop]
        max_iterations = 2
        no_progress_limit = 3
        rate_limit_per_hour = 0
        sleep_seconds_between_iters = 0
        runner_timeout_seconds = 900
        max_attempts_per_task = 3
        skip_blocked_tasks = true

        [runners.codex]
        argv = ["dummy-runner"]

        [files]
        prd = "prd.json"
        """
    ).strip() + "\n"

    (project_root / ".ralph" / "ralph.toml").write_text(config, encoding="utf-8")
    _write_prd(project_root)

    cfg = load_config(project_root)
    captured = {"stream": None}

    def fake_run_iteration(
        project_root: Path,
        agent: str,
        cfg=None,
        iteration=1,
        stream=False,
        **kwargs,
    ) -> IterationResult:
        captured["stream"] = stream
        return IterationResult(
            iteration=iteration,
            agent=agent,
            story_id="task-1",
            exit_signal=False,
            return_code=0,
            log_path=project_root / ".ralph" / "logs" / f"iter-{iteration}.log",
            progress_made=True,
            no_progress_streak=0,
            gates_ok=True,
            repo_clean=True,
        )

    monkeypatch.setattr("ralph_gold.loop.run_iteration", fake_run_iteration)

    run_loop(
        project_root,
        agent="codex",
        max_iterations=1,
        cfg=cfg,
        stream=True,
    )

    assert captured["stream"] is True
