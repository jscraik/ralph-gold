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
from .prd import SelectedTask
from .trackers import make_tracker


EXIT_RE = re.compile(r"EXIT_SIGNAL:\s*(true|false)\s*$", re.IGNORECASE | re.MULTILINE)
JUDGE_RE = re.compile(r"JUDGE_SIGNAL:\s*(true|false)\s*$", re.IGNORECASE | re.MULTILINE)


@dataclass
class GateResult:
    cmd: str
    return_code: int
    duration_seconds: float
    stdout: str
    stderr: str


@dataclass
class LlmJudgeResult:
    enabled: bool
    agent: str
    return_code: int
    duration_seconds: float
    judge_signal_raw: Optional[bool]
    judge_signal_effective: Optional[bool]
    stdout: str
    stderr: str


@dataclass
class IterationResult:
    iteration: int
    agent: str
    story_id: Optional[str]
    exit_signal: Optional[bool]
    return_code: int
    log_path: Path
    progress_made: bool
    no_progress_streak: int
    gates_ok: Optional[bool]
    repo_clean: bool
    judge_ok: Optional[bool]


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
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=str(project_root),
        check=False,
        capture_output=True,
        text=True,
    )
    if cp.returncode != 0:
        return ""
    return (cp.stdout or "").strip()


def git_current_branch(project_root: Path) -> str:
    cp = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(project_root),
        check=True,
        capture_output=True,
        text=True,
    )
    return (cp.stdout or "").strip()


def git_branch_exists(project_root: Path, branch: str) -> bool:
    cp = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return cp.returncode == 0


def git_checkout(project_root: Path, branch: str) -> None:
    subprocess.run(
        ["git", "checkout", branch],
        cwd=str(project_root),
        check=True,
        capture_output=True,
        text=True,
    )


def git_create_and_checkout(project_root: Path, branch: str, base_ref: Optional[str]) -> None:
    argv = ["git", "checkout", "-b", branch]
    if base_ref:
        argv.append(base_ref)
    subprocess.run(
        argv,
        cwd=str(project_root),
        check=True,
        capture_output=True,
        text=True,
    )


_IGNORED_GIT_STATUS_PREFIXES = (
    ".ralph/",
)


def _git_status_lines(project_root: Path) -> List[str]:
    cp = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(project_root),
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [ln for ln in (cp.stdout or "").splitlines() if ln.strip()]

    # Filter orchestrator noise that should not count as "repo dirty".
    filtered: List[str] = []
    for ln in lines:
        # porcelain: XY<space>path
        path = ln[3:].strip() if len(ln) > 3 else ln.strip()

        # Ignore orchestrator operational state under .ralph/.
        if any(path.startswith(p) for p in _IGNORED_GIT_STATUS_PREFIXES):
            continue

        filtered.append(ln)
    return filtered


def git_is_clean(project_root: Path) -> bool:
    return len(_git_status_lines(project_root)) == 0


