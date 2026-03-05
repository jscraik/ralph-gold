"""JSON contract tests for CLI machine interface."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def _write_text_output_config(tmp_path: Path) -> None:
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    (ralph_dir / "ralph.toml").write_text(
        """
[output]
verbosity = "normal"
format = "text"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_global_format_flag_enables_json_for_doctor(tmp_path: Path) -> None:
    _write_text_output_config(tmp_path)

    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "--format", "json", "doctor"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip(), "expected JSON stdout"
    payload = json.loads(result.stdout)
    assert payload["cmd"] == "doctor"
    assert payload["schema_version"] == "ralph.cli.v1"
    assert "timestamp" in payload
    assert payload["exit_code"] == result.returncode


def test_env_format_override_enables_json_output(tmp_path: Path) -> None:
    _write_text_output_config(tmp_path)

    env = dict(os.environ)
    env["RALPH_FORMAT"] = "json"
    result = subprocess.run(
        ["uv", "run", "python", "-m", "ralph_gold.cli", "doctor"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.stdout.strip(), "expected JSON stdout"
    payload = json.loads(result.stdout)
    assert payload["cmd"] == "doctor"
    assert payload["schema_version"] == "ralph.cli.v1"
    assert "timestamp" in payload
    assert payload["exit_code"] == result.returncode


def test_json_fallback_envelope_for_commands_without_json_branch(tmp_path: Path) -> None:
    _write_text_output_config(tmp_path)

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "ralph_gold.cli",
            "--format",
            "json",
            "init",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip(), "expected JSON fallback payload"
    payload = json.loads(result.stdout)
    assert payload["cmd"] == "init"
    assert payload["schema_version"] == "ralph.cli.v1"
    assert "timestamp" in payload
    assert payload["exit_code"] == result.returncode
