# Ralph-Gold v0.7.0: Parallel Execution + GitHub Issues - Requirements

## Overview

v0.7.0 adds three integrated features that enable ralph-gold to work on multiple tasks concurrently with real team workflows:

1. **Parallel execution with git worktrees** - Execute 3-5 independent tasks concurrently with full isolation
2. **GitHub Issues tracker** - Use GitHub Issues as the task source, eliminating manual PRD maintenance
3. **YAML tracker** - Machine-editable format with native parallel grouping support

These features work together: YAML and GitHub Issues provide parallel grouping metadata, while the parallel execution engine uses that metadata to safely run tasks concurrently in isolated git worktrees.

## User Stories

### 1. As a developer, I want Ralph to execute multiple independent tasks in parallel

**So that** my development loop converges 3-5x faster when I have parallelizable work.

**Acceptance Criteria:**

- Ralph can run N tasks concurrently (configurable max_workers)
- Each task runs in an isolated git worktree with its own branch
- Tasks are grouped to prevent conflicts (same group = sequential, different groups = parallel)
- Failed tasks don't affect successful tasks
- I can see real-time status of all parallel workers in the TUI
- Parallel mode is opt-in and disabled by default
- Successful tasks can be auto-merged or kept for manual review
- All worker state is preserved in logs for debugging

### 2. As a developer, I want Ralph to read tasks from GitHub Issues

**So that** I can use my existing issue tracker instead of maintaining a separate PRD file.

**Acceptance Criteria:**

- Ralph can authenticate with GitHub via gh CLI or API token
- Ralph can list issues from a specified repo with label filtering
- Ralph can read issue title, body, and labels as task metadata
- Ralph can close issues and add comments when tasks complete
- Ralph can add/remove labels to track task status
- Ralph respects GitHub rate limits with local caching
- Ralph works offline with cached issue data
- Issue updates only happen when gates pass

### 3. As a developer, I want to use YAML for task tracking with parallel grouping

**So that** I get structured, machine-editable tasks with first-class parallel support.

**Acceptance Criteria:**

- Ralph can read tasks from tasks.yaml
- YAML format supports all fields that JSON supports
- Tasks can declare a "group" field for parallel scheduling
- YAML format validates on load with clear error messages
- YAML format supports comments for documentation
- Migration tool can convert JSON/Markdown to YAML
- `ralph init --format yaml` creates a valid tasks.yaml

### 4. As a developer, I want parallel execution to be safe by default

**So that** I don't accidentally create merge conflicts or corrupt my repo.

**Acceptance Criteria:**

- Parallel mode is opt-in (disabled by default)
- Worktrees are isolated under .ralph/worktrees/
- Each worktree gets a unique branch name
- Failed worktrees are preserved for debugging
- Main worktree is never modified during parallel execution
- Merge conflicts are detected and reported
- Merge policy is configurable (manual|auto_merge)

### 5. As a developer, I want to control which tasks can run in parallel

**So that** I avoid merge conflicts and wasted work on dependent tasks.

**Acceptance Criteria:**

- Tasks can be tagged with a "group" identifier (in YAML, JSON, or GitHub labels)
- Tasks in the same group run sequentially
- Tasks in different groups can run in parallel
- Default behavior is sequential (all tasks in "default" group)
- I can opt-in to parallel mode per-project via config

### 6. As a developer, I want to see what each parallel worker is doing

**So that** I can monitor progress and debug failures.

**Acceptance Criteria:**

- TUI shows status of all workers in real-time
- Each worker displays: task_id, status, branch, duration, gates_status
- Failed workers show error summary
- Logs are isolated per worker
- I can inspect any worker's full log
- Status updates refresh at least every 2 seconds

### 7. As a developer, I want Ralph to respect GitHub rate limits

**So that** I don't get throttled or banned.

**Acceptance Criteria:**

