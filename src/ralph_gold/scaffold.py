from __future__ import annotations

import shutil
from pathlib import Path

from . import __version__


def _template_dir() -> Path:
    # templates/ lives alongside this module
    return Path(__file__).resolve().parent / "templates"


def init_project(project_root: Path, force: bool = False) -> None:
    """
    Write default Ralph files into .ralph/ (durable memory + config).
    """
    tdir = _template_dir()
    if not tdir.exists():
        raise RuntimeError("templates directory missing from installation")

    ralph_dir = project_root / ".ralph"
    ralph_dir.mkdir(parents=True, exist_ok=True)

    files = [
        # Prompt variants (plan/build).
        ("PROMPT_build.md", ".ralph/PROMPT_build.md"),
        ("PROMPT_plan.md", ".ralph/PROMPT_plan.md"),
        ("PROMPT_judge.md", ".ralph/PROMPT_judge.md"),
        # Backwards-compatible single prompt.
        ("PROMPT.md", ".ralph/PROMPT.md"),
        ("AGENTS.md", ".ralph/AGENTS.md"),
        ("progress.md", ".ralph/progress.md"),
        # Task trackers (choose one via .ralph/ralph.toml)
        ("PRD.md", ".ralph/PRD.md"),
        ("prd.json", ".ralph/prd.json"),
        # Optional planning context
        ("AUDIENCE_JTBD.md", ".ralph/AUDIENCE_JTBD.md"),
        ("loop.sh", ".ralph/loop.sh"),
        ("ralph.toml", ".ralph/ralph.toml"),
    ]

    for src_name, dst_name in files:
        src = tdir / src_name
        dst = project_root / dst_name
        if dst.exists() and not force:
            continue
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

        # Make convenience scripts executable (best effort).
        if dst_name.endswith(".sh"):
            try:
                dst.chmod(0o755)
            except Exception:
                pass

    # Ensure state dirs exist
    (project_root / ".ralph" / "logs").mkdir(parents=True, exist_ok=True)

    # Specs dir (requirements live here; used by PROMPT_plan.md)
    specs_dir = project_root / ".ralph" / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    specs_readme = specs_dir / "README.md"
    tpl_specs_readme = tdir / "specs_README.md"
    if tpl_specs_readme.exists() and (force or not specs_readme.exists()):
        specs_readme.write_text(tpl_specs_readme.read_text(encoding="utf-8"), encoding="utf-8")
