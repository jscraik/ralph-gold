from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import asdict, replace
from pathlib import Path

from ..config import load_config
from ..diagnostics import run_diagnostics
from ..output import (
    get_output_config,
    print_json_output,
    print_output,
    set_output_config,
)
from ..progress import calculate_progress, format_burndown_chart, format_progress_bar
from ..stats import calculate_stats, export_stats_csv, format_flow_report, format_stats_report
from ..trackers import make_tracker

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    return Path(os.getcwd()).resolve()


def cmd_diagnose(args: argparse.Namespace) -> int:
    """Run diagnostic checks on Ralph configuration and PRD."""
    root = _project_root()
    test_gates = args.test_gates

    results, exit_code = run_diagnostics(root, test_gates_flag=test_gates)

    if get_output_config().format == "json":
        results_payload = [
            {
                "name": r.check_name,
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

    print_output("Ralph Diagnostics Report", level="quiet")
    print_output("=" * 60, level="quiet")
    print_output("", level="quiet")

    errors = [r for r in results if r.severity == "error" and not r.passed]
    warnings = [r for r in results if r.severity == "warning" and not r.passed]
    info = [r for r in results if r.passed or r.severity == "info"]

    if errors:
        print_output("ERRORS:", level="error")
        for result in errors:
            print_output(f"  ✗ {result.message}", level="error")
            if result.suggestions:
                for suggestion in result.suggestions:
                    print_output(f"    → {suggestion}", level="error")
            print_output("", level="error")

    if warnings:
        print_output("WARNINGS:", level="normal")
        for result in warnings:
            print_output(f"  ⚠ {result.message}", level="normal")
            if result.suggestions:
                for suggestion in result.suggestions:
                    print_output(f"    → {suggestion}", level="normal")
            print_output("", level="normal")

    if info:
        info_level = "normal" if test_gates else "verbose"
        print_output("PASSED:", level=info_level)
        for result in info:
            print_output(f"  ✓ {result.message}", level=info_level)
        print_output("", level=info_level)

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

    if getattr(args, "format", None):
        cfg = get_output_config()
        set_output_config(replace(cfg, format=args.format))

    if not state_path.exists():
        print_output("No state.json found. Run some iterations first.", level="normal")
        return 0

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as e:
        print_output(f"Error loading state.json: {e}", level="error")
        return 1

    try:
        stats = calculate_stats(state)
    except Exception as e:
        print_output(f"Error calculating statistics: {e}", level="error")
        return 1

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

    if get_output_config().format == "json":
        payload = {
            "cmd": "stats",
            "exported": exported,
            "export_path": str(export_path) if export_path else None,
            "stats": asdict(stats),
        }
        print_json_output(payload)
        return 0

    by_task = args.by_task
    flow = getattr(args, "flow", False)
    report = format_flow_report(stats) if flow else format_stats_report(stats, by_task=by_task)
    print_output(report, level="normal")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = _project_root()
    cfg = load_config(root)
    tracker = make_tracker(root, cfg)
    state_path = root / ".ralph" / "state.json"
    next_task = None
    last_iteration = None

    if getattr(args, "graph", False):
        from ..dependencies import build_dependency_graph, format_dependency_graph
        from ..prd import get_all_tasks

        prd_path = root / cfg.files.prd
        try:
            tasks = get_all_tasks(prd_path)
            if not tasks:
                print_output("No tasks found in PRD file.", level="normal")
                return 0
            graph = build_dependency_graph(tasks)
            print_output(format_dependency_graph(graph), level="normal")
            return 0
        except Exception as e:
            print_output(f"Error building dependency graph: {e}", level="error")
            return 1

    if getattr(args, "chart", False):
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
        print_output("No history data available for burndown chart.", level="normal")
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
        from ..prd import status_counts

        prd_path = root / cfg.files.prd
        done_detailed, blocked, open_count, total_from_prd = status_counts(prd_path)
        if total_from_prd > 0:
            total = total_from_prd
            done = done_detailed
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Failed to load PRD status counts: %s", e)

    state = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            history = state.get("history", [])
            if isinstance(history, list) and history and isinstance(history[-1], dict):
                last_iteration = history[-1]
        except (OSError, ValueError) as e:
            logger.debug("Operation failed: %s", e)

        try:
            prd_path = root / cfg.files.prd
            metrics = calculate_progress(tracker, state, prd_path=prd_path)
            progress_bar = format_progress_bar(
                metrics.completed_tasks, metrics.total_tasks, width=60
            )
            print_output(progress_bar, level="normal")
            print_output("", level="normal")
            print_output("Detailed Progress Metrics:", level="normal")
            print_output(f"  Total Tasks:       {metrics.total_tasks}", level="normal")
            print_output(f"  Completed:         {metrics.completed_tasks}", level="normal")
            print_output(f"  In Progress:       {metrics.in_progress_tasks}", level="normal")
            print_output(f"  Blocked:           {metrics.blocked_tasks}", level="normal")
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

    if get_output_config().format == "json":
        payload = {
            "cmd": "status",
            "prd": cfg.files.prd,
            "progress": {"done": done, "total": total},
            "next": {"id": next_task.id, "title": next_task.title} if next_task else None,
            "last_iteration": last_iteration,
        }
        print_json_output(payload)
        return 0

    print_output(f"PRD: {cfg.files.prd}", level="normal")
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
