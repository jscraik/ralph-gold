from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from ..config import load_config
from ..output import get_output_config, print_json_output, print_output


def _project_root() -> Path:
    return Path(os.getcwd()).resolve()

def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def cmd_harness_collect(args: argparse.Namespace) -> int:
    """Collect harness cases from Ralph history artifacts."""
    root = _project_root()
    cfg = load_config(root)

    from ..harness import collect_harness_cases
    from ..harness_store import load_cases, save_cases

    days = (
        int(args.days)
        if args.days is not None
        else int(cfg.harness.default_days)
    )
    limit = (
        int(args.limit)
        if args.limit is not None
        else int(cfg.harness.default_limit)
    )
    output_path = _resolve_path(
        root,
        str(args.output) if args.output else str(cfg.harness.dataset_path),
    )
    append_pinned = (
        bool(args.append_pinned)
        if args.append_pinned is not None
        else bool(cfg.harness.append_pinned_by_default)
    )
    pinned_input_path = _resolve_path(
        root,
        str(args.pinned_input)
        if args.pinned_input
        else str(cfg.harness.pinned_dataset_path),
    )
    max_cases_per_task = (
        int(args.max_cases_per_task)
        if args.max_cases_per_task is not None
        else int(cfg.harness.max_cases_per_task)
    )

    pinned_cases = None
    if append_pinned and pinned_input_path.exists():
        try:
            pinned_payload = load_cases(pinned_input_path)
            pinned_cases_raw = pinned_payload.get("cases", [])
            if isinstance(pinned_cases_raw, list):
                pinned_cases = [c for c in pinned_cases_raw if isinstance(c, dict)]
        except Exception as e:
            print_output(f"Invalid pinned dataset payload: {e}", level="error")
            return 2

    try:
        payload = collect_harness_cases(
            project_root=root,
            days=days,
            limit=limit,
            include_failures=bool(args.include_failures),
            redact=bool(args.redact),
            pinned_cases=pinned_cases,
            append_pinned=append_pinned,
            max_cases_per_task=max_cases_per_task,
            small_max_seconds=float(cfg.harness.buckets.small_max_seconds),
            medium_max_seconds=float(cfg.harness.buckets.medium_max_seconds),
        )
        save_cases(output_path, payload)
    except Exception as e:
        print_output(f"Error collecting harness cases: {e}", level="error")
        return 2

    if get_output_config().format == "json":
        print_json_output(
            {
                "cmd": "harness_collect",
                "output": str(output_path),
                "cases": len(payload.get("cases", [])),
                "days": days,
                "limit": limit,
                "append_pinned": append_pinned,
                "pinned_input": str(pinned_input_path),
                "max_cases_per_task": max_cases_per_task,
                "dataset_health": payload.get("dataset_health"),
            }
        )
        return 0

    print_output(f"Harness dataset saved: {output_path}", level="normal")
    print_output(f"Cases collected: {len(payload.get('cases', []))}", level="normal")
    dataset_health = payload.get("dataset_health", {}) or {}
    if isinstance(dataset_health, dict):
        print_output(
            "Dataset health: "
            f"tasks={dataset_health.get('unique_task_ids', 0)} "
            f"diversity={float(dataset_health.get('task_diversity_ratio', 0.0)):.2%} "
            f"pinned={float(dataset_health.get('pinned_ratio', 0.0)):.2%}",
            level="normal",
        )
    return 0


