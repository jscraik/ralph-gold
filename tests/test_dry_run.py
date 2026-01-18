"""Tests for dry-run functionality."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ralph_gold.loop import dry_run_loop


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repository for testing."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    (tmp_path / "README.md").write_text("# Test Project\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    return tmp_path


@pytest.fixture
def ralph_project(git_repo: Path) -> Path:
    """Create a minimal Ralph project structure."""
    ralph_dir = git_repo / ".ralph"
    ralph_dir.mkdir()

    # Create minimal ralph.toml
    (git_repo / "ralph.toml").write_text("""
[loop]
max_iterations = 5

[runners.codex]
argv = ["echo", "mock-agent"]

[gates]
commands = ["echo 'test gate'"]

[files]
prd = "prd.json"
""")

    # Create minimal PRD
    prd = {
        "stories": [
            {"id": "task-1", "title": "First task", "status": "todo"},
            {"id": "task-2", "title": "Second task", "status": "todo"},
            {"id": "task-3", "title": "Third task", "status": "done"},
        ]
    }
    (git_repo / "prd.json").write_text(json.dumps(prd, indent=2))

    # Create minimal state.json
    state = {
        "createdAt": "2024-01-01T00:00:00Z",
        "invocations": [],
        "noProgressStreak": 0,
        "history": [
            {
                "iteration": 1,
                "duration_seconds": 45.5,
                "success": True,
            },
            {
                "iteration": 2,
                "duration_seconds": 52.3,
                "success": True,
            },
        ],
        "task_attempts": {},
        "blocked_tasks": {},
        "session_id": "",
    }
    (ralph_dir / "state.json").write_text(json.dumps(state, indent=2))

    return git_repo


def test_dry_run_does_not_execute_agents(ralph_project: Path, monkeypatch):
    """Test that dry-run mode doesn't execute agents.

    **Validates: Requirements 3.1** (Dry-run criteria 5)
    """
    # Track subprocess calls
    calls = []
    original_run = subprocess.run

    def mock_run(*args, **kwargs):
        calls.append(args[0] if args else [])
        # Still call original for git operations
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)

    # Run dry-run
    result = dry_run_loop(ralph_project, "codex", 5)

    # Verify no agent processes were spawned
    # The mock agent command is ["echo", "mock-agent"]
    agent_calls = [c for c in calls if isinstance(c, list) and "mock-agent" in c]
    assert len(agent_calls) == 0, "Dry-run should not execute agent commands"


def test_dry_run_does_not_modify_files(ralph_project: Path):
    """Test that dry-run mode doesn't modify files outside .ralph/.

    **Validates: Requirements 3.1** (Dry-run criteria 5)
    """
    # Get initial file states
    readme_content = (ralph_project / "README.md").read_text()
    prd_content = (ralph_project / "prd.json").read_text()

    # Run dry-run
    result = dry_run_loop(ralph_project, "codex", 5)

    # Verify files are unchanged
    assert (ralph_project / "README.md").read_text() == readme_content
    assert (ralph_project / "prd.json").read_text() == prd_content


def test_dry_run_validates_configuration(ralph_project: Path):
    """Test that dry-run validates configuration.

    **Validates: Requirements 3.2** (Dry-run criteria 1)
    """
    result = dry_run_loop(ralph_project, "codex", 5)

    # Should validate successfully
    assert result.config_valid is True
    assert len(result.issues) == 0


def test_dry_run_shows_tasks_to_execute(ralph_project: Path):
    """Test that dry-run shows which tasks would be selected.

    **Validates: Requirements 3.1** (Dry-run criteria 2)
    """
    result = dry_run_loop(ralph_project, "codex", 5)

    # Should show tasks that would be executed
    assert len(result.tasks_to_execute) > 0
    assert "task-1" in result.tasks_to_execute[0]


def test_dry_run_shows_gates_to_run(ralph_project: Path):
    """Test that dry-run lists gates that would run.

    **Validates: Requirements 3.1** (Dry-run criteria 3)
    """
    result = dry_run_loop(ralph_project, "codex", 5)

    # Should show gates
    assert len(result.gates_to_run) > 0
    assert any("test gate" in gate for gate in result.gates_to_run)


def test_dry_run_estimates_duration(ralph_project: Path):
    """Test that dry-run estimates duration based on history.

    **Validates: Requirements 3.3** (Dry-run criteria 4)
    """
    result = dry_run_loop(ralph_project, "codex", 5)

    # Should estimate duration based on historical data
    # History has 2 iterations: 45.5s and 52.3s (avg ~49s)
    assert result.estimated_duration_seconds > 0
    # Should be reasonable (not zero, not absurdly high)
    assert 10 < result.estimated_duration_seconds < 1000


def test_dry_run_reports_task_counts(ralph_project: Path):
    """Test that dry-run reports total and completed task counts."""
    result = dry_run_loop(ralph_project, "codex", 5)

    # Should report task counts
    assert result.total_tasks == 3
    assert result.completed_tasks == 1  # task-3 is done


def test_dry_run_with_invalid_agent(ralph_project: Path):
    """Test that dry-run detects invalid agent configuration."""
    result = dry_run_loop(ralph_project, "nonexistent-agent", 5)

    # Should report configuration error
    assert result.config_valid is False
    assert len(result.issues) > 0
    assert any("Agent configuration error" in issue for issue in result.issues)


def test_dry_run_with_missing_prd(git_repo: Path):
    """Test that dry-run detects missing PRD file."""
    # Create minimal ralph.toml without PRD
    (git_repo / "ralph.toml").write_text("""
[loop]
max_iterations = 5

[runners.codex]
argv = ["echo", "mock-agent"]

[files]
prd = "prd.json"
""")

    ralph_dir = git_repo / ".ralph"
    ralph_dir.mkdir()

    result = dry_run_loop(git_repo, "codex", 5)

    # Should report missing PRD
    assert result.config_valid is False
    assert any("PRD file not found" in issue for issue in result.issues)


def test_dry_run_respects_max_iterations(ralph_project: Path):
    """Test that dry-run respects max_iterations parameter."""
    # Request only 2 iterations
    result = dry_run_loop(ralph_project, "codex", 2)

    # Should only show up to 2 tasks
    assert len(result.tasks_to_execute) <= 2


def test_dry_run_with_no_history(ralph_project: Path):
    """Test that dry-run handles projects with no iteration history."""
    # Clear history
    state_path = ralph_project / ".ralph" / "state.json"
    state = json.loads(state_path.read_text())
    state["history"] = []
    state_path.write_text(json.dumps(state, indent=2))

    result = dry_run_loop(ralph_project, "codex", 5)

    # Should still work and provide a rough estimate
    assert result.estimated_duration_seconds > 0
    # Without history, should use default estimate (60s per task)
    assert result.estimated_duration_seconds >= 60
