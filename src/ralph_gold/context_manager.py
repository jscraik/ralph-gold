"""Context management for RALPH agent prompts.

Provides sliding window context loading to prevent agent timeout due to
excessive context size. The primary issue is unbounded growth of progress.md
which, combined with specs and PRD, exceeds effective context capacity.

This module implements:
- Sliding window for progress.md (keep N most recent entries)
- Context health checking
- Automatic archiving of old progress entries
- Configurable per-section budgets
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContextConfig:
    """Configuration for context management.

    Attributes:
        total_budget_chars: Total character budget for all context (default: 50000)
        progress_max_lines: Maximum number of progress entries to include (default: 100)
        progress_max_chars: Maximum characters for progress section (default: 10000)
        prune_on_build: Automatically truncate progress when building prompt (default: true)
        archive_old_entries: Archive old progress entries (default: true)
        archive_dir: Directory for archived progress relative to .ralph/ (default: archive/progress)
    """

    total_budget_chars: int = 50000
    progress_max_lines: int = 100
    progress_max_chars: int = 10000
    prune_on_build: bool = True
    archive_old_entries: bool = True
    archive_dir: str = "archive/progress"

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.total_budget_chars < 10000:
            raise ValueError(
                f"total_budget_chars must be >= 10000, got {self.total_budget_chars}"
            )
        if self.total_budget_chars > 200000:
            raise ValueError(
                f"total_budget_chars suspiciously large: {self.total_budget_chars} "
                f"(limit: 200000)"
            )
        if self.progress_max_lines < 10:
            raise ValueError(
                f"progress_max_lines must be >= 10, got {self.progress_max_lines}"
            )
        if self.progress_max_lines > 1000:
            raise ValueError(
                f"progress_max_lines suspiciously large: {self.progress_max_lines} "
                f"(limit: 1000)"
            )
        if self.progress_max_chars < 1000:
            raise ValueError(
                f"progress_max_chars must be >= 1000, got {self.progress_max_chars}"
            )


@dataclass
class ContextHealth:
    """Health metrics for context size.

    Attributes:
        total_size: Total context size in characters
        progress_size: Progress section size in characters
        progress_entries: Number of progress entries loaded
        progress_total_entries: Total entries in file (before windowing)
        spec_size: Combined spec size in characters
        within_budget: Whether total size is within configured budget
        saturation_score: Percentage of budget used (0-100)
        warnings: List of warning messages
    """

    total_size: int = 0
    progress_size: int = 0
    progress_entries: int = 0
    progress_total_entries: int = 0
    spec_size: int = 0
    within_budget: bool = True
    saturation_score: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Generate human-readable health report."""
        lines = [
            "Context Health Report:",
            f"  Total size: {self.total_size:,} chars ({self.saturation_score:.1f}% of budget)",
            f"  Progress: {self.progress_size:,} chars ({self.progress_entries}/{self.progress_total_entries} entries)",
            f"  Specs: {self.spec_size:,} chars",
            f"  Within budget: {'yes' if self.within_budget else 'NO'}",
        ]
        if self.warnings:
            lines.append("  Warnings:")
            for warning in self.warnings:
                lines.append(f"    - {warning}")
        return "\n".join(lines)


def _split_progress_entries(content: str) -> List[str]:
    """Split progress.md into individual entries.

    Progress entries are typically separated by timestamps in brackets:
    [2026-01-19T11:07:33.971651+00:00]
    [20260119T110658Z]

    Also handles the "Iter N:" format that appears in progress files.

    Args:
        content: The full content of progress.md

    Returns:
        List of progress entries (may be empty strings)
    """
    if not content.strip():
        return []

    # Pattern for timestamp lines: [ISO8601] or [compact timestamp]
    # Also handles "2026-01-19 Iteration N:" format
    timestamp_pattern = r"^(\[[^\]]+\]|2026-\d{2}-\d{2}\s+Iteration\s+\d+:)"

    # Split by timestamp lines, keeping the delimiter
    parts = re.split(timestamp_pattern, content, flags=re.MULTILINE)

    # Reconstruct entries by joining delimiter with following content
    entries: List[str] = []
    current_entry = ""

    for part in parts:
        if re.match(timestamp_pattern, part, flags=re.MULTILINE):
            # This is a delimiter - start a new entry
            if current_entry.strip():
                entries.append(current_entry.strip())
            current_entry = part
        else:
            current_entry += part

    # Don't forget the last entry
    if current_entry.strip():
        entries.append(current_entry.strip())

    # If no entries were parsed, return the whole content as one entry
    if not entries and content.strip():
        return [content.strip()]

    return entries


