from __future__ import annotations

import importlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple

from .config import Config
from .prd import SelectedTask, TaskId, get_prd_branch_name, is_markdown_prd
from .prd import all_done as prd_all_done
from .prd import force_task_open as prd_force_open
from .prd import is_task_done as prd_is_done
from .prd import select_next_task as prd_select_next
from .prd import task_counts as prd_counts


class Tracker(Protocol):
    """Abstraction over different task tracking backends.

    The default is file-based trackers (Markdown/JSON). Optionally, Beads can be
    used via the `bd` CLI.
    """

    kind: str

    def peek_next_task(self) -> Optional[SelectedTask]: ...

    def claim_next_task(self) -> Optional[SelectedTask]: ...

    def counts(self) -> Tuple[int, int]: ...

    def all_done(self) -> bool: ...

    def is_task_done(self, task_id: TaskId) -> bool: ...

    def force_task_open(self, task_id: TaskId) -> bool: ...

    def branch_name(self) -> Optional[str]: ...

    def get_parallel_groups(self) -> Dict[str, List[SelectedTask]]:
        """Return tasks grouped by parallel group.

        Default implementation: all tasks in "default" group (sequential).
        Trackers that support grouping override this method.

        Returns:
            Dictionary mapping group names to lists of tasks
        """
        ...


@dataclass
class FileTracker:
    prd_path: Path

    @property
    def kind(self) -> str:
        return "md" if is_markdown_prd(self.prd_path) else "json"

    def peek_next_task(self) -> Optional[SelectedTask]:
        return prd_select_next(self.prd_path)

    def claim_next_task(self) -> Optional[SelectedTask]:
        return prd_select_next(self.prd_path)

    def counts(self) -> Tuple[int, int]:
        return prd_counts(self.prd_path)

    def all_done(self) -> bool:
        return prd_all_done(self.prd_path)

    def is_task_done(self, task_id: TaskId) -> bool:
        return prd_is_done(self.prd_path, task_id)

    def force_task_open(self, task_id: TaskId) -> bool:
        return prd_force_open(self.prd_path, task_id)

    def branch_name(self) -> Optional[str]:
        return get_prd_branch_name(self.prd_path)

    def get_parallel_groups(self) -> Dict[str, List[SelectedTask]]:
        """Return all tasks in default group (sequential execution)."""
        # File-based trackers don't support parallel grouping
        # Return all incomplete tasks in a single "default" group
        tasks: List[SelectedTask] = []
        try:
            task = self.peek_next_task()
            if task:
                tasks.append(task)
        except Exception:
            # If we can't peek (file doesn't exist, etc.), return empty
            pass
        return {"default": tasks}