- Ralph caches issue data locally with configurable TTL
- Ralph only fetches updates when cache is stale
- Ralph respects GitHub's rate limit headers
- Ralph backs off when approaching rate limits
- Ralph works offline with cached data
- Cache reduces API calls by 90%+ during normal operation

### 8. As a developer, I want to migrate existing PRDs to YAML

**So that** I can adopt the new format without manual rewriting.

**Acceptance Criteria:**

- `ralph convert` can convert JSON to YAML
- `ralph convert` can convert Markdown to YAML
- Conversion is lossless (round-trip test passes)
- Generated YAML is valid and readable
- Conversion can optionally infer parallel groups from task structure

### 9. As a developer, I want lifecycle hooks to run custom scripts around the loop

**So that** I can integrate Ralph with my existing workflows (sync tasks, notifications, cleanup, etc.).

**Acceptance Criteria:**

- Hooks can be defined in `.ralph/ralph.toml` under `[hooks]`
- Hooks support: `pre_run`, `start_iteration`, `end_iteration`, `on_gate_fail`
- Each hook can run multiple commands in sequence
- Hooks can be specified via CLI flags (e.g., `--pre-run "cmd"`)
- Hook failures are logged but don't crash the loop
- Hooks have access to loop context (iteration number, task ID, etc.)
- Hooks are distinct from gates (gates block, hooks augment)

### 10. As a developer, I want Ralph to run until all tasks are complete

**So that** I don't have to guess the right max_iterations value.

**Acceptance Criteria:**

- `ralph run --until-done` runs while tracker has open tasks
- Loop exits when tracker returns no more tasks
- Manual stop (Ctrl+C) still works
- Timeouts still work as safety mechanism
- Gates still block progress on failures
- `--until-done` is the default when a tracker exists and max_iterations isn't set
- Loop runs at least once (do-while semantics)

### 11. As a developer, I want session management for resumable loops

**So that** I can resume interrupted loops and audit past runs.

**Acceptance Criteria:**

- Each `ralph run` creates a unique session ID
- Session logs are isolated under `.ralph/sessions/<session_id>/`
- Session state is tracked separately from global state
- `ralph session list` shows all sessions
- `ralph session show <id>` displays session details
- `ralph run --session <id>` resumes a specific session
- `ralph run --continue` resumes the most recent session
- Sessions track: start time, end time, iterations, tasks completed, gates status

### 12. As a developer, I want to inject feedback during a running loop

**So that** I can correct course without stopping and restarting.

**Acceptance Criteria:**

- `ralph feedback "text"` appends feedback to `.ralph/feedback.ndjson`
- Orchestrator includes recent feedback in next iteration prompt
- `ralph feedback --task <id>` attaches feedback to a specific task
- Feedback is timestamped and attributed
- Feedback can be viewed with `ralph feedback list`
- Feedback can be cleared with `ralph feedback clear`
- Feedback survives loop restarts

## Configuration Schema

### Parallel Execution Configuration

```toml
[parallel]
enabled = false              # opt-in, disabled by default
max_workers = 3              # concurrent agents
worktree_root = ".ralph/worktrees"
strategy = "queue"           # queue|group
merge_policy = "manual"      # manual|auto_merge|pr

[parallel.conflict_resolution]
strategy = "stop"            # stop|ai_resolve (ai_resolve deferred to v0.8.0)
```

### Lifecycle Hooks Configuration

```toml
[hooks]
# Run before loop starts (sync tasks, setup environment)
pre_run = [
    "./scripts/sync_tasks.sh",
    "./scripts/check_deps.sh"
]

# Run at the start of each iteration (cleanup, diagnostics)
start_iteration = [
    "./scripts/clean_temp.sh",
    "./scripts/print_env.sh"
]

# Run at the end of each iteration (summaries, notifications)
end_iteration = [
    "./scripts/post_summary.sh",
    "./scripts/notify_slack.sh"
]

# Run when gates fail (collect debug info)
on_gate_fail = [
    "./scripts/collect_debug.sh",
    "./scripts/snapshot_state.sh"
]

# Hook execution settings
[hooks.settings]
timeout_seconds = 30         # per-hook timeout
continue_on_error = true     # don't crash loop on hook failure
log_output = true            # log hook stdout/stderr
```

