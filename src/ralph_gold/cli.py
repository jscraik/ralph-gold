from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import load_config
from .doctor import check_tools, setup_checks
from .loop import (
    build_runner_invocation,
    next_iteration_number,
    run_iteration,
    run_loop,
)
from .scaffold import init_project
from .specs import check_specs, format_specs_check
from .trackers import make_tracker


def _project_root() -> Path:
    return Path(os.getcwd()).resolve()


# -------------------------
# init / doctor
# -------------------------


def cmd_init(args: argparse.Namespace) -> int:
    root = _project_root()
    format_type = getattr(args, "format", None)
    archived = init_project(root, force=bool(args.force), format_type=format_type)

    print(f"Initialized Ralph files in: {root / '.ralph'}")

    if archived:
        print(f"\n✓ Archived {len(archived)} existing file(s) to .ralph/archive/")
        for path in archived[:5]:  # Show first 5
            print(f"  - {path}")
        if len(archived) > 5:
            print(f"  ... and {len(archived) - 5} more")

    if format_type == "yaml":
        print("Created tasks.yaml template (YAML tracker)")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    root = _project_root()

    # Setup checks mode
    if args.setup_checks:
        result = setup_checks(root, dry_run=args.dry_run)

        print(f"Project type: {result['project_type']}")
        print(f"Check script: {result['script_name']}")
        print("\nSuggested gate commands:")
        for cmd in result["commands"]:
            print(f"  - {cmd}")

        if result["actions_taken"]:
            print("\n✓ Actions taken:")
            for action in result["actions_taken"]:
                print(f"  - {action}")

        if result["suggestions"]:
            print("\n→ Suggestions:")
            for suggestion in result["suggestions"]:
                print(f"  - {suggestion}")

        if args.dry_run:
            print("\n(Dry run - no changes made)")

        return 0

    # GitHub authentication check mode
    if args.check_github:
        from .github_auth import GhCliAuth, GitHubAuthError, TokenAuth

        print("Checking GitHub authentication...\n")

        # Try gh CLI first
        print("[1/2] Checking gh CLI authentication...")
        try:
            gh_auth = GhCliAuth()
            if gh_auth.validate():
                print("[OK]   gh CLI: authenticated")

                # Get user info to show who's authenticated
                try:
                    user_data = gh_auth.api_call("GET", "/user")
                    print(f"       User: {user_data.get('login', 'unknown')}")
                except Exception:
                    pass

                return 0
            else:
                print("[WARN] gh CLI: installed but not authenticated")
                print("       Run 'gh auth login' to authenticate")
        except GitHubAuthError as e:
            print(f"[MISS] gh CLI: {e}")

        # Try token auth
        print("\n[2/2] Checking token authentication...")
        try:
            token_auth = TokenAuth()
            if token_auth.validate():
                print("[OK]   Token: authenticated (GITHUB_TOKEN)")

                # Get user info to show who's authenticated
                try:
                    user_data = token_auth.api_call("GET", "/user")
                    print(f"       User: {user_data.get('login', 'unknown')}")
                except Exception:
                    pass

                return 0
            else:
                print("[WARN] Token: invalid or expired")
        except GitHubAuthError as e:
            print(f"[MISS] Token: {e}")

        print("\n✗ No valid GitHub authentication found")
        print("\nTo authenticate:")
        print("  Option 1 (recommended): gh auth login")
        print("  Option 2: Set GITHUB_TOKEN environment variable")
        print("            Get a token from https://github.com/settings/tokens")

        return 2

    # Standard doctor checks
    cfg = load_config(root)
    statuses = check_tools(cfg)
    ok = True
    for st in statuses:
        if st.found:
            print(f"[OK]   {st.name}: {st.version or st.path or 'found'}")
        else:
            ok = False
            print(f"[MISS] {st.name}: {st.hint or 'not found'}")
    return 0 if ok else 2


# -------------------------
# loop
# -------------------------


