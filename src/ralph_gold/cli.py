from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import load_config
from .doctor import check_tools
from .loop import build_runner_argv, next_iteration_number, run_iteration, run_loop
from .prd import select_next_task, task_counts
from .scaffold import init_project


def _project_root() -> Path:
    return Path(os.getcwd()).resolve()


# Simple color support (works on most terminals)
def _color(text: str, code: int) -> str:
    """Add ANSI color codes if stdout is a TTY."""
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text


def _green(text: str) -> str:
    return _color(text, 32)


def _red(text: str) -> str:
    return _color(text, 31)


def _yellow(text: str) -> str:
    return _color(text, 33)


def _blue(text: str) -> str:
    return _color(text, 34)


def cmd_init(args: argparse.Namespace) -> int:
    root = _project_root()
    init_project(root, force=bool(args.force))
    ralph_dir = root / ".ralph"
    print(_green(f"✓ Initialized Ralph v{__version__} in: {ralph_dir}"))
    print()
    print("Next steps:")
    print("  1. Edit .ralph/AGENTS.md with your build/test commands")
    print("  2. Edit .ralph/prd.json or .ralph/PRD.md with your tasks")
    print("  3. Run: " + _blue("ralph run --agent codex"))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    statuses = check_tools()
    ok = True
    print("Ralph Doctor - Checking prerequisites:\n")
    for st in statuses:
        if st.found:
            print(f"  {_green('✓')} {st.name}: {st.version or st.path or 'found'}")
        else:
            ok = False
            print(f"  {_red('✗')} {st.name}: {st.hint or 'not found'}")
    print()
    if ok:
        print(_green("All checks passed!"))
    else:
        print(_yellow("Some tools are missing. Install them to use all features."))
    return 0 if ok else 2


def cmd_step(args: argparse.Namespace) -> int:
    root = _project_root()
    cfg = load_config(root)
    agent = args.agent

    if args.dry_run:
        print(f"DRY RUN - would execute iteration with agent={agent}")
        print()
        prd_path = root / cfg.files.prd
        try:
            task = select_next_task(prd_path)
            if task:
                print(f"Selected task: id={task.id} title={task.title}")
            else:
                print("No task selected (PRD may be complete)")
        except FileNotFoundError:
            print("PRD file not found")

        print()
        print("Runner config:")
        runner = cfg.runners.get(agent)
        if runner:
            print(f"  argv: {runner.argv}")
        else:
            print(f"  ERROR: Unknown agent '{agent}'")

        print()
        print("Quality gates:")
        if cfg.gates.commands:
            for cmd in cfg.gates.commands:
                print(f"  - {cmd}")
        else:
            print("  (none configured)")

        return 0

    iter_n = next_iteration_number(root)
    res = run_iteration(root, agent=agent, cfg=cfg, iteration=iter_n)

    status = "✓" if res.return_code == 0 else "✗"
    print(
        f"{status} Iteration {res.iteration} agent={agent} story_id={res.story_id} rc={res.return_code} exit={res.exit_signal}"
    )
    print(f"Log: {res.log_path}")
    if res.no_progress_streak >= cfg.loop.no_progress_limit:
        print(
            f"⚠ Stopped: no progress streak reached ({res.no_progress_streak}/{cfg.loop.no_progress_limit})."
        )
        return 3
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    root = _project_root()
    agent = args.agent
    results = run_loop(root, agent=agent, max_iterations=args.max_iterations)
    for r in results:
        print(
            f"iter={r.iteration} story_id={r.story_id} rc={r.return_code} exit={r.exit_signal} log={r.log_path.name}"
        )
    last = results[-1] if results else None
    if last and last.exit_signal is True:
        return 0
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = _project_root()
    cfg = load_config(root)
    prd_path = root / cfg.files.prd

    try:
        done, total = task_counts(prd_path)
    except FileNotFoundError:
        done, total = 0, 0

    next_task = None
    try:
        next_task = select_next_task(prd_path)
    except FileNotFoundError:
        next_task = None

    print(f"PRD: {cfg.files.prd}")

    # Progress bar
    if total > 0:
        pct = int((done / total) * 100)
        bar_width = 30
        filled = int((done / total) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        print(f"Progress: [{bar}] {done}/{total} ({pct}%)")
    else:
        print(f"Progress: {done}/{total} tasks done")

    if next_task is not None:
        print(f"Next: id={next_task.id} title={next_task.title}")
    else:
        print("Next: (none)")

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
                        "exit_signal_effective",
                        "log",
                    ]:
                        if k in last:
                            print(f"  {k}: {last[k]}")
        except Exception:
            pass
    return 0


