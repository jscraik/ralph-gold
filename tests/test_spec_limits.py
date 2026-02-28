"""Tests for spec loading with limits."""

from __future__ import annotations

from pathlib import Path

from ralph_gold.spec_loader import SpecLoadResult, load_specs_with_limits
from ralph_gold.config import PromptConfig


class TestPromptConfig:
    """Tests for PromptConfig dataclass."""

    def test_prompt_config_defaults(self) -> None:
        """Test PromptConfig default values."""
        config = PromptConfig()
        assert config.enable_limits is False
        assert config.max_specs_files == 20
        assert config.max_specs_chars == 100000  # Updated default (Phase 1)
        assert config.max_single_spec_chars == 50000  # Updated default (Phase 1)
        assert config.truncate_long_specs is True
        assert config.specs_inclusion_order == "sorted"

    def test_prompt_config_with_values(self) -> None:
        """Test PromptConfig with custom values."""
        config = PromptConfig(
            enable_limits=True,
            max_specs_files=10,
            max_specs_chars=25000,
            max_single_spec_chars=5000,
            truncate_long_specs=False,
            specs_inclusion_order="recency",
        )
        assert config.enable_limits is True
        assert config.max_specs_files == 10
        assert config.max_specs_chars == 25000
        assert config.truncate_long_specs is False
        assert config.specs_inclusion_order == "recency"


class TestSpecLoadResult:
    """Tests for SpecLoadResult dataclass."""

    def test_spec_load_result_creation(self) -> None:
        """Test creating a SpecLoadResult."""
        result = SpecLoadResult(
            included=[("spec1.md", 1000)],
            excluded=[("spec2.md", 5000)],
            truncated=[("spec3.md", 15000, 10000)],
            total_chars=1000,
            warnings=["Some warning"],
        )
        assert len(result.included) == 1
        assert len(result.excluded) == 1
        assert len(result.truncated) == 1
        assert result.total_chars == 1000
        assert len(result.warnings) == 1

    def test_spec_load_result_defaults(self) -> None:
        """Test SpecLoadResult default values."""
        result = SpecLoadResult()
        assert result.included == []
        assert result.excluded == []
        assert result.truncated == []
        assert result.total_chars == 0
        assert result.warnings == []

    def test_spec_load_result_log_summary(self) -> None:
        """Test log_summary method."""
        result = SpecLoadResult(
            included=[("spec1.md", 1000)],
            total_chars=1000,
            warnings=["Warning 1", "Warning 2"],
        )
        summary = result.log_summary()
        assert "1 included" in summary
        assert "Total characters: 1000" in summary
        assert "Warning 1" in summary
        assert "Warning 2" in summary


