"""Tests for GitHub Issues tracker implementation."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from ralph_gold.github_auth import GitHubAuthError
from ralph_gold.trackers.github_issues import GitHubIssuesTracker


@pytest.fixture
def temp_project_root(tmp_path):
    """Create a temporary project root directory."""
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def mock_auth():
    """Create a mock GitHub auth object."""
    auth = Mock()
    auth.api_call = Mock()
    auth.validate = Mock(return_value=True)
    return auth


@pytest.fixture
def sample_issues():
    """Sample GitHub issues for testing."""
    return [
        {
            "number": 1,
            "title": "Implement user authentication",
            "body": "## Description\nAdd JWT auth\n\n## Acceptance Criteria\n- [ ] User can log in\n- [ ] Token is returned",
            "state": "open",
            "labels": [{"name": "ready"}, {"name": "group:auth"}],
            "created_at": "2024-01-15T10:00:00Z",
            "milestone": {"number": 1},
        },
        {
            "number": 2,
            "title": "Create user profile UI",
            "body": "## Description\nProfile page\n\n## Acceptance Criteria\n- [ ] Display user info",
            "state": "open",
            "labels": [{"name": "ready"}, {"name": "group:ui"}],
            "created_at": "2024-01-15T11:00:00Z",
            "milestone": {"number": 1},
        },
        {
            "number": 3,
            "title": "Add API endpoint",
            "body": "Create REST API",
            "state": "open",
            "labels": [{"name": "ready"}],
            "created_at": "2024-01-15T09:00:00Z",
            "milestone": None,
        },
    ]


class TestGitHubIssuesTrackerInit:
    """Tests for GitHubIssuesTracker initialization."""

    def test_init_with_gh_cli(self, temp_project_root, sample_issues):
        """Test initialization with gh CLI auth."""
        with patch("ralph_gold.trackers.github_issues.create_auth") as mock_create:
            mock_auth = Mock()
            mock_auth.api_call = Mock(return_value=sample_issues)
            mock_create.return_value = mock_auth

            tracker = GitHubIssuesTracker(
                project_root=temp_project_root,
                repo="owner/repo",
                auth_method="gh_cli",
            )

            assert tracker.kind == "github_issues"
            assert tracker.repo == "owner/repo"
            assert (
                tracker.cache_path == temp_project_root / ".ralph" / "github_cache.json"
            )
            mock_create.assert_called_once_with(
                auth_method="gh_cli", token_env="GITHUB_TOKEN"
            )

    def test_init_with_token(self, temp_project_root, sample_issues):
        """Test initialization with token auth."""
        with patch("ralph_gold.trackers.github_issues.create_auth") as mock_create:
            mock_auth = Mock()
            mock_auth.api_call = Mock(return_value=sample_issues)
            mock_create.return_value = mock_auth

            tracker = GitHubIssuesTracker(
                project_root=temp_project_root,
                repo="owner/repo",
                auth_method="token",
                token_env="MY_TOKEN",
            )

            assert tracker.kind == "github_issues"
            mock_create.assert_called_once_with(
                auth_method="token", token_env="MY_TOKEN"
            )

    def test_init_invalid_repo_format(self, temp_project_root):
        """Test initialization fails with invalid repo format."""
        with patch("ralph_gold.trackers.github_issues.create_auth"):
            with pytest.raises(ValueError, match="Invalid repo format"):
                GitHubIssuesTracker(
                    project_root=temp_project_root,
                    repo="invalid-repo",
                )

    def test_init_creates_ralph_dir(self, tmp_path):
        """Test initialization creates .ralph directory if missing."""
        with patch("ralph_gold.trackers.github_issues.create_auth") as mock_create:
            mock_auth = Mock()
            mock_auth.api_call = Mock(return_value=[])
            mock_create.return_value = mock_auth

            tracker = GitHubIssuesTracker(
                project_root=tmp_path,
                repo="owner/repo",
            )

            assert (tmp_path / ".ralph").exists()
            assert tracker.cache_path.exists()


class TestCaching:
    """Tests for cache functionality."""

    def test_cache_is_fresh_no_cache(self, temp_project_root, mock_auth):
        """Test cache_is_fresh returns False when no cache exists."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            # Remove cache to test
            if tracker.cache_path.exists():
                tracker.cache_path.unlink()

            assert tracker._cache_is_fresh() is False

    def test_cache_is_fresh_within_ttl(self, temp_project_root, mock_auth):
        """Test cache_is_fresh returns True when cache is fresh."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(
                temp_project_root, "owner/repo", cache_ttl_seconds=300
            )

            # Cache was just created, should be fresh
            assert tracker._cache_is_fresh() is True

    def test_cache_is_fresh_expired(self, temp_project_root, mock_auth):
        """Test cache_is_fresh returns False when cache is stale."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(
                temp_project_root, "owner/repo", cache_ttl_seconds=1
            )

            # Manually set cache to old timestamp
            cache_data = {
                "cached_at": (datetime.now() - timedelta(seconds=10)).isoformat(),
                "repo": "owner/repo",
                "issues": [],
            }
            with open(tracker.cache_path, "w") as f:
                json.dump(cache_data, f)

            assert tracker._cache_is_fresh() is False

    def test_save_and_load_cache(self, temp_project_root, mock_auth, sample_issues):
        """Test saving and loading cache."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=sample_issues)
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            # Save cache
            tracker._save_cache(sample_issues)

            # Load cache
            loaded = tracker._load_cache()
            assert len(loaded) == 3
            assert loaded[0]["number"] == 1
            assert loaded[1]["number"] == 2

    def test_load_cache_missing_file(self, temp_project_root, mock_auth):
        """Test load_cache returns empty list when file missing."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            # Remove cache
            if tracker.cache_path.exists():
                tracker.cache_path.unlink()

            loaded = tracker._load_cache()
            assert loaded == []

    def test_load_cache_invalid_json(self, temp_project_root, mock_auth):
        """Test load_cache handles invalid JSON gracefully."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            # Write invalid JSON
            with open(tracker.cache_path, "w") as f:
                f.write("invalid json{")

            loaded = tracker._load_cache()
            assert loaded == []


class TestSyncCache:
    """Tests for cache synchronization."""

    def test_sync_cache_fresh_cache_no_api_call(self, temp_project_root, mock_auth):
        """Test sync_cache doesn't call API when cache is fresh."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            # Reset mock to count calls after init
            mock_auth.api_call.reset_mock()

            # Sync with fresh cache
            tracker._sync_cache()

            # Should not call API
            mock_auth.api_call.assert_not_called()

    def test_sync_cache_stale_cache_calls_api(
        self, temp_project_root, mock_auth, sample_issues
    ):
        """Test sync_cache calls API when cache is stale."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=sample_issues)
            tracker = GitHubIssuesTracker(
                temp_project_root, "owner/repo", cache_ttl_seconds=1
            )

            # Make cache stale
            cache_data = {
                "cached_at": (datetime.now() - timedelta(seconds=10)).isoformat(),
                "repo": "owner/repo",
                "issues": [],
            }
            with open(tracker.cache_path, "w") as f:
                json.dump(cache_data, f)

            # Reset mock
            mock_auth.api_call.reset_mock()

            # Sync should call API
            tracker._sync_cache()

            mock_auth.api_call.assert_called_once()
            call_args = mock_auth.api_call.call_args[0]
            assert call_args[0] == "GET"
            assert "/repos/owner/repo/issues" in call_args[1]

    def test_sync_cache_filters_pull_requests(self, temp_project_root, mock_auth):
        """Test sync_cache filters out pull requests."""
        issues_with_pr = [
            {"number": 1, "title": "Issue", "labels": [{"name": "ready"}]},
            {
                "number": 2,
                "title": "PR",
                "labels": [{"name": "ready"}],
                "pull_request": {},
            },
        ]

        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=issues_with_pr)
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            loaded = tracker._load_cache()
            assert len(loaded) == 1
            assert loaded[0]["number"] == 1

    def test_sync_cache_filters_excluded_labels(self, temp_project_root, mock_auth):
        """Test sync_cache filters issues with excluded labels."""
        issues = [
            {"number": 1, "title": "Good", "labels": [{"name": "ready"}]},
            {
                "number": 2,
                "title": "Blocked",
                "labels": [{"name": "ready"}, {"name": "blocked"}],
            },
            {
                "number": 3,
                "title": "Manual",
                "labels": [{"name": "ready"}, {"name": "manual"}],
            },
        ]

        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=issues)
            tracker = GitHubIssuesTracker(
                temp_project_root,
                "owner/repo",
                exclude_labels=["blocked", "manual"],
            )

            loaded = tracker._load_cache()
            assert len(loaded) == 1
            assert loaded[0]["number"] == 1

    def test_sync_cache_handles_api_error_with_cache(
        self, temp_project_root, mock_auth
    ):
        """Test sync_cache uses stale cache when API fails."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            # Initial sync succeeds
            mock_auth.api_call = Mock(return_value=[{"number": 1, "title": "Test"}])
            tracker = GitHubIssuesTracker(
                temp_project_root, "owner/repo", cache_ttl_seconds=1
            )

            # Make cache stale
            cache_data = {
                "cached_at": (datetime.now() - timedelta(seconds=10)).isoformat(),
                "repo": "owner/repo",
                "issues": [{"number": 1, "title": "Cached"}],
            }
            with open(tracker.cache_path, "w") as f:
                json.dump(cache_data, f)

            # API fails on next sync
            mock_auth.api_call = Mock(side_effect=GitHubAuthError("API error"))

            # Should not raise, uses cached data
            tracker._sync_cache()
            loaded = tracker._load_cache()
            assert len(loaded) == 1
            assert loaded[0]["title"] == "Cached"

    def test_sync_cache_handles_api_error_no_cache(self, temp_project_root, mock_auth):
        """Test sync_cache raises error when API fails and no cache."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(side_effect=GitHubAuthError("API error"))

            with pytest.raises(GitHubAuthError):
                GitHubIssuesTracker(temp_project_root, "owner/repo")


class TestParallelGroups:
    """Tests for parallel group extraction."""

    def test_extract_group_from_labels(self, temp_project_root, mock_auth):
        """Test extracting group from labels."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            # Test with group label
            labels = [{"name": "ready"}, {"name": "group:auth"}]
            assert tracker._extract_group_from_labels(labels) == "auth"

            # Test without group label
            labels = [{"name": "ready"}, {"name": "bug"}]
            assert tracker._extract_group_from_labels(labels) == "default"

            # Test with multiple group labels (first wins)
            labels = [{"name": "group:auth"}, {"name": "group:ui"}]
            assert tracker._extract_group_from_labels(labels) == "auth"

    def test_extract_group_case_insensitive(self, temp_project_root, mock_auth):
        """Test group extraction is case-insensitive."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            labels = [{"name": "GROUP:Auth"}]
            assert tracker._extract_group_from_labels(labels) == "Auth"

    def test_get_parallel_groups(self, temp_project_root, mock_auth, sample_issues):
        """Test get_parallel_groups groups issues correctly."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=sample_issues)
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            groups = tracker.get_parallel_groups()

            assert "auth" in groups
            assert "ui" in groups
            assert "default" in groups

            assert len(groups["auth"]) == 1
            assert len(groups["ui"]) == 1
            assert len(groups["default"]) == 1

            assert groups["auth"][0].id == "1"
            assert groups["ui"][0].id == "2"
            assert groups["default"][0].id == "3"

    def test_get_parallel_groups_empty(self, temp_project_root, mock_auth):
        """Test get_parallel_groups with no issues."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            groups = tracker.get_parallel_groups()
            assert groups == {}


class TestAcceptanceCriteria:
    """Tests for acceptance criteria parsing."""

    def test_parse_acceptance_criteria(self, temp_project_root, mock_auth):
        """Test parsing acceptance criteria from issue body."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            body = """## Description
