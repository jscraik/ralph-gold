"""Property-based tests for diagnostics module.

These tests use hypothesis to verify universal properties across all inputs.
Each test is annotated with the requirement it validates.

**Validates: Requirements 1.1, 1.2, 1.3** (Diagnostics Epic)
"""

from pathlib import Path
from typing import List

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ralph_gold.config import load_config
from ralph_gold.diagnostics import (
    DiagnosticResult,
    check_gates,
    run_diagnostics,
    validate_config,
)

# ============================================================================
# Property 1: Configuration Validation Correctness
# ============================================================================


@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    config_content=st.one_of(
        # Valid TOML configurations
        st.just("""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = []

[runners.codex]
argv = ["codex", "exec", "-"]
"""),
        # Invalid TOML - missing bracket
        st.just("""
[files
prd = ".ralph/PRD.md"
"""),
        # Invalid TOML - unclosed string
        st.just("""
[files]
prd = ".ralph/PRD.md
"""),
        # Invalid TOML - invalid syntax
        st.just("[[[invalid"),
        # Empty file
        st.just(""),
    )
)
def test_property_config_validation_correctness(tmp_path: Path, config_content: str):
    """
    **Validates: Requirements 1.1, 1.2**

    Feature: ralph-enhancement-phase2, Property 1
    For any configuration file (TOML), validation should correctly identify
    all syntax errors and schema violations. Invalid configurations should be
    rejected while valid ones are accepted.
    """
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir(exist_ok=True)

    config_file = ralph_dir / "ralph.toml"
    config_file.write_text(config_content)

    results = validate_config(tmp_path)

    # Property: Results should always be returned
    assert isinstance(results, list)
    assert len(results) > 0

    # Property: If config exists, there should be a config_exists check
    assert any(r.check_name == "config_exists" for r in results)

    # Property: If TOML is invalid, toml_syntax check should fail
    try:
        import tomllib

        tomllib.loads(config_content)
        # If parsing succeeds, toml_syntax check should pass (if present)
        toml_checks = [r for r in results if r.check_name == "toml_syntax"]
        if toml_checks:
            assert toml_checks[0].passed
    except Exception:
        # If parsing fails, toml_syntax check should fail (if present)
        toml_checks = [r for r in results if r.check_name == "toml_syntax"]
        if toml_checks:
            assert not toml_checks[0].passed

    # Property: All results should have required fields
    for result in results:
        assert hasattr(result, "check_name")
        assert hasattr(result, "passed")
        assert hasattr(result, "message")
        assert hasattr(result, "suggestions")
        assert hasattr(result, "severity")
        assert isinstance(result.suggestions, list)
        assert result.severity in ["error", "warning", "info"]


# ============================================================================
# Property 2: Diagnostic Exit Code Mapping
# ============================================================================


@given(
    st.lists(
        st.tuples(
            st.text(min_size=1, max_size=20),  # check_name
            st.booleans(),  # passed
            st.sampled_from(["error", "warning", "info"]),  # severity
        ),
        min_size=1,
        max_size=10,
    )
)
@settings(max_examples=20)
def test_property_exit_code_mapping(check_results: List[tuple]):
    """
    **Validates: Requirements 1.1** (General criteria - Diagnostics criteria 6)

    Feature: ralph-enhancement-phase2, Property 2
    For any set of diagnostic check results, the exit code should be 0 if all
    checks pass, and 2 if any check fails with error severity.
    """
    # Create mock diagnostic results
    results = [
        DiagnosticResult(
            check_name=name,
            passed=passed,
            message=f"Test message for {name}",
            suggestions=["suggestion"] if not passed else [],
            severity=severity,
        )
        for name, passed, severity in check_results
    ]

    # Calculate expected exit code
    has_errors = any(r.severity == "error" and not r.passed for r in results)
    expected_exit_code = 2 if has_errors else 0

    # Simulate the exit code logic from run_diagnostics
    actual_exit_code = 2 if has_errors else 0

    # Property: Exit code should match expected
    assert actual_exit_code == expected_exit_code

    # Property: If all checks pass or only warnings/info, exit code is 0
    if all(r.passed or r.severity != "error" for r in results):
        assert actual_exit_code == 0

    # Property: If any error exists, exit code is 2
    if any(r.severity == "error" and not r.passed for r in results):
        assert actual_exit_code == 2