def _plan_prompt(prd_filename: str, desc: str) -> str:
    ext = Path(prd_filename).suffix.lower()
    lines: list[str] = []
    lines.append(
        "You are generating a Product Requirements Document (PRD) for the Golden Ralph Loop."
    )
    lines.append("")
    lines.append(f"Write or update the PRD file at: {prd_filename} (repo root).")
    lines.append(
        "Do NOT implement any code in this step. Only produce the PRD/task list."
    )
    lines.append("")

    if ext in {".md", ".markdown"}:
        lines.append("PRD format: Markdown")
        lines.append("- Include a '## Tasks' section.")
        lines.append("- Put each task on its own checkbox line: '- [ ] <task>'.")
        lines.append("- Keep tasks small and independently verifiable.")
    else:
        lines.append("PRD format: JSON")
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
        "After writing the PRD file, briefly summarize the task list you created."
    )
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
        print(
            "No description provided. Use --desc, --desc-file, or pipe text into stdin."
        )
        return 2

    prompt_text = _plan_prompt(cfg.files.prd, desc)

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

    argv = build_runner_argv(agent, runner.argv, prompt_text)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = logs_dir / f"{ts}-plan-{agent}.log"

    start = time.time()
    cp = subprocess.run(argv, cwd=str(root), capture_output=True, text=True)
    duration_s = time.time() - start

    log_path.write_text(
        f"# ralph-gold plan log\n"
        f"timestamp_utc: {ts}\n"
        f"agent: {agent}\n"
        f"cmd: {json.dumps(argv)}\n"
        f"duration_seconds: {duration_s:.2f}\n"
        f"return_code: {cp.returncode}\n"
        f"\n--- prompt ---\n{prompt_text}\n"
        f"\n--- stdout ---\n{cp.stdout or ''}\n"
        f"\n--- stderr ---\n{cp.stderr or ''}\n",
        encoding="utf-8",
    )

    print(f"Plan run complete (rc={cp.returncode}). Log: {log_path}")
    return int(cp.returncode)


def cmd_bridge(args: argparse.Namespace) -> int:
    root = _project_root()
    from .bridge import BridgeServer

    server = BridgeServer(root)
    # JSON-RPC over stdio (NDJSON). This call blocks until stdin closes.
    server.serve()
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    """Clear state and logs without touching config files."""
    root = _project_root()
    ralph_dir = root / ".ralph"

    if not ralph_dir.exists():
        print("No .ralph directory found. Nothing to reset.")
        return 0

    # Clear state
    state_path = ralph_dir / "state.json"
    if state_path.exists():
        state_path.unlink()
        print("✓ Cleared state.json")

    # Clear logs
    logs_dir = ralph_dir / "logs"
    if logs_dir.exists():
        for log_file in logs_dir.glob("*.log"):
            log_file.unlink()
        print(f"✓ Cleared {len(list(logs_dir.glob('*.log')))} log files")

    # Clear prompt files
    for prompt_file in ralph_dir.glob("prompt-*.txt"):
        prompt_file.unlink()

    print("\nReset complete. Config files preserved.")
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    """View recent logs."""
    root = _project_root()
    logs_dir = root / ".ralph" / "logs"

    if not logs_dir.exists():
        print("No logs directory found.")
        return 1

    log_files = sorted(
        logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True
    )

    if not log_files:
        print("No log files found.")
        return 0

    limit = args.limit or 5

    if args.last:
        # Show full content of last log
        last_log = log_files[0]
        print(f"=== {last_log.name} ===\n")
        print(last_log.read_text(encoding="utf-8"))
        return 0

    # List recent logs
    print(f"Recent logs (showing {min(limit, len(log_files))} of {len(log_files)}):\n")
    for log_file in log_files[:limit]:
        # Parse log header for summary
        content = log_file.read_text(encoding="utf-8")
        lines = content.split("\n")
        summary = {}
        for line in lines[:15]:  # Check first 15 lines for metadata
            if ": " in line:
                key, val = line.split(": ", 1)
                summary[key] = val

        iter_num = summary.get("iteration", "?")
        agent = summary.get("agent", "?")
        rc = summary.get("return_code", "?")
        story = summary.get("story_id", "?")

        status = "✓" if rc == "0" else "✗"
        print(f"{status} {log_file.name}")
        print(f"   iter={iter_num} agent={agent} story={story} rc={rc}")
        print()

    print("View full log: ralph logs --last")
    print(f"View more: ralph logs --limit {limit * 2}")
    return 0