### Loop Control Configuration

```toml
[loop]
max_iterations = 10          # max iterations (optional)
until_done = false           # run until tracker is empty (overrides max_iterations)
timeout_minutes = 120        # safety timeout
exit_on_no_progress = true   # exit if no progress for N iterations
```

### Session Management Configuration

```toml
[session]
enabled = true               # enable session tracking
auto_continue = false        # auto-resume last session on `ralph run`
retention_days = 30          # delete sessions older than this
log_level = "info"           # session log verbosity
```

### Feedback Configuration

```toml
[feedback]
enabled = true               # enable feedback channel
max_items = 10               # max feedback items to include in prompt
format = "ndjson"            # ndjson|markdown
file = ".ralph/feedback.ndjson"
```

### GitHub Issues Tracker Configuration

```toml
[tracker]
kind = "github_issues"       # auto|markdown|json|yaml|github_issues

[tracker.github]
repo = "owner/repo"          # required
auth_method = "gh_cli"       # gh_cli|token
token_env = "GITHUB_TOKEN"   # for token auth
label_filter = "ready"       # issues must have this label
exclude_labels = ["blocked", "manual"]
close_on_done = true
comment_on_done = true
add_labels_on_start = ["in-progress"]
add_labels_on_done = ["completed"]
cache_ttl_seconds = 300      # 5 minutes
```

### YAML Tracker Configuration

```toml
[files]
prd = "tasks.yaml"           # or .ralph/tasks.yaml

[tracker]
kind = "yaml"                # or "auto" to detect
```

### YAML Task Format

```yaml
# tasks.yaml
version: 1
metadata:
  project: my-project
  created: 2024-01-15

tasks:
  - id: 1
    title: Implement user authentication
    description: Add JWT-based authentication
    group: auth              # parallel group identifier
    priority: 1
    completed: false
    acceptance:
      - User can log in with email/password
      - JWT token is returned on successful login
    
  - id: 2
    title: Create user profile UI
    group: ui                # different group = can run in parallel
    priority: 2
    completed: false
    acceptance:
      - Profile page displays user info
      - User can edit profile fields
```

### GitHub Issue Body Format

Ralph parses issue bodies for structured acceptance criteria:

```markdown
## Description
Implement user authentication with JWT tokens.

## Acceptance Criteria
- [ ] User can log in with email/password
- [ ] JWT token is returned on successful login
- [ ] Token expires after 24 hours

## Notes
Use bcrypt for password hashing.
```

Ralph extracts:

- Description: everything before "## Acceptance Criteria"
- Acceptance: checkbox items under "## Acceptance Criteria"
- Notes: everything after acceptance criteria
- Group: from issue labels (e.g., "group:auth")

## CLI Interface

### Parallel Execution Commands

```bash
# Run in parallel mode
ralph run --parallel --max-workers 4

# Dry-run to see what would run in parallel
ralph run --parallel --dry-run

# Show parallel status
ralph status --parallel

# List active worktrees
ralph parallel list

# Clean up worktrees
ralph parallel clean

# Show parallel worker status
ralph parallel status
```

### GitHub Issues Commands

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

### YAML Tracker Commands

```bash
# Initialize with YAML
ralph init --format yaml

# Convert existing PRD to YAML
ralph convert prd.json tasks.yaml
ralph convert PRD.md tasks.yaml

# Validate YAML
ralph validate tasks.yaml

# Show parallel groups
ralph tasks groups
```

### Combined Workflows

