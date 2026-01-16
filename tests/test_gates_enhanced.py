"""Tests for enhanced gate functionality (pre-commit hooks, fail-fast, output modes)."""

from pathlib import Path
from ralph_gold.config import GatesConfig, LlmJudgeConfig
from ralph_gold.loop import (
    _discover_precommit_hook,
    _truncate_output,
    _format_gate_results,
    GateResult,
    run_gates,
)


def test_discover_precommit_hook_husky(tmp_path: Path):
    """Test that Husky pre-commit hooks are discovered."""
    husky_dir = tmp_path / ".husky"
    husky_dir.mkdir()
    hook = husky_dir / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'husky hook'\n")
    
    result = _discover_precommit_hook(tmp_path)
    assert result == hook


def test_discover_precommit_hook_git(tmp_path: Path):
    """Test that git hooks are discovered as fallback."""
    git_dir = tmp_path / ".git" / "hooks"
    git_dir.mkdir(parents=True)
    hook = git_dir / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'git hook'\n")
    
    result = _discover_precommit_hook(tmp_path)
    assert result == hook


def test_discover_precommit_hook_prefers_husky(tmp_path: Path):
    """Test that Husky is preferred over git hooks."""
    # Create both
    husky_dir = tmp_path / ".husky"
    husky_dir.mkdir()
    husky_hook = husky_dir / "pre-commit"
    husky_hook.write_text("#!/bin/sh\necho 'husky'\n")
    
    git_dir = tmp_path / ".git" / "hooks"
    git_dir.mkdir(parents=True)
    git_hook = git_dir / "pre-commit"
    git_hook.write_text("#!/bin/sh\necho 'git'\n")
    
    result = _discover_precommit_hook(tmp_path)
    assert result == husky_hook


def test_discover_precommit_hook_none(tmp_path: Path):
    """Test that None is returned when no hooks exist."""
    result = _discover_precommit_hook(tmp_path)
    assert result is None


def test_truncate_output_short():
    """Test that short output is not truncated."""
    text = "line1\nline2\nline3"
    result = _truncate_output(text, max_lines=10)
    assert result == text


def test_truncate_output_long():
    """Test that long output is truncated with context."""
    lines = [f"line{i}" for i in range(100)]
    text = "\n".join(lines)
    
    result = _truncate_output(text, max_lines=20)
    result_lines = result.splitlines()
    
    # Should have ~20 lines plus truncation marker
    assert len(result_lines) <= 22
    assert "truncated" in result.lower()
    
    # Should preserve first and last lines
    assert "line0" in result
    assert "line99" in result


def test_truncate_output_disabled():
    """Test that max_lines=0 disables truncation."""
    text = "\n".join([f"line{i}" for i in range(100)])
    result = _truncate_output(text, max_lines=0)
    assert result == text


def test_format_gate_results_summary():
    """Test summary output mode."""
    results = [
        GateResult(
            cmd="npm test",
            return_code=0,
            duration_seconds=1.5,
            stdout="All tests passed\n" + "\n".join([f"test{i}" for i in range(100)]),
            stderr="",
            is_precommit_hook=False,
        ),
    ]
    
    output = _format_gate_results(True, results, output_mode="summary", max_lines=10)
    
    assert "gates_overall: PASS" in output
    assert "npm test" in output
    assert "gate_1_return_code: 0" in output
    assert "truncated" in output.lower()


def test_format_gate_results_errors_only():
    """Test errors_only output mode."""
    results = [
        GateResult(
            cmd="npm test",
            return_code=0,
            duration_seconds=1.5,
            stdout="All tests passed",
            stderr="",
            is_precommit_hook=False,
        ),
        GateResult(
            cmd="npm run lint",
            return_code=1,
            duration_seconds=0.5,
            stdout="",
            stderr="Linting failed: 3 errors",
            is_precommit_hook=False,
        ),
    ]
    
    output = _format_gate_results(False, results, output_mode="errors_only", max_lines=50)
    
    assert "gates_overall: FAIL" in output
    # Passing gate should not show output
    assert "All tests passed" not in output
    # Failing gate should show output
    assert "Linting failed" in output


def test_format_gate_results_full():
    """Test full output mode."""
    results = [
        GateResult(
            cmd="echo test",
            return_code=0,
            duration_seconds=0.1,
            stdout="test output",
            stderr="",
            is_precommit_hook=False,
        ),
    ]
    
    output = _format_gate_results(True, results, output_mode="full", max_lines=10)
    
    assert "gates_overall: PASS" in output
    assert "test output" in output
    # Full mode should not truncate
    assert "truncated" not in output.lower()


def test_format_gate_results_precommit_hook_label():
    """Test that pre-commit hooks are labeled."""
    results = [
        GateResult(
            cmd=".husky/pre-commit",
            return_code=0,
            duration_seconds=0.5,
            stdout="hook passed",
            stderr="",
            is_precommit_hook=True,
        ),
    ]
    
    output = _format_gate_results(True, results, output_mode="summary", max_lines=50)
    
    assert "[pre-commit-hook]" in output


def test_run_gates_fail_fast(tmp_path: Path):
    """Test that fail_fast stops on first failure."""
    # Create a simple script that always fails
    fail_script = tmp_path / "fail.sh"
    fail_script.write_text("#!/bin/sh\nexit 1\n")
    fail_script.chmod(0o755)
    
    pass_script = tmp_path / "pass.sh"
    pass_script.write_text("#!/bin/sh\necho 'should not run'\n")
    pass_script.chmod(0o755)
    
    cfg = GatesConfig(
        commands=[],
        llm_judge=LlmJudgeConfig(),
        precommit_hook=False,
        fail_fast=True,
        output_mode="summary",
        max_output_lines=50,
    )
    
    ok, results = run_gates(tmp_path, [str(fail_script), str(pass_script)], cfg)
    
    assert not ok
    # Should only have 1 result (stopped after first failure)
    assert len(results) == 1
    assert results[0].return_code != 0


def test_run_gates_no_fail_fast(tmp_path: Path):
    """Test that all gates run when fail_fast is disabled."""
    fail_script = tmp_path / "fail.sh"
    fail_script.write_text("#!/bin/sh\nexit 1\n")
    fail_script.chmod(0o755)
    
    pass_script = tmp_path / "pass.sh"
    pass_script.write_text("#!/bin/sh\necho 'ran'\n")
    pass_script.chmod(0o755)
    
    cfg = GatesConfig(
        commands=[],
        llm_judge=LlmJudgeConfig(),
        precommit_hook=False,
        fail_fast=False,
        output_mode="summary",
        max_output_lines=50,
    )
    
    ok, results = run_gates(tmp_path, [str(fail_script), str(pass_script)], cfg)
    
    assert not ok
    # Should have 2 results (ran both)
    assert len(results) == 2
    assert results[0].return_code != 0
    assert results[1].return_code == 0
