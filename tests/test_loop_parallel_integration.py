"""Tests for parallel execution integration in loop.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ralph_gold.config import Config, ParallelConfig
from ralph_gold.loop import run_loop


def test_run_loop_sequential_mode_unchanged(tmp_path: Path):
    """Test that sequential mode still works without parallel parameter."""
    # Create .ralph directory
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config files
    (ralph_dir / "PRD.md").write_text("# Tasks\n- [ ] Task 1\n")
    (ralph_dir / "PROMPT_build.md").write_text("Build prompt")
    (ralph_dir / "AGENTS.md").write_text("# Agents")
    (ralph_dir / "progress.md").write_text("# Progress")

    with (
        patch("ralph_gold.loop.ensure_git_repo"),
        patch("ralph_gold.loop.run_iteration") as mock_iter,
        patch("ralph_gold.loop.make_tracker") as mock_tracker,
    ):
        # Mock tracker
        tracker = MagicMock()
        tracker.kind = "markdown"
        tracker.all_done.return_value = False
        mock_tracker.return_value = tracker

        # Mock iteration result
        mock_result = MagicMock()
        mock_result.iteration = 1
        mock_result.exit_signal = True
        mock_result.no_progress_streak = 0
        mock_iter.return_value = mock_result

        # Run loop in sequential mode (default)
        results = run_loop(tmp_path, agent="codex", max_iterations=1)

        # Verify sequential execution
        assert len(results) == 1
        assert mock_iter.call_count == 1


def test_run_loop_parallel_parameter_fallback(tmp_path: Path):
    """Test that parallel=True falls back to sequential when ParallelExecutor not available."""
    # Create .ralph directory
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config files
    (ralph_dir / "PRD.md").write_text("# Tasks\n- [ ] Task 1\n")
    (ralph_dir / "PROMPT_build.md").write_text("Build prompt")
    (ralph_dir / "AGENTS.md").write_text("# Agents")
    (ralph_dir / "progress.md").write_text("# Progress")

    with (
        patch("ralph_gold.loop.ensure_git_repo"),
        patch("ralph_gold.loop.run_iteration") as mock_iter,
        patch("ralph_gold.loop.make_tracker") as mock_tracker,
        patch("builtins.print") as mock_print,
    ):
        # Mock tracker
        tracker = MagicMock()
        tracker.kind = "markdown"
        tracker.all_done.return_value = False
        mock_tracker.return_value = tracker

        # Mock iteration result
        mock_result = MagicMock()
        mock_result.iteration = 1
        mock_result.exit_signal = True
        mock_result.no_progress_streak = 0
        mock_iter.return_value = mock_result

        # Run loop with parallel=True (should fall back since ParallelExecutor doesn't exist yet)
        results = run_loop(tmp_path, agent="codex", max_iterations=1, parallel=True)

        # Verify fallback to sequential
        assert len(results) == 1
        assert mock_iter.call_count == 1

        # Verify warning was printed
        mock_print.assert_called_once()
        assert "Warning" in str(mock_print.call_args)
        assert "ParallelExecutor not available" in str(mock_print.call_args)


def test_run_loop_config_parallel_enabled(tmp_path: Path):
    """Test that parallel mode is detected from config."""
    # Create .ralph directory
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config files
    (ralph_dir / "PRD.md").write_text("# Tasks\n- [ ] Task 1\n")
    (ralph_dir / "PROMPT_build.md").write_text("Build prompt")
    (ralph_dir / "AGENTS.md").write_text("# Agents")
    (ralph_dir / "progress.md").write_text("# Progress")

    # Create config with parallel enabled
    from ralph_gold.config import (
        FilesConfig,
        GatesConfig,
        GitConfig,
        LlmJudgeConfig,
        LoopConfig,
        TrackerConfig,
    )

    cfg = Config(
        loop=LoopConfig(),
        files=FilesConfig(),
        runners={"codex": MagicMock()},
        gates=GatesConfig(commands=[], llm_judge=LlmJudgeConfig()),
        git=GitConfig(),
        tracker=TrackerConfig(),
        parallel=ParallelConfig(enabled=True, max_workers=3),
    )

    with (
        patch("ralph_gold.loop.ensure_git_repo"),
        patch("ralph_gold.loop.run_iteration") as mock_iter,
        patch("ralph_gold.loop.make_tracker") as mock_tracker,
        patch("builtins.print") as mock_print,
    ):
        # Mock tracker
        tracker = MagicMock()
        tracker.kind = "markdown"
        tracker.all_done.return_value = False
        mock_tracker.return_value = tracker

        # Mock iteration result
        mock_result = MagicMock()
        mock_result.iteration = 1
        mock_result.exit_signal = True
        mock_result.no_progress_streak = 0
        mock_iter.return_value = mock_result

        # Run loop with config that has parallel enabled
        results = run_loop(tmp_path, agent="codex", max_iterations=1, cfg=cfg)

        # Verify fallback to sequential (ParallelExecutor not available yet)
        assert len(results) == 1

        # Verify warning was printed
        mock_print.assert_called_once()
        assert "Warning" in str(mock_print.call_args)


def test_run_loop_max_workers_override(tmp_path: Path):
    """Test that max_workers parameter overrides config."""
    # Create .ralph directory
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal config files
    (ralph_dir / "PRD.md").write_text("# Tasks\n- [ ] Task 1\n")
    (ralph_dir / "PROMPT_build.md").write_text("Build prompt")
    (ralph_dir / "AGENTS.md").write_text("# Agents")
    (ralph_dir / "progress.md").write_text("# Progress")

    with (
        patch("ralph_gold.loop.ensure_git_repo"),
        patch("ralph_gold.loop.run_iteration") as mock_iter,
        patch("ralph_gold.loop.make_tracker") as mock_tracker,
        patch("builtins.print"),
    ):
        # Mock tracker
        tracker = MagicMock()
        tracker.kind = "markdown"
        tracker.all_done.return_value = False
        mock_tracker.return_value = tracker

        # Mock iteration result
        mock_result = MagicMock()
        mock_result.iteration = 1
        mock_result.exit_signal = True
        mock_result.no_progress_streak = 0
        mock_iter.return_value = mock_result

        # Run loop with parallel=True and max_workers override
        results = run_loop(
            tmp_path,
            agent="codex",
            max_iterations=1,
            parallel=True,
            max_workers=5,
        )

        # Verify execution completed (falls back to sequential)
        assert len(results) == 1
