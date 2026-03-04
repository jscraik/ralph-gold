from __future__ import annotations

import sys

from ralph_gold.subprocess_helper import run_subprocess


def test_run_subprocess_supports_stdin_text() -> None:
    result = run_subprocess(
        [sys.executable, "-c", "import sys; print(sys.stdin.read().strip())"],
        stdin_text="hello from stdin\n",
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "hello from stdin"
