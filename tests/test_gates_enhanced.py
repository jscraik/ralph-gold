"""Tests for enhanced gate functionality (pre-commit hooks, fail-fast, output modes)."""

import subprocess
from pathlib import Path
from ralph_gold.config import GatesConfig, SmartGateConfig, LlmJudgeConfig
from ralph_gold.gates import get_changed_files
from ralph_gold.loop import (
    _discover_precommit_hook,
    _truncate_output,
    _format_gate_results,
    _should_skip_gates,
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


# ----------------------------------------------------------------------
# Smart Gate Filtering Tests
# ----------------------------------------------------------------------


def test_should_skip_gates_all_match():
    """Test that gates are skipped when all files match skip patterns."""
    project_root = Path("/project")
    changed_files = [project_root / "README.md", project_root / "docs/guide.md"]
    skip_patterns = ["**/*.md"]

    result = _should_skip_gates(changed_files, skip_patterns, project_root)
    assert result is True


def test_should_skip_gates_partial_match():
    """Test that gates run when some files don't match skip patterns."""
    project_root = Path("/project")
    changed_files = [project_root / "README.md", project_root / "src/main.py"]
    skip_patterns = ["**/*.md"]

    result = _should_skip_gates(changed_files, skip_patterns, project_root)
    assert result is False


def test_should_skip_gates_no_match():
    """Test that gates run when no files match skip patterns."""
    project_root = Path("/project")
    changed_files = [project_root / "src/main.py", project_root / "src/utils.py"]
    skip_patterns = ["**/*.md"]

    result = _should_skip_gates(changed_files, skip_patterns, project_root)
    assert result is False


def test_should_skip_gates_empty_patterns():
    """Test that gates run when no skip patterns are configured."""
    project_root = Path("/project")
    changed_files = [project_root / "README.md"]
    skip_patterns = []

    result = _should_skip_gates(changed_files, skip_patterns, project_root)
    assert result is False


def test_should_skip_gates_multiple_patterns():
    """Test that gates are skipped when files match any of multiple patterns."""
    project_root = Path("/project")
    changed_files = [
        project_root / "README.md",
        project_root / "pyproject.toml",
        project_root / "docs/guide.md",
    ]
    skip_patterns = ["**/*.md", "**/*.toml"]

    result = _should_skip_gates(changed_files, skip_patterns, project_root)
    assert result is True


def test_should_skip_gates_wildcard_pattern():
    """Test that wildcard patterns match files in subdirectories."""
    project_root = Path("/project")
    changed_files = [
        project_root / "docs/api/guide.md",
        project_root / "src/README.md",
    ]
    skip_patterns = ["**/*.md"]

    result = _should_skip_gates(changed_files, skip_patterns, project_root)
    assert result is True


def test_smart_gate_filters_with_git_repo(tmp_path: Path):
    """Test that smart gates are skipped when only markdown files change."""

    # Initialize a git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True, capture_output=True)

    # Create and commit a markdown file
    readme = tmp_path / "README.md"
    readme.write_text("# Test Project")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True, capture_output=True)

    # Create a pass gate script
    pass_script = tmp_path / "pass.sh"
    pass_script.write_text("#!/bin/sh\necho 'gate ran'\n")
    pass_script.chmod(0o755)

    # Create config with smart gates enabled
    cfg = GatesConfig(
        commands=[str(pass_script)],
        llm_judge=LlmJudgeConfig(),
        precommit_hook=False,
        fail_fast=True,
        output_mode="summary",
        max_output_lines=50,
        smart=SmartGateConfig(enabled=True, skip_gates_for=["**/*.md"]),
    )

    # Modify README.md (should skip gates)
    readme.write_text("# Test Project - Updated")

    ok, results = run_gates(tmp_path, [str(pass_script)], cfg)

    # Gates should be skipped (True, empty results)
    assert ok is True
    assert len(results) == 0


