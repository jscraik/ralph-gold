"""Tests for loop exit conditions when no tasks are available."""

from pathlib import Path

from ralph_gold.loop import run_iteration


def test_loop_exits_when_all_tasks_done(tmp_path: Path):
    """Test that loop exits with code 0 when all tasks are completed."""
    # Create a minimal ralph setup
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create PRD with all tasks done
    prd_content = """# PRD

## Tasks

- [x] Task 1
- [x] Task 2
"""
    (ralph_dir / "PRD.md").write_text(prd_content)

    # Create minimal config
    config_content = """[loop]
max_iterations = 1

[files]
prd = ".ralph/PRD.md"
progress = ".ralph/progress.md"
agents = ".ralph/AGENTS.md"
prompt = ".ralph/PROMPT_build.md"

[tracker]
kind = "markdown"

[git]
branch_strategy = "none"
auto_commit = false

[runners.test]
argv = ["echo", "test"]
"""
    (ralph_dir / "ralph.toml").write_text(config_content)

    # Create other required files
    (ralph_dir / "progress.md").write_text("# Progress\n")
    (ralph_dir / "AGENTS.md").write_text("# Agents\n")
    (ralph_dir / "PROMPT_build.md").write_text("# Prompt\n")

    # Initialize git repo
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True
    )

    # Run iteration
    result = run_iteration(tmp_path, agent="test", iteration=1)

    # Should exit with success when all tasks done
    assert result.return_code == 0
    assert result.story_id is None
    assert result.exit_signal is True


def test_loop_exits_when_all_tasks_blocked(tmp_path: Path):
    """Test that loop exits with code 1 when all remaining tasks are blocked."""
    # Create a minimal ralph setup
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create PRD with all tasks blocked
    prd_content = """# PRD

## Tasks

- [-] Task 1
- [-] Task 2
"""
    (ralph_dir / "PRD.md").write_text(prd_content)

    # Create minimal config
    config_content = """[loop]
max_iterations = 1
skip_blocked_tasks = true

[files]
prd = ".ralph/PRD.md"
progress = ".ralph/progress.md"
agents = ".ralph/AGENTS.md"
prompt = ".ralph/PROMPT_build.md"

[tracker]
kind = "markdown"

[git]
branch_strategy = "none"
auto_commit = false

[runners.test]
argv = ["echo", "test"]
"""
    (ralph_dir / "ralph.toml").write_text(config_content)

    # Create other required files
    (ralph_dir / "progress.md").write_text("# Progress\n")
    (ralph_dir / "AGENTS.md").write_text("# Agents\n")
    (ralph_dir / "PROMPT_build.md").write_text("# Prompt\n")

    # Create state with blocked tasks
    import json

    state = {
        "blocked_tasks": {
            "1": {"reason": "test", "attempts": 3},
            "2": {"reason": "test", "attempts": 3},
        }
    }
    (ralph_dir / "state.json").write_text(json.dumps(state))

    # Initialize git repo
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True
    )

    # Run iteration
    result = run_iteration(tmp_path, agent="test", iteration=1)

    # Should exit with failure when all tasks blocked
    assert result.return_code == 1
    assert result.story_id is None
    assert result.exit_signal is True


def test_no_story_id_none_iterations(tmp_path: Path):
    """Test that loop never runs iterations with story_id=None."""
    # Create a minimal ralph setup
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create PRD with all tasks blocked
    prd_content = """# PRD

## Tasks

- [-] Task 1
"""
    (ralph_dir / "PRD.md").write_text(prd_content)

    # Create minimal config
    config_content = """[loop]
max_iterations = 5
skip_blocked_tasks = true

[files]
prd = ".ralph/PRD.md"
progress = ".ralph/progress.md"
agents = ".ralph/AGENTS.md"
prompt = ".ralph/PROMPT_build.md"

[tracker]
kind = "markdown"

[git]
branch_strategy = "none"
auto_commit = false

[runners.test]
argv = ["echo", "test"]
"""
    (ralph_dir / "ralph.toml").write_text(config_content)

    # Create other required files
    (ralph_dir / "progress.md").write_text("# Progress\n")
    (ralph_dir / "AGENTS.md").write_text("# Agents\n")
    (ralph_dir / "PROMPT_build.md").write_text("# Prompt\n")

    # Create state with blocked task
    import json

    state = {"blocked_tasks": {"1": {"reason": "test", "attempts": 3}}}
    (ralph_dir / "state.json").write_text(json.dumps(state))

    # Initialize git repo
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True
    )

    # Run multiple iterations
    from ralph_gold.loop import run_loop

    results = run_loop(tmp_path, agent="test", max_iterations=5)

    # Should only have 1 result (exit immediately)
    assert len(results) == 1
    assert results[0].story_id is None
    assert results[0].exit_signal is True
    assert results[0].return_code == 1  # Blocked
