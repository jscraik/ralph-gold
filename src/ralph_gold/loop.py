# -*- coding: utf-8 -*-
from __future__ import annotations

import fnmatch
import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .adaptive_timeout import calculate_adaptive_timeout
from .agents import build_agent_invocation, get_runner_config
from .atomic_file import atomic_write_json
from .authorization import AuthorizationError, EnforcementMode, load_authorization_checker
from .config import Config, LoopModeConfig, RunnerConfig, load_config
from .context_manager import check_context_health, load_progress_window
from .evidence import EvidenceReceipt, extract_evidence
from .prd import SelectedTask, select_task_by_id, task_status_by_id
from .receipts import CommandReceipt, NoFilesWrittenReceipt, hash_text, iso_utc, truncate_text, write_receipt
from .repoprompt import RepoPromptError, build_context_pack, run_review
from .spec_loader import load_specs_with_limits, SpecLoadResult
from .state_validation import validate_state_against_prd
from .subprocess_helper import (
    SubprocessResult,
    run_subprocess,
    run_subprocess_live,
)
from .trackers import make_tracker

logger = logging.getLogger(__name__)

EXIT_RE = re.compile(r"EXIT_SIGNAL:\s*(true|false)\s*$", re.IGNORECASE | re.MULTILINE)
JUDGE_RE = re.compile(r"JUDGE_SIGNAL:\s*(true|false)\s*$", re.IGNORECASE | re.MULTILINE)
SHIP_TOKEN = "SHIP"
BLOCK_TOKEN = "BLOCK"


def _coerce_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


@dataclass
class GateResult:
    cmd: str
    return_code: int
    duration_seconds: float
    stdout: str
    stderr: str
    is_precommit_hook: bool = False


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
    judge_ok: Optional[bool] = None
    review_ok: Optional[bool] = None
    blocked: bool = False
    attempt_id: Optional[str] = None
    receipts_dir: Optional[str] = None
    context_dir: Optional[str] = None
    task_title: Optional[str] = None
    evidence_count: int = 0  # Number of evidence citations extracted
    target_task_id: Optional[str] = None
    target_status: Optional[str] = None
    target_failure_reason: Optional[str] = None
    targeting_policy: Optional[str] = None


@dataclass
class DryRunResult:
    """Result of a dry-run simulation."""

    tasks_to_execute: List[str]
    gates_to_run: List[str]
    estimated_duration_seconds: float
    estimated_cost: float
    config_valid: bool
    issues: List[str]
    total_tasks: int
    completed_tasks: int
    resolved_mode: Dict[str, Any]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_loop_mode(cfg: Config) -> Tuple[Config, Dict[str, Any]]:
    mode_name = (cfg.loop.mode or "speed").strip().lower() or "speed"
    mode_cfg = cfg.loop.modes.get(mode_name) if cfg.loop.modes else None
    if mode_cfg is None:
        mode_cfg = LoopModeConfig()

    resolved_settings: Dict[str, Any] = {
        "max_iterations": cfg.loop.max_iterations,
        "no_progress_limit": cfg.loop.no_progress_limit,
        "rate_limit_per_hour": cfg.loop.rate_limit_per_hour,
        "sleep_seconds_between_iters": cfg.loop.sleep_seconds_between_iters,
        "runner_timeout_seconds": cfg.loop.runner_timeout_seconds,
        "max_attempts_per_task": cfg.loop.max_attempts_per_task,
        "skip_blocked_tasks": cfg.loop.skip_blocked_tasks,
    }

    overrides = {
        "max_iterations": mode_cfg.max_iterations,
        "no_progress_limit": mode_cfg.no_progress_limit,
        "rate_limit_per_hour": mode_cfg.rate_limit_per_hour,
        "sleep_seconds_between_iters": mode_cfg.sleep_seconds_between_iters,
        "runner_timeout_seconds": mode_cfg.runner_timeout_seconds,
        "max_attempts_per_task": mode_cfg.max_attempts_per_task,
        "skip_blocked_tasks": mode_cfg.skip_blocked_tasks,
    }

    for key, value in overrides.items():
        if value is not None:
            resolved_settings[key] = value

    resolved_loop = replace(cfg.loop, **resolved_settings)
    resolved_cfg = replace(cfg, loop=resolved_loop)
    resolved_mode = {
        "name": mode_name,
        "settings": dict(resolved_settings),
    }
    return resolved_cfg, resolved_mode


def ensure_git_repo(project_root: Path) -> None:
    """Verify we're inside a git repository.

    Raises:
        RuntimeError: If not in a git repository
    """
    try:
        run_subprocess(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=project_root,
            check=True,
        )
    except RuntimeError as e:
        raise RuntimeError(
            "This tool must be run inside a git repository (git init)."
        ) from e


def git_head(project_root: Path) -> str:
    """Get the current git HEAD commit hash.

    Returns empty string if no commits yet.
    """
    result = run_subprocess(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=project_root,
        check=False,
    )
    if result.failed:
        return ""
    return result.stdout.strip()


def git_current_branch(project_root: Path) -> str:
    """Get the current git branch name."""
    result = run_subprocess(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=project_root,
        check=True,
    )
    return result.stdout.strip()


def git_branch_exists(project_root: Path, branch: str) -> bool:
    """Check if a git branch exists."""
    result = run_subprocess(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=project_root,
        check=False,
    )
    return result.success


def git_checkout(project_root: Path, branch: str) -> None:
    """Checkout a git branch."""
    run_subprocess(
        ["git", "checkout", branch],
        cwd=project_root,
        check=True,
    )


def git_create_and_checkout(
    project_root: Path, branch: str, base_ref: Optional[str]
) -> None:
    """Create and checkout a new git branch."""
    argv = ["git", "checkout", "-b", branch]
    if base_ref:
        argv.append(base_ref)
    run_subprocess(argv, cwd=project_root, check=True)


_IGNORED_GIT_STATUS_PREFIXES = (".ralph/",)


def _git_status_lines(project_root: Path) -> List[str]:
    """Get git status lines, filtering out orchestrator noise."""
    result = run_subprocess(
        ["git", "status", "--porcelain"],
        cwd=project_root,
        check=True,
    )
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]

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
    logger = logging.getLogger(__name__)

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
        except Exception as e:
            logger.debug("Failed to parse JSON line: %s", e)
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