def test_smart_gate_runs_for_code_changes(tmp_path: Path):
    """Test that gates run when code files change even with smart filtering enabled."""
    import subprocess
    from ralph_gold.config import SmartGateConfig

    # Initialize a git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True, capture_output=True)

    # Create and commit initial files
    readme = tmp_path / "README.md"
    readme.write_text("# Test Project")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True, capture_output=True)

    # Create a pass gate script
    pass_script = tmp_path / "pass.sh"
    pass_script.write_text("#!/bin/sh\necho 'gate ran'\n")
    pass_script.chmod(0o755)

    # Create config with smart gates enabled
    cfg = GatesConfig(
        commands=[str(pass_script)],
        llm_judge=LlmJudgeConfig(),
        precommit_hook=False,
        fail_fast=True,
        output_mode="summary",
        max_output_lines=50,
        smart=SmartGateConfig(enabled=True, skip_gates_for=["**/*.md"]),
    )

    # Create a Python file (should run gates)
    main_py = tmp_path / "main.py"
    main_py.write_text("print('hello')")

    ok, results = run_gates(tmp_path, [str(pass_script)], cfg)

    # Gates should run (gate should pass)
    assert ok is True
    assert len(results) == 1
    assert results[0].return_code == 0


def test_smart_gate_disabled_by_default(tmp_path: Path):
    """Test that smart filtering is opt-in (disabled by default)."""
    import subprocess

    # Initialize a git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True, capture_output=True)

    # Create and commit initial files
    readme = tmp_path / "README.md"
    readme.write_text("# Test Project")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True, capture_output=True)

    # Create a pass gate script
    pass_script = tmp_path / "pass.sh"
    pass_script.write_text("#!/bin/sh\necho 'gate ran'\n")
    pass_script.chmod(0o755)

    # Create config with smart gates DISABLED (default)
    cfg = GatesConfig(
        commands=[str(pass_script)],
        llm_judge=LlmJudgeConfig(),
        precommit_hook=False,
        fail_fast=True,
        output_mode="summary",
        max_output_lines=50,
        smart=SmartGateConfig(enabled=False, skip_gates_for=["**/*.md"]),
    )

    # Modify README.md (should NOT skip gates when disabled)
    readme.write_text("# Test Project - Updated")

    ok, results = run_gates(tmp_path, [str(pass_script)], cfg)

    # Gates should run (smart filtering disabled)
    assert ok is True
    assert len(results) == 1
    assert results[0].return_code == 0


# ----------------------------------------------------------------------
# Adaptive Rigor Tests
# ----------------------------------------------------------------------


def test_calculate_max_risk():
    """Test max risk calculation from changed files."""
    from ralph_gold.loop import _calculate_max_risk
    from pathlib import Path

    project_root = Path("/project")
    changed_files = [
        project_root / "src/core.py",
        project_root / "src/auth.py",
    ]
    area_risk_scores = {
        "src/core.py": 0.2,
        "src/auth.py": 0.9,
    }

    risk = _calculate_max_risk(project_root, changed_files, area_risk_scores)
    assert risk == 0.9


def test_calculate_max_risk_prefix_match():
    """Test max risk calculation with directory prefix matching."""
    from ralph_gold.loop import _calculate_max_risk
    from pathlib import Path

    project_root = Path("/project")
    changed_files = [
        project_root / "src/auth/login.py",
    ]
    area_risk_scores = {
        "src/auth": 0.8,
        "src/core": 0.1,
    }

    risk = _calculate_max_risk(project_root, changed_files, area_risk_scores)
    assert risk == 0.8


