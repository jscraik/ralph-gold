from __future__ import annotations

import argparse
import os
from pathlib import Path

from ..clean import clean_all, format_bytes
from ..config import load_config
from ..loop import load_state, next_iteration_number, run_iteration, save_state
from ..output import get_output_config, print_json_output, print_output
from ..prd import _load_json_prd, _load_md_prd, is_markdown_prd
from ..state_validation import cleanup_stale_task_ids, validate_state_against_prd


def _project_root() -> Path:
    return Path(os.getcwd()).resolve()


def cmd_resume(args: argparse.Namespace) -> int:
    """Handle resume command - detect and optionally continue interrupted iteration."""
    root = _project_root()

    from ..resume import (
        clear_interrupted_state,
        detect_interrupted_iteration,
        format_resume_prompt,
        should_resume,
    )

    resume_info = detect_interrupted_iteration(root)

    if resume_info is None:
        if get_output_config().format == "json":
            print_json_output(
                {
                    "cmd": "resume",
                    "exit_code": 0,
                    "interrupted": False,
                    "message": "No interrupted iteration detected.",
                }
            )
            return 0
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
            if get_output_config().format == "json":
                print_json_output(
                    {
                        "cmd": "resume",
                        "exit_code": 0,
                        "interrupted": True,
                        "action": "clear",
                        "cleared": True,
                    }
                )
                return 0
            print_output("✓ Cleared interrupted iteration from state.", level="quiet")
            print_output(
                "  Run 'ralph step' to start fresh on the same task.", level="quiet"
            )
        else:
            if get_output_config().format == "json":
                print_json_output(
                    {
                        "cmd": "resume",
                        "exit_code": 1,
                        "interrupted": True,
                        "action": "clear",
                        "cleared": False,
                    }
                )
                return 1
            print_output("✗ Failed to clear interrupted state.", level="error")
            return 1
        return 0

    if args.auto or recommended:
        if not args.auto:
            # Interactive mode - ask user
            try:
                response = input("\nResume this iteration? [Y/n]: ").strip().lower()
                if response and response not in {"y", "yes"}:
                    if get_output_config().format == "json":
                        print_json_output(
                            {
                                "cmd": "resume",
                                "exit_code": 0,
                                "interrupted": True,
                                "action": "prompt",
                                "resumed": False,
                                "reason": "user_declined",
                            }
                        )
                        return 0
                    print_output(
                        "Skipped. Use 'ralph resume --clear' to remove this entry.",
                        level="normal",
                    )
                    return 0
            except (KeyboardInterrupt, EOFError):
                if get_output_config().format == "json":
                    print_json_output(
                        {
                            "cmd": "resume",
                            "exit_code": 0,
                            "interrupted": True,
                            "action": "prompt",
                            "resumed": False,
                            "reason": "cancelled",
                        }
                    )
                    return 0
                print_output("\nCancelled.", level="normal")
                return 0

        # Resume by running another iteration
        print_output(f"\nResuming with agent '{resume_info.agent}'...", level="normal")
        cfg = load_config(root)
        iter_n = next_iteration_number(root)

        try:
            res = run_iteration(root, agent=resume_info.agent, cfg=cfg, iteration=iter_n)
        except RuntimeError as e:
            # Handle rate-limit and other runtime errors
            if get_output_config().format == "json":
                print_json_output(
                    {
                        "cmd": "resume",
                        "exit_code": 2,
                        "interrupted": True,
                        "action": "resume",
                        "resumed": False,
                        "error": str(e),
                    }
                )
                return 2
            print_output(f"Error: {e}", level="error")
            return 2

        if get_output_config().format == "json":
            exit_code = 0 if res.return_code == 0 else 2
            print_json_output(
                {
                    "cmd": "resume",
                    "exit_code": exit_code,
                    "interrupted": True,
                    "action": "resume",
                    "resumed": True,
                    "iteration": res.iteration,
                    "agent": resume_info.agent,
                    "story_id": res.story_id,
                    "return_code": res.return_code,
                    "gates_ok": res.gates_ok,
                    "log_path": str(res.log_path),
                }
            )
            return exit_code

        print_output(
            f"Iteration {res.iteration} agent={resume_info.agent} story_id={res.story_id} "
            f"rc={res.return_code} exit={res.exit_signal} gates={res.gates_ok}",
            level="quiet",
        )
        print_output(f"Log: {res.log_path}", level="quiet")

        return 0 if res.return_code == 0 else 2

    # Not recommended to resume
    if get_output_config().format == "json":
        print_json_output(
            {
                "cmd": "resume",
                "exit_code": 0,
                "interrupted": True,
                "recommended": False,
                "resumed": False,
                "next_actions": ["ralph resume --clear", "ralph resume --auto"],
            }
        )
        return 0
    print_output("\n⚠ Resume not recommended (gates may have failed).", level="normal")
    print_output("Options:", level="normal")
    print_output("  - ralph resume --clear    # Clear and start fresh", level="normal")
    print_output("  - ralph resume --auto     # Force resume anyway", level="normal")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """Clean old Ralph workspace artifacts."""
    root = _project_root()

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

    all_errors = (
        logs_result.errors
        + archives_result.errors
        + receipts_result.errors
        + context_result.errors
    )
    exit_code = 1 if all_errors else 0

    if get_output_config().format == "json":
        print_json_output(
            {
                "cmd": "clean",
                "exit_code": exit_code,
                "dry_run": dry_run,
                "totals": {
                    "files_removed": total_files,
                    "directories_removed": total_dirs,
                    "bytes_freed": total_bytes,
                },
                "details": {
                    "logs": {
                        "files_removed": logs_result.files_removed,
                        "directories_removed": logs_result.directories_removed,
                        "bytes_freed": logs_result.bytes_freed,
                    },
                    "archives": {
                        "files_removed": archives_result.files_removed,
                        "directories_removed": archives_result.directories_removed,
                        "bytes_freed": archives_result.bytes_freed,
                    },
                    "receipts": {
                        "files_removed": receipts_result.files_removed,
                        "directories_removed": receipts_result.directories_removed,
                        "bytes_freed": receipts_result.bytes_freed,
                    },
                    "context": {
                        "files_removed": context_result.files_removed,
                        "directories_removed": context_result.directories_removed,
                        "bytes_freed": context_result.bytes_freed,
                    },
                },
                "errors": all_errors,
            }
        )
        return exit_code

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
        if get_output_config().format == "json":
            print_json_output(
                {
                    "cmd": "state_cleanup",
                    "exit_code": 0,
                    "stale_ids": [],
                    "removed_ids": [],
                    "protected_ids": list(validation.protected_ids),
                    "can_auto_cleanup": bool(validation.can_auto_cleanup),
                }
            )
            return 0
        print_output("No stale task IDs found.", level="normal")
        return 0

    # Show what was found
    print_output(
        f"Found {len(validation.stale_ids)} stale task IDs: {validation.stale_ids}",
        level="normal",
    )
    if validation.protected_ids:
        print_output(
            f"Protected (current/recent): {validation.protected_ids}", level="normal"
        )

    dry_run = args.dry_run
    if dry_run:
        print_output("\nDRY RUN - No changes will be made", level="normal")

    # Check if auto-cleanup is safe
    if not validation.can_auto_cleanup:
        if get_output_config().format == "json":
            print_json_output(
                {
                    "cmd": "state_cleanup",
                    "exit_code": 1,
                    "stale_ids": list(validation.stale_ids),
                    "removed_ids": [],
                    "protected_ids": list(validation.protected_ids),
                    "can_auto_cleanup": False,
                    "dry_run": bool(dry_run),
                }
            )
            return 1
        print_output(
            "\nCannot auto-cleanup: current task is stale or PRD was recently modified",
            level="warning",
        )
        print_output(
            "Run 'ralph state cleanup' after fixing the PRD or completing current task",
            level="normal",
        )
        return 1

    # Perform cleanup
    removed_ids = cleanup_stale_task_ids(
        root,
        prd_path,
        state_path,
        dry_run=dry_run,
    )

    if removed_ids:
        if get_output_config().format == "json":
            print_json_output(
                {
                    "cmd": "state_cleanup",
                    "exit_code": 0,
                    "stale_ids": list(validation.stale_ids),
                    "removed_ids": list(removed_ids),
                    "protected_ids": list(validation.protected_ids),
                    "can_auto_cleanup": True,
                    "dry_run": bool(dry_run),
                }
            )
            return 0
        print_output(
            f"Removed {len(removed_ids)} stale task IDs: {removed_ids}",
            level="normal",
        )
        if dry_run:
            print_output(
                "\nRun without --dry-run to actually remove these IDs", level="normal"
            )
    else:
        if get_output_config().format == "json":
            print_json_output(
                {
                    "cmd": "state_cleanup",
                    "exit_code": 0,
                    "stale_ids": list(validation.stale_ids),
                    "removed_ids": [],
                    "protected_ids": list(validation.protected_ids),
                    "can_auto_cleanup": True,
                    "dry_run": bool(dry_run),
                }
            )
            return 0
        print_output("No task IDs were removed (all were protected)", level="normal")

    return 0


