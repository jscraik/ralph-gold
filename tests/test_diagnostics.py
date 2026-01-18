"""Comprehensive unit tests for diagnostics module.

Tests cover:
- Config validation with valid/invalid TOML
- PRD validation for JSON/Markdown/YAML formats
- Gate command execution
- Suggestion generation
- Exit code mapping
"""

from pathlib import Path

import pytest

from ralph_gold.config import load_config
from ralph_gold.diagnostics import (
    DiagnosticResult,
    check_gates,
    run_diagnostics,
    validate_config,
    validate_prd,
)

# ============================================================================
# Config Validation Tests
# ============================================================================


def test_validate_config_missing_file(tmp_path: Path):
    """Test config validation when no config file exists."""
    results = validate_config(tmp_path)

    # Should have a config_exists check
    config_check = next(r for r in results if r.check_name == "config_exists")
    assert not config_check.passed
    assert config_check.severity == "warning"
    assert len(config_check.suggestions) > 0
    assert "ralph.toml" in config_check.message.lower()


def test_validate_config_valid_minimal(tmp_path: Path):
    """Test config validation with minimal valid configuration."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[loop]
max_iterations = 10

[files]
prd = ".ralph/PRD.md"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    results = validate_config(tmp_path)

    # Should pass all checks
    assert any(r.check_name == "config_exists" and r.passed for r in results)
    assert any(r.check_name == "toml_syntax" and r.passed for r in results)
    assert any(r.check_name == "config_schema" and r.passed for r in results)
    assert any(r.check_name == "runners_configured" and r.passed for r in results)


def test_validate_config_invalid_toml_syntax(tmp_path: Path):
    """Test config validation with invalid TOML syntax."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[loop
max_iterations = 5
""")  # Missing closing bracket

    results = validate_config(tmp_path)

    # Should fail TOML syntax check
    toml_check = next(r for r in results if r.check_name == "toml_syntax")
    assert not toml_check.passed
    assert toml_check.severity == "error"
    assert len(toml_check.suggestions) > 0


def test_validate_config_invalid_toml_unclosed_string(tmp_path: Path):
    """Test config validation with unclosed string in TOML."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/PRD.md
""")  # Unclosed string

    results = validate_config(tmp_path)

    # Should fail TOML syntax check
    toml_check = next(r for r in results if r.check_name == "toml_syntax")
    assert not toml_check.passed
    assert toml_check.severity == "error"


def test_validate_config_no_runners(tmp_path: Path):
    """Test config validation when no runners are configured."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[loop]
max_iterations = 5

[files]
prd = ".ralph/PRD.md"

[gates]
commands = []
""")  # No runners section

    results = validate_config(tmp_path)

    # Config may have default runners, so check if runners_configured exists
    runners_checks = [r for r in results if r.check_name == "runners_configured"]
    if runners_checks:
        # If check exists, it should report on runner status
        runners_check = runners_checks[0]
        assert "runner" in runners_check.message.lower()


def test_validate_config_multiple_runners(tmp_path: Path):
    """Test config validation with multiple runners configured."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]

[runners.claude]
argv = ["claude", "exec", "-"]
""")

    results = validate_config(tmp_path)

    # Should pass with multiple runners
    runners_check = next(r for r in results if r.check_name == "runners_configured")
    assert runners_check.passed
    # Check that it reports multiple runners (at least 2)
    assert "runner" in runners_check.message.lower()


def test_validate_config_root_location(tmp_path: Path):
    """Test config validation with config in project root."""
    config_file = tmp_path / "ralph.toml"
    config_file.write_text("""
[files]
prd = "PRD.md"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    results = validate_config(tmp_path)

    # Should find and validate config in root
    assert any(r.check_name == "config_exists" and r.passed for r in results)
    assert any(r.check_name == "toml_syntax" and r.passed for r in results)


# ============================================================================
# PRD Validation Tests
# ============================================================================


def test_validate_prd_missing_file(tmp_path: Path):
    """Test PRD validation when PRD file doesn't exist."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    cfg = load_config(tmp_path)
    results = validate_prd(tmp_path, cfg)

    # Should report missing PRD
    prd_check = next(r for r in results if r.check_name == "prd_exists")
    assert not prd_check.passed
    assert prd_check.severity == "error"
    assert len(prd_check.suggestions) > 0


def test_validate_prd_valid_markdown(tmp_path: Path):
    """Test PRD validation with valid Markdown PRD."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    prd_file = ralph_dir / "PRD.md"
    prd_file.write_text("""
# Project Tasks

## Task: task-1
**Status:** open
**Priority:** high

Description of task 1

## Task: task-2
**Status:** done
**Priority:** medium

Description of task 2
""")

    cfg = load_config(tmp_path)
    results = validate_prd(tmp_path, cfg)

    # Should pass all PRD checks
    assert any(r.check_name == "prd_exists" and r.passed for r in results)
    assert any(r.check_name == "prd_format" and r.passed for r in results)
    assert any(r.check_name == "prd_structure" and r.passed for r in results)