def cmd_harness_run(args: argparse.Namespace) -> int:
    """Evaluate harness dataset and create a run report."""
    root = _project_root()
    cfg = load_config(root)

    from ..harness import (
        BUCKET_ALL,
        STATUS_ERROR,
        STATUS_HARD_FAIL,
        STATUS_PASS,
        case_bucket,
        classify_failure_category,
        compare_harness_runs,
        compute_aggregate,
        evaluate_harness_dataset,
        filter_cases_by_bucket,
        format_harness_report,
    )
    from ..harness_store import load_cases, load_run, save_run

    dataset_path = _resolve_path(
        root,
        str(args.dataset) if args.dataset else str(cfg.harness.dataset_path),
    )
    if not dataset_path.exists():
        print_output(f"Dataset not found: {dataset_path}", level="error")
        return 2

    baseline_path: Path | None = None
    baseline_payload = None
    baseline_arg = args.baseline or None
    if baseline_arg is None and str(cfg.harness.baseline_run_path).strip():
        candidate = _resolve_path(root, str(cfg.harness.baseline_run_path))
        if candidate.exists():
            baseline_arg = str(candidate)

    if baseline_arg:
        baseline_path = _resolve_path(root, str(baseline_arg))
        if not baseline_path.exists():
            print_output(f"Baseline run not found: {baseline_path}", level="error")
            return 2
        try:
            baseline_payload = load_run(baseline_path)
        except Exception as e:
            print_output(f"Invalid baseline run payload: {e}", level="error")
            return 2

    try:
        dataset_payload = load_cases(dataset_path)
    except Exception as e:
        print_output(f"Invalid dataset payload: {e}", level="error")
        return 2

    mode = (
        str(args.mode).strip().lower()
        if args.mode is not None
        else str(cfg.loop.mode)
    )
    isolation = (
        str(args.isolation).strip().lower()
        if args.isolation is not None
        else str(cfg.harness.replay.default_isolation)
    )
    max_cases = int(args.max_cases) if args.max_cases is not None else None
    threshold = float(cfg.harness.regression_threshold)
    execution_mode = str(args.execution_mode or "historical").strip().lower()
    bucket_filter = str(args.bucket or BUCKET_ALL).strip().lower()
    report_breakdown = bool(args.report_breakdown)

    if execution_mode == "live":
        from ..loop import next_iteration_number, run_iteration

        live_started_ts = time.time()
        live_started_at = datetime.now(timezone.utc).isoformat()
        cases_raw = dataset_payload.get("cases", [])
        cases_all = (
            [c for c in cases_raw if isinstance(c, dict)]
            if isinstance(cases_raw, list)
            else []
        )
        try:
            cases = filter_cases_by_bucket(
                cases_all,
                bucket=bucket_filter,
                small_max_seconds=float(cfg.harness.buckets.small_max_seconds),
                medium_max_seconds=float(cfg.harness.buckets.medium_max_seconds),
            )
        except ValueError as e:
            print_output(str(e), level="error")
            return 2
        if max_cases is not None:
            cases = cases[: max(0, int(max_cases))]

        strict_targeting = bool(args.strict_targeting)
        continue_on_target_error = bool(args.continue_on_target_error)
        results: list[dict] = []
        aborted_early = False
        for case in cases:
            case_started_ts = time.time()
            task_id = str(case.get("task_id") or "").strip()
            case_id = str(case.get("case_id") or "")
            if not task_id:
                results.append(
                    {
                        "case_id": case_id,
                        "status": STATUS_ERROR,
                        "failure_category": "target_resolution_error",
                        "bucket": case_bucket(
                            case,
                            small_max_seconds=float(cfg.harness.buckets.small_max_seconds),
                            medium_max_seconds=float(cfg.harness.buckets.medium_max_seconds),
                        ),
                        "target_status": "missing",
                        "target_failure_reason": "missing_target",
                        "metrics": {
                            "duration_seconds": round(
                                time.time() - case_started_ts, 4
                            ),
                            "return_code": 2,
                            "gates_ok": None,
                            "judge_ok": None,
                            "blocked": False,
                            "no_files_written": None,
                            "timed_out": False,
                            "evidence_count": 0,
                        },
                        "notes": "case missing task_id",
                    }
                )
                if not continue_on_target_error:
                    aborted_early = True
                    break
                continue

            try:
                iter_n = next_iteration_number(root)
                res = run_iteration(
                    root,
                    agent=str(args.agent).strip(),
                    cfg=cfg,
                    iteration=iter_n,
                    target_task_id=task_id,
                    allow_done_target=not strict_targeting,
                    allow_blocked_target=not strict_targeting,
                    reopen_if_needed=False,
                )

                if res.target_failure_reason:
                    status = STATUS_ERROR
                    failure = "target_resolution_error"
                else:
                    failure = classify_failure_category(
                        return_code=int(res.return_code),
                        gates_ok=res.gates_ok,
                        judge_ok=res.judge_ok,
                        blocked=bool(res.blocked),
                        no_files_written=None,
                        timed_out=False,
                    )
                    status = STATUS_PASS
                    if failure != "none":
                        status = STATUS_HARD_FAIL

                results.append(
                    {
                        "case_id": case_id,
                        "status": status,
                        "failure_category": failure,
                        "bucket": case_bucket(
                            case,
                            small_max_seconds=float(cfg.harness.buckets.small_max_seconds),
                            medium_max_seconds=float(cfg.harness.buckets.medium_max_seconds),
                        ),
                        "target_status": res.target_status,
                        "target_failure_reason": res.target_failure_reason,
                        "metrics": {
                            "duration_seconds": round(
                                time.time() - case_started_ts, 4
                            ),
                            "return_code": int(res.return_code),
                            "gates_ok": res.gates_ok,
                            "judge_ok": res.judge_ok,
                            "blocked": bool(res.blocked),
                            "no_files_written": None,
                            "timed_out": False,
                            "evidence_count": int(res.evidence_count),
                        },
                        "notes": None,
                    }
                )

                if res.target_failure_reason and not continue_on_target_error:
                    aborted_early = True
                    break
            except Exception as e:
                results.append(
                    {
                        "case_id": case_id,
                        "status": STATUS_ERROR,
                        "failure_category": "target_resolution_error",
                        "bucket": case_bucket(
                            case,
                            small_max_seconds=float(cfg.harness.buckets.small_max_seconds),
                            medium_max_seconds=float(cfg.harness.buckets.medium_max_seconds),
                        ),
                        "target_status": "missing",
                        "target_failure_reason": "target_resolution_error",
                        "metrics": {
                            "duration_seconds": round(
                                time.time() - case_started_ts, 4
                            ),
                            "return_code": 2,
                            "gates_ok": None,
                            "judge_ok": None,
                            "blocked": False,
                            "no_files_written": None,
                            "timed_out": False,
                            "evidence_count": 0,
                        },
                        "notes": str(e),
                    }
                )
                if not continue_on_target_error:
                    aborted_early = True
                    break

        aggregate = compute_aggregate(results)
        if not report_breakdown:
            aggregate.pop("breakdown_by_bucket", None)
        errored_cases = sum(1 for r in results if r.get("status") == STATUS_ERROR)
        live_completed_ts = time.time()
        live_completed_at = datetime.now(timezone.utc).isoformat()
        partial = aborted_early or (len(results) < len(cases))
        run_payload = {
            "_schema": "ralph_gold.harness_run.v1",
            "run_id": f"harness-{int(live_started_ts)}",
            "started_at": live_started_at,
            "completed_at": live_completed_at,
            "config": {
                "agent": str(args.agent).strip(),
                "mode": mode,
                "isolation": isolation,
                "max_cases": max_cases,
                "execution_mode": "live",
                "targeting_policy": "strict" if strict_targeting else "override",
                "continue_on_target_error": continue_on_target_error,
                "regression_threshold": float(threshold),
                "bucket_filter": bucket_filter,
                "report_breakdown": report_breakdown,
            },
            "dataset_ref": {
                "path": str(dataset_path),
            },
            "dataset_health": dataset_payload.get("dataset_health"),
            "results": results,
            "aggregate": aggregate,
            "completion": {
                "total_cases": len(cases),
                "completed_cases": len(results),
                "errored_cases": errored_cases,
                "partial": partial,
                "duration_seconds": round(live_completed_ts - live_started_ts, 4),
            },
        }
        if baseline_payload is not None and baseline_path is not None:
            run_payload["baseline_ref"] = {"path": str(baseline_path)}
            run_payload["comparison"] = compare_harness_runs(
                current_run=run_payload,
                baseline_run=baseline_payload,
                regression_threshold=threshold,
            )
    else:
        run_payload = evaluate_harness_dataset(
            dataset_payload,
            dataset_path=dataset_path,
            agent=str(args.agent).strip(),
            mode=mode,
            isolation=isolation,
            max_cases=max_cases,
            baseline_run=baseline_payload,
            baseline_path=baseline_path,
            regression_threshold=threshold,
            bucket_filter=bucket_filter,
            report_breakdown=report_breakdown,
            small_max_seconds=float(cfg.harness.buckets.small_max_seconds),
            medium_max_seconds=float(cfg.harness.buckets.medium_max_seconds),
        )

    if args.output:
        output_path = _resolve_path(root, str(args.output))
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = _resolve_path(root, str(cfg.harness.runs_dir)) / f"{ts}.json"

    try:
        save_run(output_path, run_payload)
    except Exception as e:
        print_output(f"Error saving harness run: {e}", level="error")
        return 2

    comparison = run_payload.get("comparison", {}) or {}
    regressed = bool(comparison.get("regressed", False))

    if get_output_config().format == "json":
        print_json_output(
            {
                "cmd": "harness_run",
                "output": str(output_path),
                "aggregate": run_payload.get("aggregate", {}),
                "comparison": comparison if comparison else None,
                "regressed": regressed,
            }
        )
    else:
        print_output(
            format_harness_report(
                run_payload,
                include_breakdown=report_breakdown,
            ),
            level="normal",
        )
        print_output(f"Saved run: {output_path}", level="normal")

    if bool(args.enforce_regression_threshold) and regressed:
        print_output("Regression threshold breached.", level="error")
        return 1
    return 0


