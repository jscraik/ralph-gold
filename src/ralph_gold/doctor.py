from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ToolStatus:
    name: str
    found: bool
    path: Optional[str]
    version: Optional[str]
    hint: Optional[str]


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _version(cmd: List[str]) -> Optional[str]:
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, check=False)
        out = (cp.stdout or "").strip()
        err = (cp.stderr or "").strip()
        text = out if out else err
        if text:
            # first line only
            return text.splitlines()[0][:200]
        return None
    except Exception:
        return None


def check_tools() -> List[ToolStatus]:
    checks = [
        ("git", ["git", "--version"], "Install git and run `git init` in your project."),
        ("uv", ["uv", "--version"], "Install uv (https://docs.astral.sh/uv/)."),
        ("codex", ["codex", "--version"], "Install the Codex CLI (see OpenAI Codex docs)."),
        ("claude", ["claude", "--version"], "Install Claude Code CLI (see Anthropic Claude Code docs)."),
        ("copilot", ["copilot", "--version"], "Install GitHub Copilot CLI (or configure a different runner in ralph.toml)."),
        ("gh", ["gh", "--version"], "Optional: GitHub CLI, useful for Copilot workflows."),
    ]

    results: List[ToolStatus] = []
    for name, ver_cmd, hint in checks:
        path = _which(name)
        found = path is not None
        version = _version(ver_cmd) if found else None
        results.append(ToolStatus(name=name, found=found, path=path, version=version, hint=None if found else hint))
    return results
