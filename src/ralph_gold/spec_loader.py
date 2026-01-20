"""Spec file loading with limits and diagnostics.

Provides safe loading of spec files with configurable limits to prevent
token limit issues in agent prompts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SpecLoadResult:
    """Result of spec loading with metadata.

    Attributes:
        included: List of (filepath, char_count) tuples that were included
        excluded: List of (filepath, char_count) tuples that were excluded
        truncated: List of (filepath, original_count, truncated_count) tuples
        total_chars: Total characters included
        warnings: List of warning messages
    """

    included: List[Tuple[str, int]] = field(default_factory=list)
    excluded: List[Tuple[str, int]] = field(default_factory=list)
    truncated: List[Tuple[str, int, int]] = field(default_factory=list)
    total_chars: int = 0
    warnings: List[str] = field(default_factory=list)

    def log_summary(self) -> str:
        """Generate a summary string for logging."""
        lines = [
            f"Spec loading summary: {len(self.included)} included, "
            f"{len(self.excluded)} excluded, {len(self.truncated)} truncated"
        ]
        if self.total_chars > 0:
            lines.append(f"Total characters: {self.total_chars}")
        if self.warnings:
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")
        return "\n".join(lines)


def load_specs_with_limits(
    specs_dir: Path,
    max_specs_files: int = 20,
    max_specs_chars: int = 50000,
    max_single_spec_chars: int = 10000,
    truncate_long_specs: bool = True,
    specs_inclusion_order: str = "sorted",
) -> SpecLoadResult:
    """Load spec files with configurable limits and diagnostic warnings.

    Args:
        specs_dir: Directory containing spec files (*.md)
        max_specs_files: Maximum number of spec files to include
        max_specs_chars: Maximum total characters across all specs
        max_single_spec_chars: Maximum characters for a single spec
        truncate_long_specs: If True, truncate oversized specs; if False, exclude them
        specs_inclusion_order: How to order specs - "sorted" or "recency"

    Returns:
        SpecLoadResult with included/excluded specs and any warnings
    """
    result = SpecLoadResult()

    if not specs_dir.exists() or not specs_dir.is_dir():
        return result

    # Get all spec files
    all_specs = list(specs_dir.glob("*.md"))

    # Order based on configuration
    if specs_inclusion_order == "recency":
        # Sort by modification time (most recent first)
        all_specs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    else:  # "sorted" (default)
        all_specs.sort()

    # Check file count limit
    if len(all_specs) > max_specs_files:
        result.warnings.append(
            f"Found {len(all_specs)} spec files (recommended: {max_specs_files}). "
            f"Set [prompt].enable_limits = true to apply limits."
        )

    # Load specs with limits
    total_chars = 0
    for spec_path in all_specs[:max_specs_files]:
        try:
            content = spec_path.read_text(encoding="utf-8")
            char_count = len(content)
        except Exception as e:
            logger.warning(f"Failed to read {spec_path}: {e}")
            continue

        # Check single spec size
        if char_count > max_single_spec_chars:
            if truncate_long_specs:
                total_chars += max_single_spec_chars
                result.truncated.append((spec_path.name, char_count, max_single_spec_chars))
                result.included.append((spec_path.name, max_single_spec_chars))
                result.warnings.append(
                    f"Spec {spec_path.name} truncated from {char_count} to {max_single_spec_chars} chars"
                )
            else:
                result.excluded.append((spec_path.name, char_count))
                result.warnings.append(
                    f"Spec {spec_path.name} ({char_count} chars) exceeds "
                    f"max_single_spec_chars ({max_single_spec_chars})"
                )
            continue

        # Check total char limit
        if total_chars + char_count > max_specs_chars:
            result.excluded.append((spec_path.name, char_count))
            result.warnings.append(
                f"Spec {spec_path.name} ({char_count} chars) would exceed "
                f"max_specs_chars ({max_specs_chars})"
            )
            break

        total_chars += char_count
        result.included.append((spec_path.name, char_count))

    result.total_chars = total_chars

    # Log summary if there were warnings
    if result.warnings:
        logger.warning(result.log_summary())

    return result