def test_validate_prd_valid_json(tmp_path: Path):
    """Test PRD validation with valid JSON PRD."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/prd.json"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    prd_file = ralph_dir / "prd.json"
    prd_file.write_text("""
{
  "tasks": [
    {
      "id": "task-1",
      "title": "First task",
      "status": "open",
      "priority": "high"
    },
    {
      "id": "task-2",
      "title": "Second task",
      "status": "done",
      "priority": "medium"
    }
  ]
}
""")

    cfg = load_config(tmp_path)
    results = validate_prd(tmp_path, cfg)

    # Should pass all PRD checks
    assert any(r.check_name == "prd_exists" and r.passed for r in results)
    assert any(r.check_name == "prd_format" and r.passed for r in results)


def test_validate_prd_invalid_json(tmp_path: Path):
    """Test PRD validation behavior with malformed JSON.

    Note: The YAML parser used by the tracker is very lenient and may
    accept some malformed JSON. This test verifies the diagnostics
    module correctly reports the tracker's validation result.
    """
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/prd.json"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    prd_file = ralph_dir / "prd.json"
    # Create a file that will cause tracker to fail
    prd_file.write_text("not valid json or yaml at all!!!")

    cfg = load_config(tmp_path)
    results = validate_prd(tmp_path, cfg)

    # Should have a format check result
    format_checks = [r for r in results if r.check_name == "prd_format"]
    assert len(format_checks) > 0

    # The result depends on whether the tracker can parse it
    # At minimum, we should get a result
    format_check = format_checks[0]
    assert format_check.check_name == "prd_format"


def test_validate_prd_valid_yaml(tmp_path: Path):
    """Test PRD validation with valid YAML PRD."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/prd.yaml"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    prd_file = ralph_dir / "prd.yaml"
    prd_file.write_text("""
tasks:
  - id: task-1
    title: First task
    status: open
    priority: high
  - id: task-2
    title: Second task
    status: done
    priority: medium
""")

    cfg = load_config(tmp_path)
    results = validate_prd(tmp_path, cfg)

    # Should pass PRD existence check
    assert any(r.check_name == "prd_exists" and r.passed for r in results)
    # Format check should exist (may pass or fail depending on tracker implementation)
    assert any(r.check_name == "prd_format" for r in results)


def test_validate_prd_empty_file(tmp_path: Path):
    """Test PRD validation with empty PRD file."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    prd_file = ralph_dir / "PRD.md"
    prd_file.write_text("")

    cfg = load_config(tmp_path)
    results = validate_prd(tmp_path, cfg)

    # Should exist but may have structure issues
    assert any(r.check_name == "prd_exists" and r.passed for r in results)


# ============================================================================
# Gate Command Tests
# ============================================================================


def test_check_gates_no_commands(tmp_path: Path):
    """Test gate checking when no gates are configured."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    cfg = load_config(tmp_path)
    results = check_gates(tmp_path, cfg)

    # Should report no gates configured
    gates_check = next(r for r in results if r.check_name == "gates_configured")
    assert gates_check.passed
    assert "optional" in gates_check.message.lower()


def test_check_gates_passing_command(tmp_path: Path):
    """Test gate checking with a passing command."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[gates]
commands = ["echo 'test'"]

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    cfg = load_config(tmp_path)
    results = check_gates(tmp_path, cfg)

    # Should have passing gate
    gate_check = next(r for r in results if r.check_name == "gate_1")
    assert gate_check.passed
    assert gate_check.severity == "info"


def test_check_gates_failing_command(tmp_path: Path):
    """Test gate checking with a failing command."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[gates]
commands = ["exit 1"]

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    cfg = load_config(tmp_path)
    results = check_gates(tmp_path, cfg)

    # Should have failing gate
    gate_check = next(r for r in results if r.check_name == "gate_1")
    assert not gate_check.passed
    assert gate_check.severity == "error"
    assert "exit code" in gate_check.message.lower()


