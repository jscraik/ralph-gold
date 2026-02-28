"""Tests for context_manager module.

Tests the sliding window progress loading, context health checking,
and archiving functionality.
"""

from __future__ import annotations

import pytest

from ralph_gold.context_manager import (
    ContextConfig,
    ContextHealth,
    _split_progress_entries,
    archive_old_progress,
    check_context_health,
    load_progress_window,
)


class TestSplitProgressEntries:
    """Tests for _split_progress_entries function."""

    def test_empty_content(self):
        """Empty string returns empty list."""
        result = _split_progress_entries("")
        assert result == []

    def test_single_entry(self):
        """Single entry without timestamps returns as one entry."""
        content = "This is a simple entry"
        result = _split_progress_entries(content)
        assert len(result) == 1
        assert result[0] == "This is a simple entry"

    def test_iso_timestamp_entries(self):
        """Splits entries by ISO8601 timestamps in brackets."""
        content = """[2026-01-19T11:07:33.971651+00:00] First entry
Some content here

[2026-01-19T11:09:32.956396+00:00] Second entry
More content"""
        result = _split_progress_entries(content)
        assert len(result) == 2
        assert "[2026-01-19T11:07:33.971651+00:00]" in result[0]
        assert "[2026-01-19T11:09:32.956396+00:00]" in result[1]

    def test_compact_timestamp_entries(self):
        """Splits entries by compact timestamps in brackets."""
        content = """[20260119T110658Z] First entry
Content here

[20260119T110734Z] Second entry
More content"""
        result = _split_progress_entries(content)
        assert len(result) == 2
        assert "[20260119T110658Z]" in result[0]
        assert "[20260119T110734Z]" in result[1]

    def test_iteration_format_entries(self):
        """Splits entries by 'Iteration N:' format."""
        content = """2026-01-19 Iteration 12: First entry
Content here

2026-01-19 Iteration 13: Second entry
More content"""
        result = _split_progress_entries(content)
        assert len(result) == 2
        assert "Iteration 12:" in result[0]
        assert "Iteration 13:" in result[1]

    def test_mixed_timestamps(self):
        """Handles mixed timestamp formats."""
        content = """[20260119T110658Z] Entry 1
Content

2026-01-19 Iteration 12: Entry 2
Content

[2026-01-19T11:07:33.971651+00:00] Entry 3
Content"""
        result = _split_progress_entries(content)
        assert len(result) >= 2


class TestLoadProgressWindow:
    """Tests for load_progress_window function."""

    def test_nonexistent_file(self, tmp_path):
        """Nonexistent file returns empty content."""
        content, loaded, total = load_progress_window(tmp_path / "nonexistent.md")
        assert content == ""
        assert loaded == 0
        assert total == 0

    def test_empty_file(self, tmp_path):
        """Empty file returns empty content."""
        path = tmp_path / "progress.md"
        path.write_text("")
        content, loaded, total = load_progress_window(path)
        assert content == ""
        assert loaded == 0
        assert total == 0

    def test_small_file_within_limits(self, tmp_path):
        """Small file within limits returns all content."""
        path = tmp_path / "progress.md"
        content = "[20260119T110658Z] Entry 1\nContent\n\n[20260119T110734Z] Entry 2\nContent"
        path.write_text(content)

        result, loaded, total = load_progress_window(
            path, max_lines=100, max_chars=10000
        )
        assert loaded == 2
        assert total == 2
        assert "Entry 1" in result
        assert "Entry 2" in result

    def test_window_limits_entries(self, tmp_path):
        """max_lines limits the number of entries returned."""
        path = tmp_path / "progress.md"
        content = "\n\n".join([
            f"[20260119T110{i:02d}Z] Entry {i}\nContent {i}"
            for i in range(10)
        ])
        path.write_text(content)

        result, loaded, total = load_progress_window(
            path, max_lines=3, max_chars=10000
        )
        assert loaded == 3
        assert total == 10
        assert "Entry 7" in result  # Last 3 entries
        assert "Entry 8" in result
        assert "Entry 9" in result
        assert "Entry 1" not in result  # First entries excluded

    def test_char_limit_truncates(self, tmp_path):
        """max_chars truncates the result."""
        path = tmp_path / "progress.md"
        long_content = "A" * 1000
        content = f"[20260119T110658Z] Entry 1\n{long_content}\n\n[20260119T110734Z] Entry 2\n{long_content}"
        path.write_text(content)

        result, loaded, total = load_progress_window(
            path, max_lines=100, max_chars=500
        )
        # The truncation adds "...<truncated>...\n" so result can be slightly over 500
        assert len(result) <= 550
        assert "...<truncated>..." in result