@dataclass
class BeadsTracker:
    """A tracker backed by Beads (steveyegge/beads) via the `bd` CLI.

    This is intentionally lightweight: it relies on `bd ready --json`,
    `bd update <id> --status in_progress`, and `bd close <id>`.

    If the repo does not use Beads, do not enable this tracker.
    """

    project_root: Path
    ready_args: List[str]

    kind: str = "beads"

    def _run(self, argv: List[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            argv,
            cwd=str(self.project_root),
            capture_output=True,
            text=True,
            check=False,
        )

    def _ready_json(self) -> Optional[List[Dict[str, Any]]]:
        cp = self._run(["bd", *self.ready_args])
        out = (cp.stdout or "").strip()
        if cp.returncode != 0:
            return None
        try:
            obj = json.loads(out)
            if isinstance(obj, list):
                return [x for x in obj if isinstance(x, dict)]
            return None
        except Exception:
            return None

    def _ready_text(self) -> List[Dict[str, Any]]:
        cp = self._run(["bd", "ready"])
        txt = cp.stdout or ""
        issues: List[Dict[str, Any]] = []
        current: Dict[str, Any] = {}
        for line in txt.splitlines():
            line = line.strip()
            if not line:
                if current:
                    issues.append(current)
                    current = {}
                continue
            m = re.match(r"^ID:\s*(.+)$", line, re.IGNORECASE)
            if m:
                current["id"] = m.group(1).strip()
                continue
            m = re.match(r"^Title:\s*(.+)$", line, re.IGNORECASE)
            if m:
                current["title"] = m.group(1).strip()
                continue
            m = re.match(r"^Priority:\s*(.+)$", line, re.IGNORECASE)
            if m:
                current["priority"] = m.group(1).strip()
                continue
            m = re.match(r"^Status:\s*(.+)$", line, re.IGNORECASE)
            if m:
                current["status"] = m.group(1).strip()
                continue
        if current:
            issues.append(current)
        return issues

    def _select_next_issue(self) -> Optional[Dict[str, Any]]:
        issues = self._ready_json()
        if issues is None:
            issues = self._ready_text()

        if not issues:
            return None
        # Heuristic: choose the first issue returned by bd ready (it is already
        # sorted by priority/age per beads defaults).
        return issues[0]

    def peek_next_task(self) -> Optional[SelectedTask]:
        issue = self._select_next_issue()
        if not issue:
            return None
        tid = str(issue.get("id") or "").strip()
        title = str(issue.get("title") or tid).strip() or tid
        if not tid:
            return None
        return SelectedTask(id=tid, title=title, kind="beads", acceptance=[])

    def claim_next_task(self) -> Optional[SelectedTask]:
        issue = self._select_next_issue()
        if not issue:
            return None
        tid = str(issue.get("id") or "").strip()
        title = str(issue.get("title") or tid).strip() or tid
        if not tid:
            return None

        # Mark as in progress (best-effort; ignore errors).
        self._run(["bd", "update", tid, "--status", "in_progress", "--json"])

        return SelectedTask(id=tid, title=title, kind="beads", acceptance=[])

    def counts(self) -> Tuple[int, int]:
        # Beads doesn't have a single "counts" API; keep this lightweight.
        # Users can rely on `bd stats` for deeper insights.
        return 0, 0

    def all_done(self) -> bool:
        # Unknown without a project-level query.
        return False

    def is_task_done(self, task_id: TaskId) -> bool:
        # Best-effort: bd show --json and check status.
        cp = self._run(["bd", "show", str(task_id), "--json"])
        if cp.returncode != 0:
            return False
        try:
            obj = json.loads((cp.stdout or "").strip())
            if isinstance(obj, dict):
                status = str(obj.get("status", "")).lower()
                return status in {"done", "closed", "complete", "completed"}
        except Exception:
            return False
        return False

    def force_task_open(self, task_id: TaskId) -> bool:
        # No direct equivalent. We attempt to reopen.
        cp = self._run(["bd", "update", str(task_id), "--status", "open", "--json"])
        return cp.returncode == 0

    def branch_name(self) -> Optional[str]:
        return None

    def get_parallel_groups(self) -> Dict[str, List[SelectedTask]]:
        """Return all tasks in default group (sequential execution)."""
        # Beads tracker doesn't support parallel grouping
        # Return all ready tasks in a single "default" group
        tasks: List[SelectedTask] = []
        try:
            task = self.peek_next_task()
            if task:
                tasks.append(task)
        except Exception:
            # If we can't peek (bd not available, etc.), return empty
            pass
        return {"default": tasks}


def _load_plugin(path: str, cfg: Config, project_root: Path) -> Tracker:
    """Load a tracker plugin from `module:callable`.

    The callable is invoked as `callable(cfg=cfg, project_root=project_root)` and
    must return an object implementing the Tracker protocol.
    """

    if ":" not in path:
        raise ValueError("tracker.plugin must be of the form 'module:callable'")
    mod_name, attr = path.split(":", 1)
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, attr)
    tracker = fn(cfg=cfg, project_root=project_root)
    return tracker  # type: ignore[return-value]


def make_tracker(project_root: Path, cfg: Config) -> Tracker:
    """Instantiate the configured tracker."""

    if cfg.tracker.plugin:
        return _load_plugin(cfg.tracker.plugin, cfg=cfg, project_root=project_root)

    kind = (cfg.tracker.kind or "auto").strip().lower()
    prd_path = (project_root / cfg.files.prd).resolve()

    if kind == "auto":
        # Auto-detect based on file extension
        if prd_path.suffix in {".yaml", ".yml"}:
            kind = "yaml"
        elif is_markdown_prd(prd_path):
            kind = "markdown"
        else:
            kind = "json"

    if kind in {"markdown", "md", "json", "file"}:
        return FileTracker(prd_path=prd_path)

    if kind in {"yaml", "yml"}:
        # Import YamlTracker from trackers package
        from .trackers.yaml_tracker import YamlTracker

        return YamlTracker(prd_path=prd_path)

    if kind in {"beads", "bd"}:
        # Prefer JSON output to avoid parsing.
        return BeadsTracker(project_root=project_root, ready_args=["ready", "--json"])

    if kind in {"github_issues", "github"}:
        # Import GitHubIssuesTracker from trackers package
        from .trackers.github_issues import GitHubIssuesTracker

        # Get GitHub config (will be added to Config in task 2.4)
        # For now, use sensible defaults
        github_cfg = getattr(cfg.tracker, "github", None)
        if github_cfg:
            return GitHubIssuesTracker(
                project_root=project_root,
                repo=github_cfg.repo,
                auth_method=github_cfg.auth_method,
                token_env=github_cfg.token_env,
                label_filter=github_cfg.label_filter,
                exclude_labels=github_cfg.exclude_labels,
                cache_ttl_seconds=github_cfg.cache_ttl_seconds,
            )
        else:
            # Fallback: require repo to be set somehow
            raise ValueError(
                "GitHub Issues tracker requires [tracker.github] configuration in ralph.toml"
            )

    raise ValueError(f"Unknown tracker kind: {cfg.tracker.kind}")
