"""Unit tests for harness collection/evaluation/storage."""

from __future__ import annotations

import json
from pathlib import Path

from ralph_gold.harness import (
    BUCKET_SMALL,
    HARNESS_CASES_SCHEMA_V1,
    HARNESS_RUN_SCHEMA_V1,
    STATUS_ERROR,
    STATUS_PASS,
    collect_harness_cases,
    compute_aggregate,
    evaluate_harness_dataset,
)
from ralph_gold.harness_store import load_cases, load_run, save_cases, save_run


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_collect_harness_cases_from_state_and_receipts(tmp_path: Path) -> None:
    """Collects a case and enriches it from attempt/receipt artifacts."""
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
        {
            "return_code": 0,
            "task_title": "Implement harness dataset",
        },
    )
    _write_json(
        tmp_path / ".ralph" / "receipts" / "task-1" / "attempt-1" / "runner.json",
        {"returncode": 0},
    )
    _write_json(
        tmp_path / ".ralph" / "receipts" / "task-1" / "attempt-1" / "evidence.json",
        {"citation_count": 3},
    )

    payload = collect_harness_cases(tmp_path, days=365, limit=10, include_failures=True)
    assert payload["_schema"] == HARNESS_CASES_SCHEMA_V1
    assert len(payload["cases"]) == 1

    case = payload["cases"][0]
    assert case["task_id"] == "task-1"
    assert case["task_title"] == "Implement harness dataset"
    assert case["observed_history"]["evidence_count"] == 3
    assert case["observed_history"]["return_code"] == 0
    assert case["seed_failure_category"] == "none"
    assert case["bucket"] == BUCKET_SMALL
    assert payload["dataset_health"]["task_diversity_ratio"] == 1.0


def test_collect_harness_cases_excludes_failures_when_requested(tmp_path: Path) -> None:
    """Exclude-failures mode removes failed historical cases."""
    _write_json(
        tmp_path / ".ralph" / "state.json",
        {
            "history": [
                {
                    "ts": "2026-02-10T12:00:00+00:00",
                    "iteration": 1,
                    "agent": "codex",
                    "story_id": "task-1",
                    "gates_ok": False,
                    "judge_ok": True,
                    "blocked": False,
                    "timed_out": False,
                    "duration_seconds": 5.0,
                    "attempt_id": "attempt-1",
                    "receipts_dir": ".ralph/receipts/task-1/attempt-1",
                }
            ]
        },
    )

    payload = collect_harness_cases(
        tmp_path,
        days=365,
        limit=10,
        include_failures=False,
    )
    assert payload["_schema"] == HARNESS_CASES_SCHEMA_V1
    assert payload["cases"] == []


def test_evaluate_harness_dataset_with_baseline_comparison(tmp_path: Path) -> None:
    """Computes aggregate metrics and regression comparison."""
    dataset = {
        "_schema": HARNESS_CASES_SCHEMA_V1,
        "generated_at": "2026-02-10T12:00:00+00:00",
        "source": {},
        "cases": [
            {
                "case_id": "case-pass",
                "task_id": "task-pass",
                "expected": {"files_written": True},
                "observed_history": {
                    "return_code": 0,
                    "gates_ok": True,
                    "judge_ok": True,
                    "blocked": False,
                    "timed_out": False,
                    "no_files_written": False,
                    "evidence_count": 1,
                },
            },
            {
                "case_id": "case-fail",
                "task_id": "task-fail",
                "expected": {"files_written": True},
                "observed_history": {
                    "return_code": 0,
                    "gates_ok": False,
                    "judge_ok": True,
                    "blocked": False,
                    "timed_out": False,
                    "no_files_written": False,
                    "evidence_count": 0,
                },
            },
        ],
    }
    baseline_run = {
        "_schema": HARNESS_RUN_SCHEMA_V1,
        "aggregate": {
            "quality_score": 95.0,
            "pass_rate": 0.95,
            "hard_fail_rate": 0.02,
            "judge_fail_rate": 0.01,
            "no_files_rate": 0.02,
        },
    }

    run_payload = evaluate_harness_dataset(
        dataset,
        dataset_path=tmp_path / "cases.json",
        agent="codex",
        mode="speed",
        baseline_run=baseline_run,
        baseline_path=tmp_path / "baseline.json",
        regression_threshold=0.05,
    )

    assert run_payload["_schema"] == HARNESS_RUN_SCHEMA_V1
    assert run_payload["aggregate"]["total_cases"] == 2
    assert "comparison" in run_payload
    assert run_payload["comparison"]["regressed"] is True


