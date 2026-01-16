# Ralph-Gold v0.7.0: Parallel Execution + GitHub Issues

## Quick Links

- **Requirements:** [requirements.md](requirements.md) - User stories and acceptance criteria
- **Design:** [design.md](design.md) - Architecture and implementation details
- **Tasks:** Coming next - Implementation task breakdown

## Overview

v0.7.0 adds the two highest-ROI features from ralphy analysis:

1. **Parallel Execution** - 3-5x throughput via git worktrees
2. **GitHub Issues Tracker** - Production-ready team workflows
3. **YAML Tracker** - Machine-editable format with parallel grouping

## Key Features

### Parallel Execution

- Isolated git worktrees (one per worker)
- Configurable worker pool (default: 3)
- Group-based task scheduling
- Real-time TUI status display
- Automatic merge on success

### GitHub Issues Integration

- Read tasks from GitHub Issues
- Filter by labels
- Auto-close on completion
- Comment with results
- gh CLI or token auth

### YAML Tracker

- Human-friendly structured format
- Native parallel group support
- Migration from JSON/Markdown
- Schema validation

## Configuration Example

```toml
# Enable parallel execution
[parallel]
enabled = true
max_workers = 3
worktree_root = ".ralph/worktrees"
merge_policy = "manual"

# Use GitHub Issues
[tracker]
kind = "github_issues"

[tracker.github]
repo = "owner/repo"
label_filter = "ready"
close_on_done = true
```

## Implementation Plan

- **Week 1:** YAML Tracker
- **Week 2:** GitHub Issues Tracker
- **Week 3:** Parallel Execution Core
- **Week 4:** TUI + Integration Testing

## Success Metrics

- 3x+ speedup for 3 independent tasks
- Zero merge conflicts from parallel execution
- < 10 GitHub API calls per run (with cache)
- 100% backward compatibility with v0.6.0

## Status

- [x] Requirements complete
- [x] Design complete
- [x] Tasks breakdown complete
- [ ] Implementation (ready to start)
- [ ] Testing
- [ ] Documentation
- [ ] Release
