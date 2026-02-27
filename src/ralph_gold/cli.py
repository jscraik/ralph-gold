from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import LOOP_MODE_NAMES, load_config
from .diagnostics import run_diagnostics
from .state_validation import cleanup_stale_task_ids, validate_state_against_prd
from .doctor import check_tools, setup_checks
from .json_response import build_json_response
from .logging_config import setup_logging
from .loop import (
    build_runner_invocation,
    dry_run_loop,
    next_iteration_number,
    run_iteration,
    run_loop,
)
from .output import (
    OutputConfig,
    get_output_config,
    print_json_output,
    print_output,
    set_output_config,
)
from .path_utils import validate_project_path, validate_output_path
from .scaffold import init_project
from .snapshots import (
    create_snapshot,
    list_snapshots,
    rollback_snapshot,
)
from .specs import check_specs, format_specs_check
from .stats import calculate_stats, export_stats_csv, format_stats_report
from .trackers import make_tracker
from .watch import run_watch_mode


def _project_root() -> Path:
    return Path(os.getcwd()).resolve()


def _normalize_cli_mode(value: str | None) -> str | None:
    if value is None:
        return None
    mode = value.strip().lower()
    if not mode:
        raise ValueError(
            "Invalid --mode: ''. Must be one of: "
            f"{', '.join(LOOP_MODE_NAMES)}."
        )
    if mode not in LOOP_MODE_NAMES:
        raise ValueError(
            f"Invalid --mode: {value!r}. Must be one of: "
            f"{', '.join(LOOP_MODE_NAMES)}."
        )
    return mode


def _default_planner_agent(cfg) -> str:
    """Pick the best available planning/review agent from configured runners."""

    preferred = ["claude-zai", "claude-kimi", "claude", "codex"]
    for name in preferred:
        if hasattr(cfg, "runners") and cfg.runners and name in cfg.runners:
            return name
    # Fallback: first configured runner name, else codex.
    try:
        return next(iter(cfg.runners.keys()))
    except Exception:
        return "codex"


class _RalphArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.exit(2, f"Error: {message}\n")


# -------------------------
# init / doctor
# -------------------------


