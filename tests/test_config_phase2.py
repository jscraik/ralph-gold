"""Tests for Phase 2 configuration schema extensions.

Tests the new configuration sections added in Phase 2:
- diagnostics
- stats
- watch
- progress
- templates
- output
"""

from pathlib import Path
from textwrap import dedent

import pytest

from ralph_gold.config import (
    DiagnosticsConfig,
    OutputControlConfig,
    ProgressConfig,
    StatsConfig,
    TemplatesConfig,
    WatchConfig,
    load_config,
)


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    return tmp_path


def test_diagnostics_config_defaults(temp_project: Path):
    """Test that diagnostics config has correct defaults."""
    # Create minimal config
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text("[loop]\nmax_iterations = 10\n")

    cfg = load_config(temp_project)

    assert cfg.diagnostics.enabled is True
    assert cfg.diagnostics.check_gates is True
    assert cfg.diagnostics.validate_prd is True


def test_diagnostics_config_custom(temp_project: Path):
    """Test custom diagnostics configuration."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 10

        [diagnostics]
        enabled = false
        check_gates = false
        validate_prd = true
        """
        )
    )

    cfg = load_config(temp_project)

    assert cfg.diagnostics.enabled is False
    assert cfg.diagnostics.check_gates is False
    assert cfg.diagnostics.validate_prd is True


def test_stats_config_defaults(temp_project: Path):
    """Test that stats config has correct defaults."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text("[loop]\nmax_iterations = 10\n")

    cfg = load_config(temp_project)

    assert cfg.stats.track_duration is True
    assert cfg.stats.track_cost is False


def test_stats_config_custom(temp_project: Path):
    """Test custom stats configuration."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 10

        [stats]
        track_duration = false
        track_cost = true
        """
        )
    )

    cfg = load_config(temp_project)

    assert cfg.stats.track_duration is False
    assert cfg.stats.track_cost is True


def test_watch_config_defaults(temp_project: Path):
    """Test that watch config has correct defaults."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text("[loop]\nmax_iterations = 10\n")

    cfg = load_config(temp_project)

    assert cfg.watch.enabled is False
    assert cfg.watch.patterns == ["**/*.py", "**/*.md"]
    assert cfg.watch.debounce_ms == 500
    assert cfg.watch.auto_commit is False


def test_watch_config_custom(temp_project: Path):
    """Test custom watch configuration."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 10

        [watch]
        enabled = true
        patterns = ["src/**/*.py", "tests/**/*.py", "*.toml"]
        debounce_ms = 1000
        auto_commit = true
        """
        )
    )

    cfg = load_config(temp_project)

    assert cfg.watch.enabled is True
    assert cfg.watch.patterns == ["src/**/*.py", "tests/**/*.py", "*.toml"]
    assert cfg.watch.debounce_ms == 1000
    assert cfg.watch.auto_commit is True


def test_watch_config_empty_patterns(temp_project: Path):
    """Test watch config with empty patterns list."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 10

        [watch]
        patterns = []
        """
        )
    )

    cfg = load_config(temp_project)

    assert cfg.watch.patterns == []


def test_progress_config_defaults(temp_project: Path):
    """Test that progress config has correct defaults."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text("[loop]\nmax_iterations = 10\n")

    cfg = load_config(temp_project)

    assert cfg.progress.show_velocity is True
    assert cfg.progress.show_burndown is True
    assert cfg.progress.chart_width == 60


def test_progress_config_custom(temp_project: Path):
    """Test custom progress configuration."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 10

        [progress]
        show_velocity = false
        show_burndown = false
        chart_width = 80
        """
        )
    )

    cfg = load_config(temp_project)

    assert cfg.progress.show_velocity is False
    assert cfg.progress.show_burndown is False
    assert cfg.progress.chart_width == 80


def test_templates_config_defaults(temp_project: Path):
    """Test that templates config has correct defaults."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text("[loop]\nmax_iterations = 10\n")

    cfg = load_config(temp_project)

    assert cfg.templates.builtin == ["bug-fix", "feature", "refactor"]
    assert cfg.templates.custom_dir == ".ralph/templates"


def test_templates_config_custom(temp_project: Path):
    """Test custom templates configuration."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 10

        [templates]
        builtin = ["bug-fix", "feature"]
        custom_dir = ".ralph/my-templates"
        """
        )
    )

    cfg = load_config(temp_project)

    assert cfg.templates.builtin == ["bug-fix", "feature"]
    assert cfg.templates.custom_dir == ".ralph/my-templates"


def test_templates_config_empty_builtin(temp_project: Path):
    """Test templates config with no built-in templates."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 10

        [templates]
        builtin = []
        """
        )
    )

    cfg = load_config(temp_project)

    assert cfg.templates.builtin == []


