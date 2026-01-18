"""Basic tests for diagnostics module to verify implementation."""

from pathlib import Path

from ralph_gold.config import load_config
from ralph_gold.diagnostics import (
    DiagnosticResult,
    check_gates,
    run_diagnostics,
    validate_config,
    validate_prd,
)


def test_diagnostic_result_creation():
    """Test that DiagnosticResult can be created."""
    result = DiagnosticResult(
        check_name="test_check",
        passed=True,
        message="Test message",
        suggestions=["suggestion 1"],
        severity="info",
    )
    assert result.check_name == "test_check"
    assert result.passed is True
    assert result.message == "Test message"
    assert result.suggestions == ["suggestion 1"]
    assert result.severity == "info"


def test_validate_config_no_file(tmp_path: Path):
    """Test config validation when no config file exists."""
    results = validate_config(tmp_path)

    assert len(results) > 0
    assert any(r.check_name == "config_exists" for r in results)

    # Should warn about missing config
    config_check = next(r for r in results if r.check_name == "config_exists")
    assert not config_check.passed
    assert config_check.severity == "warning"


def test_validate_config_valid_toml(tmp_path: Path):
    """Test config validation with valid TOML."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    _ = config_file.write_text("""
[loop]
max_iterations = 5

[files]
prd = ".ralph/PRD.md"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "--full-auto", "-"]
""")

    results = validate_config(tmp_path)

    # Should have successful TOML syntax check
    assert any(r.check_name == "toml_syntax" and r.passed for r in results)
    assert any(r.check_name == "config_schema" and r.passed for r in results)


def test_validate_config_invalid_toml(tmp_path: Path):
    """Test config validation with invalid TOML."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    _ = config_file.write_text("""
[loop
max_iterations = 5
""")  # Missing closing bracket

    results = validate_config(tmp_path)

    # Should have failed TOML syntax check
    assert any(r.check_name == "toml_syntax" and not r.passed for r in results)


def test_validate_prd_no_file(tmp_path: Path):
    """Test PRD validation when PRD file doesn't exist."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config
    config_file = ralph_dir / "ralph.toml"
    _ = config_file.write_text("""
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
    assert any(r.check_name == "prd_exists" and not r.passed for r in results)


def test_validate_prd_valid_markdown(tmp_path: Path):
    """Test PRD validation with valid Markdown PRD."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config
    config_file = ralph_dir / "ralph.toml"
    _ = config_file.write_text("""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    # Create valid Markdown PRD
    prd_file = ralph_dir / "PRD.md"
    _ = prd_file.write_text("""
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

    # Should pass PRD validation
    assert any(r.check_name == "prd_exists" and r.passed for r in results)
    assert any(r.check_name == "prd_format" and r.passed for r in results)


def test_check_gates_no_commands(tmp_path: Path):
    """Test gate testing when no gates are configured."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    _ = config_file.write_text("""
[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    cfg = load_config(tmp_path)
    results = check_gates(tmp_path, cfg)

    # Should report no gates configured
    assert any(r.check_name == "gates_configured" for r in results)


def test_check_gates_passing_command(tmp_path: Path):
    """Test gate testing with a passing command."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    _ = config_file.write_text("""
[gates]
commands = ["echo 'test'"]

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    cfg = load_config(tmp_path)
    results = check_gates(tmp_path, cfg)

    # Should have passing gate
    assert any(r.check_name == "gate_1" and r.passed for r in results)


def test_check_gates_failing_command(tmp_path: Path):
    """Test gate testing with a failing command."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    _ = config_file.write_text("""
[gates]
commands = ["exit 1"]

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    cfg = load_config(tmp_path)
    results = check_gates(tmp_path, cfg)

    # Should have failing gate
    assert any(r.check_name == "gate_1" and not r.passed for r in results)


def test_run_diagnostics_exit_codes(tmp_path: Path):
    """Test that run_diagnostics returns correct exit codes."""
    # Test with no config (should have warnings but not errors)
    results, exit_code = run_diagnostics(tmp_path, test_gates_flag=False)
    assert len(results) > 0
    # No config is a warning, not an error, so exit code should be 0
    assert exit_code == 0

    # Test with invalid TOML (should have errors)
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    config_file = ralph_dir / "ralph.toml"
    _ = config_file.write_text("[invalid toml")

    results, exit_code = run_diagnostics(tmp_path, test_gates_flag=False)
    assert exit_code == 2  # Should have errors


def test_run_diagnostics_with_gates(tmp_path: Path):
    """Test run_diagnostics with gate testing enabled."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    config_file = ralph_dir / "ralph.toml"
    _ = config_file.write_text("""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = ["echo 'test'"]

[runners.codex]
argv = ["codex", "exec", "-"]
""")

    # Create a minimal PRD file so diagnostics can proceed
    prd_file = ralph_dir / "PRD.md"
    _ = prd_file.write_text("""
# Tasks

## Task: task-1
**Status:** open
""")

    results, _exit_code = run_diagnostics(tmp_path, test_gates_flag=True)

    # Should include gate test results
    assert any("gate" in r.check_name for r in results)