def test_harness_store_roundtrip(tmp_path: Path) -> None:
    """Valid payloads round-trip; invalid payloads fail fast."""
    cases_payload = {
        "_schema": HARNESS_CASES_SCHEMA_V1,
        "generated_at": "2026-02-10T12:00:00+00:00",
        "source": {"state_path": "state.json", "receipts_root": "receipts"},
        "cases": [
            {
                "case_id": "case-1",
                "task_id": "task-1",
                "expected": {},
                "observed_history": {},
            }
        ],
    }
    run_payload = {
        "_schema": HARNESS_RUN_SCHEMA_V1,
        "run_id": "run-1",
        "started_at": "2026-02-10T12:00:00+00:00",
        "completed_at": "2026-02-10T12:01:00+00:00",
        "config": {},
        "dataset_ref": {},
        "results": [],
        "aggregate": {"quality_score": 0.0},
    }

    cases_path = tmp_path / "cases.json"
    run_path = tmp_path / "run.json"
    save_cases(cases_path, cases_payload)
    save_run(run_path, run_payload)

    loaded_cases = load_cases(cases_path)
    loaded_run = load_run(run_path)

    assert loaded_cases["_schema"] == HARNESS_CASES_SCHEMA_V1
    assert loaded_run["_schema"] == HARNESS_RUN_SCHEMA_V1


def test_compute_aggregate_treats_errors_as_hard_fail() -> None:
    results = [
        {
            "status": STATUS_PASS,
            "failure_category": "none",
            "metrics": {"evidence_count": 1},
        },
        {
            "status": STATUS_ERROR,
            "failure_category": "target_resolution_error",
            "metrics": {"evidence_count": 0},
        },
    ]

    aggregate = compute_aggregate(results)

    assert aggregate["total_cases"] == 2
    assert aggregate["pass_rate"] == 0.5
    assert aggregate["hard_fail_rate"] == 0.5
    assert "breakdown_by_bucket" in aggregate


def test_collect_harness_cases_respects_max_cases_per_task_and_appends_pinned(
    tmp_path: Path,
) -> None:
    _write_json(
        tmp_path / ".ralph" / "state.json",
        {
            "history": [
                {
                    "ts": "2026-02-10T12:00:00+00:00",
                    "iteration": 2,
                    "agent": "codex",
                    "story_id": "task-1",
                    "gates_ok": True,
                    "judge_ok": True,
                    "blocked": False,
                    "timed_out": False,
                    "duration_seconds": 30.0,
                },
                {
                    "ts": "2026-02-09T12:00:00+00:00",
                    "iteration": 1,
                    "agent": "codex",
                    "story_id": "task-1",
                    "gates_ok": True,
                    "judge_ok": True,
                    "blocked": False,
                    "timed_out": False,
                    "duration_seconds": 40.0,
                },
            ]
        },
    )

    payload = collect_harness_cases(
        tmp_path,
        days=365,
        limit=10,
        include_failures=True,
        max_cases_per_task=1,
        append_pinned=True,
        pinned_cases=[
            {
                "case_id": "pinned-1",
                "task_id": "task-pinned",
                "expected": {},
                "observed_history": {"duration_seconds": 5.0, "return_code": 0},
            }
        ],
    )
    assert len(payload["cases"]) == 2
    assert payload["source"]["pinned"]["merged_count"] == 1
    assert payload["dataset_health"]["total_cases"] == 2
    assert payload["cases"][1]["is_pinned"] is True


def test_evaluate_harness_dataset_bucket_filter_and_breakdown(tmp_path: Path) -> None:
    dataset = {
        "_schema": HARNESS_CASES_SCHEMA_V1,
        "generated_at": "2026-02-10T12:00:00+00:00",
        "source": {},
        "cases": [
            {
                "case_id": "small-pass",
                "task_id": "task-small",
                "bucket": "small",
                "expected": {"files_written": True},
                "observed_history": {
                    "duration_seconds": 10.0,
                    "return_code": 0,
                    "gates_ok": True,
                    "judge_ok": True,
                    "blocked": False,
                    "timed_out": False,
                    "no_files_written": False,
                    "evidence_count": 1,
                },
            },
            {
                "case_id": "large-fail",
                "task_id": "task-large",
                "bucket": "large",
                "expected": {"files_written": True},
                "observed_history": {
                    "duration_seconds": 900.0,
                    "return_code": 0,
                    "gates_ok": False,
                    "judge_ok": True,
                    "blocked": False,
                    "timed_out": False,
                    "no_files_written": False,
                    "evidence_count": 0,
                },
            },
        ],
    }

    run_payload = evaluate_harness_dataset(
        dataset,
        dataset_path=tmp_path / "cases.json",
        agent="codex",
        mode="speed",
        bucket_filter="small",
        report_breakdown=False,
    )

    assert run_payload["aggregate"]["total_cases"] == 1
    assert "breakdown_by_bucket" not in run_payload["aggregate"]
    assert run_payload["results"][0]["bucket"] == "small"