def cmd_blocked(args: argparse.Namespace) -> int:
    """Show blocked tasks with optional suggestions."""
    root = _project_root()
    from ..unblock import BlockedTaskManager, format_blocked_table

    manager = BlockedTaskManager(root)
    blocked = manager.list_blocked_tasks()

    json_mode = get_output_config().format == "json" or getattr(args, "format", "table") == "json"

    if not blocked:
        if json_mode:
            print_json_output(
                {
                    "cmd": "blocked",
                    "exit_code": 0,
                    "blocked": [],
                    "statistics": {
                        "total_blocked": 0,
                        "total_wasted_iterations": 0,
                        "avg_attempts": 0.0,
                        "by_reason": {},
                        "by_complexity": {},
                    },
                }
            )
            return 0
        print_output("✅ No blocked tasks found.", level="normal")
        return 0

    if not json_mode:
        print_output(format_blocked_table(blocked), level="normal")

    # Show suggestions if requested
    suggestions: list[dict[str, str]] = []
    if getattr(args, "suggest", False):
        print_output("\n📋 Unblock Suggestions:\n", level="normal")
        for task_info in blocked[:10]:  # Limit to 10 for readability
            suggestion = manager.suggest_unblock_strategy(task_info)
            suggestions.append({"task_id": str(task_info.task_id), "suggestion": suggestion})
            if not json_mode:
                print_output(f"Task {task_info.task_id}:\n{suggestion}\n", level="normal")

    # Show statistics
    stats = manager.get_statistics()
    if json_mode:
        print_json_output(
            {
                "cmd": "blocked",
                "exit_code": 0,
                "blocked": [b.to_dict() for b in blocked],
                "suggestions": suggestions if suggestions else None,
                "statistics": stats,
            }
        )
    else:
        print_output(
            f"\n📊 Statistics:\n"
            f"  Total blocked: {stats['total_blocked']}\n"
            f"  Wasted iterations: {stats['total_wasted_iterations']}\n"
            f"  Avg attempts: {stats['avg_attempts']:.1f}\n"
            f"  By reason: {stats['by_reason']}\n"
            f"  By complexity: {stats['by_complexity']}\n",
            level="normal",
        )

    return 0