Add authentication

## Acceptance Criteria
- [ ] User can log in
- [x] Token is returned
- [ ] Password is hashed

## Notes
Use bcrypt"""

            criteria = tracker._parse_acceptance_criteria(body)
            assert len(criteria) == 3
            assert "User can log in" in criteria
            assert "Token is returned" in criteria
            assert "Password is hashed" in criteria

    def test_parse_acceptance_criteria_no_section(self, temp_project_root, mock_auth):
        """Test parsing when no acceptance criteria section."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            body = "Just a description"
            criteria = tracker._parse_acceptance_criteria(body)
            assert criteria == []

    def test_parse_acceptance_criteria_empty_body(self, temp_project_root, mock_auth):
        """Test parsing with empty body."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            criteria = tracker._parse_acceptance_criteria("")
            assert criteria == []

            criteria = tracker._parse_acceptance_criteria(None)
            assert criteria == []

    def test_parse_acceptance_criteria_case_insensitive(
        self, temp_project_root, mock_auth
    ):
        """Test parsing is case-insensitive."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            body = """## ACCEPTANCE CRITERIA
- [ ] Test item"""

            criteria = tracker._parse_acceptance_criteria(body)
            assert len(criteria) == 1
            assert "Test item" in criteria


class TestIssueToTask:
    """Tests for issue to task conversion."""

    def test_issue_to_task(self, temp_project_root, mock_auth):
        """Test converting issue to SelectedTask."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            issue = {
                "number": 42,
                "title": "Test Issue",
                "body": "## Acceptance Criteria\n- [ ] Test item",
            }

            task = tracker._issue_to_task(issue)
            assert task.id == "42"
            assert task.title == "Test Issue"
            assert task.kind == "github_issues"
            assert len(task.acceptance) == 1
            assert "Test item" in task.acceptance

    def test_issue_to_task_no_body(self, temp_project_root, mock_auth):
        """Test converting issue without body."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            issue = {"number": 42, "title": "Test Issue"}

            task = tracker._issue_to_task(issue)
            assert task.id == "42"
            assert task.title == "Test Issue"
            assert task.acceptance == []


class TestPrioritySorting:
    """Tests for priority sorting."""

    def test_sort_issues_by_milestone(self, temp_project_root, mock_auth):
        """Test issues sorted by milestone number."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            issues = [
                {
                    "number": 1,
                    "milestone": {"number": 3},
                    "created_at": "2024-01-15T10:00:00Z",
                },
                {
                    "number": 2,
                    "milestone": {"number": 1},
                    "created_at": "2024-01-15T10:00:00Z",
                },
                {
                    "number": 3,
                    "milestone": {"number": 2},
                    "created_at": "2024-01-15T10:00:00Z",
                },
            ]

            sorted_issues = tracker._sort_issues_by_priority(issues)
            assert sorted_issues[0]["number"] == 2  # milestone 1
            assert sorted_issues[1]["number"] == 3  # milestone 2
            assert sorted_issues[2]["number"] == 1  # milestone 3

    def test_sort_issues_by_created_date(self, temp_project_root, mock_auth):
        """Test issues sorted by created date when no milestone."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            issues = [
                {"number": 1, "milestone": None, "created_at": "2024-01-15T12:00:00Z"},
                {"number": 2, "milestone": None, "created_at": "2024-01-15T10:00:00Z"},
                {"number": 3, "milestone": None, "created_at": "2024-01-15T11:00:00Z"},
            ]

            sorted_issues = tracker._sort_issues_by_priority(issues)
            assert sorted_issues[0]["number"] == 2  # oldest
            assert sorted_issues[1]["number"] == 3
            assert sorted_issues[2]["number"] == 1  # newest

    def test_sort_issues_milestone_then_date(self, temp_project_root, mock_auth):
        """Test issues sorted by milestone, then date."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            issues = [
                {
                    "number": 1,
                    "milestone": {"number": 1},
                    "created_at": "2024-01-15T12:00:00Z",
                },
                {"number": 2, "milestone": None, "created_at": "2024-01-15T10:00:00Z"},
                {
                    "number": 3,
                    "milestone": {"number": 1},
                    "created_at": "2024-01-15T10:00:00Z",
                },
            ]

            sorted_issues = tracker._sort_issues_by_priority(issues)
            assert sorted_issues[0]["number"] == 3  # milestone 1, older
            assert sorted_issues[1]["number"] == 1  # milestone 1, newer
            assert sorted_issues[2]["number"] == 2  # no milestone


