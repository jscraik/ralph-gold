#!/usr/bin/env python3
"""Validate Ralph version single-source discipline.

Checks:
1. pyproject uses dynamic version sourcing.
2. Hatch version path points to src/ralph_gold/__init__.py.
3. Runtime __version__ matches latest CHANGELOG release heading.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - fallback for older interpreters
    import tomli as tomllib  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = ROOT / "pyproject.toml"
INIT_PATH = ROOT / "src" / "ralph_gold" / "__init__.py"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']\s*$', re.MULTILINE)
CHANGELOG_RE = re.compile(r"^## \[([0-9]+\.[0-9]+\.[0-9]+)\]\s+-\s+\d{4}-\d{2}-\d{2}\s*$", re.MULTILINE)


def _read_runtime_version() -> str:
    init_text = INIT_PATH.read_text(encoding="utf-8")
    match = VERSION_RE.search(init_text)
    if match is None:
        raise ValueError(f"Could not locate __version__ in {INIT_PATH}")
    return match.group(1)


def _read_latest_changelog_version() -> str:
    changelog_text = CHANGELOG_PATH.read_text(encoding="utf-8")
    match = CHANGELOG_RE.search(changelog_text)
    if match is None:
        raise ValueError(
            f"Could not locate a release heading like '## [X.Y.Z] - YYYY-MM-DD' in {CHANGELOG_PATH}"
        )
    return match.group(1)


def main() -> int:
    errors: list[str] = []

    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    project = pyproject.get("project", {})
    dynamic = project.get("dynamic", [])
    static_version = project.get("version")

    if static_version is not None:
        errors.append(
            "pyproject.toml must not declare [project].version directly; use dynamic version sourcing."
        )
    if "version" not in dynamic:
        errors.append(
            "pyproject.toml must include [project].dynamic = [\"version\", ...]."
        )

    hatch_version = pyproject.get("tool", {}).get("hatch", {}).get("version", {})
    hatch_path = hatch_version.get("path")
    if hatch_path != "src/ralph_gold/__init__.py":
        errors.append(
            "pyproject.toml must set [tool.hatch.version].path = \"src/ralph_gold/__init__.py\"."
        )

    runtime_version = _read_runtime_version()
    changelog_version = _read_latest_changelog_version()
    if runtime_version != changelog_version:
        errors.append(
            "Version drift detected: "
            f"runtime __version__ ({runtime_version}) != latest CHANGELOG entry ({changelog_version})."
        )

    if errors:
        print("Version sync check failed:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print(f"Version sync OK: {runtime_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