def cmd_unblock(args: argparse.Namespace) -> int:
    """Unblock a specific task for retry."""
    root = _project_root()
    from ..unblock import BlockedTaskManager

    manager = BlockedTaskManager(root)

    # Keep user-provided task ID; unblock manager resolves alternate forms
    task_id = args.task_id

    # Get suggested timeout if not provided
    if args.timeout is None:
        blocked = manager.list_blocked_tasks()
        task_info = next(
            (
                b
                for b in blocked
                if b.task_id == task_id
                or (task_id.startswith("task-") and b.task_id == task_id[5:])
                or (task_id.isdigit() and b.task_id == f"task-{task_id}")
            ),
            None,
        )
        if task_info:
            args.timeout = task_info.suggested_timeout
        else:
            print_output(
                f"⚠️  Task {task_id} not found in blocked list. Using default timeout.",
                level="warning",
            )
            args.timeout = 120

    result = manager.unblock_task(
        task_id=task_id,
        reason=args.reason,
        new_timeout=args.timeout,
    )

    if result.success:
        if get_output_config().format == "json":
            print_json_output(
                {
                    "cmd": "unblock",
                    "exit_code": 0,
                    "success": True,
                    "task_id": str(task_id),
                    "message": result.message,
                    "new_timeout": result.new_timeout,
                    "previous_attempts": result.previous_attempts,
                }
            )
            return 0
        print_output(f"✅ {result.message}", level="normal")
        if result.new_timeout > 0:
            print_output(
                f"   New timeout for retry: {result.new_timeout}s ({result.new_timeout // 60} minutes)",
                level="normal",
            )
        print_output(
            f"   Previous attempts: {result.previous_attempts}",
            level="normal",
        )
        return 0

    if get_output_config().format == "json":
        print_json_output(
            {
                "cmd": "unblock",
                "exit_code": 1,
                "success": False,
                "task_id": str(task_id),
                "message": result.message,
                "new_timeout": result.new_timeout,
                "previous_attempts": result.previous_attempts,
            }
        )
        return 1
    print_output(f"❌ {result.message}", level="error")
    return 1