def test_adaptive_rigor_high_risk(tmp_path: Path):
    """Test that gates are tightened (fail_fast disabled) for high risk."""
    from ralph_gold.loop import run_gates
    from ralph_gold.config import GatesConfig, LlmJudgeConfig, AdaptiveConfig
    from unittest.mock import patch

    pass_script = tmp_path / "pass.sh"
    pass_script.write_text("#!/bin/sh\nexit 0\n")
    pass_script.chmod(0o755)

    fail_script = tmp_path / "fail.sh"
    fail_script.write_text("#!/bin/sh\nexit 1\n")
    fail_script.chmod(0o755)

    # Config with fail_fast=True
    cfg = GatesConfig(
        commands=[str(fail_script), str(pass_script)],
        llm_judge=LlmJudgeConfig(enabled=False),
        fail_fast=True,
    )

    # Mock high risk (0.9 > high_risk_threshold=0.8)
    area_risk_scores = {"src/high_risk.py": 0.9}
    
    with patch("ralph_gold.loop._get_changed_files") as mock_get_files:
        mock_get_files.return_value = [tmp_path / "src/high_risk.py"]
        
        # We need to pass adaptive config somehow. 
        # run_gates signature might need to change or we use a wrapper.
        # Acceptance criteria: Mixed changes follow strictest path.
        
        adaptive_cfg = AdaptiveConfig(enabled=True, high_risk_threshold=0.8)
        
        ok, results = run_gates(
            tmp_path, 
            cfg.commands, 
            cfg, 
            adaptive=adaptive_cfg, 
            area_risk_scores=area_risk_scores
        )
        
        assert ok is False
        # Tightened rigor should have disabled fail_fast, so both gates ran
        assert len(results) == 2


def test_adaptive_rigor_low_risk(tmp_path: Path):
    """Test that standard gates (fail_fast enabled) are used for low risk."""
    from ralph_gold.loop import run_gates
    from ralph_gold.config import GatesConfig, LlmJudgeConfig, AdaptiveConfig
    from unittest.mock import patch

    pass_script = tmp_path / "pass.sh"
    pass_script.write_text("#!/bin/sh\nexit 0\n")
    pass_script.chmod(0o755)

    fail_script = tmp_path / "fail.sh"
    fail_script.write_text("#!/bin/sh\nexit 1\n")
    fail_script.chmod(0o755)

    # Config with fail_fast=True
    cfg = GatesConfig(
        commands=[str(fail_script), str(pass_script)],
        llm_judge=LlmJudgeConfig(enabled=False),
        fail_fast=True,
    )

    # Mock low risk (0.1 < medium_risk_threshold=0.4)
    area_risk_scores = {"src/low_risk.py": 0.1}
    
    with patch("ralph_gold.loop._get_changed_files") as mock_get_files:
        mock_get_files.return_value = [tmp_path / "src/low_risk.py"]
        
        adaptive_cfg = AdaptiveConfig(enabled=True, medium_risk_threshold=0.4)
        
        ok, results = run_gates(
            tmp_path, 
            cfg.commands, 
            cfg, 
            adaptive=adaptive_cfg, 
            area_risk_scores=area_risk_scores
        )
        
        assert ok is False
        # Low rigor should respect fail_fast=True, so only 1 gate ran
        assert len(results) == 1


