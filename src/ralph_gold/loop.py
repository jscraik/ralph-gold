from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import Config, RunnerConfig, load_config
from .prd import SelectedTask, all_done as prd_all_done, force_task_open, select_next_task


EXIT_RE = re.compile(r"EXIT_SIGNAL:\s*(true|false)\s*$", re.IGNORECASE | re.MULTILINE)


@dataclass
class GateResult:
    cmd: str
    return_code: int
    duration_seconds: float
    stdout: str
    stderr: str


@dataclass
class IterationResult:
    iteration: int
    agent: str
    story_id: Optional[int]
    exit_signal: Optional[bool]
    return_code: int
    log_path: Path
    progress_made: bool
    no_progress_streak: int
    gates_ok: Optional[bool]
    repo_clean: bool


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_git_repo(project_root: Path) -> None:
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(project_root),
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as e:
        raise RuntimeError("This tool must be run inside a git repository (git init).") from e


def git_head(project_root: Path) -> str:
    cp = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(project_root),
        check=True,
        capture_output=True,
        text=True,
    )
    return cp.stdout.strip()


def git_is_clean(project_root: Path) -> bool:
    cp = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(project_root),
        check=True,
        capture_output=True,
        text=True,
    )
    return cp.stdout.strip() == ""


def parse_exit_signal(output: str) -> Optional[bool]:
    m = EXIT_RE.search(output.strip())
    if not m:
        return None
    return m.group(1).lower() == "true"


def build_prompt(project_root: Path, cfg: Config, task: Optional[SelectedTask], iteration: int) -> str:
    """Keep the prompt small; the filesystem is the memory."""

    prompt_lines: List[str] = []
    prompt_lines.append("You are running inside the Golden Ralph Loop.")
    prompt_lines.append("")
    prompt_lines.append("Read these files for context and memory:")
    prompt_lines.append(f"- {cfg.files.prompt}")
    prompt_lines.append(f"- {cfg.files.agents}")
    prompt_lines.append(f"- {cfg.files.prd}")
    prompt_lines.append(f"- {cfg.files.progress}")
    prompt_lines.append("")
    prompt_lines.append("Iteration rules:")
    prompt_lines.append("- One task per iteration.")
    prompt_lines.append("- Use backpressure: run the quality gate commands from AGENTS.md and fix until they pass.")
    prompt_lines.append("- Update the PRD file to mark the task done, append learnings to progress.md, then commit.")
    prompt_lines.append("")

    if task is not None:
        prompt_lines.append("Work on this task (selected for you):")
        prompt_lines.append(f"- Task ID: {task.id}")
        if task.title:
            prompt_lines.append(f"- Title: {task.title}")
        prompt_lines.append("")
        prompt_lines.append("Do not work on any other task in this iteration.")
        prompt_lines.append("")
    else:
        prompt_lines.append("No task was selected (the PRD may be empty or malformed).")
        prompt_lines.append("If the PRD is complete, confirm and prepare to exit.")
        prompt_lines.append("")

    prompt_lines.append("Exit protocol:")
    prompt_lines.append("At the very end of your output, print exactly one line:")
    prompt_lines.append("EXIT_SIGNAL: true|false")
    prompt_lines.append("- true ONLY if all tasks are done AND the repo is clean with all gates passing.")
    prompt_lines.append("- otherwise false.")
    prompt_lines.append("")
    return "\n".join(prompt_lines)


def build_runner_argv(agent: str, argv_template: List[str], prompt_text: str) -> List[str]:
    argv = [str(x) for x in argv_template]

    # Placeholder replacement if present anywhere.
    if "{prompt}" in argv:
        return [prompt_text if x == "{prompt}" else x for x in argv]

    if agent.lower() == "claude":
        if "-p" in argv:
            i = argv.index("-p")
            # If -p is last, or next token looks like a flag, insert prompt.
            if i == len(argv) - 1 or str(argv[i + 1]).startswith("-"):
                argv.insert(i + 1, prompt_text)
        else:
            argv.extend(["-p", prompt_text])
        return argv

    if agent.lower() == "copilot":
        if "--prompt" in argv:
            i = argv.index("--prompt")
            if i == len(argv) - 1 or str(argv[i + 1]).startswith("-"):
                argv.insert(i + 1, prompt_text)
            else:
                argv[i + 1] = prompt_text
        else:
            argv.extend(["--prompt", prompt_text])
        return argv

    # Default: append prompt as final argument (codex exec "...")
    argv.append(prompt_text)
    return argv


def load_state(state_path: Path) -> Dict[str, Any]:
    if not state_path.exists():
        return {
            "createdAt": utc_now_iso(),
            "invocations": [],  # epoch timestamps
            "noProgressStreak": 0,
            "history": [],
        }
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            raise ValueError("state.json must be an object")
        state.setdefault("history", [])
        state.setdefault("invocations", [])
        state.setdefault("noProgressStreak", 0)
        return state
    except Exception:
        return {
            "createdAt": utc_now_iso(),
            "invocations": [],
            "noProgressStreak": 0,
            "history": [],
        }


