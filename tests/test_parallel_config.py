"""Tests for parallel execution configuration."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from ralph_gold.config import load_config


def test_parallel_config_defaults():
    """Test that parallel config has safe defaults when not specified."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        # Create minimal config without parallel section
        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[loop]
max_iterations = 5
""")

        config = load_config(project_root)

        # Verify safe defaults
        assert config.parallel is not None
        assert config.parallel.enabled is False  # Disabled by default
        assert config.parallel.max_workers == 3
        assert config.parallel.worktree_root == ".ralph/worktrees"
        assert config.parallel.strategy == "queue"
        assert config.parallel.merge_policy == "manual"


def test_parallel_config_full():
    """Test full parallel configuration."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[parallel]
enabled = true
max_workers = 5
worktree_root = ".ralph/custom_worktrees"
strategy = "group"
merge_policy = "auto_merge"
""")

        config = load_config(project_root)

        # Verify all fields loaded correctly
        assert config.parallel.enabled is True
        assert config.parallel.max_workers == 5
        assert config.parallel.worktree_root == ".ralph/custom_worktrees"
        assert config.parallel.strategy == "group"
        assert config.parallel.merge_policy == "auto_merge"


def test_parallel_config_partial():
    """Test partial parallel configuration with defaults."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[parallel]
enabled = true
max_workers = 4
""")

        config = load_config(project_root)

        # Verify specified fields
        assert config.parallel.enabled is True
        assert config.parallel.max_workers == 4

        # Verify defaults for unspecified fields
        assert config.parallel.worktree_root == ".ralph/worktrees"
        assert config.parallel.strategy == "queue"
        assert config.parallel.merge_policy == "manual"


def test_parallel_config_invalid_strategy():
    """Test that invalid strategy raises clear error."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[parallel]
strategy = "invalid_strategy"
""")

        with pytest.raises(ValueError) as exc_info:
            load_config(project_root)

        assert "Invalid parallel.strategy" in str(exc_info.value)
        assert "invalid_strategy" in str(exc_info.value)
        assert "queue" in str(exc_info.value)
        assert "group" in str(exc_info.value)


def test_parallel_config_invalid_merge_policy():
    """Test that invalid merge_policy raises clear error."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[parallel]
merge_policy = "invalid_policy"
""")

        with pytest.raises(ValueError) as exc_info:
            load_config(project_root)

        assert "Invalid parallel.merge_policy" in str(exc_info.value)
        assert "invalid_policy" in str(exc_info.value)
        assert "manual" in str(exc_info.value)
        assert "auto_merge" in str(exc_info.value)


def test_parallel_config_invalid_max_workers():
    """Test that invalid max_workers raises clear error."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[parallel]
max_workers = 0
""")

        with pytest.raises(ValueError) as exc_info:
            load_config(project_root)

        assert "Invalid parallel.max_workers" in str(exc_info.value)
        assert "Must be >= 1" in str(exc_info.value)


def test_parallel_config_negative_max_workers():
    """Test that negative max_workers raises clear error."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[parallel]
max_workers = -5
""")

        with pytest.raises(ValueError) as exc_info:
            load_config(project_root)

        assert "Invalid parallel.max_workers" in str(exc_info.value)


def test_parallel_config_case_insensitive():
    """Test that strategy and merge_policy are case-insensitive."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[parallel]
strategy = "QUEUE"
merge_policy = "AUTO_MERGE"
""")

        config = load_config(project_root)

        # Should normalize to lowercase
        assert config.parallel.strategy == "queue"
        assert config.parallel.merge_policy == "auto_merge"


def test_parallel_config_with_other_sections():
    """Test parallel config works alongside other config sections."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[loop]
max_iterations = 10

[parallel]
enabled = true
max_workers = 4

[tracker]
kind = "yaml"

[gates]
commands = ["pytest", "mypy"]
""")

        config = load_config(project_root)

        # Verify all sections loaded correctly
        assert config.loop.max_iterations == 10
        assert config.parallel.enabled is True
        assert config.parallel.max_workers == 4
        assert config.tracker.kind == "yaml"
        assert config.gates.commands == ["pytest", "mypy"]


def test_parallel_config_boolean_coercion():
    """Test that enabled field handles various boolean representations."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        # Test with string "true"
        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[parallel]
enabled = "true"
""")

        config = load_config(project_root)
        assert config.parallel.enabled is True

        # Test with integer 1
        config_file.write_text("""
[parallel]
enabled = 1
""")

        config = load_config(project_root)
        assert config.parallel.enabled is True

        # Test with integer 0
        config_file.write_text("""
[parallel]
enabled = 0
""")

        config = load_config(project_root)
        assert config.parallel.enabled is False


def test_parallel_config_backward_compatibility():
    """Test that old configs without parallel section still work."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        # Old config without parallel section
        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[loop]
max_iterations = 5

[tracker]
kind = "json"

[gates]
commands = ["pytest"]
""")

        # Should load without errors
        config = load_config(project_root)

        # Verify old sections still work
        assert config.loop.max_iterations == 5
        assert config.tracker.kind == "json"
        assert config.gates.commands == ["pytest"]

        # Verify parallel has safe defaults
        assert config.parallel.enabled is False
        assert config.parallel.max_workers == 3