def _safe_task_dirname(task_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", task_id.strip()) or "unknown"


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _targeting_policy_label(
    target_task_id: Optional[str],
    allow_done_target: bool,
    allow_blocked_target: bool,
    reopen_if_needed: bool,
) -> Optional[str]:
    if not target_task_id:
        return None
    if allow_done_target or allow_blocked_target or reopen_if_needed:
        return "override"
    return "strict"


def _resolve_target_task(
    *,
    project_root: Path,
    cfg: Config,
    tracker: Any,
    target_task_id: str,
) -> Tuple[Optional[SelectedTask], str]:
    """Resolve task + status for explicit task targeting."""
    task: Optional[SelectedTask] = None
    status = "missing"

    try:
        if hasattr(tracker, "get_task_by_id"):
            task = tracker.get_task_by_id(target_task_id)
    except Exception as e:
        logger.debug("Tracker get_task_by_id failed: %s", e)

    try:
        if hasattr(tracker, "get_task_status"):
            status_candidate = str(tracker.get_task_status(target_task_id))
            if status_candidate in {"open", "done", "blocked", "missing"}:
                status = status_candidate
    except Exception as e:
        logger.debug("Tracker get_task_status failed: %s", e)

    # File-based fallback for trackers that do not support explicit lookup.
    if task is None or status == "missing":
        try:
            prd_path = (project_root / cfg.files.prd).resolve()
            if task is None:
                task = select_task_by_id(prd_path, target_task_id)
            status = task_status_by_id(prd_path, target_task_id)
        except Exception as e:
            logger.debug("PRD fallback target resolution failed: %s", e)

    return task, status


def _read_text_if_exists(path: Path, limit_chars: int = 200_000) -> str:
    try:
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > limit_chars:
            return text[:limit_chars] + "\n...<truncated>...\n"
        return text
    except OSError as e:
        return ""


def _git_status_porcelain_raw(project_root: Path) -> str:
    """Get raw git status output (unfiltered)."""
    result = run_subprocess(
        ["git", "status", "--porcelain"],
        cwd=project_root,
        check=False,
    )
    return result.stdout.strip()


def _git_diff_stat_raw(project_root: Path) -> str:
    """Get raw git diff --stat output."""
    result = run_subprocess(
        ["git", "diff", "--stat"],
        cwd=project_root,
        check=False,
    )
    return result.stdout.strip()


def _build_anchor(task: SelectedTask, project_root: Path) -> str:
    branch = git_current_branch(project_root)
    status = _git_status_porcelain_raw(project_root)
    diffstat = _git_diff_stat_raw(project_root)

    parts: List[str] = []
    parts.append("# Ralph Gold Anchor")
    parts.append("")
    parts.append(f"Task: {task.id} - {task.title}")
    parts.append("")
    if task.acceptance:
        parts.append("Acceptance criteria:")
        for a in task.acceptance:
            parts.append(f"- {a}")
        parts.append("")
    parts.append("Repo reality:")
    parts.append(f"- branch: {branch}")
    parts.append("- git status --porcelain:")
    parts.append("```\n" + (status or "<clean>") + "\n```")
    parts.append("- git diff --stat:")
    parts.append("```\n" + (diffstat or "<no diff>") + "\n```")
    parts.append("")
    parts.append("Constraints:")
    parts.append("- Work on exactly ONE task per iteration")
    parts.append("- Do not claim completion without passing gates")
    parts.append("- Prefer minimal diffs; keep repo clean")
    parts.append("")
    return "\n".join(parts)


def _now_attempt_id(iteration: int) -> str:
    ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    return f"{ts}-iter{iteration:04d}"


def _parse_review_token(output: str, required: str = SHIP_TOKEN) -> bool:
    lines = [ln.strip() for ln in (output or "").splitlines() if ln.strip()]
    if not lines:
        return False
    last = lines[-1].upper()
    return last == required.upper()


def build_prompt(
    project_root: Path,
    cfg: Config,
    task: Optional[SelectedTask],
    iteration: int,
    *,
    anchor_text: str = "",
    repoprompt_context: str = "",
) -> str:
    """Build the per-iteration prompt."""

    prompt_path = project_root / cfg.files.prompt
    base = _read_text_if_exists(prompt_path)

    agents_path = project_root / cfg.files.agents
    prd_path = project_root / cfg.files.prd
    progress_path = project_root / cfg.files.progress
    feedback_path = project_root / cfg.files.feedback
    specs_dir = project_root / cfg.files.specs_dir

    agents = _read_text_if_exists(agents_path)
    prd = _read_text_if_exists(prd_path)
    # Use sliding window for progress to prevent context overflow
    progress, entries_loaded, total_entries = load_progress_window(
        progress_path,
        max_lines=cfg.prompt.context_progress_max_lines,
        max_chars=cfg.prompt.context_progress_max_chars,
    )
    feedback = _read_text_if_exists(feedback_path)

    # Load specs with configurable limits and diagnostic warnings
    spec_result: SpecLoadResult = load_specs_with_limits(
        specs_dir,
        max_specs_files=cfg.prompt.max_specs_files,
        max_specs_chars=cfg.prompt.max_specs_chars,
        max_single_spec_chars=cfg.prompt.max_single_spec_chars,
        truncate_long_specs=cfg.prompt.truncate_long_specs,
        specs_inclusion_order=cfg.prompt.specs_inclusion_order,
    )

    # Display spec warnings to user
    if spec_result.warnings:
        logger.warning(f"Spec loading warnings: {len(spec_result.warnings)}")
        for warning in spec_result.warnings:
            logger.warning(f"  - {warning}")

    # Read spec contents
    specs: List[tuple[str, str]] = []
    for spec_name, _ in spec_result.included:
        spec_path = specs_dir / spec_name
        content = _read_text_if_exists(spec_path)
        if content:
            specs.append((spec_name, content))

    # Check context health and log warnings
    from .context_manager import ContextConfig
    context_config = ContextConfig(
        total_budget_chars=cfg.prompt.context_total_budget,
        progress_max_lines=cfg.prompt.context_progress_max_lines,
        progress_max_chars=cfg.prompt.context_progress_max_chars,
    )
    spec_size = sum(len(content) for _, content in specs)
    health = check_context_health(
        progress_size=len(progress),
        progress_entries=entries_loaded,
        progress_total=total_entries,
        spec_size=spec_size,
        config=context_config,
    )
    if health.warnings:
        logger.warning(f"Context health check: {len(health.warnings)} warnings")
        for warning in health.warnings:
            logger.warning(f"  - {warning}")
    elif entries_loaded < total_entries:
        logger.info(
            f"Progress window: {entries_loaded}/{total_entries} entries loaded "
            f"({len(progress)} chars)"
        )

    parts: List[str] = []
    if base.strip():
        parts.append(base.rstrip())
        parts.append("")
    else:
        parts.append("# Golden Ralph Loop")
        parts.append("(missing prompt file; using fallback instructions)")
        parts.append("")

    if anchor_text.strip():
        parts.append("<ANCHOR>")
        parts.append(anchor_text.strip())
        parts.append("</ANCHOR>")
        parts.append("")

    if repoprompt_context.strip():
        parts.append("<REPOPROMPT_CONTEXT_PACK>")
        parts.append(repoprompt_context.strip())
        parts.append("</REPOPROMPT_CONTEXT_PACK>")
        parts.append("")

    parts.append("## Orchestrator Addendum (auto-generated)")
    parts.append(f"Iteration: {iteration}")
    parts.append("")
    parts.append("Hard iteration constraints:")
    parts.append("- One task per iteration (one commit per iteration).")
    parts.append(
        "- Apply backpressure: run the commands in AGENTS.md and fix until they pass."
    )
    parts.append("")

    if task is not None:
        parts.append("Selected task for this iteration:")
        parts.append(f"- id: {task.id}")
        if task.title:
            parts.append(f"- title: {task.title}")
        if task.acceptance:
            parts.append("- acceptance:")
            for a in task.acceptance[:20]:
                parts.append(f"  - {a}")
        parts.append("")
        parts.append("Do not work on any other task in this iteration.")
        parts.append("")
    else:
        parts.append("No task was selected (task file may be empty or malformed).")
        parts.append("If the task file is complete, confirm and prepare to exit.")
        parts.append("")

    parts.append("<PROJECT_MEMORY>")
    if agents.strip():
        parts.append(f"## {cfg.files.agents}")
        parts.append(agents)
        parts.append("")
    if prd.strip():
        parts.append(f"## {cfg.files.prd}")
        parts.append(prd)
        parts.append("")
    if progress.strip():
        parts.append(f"## {cfg.files.progress}")
        parts.append(progress)
        parts.append("")
    if feedback.strip():
        parts.append(f"## {cfg.files.feedback}")
        parts.append(feedback)
        parts.append("")
    for name, text in specs:
        if not text.strip():
            continue
        parts.append(f"## {cfg.files.specs_dir}/{name}")
        parts.append(text)
        parts.append("")
    parts.append("</PROJECT_MEMORY>")

    parts.append("")
    parts.append("Exit protocol (required):")
    parts.append("At the very end of your output, print exactly one line:")
    parts.append("EXIT_SIGNAL: true  OR  EXIT_SIGNAL: false")
    parts.append("")
    return "\n".join(parts) + "\n"


def build_runner_invocation(
    agent: str, argv_template: List[str], prompt_text: str
) -> Tuple[List[str], Optional[str]]:
    """Build argv and optional stdin for the configured agent runner.

    This function now delegates to the agent plugin architecture.

    Key rule for Codex:
    - Prefer passing the prompt via stdin using '-' to avoid argv quoting/length issues.
      Example: `codex exec --full-auto -` (prompt read from stdin).
    """
    from .config import RunnerConfig

    # Create a temporary RunnerConfig for the plugin architecture
    temp_config = RunnerConfig(argv=argv_template)

    # Delegate to the plugin architecture
    return build_agent_invocation(agent, prompt_text, temp_config)


def load_state(state_path: Path) -> Dict[str, Any]:
    if not state_path.exists():
        return {
            "createdAt": utc_now_iso(),
            "invocations": [],  # epoch timestamps
            "noProgressStreak": 0,
            "history": [],
            "task_attempts": {},
            "blocked_tasks": {},
            "session_id": "",
            "snapshots": [],
        }
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            raise ValueError("state.json must be an object")
        state.setdefault("history", [])
        state.setdefault("invocations", [])
        state.setdefault("noProgressStreak", 0)
        state.setdefault("task_attempts", {})
        state.setdefault("blocked_tasks", {})
        state.setdefault("session_id", "")
        state.setdefault("snapshots", [])
        return state
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("Failed to load state: %s", e)
        # Return default state structure instead of empty string
        return {
            "createdAt": utc_now_iso(),
            "invocations": [],
            "noProgressStreak": 0,
            "history": [],
            "task_attempts": {},
            "blocked_tasks": {},
            "session_id": "",
            "snapshots": [],
        }


def save_state(state_path: Path, state: Dict[str, Any]) -> None:
    """Save state atomically to prevent data corruption.

    Uses atomic write operations to ensure state.json is never in a
    partially-written state, even if the process is interrupted.

    Args:
        state_path: Path to state.json file
        state: State dictionary to save
    """
    atomic_write_json(state_path, state)


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
            except (OSError, ValueError) as e:
                logger.debug("Failed to read iteration from state: %s", e)
                return 1
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
        except (ValueError, TypeError) as e:
            logger.debug("Invalid invocation timestamp: %s", e)

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
    from .subprocess_helper import check_command_available

    if check_command_available("bash"):
        return ["bash", "-lc", cmd]

    return ["sh", "-lc", cmd]


def _discover_precommit_hook(project_root: Path) -> Optional[Path]:
    """Auto-discover pre-commit hook in .husky/ or .git/hooks/."""

    # Prefer Husky (modern standard)
    husky = project_root / ".husky" / "pre-commit"
    if husky.exists() and husky.is_file():
        return husky

    # Fallback to git hooks
    git_hook = project_root / ".git" / "hooks" / "pre-commit"
    if git_hook.exists() and git_hook.is_file():
        return git_hook

    return None


def _run_gate_command(
    project_root: Path, cmd: str, is_precommit_hook: bool = False
) -> GateResult:
    """Run a single gate command in a predictable shell environment."""

    start = time.time()

    if is_precommit_hook:
        # Pre-commit hooks need to be executed directly with proper permissions
        hook_path = Path(cmd)
        if hook_path.is_absolute():
            argv = [str(hook_path)]
        else:
            argv = [str(project_root / cmd)]

        # Ensure hook is executable
        try:
            hook_file = Path(argv[0])
            if hook_file.exists():
                hook_file.chmod(hook_file.stat().st_mode | 0o111)
        except OSError as e:
            logger.debug("Failed to make hook executable: %s", e)

    result = run_subprocess(
        _gate_shell_argv(cmd),
        cwd=project_root,
    )

    return GateResult(
        cmd=cmd,
        return_code=result.returncode,
        duration_seconds=time.time() - start,
        stdout=result.stdout,
        stderr=result.stderr,
        is_precommit_hook=is_precommit_hook,
    )


def _get_changed_files(project_root: Path) -> List[Path]:
    """Get list of changed files from git diff.

    Uses git diff --name-only to get changed files.

    Args:
        project_root: Project root directory

    Returns:
        List of changed file paths (absolute paths)
    """
    result = run_subprocess(
        ["git", "diff", "--name-only"],
        cwd=project_root,
        check=False,
    )
    changed: List[Path] = []
    for line in result.stdout.strip().split('\n'):
        if line:
            changed.append(project_root / line)
    return changed


def _should_skip_gates(
    changed_files: List[Path], skip_patterns: List[str], project_root: Path
) -> bool:
    """Check if gates should be skipped based on changed files.

    Gates are skipped only if ALL changed files match at least one
    of the skip patterns. If any file doesn't match, gates must run.

    Args:
        changed_files: List of changed file paths (absolute paths)
        skip_patterns: List of glob patterns (e.g., ["**/*.md", "**/*.toml"])
        project_root: Project root directory (for path normalization)

    Returns:
        True if gates should be skipped, False otherwise
    """
    if not skip_patterns:
        return False

    if not changed_files:
        return False

    # Check if ALL changed files match skip patterns
    # If ANY file doesn't match, gates must run
    for file_path in changed_files:
        # Convert absolute path to relative for pattern matching
        try:
            rel_path = file_path.relative_to(project_root)
        except ValueError:
            # File is outside project root, don't skip
            return False

        # Convert to string for pattern matching
        rel_path_str = str(rel_path)

        # Check if the file matches any of the skip patterns
        matched = False
        for pattern in skip_patterns:
            # Handle ** patterns by converting to fnmatch-compatible pattern
            # **/*.md -> *.md (for any file) or **/*.md (for subdirectories)
            if "**" in pattern:
                # For recursive patterns, check both the full path and filename
                simple_pattern = pattern.replace("**/", "")
                if (fnmatch.fnmatchcase(rel_path_str, simple_pattern) or
                    fnmatch.fnmatchcase(rel_path_str, pattern) or
                    fnmatch.fnmatchcase(rel_path.name, simple_pattern)):
                    matched = True
                    break
            elif fnmatch.fnmatchcase(rel_path_str, pattern):
                matched = True
                break

        if not matched:
            return False  # At least one file doesn't match skip patterns

    return True  # All files match skip patterns


def run_gates(
    project_root: Path, commands: List[str], cfg: GatesConfig
) -> Tuple[bool, List[GateResult]]:
    """Run all configured gates with fail-fast and pre-commit hook support."""

    # Smart gate filtering: skip gates when only matching files change
    if cfg.smart.enabled and cfg.smart.skip_gates_for:
        changed_files = _get_changed_files(project_root)
        if changed_files and _should_skip_gates(
            changed_files, cfg.smart.skip_gates_for, project_root
        ):
            # All changed files match skip patterns - skip all gates
            return True, []

    all_commands = list(commands)

    # Optional: prepend prek if enabled and config exists.
    if cfg.prek.enabled:
        if (project_root / ".pre-commit-config.yaml").exists() or (
            project_root / ".pre-commit-config.yml"
        ).exists():
            if cfg.prek.argv:
                all_commands.insert(0, " ".join([str(x) for x in cfg.prek.argv]))

    # Auto-discover and prepend pre-commit hook if enabled
    if cfg.precommit_hook:
        hook_path = _discover_precommit_hook(project_root)
        if hook_path:
            # Insert at beginning for fail-fast (hooks are typically fast)
            all_commands.insert(0, str(hook_path))

    if not all_commands:
        return True, []

    results: List[GateResult] = []
    ok = True

    for cmd in all_commands:
        # Check if this is the pre-commit hook
        is_hook = cfg.precommit_hook and (
            cmd.endswith("pre-commit") or "/.husky/" in cmd or "/.git/hooks/" in cmd
        )

        res = _run_gate_command(project_root, cmd, is_precommit_hook=is_hook)
        results.append(res)

        if res.return_code != 0:
            ok = False
            if cfg.fail_fast:
                break

    return ok, results


def dry_run_loop(
    project_root: Path,
    agent: str,
    max_iterations: int,
    cfg: Optional[Config] = None,
) -> DryRunResult:
    """Simulate loop execution without running agents.

    This function validates configuration, shows what tasks would be selected,
    lists gates that would run, and estimates duration based on historical data.
    No agents are executed and no files are modified.

    Args:
        project_root: Project root directory
        agent: Agent/runner to use (for validation)
        max_iterations: Maximum iterations to simulate
        cfg: Configuration (loaded if not provided)

    Returns:
        DryRunResult with simulation details
    """
    cfg = cfg or load_config(project_root)
    cfg, resolved_mode = _resolve_loop_mode(cfg)
    issues: List[str] = []

    # Validate git repository
    try:
        ensure_git_repo(project_root)
    except RuntimeError as e:
        issues.append(f"Git repository error: {e}")

    # Validate agent/runner configuration
    try:
        _get_runner(cfg, agent)
    except RuntimeError as e:
        issues.append(f"Agent configuration error: {e}")

    # Load tracker and get task information
    tasks_to_execute: List[str] = []
    total_tasks = 0
    completed_tasks = 0

    try:
        tracker = make_tracker(project_root, cfg)

        # Get task counts
        try:
            completed_tasks, total_tasks = tracker.counts()
        except Exception as e:
            issues.append(f"Failed to get task counts: {e}")

        # Simulate task selection for max_iterations
        state_path = project_root / ".ralph" / "state.json"
        state = load_state(state_path)

        blocked_ids: set[str] = set()
        if cfg.loop.skip_blocked_tasks:
            blocked_raw = state.get("blocked_tasks", {}) or {}
            if isinstance(blocked_raw, dict):
                blocked_ids = {str(k) for k in blocked_raw.keys()}

        # Try to select tasks that would be executed
        for i in range(min(max_iterations, total_tasks - completed_tasks)):
            try:
                if hasattr(tracker, "select_next_task"):
                    task = tracker.select_next_task(exclude_ids=blocked_ids)
                elif hasattr(tracker, "claim_next_task"):
                    # For dry-run, we don't actually claim, just peek
                    task = tracker.claim_next_task()
                else:
                    break

                if task is not None:
                    task_label = f"{task.id}: {task.title}" if task.title else task.id
                    tasks_to_execute.append(task_label)
                    # Simulate blocking this task for next iteration
                    blocked_ids.add(task.id)
                else:
                    break
            except Exception as e:
                issues.append(f"Task selection error (iteration {i + 1}): {e}")
                break

    except Exception as e:
        issues.append(f"Tracker initialization error: {e}")

    # Collect gates that would run
    gates_to_run: List[str] = []

    if cfg.gates.commands:
        gates_to_run.extend(cfg.gates.commands)

    # Check for pre-commit hook
    if cfg.gates.precommit_hook:
        hook_path = _discover_precommit_hook(project_root)
        if hook_path:
            gates_to_run.insert(0, f"[pre-commit hook] {hook_path}")

    # Check for prek
    if cfg.gates.prek.enabled:
        if (project_root / ".pre-commit-config.yaml").exists() or (
            project_root / ".pre-commit-config.yml"
        ).exists():
            if cfg.gates.prek.argv:
                prek_cmd = " ".join([str(x) for x in cfg.gates.prek.argv])
                gates_to_run.insert(0, f"[prek] {prek_cmd}")

    # Estimate duration based on historical data
    estimated_duration = 0.0
    try:
        state_path = project_root / ".ralph" / "state.json"
        state = load_state(state_path)
        history = state.get("history", [])

        if isinstance(history, list) and history:
            # Calculate average duration from recent history
            durations = []
            for entry in history[-20:]:  # Use last 20 iterations
                if isinstance(entry, dict):
                    duration = entry.get("duration_seconds", 0)
                    if isinstance(duration, (int, float)) and duration > 0:
                        durations.append(float(duration))

            if durations:
                avg_duration = sum(durations) / len(durations)
                estimated_duration = avg_duration * len(tasks_to_execute)
            else:
                # No historical data, use rough estimate
                estimated_duration = 60.0 * len(tasks_to_execute)  # 60 seconds per task
        else:
            # No history, use rough estimate
            estimated_duration = 60.0 * len(tasks_to_execute)
    except Exception as e:
        issues.append(f"Failed to estimate duration: {e}")
        estimated_duration = 60.0 * len(tasks_to_execute)

    # Validate configuration files exist
    if not (project_root / cfg.files.prd).exists():
        issues.append(f"PRD file not found: {cfg.files.prd}")

    config_valid = len(issues) == 0

    return DryRunResult(
        tasks_to_execute=tasks_to_execute,
        gates_to_run=gates_to_run,
        estimated_duration_seconds=estimated_duration,
        estimated_cost=0.0,  # Future: implement cost estimation
        config_valid=config_valid,
        issues=issues,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        resolved_mode=resolved_mode,
    )


def _truncate_output(text: str, max_lines: int) -> str:
    """Truncate output to max_lines, keeping first and last portions."""
    if max_lines <= 0:
        return text

    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text

    # Keep first 60% and last 40% of allowed lines
    head_count = int(max_lines * 0.6)
    tail_count = max_lines - head_count

    head = lines[:head_count]
    tail = lines[-tail_count:] if tail_count > 0 else []

    truncated = head + [f"... ({len(lines) - max_lines} lines truncated) ..."] + tail
    return "\n".join(truncated)


def _format_gate_results(
    gates_ok: Optional[bool],
    results: List[GateResult],
    output_mode: str = "summary",
    max_lines: int = 50,
) -> str:
    """Format gate results with configurable output verbosity."""

    if gates_ok is None:
        return "(gates: not configured)"
    if not results:
        return "(gates: configured but empty)"

    status = "PASS" if gates_ok else "FAIL"
    lines: List[str] = [f"gates_overall: {status}"]

    for i, r in enumerate(results, start=1):
        lines.append("")
        hook_label = " [pre-commit-hook]" if r.is_precommit_hook else ""
        lines.append(f"gate_{i}_cmd: {r.cmd}{hook_label}")
        lines.append(f"gate_{i}_return_code: {r.return_code}")
        lines.append(f"gate_{i}_duration_seconds: {r.duration_seconds:.2f}")

        # Output mode logic
        if output_mode == "errors_only":
            # Only show output for failed gates
            if r.return_code != 0:
                if r.stdout.strip():
                    lines.append("--- gate stdout (errors only) ---")
                    lines.append(_truncate_output(r.stdout.rstrip(), max_lines))
                if r.stderr.strip():
                    lines.append("--- gate stderr (errors only) ---")
                    lines.append(_truncate_output(r.stderr.rstrip(), max_lines))

        elif output_mode == "summary":
            # Show truncated output for all gates
            if r.stdout.strip():
                lines.append("--- gate stdout (summary) ---")
                lines.append(_truncate_output(r.stdout.rstrip(), max_lines))
            if r.stderr.strip():
                lines.append("--- gate stderr (summary) ---")
                lines.append(_truncate_output(r.stderr.rstrip(), max_lines))

        else:  # "full"
            # Show complete output
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
    """Capture git command output, including stderr in the result."""
    result = run_subprocess(argv, cwd=project_root)
    if result.stderr.strip():
        return result.stdout + "\n" + result.stderr
    return result.stdout


def _diff_for_judge(
    project_root: Path, head_before: str, head_after: str, max_chars: int
) -> str:
    """Collect a reasonably informative diff payload for the judge."""

    parts: List[str] = []
    try:
        status = _git_capture(project_root, ["git", "status", "--porcelain"]).strip()
        parts.append("# git status --porcelain\n" + (status or "(clean)"))
    except OSError as e:
        logger.debug("File read failed: %s", e)

    combined = "\n\n".join(parts).strip() + "\n"
    return combined


def build_judge_prompt(
    project_root: Path,
    cfg: Config,
    task: SelectedTask,
    diff_text: str,
    gates_ok: Optional[bool],
    gate_results: List[GateResult],
) -> str:
    """Build the LLM-as-judge prompt."""

    prompt_path = project_root / cfg.gates.llm_judge.prompt
    base = ""
    if prompt_path.exists():
        try:
            base = prompt_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.debug("File read failed: %s", e)

    lines: List[str] = []
    if base.strip():
        lines.append(base.rstrip())
        lines.append("(missing PROMPT_judge.md; using fallback instructions)")
        lines.append("")
        lines.append("You are a strict reviewer.")
        lines.append(
            "Return JUDGE_SIGNAL: true only when the task is complete and correct."
        )
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
    lines.append(
        "- If anything important is missing/incorrect, return JUDGE_SIGNAL: false."
    )
    lines.append(
        "- If requirements are satisfied and implementation quality is acceptable, return JUDGE_SIGNAL: true."
    )
    lines.append("")
    lines.append("Output format (required):")
    lines.append("- Provide a short rationale (bullets ok).")
    lines.append("- At the very end, print exactly one line:")
    lines.append("JUDGE_SIGNAL: true  OR  JUDGE_SIGNAL: false")
    lines.append("")
    return "\n".join(lines) + "\n"


def _get_runner(cfg: Config, agent: str) -> RunnerConfig:
    """Get the runner configuration for a given agent.

    This function now delegates to the agent plugin architecture.
    """
    return get_runner_config(cfg, agent)


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


def _ensure_feature_branch(
    project_root: Path, cfg: Config, tracker_branch: Optional[str]
) -> Optional[str]:
    """Checkout/create a feature branch based on PRD metadata."""

    strategy = (cfg.git.branch_strategy or "none").strip().lower()
    if strategy in {"none", "off", "false", "0"}:
        return None
    if strategy != "per_prd":
        return None

    # Resolve branch name.
    branch = _normalize_git_branch_name(tracker_branch or "")
    if not branch:
        branch = _normalize_git_branch_name(
            f"{cfg.git.branch_prefix}{_slugify(project_root.name)}"
        )
    if not branch:
        return None

    try:
        current = git_current_branch(project_root)
    except Exception as e:
        logging.getLogger(__name__).debug("Failed to get current branch: %s", e)
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
    target_task_id: Optional[str] = None,
    allow_done_target: bool = False,
    allow_blocked_target: bool = False,
    reopen_if_needed: bool = False,
    stream: bool = False,
) -> IterationResult:
    cfg = cfg or load_config(project_root)
    cfg, resolved_mode = _resolve_loop_mode(cfg)
    ensure_git_repo(project_root)
    iter_started = time.time()

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
    allow_exit_without_all_done = tracker.kind == "beads"
    branch = _ensure_feature_branch(
        project_root, cfg, tracker_branch=tracker.branch_name()
    )

    # Capture done count before claiming a task (used for no-progress detection).
    try:
        done_before, total_before = tracker.counts()
    except OSError as e:
        logger.debug("File read failed: %s", e)

    blocked_ids: set[str] = set()
    if cfg.loop.skip_blocked_tasks:
        blocked_raw = state.get("blocked_tasks", {}) or {}
        if isinstance(blocked_raw, dict):
            blocked_ids = {str(k) for k in blocked_raw.keys()}

    requested_target = (
        str(target_task_id).strip() if target_task_id is not None else ""
    )
    target_task_id_effective = requested_target or None
    target_status: Optional[str] = None
    target_failure_reason: Optional[str] = None
    targeting_policy = _targeting_policy_label(
        target_task_id=target_task_id_effective,
        allow_done_target=allow_done_target,
        allow_blocked_target=allow_blocked_target,
        reopen_if_needed=reopen_if_needed,
    )

    task: Optional[SelectedTask]
    task_err = ""
    try:
        if task_override is not None:
            task = task_override
            if target_task_id_effective and task.id == target_task_id_effective:
                target_status = "open"
        elif target_task_id_effective is not None:
            task, target_status = _resolve_target_task(
                project_root=project_root,
                cfg=cfg,
                tracker=tracker,
                target_task_id=target_task_id_effective,
            )

            if reopen_if_needed and target_status in {"done", "blocked"}:
                reopened = False
                try:
                    reopened = bool(tracker.force_task_open(target_task_id_effective))
                except Exception as e:
                    logger.debug("Target reopen failed: %s", e)
                    reopened = False

                audit = state.get("target_reopen_audit", [])
                if not isinstance(audit, list):
                    audit = []
                audit.append(
                    {
                        "ts": utc_now_iso(),
                        "iteration": iteration,
                        "task_id": target_task_id_effective,
                        "result": "success" if reopened else "failure",
                        "reason": "reopen_target",
                    }
                )
                state["target_reopen_audit"] = audit[-200:]

                task, target_status = _resolve_target_task(
                    project_root=project_root,
                    cfg=cfg,
                    tracker=tracker,
                    target_task_id=target_task_id_effective,
                )

            if target_status == "missing":
                target_failure_reason = "missing_target"
            elif target_status == "done" and not allow_done_target:
                target_failure_reason = "target_done"
            elif target_status == "blocked" and not allow_blocked_target:
                target_failure_reason = "target_blocked"
            elif task is None:
                target_failure_reason = "target_resolution_error"

            if target_failure_reason is not None:
                ts_target = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                target_log = logs_dir / f"{ts_target}-iter{iteration:04d}-{agent}.log"
                target_log.write_text(
                    (
                        f"iteration: {iteration}\n"
                        f"agent: {agent}\n"
                        f"target_task_id: {target_task_id_effective}\n"
                        f"target_status: {target_status}\n"
                        f"target_failure_reason: {target_failure_reason}\n"
                        f"targeting_policy: {targeting_policy}\n"
                    ),
                    encoding="utf-8",
                )

                invocations = state.get("invocations", [])
                if not isinstance(invocations, list):
                    invocations = []
                invocations.append(time.time())
                state["invocations"] = invocations
                state["noProgressStreak"] = int(state.get("noProgressStreak", 0)) + 1

                history = state.get("history", [])
                if not isinstance(history, list):
                    history = []
                history.append(
                    {
                        "ts": utc_now_iso(),
                        "iteration": iteration,
                        "agent": agent,
                        "loop_mode": resolved_mode,
                        "mode": resolved_mode,
                        "story_id": target_task_id_effective,
                        "duration_seconds": round(time.time() - iter_started, 2),
                        "gates_ok": None,
                        "judge_ok": None,
                        "review_ok": None,
                        "blocked": False,
                        "return_code": 2,
                        "target_task_id": target_task_id_effective,
                        "target_status": target_status,
                        "target_failure_reason": target_failure_reason,
                        "targeting_policy": targeting_policy,
                        "log": str(target_log.name),
                    }
                )
                state["history"] = history[-200:]
                save_state(state_path, state)

                return IterationResult(
                    iteration=iteration,
                    agent=agent,
                    story_id=target_task_id_effective,
                    exit_signal=True,
                    return_code=2,
                    log_path=target_log,
                    progress_made=False,
                    no_progress_streak=int(state.get("noProgressStreak", 0)),
                    gates_ok=None,
                    repo_clean=True,
                    judge_ok=None,
                    target_task_id=target_task_id_effective,
                    target_status=target_status,
                    target_failure_reason=target_failure_reason,
                    targeting_policy=targeting_policy,
                )
        else:
            # Try to claim a task, looping around blocked ones
            max_attempts = 10  # Prevent infinite loops
            for attempt in range(max_attempts):
                try:
                    if hasattr(tracker, "claim_next_task"):
                        task = tracker.claim_next_task()
                    elif hasattr(tracker, "select_next_task"):
                        task = tracker.select_next_task(exclude_ids=blocked_ids)
                    else:
                        task = tracker.claim_next_task()

                    # If no task or task is not blocked, we're done
                    if task is None:
                        break

                    # Check if task is blocked
                    if task.id not in blocked_ids:
                        break

                    # Task is blocked - force it open and retry
                    try:
                        tracker.force_task_open(task.id)
                        # Remove from blocked set
                        blocked_ids.discard(task.id)
                        # Try to claim again in next iteration
                        task = None
                        continue
                    except (OSError, RuntimeError) as e:
                        logger.debug("Failed to force task open: %s", e)
                        task = None
                        break
                except (OSError, ValueError, RuntimeError) as e:
                    task = None
                    task_err = str(e)
                    break

    except (OSError, ValueError, RuntimeError) as e:
        task = None
        task_err = str(e)

    story_id: Optional[str] = task.id if task is not None else None
    task_title = task.title if task is not None else "No remaining tasks"

    # CRITICAL: Exit cleanly when no task is available
    if task is None:
        # Check why no task was selected
        try:
            all_done = tracker.all_done()
            done_count, total_count = tracker.counts()

            if all_done or done_count == total_count:
                # All tasks completed successfully
                from .output import print_output

                print_output("All tasks completed successfully", level="normal")
                return IterationResult(
                    iteration=iteration,
                    agent=agent,
                    story_id=None,
                    exit_signal=True,
                    return_code=0,  # Success
                    log_path=None,
                    progress_made=False,
                    no_progress_streak=0,
                    gates_ok=None,
                    repo_clean=True,
                    judge_ok=None,
                )
            elif total_count > done_count:
                # Tasks remain but all are blocked
                from .output import print_output

                print_output(
                    f"All remaining tasks are blocked ({total_count - done_count} blocked)",
                    level="error",
                )
                return IterationResult(
                    iteration=iteration,
                    agent=agent,
                    story_id=None,
                    exit_signal=True,
                    return_code=1,  # Failure - blocked tasks
                    log_path=None,
                    progress_made=False,
                    no_progress_streak=0,
                    gates_ok=None,
                    repo_clean=True,
                    judge_ok=None,
                )
            else:
                # No task but unclear why (configuration error)
                from .output import print_output

                print_output(
                    "No task selected but tasks may remain (check PRD)", level="error"
                )
                return IterationResult(
                    iteration=iteration,
                    agent=agent,
                    story_id=None,
                    exit_signal=True,
                    return_code=2,  # Configuration error
                    log_path=None,
                    progress_made=False,
                    no_progress_streak=0,
                    gates_ok=None,
                    repo_clean=True,
                    judge_ok=None,
                )
        except Exception as e:
            # Tracker error - exit with error
            from .output import print_output

            print_output(f"Tracker error when checking task status: {e}", level="error")
            return IterationResult(
                iteration=iteration,
                agent=agent,
                story_id=None,
                exit_signal=True,
                return_code=2,  # Configuration/tracker error
                log_path=None,
                progress_made=False,
                no_progress_streak=0,
                gates_ok=None,
                repo_clean=True,
                judge_ok=None,
            )

    attempt_id = _now_attempt_id(iteration)
    task_dirname = _safe_task_dirname(story_id or "(none)")
    attempts_dir = _ensure_dir(state_dir / "attempts" / task_dirname)
    receipts_dir = _ensure_dir(state_dir / "receipts" / task_dirname / attempt_id)
    context_dir = _ensure_dir(state_dir / "context" / task_dirname / attempt_id)
    attempt_record_path = attempts_dir / f"{attempt_id}.json"

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = logs_dir / f"{ts}-iter{iteration:04d}-{agent}.log"

    anchor_text = ""
    anchor_path: Optional[Path] = None
    if task is not None:
        anchor_text = _build_anchor(task, project_root)
        anchor_path = context_dir / "ANCHOR.md"

        # Authorization check (configurable enforcement mode)
        # Config may store enforcement_mode as an enum already.
        raw_mode = cfg.authorization.enforcement_mode
        if isinstance(raw_mode, EnforcementMode):
            enforcement_mode = raw_mode
        else:
            enforcement_mode = EnforcementMode(str(raw_mode).lower())
        auth_checker = load_authorization_checker(
            project_root,
            cfg.authorization.permissions_file,
            enforcement_mode=enforcement_mode,
        )
        runner_cfg = _get_runner(cfg, agent)

        try:
            allowed, reason = auth_checker.check_write_permission(anchor_path, runner_cfg.argv)
            if not allowed:
                # This branch is taken in warn mode when permission denied
                logger.warning(f"Authorization check failed for {anchor_path}: {reason}")
        except AuthorizationError as e:
            # This is raised in block mode when permission denied
            logger.error(f"Authorization blocked: {e}")
            # In block mode, we don't write the anchor file
            # Fall through to other operations but skip anchor write
            anchor_path = None  # Mark as None to skip write below
            # Optionally: could skip more operations or abort entirely

        # Only write anchor if authorization passed (or wasn't blocked)
        if anchor_path is not None:
            anchor_path.write_text(anchor_text + "\n", encoding="utf-8")
            write_receipt(
                receipts_dir / "anchor.json",
            CommandReceipt(
                name="anchor",
                argv=["git", "status", "--porcelain", "&&", "git", "diff", "--stat"],
                returncode=0,
                started_at=iso_utc(),
                ended_at=iso_utc(),
                duration_seconds=0.0,
                stdout_path=str(anchor_path.relative_to(project_root)),
            ),
        )

    rp_context_text = ""
    if cfg.repoprompt.enabled and task is not None:
        out_path = context_dir / "repoprompt_prompt.md"
        try:
            rp_run, rp_instructions = build_context_pack(
                cfg=cfg.repoprompt,
                task_id=task.id,
                task_title=task.title,
                acceptance=task.acceptance,
                out_path=out_path,
                cwd=project_root,
                anchor_path=anchor_path,
            )
            rp_context_text = _read_text_if_exists(out_path, limit_chars=400_000)
            write_receipt(
                receipts_dir / "repoprompt_context.json",
                CommandReceipt(
                    name="repoprompt_context",
                    argv=rp_run.argv,
                    returncode=rp_run.returncode,
                    started_at=iso_utc(time.time() - rp_run.duration_seconds),
                    ended_at=iso_utc(),
                    duration_seconds=rp_run.duration_seconds,
                    stdout_path=str(out_path.relative_to(project_root)),
                    stderr_path=str(
                        (receipts_dir / "repoprompt_context.stderr.txt").relative_to(
                            project_root
                        )
                    )
                    if rp_run.stderr
                    else None,
                    notes={
                        "instructions": rp_instructions,
                        "stdout_tail": truncate_text(rp_run.stdout),
                        "stderr_tail": truncate_text(rp_run.stderr),
                    },
                ),
            )
            if rp_run.stderr:
                (receipts_dir / "repoprompt_context.stderr.txt").write_text(
                    rp_run.stderr, encoding="utf-8"
                )
        except RepoPromptError as e:
            if cfg.repoprompt.required and not cfg.repoprompt.fail_open:
                raise
            write_receipt(
                receipts_dir / "repoprompt_context.json",
                CommandReceipt(
                    name="repoprompt_context",
                    argv=[cfg.repoprompt.cli],
                    returncode=127,
                    started_at=iso_utc(),
                    ended_at=iso_utc(),
                    duration_seconds=0.0,
                    stderr_path=str(
                        (receipts_dir / "repoprompt_context.error.txt").relative_to(
                            project_root
                        )
                    ),
                    notes={"error": str(e)},
                ),
            )
            (receipts_dir / "repoprompt_context.error.txt").write_text(
                str(e) + "\n", encoding="utf-8"
            )

    prompt_text = build_prompt(
        project_root,
        cfg,
        task,
        iteration,
        anchor_text=anchor_text,
        repoprompt_context=rp_context_text,
    )
    prompt_hash = hash_text(prompt_text)

    # Prompt snapshots are debug artifacts; keep them under .ralph/logs/.
    prompt_file = logs_dir / f"prompt-iter{iteration:04d}.txt"
    prompt_file.write_text(prompt_text, encoding="utf-8")

    runner = _get_runner(cfg, agent)
    argv, stdin_text = build_runner_invocation(agent, runner.argv, prompt_text)

    head_before = git_head(project_root)

    # Phase 3: Take snapshot BEFORE agent execution for no-files detection
    before_files = _snapshot_project_files(project_root)

    # Calculate timeout (with adaptive timeout if enabled)
    base_timeout = cfg.loop.runner_timeout_seconds if cfg.loop.runner_timeout_seconds > 0 else None
    timeout = base_timeout

    if cfg.adaptive_timeout.enabled and task is not None and base_timeout is not None:
        # Get previous failures count for this task
        attempts_raw = state.get("task_attempts", {}) or {}
        task_attempt_data = attempts_raw.get(task.id, {})
        if isinstance(task_attempt_data, dict):
            previous_failures = task_attempt_data.get("count", 0)
        else:
            previous_failures = int(task_attempt_data) if task_attempt_data else 0

        # Calculate adaptive timeout
        timeout = calculate_adaptive_timeout(
            task=task,
            previous_failures=previous_failures,
            config=cfg.adaptive_timeout,
            mode_timeout=base_timeout,
        )

    # Run agent
    start = time.time()
    timed_out = False
    try:
        from .output import get_output_config

        if stream:
            result = run_subprocess_live(
                argv,
                cwd=project_root,
                timeout=timeout,
                input_text=stdin_text,
                forward_output=get_output_config().format != "json",
            )
        else:
            result = run_subprocess(
                argv,
                cwd=project_root,
                timeout=timeout,
                input_text=stdin_text,
            )
        runner_ok = result.success
        duration_s = time.time() - start
    except RuntimeError as e:
        # Handle timeout and command not found from run_subprocess
        if "timed out" in str(e):
            timed_out = True
            runner_ok = False
        else:
            runner_ok = False
        duration_s = time.time() - start
        result = SubprocessResult(
            returncode=124 if timed_out else 127,
            stdout="",
            stderr=str(e),
            timed_out=timed_out,
        )

    write_receipt(
        receipts_dir / "runner.json",
        CommandReceipt(
            name="runner",
            argv=argv,
            returncode=result.returncode,
            started_at=iso_utc(time.time() - duration_s),
            ended_at=iso_utc(),
            duration_seconds=duration_s,
            stdout_path=str(log_path.relative_to(project_root)),
            notes={
                "prompt_hash": prompt_hash,
                "stdout_tail": truncate_text(result.stdout),
                "stderr_tail": truncate_text(result.stderr),
            },
        ),
    )

    # Gates
    gate_cmds = cfg.gates.commands if cfg.gates.commands else []
    if gate_cmds or cfg.gates.precommit_hook or cfg.gates.prek.enabled:
        gates_ok, gate_results = run_gates(project_root, gate_cmds, cfg.gates)
    else:
        gates_ok, gate_results = None, []

    gate_summaries: List[str] = []
    for idx, gr in enumerate(gate_results, start=1):
        stdout_path = receipts_dir / f"gate_{idx:02d}.stdout.txt"
        stderr_path = receipts_dir / f"gate_{idx:02d}.stderr.txt"
        stdout_path.write_text(gr.stdout or "", encoding="utf-8")
        stderr_path.write_text(gr.stderr or "", encoding="utf-8")

        write_receipt(
            receipts_dir / f"gate_{idx:02d}.json",
            CommandReceipt(
                name=f"gate_{idx:02d}",
                argv=[gr.cmd],
                returncode=int(gr.return_code),
                started_at=iso_utc(time.time() - gr.duration_seconds),
                ended_at=iso_utc(),
                duration_seconds=gr.duration_seconds,
                stdout_path=str(stdout_path.relative_to(project_root)),
                stderr_path=str(stderr_path.relative_to(project_root)),
                notes={
                    "cmd": gr.cmd,
                    "stdout_tail": truncate_text(gr.stdout or ""),
                    "stderr_tail": truncate_text(gr.stderr or ""),
                },
            ),
        )

        gate_summaries.append(f"[{'OK' if gr.return_code == 0 else 'FAIL'}] {gr.cmd}")

    # Safety valve: if gates fail, force the task open again.
    if gates_ok is False and story_id is not None:
        try:
            tracker.force_task_open(story_id)
        except Exception as e:
            logging.getLogger(__name__).debug("Failed to force task open: %s", e)

    head_after_agent = git_head(project_root)

    # Phase 3: No-files detection - check if agent wrote any user files
    # This is after agent execution but before gates/judge to detect the issue early
    no_files_receipt: Optional[NoFilesWrittenReceipt] = None
    if head_before == head_after_agent and result.returncode == 0:
        # No git changes despite agent returning success - possible no-files issue
        # Take snapshot AFTER agent execution and compare with BEFORE snapshot
        after_files = _snapshot_project_files(project_root)

        # Check if any user files were written (excluding .ralph internal files)
        if not _check_files_written(project_root, before_files, after_files):
            # Agent wrote no files - create receipt and diagnose
            possible_causes = _diagnose_no_files(project_root, result)
            remediation = _suggest_remediation(possible_causes, result)

            no_files_receipt = NoFilesWrittenReceipt(
                task_id=str(story_id) if story_id else "unknown",
                iteration=iteration,
                started_at=iso_utc(time.time() - duration_s),
                ended_at=iso_utc(),
                duration_seconds=duration_s,
                agent_return_code=result.returncode,
                possible_causes=possible_causes,
                remediation=remediation,
            )
            write_receipt(receipts_dir / "no_files_written.json", no_files_receipt)
            _print_no_files_warning(no_files_receipt)

    # Optional: LLM-as-judge gate
    judge_cfg = cfg.gates.llm_judge
    judge_result: Optional[LlmJudgeResult] = None
    judge_ok: Optional[bool] = None
    if judge_cfg.enabled and story_id is not None and gates_ok is not False:
        try:
            done_now = tracker.is_task_done(story_id)
        except Exception as e:
            logging.getLogger(__name__).debug("Failed to check if task is done: %s", e)
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
                jr_argv, jr_stdin = build_runner_invocation(
                    judge_cfg.agent, jr_runner.argv, judge_prompt
                )
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
                    j_result = run_subprocess(
                        jr_argv,
                        cwd=project_root,
                        timeout=timeout,
                    )
                    j_dur = time.time() - j_start
                    j_out = j_result.stdout
                    j_err = j_result.stderr
                    j_combined = j_out + "\n" + j_err
                    j_raw = parse_judge_signal(j_combined)
                    j_pass = j_result.success and (j_raw is True)
                    j_effective = True if j_pass else False
                    judge_result = LlmJudgeResult(
                        enabled=True,
                        agent=str(judge_cfg.agent),
                        return_code=j_result.returncode,
                        duration_seconds=j_dur,
                        judge_signal_raw=j_raw,
                        judge_signal_effective=j_effective,
                        stdout=j_out,
                        stderr=j_err,
                    )
                    judge_ok = bool(j_effective)
                except RuntimeError as e:
                    # Handle timeout and command not found
                    j_dur = time.time() - j_start
                    j_out = ""
                    j_err = str(e)
                    j_rc = 124 if "timed out" in str(e) else 127
                    j_effective = False
                    judge_result = LlmJudgeResult(
                        enabled=True,
                        agent=str(judge_cfg.agent),
                        return_code=j_rc,
                        duration_seconds=j_dur,
                        judge_signal_raw=None,
                        judge_signal_effective=j_effective,
                        stdout="",
                        stderr=j_err,
                    )
                    judge_ok = False

            if judge_ok is False and story_id is not None:
                try:
                    tracker.force_task_open(story_id)
                except (OSError, RuntimeError) as e:
                    logger.debug("Failed to force task open: %s", e)
        else:
            judge_ok = None

    # Optional: review gate (SHIP/BLOCK)
    review_cfg = cfg.gates.review
    review_ok: Optional[bool] = None
    if review_cfg.enabled and gates_ok is not False:
        # Collect diff for review
        diff_for_review = diff_text
        review_prompt = _read_text_if_exists(project_root / review_cfg.prompt)
        if not review_prompt:
            review_prompt = (
                "You are a strict cross-model reviewer. Review the diff and gate results.\n"
                "Return your decision on the final line only: SHIP or BLOCK."
            )
        message = (
            review_prompt
            + "\n\nGate summary:\n"
            + "\n".join(gate_summaries)
            + "\n\nDiff:\n"
            + diff_for_review
        )
        if review_cfg.backend.strip().lower() == "repoprompt":
            try:
                rp = run_review(message=message, cfg=cfg.repoprompt, cwd=project_root)
                review_ok = bool(
                    rp.returncode == 0
                    and _parse_review_token(
                        rp.stdout or "", required=review_cfg.required_token
                    )
                )
                write_receipt(
                    receipts_dir / "review.json",
                    CommandReceipt(
                        name="review",
                        argv=rp.argv,
                        returncode=rp.returncode,
                        started_at=iso_utc(time.time() - rp.duration_seconds),
                        ended_at=iso_utc(),
                        duration_seconds=rp.duration_seconds,
                        notes={
                            "required_token": review_cfg.required_token,
                            "stdout_tail": truncate_text(rp.stdout),
                            "stderr_tail": truncate_text(rp.stderr),
                        },
                    ),
                )
            except RepoPromptError as e:
                review_ok = False
                write_receipt(
                    receipts_dir / "review.json",
                    CommandReceipt(
                        name="review",
                        argv=[cfg.repoprompt.cli],
                        returncode=127,
                        started_at=iso_utc(),
                        ended_at=iso_utc(),
                        duration_seconds=0.0,
                        notes={"error": str(e)},
                    ),
                )
        else:
            try:
                rr_runner = _get_runner(cfg, review_cfg.agent)
                rr_argv, rr_stdin = build_runner_invocation(
                    review_cfg.agent, rr_runner.argv, message
                )
            except Exception as e:
                review_ok = False
                write_receipt(
                    receipts_dir / "review.json",
                    CommandReceipt(
                        name="review",
                        argv=[review_cfg.agent],
                        returncode=127,
                        started_at=iso_utc(),
                        ended_at=iso_utc(),
                        duration_seconds=0.0,
                        notes={"error": str(e)},
                    ),
                )
            else:
                r_start = time.time()
                try:
                    r_result = run_subprocess(
                        rr_argv,
                        cwd=project_root,
                        timeout=timeout,
                    )
                    r_dur = time.time() - r_start
                    r_out = r_result.stdout
                    r_err = r_result.stderr
                    review_ok = bool(
                        r_result.success
                        and _parse_review_token(
                            r_out + "\n" + r_err, required=review_cfg.required_token
                        )
                    )
                    write_receipt(
                        receipts_dir / "review.json",
                        CommandReceipt(
                            name="review",
                            argv=rr_argv,
                            returncode=r_result.returncode,
                            started_at=iso_utc(time.time() - r_dur),
                            ended_at=iso_utc(),
                            duration_seconds=r_dur,
                            notes={
                                "required_token": review_cfg.required_token,
                                "stdout_tail": truncate_text(r_out),
                                "stderr_tail": truncate_text(r_err),
                            },
                        ),
                    )
                except RuntimeError as e:
                    r_dur = time.time() - r_start
                    review_ok = False
                    write_receipt(
                        receipts_dir / "review.json",
                        CommandReceipt(
                            name="review",
                            argv=rr_argv,
                            returncode=124 if "timed out" in str(e) else 127,
                            started_at=iso_utc(time.time() - r_dur),
                            ended_at=iso_utc(),
                            duration_seconds=r_dur,
                            notes={"error": str(e)},
                        ),
                    )

        if review_ok is False and story_id is not None:
            try:
                tracker.force_task_open(story_id)
            except OSError as e:
                logger.debug("File read failed: %s", e)

    # Append orchestrator entry to progress.md (append-only)

    task_done_now = False
    if story_id is not None:
        try:
            task_done_now = tracker.is_task_done(story_id)
        except OSError as e:
            logger.debug("File read failed: %s", e)
        # After agent marks task as done, verify expected files exist
        if task_done_now and task is not None:
            if not _verify_task_completion(task, project_root):
                logger.warning(
                    f"Task {story_id} marked done but expected files not found"
                )

    status = (
        "DONE"
        if (
            task_done_now
            and gates_ok is not False
            and judge_ok is not False
            and review_ok is not False
        )
        else "CONTINUE"
    )
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
    except OSError as e:
        logger.debug("File read failed: %s", e)
    branch_label = branch or current_branch
    progress_line = (
        f"- [{ts}] iter {iteration} mode=prd status={status} checks={checks} "
        f"story={story_label} agent={agent} branch={branch_label} log={log_path.name}"
    )
    with progress_path.open("a", encoding="utf-8") as f:
        f.write(progress_line + "\n")

    # Auto-commit / amend (best-effort)
    commit_action: Optional[str] = None
    # These are logged unconditionally below; ensure they're always defined even
    # when auto-commit is disabled or skipped.
    commit_rc = 0
    commit_out = ""
    commit_err = ""
    if (
        cfg.git.auto_commit
        and (gates_ok is not False)
        and (judge_ok is not False)
        and (review_ok is not False)
    ):
        # If the agent already committed but left a dirty tree, prefer amend.
        dirty = not git_is_clean(project_root)
        if dirty:
            try:
                # Stage everything, then unstage orchestrator operational state.
                run_subprocess(
                    ["git", "add", "-A"],
                    cwd=project_root,
                    check=True,
                )
                run_subprocess(
                    ["git", "reset", "--quiet", "--", ".ralph/logs/"],
                    cwd=project_root,
                    check=False,
                )
                run_subprocess(
                    ["git", "reset", "--quiet", "--", ".ralph/state.json"],
                    cwd=project_root,
                    check=False,
                )

                # Nothing staged? Don't create empty commits.
                staged_result = run_subprocess(
                    ["git", "diff", "--cached", "--quiet"],
                    cwd=project_root,
                    check=False,
                )
                staged = not staged_result.success

                if not staged:
                    commit_action = "noop"
                    commit_rc = 0
                elif head_after_agent != head_before and cfg.git.amend_if_needed:
                    c_result = run_subprocess(
                        ["git", "commit", "--amend", "--no-edit"],
                        cwd=project_root,
                        check=False,
                    )
                    commit_action = "amend"
                    commit_rc = c_result.returncode
                    commit_out = c_result.stdout
                    commit_err = c_result.stderr
                else:
                    title = (task.title if task is not None else "no-task").strip()
                    msg = cfg.git.commit_message_template.format(
                        story_id=story_id or "-", title=title
                    )
                    msg = msg.strip() or f"ralph: {story_id or '-'}"
                    c_result = run_subprocess(
                        ["git", "commit", "-m", msg],
                        cwd=project_root,
                        check=False,
                    )
                    commit_action = "commit"
                    commit_rc = c_result.returncode
                    commit_out = c_result.stdout
                    commit_err = c_result.stderr
            except Exception as e:
                commit_action = "error"
                commit_rc = 1
                commit_err = str(e)

    # Attempt tracking + auto-block backstop
    blocked_now = False

    if task is not None:
        attempts_raw = state.get("task_attempts", {}) or {}
        blocked_raw = state.get("blocked_tasks", {}) or {}
        cur_attempts = int(attempts_raw.get(task.id, 0))

        progress_success = bool(
            task_done_now
            and runner_ok
            and (gates_ok is not False)
            and (judge_ok is not False)
            and (review_ok is not False)
        )
        if not progress_success:
            cur_attempts += 1
            attempts_raw[task.id] = cur_attempts
            if gates_ok is False:
                reason = "gates failed"
            elif review_ok is False:
                reason = "review BLOCK"
            elif judge_ok is False:
                reason = "judge failed"
            elif not runner_ok:
                reason = "runner failed"
            elif not task_done_now:
                reason = "task not marked done (agent exited successfully but task not completed)"
            else:
                reason = f"no progress made (exit_ok={runner_ok}, task_done={task_done_now}, gates_ok={gates_ok is not False})"

            blocked_raw[task.id] = {
                "blocked_at": iso_utc(),
                "attempts": cur_attempts,
                "reason": reason,
                "attempt_id": attempt_id,
            }
            state["blocked_tasks"] = blocked_raw
            try:
                tracker.block_task(
                    task.id, f"Auto-blocked after {cur_attempts} attempts: {reason}"
                )
                blocked_now = True
            except OSError as e:
                logger.debug("File read failed: %s", e)

            progress_path = project_root / cfg.files.progress
            progress_path.parent.mkdir(parents=True, exist_ok=True)
            with progress_path.open("a", encoding="utf-8") as f:
                f.write(
                    f"[{iso_utc()}] BLOCKED task {task.id} ({task.title}) after {cur_attempts} attempts: {reason}\n"
                )

        state["task_attempts"] = attempts_raw

    # Capture done count after the run (used for no-progress detection).
    done_after, total_after = done_before, total_before
    try:
        done_after, total_after = tracker.counts()
    except OSError as e:
        logger.debug("File read failed: %s", e)

    head_after = git_head(project_root)
    repo_clean = git_is_clean(project_root)
    done_delta = (done_after > done_before) and (total_after >= done_before)
    progress_made = done_delta or (head_after != head_before) or (not repo_clean)

    stdout_text = _coerce_text(result.stdout)
    stderr_text = _coerce_text(result.stderr)
    combined_output = stdout_text + "\n" + stderr_text
    exit_signal_raw = parse_exit_signal(combined_output)
    exit_signal = exit_signal_raw

    try:
        from .evidence import extract_evidence
        # Note: evidence_json_enabled would come from cfg.prompt if implemented
        citations = extract_evidence(combined_output, enable_json=False)
        evidence_count = len(citations)

        # Write evidence receipt if citations found
        if citations and receipts_dir:
            receipt = EvidenceReceipt(
                attempt_id=attempt_id,
                timestamp=iso_utc(),
                citations=citations,
                raw_output_hash=hash_text(combined_output),
                metadata={
                    "iteration": iteration,
                    "agent": agent,
                    "story_id": story_id,
                },
            )
            write_receipt(
                receipts_dir / "evidence.json",
                receipt._to_command_receipt(),
            )
    except Exception as e:
        # Evidence extraction is non-blocking
        logger.debug(f"Evidence extraction failed: {e}")

    # Enforce exit constraints at orchestrator level.
    try:
        tracker_done = tracker.all_done()
    except OSError as e:
        logger.debug("File read failed: %s", e)
        tracker_done = False

    # Beads has no reliable "all done" signal; allow exit if the agent says so.
    allow_exit_without_all_done = tracker.kind == "beads"

    if exit_signal is True and (not tracker_done) and (not allow_exit_without_all_done):
        exit_signal = False
    if exit_signal is True and not repo_clean:
        exit_signal = False
    if exit_signal is True and gates_ok is False:
        exit_signal = False
    if exit_signal is True and judge_ok is False:
        exit_signal = False
    if exit_signal is True and review_ok is False:
        exit_signal = False

    judge_section = "llm_judge_enabled: false\n"
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
                judge_section += (
                    "--- judge stdout ---\n" + judge_result.stdout.rstrip() + "\n"
                )
            if (judge_result.stderr or "").strip():
                judge_section += (
                    "--- judge stderr ---\n" + judge_result.stderr.rstrip() + "\n"
                )

    review_section = "(review: not run)\n"
    if review_cfg.enabled:
        review_section = (
            f"review_enabled: true\n"
            f"review_backend: {review_cfg.backend}\n"
            f"review_required_token: {review_cfg.required_token}\n"
            f"review_ok: {review_ok}\n"
        )

    stdin_flag = "true" if stdin_text is not None else "false"
    log_path.write_text(
        f"# ralph-gold log\n"
        f"timestamp_utc: {ts}\n"
        f"iteration: {iteration}\n"
        f"agent: {agent}\n"
        f"branch: {branch_label}\n"
        f"story_id: {story_id}\n"
        f"target_task_id: {target_task_id_effective}\n"
        f"target_status: {target_status}\n"
        f"target_failure_reason: {target_failure_reason}\n"
        f"targeting_policy: {targeting_policy}\n"
        f"task_title: {task_title}\n"
        f"attempt_id: {attempt_id}\n"
        f"prompt_hash: {prompt_hash}\n"
        f"receipts_dir: {receipts_dir}\n"
        f"context_dir: {context_dir}\n"
        f"tracker_error: {task_err}\n"
        f"cmd: {json.dumps(argv)}\n"
        f"stdin_prompt: {stdin_flag}\n"
        f"timeout_seconds: {timeout}\n"
        f"timed_out: {str(timed_out).lower()}\n"
        f"duration_seconds: {duration_s:.2f}\n"
        f"return_code: {result.returncode}\n"
        f"repo_clean: {str(repo_clean).lower()}\n"
        f"exit_signal_raw: {exit_signal_raw}\n"
        f"exit_signal_effective: {exit_signal}\n"
        f"commit_action: {commit_action}\n"
        f"commit_return_code: {commit_rc}\n"
        f"\n--- stdout ---\n{stdout_text}\n"
        f"\n--- stderr ---\n{stderr_text}\n"
        f"\n--- gates ---\n{_format_gate_results(gates_ok, gate_results, cfg.gates.output_mode, cfg.gates.max_output_lines)}"
        f"\n--- llm_judge ---\n{judge_section}"
        f"\n--- review ---\n{review_section}"
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
        state["noProgressStreak"] = int(state.get("noProgressStreak", 0)) + 1

    history = state.get("history", [])
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "ts": ts,
            "iteration": iteration,
            "agent": agent,
            "loop_mode": resolved_mode,
            "branch": branch_label,
            "story_id": story_id,
            "target_task_id": target_task_id_effective,
            "target_status": target_status,
            "target_failure_reason": target_failure_reason,
            "targeting_policy": targeting_policy,
            "mode": resolved_mode,
            "duration_seconds": round(duration_s, 2),
            "return_code": int(result.returncode),
            "gates_ok": gates_ok,
            "judge_ok": judge_ok,
            "judge_enabled": bool(judge_cfg.enabled),
            "judge_agent": str(judge_cfg.agent),
            "judge_ran": bool(judge_result is not None),
            "judge_return_code": (
                judge_result.return_code if judge_result is not None else None
            ),
            "judge_duration_seconds": (
                round(judge_result.duration_seconds, 2)
                if judge_result is not None
                else None
            ),
            "judge_signal_raw": (
                judge_result.judge_signal_raw if judge_result is not None else None
            ),
            "judge_signal_effective": (
                judge_result.judge_signal_effective
                if judge_result is not None
                else None
            ),
            "review_ok": review_ok,
            "blocked": blocked_now,
            "attempt_id": attempt_id,
            "receipts_dir": str(Path(receipts_dir).relative_to(project_root)),
            "context_dir": str(Path(context_dir).relative_to(project_root)),
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
    if not state.get("session_id"):
        state["session_id"] = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    save_state(state_path, state)

    attempt_record_path.write_text(
        json.dumps(
            {
                "attempt_id": attempt_id,
                "iteration": iteration,
                "task_id": story_id,
                "target_task_id": target_task_id_effective,
                "target_status": target_status,
                "target_failure_reason": target_failure_reason,
                "targeting_policy": targeting_policy,
                "task_title": task_title,
                "started_at": iso_utc(iter_started),
                "ended_at": iso_utc(),
                "runner_ok": runner_ok,
                "gates_ok": gates_ok,
                "judge_ok": judge_ok,
                "review_ok": review_ok,
                "blocked": blocked_now,
                "exit_signal": exit_signal,
                "return_code": int(result.returncode),
                "prompt_hash": prompt_hash,
                "branch": branch_label,
                "log_path": str(log_path),
                "receipts_dir": str(receipts_dir),
                "context_dir": str(context_dir),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return IterationResult(
        iteration=iteration,
        agent=agent,
        story_id=story_id,
        exit_signal=exit_signal,
        return_code=int(result.returncode),
        log_path=log_path,
        progress_made=progress_made,
        no_progress_streak=int(state.get("noProgressStreak", 0)),
        gates_ok=gates_ok,
        repo_clean=repo_clean,
        judge_ok=judge_ok,
        review_ok=review_ok,
        blocked=blocked_now,
        attempt_id=attempt_id,
        receipts_dir=str(receipts_dir),
        context_dir=str(context_dir),
        task_title=task_title,
        evidence_count=evidence_count,
        target_task_id=target_task_id_effective,
        target_status=target_status,
        target_failure_reason=target_failure_reason,
        targeting_policy=targeting_policy,
    )


# ============================
# Phase 3: No-Files Detection Helper Functions
# ============================


def _snapshot_project_files(project_root: Path) -> set[str]:
    """Create snapshot of project files for comparison.

    Returns a set of relative file paths from project root, excluding
    .ralph internal files, git directory, and common ignore patterns.

    Args:
        project_root: Path to the project root directory

    Returns:
        Set of relative file paths (as strings)
    """
    ignore_patterns = {
        ".git",
        ".ralph",
        "__pycache__",
        "*.pyc",
        "*.pyo",
        ".DS_Store",
        "*.tmp",
        "*.swp",
        ".pytest_cache",
        ".hypothesis",
        ".venv",
        "venv",
        "node_modules",
    }

    files: set[str] = set()
    for item in project_root.rglob("*"):
        if not item.is_file():
            continue

        # Skip if any parent directory matches ignore pattern
        rel_path = item.relative_to(project_root)
        parts = rel_path.parts

        should_ignore = False
        for part in parts:
            if part in ignore_patterns or any(
                fnmatch.fnmatch(part, pattern) for pattern in ignore_patterns
            ):
                should_ignore = True
                break

        # Also check the full path against glob patterns
        if not should_ignore:
            rel_str = str(rel_path)
            for pattern in ignore_patterns:
                if fnmatch.fnmatch(rel_str, pattern) or fnmatch.fnmatch(
                    rel_str, f"*/{pattern}"
                ):
                    should_ignore = True
                    break

        if not should_ignore:
            files.add(rel_str)

    return files


def _check_files_written(
    project_root: Path, before: set[str], after: set[str]
) -> bool:
    """Check if any user files were written.

    Compares before/after snapshots and returns True if any new files
    were added or existing files were modified (by checking mtime).

    Args:
        project_root: Path to the project root
        before: Snapshot before agent execution
        after: Snapshot after agent execution

    Returns:
        True if files were written, False otherwise
    """
    # Check for new files
    new_files = after - before
    if new_files:
        return True

    # Check for modified files (same path but different mtime)
    # We only check files that exist in both snapshots
    common_files = before & after
    now = time.time()
    recent_threshold = 900  # 15 minutes (same as runner timeout)

    for file_path in common_files:
        full_path = project_root / file_path
        try:
            mtime = full_path.stat().st_mtime
            # If file was modified in the last 15 minutes, consider it written
            if now - mtime < recent_threshold:
                return True
        except (OSError, FileNotFoundError):
            continue

    return False


def _diagnose_no_files(project_root: Path, agent_result: "SubprocessResult") -> List[str]:
    """Diagnose why agent wrote no files.

    Enhanced to detect:
    - Timeout (exit code 124)
    - Pre-existing gate failures
    - Sandbox permissions issues

    Args:
        project_root: Path to the project root
        agent_result: Result from agent subprocess execution

    Returns:
        List of possible causes (diagnostic messages)
    """
    causes: List[str] = []

    # Check for timeout
    if agent_result.returncode == 124 or (
        hasattr(agent_result, "timed_out") and agent_result.timed_out
    ):
        causes.append("Agent timed out (exit code 124)")
        causes.append("Task may be too complex for single iteration")

    # Check for timeout but files were created
    if agent_result.returncode == 124:
        recent_files = _find_recently_created_files(project_root)
        if recent_files:
            causes.append(
                f"Files were created before timeout: {', '.join(recent_files[:3])}"
            )
            causes.append("Task may be complete despite timeout - verify manually")

    # Check if agent had errors
    if agent_result.stderr:
        error_lower = agent_result.stderr.lower()
        if "permission denied" in error_lower:
            causes.append("Agent encountered permission errors")
            causes.append("Check file/directory permissions for project")
        if "command not found" in error_lower:
            causes.append("Agent command not found")
            causes.append("Verify agent CLI is installed and in PATH")
        if "no space left" in error_lower:
            causes.append("Disk full or no space left")
            causes.append("Free up disk space and retry")

    # Check for pre-existing gate failures
    ralph_dir = project_root / ".ralph"
    if ralph_dir.exists():
        # Look for recent gate failures in receipts
        receipts_dir = ralph_dir / "receipts"
        if receipts_dir.exists():
            for receipt_file in receipts_dir.glob("gate_*.json"):
                try:
                    data = json.loads(receipt_file.read_text())
                    if data.get("returncode", 0) != 0:
                        causes.append("Pre-existing gate failures detected")
                        causes.append(
                            f"Gate '{data.get('name', 'unknown')}' is failing: "
                            f"{data.get('cmd', 'unknown')}"
                        )
                        causes.append(
                            "Fix gate failures OR document why they cannot be fixed"
                        )
                        break
                except (json.JSONDecodeError, OSError) as e:
                    logger.debug("File read failed: %s", e)

    # If no specific cause found, add generic message
    if not causes:
        causes.append("Agent completed but wrote no files")
        causes.append("Agent may have only provided explanation without code changes")
        causes.append("Task may require clarification or be impossible as stated")

    return causes


def _find_recently_created_files(project_root: Path) -> List[str]:
    """Find files created in last 15 minutes.

    Args:
        project_root: Path to the project root

    Returns:
        List of up to 10 recently created file paths
    """
    recent_files: List[str] = []
    now = time.time()
    recent_threshold = 900  # 15 minutes

    for item in project_root.rglob("*"):
        if not item.is_file():
            continue

        # Skip .ralph internal files
        if ".ralph" in item.parts or ".git" in item.parts:
            continue

        try:
            mtime = item.stat().st_mtime
            if now - mtime < recent_threshold:
                rel_path = str(item.relative_to(project_root))
                recent_files.append(rel_path)
        except OSError:
            continue

    return recent_files[:10]  # Limit to 10 most recent


def _suggest_remediation(possible_causes: List[str], agent_result: "SubprocessResult") -> str:
    """Suggest remediation steps based on diagnosis.

    Args:
        possible_causes: List of diagnostic causes from _diagnose_no_files
        agent_result: Result from agent subprocess execution

    Returns:
        Remediation suggestions as a string
    """
    causes_lower = " ".join(possible_causes).lower()

    # Timeout specific
    if agent_result.returncode == 124:
        return (
            "Suggestion: Task is complex and needs more time.\n"
            "Consider increasing runner_timeout_seconds in .ralph/ralph.toml:\n"
            "  [loop]\n"
            "  runner_timeout_seconds = 1800  # 30 minutes instead of 15\n\n"
            "Also verify: Check if expected files were created despite timeout."
        )

    # Permission issues
    if "permission" in causes_lower:
        return (
            "Suggestion: Fix file/directory permissions.\n"
            "Check that the agent can write to the project directory:\n"
            "  ls -la .\n"
            "  chmod u+w .  # if needed"
        )

    # Gate failures
    if "gate" in causes_lower:
        return (
            "Suggestion: Fix failing gates before proceeding.\n"
            "Run gates manually to see errors:\n"
            "  ralph gates\n\n"
            "If gates cannot be fixed, document why in .ralph/progress.md\n"
            "and consider adjusting gate configuration."
        )

    # Command not found
    if "command not found" in causes_lower or "127" in str(agent_result.returncode):
        return (
            "Suggestion: Agent CLI is not installed or not in PATH.\n"
            "Verify the agent is available:\n"
            "  which claude  # or codex, copilot, etc.\n\n"
            "Check .ralph/ralph.toml runners configuration."
        )

    # Disk space
    if "space" in causes_lower:
        return (
            "Suggestion: Free up disk space.\n"
            "Check available space:\n"
            "  df -h ."
        )

    # Generic remediation
    return (
        "Suggestion: Agent may have misunderstood the task or lacks context.\n"
        "Consider:\n"
        "1. Review task acceptance criteria for clarity\n"
        "2. Add more context to PRD or task description\n"
        "3. Check agent output in .ralph/logs/ for explanations\n"
        "4. Try simplifying the task or breaking it into smaller steps"
    )


def _print_no_files_warning(receipt: NoFilesWrittenReceipt) -> None:
    """Print formatted warning box for no-files-written receipt.

    Args:
        receipt: The NoFilesWrittenReceipt to display
    """
    warning_box = (
        "\n"
        "+==============================================================================+\n"
        "| WARNING: NO FILES WRITTEN DETECTED                                          |\n"
        "+==============================================================================+\n"
        "\n"
        "Agent completed execution but wrote no user files to the project.\n"
        "\n"
        f"Task ID:        {receipt.task_id}\n"
        f"Iteration:      {receipt.iteration}\n"
        f"Duration:       {receipt.duration_seconds:.1f} seconds\n"
        f"Agent exit code: {receipt.agent_return_code}\n"
        "\n"
        "Possible causes:\n"
        "{causes}\n"
        "\n"
        "Remediation:\n"
        "{remediation}\n"
        "\n"
        "Receipt saved to: .ralph/receipts/no_files_written.json\n"
        "\n"
    )
    cause_lines = "\n".join(f"  * {c}" for c in receipt.possible_causes)
    remediation_lines = "\n".join(
        f"  {line}" for line in receipt.remediation.split("\n")
    )

    print(warning_box)


# ============================
# End Phase 3 Helper Functions
# ============================


# ============================
# Phase 3: Task Completion Verification
# ============================


def _extract_files_from_criteria(criteria: List[str]) -> List[str]:
    """Extract file paths from task acceptance criteria.

    Looks for patterns like:
    - "Create Sources/MyFile.swift"
    - "File: src/model.py"
    - Path-like strings with extensions

    Args:
        criteria: List of acceptance criterion strings

    Returns:
        List of extracted file paths
    """
    import re

    files: List[str] = []

    # Pattern 1: "Create X/Y/Z.ext" or similar
    create_pattern = r'[Cc]reate\s+([A-Z][a-z]+(?:/[A-Z][a-z\d]+)+\.[a-z]+)'

    # Pattern 2: "File: path/to/file.ext"
    file_pattern = r'[Ff]ile:\s*([a-z\d_]+(?:/[a-z\d_.]+)*\.[a-z]+)'

    # Pattern 3: Any path-like string with extension (catch-all)
    path_pattern = r'(?<!\w)([A-Z][a-z]+(?:/[A-Z][a-z\d]+)+\.[a-z]+)(?!\w)'

    for criterion in criteria:
        # Try each pattern
        for pattern in [create_pattern, file_pattern, path_pattern]:
            matches = re.findall(pattern, criterion)
            files.extend(matches)

    return list(set(files))  # Deduplicate


def _verify_task_completion(task: SelectedTask, project_root: Path) -> bool:
    """Verify task completion by checking for expected files.

    Parses task acceptance criteria for file mentions and verifies they exist.

    Args:
        task: The SelectedTask with acceptance criteria
        project_root: Path to the project root

    Returns:
        True if expected files exist, False otherwise
    """
    if not task.acceptance:
        # No acceptance criteria to verify against
        return True

    expected_files = _extract_files_from_criteria(task.acceptance)

    if not expected_files:
        # No files mentioned in acceptance criteria
        return True

    # Check if expected files exist
    for file_path in expected_files:
        full_path = project_root / file_path
        if not full_path.exists():
            logger.warning(
                f"Task completion verification failed: expected file not found: {file_path}"
            )
            return False

    return True


# ============================
# End Phase 3 Task Verification
# ============================


def run_loop(
    project_root: Path,
    agent: str,
    max_iterations: Optional[int] = None,
    cfg: Optional[Config] = None,
    parallel: bool = False,
    max_workers: Optional[int] = None,
    dry_run: bool = False,
    stream: bool = False,
) -> List[IterationResult]:
    """Run the Ralph loop in sequential or parallel mode.

    Args:
        project_root: Project root directory
        agent: Agent/runner to use (e.g., "codex", "claude")
        max_iterations: Maximum iterations (overrides config)
        cfg: Configuration (loaded if not provided)
        parallel: Enable parallel execution (overrides config)
        max_workers: Number of parallel workers (overrides config)
        dry_run: If True, simulate execution without running agents
        stream: If True, stream runner output to terminal during each sequential
            iteration. This flag is ignored when parallel execution is enabled.

    Returns:
        List of iteration results
    """
    cfg = cfg or load_config(project_root)
    cfg, resolved_mode = _resolve_loop_mode(cfg)
    if parallel and stream:
        logger.debug("Ignoring stream flag in parallel mode.")
        stream = False

    # Handle dry-run mode
    if dry_run:
        limit = (
            max_iterations if max_iterations is not None else cfg.loop.max_iterations
        )
        result = dry_run_loop(project_root, agent, limit, cfg)

        # Print dry-run results
        from .output import print_output

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
        print_output(
            f"Remaining tasks: {result.total_tasks - result.completed_tasks}",
            level="quiet",
        )
        print_output("", level="quiet")

        if result.issues:
            print_output("Issues found:", level="quiet")
            for issue in result.issues:
                print_output(f"  ❌ {issue}", level="error")
            print_output("", level="quiet")

        if result.tasks_to_execute:
            print_output(
                f"Tasks that would be executed (up to {limit} iterations):",
                level="quiet",
            )
            for i, task in enumerate(result.tasks_to_execute, 1):
                print_output(f"  {i}. {task}", level="quiet")
            print_output("", level="quiet")
        else:
            print_output("No tasks would be executed.", level="quiet")
            print_output("", level="quiet")

        if result.gates_to_run:
            print_output("Gates that would run:", level="quiet")
            for gate in result.gates_to_run:
                print_output(f"  • {gate}", level="quiet")
            print_output("", level="quiet")
        else:
            print_output("No gates configured.", level="quiet")
            print_output("", level="quiet")

        print_output(
            f"Estimated duration: {result.estimated_duration_seconds:.1f} seconds",
            level="quiet",
        )
        print_output(f"Estimated cost: ${result.estimated_cost:.2f}", level="quiet")
        print_output("", level="quiet")
        print_output("=" * 60, level="quiet")
        print_output("Dry-run complete. No changes were made.", level="quiet")
        print_output("=" * 60, level="quiet")

        # Return empty list for dry-run
        return []

    ensure_git_repo(project_root)

    # Determine if parallel mode should be used
    parallel_enabled = parallel or cfg.parallel.enabled

    # If parallel mode is enabled, try to delegate to ParallelExecutor
    if parallel_enabled:
        try:
            from .parallel import ParallelExecutor

            # Override max_workers if specified
            if max_workers is not None:
                from dataclasses import replace

                cfg = replace(
                    cfg, parallel=replace(cfg.parallel, max_workers=max_workers)
                )

            # Create tracker early to check parallel support
            tracker = make_tracker(project_root, cfg)

            # Check if tracker supports parallel execution
            if not hasattr(tracker, "get_parallel_groups"):
                from .output import print_output

                print_output(
                    f"Tracker '{tracker.kind}' does not support parallel execution. "
                    f"Falling back to sequential mode.",
                    level="normal",
                )
                # Fall through to sequential mode below by setting flag
                parallel_enabled = False
            else:
                # Compute effective cap considering max_iterations and rate limit
                state_path = project_root / ".ralph" / "state.json"
                state = load_state(state_path)

                # State validation (read-only, with warnings)
                if cfg.state.validate_on_startup:
                    prd_path = project_root / cfg.files.prd
                    validation = validate_state_against_prd(
                        project_root,
                        prd_path,
                        state_path,
                        cfg.state.protect_recent_hours,
                    )
                    if validation.stale_ids:
                        from .output import print_output

                        print_output(
                            f"State validation: found {len(validation.stale_ids)} stale task IDs",
                            level="warning",
                        )
                        if validation.protected_ids:
                            print_output(
                                f"Protected (current/recent): {validation.protected_ids}",
                                level="info",
                            )
                        if not validation.can_auto_cleanup:
                            print_output(
                                "Cannot auto-cleanup: current task is stale or PRD recently modified",
                                level="warning",
                            )
                        print_output(
                            f"Run 'ralph state cleanup' to remove stale task IDs",
                            level="info",
                        )

                # Rate limit check
                rate_limit_ok, wait_seconds = _rate_limit_ok(
                    state, cfg.loop.rate_limit_per_hour
                )
                if not rate_limit_ok:
                    from .output import print_output

                    print_output(
                        f"Rate limit reached. Wait ~{wait_seconds}s", level="error"
                    )
                    return []

                # Compute max tasks we can run this invocation
                limit = (
                    max_iterations
                    if max_iterations is not None
                    else cfg.loop.max_iterations
                )

                # Compute remaining slots from rate limit
                # Define invocations once before the rate-limit branch
                invocations = state.get("invocations", [])
                if not isinstance(invocations, list):
                    invocations = []

                remaining_slots = limit
                if cfg.loop.rate_limit_per_hour > 0:
                    per_hour = cfg.loop.rate_limit_per_hour
                    remaining_slots = min(limit, per_hour - len(invocations))
                else:
                    remaining_slots = limit

                # Get remaining tasks from tracker to avoid over-provisioning
                try:
                    done, total = tracker.counts()
                    remaining_tasks = max(0, total - done)
                    effective_cap = min(remaining_slots, remaining_tasks)
                except (OSError, ValueError, TypeError) as e:
                    logger.debug("File read failed: %s", e)
                    effective_cap = remaining_slots

                if effective_cap <= 0:
                    from .output import print_output

                    print_output(
                        "No tasks remaining or rate limit reached.", level="normal"
                    )
                    return []

                # Set up parallel logging BEFORE execution
                state_dir = project_root / ".ralph"
                logs_dir = state_dir / "logs"
                logs_dir.mkdir(parents=True, exist_ok=True)

                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                parallel_log = logs_dir / f"parallel-{ts}.log"
                with parallel_log.open("a", encoding="utf-8") as f:
                    f.write(f"timestamp_utc: {ts}\n")
                    f.write(f"agent: {agent}\n")
                    f.write(f"max_workers: {cfg.parallel.max_workers}\n")
                    f.write(f"strategy: {cfg.parallel.strategy}\n")
                    f.write(f"merge_policy: {cfg.parallel.merge_policy}\n")
                    f.write(f"effective_cap: {effective_cap}\n")
                    f.write("\n--- Parallel execution started ---\n\n")

                # Create and run parallel executor (do NOT reserve slots yet)
                executor = ParallelExecutor(project_root, cfg, max_tasks=effective_cap)
                results = executor.run_parallel(agent, tracker)

                # Reserve invocation slots AFTER we know we got results
                if results:
                    invocations = state.get("invocations", [])
                    if not isinstance(invocations, list):
                        invocations = []

                    now = time.time()
                    # Reserve one slot per actual result
                    for _ in results:
                        invocations.append(now)

                    state["invocations"] = invocations
                    save_state(state_path, state)

                # Log parallel execution completion (only runs if parallel succeeded)
                with open(parallel_log, "a", encoding="utf-8") as f:
                    f.write("\n--- Parallel execution completed ---\n")
                    f.write(f"total_workers: {len(results)}\n")
                    f.write(
                        f"successful: {sum(1 for r in results if r.gates_ok is not False)}\n"
                    )
                    f.write(
                        f"failed: {sum(1 for r in results if r.gates_ok is False)}\n"
                    )

                # Log completion and return results
                from .output import print_output

                print_output(
                    f"Parallel run complete: {len(results)} iteration(s)",
                    level="normal",
                )
                return results

        except ImportError:
            # ParallelExecutor not yet implemented, fall back to sequential
            from .output import print_output

            print_output(
                "Warning: Parallel mode requested but ParallelExecutor not available. Running sequentially.",
                level="normal",
            )
            # Fall through to sequential mode below
            parallel_enabled = False

    # Sequential mode (existing implementation)
    state_dir = project_root / ".ralph"
    state_dir.mkdir(exist_ok=True)
    state_path = state_dir / "state.json"
    state = load_state(state_path)
    state["noProgressStreak"] = 0
    save_state(state_path, state)

    tracker = make_tracker(project_root, cfg)
    allow_exit_without_all_done = tracker.kind == "beads"

    results: List[IterationResult] = []
    limit = max_iterations if max_iterations is not None else cfg.loop.max_iterations
    start_iter = next_iteration_number(project_root)

    for offset in range(limit):
        i = start_iter + offset
        res = run_iteration(
            project_root,
            agent=agent,
            cfg=cfg,
            iteration=i,
            stream=stream,
        )
        results.append(res)

        done = False  # Initialize before try block
        try:
            done = tracker.all_done()
        except OSError as e:
            logger.debug("File read failed: %s", e)
            done = False

        if res.no_progress_streak >= cfg.loop.no_progress_limit:
            break

        # Exit immediately if no task was selected (all done or all blocked)
        if res.story_id is None:
            try:
                # Reuse 'done' from above instead of calling all_done() again
                all_blocked = tracker.all_blocked()
            except OSError as e:
                logger.debug("File read failed: %s", e)
                all_blocked = False

            if done:
                print("All tasks completed successfully")
                break
            elif all_blocked:
                print("All tasks are blocked")
                break

        if (done or allow_exit_without_all_done) and res.exit_signal is True:
            break

        if cfg.loop.sleep_seconds_between_iters > 0:
            time.sleep(cfg.loop.sleep_seconds_between_iters)

    return results
