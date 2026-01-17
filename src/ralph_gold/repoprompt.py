from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .config import RepoPromptConfig


class RepoPromptError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepoPromptRun:
    argv: List[str]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float


def _base_args(cfg: RepoPromptConfig) -> List[str]:
    args: List[str] = [cfg.cli]
    if cfg.window_id is not None:
        args.extend(["-w", str(cfg.window_id)])
    if cfg.tab:
        args.extend(["-t", cfg.tab])
    return args


def _sanitize_one_line(text: str) -> str:
    t = " ".join(text.split())
    return t.replace('"', "'")


def run_exec(
    commands: str,
    *,
    cfg: RepoPromptConfig,
    cwd: Path,
    timeout_seconds: Optional[int] = None,
) -> RepoPromptRun:
    timeout = timeout_seconds if timeout_seconds is not None else cfg.timeout_seconds
    argv = _base_args(cfg) + ["-e", commands]
    t0 = time.time()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise RepoPromptError(f"rp-cli not found: {cfg.cli}") from e
    except subprocess.TimeoutExpired as e:
        raise RepoPromptError(f"rp-cli timed out after {timeout}s") from e
    dt = time.time() - t0
    return RepoPromptRun(
        argv=argv,
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        duration_seconds=dt,
    )


def build_context_pack(
    *,
    cfg: RepoPromptConfig,
    task_id: str,
    task_title: str,
    acceptance: List[str],
    out_path: Path,
    cwd: Path,
    anchor_path: Optional[Path] = None,
) -> Tuple[RepoPromptRun, str]:
    acc = " | ".join(a.strip() for a in acceptance if a.strip())
    extra = f" Anchor: {anchor_path}" if anchor_path else ""
    instructions = (
        f"Task {task_id}: {task_title}. Acceptance: {acc}. "
        f"Build a context pack (relevant files/slices/codemaps). Discovery only; do not implement.{extra}"
    )
    instructions = _sanitize_one_line(instructions)

    cmds: List[str] = []
    if cfg.workspace:
        cmds.append(f'workspace switch "{_sanitize_one_line(cfg.workspace)}"')

    builder_type = cfg.builder_type or "clarify"
    cmds.append(f'builder "{instructions}" --type {builder_type}')

    if cfg.copy_preset:
        preset = _sanitize_one_line(cfg.copy_preset)
        cmds.append(f'prompt preset "{preset}"')

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmds.append(f'prompt export "{out_path}"')

    chain = " && ".join(cmds)
    run = run_exec(chain, cfg=cfg, cwd=cwd)
    return run, instructions


def run_review(*, message: str, cfg: RepoPromptConfig, cwd: Path) -> RepoPromptRun:
    msg = _sanitize_one_line(message)
    chain = f'chat_send new_chat=true mode=review message="{msg}"'
    return run_exec(chain, cfg=cfg, cwd=cwd)