class TestArchiveOldProgress:
    """Tests for archive_old_progress function."""

    def test_nonexistent_file(self, tmp_path):
        """Nonexistent file returns 0 archived."""
        result = archive_old_progress(
            tmp_path / "nonexistent.md",
            tmp_path / "archive",
            keep_lines=100,
        )
        assert result == 0

    def test_small_file_no_archive(self, tmp_path):
        """File with fewer entries than keep_lines doesn't archive."""
        path = tmp_path / "progress.md"
        content = "\n\n".join([
            f"[20260119T110{i:02d}Z] Entry {i}\nContent {i}"
            for i in range(5)
        ])
        path.write_text(content)

        archive_dir = tmp_path / "archive"
        result = archive_old_progress(path, archive_dir, keep_lines=10)

        assert result == 0
        # Original file unchanged
        assert path.read_text() == content

    def test_archives_old_entries(self, tmp_path):
        """Archives entries beyond keep_lines."""
        path = tmp_path / "progress.md"
        content = "\n\n".join([
            f"[20260119T110{i:02d}Z] Entry {i}\nContent {i}"
            for i in range(10)
        ])
        path.write_text(content)

        archive_dir = tmp_path / "archive"
        result = archive_old_progress(path, archive_dir, keep_lines=3)

        assert result == 7  # 10 - 3 = 7 archived

        # Check original file only has 3 entries
        new_content = path.read_text()
        assert "Entry 7" in new_content
        assert "Entry 8" in new_content
        assert "Entry 9" in new_content
        assert "Entry 0" not in new_content

        # Check archive file exists
        archive_files = list(archive_dir.glob("progress-*.md"))
        assert len(archive_files) == 1
        archive_content = archive_files[0].read_text()
        assert "Entry 0" in archive_content


class TestCheckContextHealth:
    """Tests for check_context_health function."""

    def test_within_budget(self):
        """Context within budget has no warnings."""
        config = ContextConfig(total_budget_chars=50000)
        health = check_context_health(
            progress_size=5000,
            progress_entries=10,
            progress_total=10,
            spec_size=10000,
            config=config,
        )
        assert health.within_budget
        assert len(health.warnings) == 0

    def test_over_budget_warning(self):
        """Context over budget generates warning."""
        config = ContextConfig(total_budget_chars=10000)
        health = check_context_health(
            progress_size=8000,
            progress_entries=10,
            progress_total=10,
            spec_size=8000,
            config=config,
        )
        assert not health.within_budget
        assert len(health.warnings) > 0
        assert any("exceeds budget" in w for w in health.warnings)

    def test_high_saturation_warning(self):
        """Context at 90%+ saturation generates warning."""
        config = ContextConfig(total_budget_chars=10000)
        health = check_context_health(
            progress_size=7000,
            progress_entries=10,
            progress_total=10,
            spec_size=2000,
            config=config,  # +13K estimate = ~130% of budget
        )
        assert len(health.warnings) > 0
        assert any("90%" in w or "agent may timeout" in w for w in health.warnings)

    def test_large_progress_file_warning(self):
        """Large progress.md file generates warning."""
        config = ContextConfig(
            total_budget_chars=50000,
            progress_max_lines=100,
        )
        health = check_context_health(
            progress_size=5000,
            progress_entries=50,
            progress_total=250,  # 2.5x max_lines
            spec_size=10000,
            config=config,
        )
        assert len(health.warnings) > 0
        assert any("consider archiving" in w for w in health.warnings)

    def test_progress_exceeds_limit_warning(self):
        """Progress section exceeding max_chars generates warning."""
        config = ContextConfig(
            total_budget_chars=50000,
            progress_max_chars=10000,
        )
        health = check_context_health(
            progress_size=15000,  # Exceeds limit
            progress_entries=50,
            progress_total=100,
            spec_size=10000,
            config=config,
        )
        assert len(health.warnings) > 0
        assert any("exceeds limit" in w for w in health.warnings)


class TestContextConfig:
    """Tests for ContextConfig validation."""

    def test_default_values(self):
        """Default config has valid values."""
        config = ContextConfig()
        assert config.total_budget_chars == 50000
        assert config.progress_max_lines == 100
        assert config.progress_max_chars == 10000

    def test_total_budget_too_low_raises(self):
        """total_budget_chars below minimum raises ValueError."""
        with pytest.raises(ValueError, match="total_budget_chars must be >= 10000"):
            ContextConfig(total_budget_chars=5000)

    def test_total_budget_too_high_raises(self):
        """total_budget_chars above limit raises ValueError."""
        with pytest.raises(ValueError, match="suspiciously large"):
            ContextConfig(total_budget_chars=300000)

    def test_progress_max_lines_too_low_raises(self):
        """progress_max_lines below minimum raises ValueError."""
        with pytest.raises(ValueError, match="progress_max_lines must be >= 10"):
            ContextConfig(progress_max_lines=5)

    def test_progress_max_chars_too_low_raises(self):
        """progress_max_chars below minimum raises ValueError."""
        with pytest.raises(ValueError, match="progress_max_chars must be >= 1000"):
            ContextConfig(progress_max_chars=500)


class TestContextHealth:
    """Tests for ContextHealth dataclass."""

    def test_str_representation(self):
        """ContextHealth string representation is readable."""
        health = ContextHealth(
            total_size=25000,
            progress_size=5000,
            progress_entries=10,
            progress_total_entries=20,
            spec_size=10000,
            within_budget=True,
            saturation_score=50.0,
            warnings=["Test warning"],
        )
        result = str(health)
        assert "Context Health Report" in result
        assert "25,000 chars" in result
        assert "50.0%" in result
        assert "Test warning" in result