class TestLoadSpecsWithLimits:
    """Tests for load_specs_with_limits function."""

    def test_load_nonexistent_directory(self, tmp_path: Path) -> None:
        """Test loading from nonexistent directory."""
        result = load_specs_with_limits(tmp_path / "specs")
        assert result.included == []
        assert result.excluded == []
        assert result.total_chars == 0

    def test_load_empty_directory(self, tmp_path: Path) -> None:
        """Test loading from empty directory."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        result = load_specs_with_limits(specs_dir)
        assert result.included == []

    def test_load_specs_within_limits(self, tmp_path: Path) -> None:
        """Test loading specs that are within all limits."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "spec1.md").write_text("A" * 1000)
        (specs_dir / "spec2.md").write_text("B" * 2000)

        result = load_specs_with_limits(
            specs_dir,
            max_specs_files=10,
            max_specs_chars=50000,
            max_single_spec_chars=10000,
        )

        assert len(result.included) == 2
        assert result.total_chars == 3000
        assert len(result.warnings) == 0

    def test_load_exceeds_file_count_limit(self, tmp_path: Path) -> None:
        """Test loading when file count exceeds max_specs_files."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        for i in range(25):
            (specs_dir / f"spec{i}.md").write_text("X" * 100)

        result = load_specs_with_limits(
            specs_dir,
            max_specs_files=10,
            max_specs_chars=50000,
        )

        assert len(result.included) == 10
        assert len(result.warnings) == 1
        assert "Found 25 spec files" in result.warnings[0]

    def test_load_exceeds_total_chars_limit(self, tmp_path: Path) -> None:
        """Test loading when total chars would exceed max_specs_chars."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "spec1.md").write_text("A" * 30000)
        (specs_dir / "spec2.md").write_text("B" * 30000)

        result = load_specs_with_limits(
            specs_dir,
            max_specs_files=10,
            max_specs_chars=50000,
            max_single_spec_chars=10000,  # This causes truncation
        )

        # Both specs are truncated to 10000 each, so both fit within 50000 limit
        assert len(result.included) == 2
        assert len(result.truncated) == 2  # Both were truncated
        assert result.total_chars == 20000  # 10000 + 10000
        assert len(result.warnings) == 2  # Warning for each truncation

    def test_load_exceeds_single_spec_limit_truncate(self, tmp_path: Path) -> None:
        """Test loading single spec exceeds max_single_spec_chars with truncate=True."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "large.md").write_text("A" * 15000)

        result = load_specs_with_limits(
            specs_dir,
            max_single_spec_chars=10000,
            truncate_long_specs=True,
        )

        assert len(result.included) == 1
        assert len(result.truncated) == 1
        assert result.truncated[0] == ("large.md", 15000, 10000)
        assert result.total_chars == 10000
        assert len(result.warnings) == 1
        assert "truncated from 15000 to 10000" in result.warnings[0]

    def test_load_exceeds_single_spec_limit_exclude(self, tmp_path: Path) -> None:
        """Test loading single spec exceeds max_single_spec_chars with truncate=False."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "large.md").write_text("A" * 15000)

        result = load_specs_with_limits(
            specs_dir,
            max_single_spec_chars=10000,
            truncate_long_specs=False,
        )

        assert len(result.included) == 0
        assert len(result.excluded) == 1
        assert result.excluded[0] == ("large.md", 15000)
        assert result.total_chars == 0

    def test_load_sorted_order(self, tmp_path: Path) -> None:
        """Test sorted inclusion order."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "c.md").write_text("C")
        (specs_dir / "a.md").write_text("A")
        (specs_dir / "b.md").write_text("B")

        result = load_specs_with_limits(
            specs_dir,
            specs_inclusion_order="sorted",
        )

        assert result.included[0][0] == "a.md"
        assert result.included[1][0] == "b.md"
        assert result.included[2][0] == "c.md"

    def test_load_recency_order(self, tmp_path: Path) -> None:
        """Test recency inclusion order."""
        import time

        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        # Create files with different timestamps
        (specs_dir / "old.md").write_text("Old")
        time.sleep(0.01)
        (specs_dir / "new.md").write_text("New")
        time.sleep(0.01)
        (specs_dir / "newest.md").write_text("Newest")

        result = load_specs_with_limits(
            specs_dir,
            specs_inclusion_order="recency",
        )

        # Most recently modified should come first
        assert result.included[0][0] == "newest.md"
        assert result.included[1][0] == "new.md"
        assert result.included[2][0] == "old.md"


class TestIntegration:
    """Integration tests for spec loading."""

    def test_full_workflow_with_warnings(self, tmp_path: Path) -> None:
        """Test full spec loading workflow that generates warnings."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        # Create various specs
        (specs_dir / "small1.md").write_text("A" * 1000)
        (specs_dir / "small2.md").write_text("B" * 2000)
        (specs_dir / "large.md").write_text("C" * 15000)  # Exceeds single limit

        result = load_specs_with_limits(
            specs_dir,
            max_specs_files=10,
            max_specs_chars=50000,
            max_single_spec_chars=10000,
            truncate_long_specs=True,
        )

        assert len(result.included) == 3  # All included (large truncated)
        assert len(result.truncated) == 1
        assert result.total_chars == 13000  # 1000 + 2000 + 10000
        assert len(result.warnings) == 1
        assert "truncated from 15000 to 10000" in result.warnings[0]