def cmd_retry_blocked(args: argparse.Namespace) -> int:
    """Retry all blocked tasks with increased timeouts."""
    root = _project_root()
    from ..unblock import BlockedTaskManager

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

        preview = []
        for task in to_unblock:
            new_timeout = int(task.suggested_timeout * args.timeout_multiplier)
            preview.append(
                {
                    "task_id": str(task.task_id),
                    "title": str(task.title),
                    "new_timeout": new_timeout,
                }
            )
        if get_output_config().format == "json":
            print_json_output(
                {
                    "cmd": "retry_blocked",
                    "exit_code": 0,
                    "dry_run": True,
                    "filter": filter_type,
                    "count": len(to_unblock),
                    "preview": preview,
                }
            )
            return 0
        print_output(f"🔍 Dry run: would unblock {len(to_unblock)} tasks", level="normal")
        print_output("Tasks to unblock:\n", level="normal")
        for item in preview[:10]:
            print_output(f"  {item['task_id']}: {item['title'][:50]}...", level="normal")
            print_output(
                f"    New timeout: {item['new_timeout']}s ({item['new_timeout'] // 60} min)\n",
                level="normal",
            )
        if len(preview) > 10:
            print_output(
                f"  ... and {len(preview) - 10} more tasks\n", level="normal"
            )
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

    if get_output_config().format == "json":
        print_json_output(
            {
                "cmd": "retry_blocked",
                "exit_code": 0 if fail_count == 0 else 1,
                "dry_run": False,
                "filter": filter_type,
                "success_count": success_count,
                "fail_count": fail_count,
                "results": [r.to_dict() for r in results],
            }
        )
        return 0 if fail_count == 0 else 1

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


def cmd_sync(args: argparse.Namespace) -> int:
    """Sync state.json with PRD to remove stale blocked entries.

    This command reconciles state.json blocked_tasks with PRD status.
    Tasks marked done in PRD but still in blocked_tasks are removed.
    """
    root = _project_root()
    cfg = load_config(root)
    prd_path = root / cfg.files.prd
    state_path = root / ".ralph" / "state.json"

    if not prd_path.exists():
        if get_output_config().format == "json":
            print_json_output(
                {
                    "cmd": "sync",
                    "exit_code": 1,
                    "synced": False,
                    "error": f"PRD file not found: {prd_path}",
                }
            )
            return 1
        print_output(f"❌ PRD file not found: {prd_path}", level="error")
        return 1

    if not state_path.exists():
        if get_output_config().format == "json":
            print_json_output(
                {
                    "cmd": "sync",
                    "exit_code": 0,
                    "synced": False,
                    "removed_ids": [],
                    "message": "No state.json found. Nothing to sync.",
                }
            )
            return 0
        print_output("⚠️  No state.json found. Nothing to sync.", level="warning")
        return 0

    # Load PRD tasks and find done task IDs
    done_task_ids: set[str] = set()
    if is_markdown_prd(prd_path):
        prd = _load_md_prd(prd_path)
        done_task_ids = {t.id for t in prd.tasks if t.status == "done"}
    else:
        prd = _load_json_prd(prd_path)
        if prd:
            stories = prd.get("stories", [])
            for s in stories:
                if isinstance(s, dict) and s.get("done"):
                    # Use story id if available
                    if "id" in s:
                        done_task_ids.add(str(s["id"]))
                    elif "title" in s:
                        # Fallback: use title-based id
                        done_task_ids.add(s["title"])

    # Load state
    state = load_state(state_path)
    blocked_tasks = state.get("blocked_tasks", {})
    if not isinstance(blocked_tasks, dict):
        blocked_tasks = {}

    # Find stale entries (blocked but done in PRD)
    stale_ids = []
    for task_id in list(blocked_tasks.keys()):
        if task_id in done_task_ids or str(task_id) in done_task_ids:
            stale_ids.append(task_id)

    if not stale_ids:
        if get_output_config().format == "json":
            print_json_output(
                {
                    "cmd": "sync",
                    "exit_code": 0,
                    "synced": True,
                    "removed_ids": [],
                    "message": "State is already in sync with PRD.",
                }
            )
            return 0
        print_output("✅ State is already in sync with PRD.", level="normal")
        return 0

    # Remove stale entries
    for task_id in stale_ids:
        del state["blocked_tasks"][task_id]
        if args.verbose:
            print_output(f"  Removed blocked entry for task {task_id}", level="normal")

    # Also clean up task_attempts for done tasks if requested
    if args.clean_attempts:
        task_attempts = state.get("task_attempts", {})
        for task_id in stale_ids:
            if task_id in task_attempts:
                del state["task_attempts"][task_id]
                if args.verbose:
                    print_output(
                        f"  Removed attempt history for task {task_id}", level="normal"
                    )

    # Save updated state
    save_state(state_path, state)

    if get_output_config().format == "json":
        print_json_output(
            {
                "cmd": "sync",
                "exit_code": 0,
                "synced": True,
                "removed_ids": list(stale_ids),
                "clean_attempts": bool(args.clean_attempts),
                "removed_count": len(stale_ids),
            }
        )
        return 0

    print_output(
        f"✅ Synced state with PRD: removed {len(stale_ids)} stale blocked entries",
        level="normal",
    )

    if not args.verbose and stale_ids:
        print_output("   Run with --verbose to see removed task IDs", level="normal")

    return 0


