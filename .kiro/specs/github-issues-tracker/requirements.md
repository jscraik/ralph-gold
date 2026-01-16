# GitHub Issues Tracker - Requirements

## Overview

Add GitHub Issues as a first-class task tracker backend, enabling ralph-gold to work with real team workflows where tasks are managed as issues.

## User Stories

### 1. As a developer, I want Ralph to read tasks from GitHub Issues

**So that** I can use my existing issue tracker instead of maintaining a separate PRD file.

**Acceptance Criteria:**

- Ralph can authenticate with GitHub (via gh CLI or token)
- Ralph can list issues from a specified repo
- Ralph can filter issues by label (e.g., "ready", "ralph")
- Ralph can read issue title, body, and labels
- Ralph treats issue number as task ID
- Ralph treats issue title as task title
- Ralph treats issue body as task description/acceptance criteria

### 2. As a developer, I want Ralph to update issue status automatically

**So that** my issue tracker stays in sync with Ralph's progress.

**Acceptance Criteria:**

- Ralph can close issues when tasks complete
- Ralph can add comments to issues with iteration results
- Ralph can add labels to issues (e.g., "in-progress", "completed")
- Ralph can link commits/branches to issues
- Updates only happen when gates pass
- Failed iterations don't close issues

### 3. As a developer, I want to control which issues Ralph works on

**So that** Ralph doesn't pick up issues that aren't ready.

**Acceptance Criteria:**

- Issues must have a specific label to be eligible (configurable)
- Issues can be excluded by label (e.g., "blocked", "manual")
- Issues can be prioritized by label or milestone
- Closed issues are never selected
- Draft issues can be optionally excluded

### 4. As a developer, I want Ralph to respect GitHub rate limits

**So that** I don't get throttled or banned.

**Acceptance Criteria:**

- Ralph caches issue data locally
- Ralph only fetches updates when needed
- Ralph respects GitHub's rate limit headers
- Ralph backs off when approaching rate limits
- Ralph works offline with cached data

### 5. As a developer, I want to use gh CLI or API tokens

**So that** I can choose the auth method that fits my workflow.

**Acceptance Criteria:**

- gh CLI is the default (if available)
- API token is supported as fallback
- Token can be provided via env var or config
- Auth failures are clearly reported
- Ralph suggests installing gh CLI if missing

## Configuration Schema

```toml
[tracker]
kind = "github_issues"

[tracker.github]
repo = "owner/repo"              # required
auth_method = "gh_cli"           # gh_cli|token
token_env = "GITHUB_TOKEN"       # for token auth
label_filter = "ready"           # issues must have this label
exclude_labels = ["blocked", "manual"]
close_on_done = true
comment_on_done = true
add_labels_on_start = ["in-progress"]
add_labels_on_done = ["completed"]
cache_ttl_seconds = 300
```

## Issue Body Format

Ralph should parse issue bodies for structured acceptance criteria:

```markdown
## Description
Implement user authentication with JWT tokens.

## Acceptance Criteria
- [ ] User can log in with email/password
- [ ] JWT token is returned on successful login
- [ ] Token expires after 24 hours
- [ ] Invalid credentials return 401

## Notes
Use bcrypt for password hashing.
```

Ralph extracts:

- Description: everything before "## Acceptance Criteria"
- Acceptance: checkbox items under "## Acceptance Criteria"
- Notes: everything after acceptance criteria

## CLI Interface

```bash
# Use GitHub Issues tracker
ralph run --tracker github_issues

# List available issues
ralph issues list

# Show issue details
ralph issues show 123

# Sync issue cache
ralph issues sync

# Test GitHub auth
ralph doctor --check-github
```

## Tracker Interface Extension

Extend the existing `Tracker` interface:

```python
class GitHubIssuesTracker(Tracker):
    def __init__(self, project_root: Path, cfg: Config):
        self.repo = cfg.tracker.github.repo
        self.auth = self._setup_auth(cfg)
        self.cache = self._load_cache()
    
    def claim_next_task(self) -> Optional[SelectedTask]:
        # Fetch open issues with label_filter
        # Return highest priority issue
        pass
    
    def is_task_done(self, task_id: str) -> bool:
        # Check if issue is closed
        pass
    
    def force_task_open(self, task_id: str) -> None:
        # Reopen issue, remove "completed" label
        pass
    
    def mark_task_done(self, task_id: str, comment: str) -> None:
        # Close issue, add comment, add labels
        pass
```

## Non-Functional Requirements

### Performance

- Issue list should cache for 5 minutes by default
- Initial sync should complete in < 10 seconds for 100 issues
- Updates should be batched to minimize API calls

### Reliability

- Network failures should not crash Ralph
- Partial updates should be atomic (all or nothing)
- Cache should survive process restarts

### Security

- Tokens should never be logged
- Tokens should be stored securely (keychain on macOS)
- gh CLI auth is preferred (more secure)

### Observability

- All GitHub API calls logged to .ralph/logs/github-api.log
- Rate limit status visible in ralph status
- Auth failures clearly reported with remediation steps

## Out of Scope (for v0.7.0)

- GitHub Projects integration
- GitHub Discussions integration
- Issue creation from Ralph
- Automatic PR linking (defer to PR automation feature)
- Multi-repo support

## Dependencies

- gh CLI (optional but recommended)
- requests library for API calls
- GitHub personal access token (if not using gh CLI)

## Success Metrics

- Ralph can successfully read and update issues in 100% of test cases
- Zero auth failures with properly configured gh CLI
- Issue updates complete within 2 seconds of task completion
- Cache reduces API calls by 90% during normal operation
