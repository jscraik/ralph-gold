"""Unit tests for shell completion generation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ralph_gold.completion import (
    generate_bash_completion,
    generate_zsh_completion,
    get_dynamic_completions,
)
from ralph_gold.config import (
    Config,
    FilesConfig,
    GatesConfig,
    GitConfig,
    LlmJudgeConfig,
    LoopConfig,
    ParallelConfig,
    RunnerConfig,
    TrackerConfig,
)


# Helper function to create test configs
def _make_test_config(custom_runners: dict | None = None) -> Config:
    """Helper to create a minimal test config."""
    return Config(
        loop=LoopConfig(),
        files=FilesConfig(),
        runners=custom_runners or {},
        gates=GatesConfig(commands=[], llm_judge=LlmJudgeConfig()),
        git=GitConfig(),
        tracker=TrackerConfig(),
        parallel=ParallelConfig(),
    )


# Test bash completion generation


def test_generate_bash_completion_returns_string():
    """Test that bash completion generation returns a string."""
    script = generate_bash_completion()
    assert isinstance(script, str)
    assert len(script) > 0


def test_generate_bash_completion_contains_function():
    """Test that bash completion script contains the completion function."""
    script = generate_bash_completion()
    assert "_ralph_completion()" in script
    assert "complete -F _ralph_completion ralph" in script


def test_generate_bash_completion_contains_commands():
    """Test that bash completion script contains all main commands."""
    script = generate_bash_completion()

    # Check for main commands
    expected_commands = [
        "init",
        "doctor",
        "diagnose",
        "stats",
        "resume",
        "clean",
        "step",
        "run",
        "supervise",
        "status",
        "tui",
        "serve",
        "specs",
        "plan",
        "regen-plan",
        "snapshot",
        "rollback",
        "watch",
        "task",
        "bridge",
        "convert",
        "completion",
    ]

    for command in expected_commands:
        assert command in script


def test_generate_bash_completion_contains_global_flags():
    """Test that bash completion script contains global flags."""
    script = generate_bash_completion()

    # Check for global flags
    assert "--version" in script
    assert "--quiet" in script
    assert "--verbose" in script
    assert "--format" in script


def test_generate_bash_completion_contains_command_specific_flags():
    """Test that bash completion script contains command-specific flags."""
    script = generate_bash_completion()

    # Check for some command-specific flags
    assert "--test-gates" in script  # diagnose
    assert "--by-task" in script  # stats
    assert "--export" in script  # stats
    assert "--dry-run" in script  # multiple commands
    assert "--interactive" in script  # step
    assert "--task-id" in script  # step targeted execution
    assert "--reopen-target" in script  # step targeted execution
    assert "--graph" in script  # status
    assert "--detailed" in script  # status
    assert "--chart" in script  # status
    assert "--execution-mode" in script  # harness run modes
    assert "--strict-targeting" in script  # harness run targeting
    assert "--continue-on-target-error" in script  # harness run flow control
    assert "--pinned-input" in script  # harness collect/ci
    assert "--max-cases-per-task" in script  # harness collect/ci
    assert " pin " in script or "pin" in script  # harness pin command
    assert " ci " in script or "ci" in script  # harness ci command


def test_generate_bash_completion_contains_agent_names():
    """Test that bash completion script contains agent names."""
    script = generate_bash_completion()

    # Check for agent names
    assert "codex" in script
    assert "claude" in script
    assert "copilot" in script


def test_generate_bash_completion_contains_format_values():
    """Test that bash completion script contains format values."""
    script = generate_bash_completion()

    # Check for format values
    assert "text" in script
    assert "json" in script


def test_generate_bash_completion_contains_tracker_formats():
    """Test that bash completion script contains tracker format values."""
    script = generate_bash_completion()

    # Check for tracker formats
    assert "markdown" in script
    assert "yaml" in script


def test_generate_bash_completion_syntax_valid():
    """Test that generated bash completion script has valid syntax."""
    script = generate_bash_completion()

    # Try to check syntax using bash -n (dry run)
    # This will only work if bash is available
    try:
        result = subprocess.run(
            ["bash", "-n"], input=script, text=True, capture_output=True, timeout=5
        )
        # If bash is available, syntax should be valid (exit code 0)
        assert result.returncode == 0, f"Bash syntax error: {result.stderr}"
    except FileNotFoundError:
        # bash not available, skip syntax check
        pytest.skip("bash not available for syntax checking")


# Test zsh completion generation


def test_generate_zsh_completion_returns_string():
    """Test that zsh completion generation returns a string."""
    script = generate_zsh_completion()
    assert isinstance(script, str)
    assert len(script) > 0


def test_generate_zsh_completion_contains_compdef():
    """Test that zsh completion script contains compdef directive."""
    script = generate_zsh_completion()
    assert "#compdef ralph" in script


def test_generate_zsh_completion_contains_function():
    """Test that zsh completion script contains the completion function."""
    script = generate_zsh_completion()
    assert "_ralph()" in script
    assert '_ralph "$@"' in script


def test_generate_zsh_completion_contains_commands():
    """Test that zsh completion script contains all main commands."""
    script = generate_zsh_completion()

    # Check for main commands with descriptions
    expected_commands = [
        "init",
        "doctor",
        "diagnose",
        "stats",
        "resume",
        "clean",
        "step",
        "run",
        "supervise",
        "status",
        "tui",
        "serve",
        "specs",
        "plan",
        "regen-plan",
        "snapshot",
        "rollback",
        "watch",
        "task",
        "bridge",
        "convert",
        "completion",
    ]

    for command in expected_commands:
        assert command in script


def test_generate_zsh_completion_contains_command_descriptions():
    """Test that zsh completion script contains command descriptions."""
    script = generate_zsh_completion()

    # Check for some command descriptions
    assert "Initialize Ralph files" in script
    assert "Run diagnostic checks" in script
    assert "Display iteration statistics" in script
    assert "Run the loop" in script


def test_generate_zsh_completion_contains_global_flags():
    """Test that zsh completion script contains global flags."""
    script = generate_zsh_completion()

    # Check for global flags
    assert "--version" in script
    assert "--quiet" in script
    assert "--verbose" in script
    assert "--format" in script


def test_generate_zsh_completion_contains_command_specific_flags():
    """Test that zsh completion script contains command-specific flags."""
    script = generate_zsh_completion()

    # Check for some command-specific flags
    assert "--test-gates" in script  # diagnose
    assert "--by-task" in script  # stats
    assert "--export" in script  # stats
    assert "--dry-run" in script  # multiple commands
    assert "--interactive" in script  # step
    assert "--task-id" in script  # step targeted execution
    assert "--reopen-target" in script  # step targeted execution
    assert "--graph" in script  # status
    assert "--execution-mode" in script  # harness run modes
    assert "--strict-targeting" in script  # harness run targeting
    assert "--pinned-input" in script  # harness collect/ci
    assert "--max-cases-per-task" in script  # harness collect/ci


def test_generate_zsh_completion_contains_helper_functions():
    """Test that zsh completion script contains helper functions."""
    script = generate_zsh_completion()

    # Check for helper functions
    assert "_ralph_snapshots()" in script
    assert "_ralph_templates()" in script


def test_generate_zsh_completion_syntax_valid():
    """Test that generated zsh completion script has valid syntax."""
    script = generate_zsh_completion()

    # Try to check syntax using zsh -n (dry run)
    # This will only work if zsh is available
    try:
        result = subprocess.run(
            ["zsh", "-n"], input=script, text=True, capture_output=True, timeout=5
        )
        # If zsh is available, syntax should be valid (exit code 0)
        assert result.returncode == 0, f"Zsh syntax error: {result.stderr}"
    except FileNotFoundError:
        # zsh not available, skip syntax check
        pytest.skip("zsh not available for syntax checking")


# Test dynamic completions


def test_get_dynamic_completions_agents(tmp_path: Path):
    """Test getting dynamic completions for agent names."""
    cfg = _make_test_config()

    completions = get_dynamic_completions(tmp_path, cfg, "agents", "")

    # Should include default agents
    assert "codex" in completions
    assert "claude" in completions
    assert "copilot" in completions


def test_get_dynamic_completions_agents_with_partial(tmp_path: Path):
    """Test getting dynamic completions for agents with partial string."""
    cfg = _make_test_config()

    completions = get_dynamic_completions(tmp_path, cfg, "agents", "co")

    # Should only include agents starting with "co"
    assert "codex" in completions
    assert "copilot" in completions
    assert "claude" not in completions


def test_get_dynamic_completions_agents_with_custom_runners(tmp_path: Path):
    """Test getting dynamic completions includes custom runners."""
    cfg = _make_test_config(
        custom_runners={"custom-agent": RunnerConfig(argv=["custom"])}
    )

    completions = get_dynamic_completions(tmp_path, cfg, "agents", "")

    # Should include custom runner
    assert "custom-agent" in completions
    # Should also include defaults
    assert "codex" in completions


def test_get_dynamic_completions_formats(tmp_path: Path):
    """Test getting dynamic completions for output formats."""
    cfg = _make_test_config()

    completions = get_dynamic_completions(tmp_path, cfg, "formats", "")

    assert "text" in completions
    assert "json" in completions


def test_get_dynamic_completions_tracker_formats(tmp_path: Path):
    """Test getting dynamic completions for tracker formats."""
    cfg = _make_test_config()

    completions = get_dynamic_completions(tmp_path, cfg, "tracker_formats", "")

    assert "markdown" in completions
    assert "json" in completions
    assert "yaml" in completions


def test_get_dynamic_completions_templates_fallback(tmp_path: Path):
    """Test getting dynamic completions for templates with fallback."""
    cfg = _make_test_config()

    # No templates directory exists, should fallback to built-in
    completions = get_dynamic_completions(tmp_path, cfg, "templates", "")

    # Should include built-in templates
    assert "bug-fix" in completions
    assert "feature" in completions
    assert "refactor" in completions


def test_get_dynamic_completions_templates_with_custom(tmp_path: Path):
    """Test getting dynamic completions for templates with custom templates."""
    import json

    cfg = _make_test_config()

    # Create custom template
    templates_dir = tmp_path / ".ralph" / "templates"
    templates_dir.mkdir(parents=True)

    custom_template = {
        "name": "custom-template",
        "description": "Custom template",
        "title_template": "Custom: {title}",
        "acceptance_criteria": ["Done"],
    }

    template_file = templates_dir / "custom-template.json"
    template_file.write_text(json.dumps(custom_template), encoding="utf-8")

    completions = get_dynamic_completions(tmp_path, cfg, "templates", "")

    # Should include custom template
    assert "custom-template" in completions
    # Should also include built-in templates
    assert "bug-fix" in completions


def test_get_dynamic_completions_snapshots_empty(tmp_path: Path):
    """Test getting dynamic completions for snapshots when none exist."""
    cfg = _make_test_config()

    completions = get_dynamic_completions(tmp_path, cfg, "snapshots", "")

    # Should return empty list when no snapshots exist
    assert completions == []


def test_get_dynamic_completions_unknown_type(tmp_path: Path):
    """Test getting dynamic completions for unknown type."""
    cfg = _make_test_config()

    completions = get_dynamic_completions(tmp_path, cfg, "unknown", "")

    # Should return empty list for unknown type
    assert completions == []


def test_get_dynamic_completions_sorted(tmp_path: Path):
    """Test that dynamic completions are sorted."""
    cfg = _make_test_config()

    completions = get_dynamic_completions(tmp_path, cfg, "agents", "")

    # Should be sorted alphabetically
    assert completions == sorted(completions)


# Test edge cases


def test_bash_completion_handles_special_characters():
    """Test that bash completion script properly escapes special characters."""
    script = generate_bash_completion()

    # Should not have unescaped special characters that would break bash
    # Check that quotes are properly handled
    assert script.count('"') % 2 == 0 or script.count("'") > 0


def test_zsh_completion_handles_special_characters():
    """Test that zsh completion script properly escapes special characters."""
    script = generate_zsh_completion()

    # Should not have unescaped special characters that would break zsh
    # Check that quotes are properly handled
    assert script.count('"') % 2 == 0 or script.count("'") > 0


def test_bash_completion_contains_subcommands():
    """Test that bash completion script handles subcommands."""
    script = generate_bash_completion()

    # Check for subcommands
    assert "specs" in script
    assert "check" in script  # specs check
    assert "task" in script
    assert "add" in script  # task add
    assert "templates" in script  # task templates


def test_zsh_completion_contains_subcommands():
    """Test that zsh completion script handles subcommands."""
    script = generate_zsh_completion()

    # Check for subcommands
    assert "specs" in script
    assert "check" in script  # specs check
    assert "task" in script
    assert "add" in script  # task add
    assert "templates" in script  # task templates


def test_bash_completion_file_completion():
    """Test that bash completion script includes file completion hints."""
    script = generate_bash_completion()

    # Check for file completion patterns
    assert "_files" in script or "compgen -f" in script or "--export" in script


def test_zsh_completion_file_completion():
    """Test that zsh completion script includes file completion hints."""
    script = generate_zsh_completion()

    # Check for file completion patterns
    assert "_files" in script or "_directories" in script


def test_get_dynamic_completions_handles_load_errors(tmp_path: Path):
    """Test that dynamic completions handle load errors gracefully."""

    cfg = _make_test_config()

    # Create invalid template file
    templates_dir = tmp_path / ".ralph" / "templates"
    templates_dir.mkdir(parents=True)

    template_file = templates_dir / "invalid.json"
    template_file.write_text("{ invalid json }", encoding="utf-8")

    # Should fallback to built-in templates without crashing
    completions = get_dynamic_completions(tmp_path, cfg, "templates", "")

    # Should still have built-in templates
    assert "bug-fix" in completions
    assert "feature" in completions
    assert "refactor" in completions


def test_bash_completion_installation_instructions():
    """Test that bash completion script includes installation instructions."""
    script = generate_bash_completion()

    # Should include installation instructions in comments
    assert "source" in script or "Source this file" in script
    assert ".bashrc" in script or "bash_completion" in script


def test_zsh_completion_installation_instructions():
    """Test that zsh completion script includes installation instructions."""
    script = generate_zsh_completion()

    # Should include installation instructions in comments
    assert "fpath" in script or "Install" in script
    assert "compinit" in script


def test_bash_completion_dynamic_snapshot_completion():
    """Test that bash completion script includes dynamic snapshot completion."""
    script = generate_bash_completion()

    # Should have logic for completing snapshot names
    assert "rollback" in script
    assert "snapshot" in script


def test_zsh_completion_dynamic_template_completion():
    """Test that zsh completion script includes dynamic template completion."""
    script = generate_zsh_completion()

    # Should have helper function for template completion
    assert "_ralph_templates" in script
    assert "ralph task templates" in script


def test_get_dynamic_completions_empty_partial(tmp_path: Path):
    """Test that empty partial string returns all completions."""
    cfg = _make_test_config()

    completions = get_dynamic_completions(tmp_path, cfg, "agents", "")

    # Should return all agents
    assert len(completions) >= 3


def test_get_dynamic_completions_no_match(tmp_path: Path):
    """Test that partial string with no matches returns empty list."""
    cfg = _make_test_config()

    completions = get_dynamic_completions(tmp_path, cfg, "agents", "xyz")

    # Should return empty list
    assert completions == []


# Property-Based Tests


def test_property_34_bash_completion_script_validity():
    """
    **Validates: Requirements 12.1**

    Feature: ralph-enhancement-phase2, Property 34
    For any generated bash completion script, it should be syntactically
    valid for bash.
    """
    from hypothesis import given, settings
    from hypothesis import strategies as st

    @given(st.integers(min_value=0, max_value=100))
    @settings(max_examples=100, deadline=None)
    def property_bash_syntax_valid(_seed: int):
        """Test that bash completion script is always syntactically valid."""
        # Generate the bash completion script
        script = generate_bash_completion()

        # Verify it's a non-empty string
        assert isinstance(script, str)
        assert len(script) > 0

        # Verify it contains the completion function
        assert "_ralph_completion()" in script
        assert "complete -F _ralph_completion ralph" in script

        # Try to validate syntax with bash if available
        try:
            result = subprocess.run(
                ["bash", "-n"],
                input=script,
                text=True,
                capture_output=True,
                timeout=5,
            )
            # Bash syntax check should pass (exit code 0)
            assert result.returncode == 0, f"Bash syntax error: {result.stderr}"
        except FileNotFoundError:
            # bash not available, skip syntax check but verify structure
            # Verify basic bash syntax elements are present
            assert "local " in script
            assert "case " in script
            assert "esac" in script
            assert "COMPREPLY=" in script

    property_bash_syntax_valid()


def test_property_34_zsh_completion_script_validity():
    """
    **Validates: Requirements 12.2**

    Feature: ralph-enhancement-phase2, Property 34
    For any generated zsh completion script, it should be syntactically
    valid for zsh.
    """
    from hypothesis import given, settings
    from hypothesis import strategies as st

    @given(st.integers(min_value=0, max_value=100))
    @settings(max_examples=100, deadline=None)
    def property_zsh_syntax_valid(_seed: int):
        """Test that zsh completion script is always syntactically valid."""
        # Generate the zsh completion script
        script = generate_zsh_completion()

        # Verify it's a non-empty string
        assert isinstance(script, str)
        assert len(script) > 0

        # Verify it contains the compdef directive
        assert "#compdef ralph" in script

        # Verify it contains the completion function
        assert "_ralph()" in script
        assert '_ralph "$@"' in script

        # Try to validate syntax with zsh if available
        try:
            result = subprocess.run(
                ["zsh", "-n"],
                input=script,
                text=True,
                capture_output=True,
                timeout=5,
            )
            # Zsh syntax check should pass (exit code 0)
            assert result.returncode == 0, f"Zsh syntax error: {result.stderr}"
        except FileNotFoundError:
            # zsh not available, skip syntax check but verify structure
            # Verify basic zsh syntax elements are present
            assert "_arguments" in script
            assert "local " in script
            assert "case " in script
            assert "esac" in script

    property_zsh_syntax_valid()


def test_property_35_dynamic_completion_accuracy_agents():
    """
    **Validates: Requirements 12.3**

    Feature: ralph-enhancement-phase2, Property 35
    For any completion context requiring dynamic agent values, the completion
    suggestions should match the currently available agents from configuration.
    """
    from hypothesis import given, settings
    from hypothesis import strategies as st

    @given(
        st.lists(
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("Ll", "Lu", "Nd"), min_codepoint=97
                ),
                min_size=1,
                max_size=20,
            ),
            min_size=0,
            max_size=10,
            unique=True,
        )
    )
    @settings(max_examples=100)
    def property_agent_completions_accurate(custom_agent_names: list[str]):
        """Test that agent completions match configured agents."""
        import tempfile

        # Create a temporary directory for the test
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create custom runners config
            custom_runners = {
                name: RunnerConfig(argv=[name]) for name in custom_agent_names
            }
            cfg = _make_test_config(custom_runners=custom_runners)

            # Get agent completions
            completions = get_dynamic_completions(project_root, cfg, "agents", "")

            # Verify all default agents are present
            assert "codex" in completions
            assert "claude" in completions
            assert "copilot" in completions

            # Verify all custom agents are present
            for agent_name in custom_agent_names:
                assert agent_name in completions

            # Verify no duplicates
            assert len(completions) == len(set(completions))

            # Verify sorted
            assert completions == sorted(completions)

    property_agent_completions_accurate()


def test_property_35_dynamic_completion_accuracy_partial_match():
    """
    **Validates: Requirements 12.3**

    Feature: ralph-enhancement-phase2, Property 35
    For any partial string, dynamic completions should only return values
    that start with the partial string.
    """
    from hypothesis import given, settings
    from hypothesis import strategies as st

    @given(
        st.sampled_from(["agents", "formats", "tracker_formats"]),
        st.text(
            alphabet=st.characters(whitelist_categories=("Ll",), min_codepoint=97),
            min_size=0,
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def property_partial_match_accurate(completion_type: str, partial: str):
        """Test that partial matching filters completions correctly."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            cfg = _make_test_config()

            # Get completions with partial string
            completions = get_dynamic_completions(
                project_root, cfg, completion_type, partial
            )

            # Verify all completions start with the partial string
            for completion in completions:
                assert completion.startswith(partial), (
                    f"Completion '{completion}' does not start with '{partial}'"
                )

            # Verify sorted
            assert completions == sorted(completions)

            # Verify no duplicates
            assert len(completions) == len(set(completions))

    property_partial_match_accurate()