def save_state(state_path: Path, state: Dict[str, Any]) -> None:
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def next_iteration_number(project_root: Path) -> int:
    """Return the next iteration index based on .ralph/state.json history.

    This keeps iteration artifacts monotonic across separate invocations
    (step/run/bridge).
    """

    state_path = project_root / ".ralph" / "state.json"
    state = load_state(state_path)
    hist = state.get("history", [])
    if isinstance(hist, list) and hist:
        last = hist[-1]
        if isinstance(last, dict):
            try:
                return int(last.get("iteration", 0)) + 1
            except Exception:
                pass
    return 1



def _rate_limit_ok(state: Dict[str, Any], per_hour: int) -> Tuple[bool, int]:
    """Returns (ok, remaining_wait_seconds). If disabled, ok=True."""

    if per_hour <= 0:
        return True, 0
    now = time.time()
    window = 3600.0
    inv: List[float] = []
    for ts in state.get("invocations", []):
        try:
            inv.append(float(ts))
        except Exception:
            continue
    inv = [t for t in inv if now - t < window]
    state["invocations"] = inv
    if len(inv) < per_hour:
        return True, 0
    oldest = min(inv)
    wait = int(max(0, window - (now - oldest)))
    return False, wait


def _gate_shell_argv(cmd: str) -> List[str]:
    """Return a shell invocation argv for the current platform."""

    if os.name == "nt":
        return ["cmd", "/c", cmd]

    # Prefer bash when available for predictable behavior; otherwise fall back to sh.
    if shutil.which("bash"):
        return ["bash", "-lc", cmd]

    return ["sh", "-lc", cmd]