def cmd_init(args: argparse.Namespace) -> int:
    root = _project_root()
    format_type = getattr(args, "format", None)
    no_merge_config = getattr(args, "no_merge_config", False)
    merge_strategy = getattr(args, "merge_strategy", "user_wins")

    archived = init_project(
        root,
        force=bool(args.force),
        format_type=format_type,
        solo=bool(getattr(args, "solo", False)),
        merge_config=not no_merge_config,
        merge_strategy=merge_strategy,
        no_merge_config=no_merge_config,
    )

    print_output(f"Initialized Ralph files in: {root / '.ralph'}", level="quiet")

    if archived:
        print_output(
            f"\n✓ Archived {len(archived)} existing file(s) to .ralph/archive/",
            level="quiet",
        )
        for path in archived[:5]:  # Show first 5
            print_output(f"  - {path}", level="quiet")
        if len(archived) > 5:
            print_output(f"  ... and {len(archived) - 5} more", level="quiet")

    if format_type == "yaml":
        print_output("Created tasks.yaml template (YAML tracker)", level="quiet")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Route doctor subcommands."""
    root = _project_root()

    if args.setup_checks:
        return _doctor_setup_checks(root, args)
    if args.check_github:
        return _doctor_check_github(root, args)
    return _doctor_tools(root)


def _doctor_setup_checks(project_root: Path, args: argparse.Namespace) -> int:
    """Handle doctor --setup-checks mode.

    Auto-configure quality gates for the project based on detected type.
    """
    result = setup_checks(project_root, dry_run=args.dry_run)

    # JSON output for setup_checks mode
    if get_output_config().format == "json":
        payload = build_json_response(
            "doctor",
            mode="setup_checks",
            exit_code=0,
            result={
                "project_type": result["project_type"],
                "script_name": result["script_name"],
                "actions_taken": result["actions_taken"],
                "suggestions": result["suggestions"],
                "commands": result["commands"],
            },
        )
        print_json_output(payload)
        return 0

    # Text output
    print_output(f"Project type: {result['project_type']}", level="normal")
    print_output(f"Check script: {result['script_name']}", level="normal")
    print_output("\nSuggested gate commands:", level="normal")
    for cmd in result["commands"]:
        print_output(f"  - {cmd}", level="normal")

    if result["actions_taken"]:
        print_output("\n✓ Actions taken:", level="normal")
        for action in result["actions_taken"]:
            print_output(f"  - {action}", level="normal")

    if result["suggestions"]:
        print_output("\n→ Suggestions:", level="normal")
        for suggestion in result["suggestions"]:
            print_output(f"  - {suggestion}", level="normal")

    if args.dry_run:
        print_output("\n(Dry run - no changes made)", level="normal")

    return 0


def _doctor_check_github(project_root: Path, args: argparse.Namespace) -> int:
    """Handle doctor --check-github mode.

    Check GitHub authentication (gh CLI or token).
    """
    from .github_auth import GhCliAuth, GitHubAuthError, TokenAuth

    logger = logging.getLogger(__name__)

    # JSON output for check_github mode
    if get_output_config().format == "json":
        gh_cli_result = {"ok": False, "user": None, "error": None}
        token_result = {"ok": False, "user": None, "error": None}

        # Try gh CLI
        try:
            gh_auth = GhCliAuth()
            if gh_auth.validate():
                gh_cli_result["ok"] = True
                try:
                    user_data = gh_auth.api_call("GET", "/user")
                    gh_cli_result["user"] = user_data.get("login")
                except Exception as e:
                    logger.debug("Failed to get gh CLI user data: %s", e)
            else:
                gh_cli_result["error"] = "installed but not authenticated"
        except GitHubAuthError as e:
            gh_cli_result["error"] = str(e)

        # Try token auth
        try:
            token_auth = TokenAuth()
            if token_auth.validate():
                token_result["ok"] = True
                try:
                    user_data = token_auth.api_call("GET", "/user")
                    token_result["user"] = user_data.get("login")
                except Exception as e:
                    logger.debug("Failed to get token user data: %s", e)
            else:
                token_result["error"] = "invalid or expired"
        except GitHubAuthError as e:
            token_result["error"] = str(e)

        # Exit code 0 if either auth method is ok
        exit_code = 0 if (gh_cli_result["ok"] or token_result["ok"]) else 2

        payload = build_json_response(
            "doctor",
            mode="check_github",
            exit_code=exit_code,
            auth={"gh_cli": gh_cli_result, "token": token_result},
        )
        print_json_output(payload)
        return exit_code

    # Text output
    print_output("Checking GitHub authentication...\n", level="normal")

    # Try gh CLI first
    print_output("[1/2] Checking gh CLI authentication...", level="normal")
    try:
        gh_auth = GhCliAuth()
        if gh_auth.validate():
            print_output("[OK]   gh CLI: authenticated", level="normal")

            # Get user info to show who's authenticated
            try:
                user_data = gh_auth.api_call("GET", "/user")
                print_output(
                    f"       User: {user_data.get('login', 'unknown')}",
                    level="normal",
                )
            except Exception as e:
                logger.debug("Failed to get gh CLI user data: %s", e)

            return 0
        else:
            print_output(
                "[WARN] gh CLI: installed but not authenticated", level="normal"
            )
            print_output(
                "       Run 'gh auth login' to authenticate", level="normal"
            )
    except GitHubAuthError as e:
        print_output(f"[MISS] gh CLI: {e}", level="normal")

    # Try token auth
    print_output("\n[2/2] Checking token authentication...", level="normal")
    try:
        token_auth = TokenAuth()
        if token_auth.validate():
            print_output(
                "[OK]   Token: authenticated (GITHUB_TOKEN)", level="normal"
            )

            # Get user info to show who's authenticated
            try:
                user_data = token_auth.api_call("GET", "/user")
                print_output(
                    f"       User: {user_data.get('login', 'unknown')}",
                    level="normal",
                )
            except OSError as e:
                logger.debug("State load failed: %s", e)
                state = {}

            return 0
        else:
            print_output("[WARN] Token: invalid or expired", level="normal")
    except GitHubAuthError as e:
        print_output(f"[MISS] Token: {e}", level="normal")

    print_output("\n✗ No valid GitHub authentication found", level="error")
    print_output("\nTo authenticate:", level="normal")
    print_output("  Option 1 (recommended): gh auth login", level="normal")
    print_output(
        "  Option 2: Set GITHUB_TOKEN environment variable", level="normal"
    )
    print_output(
        "            Get a token from https://github.com/settings/tokens",
        level="normal",
    )

    return 2


def _doctor_tools(project_root: Path) -> int:
    """Handle default doctor mode - check available tools.

    Lists status of git, uv, codex, claude, copilot, gh, and configured tools.
    """
    cfg = load_config(project_root)
    statuses = check_tools(cfg)

    # JSON output for tools mode
    if get_output_config().format == "json":
        ok = all(st.found for st in statuses)
        exit_code = 0 if ok else 2
        statuses_payload = [
            {
                "name": st.name,
                "found": st.found,
                "version": st.version,
                "path": st.path,
                "hint": st.hint,
            }
            for st in statuses
        ]
        payload = build_json_response(
            "doctor",
            mode="tools",
            exit_code=exit_code,
            statuses=statuses_payload,
        )
        print_json_output(payload)
        return exit_code

    # Text output
    ok = True
    for st in statuses:
        if st.found:
            print_output(
                f"[OK]   {st.name}: {st.version or st.path or 'found'}", level="normal"
            )
        else:
            ok = False
            print_output(f"[MISS] {st.name}: {st.hint or 'not found'}", level="normal")
    return 0 if ok else 2


def cmd_diagnose(args: argparse.Namespace) -> int:
    """Run diagnostic checks on Ralph configuration and PRD."""
    root = _project_root()

    test_gates = args.test_gates

    # Run diagnostics
    results, exit_code = run_diagnostics(root, test_gates_flag=test_gates)

    # JSON output for cmd_diagnose
    if get_output_config().format == "json":
        results_payload = [
            {
                "name": r.name,
                "passed": r.passed,
                "severity": r.severity,
                "message": r.message,
                "suggestions": r.suggestions or [],
            }
            for r in results
        ]
        total = len(results)
        passed = len([r for r in results if r.passed])
        failed = total - passed
        payload = {
            "cmd": "diagnose",
            "exit_code": exit_code,
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
            },
            "results": results_payload,
        }
        print_json_output(payload)
        return exit_code

    # Format and display results
    print_output("Ralph Diagnostics Report", level="quiet")
    print_output("=" * 60, level="quiet")
    print_output("", level="quiet")

    # Group results by severity
    errors = [r for r in results if r.severity == "error" and not r.passed]
    warnings = [r for r in results if r.severity == "warning" and not r.passed]
    info = [r for r in results if r.passed or r.severity == "info"]

    # Display errors
    if errors:
        print_output("ERRORS:", level="error")
        for result in errors:
            print_output(f"  ✗ {result.message}", level="error")
            if result.suggestions:
                for suggestion in result.suggestions:
                    print_output(f"    → {suggestion}", level="error")
            print_output("", level="error")

    # Display warnings
    if warnings:
        print_output("WARNINGS:", level="normal")
        for result in warnings:
            print_output(f"  ⚠ {result.message}", level="normal")
            if result.suggestions:
                for suggestion in result.suggestions:
                    print_output(f"    → {suggestion}", level="normal")
            print_output("", level="normal")

    # Display info/passed checks
    # If test_gates was requested, show gate results at normal level
    # Otherwise show all passed checks at verbose level
    if info:
        # Determine output level based on whether this is gate testing
        info_level = "normal" if test_gates else "verbose"
        print_output("PASSED:", level=info_level)
        for result in info:
            print_output(f"  ✓ {result.message}", level=info_level)
        print_output("", level=info_level)

    # Summary
    total_checks = len(results)
    passed_checks = len([r for r in results if r.passed])
    failed_checks = len([r for r in results if not r.passed])

    print_output("=" * 60, level="quiet")
    print_output(
        f"Summary: {passed_checks}/{total_checks} checks passed", level="quiet"
    )

    if failed_checks > 0:
        print_output(f"         {failed_checks} issue(s) found", level="quiet")

    if exit_code == 0:
        print_output("\n✓ All diagnostics passed!", level="quiet")
    else:
        print_output("\n✗ Diagnostics found issues that need attention.", level="error")

    return exit_code


def cmd_stats(args: argparse.Namespace) -> int:
    """Display iteration statistics from Ralph history."""
    root = _project_root()
    state_path = root / ".ralph" / "state.json"

    # Check if state file exists
    if not state_path.exists():
        print_output("No state.json found. Run some iterations first.", level="normal")
        return 0

    # Load state
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as e:
        print_output(f"Error loading state.json: {e}", level="error")
        return 1

    # Calculate statistics
    try:
        stats = calculate_stats(state)
    except Exception as e:
        print_output(f"Error calculating statistics: {e}", level="error")
        return 1

    # Handle export flag
    export_path = None
    exported = False
    if args.export:
        export_path = Path(args.export).resolve()
        try:
            export_stats_csv(stats, export_path)
            exported = True
        except Exception as e:
            print_output(f"Error exporting statistics: {e}", level="error")
            return 1

    if args.export and get_output_config().format != "json":
        print_output(f"✓ Statistics exported to: {export_path}", level="quiet")
        return 0

    # JSON output for cmd_stats
    if get_output_config().format == "json":
        payload = {
            "cmd": "stats",
            "exported": exported,
            "export_path": str(export_path) if export_path else None,
            "stats": stats,
        }
        print_json_output(payload)
        return 0

    # Display formatted report
    by_task = args.by_task
    report = format_stats_report(stats, by_task=by_task)
    print_output(report, level="normal")

    return 0


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def cmd_harness_collect(args: argparse.Namespace) -> int:
    """Collect harness cases from Ralph history artifacts."""
    root = _project_root()
    cfg = load_config(root)

    from .harness import collect_harness_cases
    from .harness_store import load_cases, save_cases

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
                "cmd": "harness collect",
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

    from .harness import (
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
    from .harness_store import load_cases, load_run, save_run

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
        from .loop import next_iteration_number, run_iteration

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
                "cmd": "harness run",
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

    from .harness import compare_harness_runs, format_harness_report, report_to_csv
    from .harness_store import load_run

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
                "cmd": "harness report",
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

    from .harness import HARNESS_CASES_SCHEMA_V1
    from .harness_store import load_cases, load_run, save_cases

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
                "cmd": "harness pin",
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

    from .harness_store import load_cases, load_run

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
                "cmd": "harness ci",
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

    from .harness_store import load_cases, load_run

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
                "cmd": "harness doctor",
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


def cmd_resume(args: argparse.Namespace) -> int:
    """Handle resume command - detect and optionally continue interrupted iteration."""
    root = _project_root()

    from .resume import (
        clear_interrupted_state,
        detect_interrupted_iteration,
        format_resume_prompt,
        should_resume,
    )

    resume_info = detect_interrupted_iteration(root)

    if resume_info is None:
        print_output("No interrupted iteration detected.", level="normal")
        print_output("Last iteration completed normally.", level="normal")
        return 0

    # Show information about the interruption
    print_output(format_resume_prompt(resume_info), level="normal")
    print_output("", level="normal")

    # Check if we should recommend resuming
    recommended = should_resume(resume_info)

    if args.clear:
        if clear_interrupted_state(root):
            print_output("✓ Cleared interrupted iteration from state.", level="quiet")
            print_output(
                "  Run 'ralph step' to start fresh on the same task.", level="quiet"
            )
        else:
            print_output("✗ Failed to clear interrupted state.", level="error")
            return 1
        return 0

    if args.auto or recommended:
        if not args.auto:
            # Interactive mode - ask user
            try:
                response = input("\nResume this iteration? [Y/n]: ").strip().lower()
                if response and response not in {"y", "yes"}:
                    print_output(
                        "Skipped. Use 'ralph resume --clear' to remove this entry.",
                        level="normal",
                    )
                    return 0
            except (KeyboardInterrupt, EOFError):
                print_output("\nCancelled.", level="normal")
                return 0

        # Resume by running another iteration
        print_output(f"\nResuming with agent '{resume_info.agent}'...", level="normal")
        cfg = load_config(root)
        iter_n = next_iteration_number(root)

        try:
            res = run_iteration(
                root, agent=resume_info.agent, cfg=cfg, iteration=iter_n
            )
        except RuntimeError as e:
            # Handle rate-limit and other runtime errors
            print_output(f"Error: {e}", level="error")
            return 2

        print_output(
            f"Iteration {res.iteration} agent={resume_info.agent} story_id={res.story_id} "
            f"rc={res.return_code} exit={res.exit_signal} gates={res.gates_ok}",
            level="quiet",
        )
        print_output(f"Log: {res.log_path}", level="quiet")

        return 0 if res.return_code == 0 else 2

    # Not recommended to resume
    print_output("\n⚠ Resume not recommended (gates may have failed).", level="normal")
    print_output("Options:", level="normal")
    print_output("  - ralph resume --clear    # Clear and start fresh", level="normal")
    print_output("  - ralph resume --auto     # Force resume anyway", level="normal")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """Clean old Ralph workspace artifacts."""
    root = _project_root()

    from .clean import clean_all, format_bytes

    logs_days = args.logs_days
    archives_days = args.archives_days
    receipts_days = args.receipts_days
    context_days = args.context_days
    dry_run = args.dry_run

    if dry_run:
        print_output("DRY RUN - No files will be deleted\n", level="normal")

    logs_result, archives_result, receipts_result, context_result = clean_all(
        root,
        logs_days=logs_days,
        archives_days=archives_days,
        receipts_days=receipts_days,
        context_days=context_days,
        dry_run=dry_run,
    )

    total_files = (
        logs_result.files_removed
        + archives_result.files_removed
        + receipts_result.files_removed
        + context_result.files_removed
    )
    total_bytes = (
        logs_result.bytes_freed
        + archives_result.bytes_freed
        + receipts_result.bytes_freed
        + context_result.bytes_freed
    )
    total_dirs = (
        logs_result.directories_removed
        + archives_result.directories_removed
        + receipts_result.directories_removed
        + context_result.directories_removed
    )

    # Show results
    if logs_result.files_removed > 0:
        print_output(
            f"Logs:     {logs_result.files_removed} files ({format_bytes(logs_result.bytes_freed)})",
            level="quiet",
        )
    if archives_result.files_removed > 0 or archives_result.directories_removed > 0:
        print_output(
            f"Archives: {archives_result.directories_removed} dirs, "
            f"{archives_result.files_removed} files ({format_bytes(archives_result.bytes_freed)})",
            level="quiet",
        )
    if receipts_result.files_removed > 0:
        print_output(
            f"Receipts: {receipts_result.files_removed} files ({format_bytes(receipts_result.bytes_freed)})",
            level="quiet",
        )
    if context_result.files_removed > 0:
        print_output(
            f"Context:  {context_result.files_removed} files ({format_bytes(context_result.bytes_freed)})",
            level="quiet",
        )

    if total_files == 0 and total_dirs == 0:
        print_output("Nothing to clean (no old files found)", level="normal")
    else:
        print_output(
            f"\nTotal: {total_files} files, {total_dirs} directories", level="quiet"
        )
        print_output(f"Freed: {format_bytes(total_bytes)}", level="quiet")

        if dry_run:
            print_output(
                "\n(Dry run - run without --dry-run to actually delete)", level="normal"
            )

    # Show errors if any
    all_errors = (
        logs_result.errors
        + archives_result.errors
        + receipts_result.errors
        + context_result.errors
    )
    if all_errors:
        print_output("\nErrors:", level="error")
        for error in all_errors:
            print_output(f"  - {error}", level="error")
        return 1

    return 0


def cmd_state_cleanup(args: argparse.Namespace) -> int:
    """Remove stale task IDs from state.json."""
    root = _project_root()
    cfg = load_config(root)

    prd_path = root / cfg.files.prd
    state_path = root / ".ralph" / "state.json"

    # Validate first
    validation = validate_state_against_prd(
        root,
        prd_path,
        state_path,
        cfg.state.protect_recent_hours,
    )

    if not validation.stale_ids:
        print_output("No stale task IDs found.", level="normal")
        return 0

    # Show what was found
    print_output(f"Found {len(validation.stale_ids)} stale task IDs: {validation.stale_ids}", level="normal")
    if validation.protected_ids:
        print_output(f"Protected (current/recent): {validation.protected_ids}", level="normal")

    dry_run = args.dry_run
    if dry_run:
        print_output("\nDRY RUN - No changes will be made", level="normal")

    # Check if auto-cleanup is safe
    if not validation.can_auto_cleanup:
        print_output("\nCannot auto-cleanup: current task is stale or PRD was recently modified", level="warning")
        print_output("Run 'ralph state cleanup' after fixing the PRD or completing current task", level="normal")
        return 1

    # Perform cleanup
    removed_ids = cleanup_stale_task_ids(
        root,
        prd_path,
        state_path,
        dry_run=dry_run,
    )

    if removed_ids:
        print_output(f"Removed {len(removed_ids)} stale task IDs: {removed_ids}", level="normal")
        if dry_run:
            print_output("\nRun without --dry-run to actually remove these IDs", level="normal")
    else:
        print_output("No task IDs were removed (all were protected)", level="normal")

    return 0


# -------------------------
# loop
# -------------------------


def cmd_step(args: argparse.Namespace) -> int:
    root = _project_root()
    try:
        cfg = load_config(root)
    except ValueError as exc:
        print_output(str(exc), level="error")
        return 2

    try:
        mode_override = _normalize_cli_mode(getattr(args, "mode", None))
    except ValueError as exc:
        print_output(str(exc), level="error")
        return 2
    if mode_override:
        cfg = replace(cfg, loop=replace(cfg.loop, mode=mode_override))

    # Ad-hoc overrides (useful for loop.sh mode switching)
    # Validate file paths to prevent path traversal attacks
    if args.prompt_file:
        validated_prompt = validate_project_path(root, Path(args.prompt_file), must_exist=True)
        cfg = replace(cfg, files=replace(cfg.files, prompt=str(validated_prompt)))
    if args.prd_file:
        validated_prd = validate_project_path(root, Path(args.prd_file), must_exist=True)
        cfg = replace(cfg, files=replace(cfg.files, prd=str(validated_prd)))

    agent = args.agent

    # Handle dry-run mode
    dry_run = getattr(args, "dry_run", False)
    if dry_run:
        result = dry_run_loop(root, agent, 1, cfg)

        print_output("=" * 60, level="quiet")
        print_output("DRY-RUN MODE - No agents will be executed", level="quiet")
        print_output("=" * 60, level="quiet")
        print_output("", level="quiet")
        print_output(
            f"Configuration: {'VALID' if result.config_valid else 'INVALID'}",
            level="quiet",
        )
        print_output(
            f"Resolved loop mode: {result.resolved_mode.get('name')}",
            level="quiet",
        )
        print_output(f"Total tasks: {result.total_tasks}", level="quiet")
        print_output(f"Completed tasks: {result.completed_tasks}", level="quiet")
        print_output("", level="quiet")

        if result.issues:
            print_output("Issues found:", level="quiet")
            for issue in result.issues:
                print_output(f"  ❌ {issue}", level="error")
            print_output("", level="quiet")

        if result.tasks_to_execute:
            print_output("Next task that would be executed:", level="quiet")
            print_output(f"  • {result.tasks_to_execute[0]}", level="quiet")
            print_output("", level="quiet")
        else:
            print_output("No tasks would be executed.", level="quiet")
            print_output("", level="quiet")

        if result.gates_to_run:
            print_output("Gates that would run:", level="quiet")
            for gate in result.gates_to_run:
                print_output(f"  • {gate}", level="quiet")
            print_output("", level="quiet")

        print_output("=" * 60, level="quiet")
        print_output("Dry-run complete. No changes were made.", level="quiet")
        print_output("=" * 60, level="quiet")
        return 0

    # Handle interactive mode
    interactive = getattr(args, "interactive", False)
    task_override = None
    target_task_id = (
        str(getattr(args, "task_id", "")).strip()
        if getattr(args, "task_id", None) is not None
        else ""
    )
    allow_done_target = bool(getattr(args, "allow_done_target", False))
    allow_blocked_target = bool(getattr(args, "allow_blocked_target", False))
    reopen_target = bool(getattr(args, "reopen_target", False))

    if interactive and target_task_id:
        print_output(
            "--interactive cannot be combined with --task-id.", level="error"
        )
        return 2

    if interactive:
        from .interactive import (
            convert_selected_task_to_choice,
            select_task_interactive,
        )
        from .prd import SelectedTask

        # Get available tasks from tracker
        tracker = make_tracker(root, cfg)

        # Load state to get blocked tasks
        state_path = root / ".ralph" / "state.json"
        from .loop import load_state

        state = load_state(state_path)

        # Build blocked task IDs set for task selection
        blocked_ids: set[str] = set()
        if cfg.loop.skip_blocked_tasks:
            blocked_raw = state.get("blocked_tasks", {}) or {}
            if isinstance(blocked_raw, dict):
                # Convert keys to strings for type safety
                blocked_ids = {str(k) for k in blocked_raw.keys()}

        # Get all available tasks
        available_tasks = []
        try:
            # Try to get all tasks for interactive selection
            if hasattr(tracker, "list_tasks"):
                # Some trackers may have a list_tasks method
                all_tasks = tracker.list_tasks()
                for task in all_tasks:
                    if isinstance(task, SelectedTask):
                        is_blocked = task.id in blocked_ids
                        task_choice = convert_selected_task_to_choice(
                            task,
                            priority=getattr(task, "priority", "medium"),
                            status="ready" if not is_blocked else "blocked",
                            blocked=is_blocked,
                        )
                        available_tasks.append(task_choice)
            else:
                # Fallback: try to select tasks one by one
                # This is a workaround for trackers without list_tasks
                temp_excluded: set[str] = set(blocked_ids)
                for _ in range(20):  # Limit to 20 tasks to avoid infinite loop
                    try:
                        if hasattr(tracker, "select_next_task"):
                            task = tracker.select_next_task(exclude_ids=temp_excluded)
                        else:
                            break

                        if task is None:
                            break

                        is_blocked = task.id in blocked_ids
                        task_choice = convert_selected_task_to_choice(
                            task,
                            priority=getattr(task, "priority", "medium"),
                            status="ready" if not is_blocked else "blocked",
                            blocked=is_blocked,
                        )
                        available_tasks.append(task_choice)
                        temp_excluded.add(task.id)
                    except (AttributeError, NotImplementedError, OSError) as e:
                        logger.debug("Task selection failed: %s", e)
                        task = None
        except (AttributeError, NotImplementedError, OSError) as e:
            logger.debug("Failed to list tasks for interactive selection: %s", e)
            print_output(
                f"Error loading tasks for interactive selection: {e}", level="error"
            )
            return 1

        if not available_tasks:
            print_output("No tasks available for selection.", level="normal")
            return 0

        # Let user select a task
        selected_choice = select_task_interactive(available_tasks, show_blocked=False)

        if selected_choice is None:
            print_output("No task selected. Exiting.", level="normal")
            return 0

        # Convert back to SelectedTask for run_iteration
        task_override = SelectedTask(
            id=selected_choice.task_id,
            title=selected_choice.title,
            kind="markdown",  # Default to markdown kind
            acceptance=selected_choice.acceptance_criteria,
        )
        target_task_id = str(selected_choice.task_id)

    iter_n = next_iteration_number(root)
    try:
        res = run_iteration(
            root,
            agent=agent,
            cfg=cfg,
            iteration=iter_n,
            task_override=task_override,
            target_task_id=target_task_id or None,
            allow_done_target=allow_done_target,
            allow_blocked_target=allow_blocked_target,
            reopen_if_needed=reopen_target,
        )
    except RuntimeError as e:
        # Handle rate-limit and other runtime errors
        print_output(f"Error: {e}", level="error")
        return 2

    # JSON output for cmd_step
    if get_output_config().format == "json":
        exit_code = 0 if res.return_code == 0 else 2
        if res.no_progress_streak >= cfg.loop.no_progress_limit:
            exit_code = 3
        payload = {
            "cmd": "step",
            "iteration": res.iteration,
            "agent": agent,
            "story_id": res.story_id,
            "exit_signal": res.exit_signal,
            "return_code": res.return_code,
            "gates_ok": res.gates_ok,
            "judge_ok": res.judge_ok,
            "review_ok": res.review_ok,
            "log_path": str(res.log_path),
            "no_progress_streak": res.no_progress_streak,
            "no_progress_limit": cfg.loop.no_progress_limit,
            "target_task_id": res.target_task_id,
            "target_status": res.target_status,
            "target_failure_reason": res.target_failure_reason,
            "targeting_policy": res.targeting_policy,
        }
        print_json_output(payload)
        return exit_code

    print_output(
        f"Iteration {res.iteration} agent={agent} story_id={res.story_id} rc={res.return_code} "
        f"exit={res.exit_signal} gates={res.gates_ok} judge={res.judge_ok} review={res.review_ok}",
        level="quiet",
    )
    print_output(f"Log: {res.log_path}", level="quiet")

    if res.no_progress_streak >= cfg.loop.no_progress_limit:
        print_output(
            f"Stopped: no progress streak reached ({res.no_progress_streak}/{cfg.loop.no_progress_limit}).",
            level="normal",
        )
        return 3
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    root = _project_root()
    agent = args.agent
    try:
        cfg = load_config(root)
    except ValueError as exc:
        print_output(str(exc), level="error")
        return 2

    try:
        mode_override = _normalize_cli_mode(getattr(args, "mode", None))
    except ValueError as exc:
        print_output(str(exc), level="error")
        return 2
    if mode_override:
        cfg = replace(cfg, loop=replace(cfg.loop, mode=mode_override))

    # Validate file paths to prevent path traversal attacks
    if args.prompt_file:
        validated_prompt = validate_project_path(root, Path(args.prompt_file), must_exist=True)
        cfg = replace(cfg, files=replace(cfg.files, prompt=str(validated_prompt)))
    if args.prd_file:
        validated_prd = validate_project_path(root, Path(args.prd_file), must_exist=True)
        cfg = replace(cfg, files=replace(cfg.files, prd=str(validated_prd)))

    # Get parallel and max_workers from args
    parallel = getattr(args, "parallel", False)
    max_workers = getattr(args, "max_workers", None)
    dry_run = getattr(args, "dry_run", False)
    stream = getattr(args, "stream", False)
    if parallel and stream:
        print_output(
            "INFO: --stream is only supported in sequential mode and will be ignored "
            "when --parallel is enabled.",
            level="normal",
        )
        stream = False

    try:
        results = run_loop(
            root,
            agent=agent,
            max_iterations=args.max_iterations,
            cfg=cfg,
            parallel=parallel,
            max_workers=max_workers,
            dry_run=dry_run,
            stream=stream,
        )
    except RuntimeError as e:
        # Handle rate-limit and other runtime errors
        print_output(f"Error: {e}", level="error")
        return 2

    # Dry-run mode prints its own output and returns early
    if dry_run:
        return 0

    # JSON output for cmd_run
    if get_output_config().format == "json":
        results_payload = [
            {
                "iteration": r.iteration,
                "story_id": r.story_id,
                "return_code": r.return_code,
                "exit_signal": r.exit_signal,
                "gates_ok": r.gates_ok,
                "judge_ok": r.judge_ok,
                "review_ok": r.review_ok,
                "log_path": str(r.log_path),
            }
            for r in results
        ]
        last = results[-1] if results else None
        any_failed = any(
            (r.return_code != 0) or (r.gates_ok is False) or (r.judge_ok is False)
            for r in results
        )
        if any_failed:
            exit_code = 2
        elif last and last.exit_signal is True:
            exit_code = 0
        else:
            exit_code = 1
        payload = {
            "cmd": "run",
            "iterations": len(results),
            "agent": agent,
            "results": results_payload,
            "any_failed": any_failed,
            "exit_code": exit_code,
        }
        print_json_output(payload)
        return exit_code

    for r in results:
        log_name = r.log_path.name if r.log_path else "no-log"
        print_output(
            f"iter={r.iteration} story_id={r.story_id} rc={r.return_code} exit={r.exit_signal} "
            f"gates={r.gates_ok} judge={r.judge_ok} log={log_name}",
            level="quiet",
        )

    last = results[-1] if results else None
    any_failed = any(
        (r.return_code != 0) or (r.gates_ok is False) or (r.judge_ok is False)
        for r in results
    )
    if any_failed:
        return 2
    if last and last.exit_signal is True:
        return 0
    return 1


def cmd_supervise(args: argparse.Namespace) -> int:
    """Run a long-lived supervisor loop with heartbeat + notifications."""

    root = _project_root()
    agent = args.agent
    try:
        cfg = load_config(root)
    except ValueError as exc:
        print_output(str(exc), level="error")
        return 2

    try:
        mode_override = _normalize_cli_mode(getattr(args, "mode", None))
    except ValueError as exc:
        print_output(str(exc), level="error")
        return 2
    if mode_override:
        cfg = replace(cfg, loop=replace(cfg.loop, mode=mode_override))

    # Resolve supervisor defaults from config, overridden by flags when provided.
    sup = cfg.supervisor
    max_runtime_seconds = (
        args.max_runtime_seconds
        if args.max_runtime_seconds is not None
        else sup.max_runtime_seconds
    )
    heartbeat_seconds = (
        args.heartbeat_seconds if args.heartbeat_seconds is not None else sup.heartbeat_seconds
    )
    sleep_seconds_between_runs = (
        args.sleep_seconds_between_runs
        if args.sleep_seconds_between_runs is not None
        else sup.sleep_seconds_between_runs
    )
    on_no_progress_limit = (
        args.on_no_progress_limit
        if args.on_no_progress_limit is not None
        else sup.on_no_progress_limit
    )
    on_rate_limit = (
        args.on_rate_limit if args.on_rate_limit is not None else sup.on_rate_limit
    )

    # Notifications (best-effort)
    notify_enabled: bool
    if getattr(args, "notify", None) is True:
        notify_enabled = True
    elif getattr(args, "no_notify", None) is True:
        notify_enabled = False
    else:
        notify_enabled = bool(sup.notify_enabled)

    notify_backend = (
        args.notify_backend if args.notify_backend is not None else sup.notify_backend
    )
    notify_command_argv = (
        args.notify_command if args.notify_command is not None else list(sup.notify_command_argv)
    )

    from .supervisor import run_supervisor, supervise_to_stdout_json

    res = run_supervisor(
        root,
        agent=agent,
        cfg=cfg,
        max_runtime_seconds=int(max_runtime_seconds),
        heartbeat_seconds=int(heartbeat_seconds),
        sleep_seconds_between_runs=int(sleep_seconds_between_runs),
        on_no_progress_limit=str(on_no_progress_limit),
        on_rate_limit=str(on_rate_limit),
        notify_enabled=notify_enabled,
        notify_events=list(sup.notify_events),
        notify_backend=str(notify_backend),
        notify_command_argv=list(notify_command_argv or []),
    )

    # JSON mode emits exactly one JSON payload and suppresses heartbeat text
    supervise_to_stdout_json(res)

    if get_output_config().format != "json":
        print_output(
            f"Supervise finished: exit_code={res.exit_code} reason={res.reason} "
            f"iterations={res.iterations_run}",
            level="normal",
        )
        if res.last_log_path:
            print_output(f"Last log: {res.last_log_path}", level="quiet")

    return int(res.exit_code)


def cmd_status(args: argparse.Namespace) -> int:
    root = _project_root()
    cfg = load_config(root)
    tracker = make_tracker(root, cfg)
    state_path = root / ".ralph" / "state.json"
    next_task = None
    last_iteration = None

    # Handle --graph flag for dependency visualization
    if getattr(args, "graph", False):
        from .dependencies import build_dependency_graph, format_dependency_graph
        from .prd import get_all_tasks

        # Get PRD path from config
        prd_path = root / cfg.files.prd

        try:
            # Load all tasks and build dependency graph
            tasks = get_all_tasks(prd_path)

            if not tasks:
                print_output("No tasks found in PRD file.", level="normal")
                return 0

            # Build and display dependency graph
            graph = build_dependency_graph(tasks)
            print_output(format_dependency_graph(graph), level="normal")
            return 0

        except Exception as e:
            print_output(f"Error building dependency graph: {e}", level="error")
            return 1

    # Handle --chart flag for burndown chart
    if getattr(args, "chart", False):
        from .progress import format_burndown_chart

        state_path = root / ".ralph" / "state.json"
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                history = state.get("history", [])
                chart = format_burndown_chart(history, width=70, height=20)
                print_output(chart, level="normal")
                return 0
            except Exception as e:
                print_output(f"Error generating burndown chart: {e}", level="error")
                return 1
        else:
            print_output(
                "No history data available for burndown chart.", level="normal"
            )
            return 0

    try:
        done, total = tracker.counts()
    except (OSError, ValueError) as e:
        logger.debug("Tracker operation failed: %s", e)
        done, total = 0, 0

    try:
        if hasattr(tracker, "peek_next_task"):
            next_task = tracker.peek_next_task()
        elif hasattr(tracker, "select_next_task"):
            next_task = tracker.select_next_task()
    except (OSError, ValueError) as e:
        logger.debug("Failed to resolve next task: %s", e)

    blocked = 0
    open_count = 0
    try:
        from .prd import status_counts
        prd_path = root / cfg.files.prd
        done_detailed, blocked, open_count, total_from_prd = status_counts(prd_path)
        # Use detailed counts for accuracy, but keep done/total from tracker for consistency
        # if PRD has data
        if total_from_prd > 0:
            total = total_from_prd
            done = done_detailed
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Failed to load PRD status counts: %s", e)
    state = {}
    if state_path.exists():
        try:
            from .progress import calculate_progress, format_progress_bar

            state = json.loads(state_path.read_text(encoding="utf-8"))
            history = state.get("history", [])
            if isinstance(history, list) and history:
                last = history[-1]
                if isinstance(last, dict):
                    last_iteration = last
        except (OSError, ValueError) as e:
            logger.debug("Operation failed: %s", e)

        try:
            # Pass PRD path for accurate blocked task counting
            prd_path = root / cfg.files.prd
            metrics = calculate_progress(tracker, state, prd_path=prd_path)

            # Display progress bar
            progress_bar = format_progress_bar(
                metrics.completed_tasks, metrics.total_tasks, width=60
            )
            print_output(progress_bar, level="normal")
            print_output("", level="normal")

            # Display detailed metrics
            print_output("Detailed Progress Metrics:", level="normal")
            print_output(f"  Total Tasks:       {metrics.total_tasks}", level="normal")
            print_output(
                f"  Completed:         {metrics.completed_tasks}", level="normal"
            )
            print_output(
                f"  In Progress:       {metrics.in_progress_tasks}", level="normal"
            )
            print_output(
                f"  Blocked:           {metrics.blocked_tasks}", level="normal"
            )
            print_output(
                f"  Completion:        {metrics.completion_percentage:.1f}%",
                level="normal",
            )
            print_output("", level="normal")

            if metrics.velocity_tasks_per_day > 0:
                print_output(
                    f"  Velocity:          {metrics.velocity_tasks_per_day:.2f} tasks/day",
                    level="normal",
                )
                if metrics.estimated_completion_date:
                    print_output(
                        f"  Estimated ETA:     {metrics.estimated_completion_date}",
                        level="normal",
                    )
            else:
                print_output("  Velocity:          (insufficient data)", level="normal")

            return 0
        except (OSError, ValueError) as e:
            logger.debug("Progress calculation failed: %s", e)
            return 1

    # JSON output for cmd_status
    if get_output_config().format == "json":
        payload = {
            "cmd": "status",
            "prd": cfg.files.prd,
            "progress": {
                "done": done,
                "total": total,
            },
            "next": {
                "id": next_task.id,
                "title": next_task.title,
            }
            if next_task
            else None,
            "last_iteration": last_iteration,
        }
        print_json_output(payload)
        return 0

    print_output(f"PRD: {cfg.files.prd}", level="normal")
    # Show detailed progress: X/Y done (A blocked, B open)
    if blocked > 0 or open_count > 0:
        print_output(
            f"Progress: {done}/{total} done ({blocked} blocked, {open_count} open)",
            level="normal",
        )
    else:
        print_output(f"Progress: {done}/{total} tasks done", level="normal")
    if next_task is not None:
        print_output(f"Next: id={next_task.id} title={next_task.title}", level="normal")
    else:
        print_output("Next: (none)", level="normal")

    # Show last iteration summary (from .ralph/state.json)
    if last_iteration is not None:
        print_output("\nLast iteration:", level="normal")
        for k in [
            "ts",
            "iteration",
            "agent",
            "story_id",
            "duration_seconds",
            "return_code",
            "repo_clean",
            "gates_ok",
            "judge_ok",
            "exit_signal_effective",
            "log",
        ]:
            if k in last_iteration:
                print_output(f"  {k}: {last_iteration[k]}", level="normal")
    return 0


# -------------------------
# specs
# -------------------------


def cmd_specs_check(args: argparse.Namespace) -> int:
    root = _project_root()
    cfg = load_config(root)
    res = check_specs(root, specs_dir=str(args.specs_dir or cfg.files.specs_dir))
    print_output(format_specs_check(res), end="", level="normal")
    if not res.ok:
        return 2
    if args.strict and res.warnings:
        return 2
    return 0


# -------------------------
# planning helpers
# -------------------------


def _plan_prompt(prd_filename: str, desc: str) -> str:
    ext = Path(prd_filename).suffix.lower()
    lines: list[str] = []
    lines.append(
        "You are generating a prioritized task file (plan/backlog) for the Golden Ralph Loop."
    )
    lines.append("")
    lines.append(f"Write or update the task file at: {prd_filename} (repo root).")
    lines.append(
        "Do NOT implement any code in this step. Only produce the plan/task list."
    )
    lines.append("")

    if ext in {".md", ".markdown"}:
        lines.append("Format: Markdown")
        lines.append("- Include a '## Tasks' section.")
        lines.append("- Put each task on its own checkbox line: '- [ ] <task>'.")
        lines.append(
            "- Optional (recommended): add indented acceptance bullets under each task."
        )
        lines.append("  Example:")
        lines.append("  - [ ] Add feature X")
        lines.append("    - Acceptance: ...")
        lines.append("    - Tests: ...")
        lines.append("- Keep tasks small and independently verifiable.")
    else:
        lines.append("Format: JSON")
        lines.append("- Create a JSON object with a top-level 'stories' array.")
        lines.append(
            "- Each story must have: id (int), priority (int), title, description, acceptance (array of strings)."
        )
        lines.append(
            "- Mark each story as not done (either 'passes': false or 'status': 'open')."
        )

    lines.append("")
    lines.append("User description:")
    lines.append(desc.strip())
    lines.append("")
    lines.append(
        "After writing the task file, briefly summarize the task list you created."
    )
    return "\n".join(lines) + "\n"


def _regen_plan_prompt(project_root: Path, prd_filename: str, specs_report: str) -> str:
    """Prompt to regenerate the entire implementation plan.

    This is the "cheap reset" move in the Ralph Wiggum loop: refresh the plan
    by re-reading specs + codebase and rewriting IMPLEMENTATION_PLAN.md.
    """

    # Prefer using the project's planning prompt as the base, if present.
    base_path = project_root / ".ralph" / "PROMPT_plan.md"
    if not base_path.exists():
        base_path = project_root / "PROMPT_plan.md"
    base = base_path.read_text(encoding="utf-8") if base_path.exists() else ""

    lines: list[str] = []
    if base.strip():
        lines.append(base.rstrip())
        lines.append("\n---\n")

    lines.append("## Orchestrator Addendum (Regenerate Plan)")
    lines.append("")
    lines.append(f"Target plan/task file: {prd_filename}")
    lines.append("")
    lines.append("You are in PLANNING MODE.")
    lines.append("Do NOT implement production code in this run.")
    lines.append("")
    lines.append("Task:")
    lines.append("1) Read specs/*.md and the current codebase.")
    lines.append(
        "2) Perform a gap analysis: what is missing, partial, or inconsistent?"
    )
    lines.append("3) Rewrite the plan file from scratch as a prioritized task queue.")
    lines.append("")
    lines.append("Plan format requirements:")
    lines.append("- Use Markdown checkboxes under a '## Tasks' heading.")
    lines.append(
        "- Each checkbox task must be shippable in ONE iteration / ONE commit."
    )
    lines.append("- Under each checkbox, add 2-5 indented bullet acceptance criteria.")
    lines.append(
        "- Tasks must be objectively verifiable (tests/lint/typecheck/CLI commands)."
    )
    lines.append("- Keep it short; it's okay to regenerate again later.")
    lines.append("")
    if specs_report.strip():
        lines.append("Specs check (from orchestrator):")
        lines.append("```text")
        lines.append(specs_report.rstrip())
        lines.append("```")
        lines.append("")

    lines.append("Exit protocol:")
    lines.append("At the end of your output, print: EXIT_SIGNAL: false")
    lines.append("")
    return "\n".join(lines) + "\n"


# -------------------------
# planning commands
# -------------------------


def cmd_plan(args: argparse.Namespace) -> int:
    root = _project_root()
    cfg = load_config(root)

    desc = ""
    if args.desc_file:
        desc = Path(args.desc_file).read_text(encoding="utf-8")
    elif args.desc:
        desc = str(args.desc)
    else:
        # Allow piping multi-line text into the command.
        desc = sys.stdin.read() or ""

    if not desc.strip():
        print_output(
            "No description provided. Use --desc, --desc-file, or pipe text into stdin.",
            level="error",
        )
        return 2

    prd_filename = str(args.prd_file) if args.prd_file else cfg.files.prd
    prompt_text = _plan_prompt(prd_filename, desc)

    state_dir = root / ".ralph"
    logs_dir = state_dir / "logs"
    state_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)

    agent = str(args.agent).strip() if args.agent else _default_planner_agent(cfg)
    runner = cfg.runners.get(agent)
    if runner is None:
        available = ", ".join(sorted(cfg.runners.keys()))
        print_output(f"Unknown agent '{agent}'. Available: {available}", level="error")
        return 2

    argv, stdin_text = build_runner_invocation(agent, runner.argv, prompt_text)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = logs_dir / f"{ts}-plan-{agent}.log"

    start = time.time()
    timed_out = False
    timeout_s = (
        int(cfg.loop.runner_timeout_seconds)
        if int(cfg.loop.runner_timeout_seconds) > 0
        else None
    )
    try:
        cp = subprocess.run(
            argv,
            cwd=str(root),
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as e:
        timed_out = True
        cp = subprocess.CompletedProcess(
            argv, returncode=124, stdout=e.stdout or "", stderr=e.stderr or ""
        )
    duration_s = time.time() - start

    log_path.write_text(
        f"# ralph-gold plan log\n"
        f"timestamp_utc: {ts}\n"
        f"agent: {agent}\n"
        f"cmd: {json.dumps(argv)}\n"
        f"duration_seconds: {duration_s:.2f}\n"
        f"timed_out: {timed_out}\n"
        f"stdin: {stdin_text is not None}\n"
        f"return_code: {cp.returncode}\n"
        f"\n--- prompt ---\n{prompt_text}\n"
        f"\n--- stdout ---\n{cp.stdout or ''}\n"
        f"\n--- stderr ---\n{cp.stderr or ''}\n",
        encoding="utf-8",
    )

    print_output(
        f"Plan run complete (rc={cp.returncode}). Log: {log_path}", level="quiet"
    )
    return int(cp.returncode)


def cmd_regen_plan(args: argparse.Namespace) -> int:
    """Regenerate IMPLEMENTATION_PLAN.md from specs/* + codebase gap analysis."""

    root = _project_root()
    cfg = load_config(root)

    prd_filename = str(args.prd_file) if args.prd_file else cfg.files.prd

    specs_report = ""
    if not args.no_specs_check:
        try:
            sc = check_specs(root, specs_dir=str(args.specs_dir or cfg.files.specs_dir))
            specs_report = format_specs_check(sc)
        except (OSError, ValueError) as e:
            logger.debug("Operation failed: %s", e)

    prompt_text = _regen_plan_prompt(root, prd_filename, specs_report)
    logs_dir = root / ".ralph" / "logs"
    logs_dir.mkdir(exist_ok=True)

    agent = str(args.agent).strip() if args.agent else _default_planner_agent(cfg)
    runner = cfg.runners.get(agent)
    if runner is None:
        available = ", ".join(sorted(cfg.runners.keys()))
        print_output(f"Unknown agent '{agent}'. Available: {available}", level="error")
        return 2

    argv, stdin_text = build_runner_invocation(agent, runner.argv, prompt_text)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = logs_dir / f"{ts}-regen-plan-{agent}.log"

    start = time.time()
    timed_out = False
    timeout_s = (
        int(cfg.loop.runner_timeout_seconds)
        if int(cfg.loop.runner_timeout_seconds) > 0
        else None
    )
    try:
        cp = subprocess.run(
            argv,
            cwd=str(root),
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as e:
        timed_out = True
        cp = subprocess.CompletedProcess(
            argv, returncode=124, stdout=e.stdout or "", stderr=e.stderr or ""
        )
    duration_s = time.time() - start

    log_path.write_text(
        f"# ralph-gold regenerate-plan log\n"
        f"timestamp_utc: {ts}\n"
        f"agent: {agent}\n"
        f"cmd: {json.dumps(argv)}\n"
        f"duration_seconds: {duration_s:.2f}\n"
        f"timed_out: {timed_out}\n"
        f"stdin: {stdin_text is not None}\n"
        f"return_code: {cp.returncode}\n"
        f"\n--- prompt ---\n{prompt_text}\n"
        f"\n--- stdout ---\n{cp.stdout or ''}\n"
        f"\n--- stderr ---\n{cp.stderr or ''}\n",
        encoding="utf-8",
    )

    print_output(
        f"Regenerate plan run complete (rc={cp.returncode}). Log: {log_path}",
        level="quiet",
    )
    return int(cp.returncode)


# -------------------------
# snapshots
# -------------------------


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Create or list snapshots."""
    root = _project_root()

    # Handle list mode
    if args.list:
        snapshots = list_snapshots(root)

        # JSON output for list mode
        if get_output_config().format == "json":
            snapshots_payload = [
                {
                    "name": s.name,
                    "timestamp": s.timestamp,
                    "description": s.description,
                    "git_commit": s.git_commit,
                    "git_stash_ref": s.git_stash_ref,
                }
                for s in snapshots
            ]
            payload = {
                "cmd": "snapshot",
                "mode": "list",
                "snapshots": snapshots_payload,
            }
            print_json_output(payload)
            return 0

        if not snapshots:
            print_output("No snapshots found.", level="normal")
            return 0

        print_output("Available snapshots:", level="normal")
        print_output("", level="normal")

        # Sort by timestamp (newest first)
        snapshots.sort(key=lambda s: s.timestamp, reverse=True)

        for snapshot in snapshots:
            print_output(f"  {snapshot.name}", level="normal")
            print_output(f"    Created: {snapshot.timestamp}", level="normal")
            if snapshot.description:
                print_output(f"    Description: {snapshot.description}", level="normal")
            print_output(f"    Git commit: {snapshot.git_commit[:8]}", level="normal")
            print_output(f"    Stash ref: {snapshot.git_stash_ref}", level="normal")
            print_output("", level="normal")

        print_output(f"Total: {len(snapshots)} snapshot(s)", level="quiet")
        return 0

    # Create snapshot mode
    name = args.name
    description = args.description or ""

    if not name:
        print_output(
            "Error: snapshot name is required (use --list to list snapshots)",
            level="error",
        )
        return 2

    try:
        snapshot = create_snapshot(root, name, description)

        # JSON output for create mode
        if get_output_config().format == "json":
            payload = {
                "cmd": "snapshot",
                "mode": "create",
                "snapshot": {
                    "name": snapshot.name,
                    "timestamp": snapshot.timestamp,
                    "description": snapshot.description,
                    "git_commit": snapshot.git_commit,
                    "git_stash_ref": snapshot.git_stash_ref,
                    "state_backup_path": str(snapshot.state_backup_path),
                },
            }
            print_json_output(payload)
            return 0

        print_output(f"✓ Created snapshot '{snapshot.name}'", level="quiet")
        print_output(f"  Timestamp: {snapshot.timestamp}", level="normal")
        print_output(f"  Git stash: {snapshot.git_stash_ref}", level="normal")
        print_output(f"  State backup: {snapshot.state_backup_path}", level="normal")

        if description:
            print_output(f"  Description: {description}", level="normal")

        return 0

    except ValueError as e:
        print_output(f"Error: {e}", level="error")
        return 2
    except RuntimeError as e:
        print_output(f"Error: {e}", level="error")
        return 2


def cmd_rollback(args: argparse.Namespace) -> int:
    """Rollback to a previous snapshot."""
    root = _project_root()
    name = args.name
    force = args.force

    if not name:
        print_output("Error: snapshot name is required", level="error")
        print_output(
            "Use 'ralph snapshot --list' to see available snapshots", level="normal"
        )
        return 2

    try:
        # Show warning if not forcing
        if not force:
            print_output(f"Rolling back to snapshot '{name}'...", level="normal")
            print_output("This will restore git state and Ralph state.", level="normal")
            print_output("", level="normal")

            # Ask for confirmation in interactive mode
            try:
                response = input("Continue? [y/N]: ").strip().lower()
                if response not in {"y", "yes"}:
                    print_output("Rollback cancelled.", level="normal")
                    return 0
            except (KeyboardInterrupt, EOFError):
                print_output("\nRollback cancelled.", level="normal")
                return 0

        success = rollback_snapshot(root, name, force=force)

        if success:
            print_output(f"✓ Rolled back to snapshot '{name}'", level="quiet")
            print_output("  Git state and Ralph state restored", level="normal")
            return 0
        else:
            print_output(f"✗ Failed to rollback to snapshot '{name}'", level="error")
            return 2

    except ValueError as e:
        print_output(f"Error: {e}", level="error")
        return 2
    except RuntimeError as e:
        print_output(f"Error: {e}", level="error")
        return 2


# -------------------------
# watch
# -------------------------


def cmd_watch(args: argparse.Namespace) -> int:
    """Run watch mode with automatic gate execution on file changes."""
    root = _project_root()
    cfg = load_config(root)

    gates_only = args.gates_only
    auto_commit = args.auto_commit

    # Check if watch mode is enabled in config
    if not cfg.watch.enabled:
        print_output("Watch mode is not enabled in ralph.toml", level="error")
        print_output(
            "Set watch.enabled = true in the [watch] section to enable watch mode",
            level="normal",
        )
        return 2

    # JSON output not supported for watch mode (it's interactive)
    if get_output_config().format == "json":
        print_output(
            "JSON output format is not supported for watch mode", level="error"
        )
        return 2

    try:
        # Run watch mode (this blocks until Ctrl+C)
        run_watch_mode(
            root,
            cfg,
            gates_only=gates_only,
            auto_commit=auto_commit,
        )
        return 0
    except RuntimeError as e:
        print_output(f"Error: {e}", level="error")
        return 2
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        print_output("\nWatch mode stopped.", level="normal")
        return 0


# -------------------------
# task management
# -------------------------


def cmd_task_add(args: argparse.Namespace) -> int:
    """Add a new task from a template."""
    root = _project_root()
    cfg = load_config(root)

    template_name = args.template
    title = args.title

    if not template_name:
        print_output("Error: --template is required", level="error")
        print_output(
            "Use 'ralph task templates' to see available templates", level="normal"
        )
        return 2

    if not title:
        print_output("Error: --title is required", level="error")
        return 2

    # Load templates
    from .templates import TemplateError, create_task_from_template, list_templates

    try:
        templates = list_templates(root)
        template_dict = {t.name: t for t in templates}

        if template_name not in template_dict:
            print_output(f"Error: Template '{template_name}' not found", level="error")
            print_output("\nAvailable templates:", level="normal")
            for t in templates:
                print_output(f"  - {t.name}: {t.description}", level="normal")
            return 2

        template = template_dict[template_name]

        # Prepare variables
        variables = {"title": title}

        # Add any additional variables from args
        if hasattr(args, "variables") and args.variables:
            for var_assignment in args.variables:
                if "=" in var_assignment:
                    var_name, var_value = var_assignment.split("=", 1)
                    variables[var_name.strip()] = var_value.strip()

        # Create tracker
        tracker = make_tracker(root, cfg)

        # Create task from template
        task_id = create_task_from_template(template, variables, tracker)

        # JSON output
        if get_output_config().format == "json":
            payload = {
                "cmd": "task_add",
                "template": template_name,
                "task_id": task_id,
                "title": title,
            }
            print_json_output(payload)
            return 0

        print_output(
            f"✓ Created task '{task_id}' from template '{template_name}'", level="quiet"
        )
        print_output(
            f"  Title: {template.title_template.format(**variables)}", level="normal"
        )
        print_output(f"  Priority: {template.priority}", level="normal")
        print_output(
            f"  Acceptance criteria: {len(template.acceptance_criteria)} items",
            level="normal",
        )

        return 0

    except TemplateError as e:
        print_output(f"Error: {e}", level="error")
        return 2
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("JSON parse failed: %s", e)
        return 2


def cmd_task_templates(args: argparse.Namespace) -> int:
    """List available task templates."""
    root = _project_root()

    from .templates import list_templates

    try:
        templates = list_templates(root)

        # JSON output
        if get_output_config().format == "json":
            templates_payload = [
                {
                    "name": t.name,
                    "description": t.description,
                    "title_template": t.title_template,
                    "priority": t.priority,
                    "variables": t.variables,
                    "acceptance_criteria_count": len(t.acceptance_criteria),
                    "builtin": t.metadata.get("builtin", False),
                }
                for t in templates
            ]
            payload = {
                "cmd": "task_templates",
                "templates": templates_payload,
            }
            print_json_output(payload)
            return 0

        if not templates:
            print_output("No templates available.", level="normal")
            return 0

        print_output("Available Task Templates:", level="quiet")
        print_output("=" * 60, level="quiet")
        print_output("", level="quiet")

        for template in templates:
            builtin_marker = (
                " [built-in]" if template.metadata.get("builtin", False) else ""
            )
            print_output(f"{template.name}{builtin_marker}", level="normal")
            print_output(f"  Description: {template.description}", level="normal")
            print_output(f"  Title format: {template.title_template}", level="normal")
            print_output(f"  Priority: {template.priority}", level="normal")

            if template.variables:
                print_output(
                    f"  Variables: {', '.join(template.variables)}", level="normal"
                )

            print_output(
                f"  Acceptance criteria: {len(template.acceptance_criteria)} items",
                level="normal",
            )

            # Show acceptance criteria in verbose mode
            if get_output_config().verbosity == "verbose":
                for criterion in template.acceptance_criteria:
                    print_output(f"    - {criterion}", level="verbose")

            print_output("", level="normal")

        print_output("=" * 60, level="quiet")
        print_output(f"Total: {len(templates)} template(s)", level="quiet")
        print_output("", level="quiet")
        print_output("Usage:", level="normal")
        print_output(
            '  ralph task add --template <name> --title "Task title"', level="normal"
        )

        return 0

    except Exception as e:
        print_output(f"Error: {e}", level="error")
        return 2


# -------------------------
# bridge
# -------------------------


def cmd_bridge(args: argparse.Namespace) -> int:
    root = _project_root()
    from .bridge import BridgeServer

    server = BridgeServer(root)
    # JSON-RPC over stdio (NDJSON). This call blocks until stdin closes.
    server.serve()
    return 0


def cmd_blocked(args: argparse.Namespace) -> int:
    """Show blocked tasks with optional suggestions."""
    root = _project_root()
    from .unblock import BlockedTaskManager, format_blocked_table

    manager = BlockedTaskManager(root)
    blocked = manager.list_blocked_tasks()

    if not blocked:
        print_output("✅ No blocked tasks found.", level="normal")
        return 0

    if getattr(args, "format", "table") == "json":
        import json
        output = json.dumps([b.to_dict() for b in blocked], indent=2)
        print_output(output, level="normal")
    else:
        print_output(format_blocked_table(blocked), level="normal")

    # Show suggestions if requested
    if getattr(args, "suggest", False):
        print_output("\n📋 Unblock Suggestions:\n", level="normal")
        for task_info in blocked[:10]:  # Limit to 10 for readability
            suggestion = manager.suggest_unblock_strategy(task_info)
            print_output(
                f"Task {task_info.task_id}:\n{suggestion}\n",
                level="normal"
            )

    # Show statistics
    stats = manager.get_statistics()
    print_output(
        f"\n📊 Statistics:\n"
        f"  Total blocked: {stats['total_blocked']}\n"
        f"  Wasted iterations: {stats['total_wasted_iterations']}\n"
        f"  Avg attempts: {stats['avg_attempts']:.1f}\n"
        f"  By reason: {stats['by_reason']}\n"
        f"  By complexity: {stats['by_complexity']}\n",
        level="normal"
    )

    return 0


def cmd_unblock(args: argparse.Namespace) -> int:
    """Unblock a specific task for retry."""
    root = _project_root()
    from .unblock import BlockedTaskManager

    manager = BlockedTaskManager(root)

    # Normalize task_id (handle both "task-22" and "22" formats)
    task_id = args.task_id
    if not task_id.startswith("task-") and task_id.isdigit():
        task_id = f"task-{task_id}"

    # Get suggested timeout if not provided
    if args.timeout is None:
        blocked = manager.list_blocked_tasks()
        task_info = next((b for b in blocked if b.task_id == task_id), None)
        if task_info:
            args.timeout = task_info.suggested_timeout
        else:
            print_output(
                f"⚠️  Task {task_id} not found in blocked list. Using default timeout.",
                level="warning"
            )
            args.timeout = 120

    result = manager.unblock_task(
        task_id=task_id,
        reason=args.reason,
        new_timeout=args.timeout,
    )

    if result.success:
        print_output(
            f"✅ {result.message}",
            level="normal"
        )
        if result.new_timeout > 0:
            print_output(
                f"   New timeout for retry: {result.new_timeout}s ({result.new_timeout // 60} minutes)",
                level="normal"
            )
        print_output(
            f"   Previous attempts: {result.previous_attempts}",
            level="normal"
        )
        return 0
    else:
        print_output(f"❌ {result.message}", level="error")
        return 1


def cmd_retry_blocked(args: argparse.Namespace) -> int:
    """Retry all blocked tasks with increased timeouts."""
    root = _project_root()
    from .unblock import BlockedTaskManager

    manager = BlockedTaskManager(root)

    # Get filter type
    filter_type = getattr(args, "filter", "timeout")

    # Build filter parameters
    filter_complexity = "ui_heavy" if filter_type == "ui_heavy" else None

    if args.dry_run:
        # Show what would be done without actually doing it
        blocked = manager.list_blocked_tasks()

        if filter_type == "all":
            to_unblock = blocked
        elif filter_complexity:
            to_unblock = [b for b in blocked if b.complexity_level == filter_complexity]
        else:
            to_unblock = [b for b in blocked if b.reason == filter_type]

        print_output(f"🔍 Dry run: would unblock {len(to_unblock)} tasks", level="normal")
        print_output("Tasks to unblock:\n", level="normal")
        for task in to_unblock[:10]:
            new_timeout = int(task.suggested_timeout * args.timeout_multiplier)
            print_output(
                f"  {task.task_id}: {task.title[:50]}...",
                level="normal"
            )
            print_output(
                f"    New timeout: {new_timeout}s ({new_timeout // 60} min)\n",
                level="normal"
            )
        if len(to_unblock) > 10:
            print_output(f"  ... and {len(to_unblock) - 10} more tasks\n", level="normal")
        return 0

    # Actually perform the batch unblock
    results = manager.batch_unblock(
        filter_reason=None if filter_type == "all" else filter_type,
        filter_complexity=filter_complexity,
        min_attempts=1,
        new_timeout_multiplier=args.timeout_multiplier,
    )

    # Report results
    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count

    if success_count > 0:
        print_output(f"✅ Successfully unblocked {success_count} task(s)", level="normal")
    if fail_count > 0:
        print_output(f"⚠️  {fail_count} task(s) failed to unblock", level="warning")

    # Show next steps
    if success_count > 0:
        print_output("\n📋 Next steps:", level="normal")
        print_output("  1. Review unblocked tasks: ralph status", level="normal")
        print_output("  2. Resume the loop: ralph run --agent <your-agent>", level="normal")
        print_output("  3. Monitor: ralph status --watch", level="normal")

    return 0 if fail_count == 0 else 1


def cmd_tui(args: argparse.Namespace) -> int:
    root = _project_root()
    from .tui import run_tui

    return int(run_tui(root))


def cmd_serve(args: argparse.Namespace) -> int:
    from .health import serve_health

    serve_health(host=str(args.host), port=int(args.port), version=__version__)
    return 0


# -------------------------
# convert
# -------------------------


def cmd_completion(args: argparse.Namespace) -> int:
    """Generate shell completion scripts."""
    import sys

    from .completion import generate_bash_completion, generate_zsh_completion

    shell = args.shell

    if shell == "bash":
        script = generate_bash_completion()
        print(script)
        print_output("\n# Installation instructions:", level="normal", file=sys.stderr)
        print_output(
            "# Save to file: ralph completion bash > ~/.ralph-completion.sh",
            level="normal",
            file=sys.stderr,
        )
        print_output(
            "# Add to ~/.bashrc: source ~/.ralph-completion.sh",
            level="normal",
            file=sys.stderr,
        )
        print_output(
            "# Or install system-wide: sudo cp ~/.ralph-completion.sh /etc/bash_completion.d/ralph",
            level="normal",
            file=sys.stderr,
        )
    elif shell == "zsh":
        script = generate_zsh_completion()
        print(script)
        print_output("\n# Installation instructions:", level="normal", file=sys.stderr)
        print_output(
            "# Save to file: ralph completion zsh > ~/.zsh/completion/_ralph",
            level="normal",
            file=sys.stderr,
        )
        print_output(
            "# Add to ~/.zshrc: fpath=(~/.zsh/completion $fpath)",
            level="normal",
            file=sys.stderr,
        )
        print_output("# Then run: compinit", level="normal", file=sys.stderr)
    else:
        print_output(f"Error: Unknown shell '{shell}'", level="error")
        print_output("Supported shells: bash, zsh", level="error")
        return 2

    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    """Convert PRD files (JSON or Markdown) to YAML format."""
    from .converters import convert_to_yaml

    input_path = Path(args.input_file).resolve()
    output_path = Path(args.output_file).resolve()

    try:
        convert_to_yaml(
            input_path=input_path,
            output_path=output_path,
            infer_groups=bool(args.infer_groups),
        )

        print_output(f"✓ Converted {input_path.name} to {output_path}", level="quiet")

        if args.infer_groups:
            print_output("  Groups inferred from task titles", level="quiet")

        # Show summary
        import yaml

        with open(output_path) as f:
            data = yaml.safe_load(f)

        tasks = data.get("tasks", [])
        total = len(tasks)
        completed = sum(1 for t in tasks if t.get("completed", False))

        print_output(f"  Tasks: {total} total, {completed} completed", level="quiet")

        if args.infer_groups:
            groups = {}
            for task in tasks:
                group = task.get("group", "default")
                groups[group] = groups.get(group, 0) + 1

            if len(groups) > 1:
                print_output(
                    f"  Groups: {', '.join(f'{g} ({c})' for g, c in sorted(groups.items()))}",
                    level="quiet",
                )

        return 0

    except FileNotFoundError as e:
        print_output(f"Error: {e}", level="error")
        return 2
    except ValueError as e:
        print_output(f"Error: {e}", level="error")
        return 2
    except Exception as e:
        print_output(f"Unexpected error: {e}", level="error")
        return 2


# -------------------------
# argparse
# -------------------------


def build_parser() -> argparse.ArgumentParser:
    p = _RalphArgumentParser(
        prog="ralph",
        description="ralph-gold: Golden Ralph Loop orchestrator (uv-first)",
    )
    p.add_argument("--version", action="version", version=f"ralph-gold {__version__}")

    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Initialize Ralph files in the current repo")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing files")
    p_init.add_argument(
        "--solo",
        action="store_true",
        help="Use solo-dev optimized defaults for ralph.toml",
    )
    p_init.add_argument(
        "--format",
        choices=["markdown", "yaml"],
        default=None,
        help="Task tracker format (default: markdown)",
    )
    p_init.add_argument(
        "--no-merge-config",
        action="store_true",
        help="Disable config merging on --force (overwrite instead of merge)",
    )
    p_init.add_argument(
        "--merge-strategy",
        choices=["user_wins", "template_wins", "ask"],
        default="user_wins",
        help="Config merge strategy when using --force (default: user_wins)",
    )
    p_init.set_defaults(func=cmd_init)

    p_doc = sub.add_parser(
        "doctor", help="Check local prerequisites (git, uv, agent CLIs)"
    )
    p_doc.add_argument(
        "--setup-checks",
        action="store_true",
        help="Auto-configure quality gates for your project",
    )
    p_doc.add_argument(
        "--dry-run", action="store_true", help="Preview changes without applying them"
    )
    p_doc.add_argument(
        "--check-github",
        action="store_true",
        help="Check GitHub authentication (gh CLI or token)",
    )
    p_doc.set_defaults(func=cmd_doctor)

    p_diagnose = sub.add_parser(
        "diagnose",
        help="Run diagnostic checks on configuration and PRD",
    )
    p_diagnose.add_argument(
        "--test-gates",
        action="store_true",
        help="Test each gate command individually",
    )
    p_diagnose.set_defaults(func=cmd_diagnose)

    p_stats = sub.add_parser(
        "stats",
        help="Display iteration statistics from Ralph history",
    )
    p_stats.add_argument(
        "--by-task",
        action="store_true",
        help="Show detailed per-task breakdown",
    )
    p_stats.add_argument(
        "--export",
        metavar="FILE",
        default=None,
        help="Export statistics to CSV file",
    )
    p_stats.set_defaults(func=cmd_stats)

    # Harness commands
    p_harness = sub.add_parser(
        "harness",
        help="Collect/evaluate/report harness artifacts for regression tracking",
    )
    p_harness_sub = p_harness.add_subparsers(
        dest="harness_subcommand",
        title="harness subcommands",
        required=True,
    )

    p_harness_collect = p_harness_sub.add_parser(
        "collect",
        help="Collect harness cases from .ralph state and receipts",
    )
    p_harness_collect.add_argument(
        "--days",
        type=int,
        default=None,
        help="Only include cases from the last N days (default: from config)",
    )
    p_harness_collect.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of cases to include (default: from config)",
    )
    p_harness_collect.add_argument(
        "--output",
        default=None,
        help="Dataset output path (default: harness.dataset_path)",
    )
    p_harness_collect.add_argument(
        "--include-failures",
        action="store_true",
        default=True,
        help="Include failed cases (default: true)",
    )
    p_harness_collect.add_argument(
        "--exclude-failures",
        dest="include_failures",
        action="store_false",
        help="Exclude failed cases",
    )
    p_harness_collect.add_argument(
        "--redact",
        action="store_true",
        default=True,
        help="Redact long/sensitive fields where possible (default: true)",
    )
    p_harness_collect.add_argument(
        "--pinned-input",
        default=None,
        help="Pinned dataset path (default: harness.pinned_dataset_path)",
    )
    p_harness_collect.add_argument(
        "--append-pinned",
        dest="append_pinned",
        action="store_true",
        default=None,
        help="Append pinned cases to collected dataset (default: from config)",
    )
    p_harness_collect.add_argument(
        "--no-append-pinned",
        dest="append_pinned",
        action="store_false",
        help="Do not append pinned cases",
    )
    p_harness_collect.add_argument(
        "--max-cases-per-task",
        type=int,
        default=None,
        help="Cap collected cases per task_id (default: harness.max_cases_per_task)",
    )
    p_harness_collect.set_defaults(func=cmd_harness_collect)

    p_harness_run = p_harness_sub.add_parser(
        "run",
        help="Evaluate harness dataset and produce run metrics",
    )
    p_harness_run.add_argument(
        "--dataset",
        default=None,
        help="Input dataset path (default: harness.dataset_path)",
    )
    p_harness_run.add_argument(
        "--agent",
        default="codex",
        help="Agent label for run metadata (default: codex)",
    )
    p_harness_run.add_argument(
        "--mode",
        choices=LOOP_MODE_NAMES,
        default=None,
        help="Mode label for run metadata (default: loop.mode)",
    )
    p_harness_run.add_argument(
        "--isolation",
        choices=["worktree", "snapshot"],
        default=None,
        help="Replay isolation strategy label (default: harness.replay.default_isolation)",
    )
    p_harness_run.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Evaluate only the first N cases",
    )
    p_harness_run.add_argument(
        "--baseline",
        default=None,
        help="Baseline harness run JSON for regression comparison",
    )
    p_harness_run.add_argument(
        "--output",
        default=None,
        help="Run output path (default: harness.runs_dir/<timestamp>.json)",
    )
    p_harness_run.add_argument(
        "--enforce-regression-threshold",
        action="store_true",
        help="Exit non-zero when run is regressed vs baseline",
    )
    p_harness_run.add_argument(
        "--execution-mode",
        choices=["historical", "live"],
        default="historical",
        help="Evaluation mode: historical replay or live targeted execution (default: historical)",
    )
    p_harness_run.add_argument(
        "--bucket",
        choices=["all", "small", "medium", "large"],
        default="all",
        help="Only evaluate a bucket subset (default: all)",
    )
    p_harness_run.add_argument(
        "--report-breakdown",
        dest="report_breakdown",
        action="store_true",
        default=True,
        help="Include per-bucket breakdown in report output (default: true)",
    )
    p_harness_run.add_argument(
        "--no-report-breakdown",
        dest="report_breakdown",
        action="store_false",
        help="Disable per-bucket breakdown in report output",
    )
    p_harness_run.add_argument(
        "--strict-targeting",
        action="store_true",
        default=True,
        help="In live mode, fail targeted case when target is done/blocked/missing (default: true)",
    )
    p_harness_run.add_argument(
        "--allow-non-strict-targeting",
        dest="strict_targeting",
        action="store_false",
        help="In live mode, allow done/blocked target execution",
    )
    p_harness_run.add_argument(
        "--continue-on-target-error",
        action="store_true",
        default=True,
        help="In live mode, continue batch even if a case target fails (default: true)",
    )
    p_harness_run.add_argument(
        "--stop-on-target-error",
        dest="continue_on_target_error",
        action="store_false",
        help="In live mode, stop on first target resolution failure",
    )
    p_harness_run.set_defaults(func=cmd_harness_run)

    p_harness_pin = p_harness_sub.add_parser(
        "pin",
        help="Promote failing run cases into pinned harness dataset",
    )
    p_harness_pin.add_argument(
        "--run",
        required=True,
        help="Harness run JSON path to source failing cases from",
    )
    p_harness_pin.add_argument(
        "--dataset",
        default=None,
        help="Optional dataset path for enriching pinned cases",
    )
    p_harness_pin.add_argument(
        "--output",
        default=None,
        help="Pinned dataset output path (default: harness.pinned_dataset_path)",
    )
    p_harness_pin.add_argument(
        "--status",
        action="append",
        default=[],
        help="Filter by run status (repeatable)",
    )
    p_harness_pin.add_argument(
        "--failure-category",
        action="append",
        default=[],
        help="Filter by failure category (repeatable)",
    )
    p_harness_pin.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Pin at most N matching cases",
    )
    p_harness_pin.add_argument(
        "--redact",
        action="store_true",
        default=True,
        help="Redact long/sensitive fields where possible (default: true)",
    )
    p_harness_pin.set_defaults(func=cmd_harness_pin)

    p_harness_ci = p_harness_sub.add_parser(
        "ci",
        help="Run collect + evaluate in one CI-friendly command",
    )
    p_harness_ci.add_argument(
        "--days",
        type=int,
        default=None,
        help="Only include cases from last N days (default: harness.default_days)",
    )
    p_harness_ci.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of collected cases (default: harness.default_limit)",
    )
    p_harness_ci.add_argument(
        "--dataset",
        default=None,
        help="Dataset output path (default: harness.dataset_path)",
    )
    p_harness_ci.add_argument(
        "--output",
        default=None,
        help="Run output path (default: harness.runs_dir/ci-<timestamp>.json)",
    )
    p_harness_ci.add_argument(
        "--baseline",
        default=None,
        help="Baseline run path override (default: harness.baseline_run_path)",
    )
    p_harness_ci.add_argument(
        "--agent",
        default="codex",
        help="Agent label for run metadata (default: codex)",
    )
    p_harness_ci.add_argument(
        "--mode",
        choices=LOOP_MODE_NAMES,
        default=None,
        help="Mode label for run metadata (default: loop.mode)",
    )
    p_harness_ci.add_argument(
        "--isolation",
        choices=["worktree", "snapshot"],
        default=None,
        help="Replay isolation strategy label (default: harness.replay.default_isolation)",
    )
    p_harness_ci.add_argument(
        "--execution-mode",
        choices=["historical", "live"],
        default=None,
        help="Execution mode (default: harness.ci.execution_mode)",
    )
    p_harness_ci.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Max evaluated cases (default: harness.ci.max_cases)",
    )
    p_harness_ci.add_argument(
        "--bucket",
        choices=["all", "small", "medium", "large"],
        default="all",
        help="Only evaluate a bucket subset (default: all)",
    )
    p_harness_ci.add_argument(
        "--enforce-regression-threshold",
        dest="enforce_regression_threshold",
        action="store_true",
        default=None,
        help="Fail CI when run regresses versus baseline (default: harness.ci.enforce_regression_threshold)",
    )
    p_harness_ci.add_argument(
        "--no-enforce-regression-threshold",
        dest="enforce_regression_threshold",
        action="store_false",
        help="Do not fail CI on regression threshold breach",
    )
    p_harness_ci.add_argument(
        "--require-baseline",
        dest="require_baseline",
        action="store_true",
        default=None,
        help="Require baseline run availability (default: harness.ci.require_baseline)",
    )
    p_harness_ci.add_argument(
        "--allow-missing-baseline",
        dest="require_baseline",
        action="store_false",
        help="Allow CI run when baseline is missing",
    )
    p_harness_ci.add_argument(
        "--baseline-missing-policy",
        choices=["fail", "warn"],
        default=None,
        help="Policy when baseline missing and required (default: harness.ci.baseline_missing_policy)",
    )
    p_harness_ci.add_argument(
        "--include-failures",
        action="store_true",
        default=True,
        help="Include failed cases while collecting dataset (default: true)",
    )
    p_harness_ci.add_argument(
        "--exclude-failures",
        dest="include_failures",
        action="store_false",
        help="Exclude failed cases while collecting dataset",
    )
    p_harness_ci.add_argument(
        "--redact",
        action="store_true",
        default=True,
        help="Redact long/sensitive fields where possible (default: true)",
    )
    p_harness_ci.add_argument(
        "--pinned-input",
        default=None,
        help="Pinned dataset input path (default: harness.pinned_dataset_path)",
    )
    p_harness_ci.add_argument(
        "--append-pinned",
        dest="append_pinned",
        action="store_true",
        default=None,
        help="Append pinned cases to collected dataset (default: from config)",
    )
    p_harness_ci.add_argument(
        "--no-append-pinned",
        dest="append_pinned",
        action="store_false",
        help="Do not append pinned cases",
    )
    p_harness_ci.add_argument(
        "--max-cases-per-task",
        type=int,
        default=None,
        help="Cap collected cases per task_id (default: harness.max_cases_per_task)",
    )
    p_harness_ci.add_argument(
        "--strict-targeting",
        action="store_true",
        default=True,
        help="In live mode, fail targeted case when target is done/blocked/missing (default: true)",
    )
    p_harness_ci.add_argument(
        "--allow-non-strict-targeting",
        dest="strict_targeting",
        action="store_false",
        help="In live mode, allow done/blocked target execution",
    )
    p_harness_ci.add_argument(
        "--continue-on-target-error",
        action="store_true",
        default=True,
        help="In live mode, continue batch even if a case target fails (default: true)",
    )
    p_harness_ci.add_argument(
        "--stop-on-target-error",
        dest="continue_on_target_error",
        action="store_false",
        help="In live mode, stop on first target resolution failure",
    )
    p_harness_ci.set_defaults(func=cmd_harness_ci)

    p_harness_report = p_harness_sub.add_parser(
        "report",
        help="Render harness run report",
    )
    p_harness_report.add_argument(
        "--input",
        default=None,
        help="Harness run JSON path (default: latest run in harness.runs_dir)",
    )
    p_harness_report.add_argument(
        "--baseline",
        default=None,
        help="Optional baseline run JSON for comparison",
    )
    p_harness_report.add_argument(
        "--format",
        dest="report_format",
        choices=["text", "json", "csv"],
        default="text",
        help="Report output format (default: text)",
    )
    p_harness_report.set_defaults(func=cmd_harness_report)

    p_harness_doctor = p_harness_sub.add_parser(
        "doctor",
        help="Validate harness config and artifact schema integrity",
    )
    p_harness_doctor.add_argument(
        "--max-run-files",
        type=int,
        default=10,
        help="Maximum run files to validate in harness.runs_dir (default: 10)",
    )
    p_harness_doctor.set_defaults(func=cmd_harness_doctor)

    p_resume = sub.add_parser(
        "resume",
        help="Detect and resume interrupted iterations",
    )
    p_resume.add_argument(
        "--clear",
        action="store_true",
        help="Clear the interrupted iteration without resuming",
    )
    p_resume.add_argument(
        "--auto",
        action="store_true",
        help="Resume automatically without prompting",
    )
    p_resume.set_defaults(func=cmd_resume)

    p_clean = sub.add_parser(
        "clean",
        help="Clean old logs, archives, and other workspace artifacts",
    )
    p_clean.add_argument(
        "--logs-days",
        type=int,
        default=30,
        help="Remove logs older than N days (default: 30)",
    )
    p_clean.add_argument(
        "--archives-days",
        type=int,
        default=90,
        help="Remove archives older than N days (default: 90)",
    )
    p_clean.add_argument(
        "--receipts-days",
        type=int,
        default=60,
        help="Remove receipts older than N days (default: 60)",
    )
    p_clean.add_argument(
        "--context-days",
        type=int,
        default=60,
        help="Remove context files older than N days (default: 60)",
    )
    p_clean.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be deleted without actually deleting",
    )
    p_clean.set_defaults(func=cmd_clean)

    # State management subcommands
    p_state = sub.add_parser(
        "state",
        help="State management commands",
    )
    p_state_sub = p_state.add_subparsers(
        dest="state_subcommand",
        title="state subcommands",
        required=True,
    )

    p_cleanup = p_state_sub.add_parser(
        "cleanup",
        help="Remove stale task IDs from state.json",
    )
    p_cleanup.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be removed without actually removing",
    )
    p_cleanup.set_defaults(func=cmd_state_cleanup)

    p_step = sub.add_parser("step", help="Run exactly one iteration")
    p_step.add_argument(
        "--agent",
        default="codex",
        help="Runner to use (codex|claude|copilot or custom runner name)",
    )
    p_step.add_argument(
        "--mode",
        choices=LOOP_MODE_NAMES,
        help="Override loop.mode (speed|quality|exploration)",
    )
    p_step.add_argument(
        "--prompt-file",
        default=None,
        help="Override files.prompt for this run (e.g. PROMPT_plan.md)",
    )
    p_step.add_argument(
        "--prd-file",
        default=None,
        help="Override files.prd for this run (e.g. IMPLEMENTATION_PLAN.md)",
    )
    p_step.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without running agents (validate config and show execution plan)",
    )
    p_step.add_argument(
        "--interactive",
        action="store_true",
        help="Interactively select which task to work on from available tasks",
    )
    p_step.add_argument(
        "--task-id",
        default=None,
        help="Execute a specific task ID instead of auto-selecting next task",
    )
    p_step.add_argument(
        "--allow-done-target",
        action="store_true",
        help="Allow targeting a task currently marked done",
    )
    p_step.add_argument(
        "--allow-blocked-target",
        action="store_true",
        help="Allow targeting a task currently marked blocked",
    )
    p_step.add_argument(
        "--reopen-target",
        action="store_true",
        help="Attempt to reopen target task before running",
    )
    p_step.set_defaults(func=cmd_step)

    p_run = sub.add_parser(
        "run",
        help="Run the loop for N iterations (default from ralph.toml). Exit codes: 0=success, 1=incomplete, 2=failed.",
    )
    p_run.add_argument(
        "--agent",
        default="codex",
        help="Runner to use (codex|claude|copilot or custom)",
    )
    p_run.add_argument(
        "--mode",
        choices=LOOP_MODE_NAMES,
        help="Override loop.mode (speed|quality|exploration)",
    )
    p_run.add_argument(
        "--max-iterations", type=int, default=None, help="Override loop.max_iterations"
    )
    p_run.add_argument(
        "--prompt-file", default=None, help="Override files.prompt for this run"
    )
    p_run.add_argument(
        "--prd-file", default=None, help="Override files.prd for this run"
    )
    p_run.add_argument(
        "--parallel",
        action="store_true",
        help="Enable parallel execution with git worktrees (overrides config)",
    )
    p_run.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Number of parallel workers (requires --parallel, overrides config)",
    )
    p_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without running agents (validate config and show execution plan)",
    )
    p_run.add_argument(
        "--stream",
        action="store_true",
        help="Stream runner output live instead of buffering it (sequential mode only)",
    )
    p_run.set_defaults(func=cmd_run)

    p_supervise = sub.add_parser(
        "supervise",
        help="Run a long-lived supervisor loop (heartbeat + policy stops + notifications).",
    )
    p_supervise.add_argument(
        "--agent",
        default="codex",
        help="Runner to use for execution iterations (default: codex)",
    )
    p_supervise.add_argument(
        "--mode",
        choices=LOOP_MODE_NAMES,
        help="Override loop.mode (speed|quality|exploration)",
    )
    p_supervise.add_argument(
        "--max-runtime-seconds",
        type=int,
        default=None,
        help="Stop after N seconds (0/unset = unlimited)",
    )
    p_supervise.add_argument(
        "--heartbeat-seconds",
        type=int,
        default=None,
        help="Print a heartbeat every N seconds (default: from supervisor config)",
    )
    p_supervise.add_argument(
        "--sleep-seconds-between-runs",
        type=int,
        default=None,
        help="Sleep N seconds between iterations (default: from supervisor config)",
    )
    p_supervise.add_argument(
        "--on-no-progress-limit",
        choices=["stop", "continue"],
        default=None,
        help="Policy when no-progress limit is reached (default: from supervisor config)",
    )
    p_supervise.add_argument(
        "--on-rate-limit",
        choices=["wait", "stop"],
        default=None,
        help="Policy when rate limit is reached (default: from supervisor config)",
    )

    notify_group = p_supervise.add_mutually_exclusive_group()
    notify_group.add_argument(
        "--notify",
        action="store_true",
        help="Enable OS notifications (default: enabled)",
    )
    notify_group.add_argument(
        "--no-notify",
        action="store_true",
        help="Disable OS notifications",
    )
    p_supervise.add_argument(
        "--notify-backend",
        choices=["auto", "macos", "linux", "windows", "command", "none"],
        default=None,
        help="Notification backend (default: from supervisor config)",
    )
    p_supervise.add_argument(
        "--notify-command",
        nargs="+",
        default=None,
        help="Command argv to invoke for notifications when backend=command (appends title + message)",
    )
    p_supervise.set_defaults(func=cmd_supervise)

    p_status = sub.add_parser(
        "status", help="Show PRD progress + last iteration summary"
    )
    p_status.add_argument(
        "--graph",
        action="store_true",
        help="Display task dependency graph visualization",
    )
    p_status.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed progress metrics including velocity and ETA",
    )
    p_status.add_argument(
        "--chart",
        action="store_true",
        help="Display ASCII burndown chart of task completion over time",
    )
    p_status.set_defaults(func=cmd_status)

    # Blocked tasks management
    p_blocked = sub.add_parser("blocked", help="Show blocked tasks with suggestions")
    p_blocked.add_argument(
        "--suggest",
        action="store_true",
        help="Show unblock suggestions for each blocked task",
    )
    p_blocked.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )
    p_blocked.set_defaults(func=cmd_blocked)

    p_unblock = sub.add_parser("unblock", help="Unblock a task for retry")
    p_unblock.add_argument(
        "task_id",
        help="Task ID to unblock (e.g., 'task-22' or '22')",
    )
    p_unblock.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="New timeout for retry in seconds (default: suggested based on complexity)",
    )
    p_unblock.add_argument(
        "--reason",
        default="Manual unblock",
        help="Reason for unblocking (recorded in attempt history)",
    )
    p_unblock.set_defaults(func=cmd_unblock)

    p_retry_blocked = sub.add_parser(
        "retry-blocked",
        help="Retry all blocked tasks with increased timeouts"
    )
    p_retry_blocked.add_argument(
        "--filter",
        choices=["timeout", "no_files", "gate_failure", "ui_heavy", "all"],
        default="timeout",
        help="Only retry tasks with this block reason",
    )
    p_retry_blocked.add_argument(
        "--timeout-multiplier",
        type=float,
        default=1.0,
        help="Multiply suggested timeout by this factor (default: 1.0 = use suggested)",
    )
    p_retry_blocked.add_argument(
        "--max-attempts",
        type=int,
        default=1,
        help="Maximum number of retry attempts per task (default: 1)",
    )
    p_retry_blocked.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually unblocking",
    )
    p_retry_blocked.set_defaults(func=cmd_retry_blocked)

    p_tui = sub.add_parser("tui", help="Interactive control surface (TUI)")
    p_tui.set_defaults(func=cmd_tui)

    p_serve = sub.add_parser("serve", help="Serve a minimal HTTP health endpoint")
    p_serve.add_argument(
        "--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)"
    )
    p_serve.add_argument(
        "--port", type=int, default=8080, help="Bind port (default: 8080)"
    )
    p_serve.set_defaults(func=cmd_serve)

    # Specs
    p_specs = sub.add_parser("specs", help="Work with specs/*")
    specs_sub = p_specs.add_subparsers(dest="specs_cmd", required=True)

    p_specs_check = specs_sub.add_parser("check", help="Lint/check specs/*.md")
    p_specs_check.add_argument(
        "--specs-dir", default=None, help="Specs directory (default: from config)"
    )
    p_specs_check.add_argument(
        "--strict", action="store_true", help="Treat warnings as errors"
    )
    p_specs_check.set_defaults(func=cmd_specs_check)

    # Planning helpers
    p_plan = sub.add_parser(
        "plan",
        help="Generate/update PRD from a description (runs the chosen agent once)",
    )
    p_plan.add_argument(
        "--agent",
        default=None,
        help="Runner to use (defaults to claude-zai/claude-kimi/claude/codex if configured)",
    )
    p_plan.add_argument("--desc", default=None, help="Short description text")
    p_plan.add_argument(
        "--desc-file",
        default=None,
        help="Path to a text/markdown file containing the description",
    )
    p_plan.add_argument(
        "--prd-file",
        default=None,
        help="Target file to write (defaults to files.prd from ralph.toml)",
    )
    p_plan.set_defaults(func=cmd_plan)

    p_regen = sub.add_parser(
        "regen-plan",
        help="Regenerate IMPLEMENTATION_PLAN.md from specs/* + codebase gap analysis",
    )
    p_regen.add_argument(
        "--agent",
        default=None,
        help="Runner to use (defaults to claude-zai/claude-kimi/claude/codex if configured)",
    )
    p_regen.add_argument(
        "--prd-file", default=None, help="Target plan file (defaults to files.prd)"
    )
    p_regen.add_argument(
        "--specs-dir", default=None, help="Specs directory (default: from config)"
    )
    p_regen.add_argument(
        "--no-specs-check",
        action="store_true",
        help="Don't run specs check before generating prompt",
    )
    p_regen.set_defaults(func=cmd_regen_plan)

    # Snapshots
    p_snapshot = sub.add_parser(
        "snapshot",
        help="Create or list git-based snapshots for safe rollback",
    )
    p_snapshot.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Name for the snapshot (use only letters, numbers, hyphens, underscores)",
    )
    p_snapshot.add_argument(
        "--list",
        action="store_true",
        help="List all available snapshots",
    )
    p_snapshot.add_argument(
        "--description",
        "-d",
        default=None,
        help="Optional description for the snapshot",
    )
    p_snapshot.set_defaults(func=cmd_snapshot)

    p_rollback = sub.add_parser(
        "rollback",
        help="Rollback to a previous snapshot",
    )
    p_rollback.add_argument(
        "name",
        help="Name of the snapshot to rollback to",
    )
    p_rollback.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force rollback even with uncommitted changes",
    )
    p_rollback.set_defaults(func=cmd_rollback)

    # Watch mode
    p_watch = sub.add_parser(
        "watch",
        help="Watch files and automatically run gates on changes",
    )
    p_watch.add_argument(
        "--gates-only",
        action="store_true",
        default=True,
        help="Only run gates (don't run full loop) - default behavior",
    )
    p_watch.add_argument(
        "--auto-commit",
        action="store_true",
        help="Automatically commit changes when gates pass",
    )
    p_watch.set_defaults(func=cmd_watch)

    # Task management
    p_task = sub.add_parser("task", help="Manage tasks in the PRD")
    task_sub = p_task.add_subparsers(dest="task_cmd", required=True)

    p_task_add = task_sub.add_parser(
        "add",
        help="Add a new task from a template",
    )
    p_task_add.add_argument(
        "--template",
        "-t",
        required=True,
        help="Template name (use 'ralph task templates' to list available templates)",
    )
    p_task_add.add_argument(
        "--title",
        required=True,
        help="Task title (will be substituted into template)",
    )
    p_task_add.add_argument(
        "--var",
        dest="variables",
        action="append",
        help="Additional template variables in format VAR=value (can be used multiple times)",
    )
    p_task_add.set_defaults(func=cmd_task_add)

    p_task_templates = task_sub.add_parser(
        "templates",
        help="List available task templates",
    )
    p_task_templates.set_defaults(func=cmd_task_templates)

    p_bridge = sub.add_parser(
        "bridge", help="Start a JSON-RPC bridge over stdio (for VS Code)"
    )
    p_bridge.set_defaults(func=cmd_bridge)

    # Completion
    p_completion = sub.add_parser(
        "completion", help="Generate shell completion scripts"
    )
    p_completion.add_argument(
        "shell",
        choices=["bash", "zsh"],
        help="Shell type (bash or zsh)",
    )
    p_completion.set_defaults(func=cmd_completion)

    # Convert
    p_convert = sub.add_parser(
        "convert", help="Convert PRD files (JSON or Markdown) to YAML format"
    )
    p_convert.add_argument("input_file", help="Input PRD file (JSON or Markdown)")
    p_convert.add_argument("output_file", help="Output YAML file path")
    p_convert.add_argument(
        "--infer-groups",
        action="store_true",
        help="Infer parallel groups from task titles",
    )
    p_convert.set_defaults(func=cmd_convert)

    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    # Apply output config from TOML before dispatching to command
    try:
        root = Path(os.getcwd()).resolve()
        cfg = load_config(root)
        output_cfg = OutputConfig(
            verbosity=cfg.output.verbosity,
            format=cfg.output.format,
            color=True,  # Default for now
        )
        set_output_config(output_cfg)

        # Setup logging based on verbosity
        verbose = output_cfg.verbosity == "verbose"
        quiet = output_cfg.verbosity == "quiet"
        setup_logging(verbose=verbose, quiet=quiet)

        # Log startup
        logger = logging.getLogger(__name__)
        logger.debug(f"Ralph Gold v{__version__} starting")
        logger.debug(f"Command: {getattr(args, 'cmd', 'unknown')}")

        return int(args.func(args))
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error("%s", e)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