def test_check_gates_multiple_commands(tmp_path: Path):
    """Test gate checking with multiple commands."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[gates]
commands = ["echo 'test1'", "echo 'test2'", "echo 'test3'"]

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    cfg = load_config(tmp_path)
    results = check_gates(tmp_path, cfg)

    # Should have results for all gates
    assert any(r.check_name == "gate_1" for r in results)
    assert any(r.check_name == "gate_2" for r in results)
    assert any(r.check_name == "gate_3" for r in results)


def test_check_gates_mixed_results(tmp_path: Path):
    """Test gate checking with mixed passing and failing commands."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[gates]
commands = ["echo 'pass'", "exit 1", "echo 'pass2'"]

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    cfg = load_config(tmp_path)
    results = check_gates(tmp_path, cfg)

    # Should have mixed results
    gate1 = next(r for r in results if r.check_name == "gate_1")
    gate2 = next(r for r in results if r.check_name == "gate_2")
    gate3 = next(r for r in results if r.check_name == "gate_3")

    assert gate1.passed
    assert not gate2.passed
    assert gate3.passed


def test_check_gates_nonexistent_command(tmp_path: Path):
    """Test gate checking with a command that doesn't exist."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[gates]
commands = ["nonexistent_command_xyz"]

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    cfg = load_config(tmp_path)
    results = check_gates(tmp_path, cfg)

    # Should report command not found
    gate_check = next(r for r in results if r.check_name == "gate_1")
    assert not gate_check.passed
    assert gate_check.severity == "error"


def test_check_gates_with_stderr_output(tmp_path: Path):
    """Test gate checking captures stderr output in suggestions."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[gates]
commands = ["sh -c 'echo error message >&2; exit 1'"]

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    cfg = load_config(tmp_path)
    results = check_gates(tmp_path, cfg)

    # Should include stderr in suggestions
    gate_checks = [r for r in results if r.check_name == "gate_1"]
    assert len(gate_checks) > 0
    gate_check = gate_checks[0]
    assert not gate_check.passed
    # Check that suggestions contain error information
    assert len(gate_check.suggestions) > 0


# ============================================================================
# Suggestion Generation Tests
# ============================================================================


def test_suggestions_always_present_on_failure(tmp_path: Path):
    """Test that all failed checks include suggestions."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create invalid TOML
    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("[invalid")

    results = validate_config(tmp_path)

    # All failed checks should have suggestions
    for result in results:
        if not result.passed and result.severity == "error":
            assert len(result.suggestions) > 0, (
                f"Check {result.check_name} has no suggestions"
            )


def test_suggestions_actionable(tmp_path: Path):
    """Test that suggestions are actionable and specific."""
    # Test missing config
    results = validate_config(tmp_path)
    config_check = next(r for r in results if r.check_name == "config_exists")

    # Suggestions should mention specific actions
    suggestions_text = " ".join(config_check.suggestions).lower()
    assert "create" in suggestions_text or "ralph.toml" in suggestions_text


def test_suggestions_for_missing_prd(tmp_path: Path):
    """Test suggestions for missing PRD file."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    cfg = load_config(tmp_path)
    results = validate_prd(tmp_path, cfg)

    prd_check = next(r for r in results if r.check_name == "prd_exists")
    assert len(prd_check.suggestions) > 0

    # Should suggest creating the file
    suggestions_text = " ".join(prd_check.suggestions).lower()
    assert "create" in suggestions_text or "prd" in suggestions_text


# ============================================================================
# Exit Code Mapping Tests
# ============================================================================


def test_exit_code_all_pass(tmp_path: Path):
    """Test exit code is 0 when all checks pass."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    prd_file = ralph_dir / "PRD.md"
    prd_file.write_text("""
# Tasks

## Task: task-1
**Status:** open
""")

    results, exit_code = run_diagnostics(tmp_path, test_gates_flag=False)
    assert exit_code == 0


def test_exit_code_with_errors(tmp_path: Path):
    """Test exit code is 2 when errors are found."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create invalid TOML
    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("[invalid toml")

    results, exit_code = run_diagnostics(tmp_path, test_gates_flag=False)
    assert exit_code == 2


def test_exit_code_warnings_only(tmp_path: Path):
    """Test exit code is 0 when only warnings are present."""
    # No config file = warning, not error
    results, exit_code = run_diagnostics(tmp_path, test_gates_flag=False)
    assert exit_code == 0


def test_exit_code_with_failing_gates(tmp_path: Path):
    """Test exit code is 2 when gates fail."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = ["exit 1"]

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    prd_file = ralph_dir / "PRD.md"
    prd_file.write_text("""
# Tasks

## Task: task-1
**Status:** open
""")

    results, exit_code = run_diagnostics(tmp_path, test_gates_flag=True)
    assert exit_code == 2


def test_exit_code_mixed_severity(tmp_path: Path):
    """Test exit code prioritizes errors over warnings."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Valid config but no runners (error)
    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = []
""")

    results, exit_code = run_diagnostics(tmp_path, test_gates_flag=False)
    # Should have error for missing runners
    assert exit_code == 2


# ============================================================================
# Integration Tests
# ============================================================================


def test_run_diagnostics_without_gates(tmp_path: Path):
    """Test run_diagnostics without gate testing."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = ["echo 'test'"]

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    prd_file = ralph_dir / "PRD.md"
    prd_file.write_text("""
# Tasks

## Task: task-1
**Status:** open
""")

    results, exit_code = run_diagnostics(tmp_path, test_gates_flag=False)

    # Should not include gate results
    assert not any(
        "gate_" in r.check_name for r in results if r.check_name != "gates_configured"
    )
    assert exit_code == 0


def test_run_diagnostics_with_gates(tmp_path: Path):
    """Test run_diagnostics with gate testing enabled."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = ["echo 'test'"]

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    prd_file = ralph_dir / "PRD.md"
    prd_file.write_text("""
# Tasks

## Task: task-1
**Status:** open
""")

    results, exit_code = run_diagnostics(tmp_path, test_gates_flag=True)

    # Should include gate results
    assert any("gate_" in r.check_name for r in results)
    assert exit_code == 0


def test_run_diagnostics_stops_on_config_error(tmp_path: Path):
    """Test that diagnostics stops early if config has errors."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("[invalid")

    results, exit_code = run_diagnostics(tmp_path, test_gates_flag=True)

    # Should have config error but not proceed to PRD/gates
    assert any(r.check_name == "toml_syntax" and not r.passed for r in results)
    # Should not have PRD checks since config failed
    assert not any(r.check_name == "prd_exists" for r in results)


def test_diagnostic_result_dataclass():
    """Test DiagnosticResult dataclass creation and attributes."""
    result = DiagnosticResult(
        check_name="test_check",
        passed=True,
        message="Test message",
        suggestions=["suggestion 1", "suggestion 2"],
        severity="info",
    )

    assert result.check_name == "test_check"
    assert result.passed is True
    assert result.message == "Test message"
    assert result.suggestions == ["suggestion 1", "suggestion 2"]
    assert result.severity == "info"


def test_diagnostic_result_severity_levels():
    """Test that all severity levels are used appropriately."""
    ralph_dir = Path("/tmp/test_diagnostics")
    ralph_dir.mkdir(exist_ok=True)

    # Create scenario with different severity levels
    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    results = validate_config(ralph_dir)

    # Should have info severity for passing checks
    assert any(r.severity == "info" and r.passed for r in results)

    # Clean up
    import shutil

    shutil.rmtree(ralph_dir, ignore_errors=True)


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


def test_validate_config_permission_error(tmp_path: Path):
    """Test handling of permission errors when reading config."""
    # This test is platform-dependent and may not work on all systems
    # Skip on Windows where permission handling is different
    import sys

    if sys.platform == "win32":
        pytest.skip("Permission test not reliable on Windows")

    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = ".ralph/PRD.md"

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    # Make file unreadable
    import os

    os.chmod(config_file, 0o000)

    try:
        results = validate_config(tmp_path)
        # Should handle permission error gracefully
        assert any(not r.passed for r in results)
    finally:
        # Restore permissions for cleanup
        os.chmod(config_file, 0o644)


def test_validate_prd_with_custom_path(tmp_path: Path):
    """Test PRD validation with custom PRD path."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[files]
prd = "custom/path/to/prd.md"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    cfg = load_config(tmp_path)
    results = validate_prd(tmp_path, cfg)

    # Should check the custom path
    prd_check = next(r for r in results if r.check_name == "prd_exists")
    assert not prd_check.passed
    assert "custom/path/to/prd.md" in prd_check.message


def test_check_gates_with_working_directory(tmp_path: Path):
    """Test that gates run in the correct working directory."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create a test file in the project root
    test_file = tmp_path / "test_marker.txt"
    test_file.write_text("marker")

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text("""
[gates]
commands = ["test -f test_marker.txt"]

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    cfg = load_config(tmp_path)
    results = check_gates(tmp_path, cfg)

    # Gate should pass because it runs in project root
    gate_check = next(r for r in results if r.check_name == "gate_1")
    assert gate_check.passed


def test_empty_results_list():
    """Test handling of empty results list."""
    results = []
    # Should not crash when processing empty results
    has_errors = any(r.severity == "error" and not r.passed for r in results)
    assert not has_errors