def load_progress_window(
    path: Path,
    max_lines: int = 100,
    max_chars: int = 10000,
) -> Tuple[str, int, int]:
    """Load the most recent N entries from progress.md.

    Uses a sliding window approach to keep context size bounded while
    preserving recent history that's most relevant to the current task.

    Args:
        path: Path to progress.md file
        max_lines: Maximum number of entries to return
        max_chars: Maximum characters to return

    Returns:
        Tuple of (windowed_content, entries_loaded, total_entries)
    """
    if not path.exists() or not path.is_file():
        return "", 0, 0

    try:
        full_content = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read progress file {path}: {e}")
        return "", 0, 0

    if not full_content.strip():
        return "", 0, 0

    # Split into entries
    all_entries = _split_progress_entries(full_content)
    total_count = len(all_entries)

    if total_count == 0:
        return "", 0, 0

    # Take the last N entries (most recent)
    windowed_entries = all_entries[-max_lines:] if max_lines < total_count else all_entries

    # Join and truncate by character limit
    windowed_content = "\n\n".join(windowed_entries)
    if len(windowed_content) > max_chars:
        windowed_content = windowed_content[:max_chars] + "\n...<truncated>...\n"

    entries_loaded = len(windowed_entries)

    logger.debug(
        f"Loaded progress window: {entries_loaded}/{total_count} entries, "
        f"{len(windowed_content)} chars"
    )

    return windowed_content, entries_loaded, total_count


def archive_old_progress(
    path: Path,
    archive_dir: Path,
    keep_lines: int = 100,
) -> int:
    """Archive old progress entries to a dated file.

    Moves all but the most recent N entries to an archive file.
    Archive files are named by date: progress-YYYY-MM-DD.md

    Args:
        path: Path to progress.md
        archive_dir: Directory to store archives (will be created if needed)
        keep_lines: Number of recent entries to keep in progress.md

    Returns:
        Number of entries archived (0 if nothing was archived)
    """
    if not path.exists() or not path.is_file():
        return 0

    try:
        full_content = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read progress file for archival: {e}")
        return 0

    all_entries = _split_progress_entries(full_content)

    if len(all_entries) <= keep_lines:
        logger.debug(f"Progress has {len(all_entries)} entries, no archival needed")
        return 0

    # Split into keep and archive portions
    keep_entries = all_entries[-keep_lines:]
    archive_entries = all_entries[:-keep_lines]

    if not archive_entries:
        return 0

    # Create archive directory
    try:
        archive_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.debug("Failed to create context directory: %s", e)
        return 0

    # Write archive file with today's date
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    archive_path = archive_dir / f"progress-{today}.md"

    try:
        # Append to existing archive file for today (if any)
        existing_archive = ""
        if archive_path.exists():
            existing_archive = archive_path.read_text(encoding="utf-8")
            if existing_archive and not existing_archive.endswith("\n\n"):
                existing_archive += "\n\n"

        archive_content = existing_archive + "\n\n".join(archive_entries)
        archive_path.write_text(archive_content, encoding="utf-8")

        # Write truncated progress.md
        truncated_content = "\n\n".join(keep_entries)
        path.write_text(truncated_content, encoding="utf-8")

        archived_count = len(archive_entries)
        logger.info(
            f"Archived {archived_count} progress entries to {archive_path.relative_to(path.parent.parent)}"
        )
        return archived_count

    except Exception as e:
        logger.warning(f"Failed to archive progress entries: {e}")
        return 0


