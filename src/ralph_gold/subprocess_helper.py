"""Unified subprocess execution with proper error handling.

This module provides a centralized interface for running subprocess commands
with consistent error handling, timeout support, and result capture.

Security Considerations (OWASP ASVS 5.0.0):
- V5.2.1: Verify that the application uses secure channels for communications
- V5.2.2: Verify that the application validates and sanitizes all input
  passed to system commands

Benefits:
- Consistent error handling across all subprocess calls
- Timeout support to prevent hangs
- Standardized result capture
- Better error messages for debugging
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class SubprocessResult:
    """Result of a subprocess execution.

    Attributes:
        returncode: The exit code of the process (0 = success)
        stdout: Standard output (captured if capture_output=True)
        stderr: Standard error output (captured if capture_output=True)
        timed_out: True if the command exceeded the timeout
        cmd_str: String representation of the command (for logging)
    """

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    cmd_str: str = ""

    @property
    def success(self) -> bool:
        """True if the command exited with code 0."""
        return self.returncode == 0

    @property
    def failed(self) -> bool:
        """True if the command exited with a non-zero code."""
        return self.returncode != 0


def run_subprocess(
    argv: List[str],
    cwd: Optional[Path] = None,
    check: bool = False,
    timeout: Optional[int] = None,
    capture_output: bool = True,
    text: bool = True,
    env: Optional[dict] | None = None,
) -> SubprocessResult:
    """Run subprocess with unified error handling.

    This function provides a consistent interface to subprocess.run() with:
    - Standardized error handling
    - Timeout support (converts TimeoutExpired to RuntimeError)
    - Command not found detection
    - Structured result object

    Args:
        argv: Command and arguments as a list (e.g., ["git", "status"])
        cwd: Working directory for the command
        check: If True, raise RuntimeError on non-zero exit
        timeout: Maximum seconds to wait before raising TimeoutExpired
        capture_output: If True, capture stdout and stderr
        text: If True, return output as text (not bytes)
        env: Environment variables to pass to the subprocess

    Returns:
        SubprocessResult with returncode, stdout, stderr

    Raises:
        RuntimeError: If command times out, not found, or check=True and non-zero exit

    Examples:
        >>> result = run_subprocess(["git", "status"])
        >>> if result.success:
        ...     print(result.stdout)
        >>> else:
        ...     print(f"Error: {result.stderr}")

        >>> result = run_subprocess(["ls", "-la"], timeout=5)
        >>> print(result.stdout)
    """
    cmd_str = " ".join(argv)

    kwargs: dict = {
        "capture_output": capture_output,
        "text": text,
    }

    if cwd is not None:
        kwargs["cwd"] = str(cwd)
    if timeout is not None:
        kwargs["timeout"] = timeout
    if env is not None:
        kwargs["env"] = env

    try:
        cp = subprocess.run(argv, **kwargs)
        result = SubprocessResult(
            returncode=cp.returncode,
            stdout=(cp.stdout or "") if capture_output else "",
            stderr=(cp.stderr or "") if capture_output else "",
            cmd_str=cmd_str,
        )

        if check and result.failed:
            raise RuntimeError(
                f"Command failed with exit code {result.returncode}: {cmd_str}\n"
                f"stderr: {result.stderr}"
            )

        return result

    except subprocess.TimeoutExpired as e:
        # Provide more helpful timeout error
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
        raise RuntimeError(
            f"Command timed out after {timeout}s: {cmd_str}\n"
            f"Partial output:\n{stderr[:500]}"
        ) from e

    except FileNotFoundError:
        raise RuntimeError(
            f"Command not found: {argv[0]}\n"
            f"Ensure the command is installed and available in PATH."
        )


def run_subprocess_live(
    argv: List[str],
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
    text: bool = True,
    env: Optional[dict] | None = None,
) -> subprocess.CompletedProcess:
    """Run subprocess with live output (no capture).

    Use this for commands that should stream output to the terminal
    (e.g., agent runners, long-running build commands).

    Args:
        argv: Command and arguments
        cwd: Working directory
        timeout: Maximum seconds to wait
        text: If True, handle output as text
        env: Environment variables

    Returns:
        subprocess.CompletedProcess with the result

    Raises:
        RuntimeError: On timeout or command not found

    Examples:
        >>> result = run_subprocess_live(["npm", "install"])
        >>> print(f"Exit code: {result.returncode}")
    """
    cmd_str = " ".join(argv)

    kwargs: dict = {
        "capture_output": False,
        "text": text,
    }

    if cwd is not None:
        kwargs["cwd"] = str(cwd)
    if timeout is not None:
        kwargs["timeout"] = timeout
    if env is not None:
        kwargs["env"] = env

    try:
        return subprocess.run(argv, **kwargs)

    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Command timed out after {timeout}s: {cmd_str}") from e

    except FileNotFoundError:
        raise RuntimeError(
            f"Command not found: {argv[0]}\n"
            f"Ensure the command is installed and available in PATH."
        )


def which(cmd: str) -> Optional[str]:
    """Find a command in PATH, equivalent to shutil.which().

    Args:
        cmd: Command name to search for

    Returns:
        Path to the command, or None if not found

    Examples:
        >>> git_path = which("git")
        >>> if git_path:
        ...     print(f"Git found at: {git_path}")
    """
    import shutil

    return shutil.which(cmd)


def check_command_available(cmd: str) -> bool:
    """Check if a command is available in PATH.

    Args:
        cmd: Command name to check

    Returns:
        True if command is available, False otherwise

    Examples:
        >>> if check_command_available("git"):
        ...     print("Git is available")
    """
    return which(cmd) is not None
