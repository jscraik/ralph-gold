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