def cmd_step(args: argparse.Namespace) -> int:
    root = _project_root()
    cfg = load_config(root)

    # Ad-hoc overrides (useful for loop.sh mode switching)
    if args.prompt_file:
        cfg = replace(cfg, files=replace(cfg.files, prompt=str(args.prompt_file)))
    if args.prd_file:
        cfg = replace(cfg, files=replace(cfg.files, prd=str(args.prd_file)))

    agent = args.agent
    iter_n = next_iteration_number(root)
    res = run_iteration(root, agent=agent, cfg=cfg, iteration=iter_n)

    print(
        f"Iteration {res.iteration} agent={agent} story_id={res.story_id} rc={res.return_code} "
        f"exit={res.exit_signal} gates={res.gates_ok} judge={res.judge_ok} review={res.review_ok}"
    )
    print(f"Log: {res.log_path}")

    if res.no_progress_streak >= cfg.loop.no_progress_limit:
        print(
            f"Stopped: no progress streak reached ({res.no_progress_streak}/{cfg.loop.no_progress_limit})."
        )
        return 3
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    root = _project_root()
    agent = args.agent
    cfg = load_config(root)

    if args.prompt_file:
        cfg = replace(cfg, files=replace(cfg.files, prompt=str(args.prompt_file)))
    if args.prd_file:
        cfg = replace(cfg, files=replace(cfg.files, prd=str(args.prd_file)))

    # Get parallel and max_workers from args
    parallel = getattr(args, "parallel", False)
    max_workers = getattr(args, "max_workers", None)

    results = run_loop(
        root,
        agent=agent,
        max_iterations=args.max_iterations,
        cfg=cfg,
        parallel=parallel,
        max_workers=max_workers,
    )

    for r in results:
        print(
            f"iter={r.iteration} story_id={r.story_id} rc={r.return_code} exit={r.exit_signal} "
            f"gates={r.gates_ok} judge={r.judge_ok} log={r.log_path.name}"
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

    try:
        done, total = tracker.counts()
    except Exception:
        done, total = 0, 0

    try:
        next_task = tracker.select_next_task()
    except Exception:
        next_task = None

    print(f"PRD: {cfg.files.prd}")
    print(f"Progress: {done}/{total} tasks done")
    if next_task is not None:
        print(f"Next: id={next_task.id} title={next_task.title}")
    else:
        print("Next: (none)")

    # Show last iteration summary (from .ralph/state.json)
    state_path = root / ".ralph" / "state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            history = state.get("history", [])
            if isinstance(history, list) and history:
                last = history[-1]
                if isinstance(last, dict):
                    print("\nLast iteration:")
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
                        if k in last:
                            print(f"  {k}: {last[k]}")
        except Exception:
            pass
    return 0


# -------------------------
# specs
# -------------------------


def cmd_specs_check(args: argparse.Namespace) -> int:
    root = _project_root()
    cfg = load_config(root)
    res = check_specs(root, specs_dir=str(args.specs_dir or cfg.files.specs_dir))
    print(format_specs_check(res), end="")
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
        print(
            "No description provided. Use --desc, --desc-file, or pipe text into stdin."
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
        print(f"Unknown agent '{agent}'. Available: {available}")
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

    print(f"Plan run complete (rc={cp.returncode}). Log: {log_path}")
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
        print(f"Unknown agent '{agent}'. Available: {available}")
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

    print(f"Regenerate plan run complete (rc={cp.returncode}). Log: {log_path}")
    return int(cp.returncode)


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

        print(f"✓ Converted {input_path.name} to {output_path}")

        if args.infer_groups:
            print("  Groups inferred from task titles")

        # Show summary
        import yaml

        with open(output_path) as f:
            data = yaml.safe_load(f)

        tasks = data.get("tasks", [])
        total = len(tasks)
        completed = sum(1 for t in tasks if t.get("completed", False))

        print(f"  Tasks: {total} total, {completed} completed")

        if args.infer_groups:
            groups = {}
            for task in tasks:
                group = task.get("group", "default")
                groups[group] = groups.get(group, 0) + 1

            if len(groups) > 1:
                print(
                    f"  Groups: {', '.join(f'{g} ({c})' for g, c in sorted(groups.items()))}"
                )

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 2
    except ValueError as e:
        print(f"Error: {e}")
        return 2
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 2


# -------------------------
# argparse
# -------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ralph",
        description="ralph-gold: Golden Ralph Loop orchestrator (uv-first)",
    )
    p.add_argument("--version", action="version", version=f"ralph-gold {__version__}")

    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Initialize Ralph files in the current repo")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing files")
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

    p_step = sub.add_parser("step", help="Run exactly one iteration")
    p_step.add_argument(
        "--agent",
        default="codex",
        help="Runner to use (codex|claude|copilot or custom runner name)",
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
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser(
        "status", help="Show PRD progress + last iteration summary"
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

    p_bridge = sub.add_parser(
        "bridge", help="Start a JSON-RPC bridge over stdio (for VS Code)"
    )
    p_bridge.set_defaults(func=cmd_bridge)

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
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
