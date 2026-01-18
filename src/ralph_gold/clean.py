"""Cleanup utilities for Ralph workspace."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""

    files_removed: int
    bytes_freed: int
    directories_removed: int
    errors: List[str]


def _get_file_age_days(path: Path) -> float:
    """Get the age of a file in days."""
    try:
        mtime = path.stat().st_mtime
        age = datetime.now(timezone.utc).timestamp() - mtime
        return age / 86400.0  # Convert seconds to days
    except Exception:
        return 0.0


def _get_directory_size(path: Path) -> int:
    """Get total size of directory in bytes."""
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except Exception:
                    pass
    except Exception:
        pass
    return total


def clean_logs(
    project_root: Path, older_than_days: int = 30, dry_run: bool = False
) -> CleanupResult:
    """Clean old log files from .ralph/logs/.

    Args:
        project_root: Root directory of the project
        older_than_days: Remove logs older than this many days
        dry_run: If True, don't actually delete files

    Returns:
        CleanupResult with statistics
    """
    logs_dir = project_root / ".ralph" / "logs"
    if not logs_dir.exists():
        return CleanupResult(0, 0, 0, [])

    files_removed = 0
    bytes_freed = 0
    errors: List[str] = []

    try:
        for log_file in logs_dir.glob("*.log"):
            if not log_file.is_file():
                continue

            age = _get_file_age_days(log_file)
            if age > older_than_days:
                try:
                    size = log_file.stat().st_size
                    if not dry_run:
                        log_file.unlink()
                    files_removed += 1
                    bytes_freed += size
                except Exception as e:
                    errors.append(f"Failed to remove {log_file.name}: {e}")
    except Exception as e:
        errors.append(f"Failed to scan logs directory: {e}")

    return CleanupResult(files_removed, bytes_freed, 0, errors)


def clean_archives(
    project_root: Path, older_than_days: int = 90, dry_run: bool = False
) -> CleanupResult:
    """Clean old archive directories from .ralph/archive/.

    Args:
        project_root: Root directory of the project
        older_than_days: Remove archives older than this many days
        dry_run: If True, don't actually delete directories

    Returns:
        CleanupResult with statistics
    """
    archive_dir = project_root / ".ralph" / "archive"
    if not archive_dir.exists():
        return CleanupResult(0, 0, 0, [])

    files_removed = 0
    bytes_freed = 0
    directories_removed = 0
    errors: List[str] = []

    try:
        for archive_subdir in archive_dir.iterdir():
            if not archive_subdir.is_dir():
                continue

            age = _get_file_age_days(archive_subdir)
            if age > older_than_days:
                try:
                    size = _get_directory_size(archive_subdir)
                    file_count = sum(
                        1 for _ in archive_subdir.rglob("*") if _.is_file()
                    )

                    if not dry_run:
                        shutil.rmtree(archive_subdir)

                    files_removed += file_count
                    bytes_freed += size
                    directories_removed += 1
                except Exception as e:
                    errors.append(f"Failed to remove {archive_subdir.name}: {e}")
    except Exception as e:
        errors.append(f"Failed to scan archive directory: {e}")

    return CleanupResult(files_removed, bytes_freed, directories_removed, errors)


def clean_receipts(
    project_root: Path, older_than_days: int = 60, dry_run: bool = False
) -> CleanupResult:
    """Clean old receipt files from .ralph/receipts/.

    Args:
        project_root: Root directory of the project
        older_than_days: Remove receipts older than this many days
        dry_run: If True, don't actually delete files

    Returns:
        CleanupResult with statistics
    """
    receipts_dir = project_root / ".ralph" / "receipts"
    if not receipts_dir.exists():
        return CleanupResult(0, 0, 0, [])

    files_removed = 0
    bytes_freed = 0
    errors: List[str] = []

    try:
        for receipt_file in receipts_dir.rglob("*.json"):
            if not receipt_file.is_file():
                continue

            age = _get_file_age_days(receipt_file)
            if age > older_than_days:
                try:
                    size = receipt_file.stat().st_size
                    if not dry_run:
                        receipt_file.unlink()
                    files_removed += 1
                    bytes_freed += size
                except Exception as e:
                    errors.append(f"Failed to remove {receipt_file.name}: {e}")
    except Exception as e:
        errors.append(f"Failed to scan receipts directory: {e}")

    return CleanupResult(files_removed, bytes_freed, 0, errors)


def clean_context(
    project_root: Path, older_than_days: int = 60, dry_run: bool = False
) -> CleanupResult:
    """Clean old context snapshots from .ralph/context/.

    Args:
        project_root: Root directory of the project
        older_than_days: Remove context files older than this many days
        dry_run: If True, don't actually delete files

    Returns:
        CleanupResult with statistics
    """
    context_dir = project_root / ".ralph" / "context"
    if not context_dir.exists():
        return CleanupResult(0, 0, 0, [])

    files_removed = 0
    bytes_freed = 0
    errors: List[str] = []

    try:
        for context_file in context_dir.rglob("*"):
            if not context_file.is_file():
                continue

            age = _get_file_age_days(context_file)
            if age > older_than_days:
                try:
                    size = context_file.stat().st_size
                    if not dry_run:
                        context_file.unlink()
                    files_removed += 1
                    bytes_freed += size
                except Exception as e:
                    errors.append(f"Failed to remove {context_file.name}: {e}")
    except Exception as e:
        errors.append(f"Failed to scan context directory: {e}")

    return CleanupResult(files_removed, bytes_freed, 0, errors)


def format_bytes(bytes_count: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} TB"


def clean_all(
    project_root: Path,
    logs_days: int = 30,
    archives_days: int = 90,
    receipts_days: int = 60,
    context_days: int = 60,
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
        Tuple of (logs_result, archives_result, receipts_result, context_result)
    """
    logs_result = clean_logs(project_root, logs_days, dry_run)
    archives_result = clean_archives(project_root, archives_days, dry_run)
    receipts_result = clean_receipts(project_root, receipts_days, dry_run)
    context_result = clean_context(project_root, context_days, dry_run)

    return logs_result, archives_result, receipts_result, context_result