def cmd_harness_report(args: argparse.Namespace) -> int:
    """Render a harness run report in text/json/csv."""
    root = _project_root()
    cfg = load_config(root)

    from ..harness import compare_harness_runs, format_harness_report, report_to_csv
    from ..harness_store import load_run

    report_format = str(args.report_format or "text").strip().lower()
    if report_format not in {"text", "json", "csv"}:
        print_output(f"Invalid --format: {report_format}", level="error")
        return 2

    if args.input:
        input_path = _resolve_path(root, str(args.input))
    else:
        runs_dir = _resolve_path(root, str(cfg.harness.runs_dir))
        candidates = sorted(runs_dir.glob("*.json")) if runs_dir.exists() else []
        if not candidates:
            print_output("No harness run files found.", level="error")
            return 2
        input_path = candidates[-1]

    try:
        run_payload = load_run(input_path)
    except Exception as e:
        print_output(f"Invalid run payload: {e}", level="error")
        return 2

    if args.baseline:
        baseline_path = _resolve_path(root, str(args.baseline))
        if not baseline_path.exists():
            print_output(f"Baseline run not found: {baseline_path}", level="error")
            return 2
        try:
            baseline_run = load_run(baseline_path)
        except Exception as e:
            print_output(f"Invalid baseline payload: {e}", level="error")
            return 2
        run_payload["comparison"] = compare_harness_runs(
            current_run=run_payload,
            baseline_run=baseline_run,
            regression_threshold=float(cfg.harness.regression_threshold),
        )

    if report_format == "json":
        print_json_output(
            {
                "cmd": "harness_report",
                "input": str(input_path),
                "report": run_payload,
            }
        )
        return 0

    if report_format == "csv":
        print_output(report_to_csv(run_payload), level="normal")
        return 0

    print_output(format_harness_report(run_payload), level="normal")
    return 0


