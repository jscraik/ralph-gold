"""Smart resume functionality for interrupted iterations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .loop import load_state


@dataclass
class ResumeInfo:
    """Information about a resumable iteration."""

    iteration: int
    task_id: Optional[str]
    task_title: Optional[str]
    agent: str
    gates_passed: Optional[bool]
    timestamp: str
    log_path: Optional[str]
    interrupted: bool


def detect_interrupted_iteration(project_root: Path) -> Optional[ResumeInfo]:
    """Detect if the last iteration was interrupted.

    An iteration is considered interrupted if:
    - state.json exists with history
    - Last iteration has no exit_signal or return_code indicates failure
    - Log file exists but iteration didn't complete normally

    Returns:
        ResumeInfo if resumable iteration found, None otherwise
    """
    state_path = project_root / ".ralph" / "state.json"
    if not state_path.exists():
        return None

    state = load_state(state_path)
    history = state.get("history", [])
    if not history:
        return None

    last = history[-1]
    if not isinstance(last, dict):
        return None

    # Check if iteration completed normally
    exit_signal = last.get("exit_signal")
    return_code = last.get("return_code", 0)
    gates_ok = last.get("gates_ok")

    # If exit_signal is present and return_code is 0, it completed normally
    if exit_signal is not None and return_code == 0:
        return None

    # If gates failed, it's not really interrupted - it failed legitimately
    if gates_ok is False:
        return None

    # This looks like an interruption
    return ResumeInfo(
        iteration=int(last.get("iteration", 0)),
        task_id=last.get("story_id"),
        task_title=last.get("task_title"),
        agent=str(last.get("agent", "unknown")),
        gates_passed=gates_ok,
        timestamp=str(last.get("ts", "unknown")),
        log_path=last.get("log_path"),
        interrupted=True,
    )


def should_resume(resume_info: ResumeInfo) -> bool:
    """Determine if we should offer to resume based on the interruption state.

    Args:
        resume_info: Information about the interrupted iteration

    Returns:
        True if resume is recommended, False otherwise
    """
    # If gates passed, definitely worth resuming
    if resume_info.gates_passed is True:
        return True

    # If gates weren't run yet, might be worth resuming
    if resume_info.gates_passed is None:
        return True

    # If gates failed, probably not worth resuming
    return False


def format_resume_prompt(resume_info: ResumeInfo) -> str:
    """Format a user-friendly prompt about the interrupted iteration.

    Args:
        resume_info: Information about the interrupted iteration

    Returns:
        Formatted string describing the interruption
    """
    lines = []
    lines.append(f"Last iteration ({resume_info.iteration}) was interrupted:")
    lines.append(f"  Agent: {resume_info.agent}")

    if resume_info.task_id:
        lines.append(f"  Task: {resume_info.task_id}")
        if resume_info.task_title:
            lines.append(f"  Title: {resume_info.task_title}")

    if resume_info.gates_passed is True:
        lines.append("  Gates: ✓ PASSED")
    elif resume_info.gates_passed is False:
        lines.append("  Gates: ✗ FAILED")
    else:
        lines.append("  Gates: (not run)")

    lines.append(f"  Time: {resume_info.timestamp}")

    if resume_info.log_path:
        lines.append(f"  Log: {resume_info.log_path}")

    return "\n".join(lines)


def clear_interrupted_state(project_root: Path) -> bool:
    """Clear the interrupted iteration from state.json.

    This removes the last history entry if it was interrupted.

    Args:
        project_root: Root directory of the project

    Returns:
        True if state was cleared, False otherwise
    """
    state_path = project_root / ".ralph" / "state.json"
    if not state_path.exists():
        return False

    state = load_state(state_path)
    history = state.get("history", [])
    if not history:
        return False

    # Remove last entry
    state["history"] = history[:-1]

    # Reset no-progress streak if we're clearing an interrupted iteration
    state["noProgressStreak"] = 0

    # Write back
    try:
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False
