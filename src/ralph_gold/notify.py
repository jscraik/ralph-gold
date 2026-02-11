"""Best-effort OS notifications for Ralph Gold.

Security goals:
- Never invoke a shell; always execute argv lists.
- Treat notification content (task titles, reasons, paths) as untrusted input and
  escape appropriately for the backend.
"""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from typing import Literal, Optional, Sequence

from .output import print_output
from .subprocess_helper import run_subprocess, which


NotifyBackend = Literal["none", "macos", "linux", "windows", "command"]


@dataclass(frozen=True)
class NotifyConfig:
    enabled: bool = True
    backend: str = "auto"  # auto|macos|linux|windows|command|none
    command_argv: Sequence[str] = ()


def _clip(text: str, limit: int = 500) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[:limit] + "…"


def _escape_applescript_string(value: str) -> str:
    """Escape a string for embedding inside AppleScript double quotes."""

    s = value or ""
    # Escape backslashes first, then quotes.
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    # Normalize newlines and escape them.
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
    return s


def resolve_backend(backend: str) -> NotifyBackend:
    b = (backend or "").strip().lower()
    if b in {"none", "off", "false", "0"}:
        return "none"
    if b in {"macos", "linux", "windows", "command"}:
        return b  # type: ignore[return-value]
    if b != "auto":
        # Unknown value: fall back to auto.
        b = "auto"

    sysname = platform.system().lower()
    if sysname == "darwin" and which("osascript"):
        return "macos"
    if sysname == "linux" and which("notify-send"):
        return "linux"
    if sysname == "windows" and which("powershell"):
        return "windows"
    return "none"


def send_notification(
    *,
    title: str,
    message: str,
    backend: str = "auto",
    command_argv: Optional[Sequence[str]] = None,
) -> bool:
    """Send a best-effort OS notification.

    Returns:
        True if a backend was invoked successfully (not necessarily delivered),
        False otherwise.
    """

    be = resolve_backend(backend)
    if be == "none":
        return False

    t = _clip(title, 120)
    m = _clip(message, 500)

    try:
        if be == "macos":
            if not which("osascript"):
                return False
            script = (
                f'display notification "{_escape_applescript_string(m)}" '
                f'with title "{_escape_applescript_string(t)}"'
            )
            res = run_subprocess(["osascript", "-e", script], check=False)
            return res.returncode == 0

        if be == "linux":
            if not which("notify-send"):
                return False
            res = run_subprocess(["notify-send", t, m], check=False)
            return res.returncode == 0

        if be == "windows":
            # Best-effort: many environments won't have toast support available.
            # We avoid installing modules/deps; fall back to a no-op invocation.
            if not which("powershell"):
                return False
            cmd = (
                "$t=@'\n"
                + m.replace("'", "''")
                + "\n'@; "
                + "Write-Host $t"
            )
            res = run_subprocess(
                ["powershell", "-NoProfile", "-Command", cmd],
                check=False,
            )
            return res.returncode == 0

        if be == "command":
            argv = list(command_argv or [])
            if not argv:
                return False
            argv = [str(x) for x in argv] + [t, m]
            res = run_subprocess(argv, check=False)
            return res.returncode == 0

        return False
    except Exception as e:
        # Never crash the caller (supervisor) due to notification issues.
        print_output(f"Notification failed ({be}): {e}", level="verbose")
        return False


def default_title(repo_name: str) -> str:
    name = (repo_name or "").strip() or os.path.basename(os.getcwd()) or "Ralph"
    return f"Ralph: {name}"

