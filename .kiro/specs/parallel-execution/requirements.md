# Parallel Execution with Git Worktrees - Requirements

## Overview

Enable ralph-gold to execute multiple independent tasks concurrently using isolated git worktrees, dramatically improving throughput for repos with parallelizable work.

## User Stories

### 1. As a developer, I want Ralph to work on multiple independent tasks simultaneously

**So that** my loop converges 3-5x faster when I have parallelizable work.

**Acceptance Criteria:**

- Ralph can run N agents concurrently (configurable max_workers)
- Each agent runs in an isolated git worktree
- Each agent gets its own feature branch
- Agents cannot interfere with each other's state
- Failed agents don't poison successful agents
- I can see real-time status of all parallel workers

### 2. As a developer, I want to control which tasks can run in parallel

**So that** I avoid merge conflicts and wasted work on dependent tasks.

**Acceptance Criteria:**

- Tasks can be tagged with a "group" identifier
- Tasks in the same group run sequentially
- Tasks in different groups can run in parallel
- Default behavior is sequential (safe)
- I can opt-in to parallel mode per-project

### 3. As a developer, I want parallel execution to be safe by default

**So that** I don't accidentally create merge conflicts or corrupt my repo.

**Acceptance Criteria:**

- Parallel mode is opt-in (disabled by default)
- Worktrees are isolated under .ralph/worktrees/
- Each worktree gets a unique branch name
- Failed worktrees are preserved for debugging
- Successful worktrees can be merged or kept for PR
- Main worktree is never modified during parallel execution

### 4. As a developer, I want to see what each parallel worker is doing

**So that** I can monitor progress and debug failures.

**Acceptance Criteria:**

- TUI shows status of all workers in real-time
- Each worker has: task_id, status, branch, duration, gates_status
- Failed workers show error summary
- Logs are isolated per worker
- I can inspect any worker's full log

### 5. As a developer, I want parallel results to merge cleanly

**So that** I don't waste time resolving conflicts.

**Acceptance Criteria:**

- Merge policy is configurable (manual|auto_merge)
- Auto-merge only happens when gates pass
- Merge conflicts are detected and reported
- Failed merges preserve both branches for manual resolution
- Successful merges clean up worktrees automatically

## Configuration Schema

```toml
[parallel]
enabled = false              # opt-in
max_workers = 3              # concurrent agents
worktree_root = ".ralph/worktrees"
strategy = "queue"           # queue|group
merge_policy = "manual"      # manual|auto_merge|pr

[parallel.conflict_resolution]
strategy = "stop"            # stop|ai_resolve
ai_agent = "claude"          # agent to use for AI resolution
```

## Task Grouping Schema

Tasks need a way to declare parallelizability. Extend tracker formats:

**Markdown (PRD.md):**

```markdown
## Tasks

- [ ] Task 1 <!-- group: auth -->
- [ ] Task 2 <!-- group: ui -->
- [ ] Task 3 <!-- group: auth -->
```

**JSON (prd.json):**

```json
{
  "stories": [
    {"id": 1, "title": "...", "group": "auth"},
    {"id": 2, "title": "...", "group": "ui"}
  ]
}
```

**YAML (tasks.yaml):**

```yaml
tasks:
  - title: Task 1
    group: auth
    completed: false
  - title: Task 2
    group: ui
    completed: false
```

## CLI Interface

```bash
# Run in parallel mode
ralph run --parallel --max-workers 4

# Dry-run to see what would run in parallel
ralph run --parallel --dry-run

# Show parallel status
ralph status --parallel

# Clean up worktrees
ralph parallel clean

# List active worktrees
ralph parallel list
```

## Non-Functional Requirements

### Performance

- Parallel execution should achieve 3-5x throughput for 3+ independent tasks
- Worktree creation overhead should be < 2 seconds per worker
- Status updates should refresh at least every 2 seconds

### Safety

- No data loss if a worker crashes
- No corruption of main worktree
- No merge conflicts introduced by parallel execution itself
- All worker state preserved in logs

### Observability

- Every worker action logged to .ralph/logs/worker-{id}-{task}.log
- State tracked in .ralph/state.json with worker metadata
- TUI shows real-time worker status
- Failed workers clearly indicate failure reason

## Out of Scope (for v0.7.0)

- AI-powered merge conflict resolution (defer to v0.8.0)
- Dynamic worker scaling based on system resources
- Distributed execution across multiple machines
- Worker priority/scheduling beyond simple queue

## Dependencies

- Git worktree support (git >= 2.5)
- Sufficient disk space for N worktrees
- Python asyncio for worker orchestration

## Success Metrics

- Parallel execution completes 3+ independent tasks in 1/3 the sequential time
- Zero merge conflicts introduced by parallel execution
- Zero data loss or corruption in 100+ parallel runs
- TUI provides clear visibility into all worker states
