from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from ..config import load_config
from ..loop import build_runner_invocation
from ..output import get_output_config, print_json_output, print_output
from ..prd import validate_prd
from ..snapshots import create_snapshot, list_snapshots, rollback_snapshot
from ..specs import check_specs, format_specs_check
from ..trackers import make_tracker
from ..watch import run_watch_mode

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    return Path(os.getcwd()).resolve()


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

    if cp.returncode == 0:
        # Validate the newly regenerated PRD
        warnings = validate_prd(root / prd_filename)
        if warnings:
            print_output("", level="normal")
            print_output("PRD validation warnings:", level="normal")
            for w in warnings:
                print_output(f"  - {w}", level="normal")
            print_output("", level="normal")

            if getattr(args, "strict", False):
                print_output(
                    "Error: PRD validation failed in strict mode.", level="error"
                )
                return 1

    return int(cp.returncode)


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

        print_output(f"✗ Failed to rollback to snapshot '{name}'", level="error")
        return 2

    except ValueError as e:
        print_output(f"Error: {e}", level="error")
        return 2
    except RuntimeError as e:
        print_output(f"Error: {e}", level="error")
        return 2


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
        print_output("JSON output format is not supported for watch mode", level="error")
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
    from ..templates import TemplateError, create_task_from_template, list_templates

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

    from ..templates import list_templates

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
