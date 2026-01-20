"""Tests for config merge functionality."""

from __future__ import annotations

from pathlib import Path

import pytest

from ralph_gold.config_merge import (
    MergeConfig,
    _extract_section_lines,
    _extract_nested_section,
    merge_configs_text,
    merge_existing_config,
)


class TestMergeConfig:
    """Tests for MergeConfig dataclass."""

    def test_merge_config_defaults(self) -> None:
        """Test MergeConfig default values."""
        config = MergeConfig()
        assert config.strategy == "user_wins"
        assert config.preserve_sections == [
            "runners.custom",
            "tracker.github",
            "authorization",
        ]
        assert config.merge_sections == [
            "loop",
            "gates",
            "files",
            "prompt",
            "state",
            "output_control",
        ]

    def test_merge_config_custom(self) -> None:
        """Test MergeConfig with custom values."""
        config = MergeConfig(
            strategy="template_wins",
            preserve_sections=["custom.section"],
            merge_sections=["loop"],
        )
        assert config.strategy == "template_wins"
        assert config.preserve_sections == ["custom.section"]
        assert config.merge_sections == ["loop"]


class TestExtractSectionLines:
    """Tests for _extract_section_lines function."""

    def test_extract_existing_section(self) -> None:
        """Test extracting an existing section."""
        lines = """
[loop]
max_iterations = 10
mode = "quality"

[gates]
enabled = true
""".splitlines()
        start, end, section = _extract_section_lines(lines, "loop")

        assert start == 1  # First non-empty line after split
        assert end == 5  # Includes the empty line before [gates]
        assert len(section) == 4

    def test_extract_nonexistent_section(self) -> None:
        """Test extracting a section that doesn't exist."""
        lines = """
[loop]
max_iterations = 10
""".splitlines()
        start, end, section = _extract_section_lines(lines, "gates")

        assert start == -1
        assert end == -1
        assert section == []

    def test_extract_last_section(self) -> None:
        """Test extracting the last section (goes to end of file)."""
        lines = """
[loop]
max_iterations = 10

[gates]
enabled = true
""".splitlines()
        start, end, section = _extract_section_lines(lines, "gates")

        assert start == 4  # After empty string and loop section
        assert end == 6  # End of file
        assert len(section) == 2


class TestExtractNestedSection:
    """Tests for _extract_nested_section function."""

    def test_extract_existing_nested(self) -> None:
        """Test extracting an existing nested section."""
        lines = """
[runners]
custom = { cmd = "my-command" }
""".splitlines()
        result = _extract_nested_section(lines, "runners", "custom")

        assert result is not None
        assert "my-command" in result

    def test_extract_nonexistent_nested(self) -> None:
        """Test extracting a nested section that doesn't exist."""
        lines = """
[runners]
codex = { cmd = "claude" }
""".splitlines()
        result = _extract_nested_section(lines, "runners", "custom")

        assert result is None

    def test_extract_nonexistent_parent(self) -> None:
        """Test extracting from a parent section that doesn't exist."""
        lines = """
[loop]
max_iterations = 10
""".splitlines()
        result = _extract_nested_section(lines, "runners", "custom")

        assert result is None


