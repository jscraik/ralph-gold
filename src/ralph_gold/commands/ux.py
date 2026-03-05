from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from ..config import load_config
from ..output import get_output_config, print_json_output, print_output
from ..prd import get_all_tasks
from ..scaffold import init_project
from ..trackers import make_tracker

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    return Path(os.getcwd()).resolve()


def _apply_ux_mode(config_path: Path, mode: str) -> None:
    """Apply [ux].mode policy metadata to ralph.toml in a non-destructive way."""

    if mode not in {"simple", "expert"}:
        mode = "simple"

    if not config_path.exists():
        return

    text = config_path.read_text(encoding="utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()

    section_start = None
    for idx, line in enumerate(lines):
        if line.strip() == "[ux]":
            section_start = idx
            break

    mode_line = f'mode = "{mode}" # simple|expert'

    if section_start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(
            [
                "[ux]",
                "# UX posture policy metadata (simple|expert).",
                mode_line,
            ]
        )
    else:
        section_end = len(lines)
        for idx in range(section_start + 1, len(lines)):
            stripped = lines[idx].strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                section_end = idx
                break

        replaced = False
        for idx in range(section_start + 1, section_end):
            if lines[idx].strip().startswith("mode"):
                lines[idx] = mode_line
                replaced = True
                break

        if not replaced:
            lines.insert(section_end, mode_line)

    config_path.write_text(newline.join(lines) + newline, encoding="utf-8")


def _prompt_quickstart_profile(
    default_profile: str, default_agent: str
) -> tuple[str, str]:
    """Prompt for quickstart selections (best-effort, stdin-safe fallback)."""

    profile = default_profile
    agent = default_agent
    try:
        if sys.stdin is None or not sys.stdin.isatty():
            return profile, agent

        print_output(
            "Quickstart interactive setup (press Enter to accept defaults).",
            level="quiet",
        )
        raw_profile = input(
            f"Profile [simple/expert] ({default_profile}): "
        ).strip().lower()
        raw_agent = input(f"Preferred agent ({default_agent}): ").strip()

        if raw_profile in {"simple", "expert"}:
            profile = raw_profile
        if raw_agent:
            agent = raw_agent
    except EOFError:
        logger.debug("Quickstart prompt interrupted by EOF; using defaults.")
    return profile, agent


def cmd_quickstart(args: argparse.Namespace) -> int:
    """Initialize Ralph with recommended defaults and guidance."""

    root = _project_root()
    format_type = getattr(args, "format", None)
    profile = str(getattr(args, "profile", "simple") or "simple").strip().lower()
    if profile not in {"simple", "expert"}:
        print_output(
            f"Invalid --profile: {profile!r}. Falling back to 'simple'.",
            level="error",
        )
        profile = "simple"

    agent = str(getattr(args, "agent", "codex") or "codex").strip() or "codex"

    if bool(getattr(args, "interactive", False)):
        profile, agent = _prompt_quickstart_profile(profile, agent)

    archived = init_project(
        root,
        force=bool(args.force),
        format_type=format_type,
        solo=bool(getattr(args, "solo", False)),
        merge_config=True,
        merge_strategy="user_wins",
        no_merge_config=False,
    )

    config_path = root / ".ralph" / "ralph.toml"
    _apply_ux_mode(config_path, profile)

    print_output(f"Quickstart complete in: {root / '.ralph'}", level="quiet")
    print_output(f"Profile: {profile}", level="quiet")
    print_output(f"Recommended next step: ralph step --agent {agent}", level="quiet")
    print_output("Then run: ralph status", level="quiet")

    if archived:
        print_output(
            f"\n✓ Archived {len(archived)} existing file(s) to .ralph/archive/",
            level="quiet",
        )

    if format_type == "yaml":
        print_output("Created tasks.yaml template (YAML tracker)", level="quiet")

    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    """Explain task selection, blocked state, and recommended next actions."""

    root = _project_root()
    cfg = load_config(root)
    tracker = make_tracker(root, cfg)
    prd_path = root / cfg.files.prd

    try:
        done, total = tracker.counts()
    except (OSError, ValueError) as e:
        logger.debug("Tracker operation failed: %s", e)
        done, total = 0, 0

    next_task = None
    try:
        if hasattr(tracker, "peek_next_task"):
            next_task = tracker.peek_next_task()
        elif hasattr(tracker, "select_next_task"):
            next_task = tracker.select_next_task()
    except (OSError, ValueError) as e:
        logger.debug("Failed to resolve next task: %s", e)

    last_iteration = None
    state_path = root / ".ralph" / "state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            history = state.get("history", [])
            if isinstance(history, list) and history and isinstance(history[-1], dict):
                last_iteration = history[-1]
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("Failed to load state history: %s", e)

    explicit_blocked: list[dict] = []
    dependency_wait: list[dict] = []
    done_ids: set[str] = set()
    try:
        all_tasks = get_all_tasks(prd_path)
        if all_tasks:
            done_ids = {
                str(t.get("id", "")).strip()
                for t in all_tasks
                if str(t.get("status", "open")).strip().lower() == "done"
            }
            for t in all_tasks:
                task_id = str(t.get("id", "")).strip()
                title = str(t.get("title", task_id)).strip() or task_id
                status = str(t.get("status", "open")).strip().lower()
                deps = [
                    str(dep).strip()
                    for dep in (t.get("depends_on") or [])
                    if str(dep).strip()
                ]
                if status == "blocked":
                    explicit_blocked.append(
                        {"id": task_id, "title": title, "depends_on": deps}
                    )
                if status == "open" and deps:
                    unmet = [dep for dep in deps if dep not in done_ids]
                    if unmet:
                        dependency_wait.append(
                            {
                                "id": task_id,
                                "title": title,
                                "depends_on": deps,
                                "unmet_dependencies": unmet,
                            }
                        )
    except (OSError, ValueError) as e:
        logger.debug("Failed to compute dependency explainability: %s", e)

    if next_task is not None:
        if next_task.depends_on:
            why_selected = (
                f"Task {next_task.id} was selected because it is open and its dependencies "
                f"are satisfied ({', '.join(next_task.depends_on)})."
            )
        else:
            why_selected = (
                f"Task {next_task.id} was selected because it is the first open task "
                f"in tracker order."
            )
    elif total > 0 and done >= total:
        why_selected = "No task selected because all tracked tasks are complete."
    else:
        why_selected = "No task selected; all remaining tasks may be blocked or unavailable."

    if explicit_blocked or dependency_wait:
        blocked_parts = []
        if explicit_blocked:
            blocked_parts.append(f"{len(explicit_blocked)} explicitly blocked task(s)")
        if dependency_wait:
            blocked_parts.append(f"{len(dependency_wait)} dependency-waiting task(s)")
        why_blocked = "Blocked context: " + ", ".join(blocked_parts) + "."
    else:
        why_blocked = "No blocked tasks or dependency stalls detected."

    suggested_agent = str(getattr(args, "agent", "codex") or "codex").strip() or "codex"
    next_actions: list[str] = []
    if next_task is not None:
        next_actions.append(
            f"Run: ralph step --agent {suggested_agent} --task-id {next_task.id}"
        )
        next_actions.append("Review progress: ralph status")
    elif explicit_blocked:
        next_actions.append("Inspect blockers: ralph blocked --suggest")
        next_actions.append("Retry blocked tasks: ralph retry-blocked --filter all --dry-run")
    else:
        next_actions.append(f"Run: ralph run --agent {suggested_agent} --max-iterations 1")

    if last_iteration and int(last_iteration.get("return_code", 0)) != 0:
        next_actions.append("Investigate failures: ralph diagnose --test-gates")

    payload = {
        "cmd": "explain",
        "prd": cfg.files.prd,
        "progress": {"done": done, "total": total},
        "next": (
            {
                "id": next_task.id,
                "title": next_task.title,
                "depends_on": list(next_task.depends_on),
            }
            if next_task
            else None
        ),
        "explain": {
            "why_selected": why_selected,
            "why_blocked": why_blocked,
            "explicit_blocked_count": len(explicit_blocked),
            "dependency_wait_count": len(dependency_wait),
            "sample_blocked_tasks": explicit_blocked[:3],
            "sample_dependency_wait_tasks": dependency_wait[:3],
            "next_actions": next_actions,
        },
        "last_iteration": last_iteration,
    }

    if get_output_config().format == "json":
        print_json_output(payload)
        return 0

    print_output("Explainability Summary", level="normal")
    print_output("======================", level="normal")
    print_output(f"PRD: {cfg.files.prd}", level="normal")
    print_output(f"Progress: {done}/{total} done", level="normal")
    if next_task:
        print_output(f"Next task: {next_task.id} - {next_task.title}", level="normal")
    else:
        print_output("Next task: (none)", level="normal")
    print_output("", level="normal")
    print_output("Why this task was chosen:", level="normal")
    print_output(f"- {why_selected}", level="normal")
    print_output("", level="normal")
    print_output("Why blocked:", level="normal")
    print_output(f"- {why_blocked}", level="normal")
    print_output("", level="normal")
    print_output("What to do next:", level="normal")
    for action in next_actions:
        print_output(f"- {action}", level="normal")
    return 0