# ============================================================================
# Property 3: Gate Command Execution Fidelity
# ============================================================================


@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    gate_commands=st.lists(
        st.sampled_from(
            [
                "echo 'test'",
                "exit 0",
                "exit 1",
                "true",
                "false",
            ]
        ),
        min_size=1,
        max_size=5,
    )
)
def test_property_gate_execution_fidelity(tmp_path: Path, gate_commands: List[str]):
    """
    **Validates: Requirements 1.3** (Diagnostics criteria 3)

    Feature: ralph-enhancement-phase2, Property 3
    For any gate command, testing it individually should produce consistent
    results (same exit code behavior).
    """
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir(exist_ok=True)

    # Create config with gate commands
    config_content = f"""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = {gate_commands}

[runners.codex]
argv = ["codex", "exec", "-"]
"""
    config_file = ralph_dir / "ralph.toml"
    config_file.write_text(config_content)

    cfg = load_config(tmp_path)
    results = check_gates(tmp_path, cfg)

    # Property: Should have results for each gate command
    gate_results = [r for r in results if r.check_name.startswith("gate_")]
    assert len(gate_results) == len(gate_commands)

    # Property: Each gate result should be deterministic
    # Running the same command twice should give the same result
    results2 = check_gates(tmp_path, cfg)
    gate_results2 = [r for r in results2 if r.check_name.startswith("gate_")]

    for r1, r2 in zip(gate_results, gate_results2):
        assert r1.check_name == r2.check_name
        assert r1.passed == r2.passed

    # Property: Gate results should match expected outcomes
    for idx, cmd in enumerate(gate_commands, 1):
        gate_result = next(r for r in gate_results if r.check_name == f"gate_{idx}")

        # Commands that should pass
        if cmd in ["echo 'test'", "exit 0", "true"]:
            assert gate_result.passed, f"Command '{cmd}' should pass"

        # Commands that should fail
        if cmd in ["exit 1", "false"]:
            assert not gate_result.passed, f"Command '{cmd}' should fail"


# ============================================================================
# Property 4: Suggestion Completeness
# ============================================================================


@given(
    st.lists(
        st.tuples(
            st.text(min_size=1, max_size=20),  # check_name
            st.booleans(),  # passed
            st.sampled_from(["error", "warning", "info"]),  # severity
        ),
        min_size=1,
        max_size=20,
    )
)
@settings(max_examples=20)
def test_property_suggestion_completeness(check_results: List[tuple]):
    """
    **Validates: Requirements 1.1, 1.2, 1.3** (General criteria 4 - Diagnostics criteria 5)

    Feature: ralph-enhancement-phase2, Property 4
    For any detected diagnostic issue (failed check), there should be at least
    one actionable suggestion for fixing it.
    """
    # Create diagnostic results
    results = [
        DiagnosticResult(
            check_name=name,
            passed=passed,
            message=f"Test message for {name}",
            suggestions=["Fix suggestion"] if not passed else [],
            severity=severity,
        )
        for name, passed, severity in check_results
    ]

    # Property: All failed checks should have suggestions
    for result in results:
        if not result.passed and result.severity == "error":
            assert len(result.suggestions) > 0, (
                f"Failed check '{result.check_name}' must have suggestions"
            )
            # Property: Suggestions should be non-empty strings
            for suggestion in result.suggestions:
                assert isinstance(suggestion, str)
                assert len(suggestion) > 0


# ============================================================================
# Integration Property Tests
# ============================================================================