def cmd_harness_pin(args: argparse.Namespace) -> int:
    """Promote failing harness run cases into a pinned dataset."""
    root = _project_root()
    cfg = load_config(root)

    from ..harness import HARNESS_CASES_SCHEMA_V1
    from ..harness_store import load_cases, load_run, save_cases

    run_path = _resolve_path(root, str(args.run))
    if not run_path.exists():
        print_output(f"Run payload not found: {run_path}", level="error")
        return 2

    try:
        run_payload = load_run(run_path)
    except Exception as e:
        print_output(f"Invalid run payload: {e}", level="error")
        return 2

    dataset_path = None
    if args.dataset:
        dataset_path = _resolve_path(root, str(args.dataset))
    else:
        dataset_ref = run_payload.get("dataset_ref", {}) or {}
        dataset_ref_path = dataset_ref.get("path")
        if isinstance(dataset_ref_path, str) and dataset_ref_path.strip():
            dataset_path = _resolve_path(root, dataset_ref_path)

    dataset_cases_by_id: dict[str, dict] = {}
    if dataset_path is not None and dataset_path.exists():
        try:
            dataset_payload = load_cases(dataset_path)
            for case in dataset_payload.get("cases", []):
                if isinstance(case, dict):
                    case_id = str(case.get("case_id") or "").strip()
                    if case_id:
                        dataset_cases_by_id[case_id] = case
        except Exception as e:
            print_output(f"Invalid dataset payload: {e}", level="error")
            return 2

    output_path = _resolve_path(
        root,
        str(args.output) if args.output else str(cfg.harness.pinned_dataset_path),
    )

    if output_path.exists():
        try:
            pinned_payload = load_cases(output_path)
        except Exception as e:
            print_output(f"Invalid pinned dataset payload: {e}", level="error")
            return 2
    else:
        pinned_payload = {
            "_schema": HARNESS_CASES_SCHEMA_V1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": {
                "kind": "pinned_cases",
                "generated_from_run": str(run_path),
            },
            "cases": [],
        }

    existing_cases = pinned_payload.get("cases", [])
    existing_by_id: dict[str, dict] = {}
    if isinstance(existing_cases, list):
        for case in existing_cases:
            if not isinstance(case, dict):
                continue
            case_id = str(case.get("case_id") or "").strip()
            if case_id:
                existing_by_id[case_id] = case

    status_filters = {
        str(value).strip().lower()
        for value in (args.status or [])
        if str(value).strip()
    }
    failure_filters = {
        str(value).strip().lower()
        for value in (args.failure_category or [])
        if str(value).strip()
    }

    selected: list[dict] = []
    for result in run_payload.get("results", []):
        if not isinstance(result, dict):
            continue
        status = str(result.get("status") or "").strip().lower()
        failure = str(result.get("failure_category") or "").strip().lower()
        if status_filters and status not in status_filters:
            continue
        if failure_filters and failure not in failure_filters:
            continue
        if not status_filters and not failure_filters and status == "pass":
            continue
        selected.append(result)

    if args.limit is not None:
        selected = selected[: max(0, int(args.limit))]

    added = 0
    replaced = 0
    for result in selected:
        case_id = str(result.get("case_id") or "").strip()
        if not case_id:
            continue

        source_case = dataset_cases_by_id.get(case_id, {})
        if not isinstance(source_case, dict):
            source_case = {}
        metrics = result.get("metrics", {}) or {}
        if not isinstance(metrics, dict):
            metrics = {}

        pinned_case = dict(source_case) if source_case else {}
        pinned_case["case_id"] = case_id
        pinned_case["task_id"] = str(
            pinned_case.get("task_id") or source_case.get("task_id") or ""
        ).strip()
        task_title = pinned_case.get("task_title")
        if not isinstance(task_title, str):
            task_title = source_case.get("task_title")
        if not isinstance(task_title, str):
            task_title = None
        if args.redact and isinstance(task_title, str):
            task_title = task_title[:200]
        pinned_case["task_title"] = task_title
        pinned_case["expected"] = pinned_case.get("expected") or {}
        pinned_case["observed_history"] = pinned_case.get("observed_history") or {
            "duration_seconds": float(metrics.get("duration_seconds", 0.0) or 0.0),
            "return_code": int(metrics.get("return_code", 0) or 0),
            "gates_ok": metrics.get("gates_ok"),
            "judge_ok": metrics.get("judge_ok"),
            "blocked": bool(metrics.get("blocked", False)),
            "no_files_written": metrics.get("no_files_written"),
            "timed_out": bool(metrics.get("timed_out", False)),
            "evidence_count": int(metrics.get("evidence_count", 0) or 0),
        }
        pinned_case["bucket"] = (
            str(result.get("bucket")).strip().lower()
            if str(result.get("bucket") or "").strip()
            else pinned_case.get("bucket")
        )
        pinned_case["is_pinned"] = True
        pinned_case["source_kind"] = "pinned"
        pinned_case["pinned_from_run"] = str(run_payload.get("run_id") or "")
        pinned_case["pinned_at"] = datetime.now(timezone.utc).isoformat()

        if case_id in existing_by_id:
            replaced += 1
        else:
            added += 1
        existing_by_id[case_id] = pinned_case

    merged_cases = list(existing_by_id.values())
    pinned_payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    pinned_payload["cases"] = merged_cases
    pinned_payload["source"] = {
        "kind": "pinned_cases",
        "generated_from_run": str(run_path),
        "dataset_path": str(dataset_path) if dataset_path is not None else None,
        "filters": {
            "status": sorted(status_filters),
            "failure_category": sorted(failure_filters),
            "limit": int(args.limit) if args.limit is not None else None,
        },
    }

    try:
        save_cases(output_path, pinned_payload)
    except Exception as e:
        print_output(f"Error saving pinned dataset: {e}", level="error")
        return 2

    if get_output_config().format == "json":
        print_json_output(
            {
                "cmd": "harness_pin",
                "run": str(run_path),
                "output": str(output_path),
                "selected": len(selected),
                "added": added,
                "replaced": replaced,
                "total_pinned": len(merged_cases),
            }
        )
        return 0

    print_output(f"Pinned dataset saved: {output_path}", level="normal")
    print_output(
        f"Cases pinned: selected={len(selected)} added={added} replaced={replaced}",
        level="normal",
    )
    return 0