```bash
# Parallel execution with GitHub Issues
ralph run --parallel --tracker github_issues --max-workers 3

# Parallel execution with YAML
ralph run --parallel --max-workers 4

# Sequential execution with GitHub Issues (default)
ralph run --tracker github_issues
```

### Lifecycle Hooks Commands

```bash
# Run with pre-run hook
ralph run --pre-run "./scripts/sync_tasks.sh"

# Run with multiple pre-run commands (repeatable)
ralph run --pre-run "cmd1" --pre-run "cmd2"

# Run with named hook from config
ralph run --pre-run-hook sync_and_check

# Run until all tasks are done
ralph run --until-done

# Run until done with timeout
ralph run --until-done --timeout 120
```

### Session Management Commands

```bash
# List all sessions
ralph session list

# Show session details
ralph session show <session_id>

# Resume a specific session
ralph run --session <session_id>

# Continue the most recent session
ralph run --continue

# Clean up old sessions
ralph session clean --older-than 30d
```

### Feedback Commands

```bash
# Add feedback during a running loop
ralph feedback "Don't change the public API"

# Add feedback for a specific task
ralph feedback --task 5 "This task needs more error handling"

# List recent feedback
ralph feedback list

# Clear all feedback
ralph feedback clear

# Clear feedback for a specific task
ralph feedback clear --task 5
```

## Tracker Interface Extension

All three trackers (YAML, GitHub Issues, and existing JSON/Markdown) implement the extended `Tracker` interface:

```python
class Tracker(ABC):
    """Base tracker interface."""
    
    @abstractmethod
    def claim_next_task(self) -> Optional[SelectedTask]:
        """Claim the next available task."""
        pass
    
    @abstractmethod
    def is_task_done(self, task_id: str) -> bool:
        """Check if a task is marked done."""
        pass
    
    # NEW: Parallel support
    def get_parallel_groups(self) -> dict[str, list[SelectedTask]]:
        """Return tasks grouped by parallel group.
        
        Default: all tasks in "default" group (sequential).
        Trackers that support grouping override this.
        """
        return {"default": self.get_all_tasks()}
    
    def get_all_tasks(self) -> list[SelectedTask]:
        """Return all tasks (for parallel scheduling)."""
        raise NotImplementedError("Parallel mode requires get_all_tasks()")
```

### YamlTracker Implementation

```python
class YamlTracker(Tracker):
    def get_parallel_groups(self) -> dict[str, list[SelectedTask]]:
        """Group tasks by 'group' field."""
        groups: dict[str, list[SelectedTask]] = {}
        for task_data in self.data["tasks"]:
            if task_data.get("completed"):
                continue
            group = str(task_data.get("group", "default"))
            task = self._task_from_data(task_data)
            groups.setdefault(group, []).append(task)
        return groups
```

### GitHubIssuesTracker Implementation

```python
class GitHubIssuesTracker(Tracker):
    def get_parallel_groups(self) -> dict[str, list[SelectedTask]]:
        """Group tasks by 'group:*' labels."""
        groups: dict[str, list[SelectedTask]] = {}
        for issue in self._load_cache():
            if issue.get("state") == "closed":
                continue
            # Extract group from labels like "group:auth"
            group = self._extract_group_from_labels(issue["labels"])
            task = self._issue_to_task(issue)
            groups.setdefault(group, []).append(task)
        return groups
```

## Non-Functional Requirements

### Performance

- Parallel execution should achieve 3x+ speedup for 3 independent tasks
- Worktree creation overhead should be < 2 seconds per worker
- GitHub API cache should reduce calls by 90%+ during normal operation
- YAML parsing should be < 100ms for 1000 tasks
- Hook execution should not add > 5 seconds per iteration
- Session state should persist in < 100ms
- Feedback injection should be reflected in next iteration (< 1 iteration delay)

### Reliability

- Network failures should not crash Ralph
- Hook failures should not crash the loop (unless configured)
- Partial updates should be atomic (all or nothing)
- Cache should survive process restarts
- Session state should survive crashes
- Feedback should survive loop restarts
- Failed worktrees preserved for debugging