class TestTrackerProtocol:
    """Tests for Tracker protocol methods."""

    def test_peek_next_task(self, temp_project_root, mock_auth, sample_issues):
        """Test peek_next_task returns highest priority issue."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=sample_issues)
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            task = tracker.peek_next_task()
            assert task is not None
            # Issue 1 has milestone 1 and older date than issue 2
            assert task.id == "1"

    def test_peek_next_task_no_issues(self, temp_project_root, mock_auth):
        """Test peek_next_task returns None when no issues."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            task = tracker.peek_next_task()
            assert task is None

    def test_claim_next_task(self, temp_project_root, mock_auth, sample_issues):
        """Test claim_next_task returns same as peek."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=sample_issues)
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            peeked = tracker.peek_next_task()
            claimed = tracker.claim_next_task()

            assert peeked is not None
            assert claimed is not None
            assert peeked.id == claimed.id

    def test_counts(self, temp_project_root, mock_auth, sample_issues):
        """Test counts returns correct values."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=sample_issues)
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            completed, total = tracker.counts()
            assert completed == 0  # GitHub tracker doesn't track completed
            assert total == 3

    def test_all_done(self, temp_project_root, mock_auth):
        """Test all_done returns True when no issues."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            assert tracker.all_done() is True

    def test_all_done_with_issues(self, temp_project_root, mock_auth, sample_issues):
        """Test all_done returns False when issues exist."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=sample_issues)
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            assert tracker.all_done() is False

    def test_is_task_done_open_issue(self, temp_project_root, mock_auth, sample_issues):
        """Test is_task_done returns False for open issue."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=sample_issues)
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            assert tracker.is_task_done("1") is False
            assert tracker.is_task_done("2") is False

    def test_is_task_done_closed_issue(
        self, temp_project_root, mock_auth, sample_issues
    ):
        """Test is_task_done returns True for closed issue (not in cache)."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=sample_issues)
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            # Issue not in cache is considered closed
            assert tracker.is_task_done("999") is True

    def test_force_task_open_not_implemented(self, temp_project_root, mock_auth):
        """Test force_task_open returns False (not implemented)."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            result = tracker.force_task_open("1")
            assert result is False

    def test_branch_name_returns_none(self, temp_project_root, mock_auth):
        """Test branch_name returns None."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            assert tracker.branch_name() is None


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_label_filter(self, temp_project_root, mock_auth, sample_issues):
        """Test tracker works with empty label filter."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=sample_issues)
            tracker = GitHubIssuesTracker(
                temp_project_root, "owner/repo", label_filter=""
            )

            # Should still work
            task = tracker.peek_next_task()
            assert task is not None

    def test_issue_without_labels(self, temp_project_root, mock_auth):
        """Test handling issue without labels field."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            issues = [
                {"number": 1, "title": "Test", "created_at": "2024-01-15T10:00:00Z"}
            ]
            mock_auth.api_call = Mock(return_value=issues)
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            groups = tracker.get_parallel_groups()
            assert "default" in groups
            assert len(groups["default"]) == 1

    def test_issue_with_string_labels(self, temp_project_root, mock_auth):
        """Test handling labels as strings instead of dicts."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            issues = [
                {
                    "number": 1,
                    "title": "Test",
                    "labels": ["ready", "group:auth"],
                    "created_at": "2024-01-15T10:00:00Z",
                }
            ]
            mock_auth.api_call = Mock(return_value=issues)
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            groups = tracker.get_parallel_groups()
            assert "auth" in groups

    def test_api_returns_non_list(self, temp_project_root, mock_auth):
        """Test handling when API returns non-list."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value={"error": "something"})
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            # Should handle gracefully
            task = tracker.peek_next_task()
            assert task is None

    def test_custom_cache_ttl(self, temp_project_root, mock_auth):
        """Test custom cache TTL."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(
                temp_project_root, "owner/repo", cache_ttl_seconds=600
            )

            assert tracker.cache_ttl_seconds == 600

    def test_custom_exclude_labels(self, temp_project_root, mock_auth):
        """Test custom exclude labels."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(
                temp_project_root,
                "owner/repo",
                exclude_labels=["wontfix", "duplicate"],
            )

            assert "wontfix" in tracker.exclude_labels
            assert "duplicate" in tracker.exclude_labels