def _parse_bool_signal(output: str, pattern: re.Pattern[str]) -> Optional[bool]:
    """Parse a trailing boolean signal from plain text or NDJSON streams."""

    raw = output.strip()
    m = pattern.search(raw)
    if m:
        return m.group(1).lower() == "true"

    # Fallback: attempt to parse NDJSON and search within string fields.
    def _iter_strings(obj: Any):
        if isinstance(obj, str):
            yield obj
        elif isinstance(obj, dict):
            for v in obj.values():
                yield from _iter_strings(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from _iter_strings(v)

    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        for s in _iter_strings(obj):
            mm = pattern.search(s.strip())
            if mm:
                return mm.group(1).lower() == "true"
    return None


def parse_exit_signal(output: str) -> Optional[bool]:
    """Extract EXIT_SIGNAL from an agent run."""

    return _parse_bool_signal(output, EXIT_RE)


def parse_judge_signal(output: str) -> Optional[bool]:
    """Extract JUDGE_SIGNAL from an LLM judge run."""

    return _parse_bool_signal(output, JUDGE_RE)


def build_prompt(project_root: Path, cfg: Config, task: Optional[SelectedTask], iteration: int) -> str:
    """Build the per-iteration prompt.

    Design goal:
    - Keep orchestration deterministic and cross-tool.
    - Load the (version-controlled) prompt file as the base instructions.
    - Add a small, machine-generated addendum that injects the selected task.
    """

    prompt_path = project_root / cfg.files.prompt
    base = ""
    if prompt_path.exists():
        base = prompt_path.read_text(encoding="utf-8")

    prompt_lines: List[str] = []
    if base.strip():
        prompt_lines.append(base.rstrip())
        prompt_lines.append("")
        prompt_lines.append("---")
        prompt_lines.append("")
    else:
        prompt_lines.append("# Golden Ralph Loop")
        prompt_lines.append("(missing prompt file; using fallback instructions)")
        prompt_lines.append("")

    prompt_lines.append("## Orchestrator Addendum (auto-generated)")
    prompt_lines.append(f"Iteration: {iteration}")
    prompt_lines.append("")
    prompt_lines.append("Study these files for context and durable memory:")
    prompt_lines.append(f"- {cfg.files.agents}")
    prompt_lines.append(f"- {cfg.files.prd}")
    prompt_lines.append(f"- {cfg.files.progress}")
    prompt_lines.append("")
    prompt_lines.append("Hard iteration constraints:")
    prompt_lines.append("- One task per iteration (one commit per iteration).")
    prompt_lines.append("- Apply backpressure: run the commands in AGENTS.md and fix until they pass.")
    prompt_lines.append("")

    if task is not None:
        prompt_lines.append("Selected task for this iteration:")
        prompt_lines.append(f"- id: {task.id}")
        if task.title:
            prompt_lines.append(f"- title: {task.title}")
        if task.acceptance:
            prompt_lines.append("- acceptance:")
            for a in task.acceptance[:20]:
                prompt_lines.append(f"  - {a}")
        prompt_lines.append("")
        prompt_lines.append("Do not work on any other task in this iteration.")
        prompt_lines.append("")
    else:
        prompt_lines.append("No task was selected (task file may be empty or malformed).")
        prompt_lines.append("If the task file is complete, confirm and prepare to exit.")
        prompt_lines.append("")

    prompt_lines.append("Exit protocol (required):")
    prompt_lines.append("At the very end of your output, print exactly one line:")
    prompt_lines.append("EXIT_SIGNAL: true  OR  EXIT_SIGNAL: false")
    prompt_lines.append("")
    return "\n".join(prompt_lines) + "\n"


def build_runner_invocation(agent: str, argv_template: List[str], prompt_text: str) -> Tuple[List[str], Optional[str]]:
    """Build argv and optional stdin for the configured agent runner.

    Key rule for Codex:
    - Prefer passing the prompt via stdin using '-' to avoid argv quoting/length issues.
      Example: `codex exec --full-auto -` (prompt read from stdin).
    """

    argv = [str(x) for x in argv_template]
    agent_l = agent.lower().strip()

    # Placeholder replacement (string literal '{prompt}')
    if "{prompt}" in argv:
        argv = [prompt_text if x == "{prompt}" else x for x in argv]
        return argv, None

    # Codex: stdin is the most robust.
    if agent_l == "codex":
        if "-" not in argv:
            argv.append("-")
        return argv, prompt_text

    # Claude Code: `claude -p "..."`
    if agent_l == "claude":
        if "-p" in argv:
            i = argv.index("-p")
            if i == len(argv) - 1 or str(argv[i + 1]).startswith("-"):
                argv.insert(i + 1, prompt_text)
        else:
            argv.extend(["-p", prompt_text])
        return argv, None

    # GitHub Copilot CLI: `copilot --prompt "..."`
    if agent_l == "copilot":
        if "--prompt" in argv:
            i = argv.index("--prompt")
            if i == len(argv) - 1 or str(argv[i + 1]).startswith("-"):
                argv.insert(i + 1, prompt_text)
            else:
                argv[i + 1] = prompt_text
        else:
            argv.extend(["--prompt", prompt_text])
        return argv, None

    # Default: append prompt as final argument.
    argv.append(prompt_text)
    return argv, None


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


def _truncate(text: str, max_chars: int) -> Tuple[str, bool]:
    if max_chars <= 0:
        return text, False
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n\n...(truncated)...\n", True


def _git_capture(project_root: Path, argv: List[str]) -> str:
    cp = subprocess.run(argv, cwd=str(project_root), capture_output=True, text=True)
    out = cp.stdout or ""
    err = cp.stderr or ""
    if err.strip():
        return out + "\n" + err
    return out


def _diff_for_judge(project_root: Path, head_before: str, head_after: str, max_chars: int) -> str:
    """Collect a reasonably informative diff payload for the judge."""

    parts: List[str] = []
    try:
        status = _git_capture(project_root, ["git", "status", "--porcelain"]).strip()
        parts.append("# git status --porcelain\n" + (status or "(clean)"))
    except Exception:
        pass

    if head_after and head_after != head_before:
        try:
            show = _git_capture(project_root, ["git", "show", "--no-color", "HEAD"])
            parts.append("\n# git show HEAD\n" + show.strip())
        except Exception:
            pass
    else:
        try:
            diff = _git_capture(project_root, ["git", "diff", "--no-color"])
            parts.append("\n# git diff (working tree)\n" + (diff.strip() or "(no diff)"))
        except Exception:
            pass

    combined = "\n\n".join(parts).strip() + "\n"
    truncated_text, truncated = _truncate(combined, max_chars)
    if truncated:
        return truncated_text
    return combined


def build_judge_prompt(project_root: Path, cfg: Config, task: SelectedTask, diff_text: str, gates_ok: Optional[bool], gate_results: List[GateResult]) -> str:
    """Build the LLM-as-judge prompt."""

    prompt_path = project_root / cfg.gates.llm_judge.prompt
    base = ""
    if prompt_path.exists():
        try:
            base = prompt_path.read_text(encoding="utf-8")
        except Exception:
            base = ""

    lines: List[str] = []
    if base.strip():
        lines.append(base.rstrip())
        lines.append("\n---\n")
    else:
        lines.append("# Ralph LLM Judge")
        lines.append("(missing PROMPT_judge.md; using fallback instructions)")
        lines.append("")
        lines.append("You are a strict reviewer.")
        lines.append("Return JUDGE_SIGNAL: true only when the task is complete and correct.")
        lines.append("")

    lines.append("## Orchestrator Addendum (auto-generated)")
    lines.append("")
    lines.append(f"Task id: {task.id}")
    lines.append(f"Task title: {task.title}")
    if task.acceptance:
        lines.append("\nAcceptance criteria:")
        for a in task.acceptance[:30]:
            lines.append(f"- {a}")
    lines.append("")
    lines.append("Deterministic gates summary:")
    if gates_ok is None:
        lines.append("- gates: not configured")
    else:
        lines.append(f"- gates_overall: {'PASS' if gates_ok else 'FAIL'}")
        for r in gate_results[:10]:
            lines.append(f"  - cmd: {r.cmd} (rc={r.return_code})")
    lines.append("")
    lines.append("Diff/context (truncated):")
    lines.append("```diff")
    lines.append(diff_text.rstrip())
    lines.append("```")
    lines.append("")
    lines.append("Decision protocol:")
    lines.append("- If anything important is missing/incorrect, return JUDGE_SIGNAL: false.")
    lines.append("- If requirements are satisfied and implementation quality is acceptable, return JUDGE_SIGNAL: true.")
    lines.append("")
    lines.append("Output format (required):")
    lines.append("- Provide a short rationale (bullets ok).")
    lines.append("- At the very end, print exactly one line:")
    lines.append("JUDGE_SIGNAL: true  OR  JUDGE_SIGNAL: false")
    lines.append("")
    return "\n".join(lines) + "\n"


def _get_runner(cfg: Config, agent: str) -> RunnerConfig:
    runner = cfg.runners.get(agent)
    if runner is None:
        available = ", ".join(sorted(cfg.runners.keys()))
        raise RuntimeError(f"Unknown agent '{agent}'. Available runners: {available}")
    return runner


def _slugify(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t)
    t = t.strip("-")
    return t or "work"


def _normalize_git_branch_name(branch: str) -> str:
    """Best-effort normalization for branch names coming from human text."""

    b = (branch or "").strip()
    b = b.replace(" ", "-")
    # Allow common git branch characters.
    b = re.sub(r"[^A-Za-z0-9._/-]+", "-", b)
    b = re.sub(r"/{2,}", "/", b)
    b = b.strip("/-")
    return b


def _ensure_feature_branch(project_root: Path, cfg: Config, tracker_branch: Optional[str]) -> Optional[str]:
    """Checkout/create a feature branch based on PRD metadata."""

    strategy = (cfg.git.branch_strategy or "none").strip().lower()
    if strategy in {"none", "off", "false", "0"}:
        return None
    if strategy != "per_prd":
        return None

    # Resolve branch name.
    branch = _normalize_git_branch_name(tracker_branch or "")
    if not branch:
        branch = _normalize_git_branch_name(f"{cfg.git.branch_prefix}{_slugify(project_root.name)}")
    if not branch:
        return None

    try:
        current = git_current_branch(project_root)
    except Exception:
        current = ""
    if current == branch:
        return branch

    # Avoid switching branches when the worktree is dirty (risk of accidental carry-over).
    if not git_is_clean(project_root):
        return None

    base_ref = (cfg.git.base_branch or "").strip()
    if not base_ref:
        base_ref = git_head(project_root)
    if not base_ref:
        base_ref = None

    if git_branch_exists(project_root, branch):
        git_checkout(project_root, branch)
    else:
        git_create_and_checkout(project_root, branch, base_ref)
    return branch


def run_iteration(
    project_root: Path,
    agent: str,
    cfg: Optional[Config] = None,
    iteration: int = 1,
    task_override: Optional[SelectedTask] = None,
) -> IterationResult:
    cfg = cfg or load_config(project_root)
    ensure_git_repo(project_root)

    state_dir = project_root / ".ralph"
    logs_dir = state_dir / "logs"
    state_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    state_path = state_dir / "state.json"
    state = load_state(state_path)

    ok, wait_s = _rate_limit_ok(state, cfg.loop.rate_limit_per_hour)
    if not ok:
        raise RuntimeError(
            f"Rate limit reached ({cfg.loop.rate_limit_per_hour}/hour). Wait ~{wait_s}s or increase rate_limit_per_hour."
        )

    tracker = make_tracker(project_root, cfg)
    allow_exit_without_all_done = (tracker.kind == "beads")
    branch = _ensure_feature_branch(project_root, cfg, tracker_branch=tracker.branch_name())

    # Capture done count before claiming a task (used for no-progress detection).
    try:
        done_before, total_before = tracker.counts()
    except Exception:
        done_before, total_before = 0, 0

    # Select task
    task: Optional[SelectedTask]
    try:
        task = task_override if task_override is not None else tracker.claim_next_task()
    except Exception as e:
        # Tracker failure (missing PRD, malformed JSON, etc.) should still produce a log + state entry.
        task = None
        task_err = str(e)
    else:
        task_err = ""

    story_id: Optional[str] = task.id if task is not None else None

    prompt_text = build_prompt(project_root, cfg, task, iteration)
    # Prompt snapshots are debug artifacts; keep them under .ralph/logs/.
    prompt_file = logs_dir / f"prompt-iter{iteration:04d}.txt"
    prompt_file.write_text(prompt_text, encoding="utf-8")

    runner = _get_runner(cfg, agent)
    argv, stdin_text = build_runner_invocation(agent, runner.argv, prompt_text)

    head_before = git_head(project_root)

    # Run agent
    start = time.time()
    timed_out = False
    timeout = cfg.loop.runner_timeout_seconds if cfg.loop.runner_timeout_seconds > 0 else None
    try:
        cp = subprocess.run(
            argv,
            cwd=str(project_root),
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        timed_out = True
        cp = subprocess.CompletedProcess(argv, returncode=124, stdout=e.stdout or "", stderr=e.stderr or "(timeout)")
    except FileNotFoundError as e:
        cp = subprocess.CompletedProcess(argv, returncode=127, stdout="", stderr=str(e))
    duration_s = time.time() - start

    # Gates
    gate_cmds = cfg.gates.commands if cfg.gates.commands else []
    if gate_cmds:
        gates_ok, gate_results = run_gates(project_root, gate_cmds)
    else:
        gates_ok, gate_results = None, []

    # Safety valve: if gates fail, force the task open again.
    if gates_ok is False and story_id is not None:
        try:
            tracker.force_task_open(story_id)
        except Exception:
            pass

    head_after_agent = git_head(project_root)

    # Optional: LLM-as-judge gate
    judge_cfg = cfg.gates.llm_judge
    judge_result: Optional[LlmJudgeResult] = None
    judge_ok: Optional[bool] = None
    if judge_cfg.enabled and story_id is not None and gates_ok is not False:
        try:
            done_now = tracker.is_task_done(story_id)
        except Exception:
            done_now = False

        if done_now and task is not None:
            diff_text = _diff_for_judge(
                project_root,
                head_before=head_before,
                head_after=head_after_agent,
                max_chars=int(judge_cfg.max_diff_chars),
            )
            judge_prompt = build_judge_prompt(
                project_root,
                cfg,
                task=task,
                diff_text=diff_text,
                gates_ok=gates_ok,
                gate_results=gate_results,
            )

            try:
                jr_runner = _get_runner(cfg, judge_cfg.agent)
                jr_argv, jr_stdin = build_runner_invocation(judge_cfg.agent, jr_runner.argv, judge_prompt)
            except Exception as e:
                judge_result = LlmJudgeResult(
                    enabled=True,
                    agent=str(judge_cfg.agent),
                    return_code=127,
                    duration_seconds=0.0,
                    judge_signal_raw=None,
                    judge_signal_effective=False,
                    stdout="",
                    stderr=str(e),
                )
                judge_ok = False
            else:
                j_start = time.time()
                try:
                    j_cp = subprocess.run(
                        jr_argv,
                        cwd=str(project_root),
                        input=jr_stdin,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )
                except subprocess.TimeoutExpired as e:
                    j_cp = subprocess.CompletedProcess(jr_argv, returncode=124, stdout=e.stdout or "", stderr=e.stderr or "(timeout)")
                j_dur = time.time() - j_start
                j_out = (j_cp.stdout or "")
                j_err = (j_cp.stderr or "")
                j_combined = j_out + "\n" + j_err
                j_raw = parse_judge_signal(j_combined)
                j_pass = (int(j_cp.returncode) == 0) and (j_raw is True)
                j_effective = True if j_pass else False
                judge_result = LlmJudgeResult(
                    enabled=True,
                    agent=str(judge_cfg.agent),
                    return_code=int(j_cp.returncode),
                    duration_seconds=j_dur,
                    judge_signal_raw=j_raw,
                    judge_signal_effective=j_effective,
                    stdout=j_out,
                    stderr=j_err,
                )
                judge_ok = bool(j_effective)

            if judge_ok is False and story_id is not None:
                try:
                    tracker.force_task_open(story_id)
                except Exception:
                    pass
        else:
            judge_ok = None

    # Append orchestrator entry to progress.md (append-only)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = logs_dir / f"{ts}-iter{iteration:04d}-{agent}.log"

    # Decide status for progress log
    try:
        done_now = bool(story_id) and tracker.is_task_done(story_id or "")
    except Exception:
        done_now = False
    status = "DONE" if (done_now and gates_ok is not False and judge_ok is not False) else "CONTINUE"
    checks = "PASS" if gates_ok is not False else "FAIL"

    progress_path = project_root / cfg.files.progress
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    if not progress_path.exists():
        progress_path.write_text(
            "# Ralph Progress Log\n\nAppend-only log of Ralph Loop iterations. Do not edit existing entries.\n\n## Iteration Log\n\n",
            encoding="utf-8",
        )
    story_label = f"S{story_id}" if story_id is not None else "-"
    try:
        current_branch = git_current_branch(project_root)
    except Exception:
        current_branch = "(no-branch)"
    branch_label = branch or current_branch
    progress_line = (
        f"- [{ts}] iter {iteration} mode=prd status={status} checks={checks} "
        f"story={story_label} agent={agent} branch={branch_label} log={log_path.name}"
    )
    with progress_path.open("a", encoding="utf-8") as f:
        f.write(progress_line + "\n")

    # Auto-commit / amend (best-effort)
    commit_action: Optional[str] = None
    commit_rc: Optional[int] = None
    commit_out = ""
    commit_err = ""
    if cfg.git.auto_commit and (gates_ok is not False) and (judge_ok is not False):
        # If the agent already committed but left a dirty tree, prefer amend.
        dirty = not git_is_clean(project_root)
        if dirty:
            try:
                # Stage everything, then unstage orchestrator operational state.
                subprocess.run(["git", "add", "-A"], cwd=str(project_root), check=True, capture_output=True, text=True)
                subprocess.run(["git", "reset", "--quiet", "--", ".ralph/logs/"], cwd=str(project_root), check=False, capture_output=True, text=True)
                subprocess.run(["git", "reset", "--quiet", "--", ".ralph/state.json"], cwd=str(project_root), check=False, capture_output=True, text=True)

                # Nothing staged? Don't create empty commits.
                staged = subprocess.run(
                    ["git", "diff", "--cached", "--quiet"],
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    check=False,
                ).returncode != 0
                if not staged:
                    commit_action = "noop"
                    commit_rc = 0
                elif head_after_agent != head_before and cfg.git.amend_if_needed:
                    c_cp = subprocess.run(
                        ["git", "commit", "--amend", "--no-edit"],
                        cwd=str(project_root),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    commit_action = "amend"
                else:
                    title = (task.title if task is not None else "no-task").strip()
                    msg = cfg.git.commit_message_template.format(story_id=story_id or "-", title=title)
                    msg = msg.strip() or f"ralph: {story_id or '-'}"
                    c_cp = subprocess.run(
                        ["git", "commit", "-m", msg],
                        cwd=str(project_root),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    commit_action = "commit"
                if commit_action not in {"noop"}:
                    commit_rc = int(c_cp.returncode)
                    commit_out = c_cp.stdout or ""
                    commit_err = c_cp.stderr or ""
            except Exception as e:
                commit_action = "error"
                commit_rc = 1
                commit_err = str(e)

    try:
        done_after, total_after = tracker.counts()
    except Exception:
        done_after, total_after = done_before, total_before

    head_after = git_head(project_root)
    repo_clean = git_is_clean(project_root)
    done_delta = (done_after > done_before) and (total_after >= done_before)
    progress_made = done_delta or (head_after != head_before) or (not repo_clean)

    combined_output = (cp.stdout or "") + "\n" + (cp.stderr or "")
    exit_signal_raw = parse_exit_signal(combined_output)
    exit_signal = exit_signal_raw

    # Enforce exit constraints at orchestrator level.
    try:
        tracker_done = tracker.all_done()
    except Exception:
        tracker_done = False

    # Beads has no reliable "all done" signal; allow exit if the agent says so.
    allow_exit_without_all_done = (tracker.kind == "beads")

    if exit_signal is True and (not tracker_done) and (not allow_exit_without_all_done):
        exit_signal = False
    if exit_signal is True and not repo_clean:
        exit_signal = False
    if exit_signal is True and gates_ok is False:
        exit_signal = False
    if exit_signal is True and judge_ok is False:
        exit_signal = False

    # Persist log
    judge_section = "(llm_judge: not run)\n"
    if judge_cfg.enabled:
        if judge_result is None:
            judge_section = f"llm_judge_enabled: true\nllm_judge_agent: {judge_cfg.agent}\nllm_judge_ran: false\n"
        else:
            judge_section = (
                f"llm_judge_enabled: true\n"
                f"llm_judge_agent: {judge_result.agent}\n"
                f"llm_judge_ran: true\n"
                f"llm_judge_duration_seconds: {judge_result.duration_seconds:.2f}\n"
                f"llm_judge_return_code: {judge_result.return_code}\n"
                f"llm_judge_signal_raw: {judge_result.judge_signal_raw}\n"
                f"llm_judge_signal_effective: {judge_result.judge_signal_effective}\n"
            )
            if (judge_result.stdout or "").strip():
                judge_section += "--- judge stdout ---\n" + judge_result.stdout.rstrip() + "\n"
            if (judge_result.stderr or "").strip():
                judge_section += "--- judge stderr ---\n" + judge_result.stderr.rstrip() + "\n"

    stdin_flag = "true" if stdin_text is not None else "false"
    log_path.write_text(
        f"# ralph-gold log\n"
        f"timestamp_utc: {ts}\n"
        f"iteration: {iteration}\n"
        f"agent: {agent}\n"
        f"branch: {branch_label}\n"
        f"story_id: {story_id}\n"
        f"tracker_error: {task_err}\n"
        f"cmd: {json.dumps(argv)}\n"
        f"stdin_prompt: {stdin_flag}\n"
        f"timeout_seconds: {timeout}\n"
        f"timed_out: {str(timed_out).lower()}\n"
        f"duration_seconds: {duration_s:.2f}\n"
        f"return_code: {cp.returncode}\n"
        f"repo_clean: {str(repo_clean).lower()}\n"
        f"exit_signal_raw: {exit_signal_raw}\n"
        f"exit_signal_effective: {exit_signal}\n"
        f"commit_action: {commit_action}\n"
        f"commit_return_code: {commit_rc}\n"
        f"\n--- stdout ---\n{cp.stdout or ''}\n"
        f"\n--- stderr ---\n{cp.stderr or ''}\n"
        f"\n--- gates ---\n{_format_gate_results(gates_ok, gate_results)}"
        f"\n--- llm_judge ---\n{judge_section}"
        f"\n--- git_commit ---\n{commit_out}\n{commit_err}\n",
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
            "branch": branch_label,
            "story_id": story_id,
            "duration_seconds": round(duration_s, 2),
            "return_code": int(cp.returncode),
            "exit_signal_raw": exit_signal_raw,
            "exit_signal_effective": exit_signal,
            "repo_clean": bool(repo_clean),
            "gates_ok": gates_ok,
            "judge_ok": judge_ok,
            "judge_enabled": bool(judge_cfg.enabled),
            "judge_agent": str(judge_cfg.agent),
            "judge_ran": bool(judge_result is not None),
            "judge_return_code": (judge_result.return_code if judge_result is not None else None),
            "judge_duration_seconds": (round(judge_result.duration_seconds, 2) if judge_result is not None else None),
            "judge_signal_raw": (judge_result.judge_signal_raw if judge_result is not None else None),
            "judge_signal_effective": (judge_result.judge_signal_effective if judge_result is not None else None),
            "timed_out": bool(timed_out),
            "commit_action": commit_action,
            "commit_return_code": commit_rc,
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
    state["history"] = history[-200:]
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
        judge_ok=judge_ok,
    )


def run_loop(
    project_root: Path,
    agent: str,
    max_iterations: Optional[int] = None,
    cfg: Optional[Config] = None,
) -> List[IterationResult]:
    cfg = cfg or load_config(project_root)
    ensure_git_repo(project_root)

    state_dir = project_root / ".ralph"
    state_dir.mkdir(exist_ok=True)
    state_path = state_dir / "state.json"
    state = load_state(state_path)
    state["noProgressStreak"] = 0
    save_state(state_path, state)

    tracker = make_tracker(project_root, cfg)
    allow_exit_without_all_done = (tracker.kind == "beads")

    results: List[IterationResult] = []
    limit = max_iterations if max_iterations is not None else cfg.loop.max_iterations
    start_iter = next_iteration_number(project_root)

    for offset in range(limit):
        i = start_iter + offset
        res = run_iteration(project_root, agent=agent, cfg=cfg, iteration=i)
        results.append(res)

        try:
            done = tracker.all_done()
        except Exception:
            done = False

        if res.no_progress_streak >= cfg.loop.no_progress_limit:
            break

        if (done or allow_exit_without_all_done) and res.exit_signal is True:
            break

        if cfg.loop.sleep_seconds_between_iters > 0:
            time.sleep(cfg.loop.sleep_seconds_between_iters)

    return results
