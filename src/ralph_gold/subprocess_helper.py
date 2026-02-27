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
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Union
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


def _coerce_input_payload(raw: str | bytes, text: bool) -> str | bytes:
    """Normalize input payload for subprocess APIs.

    Args:
        raw: Input payload to pass into subprocess stdin
        text: Whether subprocess text mode is enabled

    Returns:
        A payload type compatible with subprocess stdin/input handling.
    """
    if text:
        if isinstance(raw, (bytes, bytearray)):
            return raw.decode("utf-8", errors="replace")
        return str(raw)
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return str(raw).encode("utf-8")


def _coerce_output_payload(raw: str | bytes | None) -> str:
    """Normalize subprocess output to text."""
    if raw is None:
        return ""
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw).decode("utf-8", errors="replace")
    return str(raw)


def run_subprocess(
    argv: List[str],
    cwd: Optional[Path] = None,
    check: bool = False,
    timeout: Optional[int] = None,
    capture_output: bool = True,
    input_text: Optional[str | bytes] = None,
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
        input_text: Optional bytes or text passed to process stdin
        text: If True, subprocess is run in text mode. Output is normalized
            to text for callers in either case.
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
    if input_text is not None:
        kwargs["input"] = _coerce_input_payload(input_text, text)

    try:
        cp = subprocess.run(argv, **kwargs)
        result = SubprocessResult(
            returncode=cp.returncode,
            stdout=_coerce_output_payload(cp.stdout) if capture_output else "",
            stderr=_coerce_output_payload(cp.stderr) if capture_output else "",
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
        if e.stderr is None:
            stderr = ""
        elif isinstance(e.stderr, (bytes, bytearray)):
            stderr = e.stderr.decode("utf-8", errors="replace")
        else:
            stderr = str(e.stderr)
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
    capture_output: bool = True,
    input_text: Optional[str | bytes] = None,
    forward_output: bool = True,
    text: bool = True,
    env: Optional[dict] | None = None,
) -> SubprocessResult:
    """Run subprocess with live output and optional capture.

    Use this for commands that should stream output to the terminal
    (e.g., agent runners, long-running build commands).

    Args:
        argv: Command and arguments
        cwd: Working directory
        timeout: Maximum seconds to wait
        capture_output: If True, capture stdout and stderr in the returned result
        input_text: Optional bytes or text passed to process stdin
        forward_output: If True, write streaming output to terminal in real time
        text: If True, handle output as text
        env: Environment variables

    Returns:
        SubprocessResult with captured output

    Raises:
        RuntimeError: On timeout or command not found

    Examples:
        >>> result = run_subprocess_live(["npm", "install"])
        >>> print(f"Exit code: {result.returncode}")
    """
    cmd_str = " ".join(argv)

    def _coerce_stream_line(line: Union[str, bytes]) -> str:
        if isinstance(line, (bytes, bytearray)):
            return line.decode("utf-8", errors="replace")
        return str(line)

    kwargs: dict = {
        "stdin": subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        "text": text,
    }

    stream_enabled = capture_output or forward_output
    if stream_enabled:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    else:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL

    if cwd is not None:
        kwargs["cwd"] = str(cwd)
    if env is not None:
        kwargs["env"] = env

    timeout_seconds: Optional[int] = timeout
    timed_out = False

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def _stream_reader(
        stream: IO[str] | IO[bytes],
        sink: list[str],
        forward_to_stderr: bool = False,
    ) -> None:
        sentinel = "" if text else b""
        reader = stream.readline
        while True:
            line = reader()
            if line == sentinel:
                break

            text_line = _coerce_stream_line(line)
            if forward_output:
                print(
                    text_line,
                    end="",
                    flush=True,
                    file=sys.stderr if forward_to_stderr else sys.stdout,
                )
            if capture_output:
                sink.append(text_line)

    try:
        with subprocess.Popen(**{**kwargs, "args": argv}) as proc:
            if input_text is not None and proc.stdin is not None:
                try:
                    payload = _coerce_input_payload(input_text, text)
                    proc.stdin.write(payload)  # type: ignore[arg-type]
                    proc.stdin.flush()
                except OSError:
                    # If the subprocess exits before consuming stdin, continue.
                    # The final return code will still reflect subprocess state.
                    pass
                finally:
                    proc.stdin.close()

            readers: list[threading.Thread] = []
            if proc.stdout is not None:
                stdout_reader = threading.Thread(
                    target=_stream_reader,
                    args=(proc.stdout, stdout_lines, False),
                    daemon=True,
                )
                stdout_reader.start()
                readers.append(stdout_reader)

            if proc.stderr is not None and proc.stderr is not proc.stdout:
                stderr_reader = threading.Thread(
                    target=_stream_reader,
                    args=(proc.stderr, stderr_lines, True),
                    daemon=True,
                )
                stderr_reader.start()
                readers.append(stderr_reader)

            try:
                proc.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired as e:
                timed_out = True
                proc.kill()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass

                for reader in readers:
                    reader.join(timeout=1.0)

                partial_stdout = "".join(stdout_lines)
                partial_stderr = "".join(stderr_lines)
                raise RuntimeError(
                    f"Command timed out after {timeout_seconds}s: {cmd_str}\n"
                    f"Partial stdout:\n{partial_stdout[:500]}\n"
                    f"Partial stderr:\n{partial_stderr[:500]}"
                ) from e

            for reader in readers:
                reader.join()

            return SubprocessResult(
                returncode=proc.returncode if proc.returncode is not None else -1,
                stdout="".join(stdout_lines) if capture_output else "",
                stderr="".join(stderr_lines) if capture_output else "",
                timed_out=timed_out,
                cmd_str=cmd_str,
            )

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
