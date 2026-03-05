from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable


def run_step_command(
    args: argparse.Namespace,
    *,
    project_root_fn: Callable[[], Path],
    load_config_fn: Callable[[Path], Any],
    normalize_mode_fn: Callable[[str | None], str | None],
    validate_project_path_fn: Callable[..., Path],
    dry_run_loop_fn: Callable[..., Any],
    make_tracker_fn: Callable[..., Any],
    next_iteration_number_fn: Callable[[Path], int],
    run_iteration_fn: Callable[..., Any],
    get_output_config_fn: Callable[[], Any],
    print_json_output_fn: Callable[[dict], None],
    print_output_fn: Callable[..., None],
    logger: Any,
) -> int:
    root = project_root_fn()
    try:
        cfg = load_config_fn(root)
    except ValueError as exc:
        print_output_fn(str(exc), level="error")
        return 2

    mode_override = None
    batch_override = None
    timeout_override = None

    if getattr(args, "quick", False):
        mode_override = "speed"
    elif getattr(args, "batch", False):
        mode_override = "speed"
        batch_override = True
    elif getattr(args, "explore", False):
        mode_override = "exploration"
        timeout_override = 3600
    elif getattr(args, "hotfix", False):
        mode_override = "speed"
    else:
        try:
            mode_override = normalize_mode_fn(getattr(args, "mode", None))
        except ValueError as exc:
            print_output_fn(str(exc), level="error")
            return 2

    if mode_override:
        cfg = replace(cfg, loop=replace(cfg.loop, mode=mode_override))
    if batch_override is not None:
        cfg = replace(cfg, loop=replace(cfg.loop, batch_enabled=batch_override))
    if timeout_override is not None:
        cfg = replace(
            cfg, loop=replace(cfg.loop, runner_timeout_seconds=timeout_override)
        )

    # Ad-hoc overrides (useful for loop.sh mode switching)
    # Validate file paths to prevent path traversal attacks
    if args.prompt_file:
        validated_prompt = validate_project_path_fn(
            root, Path(args.prompt_file), must_exist=True
        )
        cfg = replace(cfg, files=replace(cfg.files, prompt=str(validated_prompt)))
    if args.prd_file:
        validated_prd = validate_project_path_fn(
            root, Path(args.prd_file), must_exist=True
        )
        cfg = replace(cfg, files=replace(cfg.files, prd=str(validated_prd)))

    agent = args.agent

    # Handle dry-run mode
    dry_run = getattr(args, "dry_run", False)
    if dry_run:
        result = dry_run_loop_fn(root, agent, 1, cfg)

        print_output_fn("=" * 60, level="quiet")
        print_output_fn("DRY-RUN MODE - No agents will be executed", level="quiet")
        print_output_fn("=" * 60, level="quiet")
        print_output_fn("", level="quiet")
        print_output_fn(
            f"Configuration: {'VALID' if result.config_valid else 'INVALID'}",
            level="quiet",
        )
        print_output_fn(
            f"Resolved loop mode: {result.resolved_mode.get('name')}",
            level="quiet",
        )
        print_output_fn(f"Total tasks: {result.total_tasks}", level="quiet")
        print_output_fn(f"Completed tasks: {result.completed_tasks}", level="quiet")
        print_output_fn("", level="quiet")

        if result.issues:
            print_output_fn("Issues found:", level="quiet")
            for issue in result.issues:
                print_output_fn(f"  ❌ {issue}", level="error")
            print_output_fn("", level="quiet")

        if result.tasks_to_execute:
            print_output_fn("Next task that would be executed:", level="quiet")
            print_output_fn(f"  • {result.tasks_to_execute[0]}", level="quiet")
            print_output_fn("", level="quiet")
        else:
            print_output_fn("No tasks would be executed.", level="quiet")
            print_output_fn("", level="quiet")

        if result.gates_to_run:
            print_output_fn("Gates that would run:", level="quiet")
            for gate in result.gates_to_run:
                print_output_fn(f"  • {gate}", level="quiet")
            print_output_fn("", level="quiet")

        print_output_fn("=" * 60, level="quiet")
        print_output_fn("Dry-run complete. No changes were made.", level="quiet")
        print_output_fn("=" * 60, level="quiet")
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
        print_output_fn("--interactive cannot be combined with --task-id.", level="error")
        return 2

    if interactive:
        from ..interactive import convert_selected_task_to_choice, select_task_interactive
        from ..loop import load_state
        from ..prd import SelectedTask

        # Get available tasks from tracker
        tracker = make_tracker_fn(root, cfg)

        # Load state to get blocked tasks
        state_path = root / ".ralph" / "state.json"
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
            print_output_fn(
                f"Error loading tasks for interactive selection: {e}", level="error"
            )
            return 1

        if not available_tasks:
            print_output_fn("No tasks available for selection.", level="normal")
            return 0

        # Let user select a task
        selected_choice = select_task_interactive(available_tasks, show_blocked=False)

        if selected_choice is None:
            print_output_fn("No task selected. Exiting.", level="normal")
            return 0

        # Convert back to SelectedTask for run_iteration
        task_override = SelectedTask(
            id=selected_choice.task_id,
            title=selected_choice.title,
            kind="markdown",  # Default to markdown kind
            acceptance=selected_choice.acceptance_criteria,
        )
        target_task_id = str(selected_choice.task_id)

    iter_n = next_iteration_number_fn(root)
    try:
        res = run_iteration_fn(
            root,
            agent=agent,
            cfg=cfg,
            iteration=iter_n,
            task_override=task_override,
            target_task_id=target_task_id or None,
            allow_done_target=allow_done_target,
            allow_blocked_target=allow_blocked_target,
            reopen_if_needed=reopen_target,
            skip_gates=bool(getattr(args, "hotfix", False)),
        )
    except RuntimeError as e:
        # Handle rate-limit and other runtime errors
        print_output_fn(f"Error: {e}", level="error")
        return 2

    # JSON output for cmd_step
    if get_output_config_fn().format == "json":
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
        print_json_output_fn(payload)
        return exit_code

    print_output_fn(
        f"Iteration {res.iteration} agent={agent} story_id={res.story_id} rc={res.return_code} "
        f"exit={res.exit_signal} gates={res.gates_ok} judge={res.judge_ok} review={res.review_ok}",
        level="quiet",
    )
    print_output_fn(f"Log: {res.log_path}", level="quiet")

    if res.no_progress_streak >= cfg.loop.no_progress_limit:
        print_output_fn(
            f"Stopped: no progress streak reached ({res.no_progress_streak}/{cfg.loop.no_progress_limit}).",
            level="normal",
        )
        return 3
    return 0


