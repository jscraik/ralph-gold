# -*- coding: utf-8 -*-
"""Enhanced gate logic for smart gate selection and fail-fast execution."""
from __future__ import annotations

import fnmatch
import logging
from pathlib import Path
from typing import List

from .subprocess_helper import run_subprocess

logger = logging.getLogger(__name__)


def get_changed_files(project_root: Path) -> List[Path]:
    """Get list of changed files from git diff.

    Uses git diff --name-only HEAD to get changed files (staged + unstaged).
    Returns empty list if not in a git repo or on error.

    Args:
        project_root: Project root directory

    Returns:
        List of changed file paths (absolute paths)
    """
    try:
        # Check if we are inside a git repository first
        # git diff --name-only HEAD fails if not a git repo or no commits yet.
        # Acceptance criteria: fail-open for safety (empty list)
        result = run_subprocess(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=project_root,
            check=False,
            capture_output=True,
        )
        if result.failed:
            # Not a git repo or no HEAD yet (empty repo)
            return []

        changed: List[Path] = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line:
                # Ensure the path is joined to project root
                full_path = project_root / line
                changed.append(full_path)
        return changed
    except Exception as e:
        logger.debug(f"Failed to get changed files: {e}")
        return []


def should_skip_gates(
    changed_files: List[Path], skip_patterns: List[str], project_root: Path
) -> bool:
    """Check if gates should be skipped based on changed files.

    Gates are skipped only if ALL changed files match at least one
    of the skip patterns. If any file doesn't match, gates must run.

    Args:
        changed_files: List of changed file paths (absolute paths)
        skip_patterns: List of glob patterns (e.g., ["**/*.md", "**/*.toml"])
        project_root: Project root directory (for path normalization)

    Returns:
        True if gates should be skipped, False otherwise
    """
    if not skip_patterns:
        return False

    if not changed_files:
        return False

    # Check if ALL changed files match skip patterns
    # If ANY file doesn't match, gates must run
    for file_path in changed_files:
        # Convert absolute path to relative for pattern matching
        try:
            rel_path = file_path.relative_to(project_root)
        except ValueError:
            # File is outside project root, don't skip
            return False

        # Convert to string for pattern matching
        rel_path_str = str(rel_path)

        # Check if the file matches any of the skip patterns
        matched = False
        for pattern in skip_patterns:
            # Handle ** patterns by converting to fnmatch-compatible pattern
            # **/*.md -> *.md (for any file) or **/*.md (for subdirectories)
            if "**" in pattern:
                # For recursive patterns, check both the full path and filename
                simple_pattern = pattern.replace("**/", "")
                if (
                    fnmatch.fnmatchcase(rel_path_str, simple_pattern)
                    or fnmatch.fnmatchcase(rel_path_str, pattern)
                    or fnmatch.fnmatchcase(rel_path.name, simple_pattern)
                ):
                    matched = True
                    break
            elif fnmatch.fnmatchcase(rel_path_str, pattern):
                matched = True
                break

        if not matched:
            return False  # At least one file doesn't match skip patterns

    return True  # All files match skip patterns
