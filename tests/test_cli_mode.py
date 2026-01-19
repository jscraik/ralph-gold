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
    ):
        captured["mode"] = cfg.loop.mode
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
    )

    exit_code = cmd_run(args)
    assert exit_code == 0
    assert captured["mode"] == "exploration"


def test_invalid_mode_rejected() -> None:
    """Invalid --mode values should be rejected with a clear error."""
    parser = build_parser()
    stderr = io.StringIO()

    with contextlib.redirect_stderr(stderr), pytest.raises(SystemExit) as exc:
        parser.parse_args(["step", "--mode", "fast"])

    assert exc.value.code == 2
    assert "Error: argument --mode: invalid choice: 'fast'" in stderr.getvalue()