def _run_gate_command(project_root: Path, cmd: str) -> GateResult:
    """Run a single gate command in a predictable shell environment."""

    start = time.time()
    cp = subprocess.run(
        _gate_shell_argv(cmd),
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    return GateResult(
        cmd=cmd,
        return_code=int(cp.returncode),
        duration_seconds=time.time() - start,
        stdout=cp.stdout or "",
        stderr=cp.stderr or "",
    )


def run_gates(project_root: Path, commands: List[str]) -> Tuple[bool, List[GateResult]]:
    if not commands:
        return True, []
    results: List[GateResult] = []
    ok = True
    for cmd in commands:
        res = _run_gate_command(project_root, cmd)
        results.append(res)
        if res.return_code != 0:
            ok = False
    return ok, results


def _format_gate_results(gates_ok: Optional[bool], results: List[GateResult]) -> str:
    if gates_ok is None:
        return "(gates: not configured)"
    if not results:
        return "(gates: configured but empty)"
    status = "PASS" if gates_ok else "FAIL"
    lines: List[str] = [f"gates_overall: {status}"]
    for i, r in enumerate(results, start=1):
        lines.append("")
        lines.append(f"gate_{i}_cmd: {r.cmd}")
        lines.append(f"gate_{i}_return_code: {r.return_code}")
        lines.append(f"gate_{i}_duration_seconds: {r.duration_seconds:.2f}")
        if r.stdout.strip():
            lines.append("--- gate stdout ---")
            lines.append(r.stdout.rstrip())
        if r.stderr.strip():
            lines.append("--- gate stderr ---")
            lines.append(r.stderr.rstrip())
    return "\n".join(lines) + "\n"


def _get_runner(cfg: Config, agent: str) -> RunnerConfig:
    runner = cfg.runners.get(agent)
    if runner is None:
        available = ", ".join(sorted(cfg.runners.keys()))
        raise RuntimeError(f"Unknown agent '{agent}'. Available runners: {available}")
    return runner


def run_iteration(project_root: Path, agent: str, cfg: Optional[Config] = None, iteration: int = 1, task_override: Optional[SelectedTask] = None) -> IterationResult:
    cfg = cfg or load_config(project_root)
    ensure_git_repo(project_root)

    prd_path = project_root / cfg.files.prd
    state_dir = project_root / ".ralph"
    logs_dir = state_dir / "logs"
    state_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)

    state_path = state_dir / "state.json"
    state = load_state(state_path)

    ok, wait_s = _rate_limit_ok(state, cfg.loop.rate_limit_per_hour)
    if not ok:
        raise RuntimeError(
            f"Rate limit reached ({cfg.loop.rate_limit_per_hour}/hour). Wait ~{wait_s}s or increase rate_limit_per_hour."
        )

    task = task_override if task_override is not None else select_next_task(prd_path)
    story_id = task.id if task is not None else None

    prompt_text = build_prompt(project_root, cfg, task, iteration)

    # Write prompt to disk for debugging / reproducibility.
    prompt_file = state_dir / f"prompt-iter{iteration:04d}.txt"
    prompt_file.write_text(prompt_text, encoding="utf-8")

    runner = _get_runner(cfg, agent)
    argv = build_runner_argv(agent, runner.argv, prompt_text)

    head_before = git_head(project_root)

    start = time.time()
    cp = subprocess.run(
        argv,
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    duration_s = time.time() - start

    gate_cmds = cfg.gates.commands if cfg.gates.commands else []
    gates_ok: Optional[bool]
    gate_results: List[GateResult]
    if gate_cmds:
        gates_ok, gate_results = run_gates(project_root, gate_cmds)
    else:
        gates_ok, gate_results = None, []

    # If gates fail, undo any PRD completion that the agent might have applied.
    if gates_ok is False and story_id is not None:
        force_task_open(prd_path, story_id)

    head_after = git_head(project_root)
    repo_clean = git_is_clean(project_root)

    progress_made = (head_after != head_before) or (not repo_clean)

    combined_output = (cp.stdout or "") + "\n" + (cp.stderr or "")
    exit_signal_raw = parse_exit_signal(combined_output)
    exit_signal = exit_signal_raw

    # Enforce exit constraints at orchestrator level as well.
    if exit_signal is True and not repo_clean:
        exit_signal = False
    if exit_signal is True and gates_ok is False:
        exit_signal = False

    # Persist logs (stdout/stderr + gates)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = logs_dir / f"{ts}-iter{iteration:04d}-{agent}.log"

    log_path.write_text(
        f"# ralph-gold log\n"
        f"timestamp_utc: {ts}\n"
        f"iteration: {iteration}\n"
        f"agent: {agent}\n"
        f"story_id: {story_id}\n"
        f"cmd: {json.dumps(argv)}\n"
        f"duration_seconds: {duration_s:.2f}\n"
        f"return_code: {cp.returncode}\n"
        f"repo_clean: {str(repo_clean).lower()}\n"
        f"exit_signal_raw: {exit_signal_raw}\n"
        f"exit_signal_effective: {exit_signal}\n"
        f"\n--- stdout ---\n{cp.stdout or ''}\n"
        f"\n--- stderr ---\n{cp.stderr or ''}\n"
        f"\n--- gates ---\n{_format_gate_results(gates_ok, gate_results)}",
        encoding="utf-8",
    )

    # Update state + rate limit
    invocations = state.get("invocations", [])
    if not isinstance(invocations, list):
        invocations = []
    invocations = [float(x) for x in invocations if isinstance(x, (int, float, str))]
    invocations.append(time.time())
    state["invocations"] = invocations

    if progress_made:
        state["noProgressStreak"] = 0
    else:
        try:
            state["noProgressStreak"] = int(state.get("noProgressStreak", 0)) + 1
        except Exception:
            state["noProgressStreak"] = 1

    history = state.get("history", [])
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "ts": ts,
            "iteration": iteration,
            "agent": agent,
            "story_id": story_id,
            "duration_seconds": round(duration_s, 2),
            "return_code": int(cp.returncode),
            "exit_signal_raw": exit_signal_raw,
            "exit_signal_effective": exit_signal,
            "repo_clean": bool(repo_clean),
            "gates_ok": gates_ok,
            "gate_results": [
                {
                    "cmd": r.cmd,
                    "return_code": r.return_code,
                    "duration_seconds": round(r.duration_seconds, 2),
                }
                for r in gate_results
            ],
            "log": str(log_path.name),
        }
    )
    state["history"] = history[-200:]  # keep last 200 iterations

    save_state(state_path, state)

    return IterationResult(
        iteration=iteration,
        agent=agent,
        story_id=story_id,
        exit_signal=exit_signal,
        return_code=int(cp.returncode),
        log_path=log_path,
        progress_made=progress_made,
        no_progress_streak=int(state.get("noProgressStreak", 0)),
        gates_ok=gates_ok,
        repo_clean=repo_clean,
    )


def run_loop(project_root: Path, agent: str, max_iterations: Optional[int] = None) -> List[IterationResult]:
    cfg = load_config(project_root)
    ensure_git_repo(project_root)

    prd_path = project_root / cfg.files.prd
    state_dir = project_root / ".ralph"
    state_dir.mkdir(exist_ok=True)
    state_path = state_dir / "state.json"
    state = load_state(state_path)
    state["noProgressStreak"] = 0
    save_state(state_path, state)

    results: List[IterationResult] = []
    limit = max_iterations if max_iterations is not None else cfg.loop.max_iterations

    start_iter = next_iteration_number(project_root)

    for offset in range(limit):
        i = start_iter + offset
        res = run_iteration(project_root, agent=agent, cfg=cfg, iteration=i)
        results.append(res)

        done = prd_all_done(prd_path)

        # Circuit breaker: stop if we see repeated no-progress iterations.
        if res.no_progress_streak >= cfg.loop.no_progress_limit:
            break

        # Dual gate: only exit when PRD done AND explicit EXIT_SIGNAL true.
        if done and res.exit_signal is True:
            break

        if cfg.loop.sleep_seconds_between_iters > 0:
            time.sleep(cfg.loop.sleep_seconds_between_iters)

    return results
