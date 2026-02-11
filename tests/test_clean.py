"""Tests for cleanup functionality."""

import time
from pathlib import Path

from ralph_gold.clean import (
    clean_all,
    clean_archives,
    clean_context,
    clean_contexts,
    clean_logs,
    clean_receipts,
    format_bytes,
)


def test_format_bytes() -> None:
    """Test byte formatting."""
    assert format_bytes(0) == "0.0 B"
    assert format_bytes(512) == "512.0 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1536) == "1.5 KB"
    assert format_bytes(1024 * 1024) == "1.0 MB"
    assert format_bytes(1024 * 1024 * 1024) == "1.0 GB"


def test_clean_logs_no_directory(tmp_path: Path) -> None:
    """Test cleaning logs when directory doesn't exist."""
    result = clean_logs(tmp_path, older_than_days=30)
    assert result.files_removed == 0
    assert result.bytes_freed == 0
    assert len(result.errors) == 0


def test_clean_logs_removes_old_files(tmp_path: Path) -> None:
    """Test that old log files are removed."""
    logs_dir = tmp_path / ".ralph" / "logs"
    logs_dir.mkdir(parents=True)

    # Create an old log file
    old_log = logs_dir / "old.log"
    old_log.write_text("old content")

    # Make it old by modifying mtime
    old_time = time.time() - (31 * 86400)  # 31 days ago
    old_log.touch()
    import os

    os.utime(old_log, (old_time, old_time))

    # Create a recent log file
    recent_log = logs_dir / "recent.log"
    recent_log.write_text("recent content")

    result = clean_logs(tmp_path, older_than_days=30)

    assert result.files_removed == 1
    assert result.bytes_freed > 0
    assert not old_log.exists()
    assert recent_log.exists()


def test_clean_logs_dry_run(tmp_path: Path) -> None:
    """Test that dry run doesn't actually delete files."""
    logs_dir = tmp_path / ".ralph" / "logs"
    logs_dir.mkdir(parents=True)

    old_log = logs_dir / "old.log"
    old_log.write_text("old content")

    old_time = time.time() - (31 * 86400)
    import os

    os.utime(old_log, (old_time, old_time))

    result = clean_logs(tmp_path, older_than_days=30, dry_run=True)

    assert result.files_removed == 1
    assert result.bytes_freed > 0
    assert old_log.exists()  # File should still exist


def test_clean_archives_removes_old_directories(tmp_path: Path) -> None:
    """Test that old archive directories are removed."""
    archive_dir = tmp_path / ".ralph" / "archive"
    archive_dir.mkdir(parents=True)

    # Create an old archive
    old_archive = archive_dir / "20240101-120000"
    old_archive.mkdir()
    (old_archive / "test.txt").write_text("old archive content")

    old_time = time.time() - (91 * 86400)  # 91 days ago
    import os

    os.utime(old_archive, (old_time, old_time))

    # Create a recent archive
    recent_archive = archive_dir / "20240601-120000"
    recent_archive.mkdir()
    (recent_archive / "test.txt").write_text("recent archive content")

    result = clean_archives(tmp_path, older_than_days=90)

    assert result.directories_removed == 1
    assert result.files_removed == 1
    assert result.bytes_freed > 0
    assert not old_archive.exists()
    assert recent_archive.exists()


def test_clean_receipts_removes_old_files(tmp_path: Path) -> None:
    """Test that old receipt files are removed."""
    receipts_dir = tmp_path / ".ralph" / "receipts"
    receipts_dir.mkdir(parents=True)

    # Create an old receipt
    old_receipt = receipts_dir / "old_receipt.json"
    old_receipt.write_text('{"old": true}')

    old_time = time.time() - (61 * 86400)  # 61 days ago
    import os

    os.utime(old_receipt, (old_time, old_time))

    # Create a recent receipt
    recent_receipt = receipts_dir / "recent_receipt.json"
    recent_receipt.write_text('{"recent": true}')

    result = clean_receipts(tmp_path, older_than_days=60)

    assert result.files_removed == 1
    assert result.bytes_freed > 0
    assert not old_receipt.exists()
    assert recent_receipt.exists()


def test_clean_context_removes_old_files(tmp_path: Path) -> None:
    """Test that old context files are removed."""
    context_dir = tmp_path / ".ralph" / "context"
    context_dir.mkdir(parents=True)

    # Create an old context file
    old_context = context_dir / "old_context.txt"
    old_context.write_text("old context")

    old_time = time.time() - (61 * 86400)  # 61 days ago
    import os

    os.utime(old_context, (old_time, old_time))

    # Create a recent context file
    recent_context = context_dir / "recent_context.txt"
    recent_context.write_text("recent context")

    result = clean_context(tmp_path, older_than_days=60)

    assert result.files_removed == 1
    assert result.bytes_freed > 0
    assert not old_context.exists()
    assert recent_context.exists()


def test_clean_all_comprehensive(tmp_path: Path) -> None:
    """Test cleaning all artifact types at once."""
    # Create old files in all directories
    logs_dir = tmp_path / ".ralph" / "logs"
    logs_dir.mkdir(parents=True)
    old_log = logs_dir / "old.log"
    old_log.write_text("log")

    archive_dir = tmp_path / ".ralph" / "archive"
    archive_dir.mkdir(parents=True)
    old_archive = archive_dir / "old_archive"
    old_archive.mkdir()
    (old_archive / "file.txt").write_text("archive")

    receipts_dir = tmp_path / ".ralph" / "receipts"
    receipts_dir.mkdir(parents=True)
    old_receipt = receipts_dir / "old.json"
    old_receipt.write_text("{}")

    context_dir = tmp_path / ".ralph" / "context"
    context_dir.mkdir(parents=True)
    old_context = context_dir / "old.txt"
    old_context.write_text("context")

    # Make all files old
    old_time = time.time() - (100 * 86400)
    import os

    for path in [old_log, old_archive, old_receipt, old_context]:
        os.utime(path, (old_time, old_time))

    logs_result, archives_result, receipts_result, context_result = clean_all(
        tmp_path,
        logs_days=30,
        archives_days=90,
        receipts_days=60,
        context_days=60,
    )

    assert logs_result.files_removed == 1
    assert archives_result.directories_removed == 1
    assert receipts_result.files_removed == 1
    assert context_result.files_removed == 1

    assert not old_log.exists()
    assert not old_archive.exists()
    assert not old_receipt.exists()
    assert not old_context.exists()


def test_clean_all_dry_run(tmp_path: Path) -> None:
    """Test that dry run mode doesn't delete anything."""
    logs_dir = tmp_path / ".ralph" / "logs"
    logs_dir.mkdir(parents=True)
    old_log = logs_dir / "old.log"
    old_log.write_text("log")

    old_time = time.time() - (100 * 86400)
    import os

    os.utime(old_log, (old_time, old_time))

    logs_result, _, _, _ = clean_all(tmp_path, logs_days=30, dry_run=True)

    assert logs_result.files_removed == 1
    assert old_log.exists()  # Should still exist in dry run