def cmd_harness_ci(args: argparse.Namespace) -> int:
    """Run collect + evaluate as a CI-friendly harness workflow."""
    root = _project_root()
    cfg = load_config(root)

    from ..harness_store import load_cases, load_run

    dataset_path = _resolve_path(
        root,
        str(args.dataset) if args.dataset else str(cfg.harness.dataset_path),
    )
    collect_args = argparse.Namespace(
        days=args.days,
        limit=args.limit,
        output=str(dataset_path),
        include_failures=args.include_failures,
        redact=args.redact,
        pinned_input=args.pinned_input,
        append_pinned=args.append_pinned,
        max_cases_per_task=args.max_cases_per_task,
    )
    collect_rc = cmd_harness_collect(collect_args)
    if collect_rc != 0:
        print_output("DATASET_ERROR: harness collect failed", level="error")
        return 2

    baseline_arg = args.baseline
    if not baseline_arg and str(cfg.harness.baseline_run_path).strip():
        baseline_arg = str(_resolve_path(root, str(cfg.harness.baseline_run_path)))

    require_baseline = (
        bool(args.require_baseline)
        if args.require_baseline is not None
        else bool(cfg.harness.ci.require_baseline)
    )
    baseline_missing_policy = str(
        args.baseline_missing_policy or cfg.harness.ci.baseline_missing_policy
    ).strip().lower()
    if baseline_missing_policy not in {"fail", "warn"}:
        baseline_missing_policy = "fail"

    baseline_path = _resolve_path(root, str(baseline_arg)) if baseline_arg else None
    if require_baseline and baseline_path is not None and not baseline_path.exists():
        message = f"Baseline run not found: {baseline_path}"
        if baseline_missing_policy == "fail":
            print_output(f"BASELINE_ERROR: {message}", level="error")
            return 2
        print_output(f"BASELINE_ERROR (warn): {message}", level="warning")
        baseline_arg = None
    elif require_baseline and baseline_path is None:
        message = "Baseline run path not configured."
        if baseline_missing_policy == "fail":
            print_output(f"BASELINE_ERROR: {message}", level="error")
            return 2
        print_output(f"BASELINE_ERROR (warn): {message}", level="warning")

    execution_mode = str(
        args.execution_mode or cfg.harness.ci.execution_mode
    ).strip().lower()
    if execution_mode not in {"historical", "live"}:
        execution_mode = "historical"

    enforce_threshold = (
        bool(args.enforce_regression_threshold)
        if args.enforce_regression_threshold is not None
        else bool(cfg.harness.ci.enforce_regression_threshold)
    )
    max_cases = args.max_cases if args.max_cases is not None else cfg.harness.ci.max_cases

    if args.output:
        run_output_path = _resolve_path(root, str(args.output))
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_output_path = _resolve_path(root, str(cfg.harness.runs_dir)) / f"ci-{ts}.json"

    run_args = argparse.Namespace(
        dataset=str(dataset_path),
        agent=args.agent,
        mode=args.mode,
        isolation=args.isolation,
        max_cases=max_cases,
        baseline=baseline_arg,
        output=str(run_output_path),
        enforce_regression_threshold=enforce_threshold,
        execution_mode=execution_mode,
        strict_targeting=args.strict_targeting,
        continue_on_target_error=args.continue_on_target_error,
        bucket=args.bucket,
        report_breakdown=True,
    )
    run_rc = cmd_harness_run(run_args)

    if run_rc == 1:
        print_output("REGRESSION_BREACH: harness regression threshold exceeded", level="error")
        return 1
    if run_rc != 0:
        print_output("DATASET_ERROR: harness run failed", level="error")
        return 2

    try:
        run_payload = load_run(run_output_path)
    except Exception:
        return 0

    if execution_mode == "live":
        completion = run_payload.get("completion", {}) or {}
        partial = bool(completion.get("partial", False))
        if partial and not bool(args.continue_on_target_error):
            print_output("LIVE_PARTIAL: live run stopped on target error", level="error")
            return 2
        if partial:
            print_output("LIVE_PARTIAL (warn): live run completed with target errors", level="warning")

    if get_output_config().format == "json":
        try:
            dataset_payload = load_cases(dataset_path)
            case_count = len(dataset_payload.get("cases", []))
        except Exception:
            case_count = None
        print_json_output(
            {
                "cmd": "harness_ci",
                "dataset": str(dataset_path),
                "run": str(run_output_path),
                "execution_mode": execution_mode,
                "cases": case_count,
                "baseline": baseline_arg,
                "ok": True,
            }
        )
    else:
        print_output(f"Harness CI run saved: {run_output_path}", level="normal")
    return 0