### Safety

- No data loss if a worker crashes
- No corruption of main worktree
- No merge conflicts introduced by parallel execution itself
- All worker state preserved in logs
- Hooks run in isolated environment (no access to Ralph internals)
- Feedback cannot execute arbitrary code

### Usability

- YAML should be easier to edit than JSON
- Error messages should be clear and actionable
- TUI should provide real-time visibility
- Documentation should cover all common workflows
- Migration should be lossless
- Hooks should be easy to debug

### Security

- GitHub tokens should never be logged
- Tokens should be stored securely (keychain on macOS)
- gh CLI auth is preferred (more secure)
- Hook scripts should be explicitly configured (no auto-discovery)
- Feedback should be sanitized before inclusion in prompts

### Observability

- All GitHub API calls logged to `.ralph/logs/github-api.log`
- All hook executions logged to `.ralph/logs/hooks.log`
- All worker actions logged to `.ralph/logs/worker-{id}-{task}.log`
- All sessions tracked in `.ralph/sessions/`
- All feedback tracked in `.ralph/feedback.ndjson`
- Rate limit status visible in `ralph status`
- Session status visible in `ralph session list`

## Out of Scope (for v0.7.0)

### Deferred to v0.8.0

- AI-powered merge conflict resolution
- Dynamic worker scaling based on system resources
- PR automation (create-pr, auto-merge)
- Cost/telemetry reporting
- Retry logic + notifications
- Distributed execution across multiple machines

### Not Planned

- GitHub Projects integration (Issues are sufficient)
- GitHub Discussions integration
- Slack integration in core (use hooks instead)
- Issue creation from Ralph
- Multi-repo support
- YAML schema versioning beyond v1
- YAML includes/references
- Service scripts as runner extensibility (existing runner plugins sufficient)

## Dependencies

### Required

- Python >= 3.10
- Git >= 2.5 (for worktree support)
- PyYAML or ruamel.yaml (for YAML parsing)
- requests (for GitHub API)

### Optional

- gh CLI (recommended for GitHub auth)
- GitHub personal access token (if not using gh CLI)

### System Requirements

- Sufficient disk space for N worktrees (~500MB per worktree)
- Memory: < 100MB additional per worker
- OS: macOS, Linux, Windows (with WSL for hooks)

## Success Metrics

### Parallel Execution

- Parallel execution achieves 3x+ speedup for 3+ independent tasks
- Zero merge conflicts introduced by parallel execution in 100+ runs
- Zero data loss or corruption in 100+ parallel runs
- TUI provides clear visibility into all worker states

### GitHub Issues

- Ralph can successfully read and update issues in 100% of test cases
- Zero auth failures with properly configured gh CLI
- Issue updates complete within 2 seconds of task completion
- Cache reduces API calls by 90% during normal operation

### YAML Tracker

- YAML format is preferred by 50%+ of users for new projects
- Zero data loss in JSON→YAML→JSON round-trip
- YAML validation catches 100% of schema violations
- Parallel grouping is used in 80%+ of parallel workflows

### Lifecycle Hooks

- Hooks are used in 60%+ of production deployments
- Hook failures are debuggable within 5 minutes
- Hooks enable Slack/notification integrations without core changes
- Zero loop crashes due to hook failures (with continue_on_error=true)

### Session Management

- Sessions enable resumption in 100% of interrupted loops
- Session logs enable debugging in 90%+ of failure cases
- Session retention reduces disk usage by auto-cleanup

### Feedback Channel

- Feedback enables course correction in 80%+ of AFK loops
- Feedback is reflected in next iteration 100% of the time
- Feedback does not introduce security vulnerabilities

### Overall

- 100% backward compatibility with v0.6.0
- Zero breaking changes for existing users
- All features opt-in with safe defaults
- Documentation covers 100% of user stories
