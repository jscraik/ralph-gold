"""CLI tests for loop mode overrides."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from ralph_gold.cli import build_parser, cmd_run, cmd_step


def test_step_mode_overrides_loop_config(tmp_path: Path, monkeypatch) -> None:
    """Ensure --mode overrides loop.mode for ralph step."""
    monkeypatch.chdir(tmp_path)

    captured = {}

    def mock_dry_run_loop(project_root: Path, agent: str, limit: int, cfg):
        captured["mode"] = cfg.loop.mode
        return SimpleNamespace(
            resolved_mode={"name": cfg.loop.mode},
            config_valid=True,
            total_tasks=0,
            completed_tasks=0,
            issues=[],
            tasks_to_execute=[],
            gates_to_run=[],
        )

    monkeypatch.setattr("ralph_gold.cli.dry_run_loop", mock_dry_run_loop)

    args = SimpleNamespace(
        agent="codex",
        mode="quality",
        prompt_file=None,
        prd_file=None,
        dry_run=True,
        interactive=False,
    )

    exit_code = cmd_step(args)
    assert exit_code == 0
    assert captured["mode"] == "quality"


def test_run_mode_overrides_loop_config(tmp_path: Path, monkeypatch) -> None:
    """Ensure --mode overrides loop.mode for ralph run."""
    monkeypatch.chdir(tmp_path)

    captured = {}

    def mock_run_loop(
        project_root: Path,
        agent: str,
        max_iterations: int | None = None,
        cfg=None,
        parallel: bool = False,
        max_workers: int | None = None,
        dry_run: bool = False,
        stream: bool = False,
        skip_gates: bool = False,
        target_task_id: str | None = None,
    ):
        captured["mode"] = cfg.loop.mode
        captured["stream"] = stream
        return []

    monkeypatch.setattr("ralph_gold.cli.run_loop", mock_run_loop)

    args = SimpleNamespace(
        agent="codex",
        mode="exploration",
        max_iterations=None,
        prompt_file=None,
        prd_file=None,
        parallel=False,
        max_workers=None,
        dry_run=True,
        stream=True,
    )

    exit_code = cmd_run(args)
    assert exit_code == 0
    assert captured["mode"] == "exploration"
    assert captured["stream"] is True


def test_run_mode_stream_flag_is_forwarded(tmp_path: Path, monkeypatch) -> None:
    """Ensure --stream flag is passed to loop runtime."""
    monkeypatch.chdir(tmp_path)

    captured = {}

    def mock_run_loop(
        project_root: Path,
        agent: str,
        max_iterations: int | None = None,
        cfg=None,
        parallel: bool = False,
        max_workers: int | None = None,
        dry_run: bool = False,
        stream: bool = False,
        skip_gates: bool = False,
        target_task_id: str | None = None,
    ):
        captured["stream"] = stream
        return []

    monkeypatch.setattr("ralph_gold.cli.run_loop", mock_run_loop)

    args = SimpleNamespace(
        agent="codex",
        mode=None,
        max_iterations=None,
        prompt_file=None,
        prd_file=None,
        parallel=False,
        max_workers=None,
        dry_run=True,
        stream=True,
    )

    exit_code = cmd_run(args)
    assert exit_code == 0
    assert captured["stream"] is True


def test_run_mode_stream_flag_disabled_with_parallel(tmp_path: Path, monkeypatch) -> None:
    """Parallel runs cannot stream live output, so --stream should be ignored."""
    monkeypatch.chdir(tmp_path)

    captured = {}

    def mock_run_loop(
        project_root: Path,
        agent: str,
        max_iterations: int | None = None,
        cfg=None,
        parallel: bool = False,
        max_workers: int | None = None,
        dry_run: bool = False,
        stream: bool = False,
        skip_gates: bool = False,
        target_task_id: str | None = None,
    ):
        captured["parallel"] = parallel
        captured["stream"] = stream
        return []

    monkeypatch.setattr("ralph_gold.cli.run_loop", mock_run_loop)

    args = SimpleNamespace(
        agent="codex",
        mode=None,
        max_iterations=None,
        prompt_file=None,
        prd_file=None,
        parallel=True,
        max_workers=None,
        dry_run=True,
        stream=True,
    )

    exit_code = cmd_run(args)
    assert exit_code == 0
    assert captured["parallel"] is True
    assert captured["stream"] is False


def test_invalid_mode_rejected() -> None:
    """Invalid --mode values should be rejected with a clear error."""
    parser = build_parser()
    stderr = io.StringIO()

    with contextlib.redirect_stderr(stderr), pytest.raises(SystemExit) as exc:
        parser.parse_args(["step", "--mode", "fast"])

    assert exc.value.code == 2
    assert "Error: argument --mode: invalid choice: 'fast'" in stderr.getvalue()


def test_step_targeting_flags_parse() -> None:
    """Step parser should accept task-targeted execution flags."""
    parser = build_parser()
    args = parser.parse_args(
        [
            "step",
            "--task-id",
            "42",
            "--allow-done-target",
            "--allow-blocked-target",
            "--reopen-target",
        ]
    )
    assert args.task_id == "42"
    assert args.allow_done_target is True
    assert args.allow_blocked_target is True
    assert args.reopen_target is True


def test_harness_live_flags_parse() -> None:
    """Harness parser should accept live execution controls."""
    parser = build_parser()
    args = parser.parse_args(
        [
            "harness",
            "run",
            "--execution-mode",
            "live",
            "--allow-non-strict-targeting",
            "--stop-on-target-error",
        ]
    )
    assert args.execution_mode == "live"
    assert args.strict_targeting is False
    assert args.continue_on_target_error is False


def test_quick_flag_overrides_mode_and_max_iterations(tmp_path: Path, monkeypatch) -> None:
    """Ensure --quick flag correctly overrides mode and max_iterations."""
    monkeypatch.chdir(tmp_path)

    captured = {}

    def mock_run_loop(
        project_root: Path,
        agent: str,
        max_iterations: int | None = None,
        cfg=None,
        parallel: bool = False,
        max_workers: int | None = None,
        dry_run: bool = False,
        stream: bool = False,
        skip_gates: bool = False,
        target_task_id: str | None = None,
    ):
        captured["mode"] = cfg.loop.mode
        captured["max_iterations"] = max_iterations
        return [
            SimpleNamespace(
                iteration=1,
                story_id="S1",
                return_code=0,
                exit_signal=True,
                gates_ok=True,
                judge_ok=True,
                review_ok=True,
                log_path=Path("log.txt"),
            )
        ]

    monkeypatch.setattr("ralph_gold.cli.run_loop", mock_run_loop)

    # Test ralph run --quick
    parser = build_parser()
    args = parser.parse_args(["run", "--quick"])
    exit_code = cmd_run(args)
    assert exit_code == 0
    assert captured["mode"] == "speed"
    assert captured["max_iterations"] == 1

    # Test ralph step --quick
    captured = {}

    def mock_dry_run_loop(project_root: Path, agent: str, limit: int, cfg):
        captured["mode"] = cfg.loop.mode
        return SimpleNamespace(
            resolved_mode={"name": cfg.loop.mode},
            config_valid=True,
            total_tasks=0,
            completed_tasks=0,
            issues=[],
            tasks_to_execute=[],
            gates_to_run=[],
        )

    monkeypatch.setattr("ralph_gold.cli.dry_run_loop", mock_dry_run_loop)

    args = parser.parse_args(["step", "--quick", "--dry-run"])
    exit_code = cmd_step(args)
    assert exit_code == 0
    assert captured["mode"] == "speed"


def test_batch_flag_overrides_mode_and_enables_batch(tmp_path: Path, monkeypatch) -> None:
    """Ensure --batch flag correctly overrides mode and enables batch selection."""
    monkeypatch.chdir(tmp_path)

    captured = {}

    def mock_run_loop(
        project_root: Path,
        agent: str,
        max_iterations: int | None = None,
        cfg=None,
        parallel: bool = False,
        max_workers: int | None = None,
        dry_run: bool = False,
        stream: bool = False,
        skip_gates: bool = False,
        target_task_id: str | None = None,
    ):
        captured["mode"] = cfg.loop.mode
        captured["batch_enabled"] = cfg.loop.batch_enabled
        return [
            SimpleNamespace(
                iteration=1,
                story_id="S1",
                return_code=0,
                exit_signal=True,
                gates_ok=True,
                judge_ok=True,
                review_ok=True,
                log_path=Path("log.txt"),
            )
        ]

    monkeypatch.setattr("ralph_gold.cli.run_loop", mock_run_loop)

    # Test ralph run --batch
    parser = build_parser()
    args = parser.parse_args(["run", "--batch"])
    exit_code = cmd_run(args)
    assert exit_code == 0
    assert captured["mode"] == "speed"
    assert captured["batch_enabled"] is True

    # Test ralph step --batch
    captured = {}

    def mock_dry_run_loop(project_root: Path, agent: str, limit: int, cfg):
        captured["mode"] = cfg.loop.mode
        captured["batch_enabled"] = cfg.loop.batch_enabled
        return SimpleNamespace(
            resolved_mode={"name": cfg.loop.mode},
            config_valid=True,
            total_tasks=0,
            completed_tasks=0,
            issues=[],
            tasks_to_execute=[],
            gates_to_run=[],
        )

    monkeypatch.setattr("ralph_gold.cli.dry_run_loop", mock_dry_run_loop)

    args = parser.parse_args(["step", "--batch", "--dry-run"])
    exit_code = cmd_step(args)
    assert exit_code == 0
    assert captured["mode"] == "speed"
    assert captured["batch_enabled"] is True


def test_explore_flag_overrides_mode_and_extended_timeout(tmp_path: Path, monkeypatch) -> None:
    """Ensure --explore flag correctly overrides mode and extends timeout."""
    monkeypatch.chdir(tmp_path)

    captured = {}

    def mock_run_loop(
        project_root: Path,
        agent: str,
        max_iterations: int | None = None,
        cfg=None,
        parallel: bool = False,
        max_workers: int | None = None,
        dry_run: bool = False,
        stream: bool = False,
        skip_gates: bool = False,
        target_task_id: str | None = None,
    ):
        captured["mode"] = cfg.loop.mode
        captured["timeout"] = cfg.loop.runner_timeout_seconds
        return [
            SimpleNamespace(
                iteration=1,
                story_id="S1",
                return_code=0,
                exit_signal=True,
                gates_ok=True,
                judge_ok=True,
                review_ok=True,
                log_path=Path("log.txt"),
            )
        ]

    monkeypatch.setattr("ralph_gold.cli.run_loop", mock_run_loop)

    # Test ralph run --explore
    parser = build_parser()
    args = parser.parse_args(["run", "--explore"])
    exit_code = cmd_run(args)
    assert exit_code == 0
    assert captured["mode"] == "exploration"
    assert captured["timeout"] == 3600

    # Test ralph step --explore
    captured = {}

    def mock_dry_run_loop(project_root: Path, agent: str, limit: int, cfg):
        captured["mode"] = cfg.loop.mode
        captured["timeout"] = cfg.loop.runner_timeout_seconds
        return SimpleNamespace(
            resolved_mode={"name": cfg.loop.mode},
            config_valid=True,
            total_tasks=0,
            completed_tasks=0,
            issues=[],
            tasks_to_execute=[],
            gates_to_run=[],
        )

    monkeypatch.setattr("ralph_gold.cli.dry_run_loop", mock_dry_run_loop)

    args = parser.parse_args(["step", "--explore", "--dry-run"])
    exit_code = cmd_step(args)
    assert exit_code == 0
    assert captured["mode"] == "exploration"
    assert captured["timeout"] == 3600


def test_quick_and_mode_are_mutually_exclusive() -> None:
    """Ensure --quick and --mode cannot be used together."""
    parser = build_parser()

    # argparse will exit when mutually exclusive arguments are used together
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "--quick", "--mode", "quality"])

    with pytest.raises(SystemExit):
        parser.parse_args(["step", "--quick", "--mode", "exploration"])

    with pytest.raises(SystemExit):
        parser.parse_args(["run", "--explore", "--mode", "quality"])

    with pytest.raises(SystemExit):
        parser.parse_args(["run", "--batch", "--quick"])

    with pytest.raises(SystemExit):
        parser.parse_args(["run", "--batch", "--explore"])

    with pytest.raises(SystemExit):
        parser.parse_args(["step", "--batch", "--mode", "quality"])

def test_shortcuts(tmp_path: Path, monkeypatch) -> None:
    """Ensure --hotfix and --task shortcuts work correctly."""
    monkeypatch.chdir(tmp_path)

    captured = {}

    def mock_run_loop(
        project_root: Path,
        agent: str,
        max_iterations: int | None = None,
        cfg=None,
        parallel: bool = False,
        max_workers: int | None = None,
        dry_run: bool = False,
        stream: bool = False,
        skip_gates: bool = False,
        target_task_id: str | None = None,
            ):
                captured["mode"] = cfg.loop.mode
                captured["skip_gates"] = skip_gates
                captured["target_task_id"] = target_task_id
                return [
    
            SimpleNamespace(
                iteration=1,
                story_id="S1",
                return_code=0,
                exit_signal=True,
                gates_ok=True,
                judge_ok=True,
                review_ok=True,
                log_path=Path("log.txt"),
            )
        ]

    monkeypatch.setattr("ralph_gold.cli.run_loop", mock_run_loop)

    # Test ralph run --hotfix
    parser = build_parser()
    args = parser.parse_args(["run", "--hotfix"])
    exit_code = cmd_run(args)
    assert exit_code == 0
    assert captured["mode"] == "speed"
    assert captured["skip_gates"] is True

    # Test ralph step --hotfix
    captured = {}

    def mock_run_iteration(
        project_root: Path,
        agent: str,
        cfg=None,
        iteration: int = 1,
        task_override=None,
        target_task_id=None,
        allow_done_target=False,
        allow_blocked_target=False,
        reopen_if_needed=False,
        stream=False,
        skip_gates=False,
    ):
        captured["mode"] = cfg.loop.mode
        captured["skip_gates"] = skip_gates
        captured["target_task_id"] = target_task_id
        return SimpleNamespace(
            iteration=1,
            story_id="S1",
            return_code=0,
            exit_signal=True,
            gates_ok=True,
            judge_ok=True,
            review_ok=True,
            log_path=Path("log.txt"),
            no_progress_streak=0,
            target_task_id=target_task_id,
            target_status="open",
            target_failure_reason=None,
            targeting_policy="strict",
        )

    monkeypatch.setattr("ralph_gold.cli.run_iteration", mock_run_iteration)

    args = parser.parse_args(["step", "--hotfix"])
    exit_code = cmd_step(args)
    assert exit_code == 0
    assert captured["mode"] == "speed"
    assert captured["skip_gates"] is True

    # Test ralph step --task
    captured = {}
    args = parser.parse_args(["step", "--task", "42"])
    exit_code = cmd_step(args)
    assert exit_code == 0
    assert captured["target_task_id"] == "42"

    # Test ralph step --task-id
    captured = {}
    args = parser.parse_args(["step", "--task-id", "43"])
    exit_code = cmd_step(args)
    assert exit_code == 0
    assert captured["target_task_id"] == "43"

    # Test ralph run --task
    captured = {}
    args = parser.parse_args(["run", "--task", "44"])
    exit_code = cmd_run(args)
    assert exit_code == 0
    assert captured.get("target_task_id") == "44"
