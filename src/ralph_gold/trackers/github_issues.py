"""GitHub Issues-based task tracker with parallel grouping support.

This tracker fetches issues from a GitHub repository and uses them as tasks.
It supports:
- Label-based filtering (include/exclude)
- Local caching with TTL to reduce API calls
- Rate limit detection and handling
- Priority sorting (milestone, then created_at)
- Parallel grouping via "group:*" labels
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..github_auth import GitHubAuth, GitHubAuthError, create_auth
from ..prd import SelectedTask, TaskId

logger = logging.getLogger(__name__)


@dataclass
class GitHubIssuesTracker:
    """GitHub Issues-based task tracker.

    Fetches issues from a GitHub repository and caches them locally.
    Supports label filtering, priority sorting, and parallel grouping.
    """

    project_root: Path
    repo: str
    auth: GitHubAuth
    label_filter: str
    exclude_labels: List[str]
    cache_ttl_seconds: int
    cache_path: Path

    def __init__(
        self,
        project_root: Path,
        repo: str,
        auth_method: str = "gh_cli",
        token_env: str = "GITHUB_TOKEN",
        label_filter: str = "ready",
        exclude_labels: Optional[List[str]] = None,
        cache_ttl_seconds: int = 300,
    ):
        """Initialize GitHub Issues tracker.

        Args:
            project_root: Project root directory
            repo: GitHub repository in "owner/repo" format
            auth_method: Authentication method ("gh_cli" or "token")
            token_env: Environment variable name for token auth
            label_filter: Label that issues must have to be included
            exclude_labels: Labels that exclude issues from being tracked
            cache_ttl_seconds: Cache time-to-live in seconds (default: 5 minutes)

        Raises:
            GitHubAuthError: If authentication setup fails
            ValueError: If repo format is invalid
        """
        self.project_root = project_root
        self.repo = repo
        self.label_filter = label_filter
        self.exclude_labels = exclude_labels or []
        self.cache_ttl_seconds = cache_ttl_seconds

        # Validate repo format
        if not repo or "/" not in repo:
            raise ValueError(
                f"Invalid repo format: {repo}. Expected 'owner/repo' format."
            )

        # Setup authentication
        self.auth = create_auth(auth_method=auth_method, token_env=token_env)

        # Setup cache path
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = ralph_dir / "github_cache.json"

        # Setup API logging
        logs_dir = ralph_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        self.api_log_path = logs_dir / "github-api.log"

        # Initial sync
        self._sync_cache()

    @property
    def kind(self) -> str:
        """Return tracker kind identifier."""
        return "github_issues"

    def _cache_is_fresh(self) -> bool:
        """Check if cache is fresh (within TTL).

        Returns:
            True if cache exists and is fresh, False otherwise
        """
        if not self.cache_path.exists():
            return False

        try:
            with open(self.cache_path, "r") as f:
                cache_data = json.load(f)

            cached_at = cache_data.get("cached_at")
            if not cached_at:
                return False

            # Parse timestamp
            cached_time = datetime.fromisoformat(cached_at)
            age = datetime.now() - cached_time

            return age.total_seconds() < self.cache_ttl_seconds

        except (json.JSONDecodeError, ValueError, KeyError):
            return False

    def _load_cache(self) -> List[Dict[str, Any]]:
        """Load issues from cache.

        Returns:
            List of cached issue dictionaries
        """
        if not self.cache_path.exists():
            return []

        try:
            with open(self.cache_path, "r") as f:
                cache_data = json.load(f)
            return cache_data.get("issues", [])
        except (json.JSONDecodeError, ValueError):
            return []

    def _save_cache(self, issues: List[Dict[str, Any]]) -> None:
        """Save issues to cache.

        Args:
            issues: List of issue dictionaries to cache
        """
        cache_data = {
            "cached_at": datetime.now().isoformat(),
            "repo": self.repo,
            "issues": issues,
        }

        with open(self.cache_path, "w") as f:
            json.dump(cache_data, f, indent=2)

    def _sync_cache(self) -> None:
        """Fetch issues from GitHub and update cache.

        Only fetches if cache is stale. Handles rate limits gracefully.
        """
        # Check if cache is fresh
        if self._cache_is_fresh():
            return

        try:
            # Fetch issues from GitHub
            endpoint = f"/repos/{self.repo}/issues"

            # Build query parameters
            params = []
            if self.label_filter:
                params.append(f"labels={self.label_filter}")
            params.append("state=open")
            params.append("per_page=100")  # Fetch up to 100 issues

            if params:
                endpoint += "?" + "&".join(params)

            # Make API call
            issues = self.auth.api_call("GET", endpoint)

            # Ensure we got a list
            if not isinstance(issues, list):
                issues = []

            # Filter out excluded labels
            filtered_issues = []
            for issue in issues:
                # Skip pull requests (they appear as issues in the API)
                if "pull_request" in issue:
                    continue

                # Check for excluded labels
                issue_labels = [
                    label["name"] if isinstance(label, dict) else str(label)
                    for label in issue.get("labels", [])
                ]

                if any(excluded in issue_labels for excluded in self.exclude_labels):
                    continue

                filtered_issues.append(issue)

            # Save to cache
            self._save_cache(filtered_issues)

        except GitHubAuthError:
            # If sync fails, use cached data if available
            # This allows offline operation with stale cache
            if self.cache_path.exists():
                # Log warning but continue with cached data
                pass
            else:
                # No cache available, re-raise error
                raise

    def _extract_group_from_labels(self, labels: List[Any]) -> str:
        """Extract parallel group from issue labels.

        Looks for labels matching "group:*" pattern.
        If no group label found, returns "default".

        Args:
            labels: List of label objects or strings

        Returns:
            Group name (e.g., "auth" from "group:auth", or "default")
        """
        group_pattern = re.compile(r"^group:(.+)$", re.IGNORECASE)

        for label in labels:
            # Handle both label objects and strings
            label_name = label["name"] if isinstance(label, dict) else str(label)

            match = group_pattern.match(label_name)
            if match:
                return match.group(1).strip()

        return "default"

    def _parse_acceptance_criteria(self, body: str) -> List[str]:
        """Parse acceptance criteria from issue body.

        Looks for "## Acceptance Criteria" section and extracts checkbox items.

        Args:
            body: Issue body text

        Returns:
            List of acceptance criteria strings
        """
        if not body:
            return []

        acceptance = []
        in_acceptance_section = False
        lines = body.split("\n")

        for line in lines:
            # Check for acceptance criteria heading
            if re.match(r"^\s*#{1,6}\s+acceptance\s+criteria\b", line, re.IGNORECASE):
                in_acceptance_section = True
                continue

            # Stop at next heading
            if in_acceptance_section and re.match(r"^\s*#{1,6}\s+", line):
                break

            # Extract checkbox items
            if in_acceptance_section:
                # Match checkbox items: - [ ] or - [x]
                match = re.match(r"^\s*[-*]\s+\[[ xX]\]\s+(.+)$", line)
                if match:
                    acceptance.append(match.group(1).strip())

        return acceptance

    def _issue_to_task(self, issue: Dict[str, Any]) -> SelectedTask:
        """Convert GitHub issue to SelectedTask.

        Args:
            issue: Issue dictionary from GitHub API

        Returns:
            SelectedTask instance
        """
        issue_number = str(issue.get("number", ""))
        title = str(issue.get("title", f"Issue {issue_number}"))
        body = issue.get("body", "") or ""

        # Parse acceptance criteria from body
        acceptance = self._parse_acceptance_criteria(body)

        return SelectedTask(
            id=issue_number, title=title, kind="github_issues", acceptance=acceptance
        )

    def _sort_issues_by_priority(
        self, issues: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Sort issues by priority (milestone, then created_at).

        Args:
            issues: List of issue dictionaries

        Returns:
            Sorted list of issues
        """

        def priority_key(issue: Dict[str, Any]) -> Tuple[int, str]:
            # Milestone priority (lower number = higher priority)
            milestone = issue.get("milestone")
            if milestone and isinstance(milestone, dict):
                milestone_number = milestone.get("number", 999999)
            else:
                milestone_number = 999999

            # Created date (older = higher priority)
            created_at = issue.get("created_at", "9999-12-31T23:59:59Z")

            return (milestone_number, created_at)

        return sorted(issues, key=priority_key)

    def select_next_task(
        self, exclude_ids: Optional[Set[str]] = None
    ) -> Optional[SelectedTask]:
        """Return the next available task without claiming it.

        Returns:
            Next uncompleted task, or None if no tasks available
        """
        self._sync_cache()
        issues = self._load_cache()

        if not issues:
            return None

        # Sort by priority
        sorted_issues = self._sort_issues_by_priority(issues)

        exclude = exclude_ids or set()
        for issue in sorted_issues:
            issue_number = str(issue.get("number", ""))
            if issue_number and issue_number in exclude:
                continue
            return self._issue_to_task(issue)
        return None

    def peek_next_task(self) -> Optional[SelectedTask]:
        return self.select_next_task()

    def claim_next_task(self) -> Optional[SelectedTask]:
        """Claim the next available task.

        For GitHub Issues, this is the same as peek_next_task since
        we don't modify issue state on claim (only on completion).

        Returns:
            Next uncompleted task, or None if no tasks available
        """
        return self.select_next_task()

    def counts(self) -> Tuple[int, int]:
        """Return (completed_count, total_count) for tasks.

        Note: For GitHub Issues, we only track open issues in cache,
        so completed count is always 0 and total is the number of open issues.

        Returns:
            Tuple of (0, open_issues_count)
        """
        self._sync_cache()
        issues = self._load_cache()
        return (0, len(issues))

    def all_done(self) -> bool:
        """Check if all tasks are completed.

        Returns:
            True if no open issues remain
        """
        self._sync_cache()
        issues = self._load_cache()
        return len(issues) == 0

    def all_blocked(self) -> bool:
        """Check if all remaining tasks are marked as blocked.

        For GitHub Issues, we check if all remaining issues have the "blocked" label.

        Returns:
            True if all remaining issues have the "blocked" label, False otherwise.
            Returns False if there are no remaining issues (all done).
        """
        self._sync_cache()
        issues = self._load_cache()
        if not issues:
            return False  # All done, not blocked
        for issue in issues:
            labels = issue.get("labels", [])
            if isinstance(labels, list):
                label_names = [lbl.get("name", "") for lbl in labels if isinstance(lbl, dict)]
                if "blocked" not in label_names:
                    return False
        return True

    def is_task_done(self, task_id: TaskId) -> bool:
        """Check if a specific task is marked done.

        For GitHub Issues, we check if the issue is closed.

        Args:
            task_id: Issue number to check

        Returns:
            True if issue is closed (not in cache)
        """
        self._sync_cache()
        issues = self._load_cache()

        # If issue is not in cache, it's either closed or doesn't exist
        for issue in issues:
            if str(issue.get("number")) == str(task_id):
                return False  # Issue is open

        return True  # Issue not found in open issues

    def force_task_open(self, task_id: TaskId) -> bool:
        """Force a task to be marked as open.

        For GitHub Issues, this would require reopening the issue via API.
        This is not implemented in the core tracker (handled by updates module).

        Args:
            task_id: Issue number to reopen

        Returns:
            False (not implemented in core tracker)
        """
        # This would require API call to reopen issue
        # Deferred to task 2.3 (GitHub Issues Updates)
        return False

    def block_task(self, task_id: TaskId, reason: str) -> bool:
        """Best-effort: label the issue as blocked."""
        try:
            return self._add_labels(str(task_id), ["blocked"])
        except (GitHubAuthError, RuntimeError, OSError) as e:
            logger.error("Failed to block task %s: %s", task_id, e)
            return False

    def _find_open_issue(self, task_id: TaskId) -> Optional[Dict[str, Any]]:
        """Find an issue in the current open-issues cache."""
        self._sync_cache()
        issues = self._load_cache()
        tid = str(task_id)
        for issue in issues:
            if str(issue.get("number")) == tid:
                return issue
        return None

    def _fetch_issue(self, task_id: TaskId) -> Optional[Dict[str, Any]]:
        """Fetch issue (open or closed) directly from GitHub API."""
        endpoint = f"/repos/{self.repo}/issues/{task_id}"
        try:
            issue = self.auth.api_call("GET", endpoint)
        except GitHubAuthError:
            return None
        if isinstance(issue, dict) and issue.get("number") is not None:
            return issue
        return None

    def get_task_by_id(self, task_id: TaskId) -> Optional[SelectedTask]:
        """Return task by ID from cache/API if present."""
        issue = self._find_open_issue(task_id)
        if issue is None:
            issue = self._fetch_issue(task_id)
        if issue is None:
            return None
        return self._issue_to_task(issue)

    def get_task_status(self, task_id: TaskId) -> str:
        """Return task status by ID: open|done|blocked|missing."""
        issue = self._find_open_issue(task_id)
        if issue is not None:
            labels = issue.get("labels", [])
            if isinstance(labels, list):
                label_names = [lbl.get("name", "") for lbl in labels if isinstance(lbl, dict)]
                if "blocked" in label_names:
                    return "blocked"
            return "open"

        issue = self._fetch_issue(task_id)
        if issue is None:
            return "missing"
        state = str(issue.get("state", "")).lower()
        if state == "closed":
            return "done"
        labels = issue.get("labels", [])
        if isinstance(labels, list):
            label_names = [lbl.get("name", "") for lbl in labels if isinstance(lbl, dict)]
            if "blocked" in label_names:
                return "blocked"
        return "open"

    def branch_name(self) -> Optional[str]:
        """Return the branch name for the current task.

        For GitHub Issues, we don't have a single branch name since
        each issue could have its own branch.

        Returns:
            None
        """
        return None

    def get_parallel_groups(self) -> Dict[str, List[SelectedTask]]:
        """Return tasks grouped by parallel group.

        Groups are extracted from "group:*" labels on issues.
        Issues without a group label default to the "default" group.

        Only open issues are included in the groups.

        Returns:
            Dictionary mapping group names to lists of SelectedTask instances
        """
        self._sync_cache()
        issues = self._load_cache()

        groups: Dict[str, List[SelectedTask]] = {}

        for issue in issues:
            # Extract group from labels
            labels = issue.get("labels", [])
            group = self._extract_group_from_labels(labels)

            # Convert to SelectedTask
            task = self._issue_to_task(issue)

            # Add to group
            if group not in groups:
                groups[group] = []
            groups[group].append(task)

        return groups

    def mark_task_done(
        self,
        task_id: TaskId,
        close_issue: bool = True,
        add_comment: bool = True,
        comment_body: Optional[str] = None,
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None,
        commit_sha: Optional[str] = None,
    ) -> bool:
        """Mark a task as done by updating the GitHub issue.

        This method can:
        - Close the issue
        - Add a completion comment
        - Add/remove labels
        - Link to commit SHA

        All API failures are logged but don't crash the tracker.

        Args:
            task_id: Issue number to update
            close_issue: Whether to close the issue (default: True)
            add_comment: Whether to add a completion comment (default: True)
            comment_body: Custom comment text (if None, generates default)
            add_labels: Labels to add to the issue
            remove_labels: Labels to remove from the issue
            commit_sha: Commit SHA to link in the comment

        Returns:
            True if all operations succeeded, False if any failed
        """
        success = True
        issue_number = str(task_id)

        try:
            # Close the issue if requested
            if close_issue:
                success = success and self._close_issue(issue_number)

            # Add completion comment if requested
            if add_comment:
                if comment_body is None:
                    comment_body = self._generate_completion_comment(commit_sha)
                success = success and self._add_comment(issue_number, comment_body)

            # Manage labels
            if add_labels:
                success = success and self._add_labels(issue_number, add_labels)
            if remove_labels:
                success = success and self._remove_labels(issue_number, remove_labels)

            # Invalidate cache to force refresh on next sync
            if success:
                self._invalidate_cache()

            return success

        except (GitHubAuthError, json.JSONDecodeError, OSError, RuntimeError) as e:
            logger.error("Failed to mark task %s as done: %s", task_id, e)
            return False

    def _log_api_call(self, level: str, message: str) -> None:
        """Log an API call to a file for debugging."""
        if not self.api_log_path:
            return
        try:
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "method": level,
                "message": message,
            }
            with open(self.api_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except OSError as e:
            logger.debug("Failed to write API call log: %s", e)

    def _close_issue(self, issue_number: str) -> bool:
        """Close a GitHub issue.

        Args:
            issue_number: Issue number to close

        Returns:
            True if successful, False otherwise
        """
        try:
            endpoint = f"/repos/{self.repo}/issues/{issue_number}"
            data = {"state": "closed"}

            self._log_api_call("INFO", f"Closing issue #{issue_number}")
            self.auth.api_call("PATCH", endpoint, data)
            self._log_api_call("INFO", f"Successfully closed issue #{issue_number}")

            return True

        except GitHubAuthError as e:
            self._log_api_call("ERROR", f"Failed to close issue #{issue_number}: {e}")
            return False

    def _add_comment(self, issue_number: str, body: str) -> bool:
        """Add a comment to a GitHub issue.

        Args:
            issue_number: Issue number to comment on
            body: Comment text

        Returns:
            True if successful, False otherwise
        """
        try:
            endpoint = f"/repos/{self.repo}/issues/{issue_number}/comments"
            data = {"body": body}

            self._log_api_call("INFO", f"Adding comment to issue #{issue_number}")
            self.auth.api_call("POST", endpoint, data)
            self._log_api_call(
                "INFO", f"Successfully added comment to issue #{issue_number}"
            )

            return True

        except GitHubAuthError as e:
            self._log_api_call(
                "ERROR", f"Failed to add comment to issue #{issue_number}: {e}"
            )
            return False

    def _add_labels(self, issue_number: str, labels: List[str]) -> bool:
        """Add labels to a GitHub issue.

        Args:
            issue_number: Issue number to label
            labels: List of label names to add

        Returns:
            True if successful, False otherwise
        """
        try:
            endpoint = f"/repos/{self.repo}/issues/{issue_number}/labels"
            data = {"labels": labels}

            self._log_api_call(
                "INFO", f"Adding labels {labels} to issue #{issue_number}"
            )
            self.auth.api_call("POST", endpoint, data)
            self._log_api_call(
                "INFO", f"Successfully added labels to issue #{issue_number}"
            )

            return True

        except GitHubAuthError as e:
            self._log_api_call(
                "ERROR", f"Failed to add labels to issue #{issue_number}: {e}"
            )
            return False

    def _remove_labels(self, issue_number: str, labels: List[str]) -> bool:
        """Remove labels from a GitHub issue.

        Args:
            issue_number: Issue number to unlabel
            labels: List of label names to remove

        Returns:
            True if all removals successful, False if any failed
        """
        success = True

        for label in labels:
            try:
                endpoint = f"/repos/{self.repo}/issues/{issue_number}/labels/{label}"

                self._log_api_call(
                    "INFO", f"Removing label '{label}' from issue #{issue_number}"
                )
                self.auth.api_call("DELETE", endpoint)
                self._log_api_call(
                    "INFO",
                    f"Successfully removed label '{label}' from issue #{issue_number}",
                )

            except GitHubAuthError as e:
                self._log_api_call(
                    "ERROR",
                    f"Failed to remove label '{label}' from issue #{issue_number}: {e}",
                )
                success = False

        return success

    def _generate_completion_comment(self, commit_sha: Optional[str] = None) -> str:
        """Generate a default completion comment.

        Args:
            commit_sha: Optional commit SHA to link

        Returns:
            Formatted comment text
        """
        lines = ["✅ Task completed by ralph-gold", ""]

        if commit_sha:
            lines.append(f"**Commit:** {commit_sha}")
            lines.append("")

        lines.append(
            f"**Completed at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        return "\n".join(lines)

    def _invalidate_cache(self) -> None:
        """Invalidate the cache to force refresh on next sync."""
        if self.cache_path.exists():
            try:
                # Set cached_at to a very old timestamp
                with open(self.cache_path, "r") as f:
                    cache_data = json.load(f)

                cache_data["cached_at"] = "2000-01-01T00:00:00"

                with open(self.cache_path, "w") as f:
                    json.dump(cache_data, f, indent=2)

            except (json.JSONDecodeError, ValueError, KeyError):
                # If cache is corrupted, just delete it
                self.cache_path.unlink()
