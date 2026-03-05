from __future__ import annotations

import re
import subprocess
from pathlib import Path

import tomllib

from ralph_gold import __version__


def test_pyproject_uses_dynamic_version_from_init() -> None:
    root = Path(__file__).parent.parent
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))

    project = pyproject["project"]
    assert "version" not in project
    assert "version" in project.get("dynamic", [])

    hatch_version = pyproject["tool"]["hatch"]["version"]
    assert hatch_version.get("path") == "src/ralph_gold/__init__.py"


def test_runtime_version_matches_latest_changelog_heading() -> None:
    root = Path(__file__).parent.parent
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")

    match = re.search(
        r"^## \[([0-9]+\.[0-9]+\.[0-9]+)\]\s+-\s+\d{4}-\d{2}-\d{2}\s*$",
        changelog,
        flags=re.MULTILINE,
    )
    assert match is not None
    assert match.group(1) == __version__


def test_version_sync_script_passes() -> None:
    root = Path(__file__).parent.parent
    result = subprocess.run(
        ["python3", "scripts/check_version_sync.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert f"Version sync OK: {__version__}" in result.stdout