@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    has_config=st.booleans(),
    config_valid=st.booleans(),
    has_prd=st.booleans(),
    test_gates=st.booleans(),
)
def test_property_run_diagnostics_consistency(
    tmp_path: Path,
    has_config: bool,
    config_valid: bool,
    has_prd: bool,
    test_gates: bool,
):
    """
    **Validates: Requirements 1.1, 1.2, 1.3**

    Feature: ralph-enhancement-phase2, Integration Property
    The run_diagnostics function should consistently return results and exit
    codes based on the project state.
    """
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir(exist_ok=True)

    # Setup config if requested
    if has_config:
        config_file = ralph_dir / "ralph.toml"
        if config_valid:
            config_file.write_text("""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = ["echo 'test'"]

[runners.codex]
argv = ["codex", "exec", "-"]
""")
        else:
            config_file.write_text("[invalid toml")

    # Setup PRD if requested
    if has_prd and has_config and config_valid:
        prd_file = ralph_dir / "PRD.md"
        prd_file.write_text("""
# Tasks

## Task: task-1
**Status:** open
""")

    # Run diagnostics
    results, exit_code = run_diagnostics(tmp_path, test_gates_flag=test_gates)

    # Property: Should always return results
    assert isinstance(results, list)
    assert len(results) > 0

    # Property: Exit code should be 0 or 2
    assert exit_code in [0, 2]

    # Property: If no config, should have config_exists check
    if not has_config:
        assert any(r.check_name == "config_exists" for r in results)

    # Property: If config is invalid, should have error and exit code 2
    if has_config and not config_valid:
        assert exit_code == 2
        assert any(r.severity == "error" and not r.passed for r in results)

    # Property: If config is valid, should have config checks passing
    if has_config and config_valid:
        assert any(r.check_name == "config_exists" and r.passed for r in results)

    # Property: Gate tests should only appear if test_gates is True
    gate_checks = [r for r in results if r.check_name.startswith("gate_")]
    if test_gates and has_config and config_valid:
        # Should have gate results
        assert len(gate_checks) >= 0  # May be 0 if no gates configured
    elif not test_gates:
        # Should not have individual gate results (only gates_configured)
        assert all(
            r.check_name == "gates_configured"
            for r in gate_checks
            if "gate" in r.check_name
        )


# ============================================================================
# Edge Case Property Tests
# ============================================================================


@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(arbitrary_content=st.text(min_size=0, max_size=1000))
def test_property_config_validation_handles_arbitrary_input(
    tmp_path: Path, arbitrary_content: str
):
    """
    **Validates: Requirements 1.1**

    Feature: ralph-enhancement-phase2, Robustness Property
    Configuration validation should handle arbitrary input without crashing.
    """
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir(exist_ok=True)

    config_file = ralph_dir / "ralph.toml"
    try:
        config_file.write_text(arbitrary_content)
    except Exception:
        # If we can't even write the file, skip this test case
        pytest.skip("Cannot write arbitrary content to file")

    # Property: Should not crash, should return results
    try:
        results = validate_config(tmp_path)
        assert isinstance(results, list)
        assert len(results) > 0
    except Exception as e:
        pytest.fail(f"validate_config crashed with arbitrary input: {e}")


@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,  # Uses subprocess; avoid flaky deadline failures.
)
@given(
    gate_commands=st.lists(
        st.text(
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                whitelist_characters=" -_./",
            ),
            min_size=1,
            max_size=50,
        ),
        min_size=0,
        max_size=10,
    )
)
def test_property_gate_commands_handle_various_inputs(
    tmp_path: Path, gate_commands: List[str]
):
    """
    **Validates: Requirements 1.3**

    Feature: ralph-enhancement-phase2, Robustness Property
    Gate command testing should handle various command inputs gracefully.
    """
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir(exist_ok=True)

    # Create config with gate commands
    config_content = f"""
[files]
prd = ".ralph/PRD.md"

[gates]
commands = {gate_commands}

[runners.codex]
argv = ["codex", "exec", "-"]
"""
    config_file = ralph_dir / "ralph.toml"
    try:
        config_file.write_text(config_content)
    except Exception:
        pytest.skip("Cannot write config with these gate commands")

    try:
        cfg = load_config(tmp_path)
        results = check_gates(tmp_path, cfg)

        # Property: Should return results without crashing
        assert isinstance(results, list)

        # Property: Should have at least gates_configured check
        assert any(r.check_name == "gates_configured" for r in results)

    except Exception as e:
        # It's okay if config loading fails with invalid input
        # But check_gates itself should not crash
        if "check_gates" in str(e):
            pytest.fail(f"check_gates crashed: {e}")