def test_adaptive_integration_high_risk_forces_judge(tmp_path: Path):
    """Test that high-risk areas force enable llm_judge in run_iteration."""
    from unittest.mock import patch, MagicMock
    from ralph_gold.loop import run_iteration
    from ralph_gold.config import (
        Config,
        LoopConfig,
        FilesConfig,
        GatesConfig,
        LlmJudgeConfig,
        GitConfig,
        TrackerConfig,
        ParallelConfig,
        AdaptiveTimeoutConfig,
        AdaptiveConfig,
        AuthorizationConfig,
    )
    from ralph_gold.prd import SelectedTask

    project_root = tmp_path
    (project_root / ".ralph").mkdir()
    (project_root / "PRD.md").write_text("# PRD\n- [ ] Task 1")

    cfg = Config(
        loop=LoopConfig(
            adaptive=AdaptiveConfig(enabled=True, high_risk_threshold=0.8)
        ),
        files=FilesConfig(prd="PRD.md"),
        runners={"claude": MagicMock()},
        gates=GatesConfig(
            commands=["echo 'gate'"],
            # llm_judge is DISABLED in config
            llm_judge=LlmJudgeConfig(enabled=False, agent="claude"),
        ),
        git=GitConfig(),
        tracker=TrackerConfig(kind="markdown"),
        parallel=ParallelConfig(),
        adaptive_timeout=AdaptiveTimeoutConfig(enabled=False),
        authorization=AuthorizationConfig(enabled=False),
    )

    task = SelectedTask(id="1", title="Task 1", kind="md", acceptance=[])

    # Mock risk score: 0.9 (HIGH RISK)
    area_risk_scores = {"src/critical.py": 0.9}

    with patch("ralph_gold.loop._get_changed_files") as mock_get_files, \
         patch("ralph_gold.loop.run_gates") as mock_run_gates, \
         patch("ralph_gold.loop.run_subprocess") as mock_run_sub, \
         patch("ralph_gold.loop.make_tracker") as mock_make_tracker, \
         patch("ralph_gold.loop._get_runner") as mock_get_runner, \
         patch("ralph_gold.loop.build_prompt", return_value="prompt"), \
         patch("ralph_gold.loop.build_runner_invocation", return_value=(["echo"], None)), \
         patch("ralph_gold.loop.ensure_git_repo"), \
         patch("ralph_gold.loop.git_head", return_value="abc"), \
         patch("ralph_gold.loop.load_state") as mock_load_state, \
         patch("ralph_gold.loop.build_judge_prompt", return_value="judge prompt"), \
         patch("ralph_gold.loop.parse_judge_signal", return_value=True):

        # Setup state mock with risk scores
        mock_load_state.return_value = {
            "history": [],
            "area_risk_scores": area_risk_scores
        }

        # Setup tracker mock
        tracker = MagicMock()
        tracker.claim_next_task.return_value = task
        tracker.counts.return_value = (0, 1)
        tracker.branch_name.return_value = None
        tracker.is_task_done.return_value = True # Judge only runs if task is done
        mock_make_tracker.return_value = tracker

        mock_get_files.return_value = [project_root / "src/critical.py"]
        mock_run_gates.return_value = (True, [])
        mock_run_sub.return_value = MagicMock(
            success=True, returncode=0, stdout="JUDGE_SIGNAL: true", stderr=""
        )
        mock_get_runner.return_value = MagicMock(argv=["echo"])

        result = run_iteration(project_root, "claude", cfg=cfg, iteration=1)

        # Judge SHOULD have run even though it was disabled in cfg
        assert result.judge_ok is True
        # Verify build_judge_prompt was called
        from ralph_gold.loop import build_judge_prompt
        assert build_judge_prompt.called


def test_changed_files(tmp_path: Path):
    """Test get_changed_files function."""
    import subprocess

    # 1. Not a git repo
    not_git = tmp_path / "not_git"
    not_git.mkdir()
    assert get_changed_files(not_git) == []

    # 2. Empty git repo (no HEAD)
    git_repo = tmp_path / "git_repo"
    git_repo.mkdir()
    subprocess.run(["git", "init"], cwd=git_repo, check=True, capture_output=True)
    assert get_changed_files(git_repo) == []

    # 3. Git repo with commits and changes
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=git_repo, check=True, capture_output=True)
    
    readme = git_repo / "README.md"
    readme.write_text("# Initial")
    subprocess.run(["git", "add", "README.md"], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=git_repo, check=True, capture_output=True)
    
    # Modify existing file (unstaged)
    readme.write_text("# Updated")
    # Create new file (untracked)
    new_file = git_repo / "new.py"
    new_file.write_text("print('new')")
    
    changed = get_changed_files(git_repo)
    # git diff --name-only HEAD shows changes since last commit (unstaged + staged)
    # Untracked files are NOT shown.
    assert readme in [p.resolve() for p in changed]
    assert new_file not in [p.resolve() for p in changed]
    assert len(changed) == 1

    # Add new file (staged)
    subprocess.run(["git", "add", "new.py"], cwd=git_repo, check=True, capture_output=True)
    changed = get_changed_files(git_repo)
    # Use resolve() to handle Path comparison safely
    assert readme.resolve() in [p.resolve() for p in changed]
    assert new_file.resolve() in [p.resolve() for p in changed]
    assert len(changed) == 2


