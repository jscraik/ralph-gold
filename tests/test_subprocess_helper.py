"""Tests for subprocess helper binary-safe stdin handling."""

from __future__ import annotations

import sys

from ralph_gold.subprocess_helper import run_subprocess, run_subprocess_live


def test_run_subprocess_coerces_bytes_input_when_text_disabled() -> None:
    argv = [
        sys.executable,
        "-c",
        "import sys; data = sys.stdin.buffer.read(); sys.stdout.buffer.write(data);",
    ]
    result = run_subprocess(
        argv,
        input_text=b"hello",
        text=False,
    )
    assert result.returncode == 0
    assert result.stdout == "hello"


def test_run_subprocess_live_coerces_bytes_input_when_text_disabled() -> None:
    argv = [
        sys.executable,
        "-c",
        "import sys; data = sys.stdin.buffer.read(); sys.stdout.buffer.write(data)",
    ]
    result = run_subprocess_live(
        argv,
        input_text=b"world",
        capture_output=True,
        forward_output=False,
        text=False,
    )
    assert result.returncode == 0
    assert result.stdout == "world"


def test_run_subprocess_live_handles_closed_stdin_pipe() -> None:
    argv = [
        sys.executable,
        "-c",
        "import os; os._exit(0)",
    ]
    result = run_subprocess_live(
        argv,
        input_text="late",
        capture_output=False,
        forward_output=False,
    )
    assert result.returncode == 0
