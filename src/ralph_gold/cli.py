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


class _RalphArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.exit(2, f"Error: {message}\n")


# -------------------------
# init / doctor
# -------------------------


def cmd_init(args: argparse.Namespace) -> int:
    root = _project_root()
    format_type = getattr(args, "format", None)
    archived = init_project(
        root,
        force=bool(args.force),
        format_type=format_type,
        solo=bool(getattr(args, "solo", False)),
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
            except Exception:
                pass

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

        blocked_ids = set()
        if cfg.loop.skip_blocked_tasks:
            blocked_raw = state.get("blocked_tasks", {}) or {}
            if isinstance(blocked_raw, dict):
                blocked_ids = set(str(k) for k in blocked_raw.keys())

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
                temp_excluded = set(blocked_ids)
                for _ in range(20):  # Limit to 20 tasks to avoid infinite loop
                    try:
                        if hasattr(tracker, "select_next_task"):
                            task = tracker.select_next_task(exclude_ids=temp_excluded)  # type: ignore[arg-type]
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
                    except Exception:
                        break
        except Exception as e:
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

    iter_n = next_iteration_number(root)
    try:
        res = run_iteration(
            root, agent=agent, cfg=cfg, iteration=iter_n, task_override=task_override
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

    try:
        results = run_loop(
            root,
            agent=agent,
            max_iterations=args.max_iterations,
            cfg=cfg,
            parallel=parallel,
            max_workers=max_workers,
            dry_run=dry_run,
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


def cmd_status(args: argparse.Namespace) -> int:
    root = _project_root()
    cfg = load_config(root)
    tracker = make_tracker(root, cfg)

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
    except Exception:
        done, total = 0, 0

    # Get detailed status counts for accurate progress reporting
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
    except Exception:
        pass  # Fall back to simple counts if status_counts fails

    try:
        next_task = tracker.select_next_task()
    except Exception:
        next_task = None

    # Load state for progress metrics
    state_path = root / ".ralph" / "state.json"
    last_iteration = None
    state = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            history = state.get("history", [])
            if isinstance(history, list) and history:
                last = history[-1]
                if isinstance(last, dict):
                    last_iteration = last
        except Exception:
            pass

    # Handle --detailed flag for progress metrics
    if getattr(args, "detailed", False):
        from .progress import calculate_progress, format_progress_bar

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
        except Exception as e:
            print_output(f"Error calculating progress metrics: {e}", level="error")
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

    agent = args.agent
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
        except Exception:
            specs_report = ""

    prompt_text = _regen_plan_prompt(root, prd_filename, specs_report)

    state_dir = root / ".ralph"
    logs_dir = state_dir / "logs"
    state_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)

    agent = args.agent
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
    except Exception as e:
        print_output(f"Unexpected error: {e}", level="error")
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
        choices=["markdown", "json", "yaml"],
        default=None,
        help="Task tracker format (default: markdown)",
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
    p_run.set_defaults(func=cmd_run)

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
        default="codex",
        help="Runner to use (codex|claude|copilot or custom)",
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
        "--agent", default="claude", help="Runner to use (default: claude)"
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
    except Exception:
        # If config loading fails, fall back to defaults (quiet/normal/verbose from env)
        setup_logging(verbose=False, quiet=False)

    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
