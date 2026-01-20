"""Tests for PROMPT_build.md enhancements (Phase 2).

Tests that the prompt template includes the new AUTHORIZATION & MODE section
with explicit tool authorization and no-files detection warnings.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ralph_gold.config import Config, load_config


class TestPromptBuildTemplate:
    """Tests for PROMPT_build.md template content."""

    def test_prompt_build_contains_authorization_section(self) -> None:
        """Test that PROMPT_build.md contains AUTHORIZATION & MODE section."""
        template_path = Path(__file__).parent.parent / "src" / "ralph_gold" / "templates" / "PROMPT_build.md"
        assert template_path.exists(), "PROMPT_build.md template should exist"

        content = template_path.read_text()

        # Verify main section header exists
        assert "AUTHORIZATION & MODE" in content, "Should contain AUTHORIZATION & MODE section"
        assert "REQUIRED FOR TASK COMPLETION" in content

    def test_prompt_build_lists_required_tools(self) -> None:
        """Test that prompt template lists required tools explicitly."""
        template_path = Path(__file__).parent.parent / "src" / "ralph_gold" / "templates" / "PROMPT_build.md"
        content = template_path.read_text()

        # Verify file operation tools are mentioned
        assert "`Write`" in content, "Should mention Write tool"
        assert "`Edit`" in content, "Should mention Edit tool"
        assert "`Read`" in content, "Should mention Read tool"

        # Verify verification tools
        assert "`Bash`" in content, "Should mention Bash tool"

    def test_prompt_build_mentions_no_files_detection(self) -> None:
        """Test that prompt template mentions no-files-written detection."""
        template_path = Path(__file__).parent.parent / "src" / "ralph_gold" / "templates" / "PROMPT_build.md"
        content = template_path.read_text()

        # Should mention the detection explicitly
        assert "No-files-written detection" in content or "no-files-written" in content.lower(), \
            "Should warn agent about no-files detection"

    def test_prompt_build_excludes_evidence_section(self) -> None:
        """Test that prompt template still has Evidence Discipline section."""
        template_path = Path(__file__).parent.parent / "src" / "ralph_gold" / "templates" / "PROMPT_build.md"
        content = template_path.read_text()

        # Evidence Discipline section should still be present
        assert "Evidence Discipline" in content, "Should contain Evidence Discipline section"
        assert "**Evidence**:" in content, "Should show evidence format"

    def test_prompt_build_authorization_placement(self) -> None:
        """Test that AUTHORIZATION section is placed after File writing authority."""
        template_path = Path(__file__).parent.parent / "src" / "ralph_gold" / "templates" / "PROMPT_build.md"
        content = template_path.read_text()

        # Find section positions
        file_writing_pos = content.find("File writing authority")
        auth_pos = content.find("AUTHORIZATION & MODE")
        evidence_pos = content.find("Evidence Discipline")

        # Verify ordering: File writing -> AUTHORIZATION -> Evidence
        assert file_writing_pos > 0, "Should have File writing authority section"
        assert auth_pos > file_writing_pos, "AUTHORIZATION should come after File writing authority"
        assert evidence_pos > auth_pos, "Evidence Discipline should come after AUTHORIZATION"

    def test_prompt_build_has_cannot_write_guidance(self) -> None:
        """Test that prompt template provides guidance when agent cannot write files."""
        template_path = Path(__file__).parent.parent / "src" / "ralph_gold" / "templates" / "PROMPT_build.md"
        content = template_path.read_text()

        # Should have guidance for when agent cannot write
        assert "When You Cannot Write Files" in content or "Cannot Write" in content, \
            "Should provide guidance for write failures"
        assert "remediation" in content.lower() or "fix by:" in content.lower(), \
            "Should suggest remediation steps"

    def test_prompt_build_complete_content(self) -> None:
        """Test that PROMPT_build.md has all expected sections."""
        template_path = Path(__file__).parent.parent / "src" / "ralph_gold" / "templates" / "PROMPT_build.md"
        content = template_path.read_text()

        # All expected sections should be present
        expected_sections = [
            "You are operating inside the Ralph Gold loop",
            "Rules:",
            "File writing authority",
            "AUTHORIZATION & MODE",
            "Evidence Discipline",
            "Workflow:",
            "Output:",
        ]

        for section in expected_sections:
            assert section in content, f"Should contain section: {section}"


class TestPromptBuildIntegration:
    """Integration tests for prompt template with config."""

    def test_config_loads_with_template(self, tmp_path: Path) -> None:
        """Test that config loads successfully with updated template."""
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()

        # Copy the template to test directory
        from ralph_gold.config import FilesConfig
        agents_dir = ralph_dir / "templates"
        agents_dir.mkdir(parents=True)

        template_src = Path(__file__).parent.parent / "src" / "ralph_gold" / "templates" / "PROMPT_build.md"
        template_dst = agents_dir / "PROMPT_build.md"
        template_dst.write_text(template_src.read_text())

        # Config should load without errors
        config = load_config(tmp_path)
        assert isinstance(config, Config)

    def test_template_path_resolution(self, tmp_path: Path) -> None:
        """Test that the template path is correctly resolved."""
        from ralph_gold.config import load_config

        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()
        (ralph_dir / "ralph.toml").write_text("")

        config = load_config(tmp_path)

        # The files config should have the prompt path
        assert config.files.prompt == ".ralph/PROMPT_build.md"