def cmd_interventions(args: argparse.Namespace) -> int:
    """Show intervention recommendations and analysis.

    This command surfaces recommendations generated by the intervention engine
    based on failure patterns in recent iterations.
    """
    root = _project_root()
    from ..interventions import (
        ensure_interventions_dir,
        format_recommendation_summary,
        list_recommendations,
        read_events,
        read_latest_recommendation,
    )

    cfg = load_config(root)
    interventions_dir = ensure_interventions_dir(root)

    json_mode = bool(args.json) or get_output_config().format == "json"

    # Check if interventions are enabled
    if not cfg.interventions.enabled:
        if json_mode:
            print_json_output(
                {
                    "cmd": "interventions",
                    "exit_code": 0,
                    "enabled": False,
                    "recommendations": [],
                    "recent_events": [],
                }
            )
            return 0
        print_output(
            "Intervention engine is disabled. Enable in .ralph/ralph.toml with:",
            level="normal",
        )
        print_output("  [interventions]", level="normal")
        print_output("  enabled = true", level="normal")
        return 0

    # JSON output mode
    if json_mode:
        if args.latest:
            rec = read_latest_recommendation(interventions_dir)
            print_json_output(
                {
                    "cmd": "interventions",
                    "exit_code": 0,
                    "latest": rec.to_dict() if rec else None,
                }
            )
        else:
            recs = list_recommendations(interventions_dir, limit=args.limit)
            events = read_events(interventions_dir, limit=args.limit)
            print_json_output(
                {
                    "cmd": "interventions",
                    "exit_code": 0,
                    "enabled": True,
                    "recommendations": [r.to_dict() for r in recs],
                    "recent_events": [e.to_dict() for e in events],
                    "config": {
                        "enabled": cfg.interventions.enabled,
                        "policy_mode": cfg.interventions.policy_mode,
                        "lookback_iterations": cfg.interventions.lookback_iterations,
                        "confidence_threshold": cfg.interventions.confidence_threshold,
                    },
                }
            )
        return 0

    # Show latest recommendation only
    if args.latest:
        rec = read_latest_recommendation(interventions_dir)
        if rec:
            print_output(format_recommendation_summary(rec), level="normal")
        else:
            print_output("No recommendations available yet.", level="normal")
            print_output(
                "Recommendations are generated after iterations with failure patterns.",
                level="normal",
            )
        return 0

    # Show summary
    recs = list_recommendations(interventions_dir, limit=args.limit)
    events = read_events(interventions_dir, limit=args.limit)

    print_output("Intervention Engine Status", level="normal")
    print_output("=" * 40, level="normal")
    print_output(f"  Policy mode: {cfg.interventions.policy_mode}", level="normal")
    print_output(
        f"  Lookback: {cfg.interventions.lookback_iterations} iterations", level="normal"
    )
    print_output(
        f"  Confidence threshold: {cfg.interventions.confidence_threshold}",
        level="normal",
    )
    print_output("", level="normal")

    print_output(f"Recent Recommendations: {len(recs)}", level="normal")
    print_output(f"Recent Events: {len(events)}", level="normal")
    print_output("", level="normal")

    if recs:
        print_output("Latest Recommendations:", level="normal")
        print_output("-" * 40, level="normal")
        for rec in recs[:5]:
            print_output(
                f"  [{rec.confidence_level}] {rec.category}: {rec.rationale[:60]}...",
                level="normal",
            )
        print_output("", level="normal")
        print_output(
            "Use --latest to see full details, or --json for machine-readable output.",
            level="normal",
        )
    else:
        print_output(
            "No recommendations yet. Run some iterations to generate recommendations.",
            level="normal",
        )

    return 0