def load_context_metadata(
    metadata_path: Path,
) -> dict:
    """Load context metadata from a JSON file.

    Args:
        metadata_path: Path to metadata JSON file

    Returns:
        Dictionary containing metadata (empty dict if file doesn't exist or fails to load)
    """
    if not metadata_path.exists() or not metadata_path.is_file():
        return {}

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Failed to load context metadata: %s", e)
        metadata = {}

    return metadata


def check_context_health(
    progress_size: int,
    progress_entries: int,
    progress_total: int,
    spec_size: int,
    config: ContextConfig,
) -> ContextHealth:
    """Check the health of context usage.

    Args:
        progress_size: Size of progress section in characters
        progress_entries: Number of progress entries loaded
        progress_total: Total number of progress entries available
        spec_size: Size of specs section in characters
        config: Context configuration

    Returns:
        ContextHealth object with metrics and warnings
    """
    health = ContextHealth()

    # Calculate sizes (rough estimate for other sections)
    # AGENTS.md ~1K, PRD.md ~10K, prompt overhead ~2K
    other_sections_estimate = 13000
    health.total_size = progress_size + spec_size + other_sections_estimate
    health.progress_size = progress_size
    health.progress_entries = progress_entries
    health.progress_total_entries = progress_total
    health.spec_size = spec_size

    # Check budget
    health.within_budget = health.total_size <= config.total_budget_chars
    health.saturation_score = (health.total_size / config.total_budget_chars) * 100

    # Generate warnings
    if not health.within_budget:
        health.warnings.append(
            f"Context size ({health.total_size:,} chars) exceeds budget ({config.total_budget_chars:,} chars)"
        )

    if health.saturation_score > 90:
        health.warnings.append(
            f"Context at {health.saturation_score:.1f}% of budget - agent may timeout"
        )
    elif health.saturation_score > 75:
        health.warnings.append(
            f"Context at {health.saturation_score:.1f}% of budget - approaching limit"
        )

    if progress_total > config.progress_max_lines * 2:
        health.warnings.append(
            f"Progress.md has {progress_total} entries - consider archiving old entries"
        )

    if progress_size > config.progress_max_chars:
        health.warnings.append(
            f"Progress section ({progress_size:,} chars) exceeds limit ({config.progress_max_chars:,} chars)"
        )

    return health


def build_context_with_budget(
    project_root: Path,
    config: ContextConfig,
    agents_path: Path,
    prd_path: Path,
    progress_path: Path,
) -> dict[str, str | list[str]]:
    """Build context sections with size budgeting.

    This is the main entry point for context-aware prompt building.
    Returns a dictionary of context sections that fit within the budget.

    Args:
        project_root: Project root directory
        config: Context configuration
        agents_path: Path to AGENTS.md
        prd_path: Path to PRD.md
        progress_path: Path to progress.md

    Returns:
        Dictionary with keys: agents, prd, progress, progress_entries_loaded,
        progress_total_entries, specs (empty list, populated by caller)
    """
    result: dict[str, str | list[str]] = {}

    # Read agents (usually small)
    try:
        agents = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    except OSError as e:
        logger.debug("Failed to read agents file: %s", e)
        agents = ""
    result["agents"] = agents

    # Read PRD (medium size)
    try:
        prd = prd_path.read_text(encoding="utf-8") if prd_path.exists() else ""
    except OSError as e:
        logger.debug("Failed to read PRD: %s", e)
        prd = ""
    result["prd"] = prd

    # Read progress with sliding window
    progress, entries_loaded, total_entries = load_progress_window(
        progress_path,
        max_lines=config.progress_max_lines,
        max_chars=config.progress_max_chars,
    )
    result["progress"] = progress
    result["progress_entries_loaded"] = str(entries_loaded)
    result["progress_total_entries"] = str(total_entries)

    # Archive old entries if enabled and needed
    if config.archive_old_entries and total_entries > config.progress_max_lines * 2:
        archive_dir = project_root / ".ralph" / config.archive_dir
        archived = archive_old_progress(
            progress_path,
            archive_dir,
            keep_lines=config.progress_max_lines,
        )
        if archived > 0:
            logger.info(f"Archived {archived} old progress entries")

    # Specs are loaded separately by spec_loader.py
    result["specs"] = []  # Will be populated by caller

    return result