def run_run_command(
    args: argparse.Namespace,
    *,
    project_root_fn: Callable[[], Path],
    load_config_fn: Callable[[Path], Any],
    normalize_mode_fn: Callable[[str | None], str | None],
    validate_project_path_fn: Callable[..., Path],
    run_loop_fn: Callable[..., Any],
    get_output_config_fn: Callable[[], Any],
    print_json_output_fn: Callable[[dict], None],
    print_output_fn: Callable[..., None],
) -> int:
    root = project_root_fn()
    agent = args.agent
    try:
        cfg = load_config_fn(root)
    except ValueError as exc:
        print_output_fn(str(exc), level="error")
        return 2

    mode_override = None
    batch_override = None
    timeout_override = None
    max_iterations = args.max_iterations

    if getattr(args, "quick", False):
        mode_override = "speed"
        max_iterations = 1
    elif getattr(args, "batch", False):
        mode_override = "speed"
        batch_override = True
    elif getattr(args, "explore", False):
        mode_override = "exploration"
        timeout_override = 3600
    elif getattr(args, "hotfix", False):
        mode_override = "speed"
    else:
        try:
            mode_override = normalize_mode_fn(getattr(args, "mode", None))
        except ValueError as exc:
            print_output_fn(str(exc), level="error")
            return 2

    if mode_override:
        cfg = replace(cfg, loop=replace(cfg.loop, mode=mode_override))
    if batch_override is not None:
        cfg = replace(cfg, loop=replace(cfg.loop, batch_enabled=batch_override))
    if timeout_override is not None:
        cfg = replace(
            cfg, loop=replace(cfg.loop, runner_timeout_seconds=timeout_override)
        )

    # Validate file paths to prevent path traversal attacks
    if args.prompt_file:
        validated_prompt = validate_project_path_fn(
            root, Path(args.prompt_file), must_exist=True
        )
        cfg = replace(cfg, files=replace(cfg.files, prompt=str(validated_prompt)))
    if args.prd_file:
        validated_prd = validate_project_path_fn(
            root, Path(args.prd_file), must_exist=True
        )
        cfg = replace(cfg, files=replace(cfg.files, prd=str(validated_prd)))

    # Get parallel and max_workers from args
    parallel = getattr(args, "parallel", False)
    max_workers = getattr(args, "max_workers", None)
    dry_run = getattr(args, "dry_run", False)
    stream = getattr(args, "stream", False)
    target_task_id = (
        str(getattr(args, "task_id", "")).strip()
        if getattr(args, "task_id", None) is not None
        else ""
    )

    if parallel and stream:
        print_output_fn(
            "INFO: --stream is only supported in sequential mode and will be ignored "
            "when --parallel is enabled.",
            level="normal",
        )
        stream = False

    try:
        results = run_loop_fn(
            root,
            agent=agent,
            max_iterations=max_iterations,
            cfg=cfg,
            parallel=parallel,
            max_workers=max_workers,
            dry_run=dry_run,
            stream=stream,
            skip_gates=bool(getattr(args, "hotfix", False)),
            target_task_id=target_task_id or None,
        )
    except RuntimeError as e:
        # Handle rate-limit and other runtime errors
        print_output_fn(f"Error: {e}", level="error")
        return 2

    # Dry-run mode prints its own output and returns early
    if dry_run:
        return 0

    # JSON output for cmd_run
    if get_output_config_fn().format == "json":
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
        print_json_output_fn(payload)
        return exit_code

    for r in results:
        log_name = r.log_path.name if r.log_path else "no-log"
        print_output_fn(
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


def run_supervise_command(
    args: argparse.Namespace,
    *,
    project_root_fn: Callable[[], Path],
    load_config_fn: Callable[[Path], Any],
    normalize_mode_fn: Callable[[str | None], str | None],
    get_output_config_fn: Callable[[], Any],
    print_output_fn: Callable[..., None],
) -> int:
    """Run a long-lived supervisor loop with heartbeat + notifications."""

    root = project_root_fn()
    agent = args.agent
    try:
        cfg = load_config_fn(root)
    except ValueError as exc:
        print_output_fn(str(exc), level="error")
        return 2

    try:
        mode_override = normalize_mode_fn(getattr(args, "mode", None))
    except ValueError as exc:
        print_output_fn(str(exc), level="error")
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
        args.heartbeat_seconds
        if args.heartbeat_seconds is not None
        else sup.heartbeat_seconds
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
        args.notify_command
        if args.notify_command is not None
        else list(sup.notify_command_argv)
    )

    from ..supervisor import run_supervisor, supervise_to_stdout_json

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

    if get_output_config_fn().format != "json":
        print_output_fn(
            f"Supervise finished: exit_code={res.exit_code} reason={res.reason} "
            f"iterations={res.iterations_run}",
            level="normal",
        )
        if res.last_log_path:
            print_output_fn(f"Last log: {res.last_log_path}", level="quiet")

    return int(res.exit_code)
