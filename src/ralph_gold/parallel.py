"""Parallel execution engine for ralph-gold.

This module provides parallel task execution using git worktrees for isolation.
Each worker runs in its own worktree with a unique branch, enabling safe
concurrent execution of independent tasks.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .config import Config
from .loop import IterationResult, run_iteration
from .prd import SelectedTask
from .trackers import Tracker
from .worktree import WorktreeManager


@dataclass
class WorkerState:
    """State of a single parallel worker.

    Tracks the complete lifecycle of a worker from task assignment through
    completion or failure.
    """

    worker_id: int
    task: SelectedTask
    worktree_path: Path
    branch_name: str
    status: str  # queued|running|success|failed
    started_at: Optional[float]
    completed_at: Optional[float]
    iteration_result: Optional[IterationResult]
    error: Optional[str]


class ParallelExecutor:
    """Executes tasks in parallel using worker pool and git worktrees.

    Key features:
    - Worker isolation via git worktrees
    - Configurable scheduling strategies (queue, group)
    - Failure isolation (one worker failure doesn't kill others)
    - Optional auto-merge on success
    """

    def __init__(self, project_root: Path, cfg: Config):
        """Initialize parallel executor.

        Args:
            project_root: Root directory of the project
            cfg: Configuration object with parallel settings
        """
        self.project_root = project_root
        self.cfg = cfg
        self.worktree_mgr = WorktreeManager(
            project_root, project_root / cfg.parallel.worktree_root
        )
        self.workers: dict[int, WorkerState] = {}
        self.executor = ThreadPoolExecutor(max_workers=cfg.parallel.max_workers)

    def run_parallel(self, agent: str, tracker: Tracker) -> List[IterationResult]:
        """Execute tasks in parallel.

        Args:
            agent: Name of the agent to use (e.g., "codex", "claude")
            tracker: Tracker instance for task management

        Returns:
            List of iteration results from all workers
        """
        # Get parallel groups from tracker
        groups = tracker.get_parallel_groups()

        # Schedule tasks based on strategy
        if self.cfg.parallel.strategy == "queue":
            tasks = self._flatten_groups(groups)
        else:  # "group"
            tasks = self._schedule_by_groups(groups)

        if not tasks:
            return []

        # Execute workers
        futures = []
        for worker_id, task in enumerate(tasks):
            future = self.executor.submit(
                self._run_worker, worker_id=worker_id, task=task, agent=agent
            )
            futures.append(future)

        # Wait for completion and collect results
        results = []
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception:
                # Worker failure is already logged in worker state
                # Continue collecting other results
                pass

        return results

    def _run_worker(
        self, worker_id: int, task: SelectedTask, agent: str
    ) -> IterationResult:
        """Run single worker in isolated worktree.

        Args:
            worker_id: Unique identifier for this worker
            task: Task to execute
            agent: Agent name to use

        Returns:
            IterationResult from the worker execution

        Raises:
            Exception: If worker execution fails
        """
        # Create worktree
        worktree_path, branch_name = self.worktree_mgr.create_worktree(task, worker_id)

        # Initialize worker state
        worker = WorkerState(
            worker_id=worker_id,
            task=task,
            worktree_path=worktree_path,
            branch_name=branch_name,
            status="running",
            started_at=time.time(),
            completed_at=None,
            iteration_result=None,
            error=None,
        )
        self.workers[worker_id] = worker

        try:
            # Run iteration in worktree
            result = run_iteration(
                project_root=worktree_path,
                agent=agent,
                cfg=self.cfg,
                iteration=worker_id + 1,
                task_override=task,
            )

            worker.status = "success" if result.gates_ok else "failed"
            worker.iteration_result = result

            # Handle merge if successful and auto-merge enabled
            if result.gates_ok and self.cfg.parallel.merge_policy == "auto_merge":
                self._merge_worker(worker)

            return result

        except Exception as e:
            worker.status = "failed"
            worker.error = str(e)
            raise

        finally:
            worker.completed_at = time.time()

    def _flatten_groups(
        self, groups: dict[str, List[SelectedTask]]
    ) -> List[SelectedTask]:
        """Flatten all groups into a single FIFO queue.

        Args:
            groups: Dictionary mapping group names to task lists

        Returns:
            Flattened list of all tasks
        """
        tasks: List[SelectedTask] = []
        for group_name in sorted(groups.keys()):
            tasks.extend(groups[group_name])
        return tasks

    def _schedule_by_groups(
        self, groups: dict[str, List[SelectedTask]]
    ) -> List[SelectedTask]:
        """Schedule tasks by groups (groups run sequentially, tasks within parallel).

        This is a simplified implementation that returns tasks in group order.
        Full group-aware scheduling would require more complex orchestration.

        Args:
            groups: Dictionary mapping group names to task lists

        Returns:
            List of tasks ordered by group
        """
        # For now, return tasks in group order
        # Full implementation would run groups sequentially with parallel tasks within
        tasks: List[SelectedTask] = []
        for group_name in sorted(groups.keys()):
            tasks.extend(groups[group_name])
        return tasks

    def _merge_worker(self, worker: WorkerState) -> None:
        """Merge worker branch back to main (for auto_merge policy).

        Args:
            worker: Worker state with branch to merge

        Note:
            This is a placeholder for merge functionality.
            Full implementation would handle merge conflicts and cleanup.
        """
        # TODO: Implement merge logic
        # - Switch to base branch
        # - Merge worker branch
        # - Handle conflicts
        # - Clean up worktree on success
        pass
