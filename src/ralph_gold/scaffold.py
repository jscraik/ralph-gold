from __future__ import annotations

from pathlib import Path


def _template_dir() -> Path:
    # templates/ lives alongside this module
    return Path(__file__).resolve().parent / "templates"


def init_project(project_root: Path, force: bool = False) -> None:
    """
    Write default Ralph files into .ralph/ directory.
    """
    tdir = _template_dir()
    if not tdir.exists():
        raise RuntimeError("templates directory missing from installation")

    ralph_dir = project_root / ".ralph"
    ralph_dir.mkdir(parents=True, exist_ok=True)

    files = [
        ("README.md", "README.md"),
        ("PROMPT.md", "PROMPT.md"),
        ("AGENTS.md", "AGENTS.md"),
        ("progress.md", "progress.md"),
        ("prd.json", "prd.json"),
        ("PRD.md", "PRD.md"),
        ("ralph.toml", "ralph.toml"),
    ]

    for src_name, dst_name in files:
        src = tdir / src_name
        dst = ralph_dir / dst_name
        if dst.exists() and not force:
            continue
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    # Ensure logs dir exists
    (ralph_dir / "logs").mkdir(parents=True, exist_ok=True)

    # Append ralph gitignore rules to project .gitignore if not already present
    gitignore_path = project_root / ".gitignore"
    ralph_gitignore = tdir / "gitignore.ralph"
    if ralph_gitignore.exists():
        ralph_rules = ralph_gitignore.read_text(encoding="utf-8")
        marker = "# Ralph runtime state"
        existing = ""
        if gitignore_path.exists():
            existing = gitignore_path.read_text(encoding="utf-8")
        if marker not in existing:
            with gitignore_path.open("a", encoding="utf-8") as f:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                f.write("\n" + ralph_rules)
