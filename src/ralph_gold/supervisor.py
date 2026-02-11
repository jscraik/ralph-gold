"""Long-running supervisor/heartbeat loop for Ralph Gold.

`ralph supervise` is an outer loop that repeatedly calls `run_iteration` while:
- printing a periodic heartbeat (progress + last iteration summary)
- optionally waiting for rate-limit windows
- stopping with clear reasons
- emitting best-effort OS notifications on completion/stop/error
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from .config import Config
from .notify import default_title, send_notification
from .output import get_output_config, print_json_output, print_output
from .trackers import make_tracker

# Reuse internal helpers from loop to keep behavior consistent.
from .loop import (  # noqa: PLC0415 (intentional local import style)
    _rate_limit_ok,
    load_state,
    next_iteration_number,
    run_iteration,
    save_state,
)


@dataclass(frozen=True)
class SuperviseResult:
    exit_code: int  # 0|1|2
    reason: str
    iterations_run: int
    started_at: float
    ended_at: float
    last_iteration: Optional[int] = None
    last_story_id: Optional[str] = None
    last_task_title: Optional[str] = None
    last_log_path: Optional[str] = None


def _maybe_notify(
    *,
    enabled: bool,
    event: str,
    allowed_events: Sequence[str],
    title: str,
    message: str,
    backend: str,
    command_argv: Sequence[str],
) -> None:
    if not enabled:
        return
    if allowed_events and event not in {str(x).strip().lower() for x in allowed_events}:
        return
    send_notification(
        title=title,
        message=message,
        backend=backend,
        command_argv=command_argv,
    )


def _format_last(res) -> str:
    if res is None:
        return "(no iterations yet)"
    return (
        f"last: iter={res.iteration} task={res.story_id or '-'} "
        f"rc={res.return_code} exit={res.exit_signal} "
        f"gates={res.gates_ok} judge={res.judge_ok} review={res.review_ok} "
        f"no_prog={res.no_progress_streak}"
    )


def run_supervisor(
    project_root: Path,
    *,
    agent: str,
    cfg: Config,
    max_runtime_seconds: int,
    heartbeat_seconds: int,
    sleep_seconds_between_runs: int,
    on_no_progress_limit: str,
    on_rate_limit: str,
    notify_enabled: bool,
    notify_events: Sequence[str],
    notify_backend: str,
    notify_command_argv: Sequence[str],
) -> SuperviseResult:
    started = time.time()
    state_path = project_root / ".ralph" / "state.json"

    # Reset streak at supervisor start for predictability (matches run_loop()).
    try:
        st = load_state(state_path)
        st["noProgressStreak"] = 0
        save_state(state_path, st)
    except Exception:
        pass

    tracker = make_tracker(project_root, cfg)

    next_heartbeat = started
    iterations_run = 0
    last_res = None

    repo_name = project_root.name
    title = default_title(repo_name)

    def _heartbeat() -> None:
        try:
            done, total = tracker.counts()
        except Exception:
            done, total = 0, 0
        msg = f"supervise: {done}/{total} done • {_format_last(last_res)}"
        print_output(msg, level="normal")

    while True:
        now = time.time()

        if heartbeat_seconds > 0 and now >= next_heartbeat:
            _heartbeat()
            next_heartbeat = now + heartbeat_seconds

        if max_runtime_seconds and max_runtime_seconds > 0:
            if (now - started) >= max_runtime_seconds:
                reason = "max_runtime"
                _maybe_notify(
                    enabled=notify_enabled,
                    event="stopped",
                    allowed_events=notify_events,
                    title=title,
                    message=f"Stopped (max runtime reached). {_format_last(last_res)}",
                    backend=notify_backend,
                    command_argv=notify_command_argv,
                )
                return SuperviseResult(
                    exit_code=1,
                    reason=reason,
                    iterations_run=iterations_run,
                    started_at=started,
                    ended_at=time.time(),
                    last_iteration=getattr(last_res, "iteration", None),
                    last_story_id=getattr(last_res, "story_id", None),
                    last_task_title=getattr(last_res, "task_title", None),
                    last_log_path=str(getattr(last_res, "log_path", "") or "") or None,
                )

        # Rate limit: prefer pre-check to avoid raising in run_iteration.
        try:
            st = load_state(state_path)
            ok, wait_s = _rate_limit_ok(st, cfg.loop.rate_limit_per_hour)
        except Exception:
            ok, wait_s = True, 0

        if not ok:
            if (on_rate_limit or "").strip().lower() == "wait":
                wait_s = max(1, int(wait_s))
                print_output(
                    f"Rate limit reached ({cfg.loop.rate_limit_per_hour}/hour). Waiting ~{wait_s}s…",
                    level="normal",
                )
                time.sleep(wait_s)
                continue

            # stop
            _maybe_notify(
                enabled=notify_enabled,
                event="stopped",
                allowed_events=notify_events,
                title=title,
                message=f"Stopped (rate limit). {_format_last(last_res)}",
                backend=notify_backend,
                command_argv=notify_command_argv,
            )
            return SuperviseResult(
                exit_code=1,
                reason="rate_limit",
                iterations_run=iterations_run,
                started_at=started,
                ended_at=time.time(),
                last_iteration=getattr(last_res, "iteration", None),
                last_story_id=getattr(last_res, "story_id", None),
                last_task_title=getattr(last_res, "task_title", None),
                last_log_path=str(getattr(last_res, "log_path", "") or "") or None,
            )

        # Run one iteration
        try:
            iter_n = next_iteration_number(project_root)
            last_res = run_iteration(project_root, agent=agent, cfg=cfg, iteration=iter_n)
            iterations_run += 1
        except Exception as e:
            _maybe_notify(
                enabled=notify_enabled,
                event="error",
                allowed_events=notify_events,
                title=title,
                message=f"Error: {e}",
                backend=notify_backend,
                command_argv=notify_command_argv,
            )
            return SuperviseResult(
                exit_code=2,
                reason="error",
                iterations_run=iterations_run,
                started_at=started,
                ended_at=time.time(),
                last_iteration=getattr(last_res, "iteration", None),
                last_story_id=getattr(last_res, "story_id", None),
                last_task_title=getattr(last_res, "task_title", None),
                last_log_path=str(getattr(last_res, "log_path", "") or "") or None,
            )

        # Stop conditions
        try:
            done = tracker.all_done()
        except Exception:
            done = False

        all_blocked = False
        try:
            if hasattr(tracker, "all_blocked"):
                all_blocked = bool(tracker.all_blocked())
        except Exception:
            all_blocked = False

        # Completion
        if (done or (last_res.story_id is None and last_res.return_code == 0)) and (
            last_res.exit_signal is True
        ):
            _maybe_notify(
                enabled=notify_enabled,
                event="complete",
                allowed_events=notify_events,
                title=title,
                message=f"Complete. {_format_last(last_res)}",
                backend=notify_backend,
                command_argv=notify_command_argv,
            )
            return SuperviseResult(
                exit_code=0,
                reason="complete",
                iterations_run=iterations_run,
                started_at=started,
                ended_at=time.time(),
                last_iteration=last_res.iteration,
                last_story_id=last_res.story_id,
                last_task_title=getattr(last_res, "task_title", None),
                last_log_path=str(last_res.log_path) if last_res.log_path else None,
            )

        # All blocked
        if all_blocked or (last_res.story_id is None and last_res.return_code == 1):
            _maybe_notify(
                enabled=notify_enabled,
                event="stopped",
                allowed_events=notify_events,
                title=title,
                message=f"Stopped (all blocked). {_format_last(last_res)}",
                backend=notify_backend,
                command_argv=notify_command_argv,
            )
            return SuperviseResult(
                exit_code=1,
                reason="all_blocked",
                iterations_run=iterations_run,
                started_at=started,
                ended_at=time.time(),
                last_iteration=last_res.iteration,
                last_story_id=last_res.story_id,
                last_task_title=getattr(last_res, "task_title", None),
                last_log_path=str(last_res.log_path) if last_res.log_path else None,
            )

        # No-progress circuit breaker policy
        if last_res.no_progress_streak >= cfg.loop.no_progress_limit:
            if (on_no_progress_limit or "").strip().lower() == "continue":
                try:
                    st = load_state(state_path)
                    st["noProgressStreak"] = 0
                    save_state(state_path, st)
                except Exception:
                    pass
            else:
                _maybe_notify(
                    enabled=notify_enabled,
                    event="stopped",
                    allowed_events=notify_events,
                    title=title,
                    message=(
                        f"Stopped (no progress: {last_res.no_progress_streak}/{cfg.loop.no_progress_limit}). "
                        f"{_format_last(last_res)}"
                    ),
                    backend=notify_backend,
                    command_argv=notify_command_argv,
                )
                return SuperviseResult(
                    exit_code=1,
                    reason="no_progress",
                    iterations_run=iterations_run,
                    started_at=started,
                    ended_at=time.time(),
                    last_iteration=last_res.iteration,
                    last_story_id=last_res.story_id,
                    last_task_title=getattr(last_res, "task_title", None),
                    last_log_path=str(last_res.log_path) if last_res.log_path else None,
                )

        if sleep_seconds_between_runs > 0:
            time.sleep(sleep_seconds_between_runs)


def supervise_to_stdout_json(result: SuperviseResult) -> None:
    """Convenience for printing JSON output summaries for `ralph supervise`."""

    if get_output_config().format != "json":
        return
    payload = {
        "cmd": "supervise",
        "exit_code": result.exit_code,
        "reason": result.reason,
        "iterations_run": result.iterations_run,
        "started_at": result.started_at,
        "ended_at": result.ended_at,
        "duration_seconds": round(result.ended_at - result.started_at, 2),
        "last_iteration": result.last_iteration,
        "last_story_id": result.last_story_id,
        "last_task_title": result.last_task_title,
        "last_log_path": result.last_log_path,
    }
    print_json_output(payload)

