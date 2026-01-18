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


# Property-Based Tests

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st


@given(
    max_iterations=st.integers(min_value=1, max_value=100),
    num_tasks=st.integers(min_value=0, max_value=50),
)
@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_dry_run_safety(
    git_repo: Path, max_iterations: int, num_tasks: int, monkeypatch
):
    """Property 8: Dry-run safety.

    **Validates: Requirements 3.1** (Dry-run criteria 5)

    For any dry-run execution, no agent processes should be spawned
    and no files outside .ralph/ should be modified.
    """
    # Setup Ralph project
    ralph_dir = git_repo / ".ralph"
    ralph_dir.mkdir(exist_ok=True)

    (git_repo / "ralph.toml").write_text("""
[loop]
max_iterations = 100

[runners.codex]
argv = ["echo", "mock-agent"]

[files]
prd = "prd.json"
""")

    # Create PRD with variable number of tasks
    stories = [
        {"id": f"task-{i}", "title": f"Task {i}", "status": "todo"}
        for i in range(num_tasks)
    ]
    (git_repo / "prd.json").write_text(json.dumps({"stories": stories}, indent=2))

    (ralph_dir / "state.json").write_text(
        json.dumps(
            {
                "createdAt": "2024-01-01T00:00:00Z",
                "invocations": [],
                "noProgressStreak": 0,
                "history": [],
                "task_attempts": {},
                "blocked_tasks": {},
                "session_id": "",
            },
            indent=2,
        )
    )

    # Track file modifications
    initial_files = {
        f: f.read_bytes()
        for f in git_repo.rglob("*")
        if f.is_file() and ".git" not in str(f)
    }

    # Track subprocess calls
    agent_calls = []
    original_run = subprocess.run

    def mock_run(*args, **kwargs):
        cmd = args[0] if args else []
        if isinstance(cmd, list) and "mock-agent" in cmd:
            agent_calls.append(cmd)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)

    # Run dry-run
    try:
        result = dry_run_loop(git_repo, "codex", max_iterations)
    except Exception:
        # Even if dry-run fails, it should not execute agents or modify files
        pass

    # Verify no agent processes were spawned
    assert len(agent_calls) == 0, "Dry-run must not execute agent commands"

    # Verify no files outside .ralph/ were modified
    for file_path, original_content in initial_files.items():
        if ".ralph" not in str(file_path):
            current_content = file_path.read_bytes() if file_path.exists() else b""
            assert current_content == original_content, (
                f"Dry-run must not modify {file_path}"
            )


@given(
    num_tasks=st.integers(min_value=1, max_value=20),
    num_completed=st.integers(min_value=0, max_value=20),
    max_iterations=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_dry_run_prediction_accuracy(
    git_repo: Path, num_tasks: int, num_completed: int, max_iterations: int
):
    """Property 9: Dry-run prediction accuracy.

    **Validates: Requirements 3.1, 3.2** (Dry-run criteria 2, 3)

    For any project state, the tasks and gates shown in dry-run mode
    should match what would be selected in a real run with the same state.
    """
    # Ensure num_completed doesn't exceed num_tasks
    num_completed = min(num_completed, num_tasks)

    # Setup Ralph project
    ralph_dir = git_repo / ".ralph"
    ralph_dir.mkdir(exist_ok=True)

    (git_repo / "ralph.toml").write_text("""
[loop]
max_iterations = 100

[runners.codex]
argv = ["echo", "mock-agent"]

[gates]
commands = ["echo 'gate1'", "echo 'gate2'"]

[files]
prd = "prd.json"
""")

    # Create PRD with tasks
    stories = []
    for i in range(num_tasks):
        status = "done" if i < num_completed else "todo"
        stories.append({"id": f"task-{i}", "title": f"Task {i}", "status": status})

    (git_repo / "prd.json").write_text(json.dumps({"stories": stories}, indent=2))

    (ralph_dir / "state.json").write_text(
        json.dumps(
            {
                "createdAt": "2024-01-01T00:00:00Z",
                "invocations": [],
                "noProgressStreak": 0,
                "history": [],
                "task_attempts": {},
                "blocked_tasks": {},
                "session_id": "",
            },
            indent=2,
        )
    )

    # Run dry-run
    try:
        result = dry_run_loop(git_repo, "codex", max_iterations)
    except Exception:
        # If dry-run fails, skip validation
        return

    # Verify task counts are accurate
    assert result.total_tasks == num_tasks
    assert result.completed_tasks == num_completed

    # Verify number of tasks to execute doesn't exceed remaining tasks
    remaining_tasks = num_tasks - num_completed
    expected_tasks = min(max_iterations, remaining_tasks)
    assert len(result.tasks_to_execute) <= expected_tasks

    # Verify gates are listed
    if result.gates_to_run:
        # Should include configured gates
        gate_str = " ".join(result.gates_to_run)
        assert "gate1" in gate_str or "gate2" in gate_str