def test_integration(tmp_path: Path):
    """Test integration of smart gates into run_iteration."""
    from unittest.mock import patch, MagicMock
    from ralph_gold.loop import run_iteration
    from ralph_gold.config import (
        Config,
        LoopConfig,
        FilesConfig,
        GatesConfig,
        SmartGateConfig,
        GitConfig,
        TrackerConfig,
        ParallelConfig,
        AdaptiveTimeoutConfig,
        AuthorizationConfig,
    )
    from ralph_gold.prd import SelectedTask

    project_root = tmp_path
    (project_root / ".ralph").mkdir()
    (project_root / "PRD.md").write_text("# PRD\n- [ ] Task 1")

    cfg = Config(
        loop=LoopConfig(),
        files=FilesConfig(prd="PRD.md"),
        runners={"claude": MagicMock()},
        gates=GatesConfig(
            commands=["echo 'gate'"],
            llm_judge=MagicMock(),
            smart=SmartGateConfig(enabled=True, skip_gates_for=["**/*.md"]),
        ),
        git=GitConfig(),
        tracker=TrackerConfig(kind="markdown"),
        parallel=ParallelConfig(),
        adaptive_timeout=AdaptiveTimeoutConfig(enabled=False),
        authorization=AuthorizationConfig(enabled=False),
    )

    task = SelectedTask(id="1", title="Task 1", kind="md", acceptance=[])

    # Mock all external dependencies of run_iteration
    with patch("ralph_gold.loop._get_changed_files") as mock_get_files, \
        patch("ralph_gold.loop.run_gates") as mock_run_gates, \
        patch("ralph_gold.loop.run_subprocess") as mock_run_sub, \
        patch("ralph_gold.loop.make_tracker") as mock_make_tracker, \
        patch("ralph_gold.loop._get_runner") as mock_get_runner, \
        patch("ralph_gold.loop.build_prompt", return_value="prompt"), \
        patch(
            "ralph_gold.loop.build_runner_invocation", return_value=(["echo"], None)
        ), \
        patch("ralph_gold.loop.ensure_git_repo"), \
        patch("ralph_gold.loop.git_head", return_value="abc"):

        # Setup tracker mock
        tracker = MagicMock()
        tracker.claim_next_task.return_value = task
        tracker.counts.return_value = (0, 1)
        tracker.branch_name.return_value = None
        tracker.kind = "markdown"
        mock_make_tracker.return_value = tracker

        mock_run_sub.return_value = MagicMock(
            success=True, returncode=0, stdout="DONE", stderr=""
        )
        mock_get_runner.return_value = MagicMock(argv=["echo"])

        # 1. Test skip: only README.md changed
        mock_get_files.return_value = [project_root / "README.md"]

        result = run_iteration(project_root, "claude", cfg=cfg, iteration=1)

        # Should NOT have called run_gates
        assert mock_run_gates.call_count == 0
        assert result.gates_ok is True

        # Check if receipt was written
        receipt_dir = project_root / ".ralph" / "receipts" / "1" / f"{result.attempt_id}"
        receipt_path = receipt_dir / "smart_gates_skip.json"
        assert receipt_path.exists()
        
        import json
        receipt_data = json.loads(receipt_path.read_text())
        assert receipt_data["task_id"] == "1"
        assert "All changed files" in receipt_data["reason"]
        assert "README.md" in receipt_data["changed_files"][0]
        assert "**/*.md" in receipt_data["patterns"]

        # 2. Test run: Python file changed
        mock_get_files.return_value = [project_root / "main.py"]
        mock_run_gates.return_value = (True, [])
        mock_run_gates.reset_mock()

        result = run_iteration(project_root, "claude", cfg=cfg, iteration=2)

        # Should HAVE called run_gates
        assert mock_run_gates.call_count == 1
        assert result.gates_ok is True