def cmd_edit(args: argparse.Namespace) -> int:
    """Open ralph files in editor."""
    root = _project_root()
    ralph_dir = root / ".ralph"

    file_map = {
        "agents": "AGENTS.md",
        "prompt": "PROMPT.md",
        "prd": "prd.json",  # Default, will be overridden from config
        "config": "ralph.toml",
        "progress": "progress.md",
    }

    target = args.file

    if target == "prd":
        cfg = load_config(root)
        file_path = root / cfg.files.prd
    elif target in file_map:
        filename = file_map[target]
        if filename:
            file_path = ralph_dir / filename
        else:
            print(f"Unknown file: {target}")
            return 1
    else:
        print(f"Unknown file: {target}")
        print(f"Available: {', '.join(file_map.keys())}")
        return 1

    if not file_path.exists():
        print(f"File not found: {file_path}")
        return 1

    editor = os.environ.get("EDITOR", "vim")
    subprocess.run([editor, str(file_path)])
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ralph",
        description="ralph-gold: Golden Ralph Loop orchestrator (uv-first)",
    )
    p.add_argument("--version", action="version", version=f"ralph-gold {__version__}")

    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Initialize Ralph files in the current repo")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing files")
    p_init.set_defaults(func=cmd_init)

    p_doc = sub.add_parser(
        "doctor", help="Check local prerequisites (git, uv, agent CLIs)"
    )
    p_doc.set_defaults(func=cmd_doctor)

    p_step = sub.add_parser("step", help="Run exactly one iteration")
    p_step.add_argument(
        "--agent",
        default="codex",
        help="Runner to use (codex|claude|copilot or custom runner name)",
    )
    p_step.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without executing",
    )
    p_step.set_defaults(func=cmd_step)

    p_run = sub.add_parser(
        "run", help="Run the loop for N iterations (default from ralph.toml)"
    )
    p_run.add_argument(
        "--agent",
        default="codex",
        help="Runner to use (codex|claude|copilot or custom)",
    )
    p_run.add_argument(
        "--max-iterations", type=int, default=None, help="Override loop.max_iterations"
    )
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser(
        "status", help="Show PRD progress + last iteration summary"
    )
    p_status.set_defaults(func=cmd_status)

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
    p_plan.set_defaults(func=cmd_plan)

    p_bridge = sub.add_parser(
        "bridge", help="Start a JSON-RPC bridge over stdio (for VS Code)"
    )
    p_bridge.set_defaults(func=cmd_bridge)

    p_reset = sub.add_parser(
        "reset", help="Clear state and logs (preserves config files)"
    )
    p_reset.set_defaults(func=cmd_reset)

    p_logs = sub.add_parser("logs", help="View recent iteration logs")
    p_logs.add_argument(
        "--limit", type=int, default=5, help="Number of logs to show (default: 5)"
    )
    p_logs.add_argument(
        "--last", action="store_true", help="Show full content of most recent log"
    )
    p_logs.set_defaults(func=cmd_logs)

    p_edit = sub.add_parser("edit", help="Open ralph files in $EDITOR")
    p_edit.add_argument(
        "file",
        choices=["agents", "prompt", "prd", "config", "progress"],
        help="File to edit",
    )
    p_edit.set_defaults(func=cmd_edit)

    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