def test_property_35_dynamic_completion_accuracy_formats():
    """
    **Validates: Requirements 12.3**

    Feature: ralph-enhancement-phase2, Property 35
    For format completions, the suggestions should always include the
    standard format values.
    """
    from hypothesis import given, settings
    from hypothesis import strategies as st

    @given(st.integers(min_value=0, max_value=100))
    @settings(max_examples=100)
    def property_format_completions_accurate(_seed: int):
        """Test that format completions are accurate."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            cfg = _make_test_config()

            # Get format completions
            completions = get_dynamic_completions(project_root, cfg, "formats", "")

            # Verify standard formats are present
            assert "text" in completions
            assert "json" in completions

            # Verify sorted
            assert completions == sorted(completions)

            # Get tracker format completions
            tracker_completions = get_dynamic_completions(
                project_root, cfg, "tracker_formats", ""
            )

            # Verify standard tracker formats are present
            assert "markdown" in tracker_completions
            assert "json" in tracker_completions
            assert "yaml" in tracker_completions

            # Verify sorted
            assert tracker_completions == sorted(tracker_completions)

    property_format_completions_accurate()


def test_property_35_dynamic_completion_accuracy_templates():
    """
    **Validates: Requirements 12.3**

    Feature: ralph-enhancement-phase2, Property 35
    For template completions, the suggestions should include built-in
    templates and any custom templates that exist.
    """
    from hypothesis import given, settings
    from hypothesis import strategies as st

    @given(
        st.lists(
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("Ll", "Nd"), min_codepoint=97
                ),
                min_size=1,
                max_size=20,
            ),
            min_size=0,
            max_size=5,
            unique=True,
        )
    )
    @settings(max_examples=100)
    def property_template_completions_accurate(custom_template_names: list[str]):
        """Test that template completions include built-in and custom templates."""
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            cfg = _make_test_config()

            # Create custom templates
            if custom_template_names:
                templates_dir = project_root / ".ralph" / "templates"
                templates_dir.mkdir(parents=True)

                for template_name in custom_template_names:
                    template_data = {
                        "name": template_name,
                        "description": f"Template {template_name}",
                        "title_template": f"{template_name}: {{title}}",
                        "acceptance_criteria": ["Done"],
                    }
                    template_file = templates_dir / f"{template_name}.json"
                    _ = template_file.write_text(
                        json.dumps(template_data), encoding="utf-8"
                    )

            # Get template completions
            completions = get_dynamic_completions(project_root, cfg, "templates", "")

            # Verify built-in templates are present
            assert "bug-fix" in completions
            assert "feature" in completions
            assert "refactor" in completions

            # Verify custom templates are present
            for template_name in custom_template_names:
                assert template_name in completions, (
                    f"Custom template '{template_name}' not in completions"
                )

            # Verify sorted
            assert completions == sorted(completions)

            # Verify no duplicates
            assert len(completions) == len(set(completions))

    property_template_completions_accurate()


def test_property_34_completion_script_structure():
    """
    **Validates: Requirements 12.1, 12.2**

    Feature: ralph-enhancement-phase2, Property 34
    For any generated completion script, it should contain all required
    commands and flags.
    """
    from hypothesis import given, settings
    from hypothesis import strategies as st

    @given(st.sampled_from(["bash", "zsh"]))
    @settings(max_examples=100)
    def property_completion_contains_all_commands(shell: str):
        """Test that completion scripts contain all commands."""
        # Generate the appropriate completion script
        if shell == "bash":
            script = generate_bash_completion()
        else:
            script = generate_zsh_completion()

        # Define all expected commands
        expected_commands = [
            "init",
            "doctor",
            "diagnose",
            "stats",
            "resume",
            "clean",
            "step",
            "run",
            "status",
            "tui",
            "serve",
            "specs",
            "plan",
            "regen-plan",
            "snapshot",
            "rollback",
            "watch",
            "task",
            "bridge",
            "convert",
            "completion",
        ]

        # Verify all commands are present
        for command in expected_commands:
            assert command in script, (
                f"Command '{command}' not found in {shell} completion script"
            )

        # Define expected global flags
        expected_flags = ["--version", "--quiet", "--verbose", "--format"]

        # Verify all global flags are present
        for flag in expected_flags:
            assert flag in script, (
                f"Flag '{flag}' not found in {shell} completion script"
            )

    property_completion_contains_all_commands()


def test_property_35_dynamic_completion_empty_on_error():
    """
    **Validates: Requirements 12.3**

    Feature: ralph-enhancement-phase2, Property 35
    For any completion type that encounters an error during loading,
    the function should return a valid (possibly empty) list rather than
    raising an exception.
    """
    from hypothesis import given, settings
    from hypothesis import strategies as st

    @given(
        st.sampled_from(
            ["agents", "templates", "snapshots", "formats", "tracker_formats"]
        )
    )
    @settings(max_examples=100)
    def property_completions_handle_errors_gracefully(
        completion_type: str,
    ):
        """Test that completion errors are handled gracefully."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create invalid state that might cause errors
            ralph_dir = project_root / ".ralph"
            ralph_dir.mkdir()

            # Create invalid template file
            if completion_type == "templates":
                templates_dir = ralph_dir / "templates"
                templates_dir.mkdir()
                invalid_file = templates_dir / "invalid.json"
                _ = invalid_file.write_text("{ invalid json }", encoding="utf-8")

            cfg = _make_test_config()

            # Get completions - should not raise exception
            try:
                completions = get_dynamic_completions(
                    project_root, cfg, completion_type, ""
                )

                # Should return a list (possibly empty)
                assert isinstance(completions, list)

                # All items should be strings
                for item in completions:
                    assert isinstance(item, str)

                # Should be sorted
                assert completions == sorted(completions)

                # Should have no duplicates
                assert len(completions) == len(set(completions))

            except Exception as e:
                pytest.fail(
                    f"get_dynamic_completions raised exception for {completion_type}: {e}"
                )

    property_completions_handle_errors_gracefully()