class TestMarkTaskDone:
    """Tests for mark_task_done functionality."""

    def test_mark_task_done_close_only(self, temp_project_root, mock_auth):
        """Test marking task done with only issue closing."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            # Reset mock to track calls
            mock_auth.api_call.reset_mock()

            # Mark task done with only closing
            result = tracker.mark_task_done("42", close_issue=True, add_comment=False)

            assert result is True
            # Should have called PATCH to close issue
            assert mock_auth.api_call.call_count == 1
            call_args = mock_auth.api_call.call_args[0]
            assert call_args[0] == "PATCH"
            assert "/repos/owner/repo/issues/42" in call_args[1]

    def test_mark_task_done_with_comment(self, temp_project_root, mock_auth):
        """Test marking task done with comment."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            mock_auth.api_call.reset_mock()

            # Mark task done with comment
            result = tracker.mark_task_done("42", close_issue=True, add_comment=True)

            assert result is True
            # Should have called PATCH (close) and POST (comment)
            assert mock_auth.api_call.call_count == 2

            # Check close call
            close_call = mock_auth.api_call.call_args_list[0]
            assert close_call[0][0] == "PATCH"
            assert "/repos/owner/repo/issues/42" in close_call[0][1]

            # Check comment call
            comment_call = mock_auth.api_call.call_args_list[1]
            assert comment_call[0][0] == "POST"
            assert "/repos/owner/repo/issues/42/comments" in comment_call[0][1]

    def test_mark_task_done_custom_comment(self, temp_project_root, mock_auth):
        """Test marking task done with custom comment."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            mock_auth.api_call.reset_mock()

            custom_comment = "Custom completion message"
            result = tracker.mark_task_done(
                "42",
                close_issue=False,
                add_comment=True,
                comment_body=custom_comment,
            )

            assert result is True
            # Should have called POST for comment
            assert mock_auth.api_call.call_count == 1
            call_args = mock_auth.api_call.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][2]["body"] == custom_comment

    def test_mark_task_done_with_commit_sha(self, temp_project_root, mock_auth):
        """Test marking task done with commit SHA."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            mock_auth.api_call.reset_mock()

            result = tracker.mark_task_done(
                "42",
                close_issue=False,
                add_comment=True,
                commit_sha="abc123def456",
            )

            assert result is True
            # Check that comment includes commit SHA
            call_args = mock_auth.api_call.call_args
            comment_body = call_args[0][2]["body"]
            assert "abc123def456" in comment_body

    def test_mark_task_done_add_labels(self, temp_project_root, mock_auth):
        """Test marking task done with adding labels."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            mock_auth.api_call.reset_mock()

            result = tracker.mark_task_done(
                "42",
                close_issue=False,
                add_comment=False,
                add_labels=["completed", "verified"],
            )

            assert result is True
            # Should have called POST to add labels
            assert mock_auth.api_call.call_count == 1
            call_args = mock_auth.api_call.call_args
            assert call_args[0][0] == "POST"
            assert "/repos/owner/repo/issues/42/labels" in call_args[0][1]
            assert call_args[0][2]["labels"] == ["completed", "verified"]

    def test_mark_task_done_remove_labels(self, temp_project_root, mock_auth):
        """Test marking task done with removing labels."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            mock_auth.api_call.reset_mock()

            result = tracker.mark_task_done(
                "42",
                close_issue=False,
                add_comment=False,
                remove_labels=["in-progress", "ready"],
            )

            assert result is True
            # Should have called DELETE for each label
            assert mock_auth.api_call.call_count == 2

            # Check both DELETE calls
            for i, label in enumerate(["in-progress", "ready"]):
                call = mock_auth.api_call.call_args_list[i]
                assert call[0][0] == "DELETE"
                assert f"/repos/owner/repo/issues/42/labels/{label}" in call[0][1]

    def test_mark_task_done_all_operations(self, temp_project_root, mock_auth):
        """Test marking task done with all operations."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            mock_auth.api_call.reset_mock()

            result = tracker.mark_task_done(
                "42",
                close_issue=True,
                add_comment=True,
                commit_sha="abc123",
                add_labels=["completed"],
                remove_labels=["in-progress"],
            )

            assert result is True
            # Should have: PATCH (close), POST (comment), POST (add labels), DELETE (remove label)
            assert mock_auth.api_call.call_count == 4

    def test_mark_task_done_api_failure_close(self, temp_project_root, mock_auth):
        """Test mark_task_done handles API failure gracefully."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            # Make API call fail
            mock_auth.api_call = Mock(side_effect=GitHubAuthError("API error"))

            result = tracker.mark_task_done("42", close_issue=True, add_comment=False)

            # Should return False but not crash
            assert result is False

    def test_mark_task_done_partial_failure(self, temp_project_root, mock_auth):
        """Test mark_task_done continues on partial failure."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            # Make only the comment call fail
            def api_call_side_effect(method, endpoint, data=None):
                if "comments" in endpoint:
                    raise GitHubAuthError("Comment failed")
                return {}

            mock_auth.api_call = Mock(side_effect=api_call_side_effect)

            result = tracker.mark_task_done("42", close_issue=True, add_comment=True)

            # Should return False due to comment failure
            assert result is False
            # But should have attempted both operations
            assert mock_auth.api_call.call_count == 2

    def test_mark_task_done_invalidates_cache(self, temp_project_root, mock_auth):
        """Test mark_task_done invalidates cache on success."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            # Ensure cache exists and is fresh
            assert tracker._cache_is_fresh() is True

            mock_auth.api_call.reset_mock()

            # Mark task done
            tracker.mark_task_done("42", close_issue=True, add_comment=False)

            # Cache should now be stale
            assert tracker._cache_is_fresh() is False

    def test_mark_task_done_logs_api_calls(self, temp_project_root, mock_auth):
        """Test mark_task_done logs API calls."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            mock_auth.api_call.reset_mock()

            # Mark task done
            tracker.mark_task_done("42", close_issue=True, add_comment=True)

            # Check that log file was created
            log_path = temp_project_root / ".ralph" / "logs" / "github-api.log"
            assert log_path.exists()

            # Check log contents
            with open(log_path, "r") as f:
                log_content = f.read()

            assert "Closing issue #42" in log_content
            assert "Adding comment to issue #42" in log_content
            assert "Successfully closed issue #42" in log_content
            assert "Successfully added comment to issue #42" in log_content

    def test_mark_task_done_logs_failures(self, temp_project_root, mock_auth):
        """Test mark_task_done logs failures."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            # Make API call fail
            mock_auth.api_call = Mock(side_effect=GitHubAuthError("API error"))

            # Mark task done
            tracker.mark_task_done("42", close_issue=True, add_comment=False)

            # Check log for error
            log_path = temp_project_root / ".ralph" / "logs" / "github-api.log"
            with open(log_path, "r") as f:
                log_content = f.read()

            assert "ERROR" in log_content
            assert "Failed to close issue #42" in log_content

    def test_generate_completion_comment_no_sha(self, temp_project_root, mock_auth):
        """Test generating completion comment without commit SHA."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            comment = tracker._generate_completion_comment()

            assert "✅ Task completed by ralph-gold" in comment
            assert "Completed at:" in comment
            assert "Commit:" not in comment

    def test_generate_completion_comment_with_sha(self, temp_project_root, mock_auth):
        """Test generating completion comment with commit SHA."""
        with patch(
            "ralph_gold.trackers.github_issues.create_auth", return_value=mock_auth
        ):
            mock_auth.api_call = Mock(return_value=[])
            tracker = GitHubIssuesTracker(temp_project_root, "owner/repo")

            comment = tracker._generate_completion_comment(commit_sha="abc123def456")

            assert "✅ Task completed by ralph-gold" in comment
            assert "Completed at:" in comment
            assert "abc123def456" in comment