class TestMergeConfigsText:
    """Tests for merge_configs_text function."""

    def test_merge_preserves_top_level_section(self) -> None:
        """Test that a top-level section is preserved from user config."""
        user_config = """
[loop]
max_iterations = 99

[gates]
enabled = false
""".strip()

        template_config = """
[loop]
max_iterations = 10
mode = "quality"

[gates]
enabled = true
""".strip()

        result = merge_configs_text(
            user_config, template_config, MergeConfig(preserve_sections=["loop"])
        )

        assert "max_iterations = 99" in result  # User value preserved
        # Note: mode is NOT added because entire [loop] section is replaced
        assert "[gates]" in result  # Other sections from template included

    def test_merge_preserves_nested_section(self) -> None:
        """Test that a nested section is preserved from user config."""
        user_config = """
[runners]
custom = { cmd = "my-custom-cmd" }

[loop]
max_iterations = 10
""".strip()

        template_config = """
[runners]
codex = { cmd = "claude" }

[loop]
max_iterations = 5
""".strip()

        result = merge_configs_text(
            user_config, template_config, MergeConfig(preserve_sections=["runners.custom"])
        )

        assert "my-custom-cmd" in result  # User's custom runner preserved
        assert "codex" in result  # Template's codex added

    def test_merge_adds_missing_section(self) -> None:
        """Test that a section only in user config is added to template."""
        user_config = """
[custom_section]
key = "value"
""".strip()

        template_config = """
[loop]
max_iterations = 10
""".strip()

        result = merge_configs_text(
            user_config, template_config, MergeConfig(preserve_sections=["custom_section"])
        )

        assert "[custom_section]" in result
        assert "key = \"value\"" in result
        assert "[loop]" in result

    def test_merge_no_preserve(self) -> None:
        """Test merge with no sections to preserve."""
        user_config = """
[loop]
max_iterations = 99
""".strip()

        template_config = """
[loop]
max_iterations = 10
mode = "quality"
""".strip()

        result = merge_configs_text(user_config, template_config, MergeConfig(preserve_sections=[]))

        assert "max_iterations = 10" in result  # Template value
        assert "mode = \"quality\"" in result  # Template value

    def test_merge_empty_user_config(self) -> None:
        """Test merge with empty user config."""
        user_config = ""

        template_config = """
[loop]
max_iterations = 10
""".strip()

        result = merge_configs_text(user_config, template_config, MergeConfig())

        assert result == template_config  # Returns template as-is


class TestMergeExistingConfig:
    """Tests for merge_existing_config function."""

    def test_merge_existing_config_basic(self, tmp_path: Path) -> None:
        """Test merging existing config with template."""
        # Create user config
        config_dir = tmp_path / ".ralph"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "ralph.toml"

        user_config = """
[loop]
max_iterations = 99
""".strip()
        config_file.write_text(user_config)

        # Create template
        template_file = tmp_path / "template.toml"
        template_config = """
[loop]
max_iterations = 10
mode = "quality"
""".strip()
        template_file.write_text(template_config)

        # Merge - no preserve means template wins
        result = merge_existing_config(tmp_path, template_file, MergeConfig(preserve_sections=[]))

        assert "max_iterations = 10" in result  # Template value
        assert "mode = \"quality\"" in result

    def test_merge_existing_config_preserves(self, tmp_path: Path) -> None:
        """Test that preserved sections are kept."""
        config_dir = tmp_path / ".ralph"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "ralph.toml"

        user_config = """
[loop]
max_iterations = 99
""".strip()
        config_file.write_text(user_config)

        template_file = tmp_path / "template.toml"
        template_config = """
[loop]
max_iterations = 10
mode = "quality"
""".strip()
        template_file.write_text(template_config)

        # Merge - preserve loop section
        result = merge_existing_config(
            tmp_path, template_file, MergeConfig(preserve_sections=["loop"])
        )

        assert "max_iterations = 99" in result  # User value preserved

    def test_merge_existing_config_no_user_config(self, tmp_path: Path) -> None:
        """Test merging when user config doesn't exist."""
        config_dir = tmp_path / ".ralph"
        config_dir.mkdir(parents=True, exist_ok=True)
        # No ralph.toml created

        template_file = tmp_path / "template.toml"
        template_config = "[section]\nkey = \"value\""
        template_file.write_text(template_config)

        result = merge_existing_config(tmp_path, template_file)

        assert result == template_config  # Returns template as-is

    def test_merge_existing_config_template_not_found(self, tmp_path: Path) -> None:
        """Test merging when template doesn't exist."""
        config_dir = tmp_path / ".ralph"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "ralph.toml"
        config_file.write_text("[loop]\nmax_iterations = 10")

        template_file = tmp_path / "template.toml"
        # Don't create the file

        with pytest.raises(FileNotFoundError):
            merge_existing_config(tmp_path, template_file)
