"""Cleanup utilities for Ralph workspace artifacts.

This module provides functions to clean old files and directories
from the .ralph workspace, including logs, archives, receipts, and context.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple


logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""
    files_removed: int
    bytes_freed: int
    directories_removed: int
    errors: List[str]


def _get_file_age_days(path: Path) -> float:
    """Get the age of a file in days.
    
    Args:
        path: Path to the file
        
    Returns:
        Age in days (0.0 if file cannot be accessed)
    """
    try:
        mtime = path.stat().st_mtime
        age = datetime.now(timezone.utc).timestamp() - mtime
        return age / 86400.0  # Convert seconds to days
    except OSError as e:
        logger.debug("Failed to get mtime for %s: %s", path, e)
        return 0.0


def _get_directory_size(path: Path) -> int:
    """Get the total size of a directory in bytes (recursive).
    
    Args:
        path: Path to the directory
        
    Returns:
        Total size in bytes (0 if directory cannot be accessed)
    """
    try:
        total = 0
        for item in path.rglob("*"):
            try:
                if item.is_file():
                    total += item.stat().st_size
            except OSError as e:
                logger.debug("Failed to get size for %s: %s", item, e)
                continue
        return total
    except OSError as e:
        logger.debug("Failed to calculate directory size for %s: %s", path, e)
        return 0


def _cleanup_files_by_age(
    project_root: Path,
    subdir: str,
    pattern: str,
    older_than_days: int,
    dry_run: bool,
    remove_dirs: bool = False,
) -> CleanupResult:
    """Generic cleanup function for files or directories by age.
    
    Args:
        project_root: Root directory of the project
        subdir: Subdirectory under .ralph/ to clean (e.g., 'logs', 'archives')
        pattern: Glob pattern for files to clean (e.g., '*.json', '*.tar.gz')
        older_than_days: Remove files older than this many days
        dry_run: If True, don't actually delete files
        remove_dirs: If True, remove directories as well as files
        
    Returns:
        CleanupResult with statistics on files removed and bytes freed
    """
    target_dir = project_root / ".ralph" / subdir
    
    if not target_dir.exists():
        return CleanupResult(files_removed=0, bytes_freed=0, directories_removed=0, errors=[])
    
    # Scan for files matching pattern
    try:
        if remove_dirs:
            items = list(target_dir.iterdir())
        else:
            items = list(target_dir.glob(pattern))
    except OSError as e:
        logger.debug("Failed to scan %s: %s", target_dir, e)
        return CleanupResult(files_removed=0, bytes_freed=0, directories_removed=0, errors=[])
    
    removed_count = 0
    total_size = 0
    directories_removed = 0
    errors: List[str] = []
    cutoff_time = datetime.now(timezone.utc).timestamp() - (older_than_days * 86400)
    
    for item_path in items:
        # Skip if not the right type
        if remove_dirs and not item_path.is_dir():
            continue
        if not remove_dirs and not item_path.is_file():
            continue
        
        try:
            item_mtime = item_path.stat().st_mtime
        except OSError as e:
            logger.debug("Failed to get mtime for %s: %s", item_path, e)
            continue
        
        # Skip if newer than cutoff
        if item_mtime > cutoff_time:
            continue
        
        # Remove file or directory
        try:
            item_size = item_path.stat().st_size
            if remove_dirs and item_path.is_dir():
                # For directories, calculate total size and file count
                dir_size = _get_directory_size(item_path)
                file_count = sum(1 for _ in item_path.rglob("*") if _.is_file())
                
                if not dry_run:
                    shutil.rmtree(item_path)
                
                total_size += dir_size
                removed_count += file_count
                directories_removed += 1
            else:
                if not dry_run:
                    item_path.unlink()
                total_size += item_size
                removed_count += 1
        except OSError as e:
            logger.debug("Failed to remove %s: %s", item_path, e)
            continue
    
    return CleanupResult(
        files_removed=removed_count,
        bytes_freed=total_size,
        directories_removed=directories_removed,
        errors=errors
    )


def _merge_results(a: CleanupResult, b: CleanupResult) -> CleanupResult:
    return CleanupResult(
        files_removed=int(a.files_removed) + int(b.files_removed),
        bytes_freed=int(a.bytes_freed) + int(b.bytes_freed),
        directories_removed=int(a.directories_removed) + int(b.directories_removed),
        errors=[*a.errors, *b.errors],
    )


def clean_logs(
    project_root: Path,
    older_than_days: int = 30,
    dry_run: bool = False,
) -> CleanupResult:
    """Clean old log files from .ralph/logs/.

    Removes log files older than the specified number of days.
    This helps manage disk usage by removing old execution logs.

    Args:
        project_root: Root directory of the project
        older_than_days: Remove logs older than this many days (default: 30)
        dry_run: If True, scan and report but don't delete (default: False)

    Returns:
        CleanupResult with statistics on files removed and bytes freed

    Raises:
        ValueError: If older_than_days is negative
    """
    if older_than_days < 0:
        raise ValueError("older_than_days must be non-negative")

    if dry_run:
        logger.info("Dry run: would clean logs older than %d days", older_than_days)

    return _cleanup_files_by_age(
        project_root=project_root,
        subdir="logs",
        pattern="*",
        older_than_days=older_than_days,
        dry_run=dry_run,
        remove_dirs=False,
    )


def clean_archives(
    project_root: Path,
    older_than_days: int = 90,
    dry_run: bool = False,
) -> CleanupResult:
    """Clean old archive files from .ralph/archive/.

    Removes archive files older than the specified number of days.
    Archives are compressed backups of old attempts.

    Args:
        project_root: Root directory of the project
        older_than_days: Remove archives older than this many days (default: 90)
        dry_run: If True, scan and report but don't delete (default: False)

    Returns:
        CleanupResult with statistics on files removed and bytes freed

    Raises:
        ValueError: If older_than_days is negative
    """
    if older_than_days < 0:
        raise ValueError("older_than_days must be non-negative")

    if dry_run:
        logger.info("Dry run: would clean archives older than %d days", older_than_days)

    # Archives are commonly stored as timestamped directories (from init --force)
    # but may also exist as compressed files.
    dir_result = _cleanup_files_by_age(
        project_root=project_root,
        subdir="archive",
        pattern="*",
        older_than_days=older_than_days,
        dry_run=dry_run,
        remove_dirs=True,
    )
    file_result = _cleanup_files_by_age(
        project_root=project_root,
        subdir="archive",
        pattern="*.tar.gz",
        older_than_days=older_than_days,
        dry_run=dry_run,
        remove_dirs=False,
    )
    return _merge_results(dir_result, file_result)


def clean_receipts(
    project_root: Path,
    older_than_days: int = 90,
    dry_run: bool = False,
) -> CleanupResult:
    """Clean old receipt files from .ralph/receipts/.

    Removes receipt files older than the specified number of days.
    Receipts track completed iterations and are useful for debugging.

    Args:
        project_root: Root directory of the project
        older_than_days: Remove receipts older than this many days (default: 90)
        dry_run: If True, scan and report but don't delete (default: False)

    Returns:
        CleanupResult with statistics on files removed and bytes freed

    Raises:
        ValueError: If older_than_days is negative
    """
    if older_than_days < 0:
        raise ValueError("older_than_days must be non-negative")

    if dry_run:
        logger.info("Dry run: would clean receipts older than %d days", older_than_days)

    return _cleanup_files_by_age(
        project_root=project_root,
        subdir="receipts",
        pattern="*.json",
        older_than_days=older_than_days,
        dry_run=dry_run,
        remove_dirs=False,
    )


def clean_contexts(
    project_root: Path,
    older_than_days: int = 90,
    dry_run: bool = False,
) -> CleanupResult:
    """Clean old context snapshots from .ralph/context/.

    Removes context directories older than the specified number of days.
    Context snapshots preserve LLM conversation history between iterations.

    Args:
        project_root: Root directory of the project
        older_than_days: Remove contexts older than this many days (default: 90)
        dry_run: If True, scan and report but don't delete (default: False)

    Returns:
        CleanupResult with statistics on files removed and bytes freed

    Raises:
        ValueError: If older_than_days is negative
    """
    if older_than_days < 0:
        raise ValueError("older_than_days must be non-negative")

    if dry_run:
        logger.info("Dry run: would clean contexts older than %d days", older_than_days)

    # Context may include both directories (per-task snapshots) and loose files.
    dir_result = _cleanup_files_by_age(
        project_root=project_root,
        subdir="context",
        pattern="*",
        older_than_days=older_than_days,
        dry_run=dry_run,
        remove_dirs=True,
    )
    file_result = _cleanup_files_by_age(
        project_root=project_root,
        subdir="context",
        pattern="*",
        older_than_days=older_than_days,
        dry_run=dry_run,
        remove_dirs=False,
    )
    return _merge_results(dir_result, file_result)


def clean_context(
    project_root: Path,
    older_than_days: int = 90,
    dry_run: bool = False,
) -> CleanupResult:
    """Backward-compatible alias for clean_contexts()."""

    return clean_contexts(project_root, older_than_days=older_than_days, dry_run=dry_run)


def format_bytes(bytes_count: int) -> str:
    """Format bytes as human-readable string.
    
    Args:
        bytes_count: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 KB", "2.3 MB")
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(bytes_count) < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} TB"


def clean_all(
    project_root: Path,
    logs_days: int = 30,
    archives_days: int = 90,
    receipts_days: int = 90,
    context_days: int = 90,
    dry_run: bool = False,
) -> Tuple[CleanupResult, CleanupResult, CleanupResult, CleanupResult]:
    """Clean all Ralph workspace artifacts.

    Args:
        project_root: Root directory of the project
        logs_days: Remove logs older than this many days
        archives_days: Remove archives older than this many days
        receipts_days: Remove receipts older than this many days
        context_days: Remove context files older than this many days
        dry_run: If True, don't actually delete anything

    Returns:
        Tuple of (logs_result, archives_result, receipts_result, contexts_result)
    """
    logs_result = clean_logs(project_root, logs_days, dry_run)
    archives_result = clean_archives(project_root, archives_days, dry_run)
    receipts_result = clean_receipts(project_root, receipts_days, dry_run)
    contexts_result = clean_contexts(project_root, context_days, dry_run)

    return logs_result, archives_result, receipts_result, contexts_result
