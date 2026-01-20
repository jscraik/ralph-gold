"""Tests for PromptConfig updated defaults (Phase 1).

Tests that the new default values for spec limits are correctly set:
- max_specs_chars: 100000 (increased from 50000)
- max_single_spec_chars: 50000 (increased from 10000)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ralph_gold.config import PromptConfig, load_config


class TestPromptConfigDefaults:
    """Tests for PromptConfig default values after Phase 1 update."""

    def test_prompt_config_new_defaults(self) -> None:
        """Test PromptConfig has updated default values."""
        config = PromptConfig()
        assert config.enable_limits is False
        assert config.max_specs_files == 20
        assert config.max_specs_chars == 100000, "max_specs_chars should be 100000 (2x increase)"
        assert config.max_single_spec_chars == 50000, "max_single_spec_chars should be 50000 (5x increase)"
        assert config.truncate_long_specs is True
        assert config.specs_inclusion_order == "sorted"

    def test_prompt_config_custom_overrides(self) -> None:
        """Test PromptConfig can be overridden with custom values."""
        config = PromptConfig(
            enable_limits=True,
            max_specs_files=5,
            max_specs_chars=75000,
            max_single_spec_chars=25000,
            truncate_long_specs=False,
            specs_inclusion_order="recency",
        )
        assert config.enable_limits is True
        assert config.max_specs_files == 5
        assert config.max_specs_chars == 75000
        assert config.max_single_spec_chars == 25000
        assert config.truncate_long_specs is False
        assert config.specs_inclusion_order == "recency"

    def test_prompt_config_immutable(self) -> None:
        """Test PromptConfig is frozen (immutable)."""
        config = PromptConfig()
        with pytest.raises(Exception):  # FrozenInstanceError from dataclasses
            config.max_specs_chars = 99999


class TestLoadConfigWithDefaults:
    """Tests for load_config using new PromptConfig defaults."""

    def test_load_config_default_prompt_limits(self, tmp_path: Path) -> None:
        """Test loading config uses new PromptConfig defaults."""
        # Create empty ralph.toml to use defaults
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()
        (ralph_dir / "ralph.toml").write_text("")

        config = load_config(tmp_path)

        assert config.prompt.max_specs_chars == 100000
        assert config.prompt.max_single_spec_chars == 50000
        assert config.prompt.max_specs_files == 20

    def test_load_config_with_custom_prompt_limits(self, tmp_path: Path) -> None:
        """Test loading config with custom prompt limits overrides."""
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()
        (ralph_dir / "ralph.toml").write_text("""
[prompt]
enable_limits = true
max_specs_chars = 75000
max_single_spec_chars = 25000
""")

        config = load_config(tmp_path)

        assert config.prompt.enable_limits is True
        assert config.prompt.max_specs_chars == 75000
        assert config.prompt.max_single_spec_chars == 25000

    def test_load_config_partial_prompt_override(self, tmp_path: Path) -> None:
        """Test loading config with partial prompt override uses defaults for others."""
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()
        # Only override max_specs_chars, others should use defaults
        (ralph_dir / "ralph.toml").write_text("""
[prompt]
max_specs_chars = 75000
""")

        config = load_config(tmp_path)

        assert config.prompt.max_specs_chars == 75000
        assert config.prompt.max_single_spec_chars == 50000  # Default
        assert config.prompt.max_specs_files == 20  # Default
