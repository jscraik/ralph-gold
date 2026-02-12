"""Integration tests for harness CLI commands."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_harness_command_exists() -> None:
    """Top-level help should include harness command."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "harness" in result.stdout


def test_harness_collect_run_report_flow(tmp_path: Path) -> None:
    """Collect dataset, run evaluation, then report as CSV."""
    _write_json(
        tmp_path / ".ralph" / "state.json",
        {
            "history": [
                {
                    "ts": "2026-02-10T12:00:00+00:00",
                    "iteration": 7,
                    "agent": "codex",
                    "story_id": "task-1",
                    "mode": "speed",
                    "gates_ok": True,
                    "judge_ok": True,
                    "blocked": False,
                    "timed_out": False,
                    "duration_seconds": 12.3,
                    "attempt_id": "attempt-1",
                    "receipts_dir": ".ralph/receipts/task-1/attempt-1",
                }
            ]
        },
    )
    _write_json(
        tmp_path / ".ralph" / "attempts" / "task-1" / "attempt-1.json",
        {"return_code": 0, "task_title": "Harness case"},
    )
    _write_json(
        tmp_path / ".ralph" / "receipts" / "task-1" / "attempt-1" / "runner.json",
        {"returncode": 0},
    )

    dataset_path = tmp_path / ".ralph" / "harness" / "cases.json"
    run_path = tmp_path / ".ralph" / "harness" / "runs" / "run-1.json"

    collect = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "ralph_gold.cli",
            "harness",
            "collect",
            "--days",
            "365",
            "--limit",
            "10",
            "--output",
            str(dataset_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert collect.returncode == 0
    assert dataset_path.exists()

    run = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "ralph_gold.cli",
            "harness",
            "run",
            "--dataset",
            str(dataset_path),
            "--output",
            str(run_path),
            "--max-cases",
            "1",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0
    assert run_path.exists()

    report = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "ralph_gold.cli",
            "harness",
            "report",
            "--input",
            str(run_path),
            "--format",
            "csv",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert report.returncode == 0
    assert "quality_score" in report.stdout


def test_harness_run_live_mode_stops_on_target_error(
    tmp_path: Path, monkeypatch
) -> None:
    """Live harness mode should support strict/stop targeting controls."""
    from ralph_gold import cli

    dataset_path = tmp_path / ".ralph" / "harness" / "cases.json"
    run_path = tmp_path / ".ralph" / "harness" / "runs" / "live-run.json"
    _write_json(
        dataset_path,
        {
            "_schema": "ralph_gold.harness_cases.v1",
            "generated_at": "2026-02-11T00:00:00+00:00",
            "source": {},
            "cases": [
                {
                    "case_id": "case-1",
                    "task_id": "T-1",
                    "expected": {},
                    "observed_history": {},
                },
                {
                    "case_id": "case-2",
                    "task_id": "",
                    "expected": {},
                    "observed_history": {},
                },
            ],
        },
    )

    monkeypatch.chdir(tmp_path)
    calls: list[dict] = []

    def fake_next_iteration_number(_root: Path) -> int:
        return len(calls) + 1

    def fake_run_iteration(project_root: Path, **kwargs):
        calls.append({"project_root": str(project_root), **kwargs})
        return SimpleNamespace(
            return_code=0,
            gates_ok=True,
            judge_ok=True,
            blocked=False,
            evidence_count=2,
            target_status="open",
            target_failure_reason=None,
        )

    monkeypatch.setattr("ralph_gold.loop.next_iteration_number", fake_next_iteration_number)
    monkeypatch.setattr("ralph_gold.loop.run_iteration", fake_run_iteration)

    args = SimpleNamespace(
        dataset=str(dataset_path),
        agent="codex",
        mode=None,
        isolation=None,
        max_cases=None,
        baseline=None,
        output=str(run_path),
        enforce_regression_threshold=False,
        execution_mode="live",
        strict_targeting=True,
        continue_on_target_error=False,
        bucket="all",
        report_breakdown=True,
    )

    rc = cli.cmd_harness_run(args)
    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["target_task_id"] == "T-1"
    assert calls[0]["allow_done_target"] is False
    assert calls[0]["allow_blocked_target"] is False

    payload = json.loads(run_path.read_text(encoding="utf-8"))
    assert payload["config"]["execution_mode"] == "live"
    assert payload["config"]["targeting_policy"] == "strict"
    assert payload["completion"]["total_cases"] == 2
    assert payload["completion"]["completed_cases"] == 2
    assert payload["completion"]["partial"] is True
    assert payload["completion"]["duration_seconds"] >= 0.0
    assert payload["results"][0]["status"] == "pass"
    assert payload["results"][1]["status"] == "error"


def test_harness_pin_command_creates_pinned_dataset(tmp_path: Path, monkeypatch) -> None:
    from ralph_gold import cli

    run_path = tmp_path / ".ralph" / "harness" / "runs" / "run.json"
    dataset_path = tmp_path / ".ralph" / "harness" / "cases.json"
    pinned_path = tmp_path / ".ralph" / "harness" / "pinned.json"
    _write_json(
        dataset_path,
        {
            "_schema": "ralph_gold.harness_cases.v1",
            "generated_at": "2026-02-11T00:00:00+00:00",
            "source": {},
            "cases": [
                {
                    "case_id": "case-1",
                    "task_id": "T-1",
                    "task_title": "Failure case",
                    "expected": {},
                    "observed_history": {"return_code": 1},
                }
            ],
        },
    )
    _write_json(
        run_path,
        {
            "_schema": "ralph_gold.harness_run.v1",
            "run_id": "harness-1",
            "started_at": "2026-02-11T00:00:00+00:00",
            "completed_at": "2026-02-11T00:01:00+00:00",
            "config": {},
            "dataset_ref": {"path": str(dataset_path)},
            "results": [
                {
                    "case_id": "case-1",
                    "status": "hard_fail",
                    "failure_category": "gate_failed",
                    "metrics": {"return_code": 1},
                }
            ],
            "aggregate": {"quality_score": 50.0},
        },
    )

    monkeypatch.chdir(tmp_path)
    args = SimpleNamespace(
        run=str(run_path),
        dataset=str(dataset_path),
        output=str(pinned_path),
        status=[],
        failure_category=[],
        limit=None,
        redact=True,
    )
    rc = cli.cmd_harness_pin(args)
    assert rc == 0
    payload = json.loads(pinned_path.read_text(encoding="utf-8"))
    assert payload["_schema"] == "ralph_gold.harness_cases.v1"
    assert len(payload["cases"]) == 1
    assert payload["cases"][0]["is_pinned"] is True


def test_harness_ci_baseline_missing_fails_when_required(
    tmp_path: Path, monkeypatch
) -> None:
    from ralph_gold import cli

    _write_json(
        tmp_path / ".ralph" / "state.json",
        {
            "history": [
                {
                    "ts": "2026-02-10T12:00:00+00:00",
                    "iteration": 1,
                    "agent": "codex",
                    "story_id": "task-1",
                    "gates_ok": True,
                    "judge_ok": True,
                    "blocked": False,
                    "timed_out": False,
                    "duration_seconds": 12.0,
                }
            ]
        },
    )
    monkeypatch.chdir(tmp_path)

    args = SimpleNamespace(
        days=365,
        limit=10,
        dataset=None,
        output=None,
        baseline=str(tmp_path / "missing-baseline.json"),
        agent="codex",
        mode=None,
        isolation=None,
        execution_mode="historical",
        max_cases=10,
        bucket="all",
        enforce_regression_threshold=True,
        require_baseline=True,
        baseline_missing_policy="fail",
        include_failures=True,
        redact=True,
        pinned_input=None,
        append_pinned=False,
        max_cases_per_task=2,
        strict_targeting=True,
        continue_on_target_error=True,
    )
    rc = cli.cmd_harness_ci(args)
    assert rc == 2