def test_output_config_defaults(temp_project: Path):
    """Test that output config has correct defaults."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text("[loop]\nmax_iterations = 10\n")

    cfg = load_config(temp_project)

    assert cfg.output.verbosity == "normal"
    assert cfg.output.format == "text"


def test_output_config_quiet(temp_project: Path):
    """Test output config with quiet verbosity."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 10

        [output]
        verbosity = "quiet"
        format = "text"
        """
        )
    )

    cfg = load_config(temp_project)

    assert cfg.output.verbosity == "quiet"
    assert cfg.output.format == "text"


def test_output_config_verbose(temp_project: Path):
    """Test output config with verbose verbosity."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 10

        [output]
        verbosity = "verbose"
        format = "json"
        """
        )
    )

    cfg = load_config(temp_project)

    assert cfg.output.verbosity == "verbose"
    assert cfg.output.format == "json"


def test_output_config_invalid_verbosity(temp_project: Path):
    """Test that invalid verbosity falls back to default."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 10

        [output]
        verbosity = "invalid"
        """
        )
    )

    cfg = load_config(temp_project)

    # Should fall back to default
    assert cfg.output.verbosity == "normal"


def test_output_config_invalid_format(temp_project: Path):
    """Test that invalid format falls back to default."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 10

        [output]
        format = "xml"
        """
        )
    )

    cfg = load_config(temp_project)

    # Should fall back to default
    assert cfg.output.format == "text"


def test_all_phase2_configs_together(temp_project: Path):
    """Test loading all Phase 2 configs together."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 10

        [diagnostics]
        enabled = true
        check_gates = false

        [stats]
        track_duration = true
        track_cost = false

        [watch]
        enabled = true
        patterns = ["**/*.py"]
        debounce_ms = 750

        [progress]
        show_velocity = true
        chart_width = 70

        [templates]
        builtin = ["bug-fix"]
        custom_dir = ".ralph/custom"

        [output]
        verbosity = "verbose"
        format = "json"
        """
        )
    )

    cfg = load_config(temp_project)

    # Verify all sections loaded correctly
    assert cfg.diagnostics.enabled is True
    assert cfg.diagnostics.check_gates is False

    assert cfg.stats.track_duration is True
    assert cfg.stats.track_cost is False

    assert cfg.watch.enabled is True
    assert cfg.watch.patterns == ["**/*.py"]
    assert cfg.watch.debounce_ms == 750

    assert cfg.progress.show_velocity is True
    assert cfg.progress.chart_width == 70

    assert cfg.templates.builtin == ["bug-fix"]
    assert cfg.templates.custom_dir == ".ralph/custom"

    assert cfg.output.verbosity == "verbose"
    assert cfg.output.format == "json"


def test_phase2_configs_with_phase1_configs(temp_project: Path):
    """Test that Phase 2 configs work alongside Phase 1 configs."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 50
        no_progress_limit = 3

        [files]
        prd = ".ralph/PRD.md"
        progress = ".ralph/progress.md"

        [git]
        auto_commit = false
        branch_strategy = "none"

        [gates]
        commands = ["npm test"]

        [diagnostics]
        enabled = true

        [stats]
        track_duration = true

        [output]
        verbosity = "normal"

        [runners.codex]
        argv = ["codex", "exec", "--full-auto", "-"]
        """
        )
    )

    cfg = load_config(temp_project)

    # Verify Phase 1 configs still work
    assert cfg.loop.max_iterations == 50
    assert cfg.loop.no_progress_limit == 3
    assert cfg.files.prd == ".ralph/PRD.md"
    assert cfg.git.auto_commit is False
    assert cfg.gates.commands == ["npm test"]

    # Verify Phase 2 configs work
    assert cfg.diagnostics.enabled is True
    assert cfg.stats.track_duration is True
    assert cfg.output.verbosity == "normal"


def test_config_dataclass_immutability():
    """Test that Phase 2 config dataclasses are immutable (frozen)."""
    diagnostics = DiagnosticsConfig()
    with pytest.raises(AttributeError):
        diagnostics.enabled = False  # type: ignore

    stats = StatsConfig()
    with pytest.raises(AttributeError):
        stats.track_duration = False  # type: ignore

    watch = WatchConfig()
    with pytest.raises(AttributeError):
        watch.enabled = True  # type: ignore

    progress = ProgressConfig()
    with pytest.raises(AttributeError):
        progress.chart_width = 100  # type: ignore

    templates = TemplatesConfig()
    with pytest.raises(AttributeError):
        templates.custom_dir = "other"  # type: ignore

    output = OutputControlConfig()
    with pytest.raises(AttributeError):
        output.verbosity = "quiet"  # type: ignore


def test_backward_compatibility_no_phase2_sections(temp_project: Path):
    """Test that configs without Phase 2 sections still work (backward compatibility)."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    # Old-style config without any Phase 2 sections
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 10

        [files]
        prd = ".ralph/PRD.md"

        [gates]
        commands = []

        [runners.codex]
        argv = ["codex", "exec", "--full-auto", "-"]
        """
        )
    )

    cfg = load_config(temp_project)

    # Should load successfully with defaults
    assert cfg.diagnostics.enabled is True
    assert cfg.stats.track_duration is True
    assert cfg.watch.enabled is False
    assert cfg.progress.show_velocity is True
    assert cfg.templates.builtin == ["bug-fix", "feature", "refactor"]
    assert cfg.output.verbosity == "normal"


def test_config_type_coercion(temp_project: Path):
    """Test that config values are properly coerced to correct types."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 10

        [diagnostics]
        enabled = 1  # Should coerce to True

        [watch]
        debounce_ms = "500"  # Should coerce to int

        [progress]
        chart_width = 60.5  # Should coerce to int
        """
        )
    )

    cfg = load_config(temp_project)

    assert cfg.diagnostics.enabled is True
    assert cfg.watch.debounce_ms == 500
    assert cfg.progress.chart_width == 60


def test_empty_config_sections(temp_project: Path):
    """Test that empty config sections use defaults."""
    config_path = temp_project / ".ralph" / "ralph.toml"
    config_path.write_text(
        dedent(
            """
        [loop]
        max_iterations = 10

        [diagnostics]

        [stats]

        [watch]

        [progress]

        [templates]

        [output]
        """
        )
    )

    cfg = load_config(temp_project)

    # All should have default values
    assert cfg.diagnostics.enabled is True
    assert cfg.stats.track_duration is True
    assert cfg.watch.enabled is False
    assert cfg.progress.show_velocity is True
    assert cfg.templates.builtin == ["bug-fix", "feature", "refactor"]
    assert cfg.output.verbosity == "normal"
