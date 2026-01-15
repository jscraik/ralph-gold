\
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tomllib  # py>=3.11
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


@dataclass(frozen=True)
class LoopConfig:
    max_iterations: int = 10
    no_progress_limit: int = 3
    rate_limit_per_hour: int = 0  # 0 = disabled
    sleep_seconds_between_iters: int = 0


@dataclass(frozen=True)
class FilesConfig:
    prd: str = "prd.json"
    progress: str = "progress.md"
    prompt: str = "PROMPT.md"
    agents: str = "AGENTS.md"


@dataclass(frozen=True)
class RunnerConfig:
    argv: List[str]


@dataclass(frozen=True)
class GatesConfig:
    """Optional post-iteration quality gates.

    If provided, the loop will run these commands after each agent iteration.
    Failing gates will prevent task completion and block exiting the loop.
    """

    commands: List[str]


@dataclass(frozen=True)
class Config:
    loop: LoopConfig
    files: FilesConfig
    runners: Dict[str, RunnerConfig]
    gates: GatesConfig


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def load_config(project_root: Path) -> Config:
    """
    Load ralph.toml from the project root.

    If missing, returns defaults. This keeps the tool usable even if users
    want to hand-roll configs.
    """
    cfg_path = project_root / "ralph.toml"
    data: Dict[str, Any] = {}
    if cfg_path.exists():
        data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))

    loop_raw = data.get("loop", {}) or {}
    files_raw = data.get("files", {}) or {}
    runners_raw = data.get("runners", {}) or {}
    gates_raw = data.get("gates", {}) or {}

    loop = LoopConfig(
        max_iterations=_coerce_int(loop_raw.get("max_iterations"), 10),
        no_progress_limit=_coerce_int(loop_raw.get("no_progress_limit"), 3),
        rate_limit_per_hour=_coerce_int(loop_raw.get("rate_limit_per_hour"), 0),
        sleep_seconds_between_iters=_coerce_int(loop_raw.get("sleep_seconds_between_iters"), 0),
    )

    files = FilesConfig(
        prd=str(files_raw.get("prd", "prd.json")),
        progress=str(files_raw.get("progress", "progress.md")),
        prompt=str(files_raw.get("prompt", "PROMPT.md")),
        agents=str(files_raw.get("agents", "AGENTS.md")),
    )

    # Default runner argv are intentionally conservative and easy to edit.
    default_runners: Dict[str, RunnerConfig] = {
        "codex": RunnerConfig(argv=["codex", "exec", "--full-auto"]),
        "claude": RunnerConfig(argv=["claude", "-p", "--output-format", "text"]),
        "copilot": RunnerConfig(argv=["copilot", "--prompt"]),
    }

    runners: Dict[str, RunnerConfig] = {}
    for name, rc in default_runners.items():
        raw = runners_raw.get(name, None)
        if isinstance(raw, dict) and isinstance(raw.get("argv"), list):
            runners[name] = RunnerConfig(argv=[str(x) for x in raw["argv"]])
        else:
            runners[name] = rc

    # Also carry any user-defined runners (amp/opencode/etc.) if present.
    for name, raw in runners_raw.items():
        if name in runners:
            continue
        if isinstance(raw, dict) and isinstance(raw.get("argv"), list):
            runners[name] = RunnerConfig(argv=[str(x) for x in raw["argv"]])

    gate_cmds: List[str] = []
    raw_cmds = gates_raw.get("commands", [])
    if isinstance(raw_cmds, list):
        gate_cmds = [str(x) for x in raw_cmds if str(x).strip()]

    gates = GatesConfig(commands=gate_cmds)

    return Config(loop=loop, files=files, runners=runners, gates=gates)
