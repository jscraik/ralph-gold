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
            {"id": "task-2", "title": "Second task", "status": "todo"},
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


def test_flow_metrics_recorded_in_state(tmp_path: Path) -> None:
    project_root = _init_git_repo(tmp_path)
    (project_root / ".ralph").mkdir()

    config = dedent(
        """
        [loop]
        max_iterations = 5
        rate_limit_per_hour = 0
        runner_timeout_seconds = 900

        [runners.codex]
        argv = ["echo", "mock-agent"]

        [files]
        prd = "prd.json"
        """
    ).strip() + "\n"

    (project_root / ".ralph" / "ralph.toml").write_text(config, encoding="utf-8")
    _write_prd(project_root)

    cfg = load_config(project_root)
    # Run one iteration
    run_iteration(project_root, agent="codex", cfg=cfg, iteration=1)

    state = load_state(project_root / ".ralph" / "state.json")
    assert "flow_metrics" in state
    metrics = state["flow_metrics"]
    assert "tasks_per_hour" in metrics
    assert "blocked_task_rate" in metrics
    assert "success_rate" in metrics
    assert "updated_at" in metrics


def test_prompt_select(tmp_path: Path):
    from ralph_gold.loop import build_prompt
    from ralph_gold.config import Config, FilesConfig, PromptConfig
    from ralph_gold.prd import SelectedTask
    
    project_root = tmp_path
    (project_root / ".ralph").mkdir()
    (project_root / ".ralph" / "PROMPT_build.md").write_text("DEFAULT PROMPT", encoding="utf-8")
    (project_root / ".ralph" / "PROMPT_docs.md").write_text("DOCS PROMPT", encoding="utf-8")
    (project_root / ".ralph" / "PROMPT_hotfix.md").write_text("HOTFIX PROMPT", encoding="utf-8")
    (project_root / ".ralph" / "PROMPT_exploration.md").write_text("EXPLORE PROMPT", encoding="utf-8")
    
    cfg = Config(
        loop=None,
        files=FilesConfig(
            prompt=".ralph/PROMPT_build.md",
            prompt_docs=".ralph/PROMPT_docs.md",
            prompt_hotfix=".ralph/PROMPT_hotfix.md",
            prompt_exploration=".ralph/PROMPT_exploration.md"
        ),
        runners={},
        gates=None,
        git=None,
        tracker=None,
        parallel=None,
        prompt=PromptConfig()
    )
    
    # Default
    task = SelectedTask(id="1", title="Regular task", kind="md")
    assert "DEFAULT PROMPT" in build_prompt(project_root, cfg, task, 1)
    
    # Docs
    task = SelectedTask(id="1", title="[DOCS] Update readme", kind="md")
    assert "DOCS PROMPT" in build_prompt(project_root, cfg, task, 1)
    
    # Hotfix
    task = SelectedTask(id="1", title="[HOTFIX] Fix crash", kind="md")
    assert "HOTFIX PROMPT" in build_prompt(project_root, cfg, task, 1)
    
    # Exploration
    task = SelectedTask(id="1", title="[EXPLORE] Research new API", kind="md")
    assert "EXPLORE PROMPT" in build_prompt(project_root, cfg, task, 1)
    
    # Fallback if file missing
    (project_root / ".ralph" / "PROMPT_docs.md").unlink()
    task = SelectedTask(id="1", title="[DOCS] Update readme", kind="md")
    assert "DEFAULT PROMPT" in build_prompt(project_root, cfg, task, 1)


def test_adaptive(tmp_path: Path) -> None:
    project_root = _init_git_repo(tmp_path)
    (project_root / ".ralph").mkdir()

    # Adaptive config: medium threshold 0.4, high threshold 0.8
    config_text = dedent(
        """
        [loop]
        max_iterations = 2
        mode = "speed"

        [loop.adaptive]
        enabled = true
        medium_risk_threshold = 0.4
        high_risk_threshold = 0.8

        [gates]
        commands = ["exit 0", "exit 0"]
        fail_fast = true

        [gates.llm_judge]
        enabled = false
        agent = "codex"

        [runners.codex]
        argv = ["echo", "mock-agent"]

        [files]
        prd = "prd.json"
        """
    ).strip() + "\n"

    (project_root / ".ralph" / "ralph.toml").write_text(config_text, encoding="utf-8")
    _write_prd(project_root)

    # Initialize state with high-risk score for src/risky.py
    state = {
        "area_risk_scores": {"src/risky.py": 0.9},
        "history": [],
        "invocations": [],
        "noProgressStreak": 0,
    }
    (project_root / ".ralph" / "state.json").write_text(json.dumps(state), encoding="utf-8")

    # Create risky file
    (project_root / "src").mkdir()
    risky_file = project_root / "src" / "risky.py"
    risky_file.write_text("# risky\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=project_root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Add risky file"], cwd=project_root, check=True, capture_output=True)

    from dataclasses import replace
    from unittest.mock import patch, MagicMock
    with patch("ralph_gold.loop._get_changed_files") as mock_files, \
         patch("ralph_gold.trackers.FileTracker.is_task_done", return_value=True), \
         patch("ralph_gold.loop.run_subprocess") as mock_run_sub:
        
        # Mock run_subprocess with side effect to handle failures and judge
        def mock_run(argv, *args, **kwargs):
            cmd = " ".join(argv) if isinstance(argv, list) else str(argv)
            if "exit 1" in cmd:
                return SubprocessResult(returncode=1, stdout="", stderr="")
            return SubprocessResult(returncode=0, stdout="SHIP", stderr="")

        mock_run_sub.side_effect = mock_run
        mock_files.return_value = [risky_file]
        
        cfg = load_config(project_root)
        
        # First iteration: gates pass, verify judge is forced ON
        run_iteration(project_root, agent="codex", cfg=cfg, iteration=1)

        state = load_state(project_root / ".ralph" / "state.json")
        history = state.get("history", [])
        assert len(history) == 1, "Expected 1 history entry after first iteration"
        entry = history[-1]
        assert entry.get("risk_score") == 0.9
        assert entry.get("judge_ran") is True
        
        # Mark task-1 done manually in PRD so iteration 2 picks task-2
        prd_content = json.loads((project_root / "prd.json").read_text(encoding="utf-8"))
        prd_content["stories"][0]["status"] = "done"
        (project_root / "prd.json").write_text(json.dumps(prd_content, indent=2), encoding="utf-8")
        
        # Second iteration: gates fail, verify fail_fast is disabled
        # Use dataclasses.replace because config classes are frozen
        new_gates = replace(cfg.gates, commands=["exit 1", "exit 0"])
        cfg = replace(cfg, gates=new_gates)
        
        run_iteration(project_root, agent="codex", cfg=cfg, iteration=2)
        
        state = load_state(project_root / ".ralph" / "state.json")
        history = state.get("history", [])
        assert len(history) == 2, "Expected 2 history entries after second iteration"
        entry = history[-1]
        assert entry.get("story_id") == "task-2"
        gate_results = entry.get("gate_results", [])
        # Should have 2 results because fail_fast was disabled by adaptive rigor
        assert len(gate_results) == 2
        assert gate_results[0]["return_code"] == 1
        assert gate_results[1]["return_code"] == 0
