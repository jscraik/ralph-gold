"""Harness dataset collection, scoring, and reporting utilities.

This module turns historical Ralph artifacts into a replay/evaluation dataset
and computes quality trajectories suitable for regression checks.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

HARNESS_CASES_SCHEMA_V1 = "ralph_gold.harness_cases.v1"
HARNESS_RUN_SCHEMA_V1 = "ralph_gold.harness_run.v1"

FAILURE_NONE = "none"
FAILURE_GATE_FAILED = "gate_failed"
FAILURE_JUDGE_FAILED = "judge_failed"
FAILURE_BLOCKED = "blocked"
FAILURE_NO_FILES_WRITTEN = "no_files_written"
FAILURE_TIMEOUT = "timeout"
FAILURE_OTHER = "other"

STATUS_PASS = "pass"
STATUS_SOFT_FAIL = "soft_fail"
STATUS_HARD_FAIL = "hard_fail"
STATUS_ERROR = "error"

BUCKET_ALL = "all"
BUCKET_SMALL = "small"
BUCKET_MEDIUM = "medium"
BUCKET_LARGE = "large"
VALID_BUCKETS = {BUCKET_SMALL, BUCKET_MEDIUM, BUCKET_LARGE}


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso8601(value: str) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_json_read(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("Failed to read JSON %s: %s", path, e)
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _compute_case_id(task_id: str, iteration: int, timestamp: str) -> str:
    base = f"{task_id}|{iteration}|{timestamp}"
    digest = hashlib.sha256(base.encode("utf-8", errors="replace")).hexdigest()
    return f"case-{digest[:16]}"


def _payload_sha256(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8", errors="replace")).hexdigest()


def _read_attempt_record(
    project_root: Path,
    story_id: str,
    attempt_id: Optional[str],
) -> Dict[str, Any]:
    if not story_id or not attempt_id:
        return {}
    safe_story = story_id.replace("/", "_")
    path = project_root / ".ralph" / "attempts" / safe_story / f"{attempt_id}.json"
    return _safe_json_read(path)


def _read_receipt_metrics(
    project_root: Path,
    receipts_dir_rel: Optional[str],
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "no_files_written": None,
        "evidence_count": 0,
        "runner_return_code": None,
    }
    if not receipts_dir_rel:
        return metrics

    receipts_dir = (project_root / receipts_dir_rel).resolve()
    if not receipts_dir.exists():
        return metrics

    no_files = _safe_json_read(receipts_dir / "no_files_written.json")
    if no_files:
        metrics["no_files_written"] = True
        if isinstance(no_files.get("agent_return_code"), int):
            metrics["runner_return_code"] = int(no_files["agent_return_code"])
    else:
        metrics["no_files_written"] = False

    evidence = _safe_json_read(receipts_dir / "evidence.json")
    citation_count = evidence.get("citation_count")
    if isinstance(citation_count, int):
        metrics["evidence_count"] = citation_count

    runner = _safe_json_read(receipts_dir / "runner.json")
    if isinstance(runner.get("returncode"), int):
        metrics["runner_return_code"] = int(runner["returncode"])

    return metrics


def _safe_duration(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def normalize_bucket(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in VALID_BUCKETS:
        return normalized
    return None


def classify_duration_bucket(
    duration_seconds: float,
    *,
    small_max_seconds: float = 120.0,
    medium_max_seconds: float = 600.0,
) -> str:
    duration = max(0.0, _safe_duration(duration_seconds))
    if duration <= max(0.0, float(small_max_seconds)):
        return BUCKET_SMALL
    if duration <= max(0.0, float(medium_max_seconds)):
        return BUCKET_MEDIUM
    return BUCKET_LARGE


def case_bucket(
    case: Dict[str, Any],
    *,
    small_max_seconds: float = 120.0,
    medium_max_seconds: float = 600.0,
) -> str:
    normalized = normalize_bucket(case.get("bucket"))
    if normalized is not None:
        return normalized
    observed = case.get("observed_history", {}) or {}
    duration_seconds = _safe_duration(observed.get("duration_seconds", 0.0))
    return classify_duration_bucket(
        duration_seconds,
        small_max_seconds=small_max_seconds,
        medium_max_seconds=medium_max_seconds,
    )


def _sort_history_entry(entry: Dict[str, Any]) -> Tuple[float, int, str, str]:
    ts = _parse_iso8601(str(entry.get("ts", "")))
    ts_key = ts.timestamp() if ts is not None else 0.0
    iteration = int(entry.get("iteration", 0) or 0)
    task_id = str(entry.get("story_id") or entry.get("task_id") or "").strip()
    case_id = _compute_case_id(task_id or "__none__", iteration, str(entry.get("ts", "")))
    return (-ts_key, -iteration, task_id, case_id)


def _redact_task_title(task_title: Any, redact: bool) -> Optional[str]:
    if not isinstance(task_title, str):
        return None
    if not redact:
        return task_title
    return task_title[:200]


def _normalize_case_shape(
    case: Dict[str, Any],
    *,
    redact: bool,
    small_max_seconds: float,
    medium_max_seconds: float,
    is_pinned: bool,
) -> Optional[Dict[str, Any]]:
    case_id = str(case.get("case_id") or "").strip()
    if not case_id:
        return None

    observed = case.get("observed_history", {})
    if not isinstance(observed, dict):
        observed = {}

    expected = case.get("expected", {})
    if not isinstance(expected, dict):
        expected = {}

    normalized = dict(case)
    normalized["case_id"] = case_id
    normalized["task_id"] = str(case.get("task_id") or "").strip()
    normalized["task_title"] = _redact_task_title(case.get("task_title"), redact)
    normalized["observed_history"] = observed
    normalized["expected"] = expected
    normalized["bucket"] = case_bucket(
        normalized,
        small_max_seconds=small_max_seconds,
        medium_max_seconds=medium_max_seconds,
    )
    normalized["is_pinned"] = bool(is_pinned)
    normalized["source_kind"] = "pinned" if is_pinned else str(case.get("source_kind") or "history")
    return normalized


def compute_dataset_health(
    cases: List[Dict[str, Any]],
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    if now is None:
        now = datetime.now(timezone.utc)

    total_cases = len(cases)
    if total_cases == 0:
        return {
            "total_cases": 0,
            "unique_task_ids": 0,
            "task_diversity_ratio": 0.0,
            "median_case_age_days": 0.0,
            "pinned_ratio": 0.0,
            "bucket_distribution": {
                BUCKET_SMALL: 0,
                BUCKET_MEDIUM: 0,
                BUCKET_LARGE: 0,
            },
        }

    task_ids = {
        str(case.get("task_id") or "").strip()
        for case in cases
        if str(case.get("task_id") or "").strip()
    }

    age_days: List[float] = []
    pinned_count = 0
    bucket_distribution = {
        BUCKET_SMALL: 0,
        BUCKET_MEDIUM: 0,
        BUCKET_LARGE: 0,
    }

    for case in cases:
        if bool(case.get("is_pinned", False)):
            pinned_count += 1
        bucket = normalize_bucket(case.get("bucket"))
        if bucket is not None:
            bucket_distribution[bucket] += 1

        ts = _parse_iso8601(str(case.get("timestamp", "")))
        if ts is None:
            continue
        delta = now - ts
        age_days.append(max(0.0, delta.total_seconds() / 86400.0))

    median_age = 0.0
    if age_days:
        age_days_sorted = sorted(age_days)
        mid = len(age_days_sorted) // 2
        if len(age_days_sorted) % 2 == 1:
            median_age = age_days_sorted[mid]
        else:
            median_age = (age_days_sorted[mid - 1] + age_days_sorted[mid]) / 2.0

    return {
        "total_cases": total_cases,
        "unique_task_ids": len(task_ids),
        "task_diversity_ratio": round(len(task_ids) / total_cases, 4),
        "median_case_age_days": round(median_age, 2),
        "pinned_ratio": round(pinned_count / total_cases, 4),
        "bucket_distribution": bucket_distribution,
    }


def classify_failure_category(
    return_code: int,
    gates_ok: Optional[bool],
    judge_ok: Optional[bool],
    blocked: bool,
    no_files_written: Optional[bool],
    timed_out: bool,
) -> str:
    if timed_out:
        return FAILURE_TIMEOUT
    if blocked:
        return FAILURE_BLOCKED
    if gates_ok is False:
        return FAILURE_GATE_FAILED
    if judge_ok is False:
        return FAILURE_JUDGE_FAILED
    if no_files_written is True:
        return FAILURE_NO_FILES_WRITTEN
    if return_code != 0:
        return FAILURE_OTHER
    return FAILURE_NONE


def _evaluate_case_status(case: Dict[str, Any]) -> Tuple[str, str]:
    observed = case.get("observed_history", {}) or {}
    expected = case.get("expected", {}) or {}

    return_code = int(observed.get("return_code", 0) or 0)
    gates_ok = observed.get("gates_ok")
    judge_ok = observed.get("judge_ok")
    blocked = bool(observed.get("blocked", False))
    timed_out = bool(observed.get("timed_out", False))
    no_files_written = observed.get("no_files_written")

    failure = classify_failure_category(
        return_code=return_code,
        gates_ok=gates_ok,
        judge_ok=judge_ok,
        blocked=blocked,
        no_files_written=no_files_written,
        timed_out=timed_out,
    )

    if failure in {
        FAILURE_TIMEOUT,
        FAILURE_BLOCKED,
        FAILURE_GATE_FAILED,
        FAILURE_JUDGE_FAILED,
        FAILURE_OTHER,
    }:
        return STATUS_HARD_FAIL, failure

    expected_files_written = expected.get("files_written")
    if expected_files_written is True and no_files_written is True:
        return STATUS_SOFT_FAIL, FAILURE_NO_FILES_WRITTEN

    return STATUS_PASS, failure


def collect_harness_cases(
    project_root: Path,
    days: int = 30,
    limit: int = 200,
    include_failures: bool = True,
    redact: bool = True,
    *,
    pinned_cases: Optional[List[Dict[str, Any]]] = None,
    append_pinned: bool = False,
    max_cases_per_task: int = 0,
    small_max_seconds: float = 120.0,
    medium_max_seconds: float = 600.0,
) -> Dict[str, Any]:
    """Collect harness cases from state history + receipts."""
    state_path = project_root / ".ralph" / "state.json"
    state = _safe_json_read(state_path)
    history_raw = state.get("history", [])
    history: List[Dict[str, Any]] = (
        [h for h in history_raw if isinstance(h, dict)] if isinstance(history_raw, list) else []
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(0, int(days)))
    history_sorted = sorted(history, key=_sort_history_entry)

    cases: List[Dict[str, Any]] = []
    per_task_counts: Dict[str, int] = {}
    max_per_task = max(0, int(max_cases_per_task))
    max_total = max(0, int(limit))

    for entry in history_sorted:
        ts_raw = str(entry.get("ts", ""))
        ts = _parse_iso8601(ts_raw)
        if ts is not None and ts < cutoff:
            continue

        story_id = str(entry.get("story_id") or entry.get("task_id") or "").strip()
        iteration = int(entry.get("iteration", 0) or 0)
        attempt_id = (
            str(entry.get("attempt_id")).strip()
            if entry.get("attempt_id") is not None
            else None
        )
        receipts_dir_rel = (
            str(entry.get("receipts_dir")).strip()
            if entry.get("receipts_dir") is not None
            else None
        )

        if max_per_task > 0 and story_id:
            current_count = per_task_counts.get(story_id, 0)
            if current_count >= max_per_task:
                continue

        attempt = _read_attempt_record(project_root, story_id, attempt_id)
        receipt_metrics = _read_receipt_metrics(project_root, receipts_dir_rel)

        return_code = int(
            attempt.get(
                "return_code",
                receipt_metrics.get("runner_return_code", 0) or 0,
            )
        )
        gates_ok = entry.get("gates_ok")
        judge_ok = entry.get("judge_ok")
        blocked = bool(entry.get("blocked", False))
        timed_out = bool(entry.get("timed_out", False))
        no_files_written = receipt_metrics.get("no_files_written")
        evidence_count = int(receipt_metrics.get("evidence_count", 0) or 0)

        task_title = _redact_task_title(attempt.get("task_title"), redact)

        expected_files_written: Optional[bool]
        if isinstance(no_files_written, bool):
            expected_files_written = not no_files_written
        else:
            expected_files_written = None

        duration_seconds = _safe_duration(entry.get("duration_seconds", 0.0))
        case = {
            "case_id": _compute_case_id(story_id or "__none__", iteration, ts_raw),
            "task_id": story_id,
            "task_title": task_title,
            "timestamp": ts_raw,
            "iteration": iteration,
            "agent": str(entry.get("agent") or ""),
            "mode": str(entry.get("mode") or entry.get("loop_mode") or ""),
            "expected": {
                "gates_ok": gates_ok if isinstance(gates_ok, bool) else None,
                "judge_ok": judge_ok if isinstance(judge_ok, bool) else None,
                "files_written": expected_files_written,
            },
            "observed_history": {
                "duration_seconds": duration_seconds,
                "return_code": return_code,
                "blocked": blocked,
                "gates_ok": gates_ok if isinstance(gates_ok, bool) else None,
                "judge_ok": judge_ok if isinstance(judge_ok, bool) else None,
                "no_files_written": (
                    no_files_written if isinstance(no_files_written, bool) else None
                ),
                "timed_out": timed_out,
                "evidence_count": evidence_count,
            },
            "bucket": classify_duration_bucket(
                duration_seconds,
                small_max_seconds=small_max_seconds,
                medium_max_seconds=medium_max_seconds,
            ),
            "is_pinned": False,
            "source_kind": "history",
        }
        _, failure = _evaluate_case_status(case)
        case["seed_failure_category"] = failure

        if not include_failures and failure != FAILURE_NONE:
            continue

        cases.append(case)
        if story_id:
            per_task_counts[story_id] = per_task_counts.get(story_id, 0) + 1

        if max_total > 0 and len(cases) >= max_total:
            break

    merged_pinned_count = 0
    if append_pinned and pinned_cases:
        case_index = {
            str(case.get("case_id") or ""): idx
            for idx, case in enumerate(cases)
            if str(case.get("case_id") or "")
        }
        for pinned in pinned_cases:
            if not isinstance(pinned, dict):
                continue
            normalized = _normalize_case_shape(
                pinned,
                redact=redact,
                small_max_seconds=small_max_seconds,
                medium_max_seconds=medium_max_seconds,
                is_pinned=True,
            )
            if normalized is None:
                continue
            case_id = str(normalized.get("case_id") or "")
            if case_id in case_index:
                cases[case_index[case_id]] = normalized
            else:
                case_index[case_id] = len(cases)
                cases.append(normalized)
            merged_pinned_count += 1

    dataset_health = compute_dataset_health(cases)

    return {
        "_schema": HARNESS_CASES_SCHEMA_V1,
        "generated_at": _iso_utc_now(),
        "source": {
            "state_path": str(state_path),
            "receipts_root": str(project_root / ".ralph" / "receipts"),
            "filters": {
                "days": int(days),
                "limit": int(limit),
                "include_failures": bool(include_failures),
                "redact": bool(redact),
                "max_cases_per_task": max_per_task,
                "append_pinned": bool(append_pinned),
            },
            "pinned": {
                "merged_count": merged_pinned_count,
                "input_count": len(pinned_cases or []),
            },
        },
        "dataset_health": dataset_health,
        "cases": cases,
    }


def _compute_rates(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    if total == 0:
        return {
            "total_cases": 0,
            "pass_rate": 0.0,
            "hard_fail_rate": 0.0,
            "soft_fail_rate": 0.0,
            "judge_fail_rate": 0.0,
            "no_files_rate": 0.0,
            "evidence_completeness_rate": 0.0,
            "quality_score": 0.0,
        }

    pass_count = sum(1 for r in results if r.get("status") == STATUS_PASS)
    hard_fail_count = sum(
        1
        for r in results
        if r.get("status") in {STATUS_HARD_FAIL, STATUS_ERROR}
    )
    soft_fail_count = sum(1 for r in results if r.get("status") == STATUS_SOFT_FAIL)
    judge_fail_count = sum(
        1 for r in results if r.get("failure_category") == FAILURE_JUDGE_FAILED
    )
    no_files_count = sum(
        1 for r in results if r.get("failure_category") == FAILURE_NO_FILES_WRITTEN
    )
    evidence_count = sum(
        1
        for r in results
        if int((r.get("metrics") or {}).get("evidence_count", 0) or 0) > 0
    )

    pass_rate = pass_count / total
    hard_fail_rate = hard_fail_count / total
    soft_fail_rate = soft_fail_count / total
    judge_fail_rate = judge_fail_count / total
    no_files_rate = no_files_count / total
    evidence_rate = evidence_count / total

    quality_score = 100.0 * (
        0.50 * pass_rate
        + 0.20 * (1.0 - hard_fail_rate)
        + 0.15 * (1.0 - judge_fail_rate)
        + 0.10 * (1.0 - no_files_rate)
        + 0.05 * evidence_rate
    )

    return {
        "total_cases": total,
        "pass_rate": round(pass_rate, 4),
        "hard_fail_rate": round(hard_fail_rate, 4),
        "soft_fail_rate": round(soft_fail_rate, 4),
        "judge_fail_rate": round(judge_fail_rate, 4),
        "no_files_rate": round(no_files_rate, 4),
        "evidence_completeness_rate": round(evidence_rate, 4),
        "quality_score": round(quality_score, 2),
    }


def compute_aggregate(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    aggregate = _compute_rates(results)

    breakdown: Dict[str, Dict[str, Any]] = {
        BUCKET_SMALL: _compute_rates([r for r in results if r.get("bucket") == BUCKET_SMALL]),
        BUCKET_MEDIUM: _compute_rates([r for r in results if r.get("bucket") == BUCKET_MEDIUM]),
        BUCKET_LARGE: _compute_rates([r for r in results if r.get("bucket") == BUCKET_LARGE]),
    }
    aggregate["breakdown_by_bucket"] = breakdown
    return aggregate


def compare_harness_runs(
    current_run: Dict[str, Any],
    baseline_run: Dict[str, Any],
    regression_threshold: float = 0.05,
) -> Dict[str, Any]:
    current = current_run.get("aggregate", {}) or {}
    baseline = baseline_run.get("aggregate", {}) or {}

    current_score = float(current.get("quality_score", 0.0) or 0.0)
    baseline_score = float(baseline.get("quality_score", 0.0) or 0.0)
    delta_score = round(current_score - baseline_score, 2)

    threshold_points = float(regression_threshold) * 100.0
    regressed = delta_score < -threshold_points

    return {
        "baseline_quality_score": baseline_score,
        "delta_quality_score": delta_score,
        "delta_pass_rate": round(
            float(current.get("pass_rate", 0.0) or 0.0)
            - float(baseline.get("pass_rate", 0.0) or 0.0),
            4,
        ),
        "delta_hard_fail_rate": round(
            float(current.get("hard_fail_rate", 0.0) or 0.0)
            - float(baseline.get("hard_fail_rate", 0.0) or 0.0),
            4,
        ),
        "delta_judge_fail_rate": round(
            float(current.get("judge_fail_rate", 0.0) or 0.0)
            - float(baseline.get("judge_fail_rate", 0.0) or 0.0),
            4,
        ),
        "delta_no_files_rate": round(
            float(current.get("no_files_rate", 0.0) or 0.0)
            - float(baseline.get("no_files_rate", 0.0) or 0.0),
            4,
        ),
        "regression_threshold": float(regression_threshold),
        "regressed": regressed,
    }


def filter_cases_by_bucket(
    cases: List[Dict[str, Any]],
    *,
    bucket: str,
    small_max_seconds: float = 120.0,
    medium_max_seconds: float = 600.0,
) -> List[Dict[str, Any]]:
    bucket_norm = str(bucket or BUCKET_ALL).strip().lower()
    if bucket_norm == BUCKET_ALL:
        return list(cases)

    if bucket_norm not in VALID_BUCKETS:
        raise ValueError(
            f"Invalid bucket filter: {bucket!r}. Must be one of: all, small, medium, large"
        )

    return [
        case
        for case in cases
        if case_bucket(
            case,
            small_max_seconds=small_max_seconds,
            medium_max_seconds=medium_max_seconds,
        )
        == bucket_norm
    ]


def evaluate_harness_dataset(
    dataset: Dict[str, Any],
    *,
    dataset_path: Path,
    agent: str,
    mode: str,
    isolation: str = "worktree",
    max_cases: Optional[int] = None,
    baseline_run: Optional[Dict[str, Any]] = None,
    baseline_path: Optional[Path] = None,
    regression_threshold: float = 0.05,
    bucket_filter: str = BUCKET_ALL,
    report_breakdown: bool = True,
    small_max_seconds: float = 120.0,
    medium_max_seconds: float = 600.0,
) -> Dict[str, Any]:
    """Evaluate a harness dataset and build a run artifact.

    Note: this v1 evaluation is based on deterministic historical replay from
    collected artifacts, not live agent re-execution.
    """
    started_at = _iso_utc_now()
    started_ts = time.time()

    cases_raw = dataset.get("cases", [])
    cases: List[Dict[str, Any]] = (
        [c for c in cases_raw if isinstance(c, dict)] if isinstance(cases_raw, list) else []
    )
    cases = filter_cases_by_bucket(
        cases,
        bucket=bucket_filter,
        small_max_seconds=small_max_seconds,
        medium_max_seconds=medium_max_seconds,
    )
    if max_cases is not None:
        cases = cases[: max(0, int(max_cases))]

    results: List[Dict[str, Any]] = []
    for case in cases:
        status, failure = _evaluate_case_status(case)
        observed = case.get("observed_history", {}) or {}
        results.append(
            {
                "case_id": str(case.get("case_id") or ""),
                "status": status,
                "failure_category": failure,
                "bucket": case_bucket(
                    case,
                    small_max_seconds=small_max_seconds,
                    medium_max_seconds=medium_max_seconds,
                ),
                "metrics": {
                    "duration_seconds": _safe_duration(observed.get("duration_seconds", 0.0)),
                    "return_code": int(observed.get("return_code", 0) or 0),
                    "gates_ok": observed.get("gates_ok"),
                    "judge_ok": observed.get("judge_ok"),
                    "blocked": bool(observed.get("blocked", False)),
                    "no_files_written": observed.get("no_files_written"),
                    "timed_out": bool(observed.get("timed_out", False)),
                    "evidence_count": int(observed.get("evidence_count", 0) or 0),
                },
                "notes": None,
            }
        )

    aggregate = compute_aggregate(results)
    if not report_breakdown:
        aggregate.pop("breakdown_by_bucket", None)

    completed_at = _iso_utc_now()

    run_payload: Dict[str, Any] = {
        "_schema": HARNESS_RUN_SCHEMA_V1,
        "run_id": f"harness-{int(started_ts)}",
        "started_at": started_at,
        "completed_at": completed_at,
        "config": {
            "agent": agent,
            "mode": mode,
            "isolation": isolation,
            "max_cases": max_cases,
            "execution_mode": "historical_replay",
            "regression_threshold": float(regression_threshold),
            "bucket_filter": bucket_filter,
            "report_breakdown": bool(report_breakdown),
        },
        "dataset_ref": {
            "path": str(dataset_path),
            "sha256": _payload_sha256(dataset),
        },
        "dataset_health": dataset.get("dataset_health") or compute_dataset_health(cases),
        "results": results,
        "aggregate": aggregate,
    }

    if baseline_run is not None and baseline_path is not None:
        run_payload["baseline_ref"] = {
            "path": str(baseline_path),
            "sha256": _payload_sha256(baseline_run),
        }
        run_payload["comparison"] = compare_harness_runs(
            current_run=run_payload,
            baseline_run=baseline_run,
            regression_threshold=regression_threshold,
        )

    return run_payload


def format_harness_report(
    run_payload: Dict[str, Any],
    *,
    include_comparison: bool = True,
    include_breakdown: bool = True,
) -> str:
    aggregate = run_payload.get("aggregate", {}) or {}
    lines: List[str] = []
    lines.append("=" * 60)
    lines.append("Ralph Gold - Harness Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Run ID:                {run_payload.get('run_id', '-')}")
    lines.append(f"Execution mode:        {(run_payload.get('config') or {}).get('execution_mode', '-')}")
    lines.append(f"Total cases:           {aggregate.get('total_cases', 0)}")
    lines.append(f"Quality score:         {aggregate.get('quality_score', 0.0)}")
    lines.append(f"Pass rate:             {aggregate.get('pass_rate', 0.0):.2%}")
    lines.append(f"Hard fail rate:        {aggregate.get('hard_fail_rate', 0.0):.2%}")
    lines.append(f"Judge fail rate:       {aggregate.get('judge_fail_rate', 0.0):.2%}")
    lines.append(f"No files rate:         {aggregate.get('no_files_rate', 0.0):.2%}")
    lines.append(
        f"Evidence completeness: {aggregate.get('evidence_completeness_rate', 0.0):.2%}"
    )

    dataset_health = run_payload.get("dataset_health")
    if isinstance(dataset_health, dict):
        lines.append("")
        lines.append("Dataset health:")
        lines.append(f"  Unique task ids:     {dataset_health.get('unique_task_ids', 0)}")
        lines.append(f"  Task diversity:      {float(dataset_health.get('task_diversity_ratio', 0.0)):.2%}")
        lines.append(f"  Median age (days):   {dataset_health.get('median_case_age_days', 0.0)}")
        lines.append(f"  Pinned ratio:        {float(dataset_health.get('pinned_ratio', 0.0)):.2%}")

    if include_breakdown:
        breakdown = aggregate.get("breakdown_by_bucket")
        if isinstance(breakdown, dict):
            lines.append("")
            lines.append("Breakdown by bucket:")
            for bucket_name in (BUCKET_SMALL, BUCKET_MEDIUM, BUCKET_LARGE):
                bucket_metrics = breakdown.get(bucket_name, {}) or {}
                lines.append(
                    f"  {bucket_name:>6}: cases={bucket_metrics.get('total_cases', 0)} "
                    f"quality={bucket_metrics.get('quality_score', 0.0)} "
                    f"pass={float(bucket_metrics.get('pass_rate', 0.0)):.2%}"
                )

    if include_comparison:
        comparison = run_payload.get("comparison")
        if isinstance(comparison, dict):
            lines.append("")
            lines.append("Comparison vs baseline:")
            lines.append(
                f"  Δ quality score:     {comparison.get('delta_quality_score', 0.0)}"
            )
            lines.append(
                f"  Δ pass rate:         {comparison.get('delta_pass_rate', 0.0):+.2%}"
            )
            lines.append(
                f"  Δ hard fail rate:    {comparison.get('delta_hard_fail_rate', 0.0):+.2%}"
            )
            lines.append(
                f"  Regressed:           {comparison.get('regressed', False)}"
            )

    return "\n".join(lines) + "\n"


def report_to_csv(run_payload: Dict[str, Any]) -> str:
    aggregate = run_payload.get("aggregate", {}) or {}
    rows = [
        ["metric", "value"],
        ["run_id", str(run_payload.get("run_id", ""))],
        ["total_cases", str(aggregate.get("total_cases", 0))],
        ["quality_score", str(aggregate.get("quality_score", 0.0))],
        ["pass_rate", str(aggregate.get("pass_rate", 0.0))],
        ["hard_fail_rate", str(aggregate.get("hard_fail_rate", 0.0))],
        ["judge_fail_rate", str(aggregate.get("judge_fail_rate", 0.0))],
        ["no_files_rate", str(aggregate.get("no_files_rate", 0.0))],
        [
            "evidence_completeness_rate",
            str(aggregate.get("evidence_completeness_rate", 0.0)),
        ],
    ]

    dataset_health = run_payload.get("dataset_health")
    if isinstance(dataset_health, dict):
        rows.extend(
            [
                ["dataset_unique_task_ids", str(dataset_health.get("unique_task_ids", 0))],
                ["dataset_task_diversity_ratio", str(dataset_health.get("task_diversity_ratio", 0.0))],
                ["dataset_median_case_age_days", str(dataset_health.get("median_case_age_days", 0.0))],
                ["dataset_pinned_ratio", str(dataset_health.get("pinned_ratio", 0.0))],
            ]
        )

    breakdown = aggregate.get("breakdown_by_bucket")
    if isinstance(breakdown, dict):
        for bucket_name in (BUCKET_SMALL, BUCKET_MEDIUM, BUCKET_LARGE):
            bucket_metrics = breakdown.get(bucket_name, {}) or {}
            rows.extend(
                [
                    [f"{bucket_name}_total_cases", str(bucket_metrics.get("total_cases", 0))],
                    [f"{bucket_name}_quality_score", str(bucket_metrics.get("quality_score", 0.0))],
                    [f"{bucket_name}_pass_rate", str(bucket_metrics.get("pass_rate", 0.0))],
                ]
            )

    comparison = run_payload.get("comparison")
    if isinstance(comparison, dict):
        rows.extend(
            [
                ["delta_quality_score", str(comparison.get("delta_quality_score", 0.0))],
                ["delta_pass_rate", str(comparison.get("delta_pass_rate", 0.0))],
                [
                    "delta_hard_fail_rate",
                    str(comparison.get("delta_hard_fail_rate", 0.0)),
                ],
                ["regressed", str(bool(comparison.get("regressed", False))).lower()],
            ]
        )

    return "\n".join([",".join(row) for row in rows]) + "\n"
