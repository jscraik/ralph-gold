\
from __future__ import annotations

import shutil
from pathlib import Path

from . import __version__


def _template_dir() -> Path:
    # templates/ lives alongside this module
    return Path(__file__).resolve().parent / "templates"


def init_project(project_root: Path, force: bool = False) -> None:
    """
    Write default Ralph files into the project root.
    """
    tdir = _template_dir()
    if not tdir.exists():
        raise RuntimeError("templates directory missing from installation")

    files = [
        ("PROMPT.md", "PROMPT.md"),
        ("AGENTS.md", "AGENTS.md"),
        ("progress.md", "progress.md"),
        ("prd.json", "prd.json"),
        ("PRD.md", "PRD.md"),
        ("ralph.toml", "ralph.toml"),
    ]

    for src_name, dst_name in files:
        src = tdir / src_name
        dst = project_root / dst_name
        if dst.exists() and not force:
            continue
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    # Ensure state dir exists
    (project_root / ".ralph" / "logs").mkdir(parents=True, exist_ok=True)
