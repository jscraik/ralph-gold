from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path


def _template_dir() -> Path:
    # templates/ lives alongside this module
    return Path(__file__).resolve().parent / "templates"


def _archive_existing_files(
    project_root: Path, files_to_check: list[tuple[str, str]]
) -> list[str]:
    """Archive existing Ralph files before overwriting.

    Args:
        project_root: Root directory of the project
        files_to_check: List of (src_name, dst_name) tuples to check

    Returns:
        List of archived file paths (relative to project_root)
    """
    ralph_dir = project_root / ".ralph"
    archive_dir = ralph_dir / "archive"

    # Check if any files exist that would be overwritten
    files_to_archive = []
    for _, dst_name in files_to_check:
        dst = project_root / dst_name
        if dst.exists() and dst.is_file():
            files_to_archive.append(dst)

    if not files_to_archive:
        return []

    # Create archive directory with timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive_subdir = archive_dir / timestamp
    archive_subdir.mkdir(parents=True, exist_ok=True)

    archived = []
    for src_file in files_to_archive:
        # Preserve directory structure within archive
        rel_path = src_file.relative_to(project_root)
        archive_dest = archive_subdir / rel_path
        archive_dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.copy2(src_file, archive_dest)
            archived.append(str(rel_path))
        except Exception:
            # Best effort - continue even if one file fails
            pass

    return archived


def init_project(
    project_root: Path,
    force: bool = False,
    format_type: str | None = None,
    solo: bool = False,
) -> list[str]:
    """
    Write default Ralph files into .ralph/ (durable memory + config).

    Args:
        project_root: Root directory of the project
        force: If True, overwrite existing files (after archiving)
        format_type: Task tracker format ("markdown", "yaml", or None for markdown default)
        solo: If True, use the solo-optimized config template

    Returns:
        List of archived file paths (empty if nothing was archived)
    """
    tdir = _template_dir()
    if not tdir.exists():
        raise RuntimeError("templates directory missing from installation")

    ralph_dir = project_root / ".ralph"
    ralph_dir.mkdir(parents=True, exist_ok=True)

    ralph_template = "ralph_solo.toml" if solo else "ralph.toml"
    files = [
        # Prompt variants (plan/build).
        ("PROMPT_build.md", ".ralph/PROMPT_build.md"),
        ("PROMPT_plan.md", ".ralph/PROMPT_plan.md"),
        ("PROMPT_judge.md", ".ralph/PROMPT_judge.md"),
        ("PROMPT_review.md", ".ralph/PROMPT_review.md"),
        # Backwards-compatible single prompt.
        ("PROMPT.md", ".ralph/PROMPT.md"),
        ("AGENTS.md", ".ralph/AGENTS.md"),
        ("progress.md", ".ralph/progress.md"),
        ("FEEDBACK.md", ".ralph/FEEDBACK.md"),
        # Optional planning context
        ("AUDIENCE_JTBD.md", ".ralph/AUDIENCE_JTBD.md"),
        ("loop.sh", ".ralph/loop.sh"),
        (ralph_template, ".ralph/ralph.toml"),
        # Authorization artifacts
        (".ralph/permissions.json", ".ralph/permissions.json"),
    ]

    # Add task tracker files based on format
    if format_type == "yaml":
        files.append(("tasks.yaml", "tasks.yaml"))
    else:
        # Default to markdown (PRD.md)
        files.append(("PRD.md", ".ralph/PRD.md"))

    # Archive existing files if force=True
    archived = []
    if force:
        archived = _archive_existing_files(project_root, files)

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

    # Update ralph.toml to use the correct tracker format
    if format_type:
        _update_config_for_format(project_root, format_type)

    # Ensure state dirs exist
    (project_root / ".ralph" / "logs").mkdir(parents=True, exist_ok=True)
    (project_root / ".ralph" / "receipts").mkdir(parents=True, exist_ok=True)
    (project_root / ".ralph" / "context").mkdir(parents=True, exist_ok=True)
    (project_root / ".ralph" / "attempts").mkdir(parents=True, exist_ok=True)

    # Specs dir (requirements live here; used by PROMPT_plan.md)
    specs_dir = project_root / ".ralph" / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    specs_readme = specs_dir / "README.md"
    tpl_specs_readme = tdir / "specs_README.md"
    if tpl_specs_readme.exists() and (force or not specs_readme.exists()):
        specs_readme.write_text(
            tpl_specs_readme.read_text(encoding="utf-8"), encoding="utf-8"
        )

    return archived


def _update_config_for_format(project_root: Path, format_type: str) -> None:
    """Update ralph.toml to use the specified tracker format.

    Args:
        project_root: Root directory of the project
        format_type: Task tracker format ("markdown", "json", or "yaml")
    """
    config_path = project_root / ".ralph" / "ralph.toml"

    if not config_path.exists():
        return

    # Read current config
    config_text = config_path.read_text(encoding="utf-8")

    # Update the prd file path based on format
    if format_type == "yaml":
        prd_path = "tasks.yaml"
        tracker_kind = "yaml"
    else:  # markdown (default)
        prd_path = ".ralph/PRD.md"
        tracker_kind = "markdown"

    # Replace the prd line in [files] section
    import re

    config_text = re.sub(r'prd\s*=\s*"[^"]*"', f'prd = "{prd_path}"', config_text)

    # Replace or add tracker kind in [tracker] section
    if "[tracker]" in config_text:
        # Update existing tracker section
        config_text = re.sub(
            r'(\[tracker\][^\[]*?)kind\s*=\s*"[^"]*"',
            rf'\1kind = "{tracker_kind}"',
            config_text,
            flags=re.DOTALL,
        )
        # If kind wasn't found, add it after [tracker]
        if f'kind = "{tracker_kind}"' not in config_text:
            config_text = re.sub(
                r"\[tracker\]", f'[tracker]\nkind = "{tracker_kind}"', config_text
            )
    else:
        # Add tracker section at the end
        config_text += f'\n\n[tracker]\nkind = "{tracker_kind}"\n'

    # Write updated config
    config_path.write_text(config_text, encoding="utf-8")