def cmd_harness_doctor(args: argparse.Namespace) -> int:
    """Validate harness config and artifact schemas."""
    root = _project_root()
    cfg = load_config(root)

    from ..harness_store import load_cases, load_run

    issues: list[str] = []
    info: list[str] = []

    if cfg.harness.default_days < 0:
        issues.append("harness.default_days must be >= 0")
    if cfg.harness.default_limit < 1:
        issues.append("harness.default_limit must be >= 1")
    if cfg.harness.max_cases_per_task < 0:
        issues.append("harness.max_cases_per_task must be >= 0")
    if cfg.harness.regression_threshold < 0 or cfg.harness.regression_threshold > 1:
        issues.append("harness.regression_threshold must be between 0 and 1")
    if cfg.harness.replay.default_isolation not in {"worktree", "snapshot"}:
        issues.append("harness.replay.default_isolation must be worktree|snapshot")
    if cfg.harness.ci.execution_mode not in {"historical", "live"}:
        issues.append("harness.ci.execution_mode must be historical|live")
    if cfg.harness.ci.baseline_missing_policy not in {"fail", "warn"}:
        issues.append("harness.ci.baseline_missing_policy must be fail|warn")
    if cfg.harness.buckets.small_max_seconds < 1:
        issues.append("harness.buckets.small_max_seconds must be >= 1")
    if cfg.harness.buckets.medium_max_seconds < cfg.harness.buckets.small_max_seconds:
        issues.append(
            "harness.buckets.medium_max_seconds must be >= harness.buckets.small_max_seconds"
        )

    dataset_path = _resolve_path(root, str(cfg.harness.dataset_path))
    if dataset_path.exists():
        try:
            payload = load_cases(dataset_path)
            info.append(f"dataset OK ({len(payload.get('cases', []))} cases)")
        except Exception as e:
            issues.append(f"dataset invalid: {e}")
    else:
        info.append("dataset missing (run `ralph harness collect`)")

    pinned_path = _resolve_path(root, str(cfg.harness.pinned_dataset_path))
    if pinned_path.exists():
        try:
            payload = load_cases(pinned_path)
            info.append(f"pinned dataset OK ({len(payload.get('cases', []))} cases)")
        except Exception as e:
            issues.append(f"pinned dataset invalid: {e}")
    else:
        info.append("pinned dataset missing (optional)")

    runs_dir = _resolve_path(root, str(cfg.harness.runs_dir))
    if runs_dir.exists():
        run_files = sorted(runs_dir.glob("*.json"))
        if run_files:
            max_checks = int(args.max_run_files or 10)
            for run_file in run_files[-max_checks:]:
                try:
                    load_run(run_file)
                except Exception as e:
                    issues.append(f"invalid run {run_file.name}: {e}")
            info.append(f"validated {min(len(run_files), max_checks)} run file(s)")
        else:
            info.append("no run files found")
    else:
        info.append("runs dir missing (no runs yet)")

    if get_output_config().format == "json":
        print_json_output(
            {
                "cmd": "harness_doctor",
                "ok": len(issues) == 0,
                "issues": issues,
                "info": info,
            }
        )
        return 0 if not issues else 1

    print_output("Harness doctor", level="normal")
    for line in info:
        print_output(f"  ✓ {line}", level="normal")
    for issue in issues:
        print_output(f"  ✗ {issue}", level="error")
    return 0 if not issues else 1
