"""Git worktree management for parallel execution.

This module provides the WorktreeManager class for creating, managing, and
cleaning up git worktrees used for isolated parallel task execution.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple

from .prd import SelectedTask

logger = logging.getLogger(__name__)


class WorktreeError(Exception):
    """Base exception for worktree operations."""

    pass


class WorktreeCreationError(WorktreeError):
    """Failed to create worktree."""

    pass


class WorktreeRemovalError(WorktreeError):
    """Failed to remove worktree."""

    pass


class WorktreeManager:
    """Manages git worktrees for parallel execution.

    Each worktree provides complete isolation for a parallel worker,
    with its own working directory and branch.
    """

    def __init__(self, project_root: Path, worktree_root: Path):
        """Initialize worktree manager.

        Args:
            project_root: Root directory of the git repository
            worktree_root: Directory where worktrees will be created
        """
        self.project_root = project_root
        self.worktree_root = worktree_root
        self.worktree_root.mkdir(parents=True, exist_ok=True)

    def create_worktree(self, task: SelectedTask, worker_id: int) -> Tuple[Path, str]:
        """Create isolated worktree for task.

        Args:
            task: Task to execute in this worktree
            worker_id: Unique identifier for the worker

        Returns:
            Tuple of (worktree_path, branch_name)

        Raises:
            WorktreeCreationError: If git worktree creation fails
        """
        # Generate unique branch name
        branch_name = self._generate_branch_name(task, worker_id)

        # Generate worktree path
        worktree_path = self.worktree_root / f"worker-{worker_id}-{task.id}"

        # Remove existing worktree if it exists (cleanup from previous run)
        if worktree_path.exists():
            try:
                self.remove_worktree(worktree_path)
            except WorktreeRemovalError:
                # If removal fails, try with a different path
                worktree_path = (
                    self.worktree_root / f"worker-{worker_id}-{task.id}-retry"
                )

        # Check if branch already exists and delete it (best-effort).
        # We intentionally do not use check=True here because:
        # - branch may not exist
        # - we want creation to proceed regardless
        try:
            subprocess.run(
                ["git", "branch", "-D", branch_name],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                check=False,
            )
        except subprocess.CalledProcessError as e:
            logger.debug("Branch delete failed (ignored): %s", e)

        try:
            # Create worktree with new branch
            subprocess.run(
                ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
                cwd=str(self.project_root),
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )

            return worktree_path, branch_name

        except (subprocess.SubprocessError, OSError) as e:
            error_msg = f"Failed to create worktree: {getattr(e, 'stderr', str(e))}"
            raise WorktreeCreationError(error_msg) from e

    def remove_worktree(self, worktree_path: Path) -> None:
        """Remove worktree and clean up.

        Args:
            worktree_path: Path to the worktree to remove

        Raises:
            WorktreeRemovalError: If git worktree removal fails
        """
        if not worktree_path.exists():
            return

        try:
            subprocess.run(
                ["git", "worktree", "remove", str(worktree_path), "--force"],
                cwd=str(self.project_root),
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to remove worktree at {worktree_path}: {e.stderr}"
            raise WorktreeRemovalError(error_msg) from e

    def list_worktrees(self) -> List[Path]:
        """List all worktrees managed by this manager.

        Returns:
            List of worktree paths
        """
        if not self.worktree_root.exists():
            return []

        return [
            p
            for p in self.worktree_root.iterdir()
            if p.is_dir() and p.name.startswith("worker-")
        ]

    def cleanup_stale_worktrees(self) -> int:
        """Clean up stale worktrees that are no longer in use.

        This removes worktrees that exist on disk but are not registered
        with git (e.g., from crashed processes).

        Returns:
            Number of worktrees cleaned up
        """
        cleaned = 0

        # Get list of registered worktrees from git
        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=str(self.project_root),
                check=True,
                capture_output=True,
                text=True,
            )

            # Parse worktree list to get paths (resolve to absolute paths for comparison)
            registered_paths = set()
            for line in result.stdout.splitlines():
                if line.startswith("worktree "):
                    path = Path(line.split(" ", 1)[1]).resolve()
                    registered_paths.add(path)

            # Check each worktree directory
            for worktree_path in self.list_worktrees():
                if worktree_path.resolve() not in registered_paths:
                    # Stale worktree - remove directory
                    try:
                        shutil.rmtree(worktree_path)
                        cleaned += 1
                    except OSError as e:
                        logger.debug("Failed to remove worktree: %s", e)
                        # If we can't remove it, skip it
                        pass

        except subprocess.CalledProcessError:
            # If git worktree list fails, we can't clean up safely
            pass

        return cleaned

    def _generate_branch_name(self, task: SelectedTask, worker_id: int) -> str:
        """Generate unique branch name for worker.

        Args:
            task: Task being executed
            worker_id: Worker identifier

        Returns:
            Branch name in format: ralph/worker-{id}-task-{task_id}
        """
        # Sanitize task ID for branch name
        task_id_safe = str(task.id).replace("/", "-").replace(" ", "-")
        return f"ralph/worker-{worker_id}-task-{task_id_safe}"
