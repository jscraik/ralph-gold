# Ralph Loop Optimizations for Solo Developers

## Problem Statement

Ralph was designed for team workflows with formal processes. Solo developers need:

- **Speed over ceremony** - Ship fast, iterate faster
- **Flow state preservation** - Minimize interruptions and context switches
- **Pragmatic quality** - Good enough > perfect
- **Momentum maintenance** - Quick wins to stay motivated
- **Flexible rigor** - Strict when needed, loose when shipping

## Current Pain Points

### 1. Too Much Ceremony

- **Issue**: Every task requires full test suite, linting, type checking
- **Solo dev reality**: Sometimes you just need to ship a hotfix
- **Impact**: Slows velocity, breaks flow state

### 2. Rigid Iteration Structure

- **Issue**: One task per iteration, no flexibility
- **Solo dev reality**: Sometimes you want to batch 3 tiny tasks
- **Impact**: Overhead of iteration setup/teardown

### 3. No "Quick Mode"

- **Issue**: No fast path for trivial changes
- **Solo dev reality**: Fixing a typo shouldn't take 5 minutes
- **Impact**: Friction for small improvements

### 4. Limited Context Awareness

- **Issue**: Ralph doesn't know if you're exploring vs shipping
- **Solo dev reality**: Different modes need different rigor
- **Impact**: Same process for spike vs production code

### 5. No Momentum Tracking

- **Issue**: No visibility into velocity or flow state
- **Solo dev reality**: Need to know when you're in the zone
- **Impact**: Can't optimize for peak productivity times

## Proposed Improvements

### 1. Execution Modes

Add mode-based configuration to balance speed vs rigor:

#### Speed Mode (Default for Solo Devs)

```toml
[loop.modes.speed]
enabled = true
max_iterations = 20              # More iterations, less overhead
no_progress_limit = 2            # Fail fast
runner_timeout_seconds = 60      # Quick iterations
skip_gates_for_wip = true        # Skip gates for WIP commits
allow_batch_tasks = true         # Allow 2-3 tiny tasks per iteration
auto_commit = true               # Commit after each task
commit_message_template = "wip: {task_id}"
```

#### Quality Mode (For Production)

```toml
[loop.modes.quality]
enabled = false
max_iterations = 10
no_progress_limit = 3
runner_timeout_seconds = 120
skip_gates_for_wip = false       # Always run gates
allow_batch_tasks = false        # Strict one task per iteration
require_tests = true             # Must have tests
auto_commit = false              # Manual review
```

#### Exploration Mode (For Spikes)

```toml
[loop.modes.exploration]
enabled = false
max_iterations = 5               # Short exploration
no_progress_limit = 1            # Fail immediately if stuck
runner_timeout_seconds = 30      # Quick experiments
skip_gates = true                # No gates during exploration
allow_incomplete = true          # OK to leave things broken
auto_branch = true               # Create spike branch
branch_prefix = "spike/"
```

### 2. Quick Task Batching

Allow batching of trivial tasks to reduce overhead:

```markdown
## Quick Batch (5 min total)
- [ ] Fix typo in README
- [ ] Add missing docstring to User class
- [ ] Update version number in package.json

**Batch criteria:**
- All tasks < 2 min each
- No dependencies between tasks
- No tests required (docs, comments, config)
- Total batch < 10 min
```

### 3. Smart Gate Selection

Run only relevant gates based on what changed:

```toml
[gates.smart]
enabled = true

# Only run tests if code changed
run_tests_if = ["**/*.py", "!**/test_*.py"]

# Only run linting if code changed
run_lint_if = ["**/*.py", "**/*.ts"]

# Only run type checking if type hints changed
run_mypy_if = ["**/*.py"]

# Always skip for these patterns
skip_gates_for = [
    "**/*.md",           # Documentation
    "**/*.txt",          # Text files
    ".ralph/**",         # Ralph internal files
    "**/test_*.py"       # Test files (assume tests test themselves)
]
```

### 4. Flow State Indicators

Track and optimize for flow state:

```toml
[loop.flow]
enabled = true

# Track velocity
track_tasks_per_hour = true
track_iteration_duration = true

# Flow state detection
flow_threshold_tasks_per_hour = 4    # 4+ tasks/hour = flow state
flow_threshold_success_rate = 0.8    # 80%+ success = flow state

# Optimize for flow
prefer_similar_tasks = true          # Batch similar tasks to reduce context switching
suggest_break_after_minutes = 90     # Suggest break after 90 min
celebrate_streaks = true             # Show encouragement after 5+ tasks
```

### 5. Momentum Preservation

Keep the loop moving even when stuck:

```toml
[loop.momentum]
enabled = true

# Auto-skip blocked tasks
auto_skip_blocked = true
max_block_time_minutes = 15          # Skip if blocked > 15 min

# Suggest alternative tasks
suggest_easier_task = true           # Suggest easier task when stuck
suggest_momentum_task = true         # Suggest quick win to maintain flow

# Progress visibility
show_velocity_trend = true           # Show if you're speeding up or slowing down
show_completion_estimate = true      # Estimate time to completion
```

### 6. Context-Aware Prompts

Adjust prompts based on task type and mode:

#### For Documentation Tasks

```markdown
You are updating documentation. This is low-risk.

Rules:
- Skip running tests (docs don't break code)
- Focus on clarity and accuracy
- Use examples where helpful
- Update immediately, no ceremony
```

#### For Hotfix Tasks

```markdown
You are implementing a HOTFIX. Speed is critical.

Rules:
- Minimal change to fix the issue
- Add TODO for proper fix later
- Skip non-critical gates
- Commit immediately with [HOTFIX] prefix
```

#### For Exploration Tasks

```markdown
You are exploring/spiking. Learning is the goal.

Rules:
- It's OK to leave things broken
- Document findings in progress.md
- No need for tests or perfect code
- Focus on answering the research question
```

### 7. Solo Dev Workflow Shortcuts

Add convenience commands for common solo dev patterns:

```bash
# Quick mode - skip gates, fast iterations
ralph run --quick

# Batch mode - allow multiple tiny tasks per iteration
ralph run --batch

# Exploration mode - spike/research with no gates
ralph run --explore

# Hotfix mode - emergency fix, minimal process
ralph run --hotfix

# Focus mode - work on specific task, ignore others
ralph run --task task-5

# Resume from where you left off
ralph resume --continue
```

### 8. Intelligent Progress Tracking

Better visibility into what's working:

```bash
# Show velocity and flow state
ralph stats --flow

# Show what's blocking you
ralph stats --blockers

# Show time estimates
ralph stats --eta

# Show your productivity patterns
ralph stats --patterns
```

Output example:

```
Flow State: 🔥 IN THE ZONE
Tasks completed: 7 in 90 minutes (4.7 tasks/hour)
Success rate: 85% (6/7 passed gates)
Current streak: 5 tasks

Velocity trend: ↗️ Speeding up
Estimated completion: 2.5 hours (12 tasks remaining)

Suggestion: You're in flow state! Keep going for another 30 min, then take a break.
```

### 9. Adaptive Rigor

Automatically adjust rigor based on context:

```toml
[loop.adaptive]
enabled = true

# Relax rigor for low-risk changes
relax_for_docs = true
relax_for_tests = true
relax_for_config = true

# Increase rigor for high-risk changes
strict_for_auth = true
strict_for_security = true
strict_for_data_migration = true

# Learn from history
learn_from_failures = true          # Remember what breaks often
increase_rigor_after_bugs = true    # Stricter after bugs in same area
```

### 10. Solo Dev Defaults

Opinionated defaults optimized for solo developers:

```toml
[loop]
mode = "speed"                      # Default to speed mode
max_iterations = 20                 # More iterations
no_progress_limit = 2               # Fail fast
runner_timeout_seconds = 60         # Quick iterations
auto_commit = true                  # Commit after each task
allow_batch_tasks = true            # Allow batching tiny tasks

[gates]
smart_selection = true              # Only run relevant gates
skip_for_docs = true                # Skip gates for docs
skip_for_wip = true                 # Skip gates for WIP commits

[git]
auto_commit = true                  # Commit automatically
commit_message_template = "feat: {task_id} - {title}"
amend_if_needed = true              # Amend instead of new commits

[flow]
track_velocity = true               # Track tasks/hour
suggest_breaks = true               # Suggest breaks
celebrate_wins = true               # Show encouragement

[momentum]
auto_skip_blocked = true            # Skip blocked tasks
suggest_alternatives = true         # Suggest easier tasks when stuck
show_progress = true                # Show completion estimates
```

## Implementation Priority

### Phase 1: Quick Wins (Immediate)

1. ✅ Add execution modes (speed/quality/exploration)
2. ✅ Add smart gate selection
3. ✅ Add quick task batching
4. ✅ Add solo dev defaults to config

### Phase 2: Flow Optimization (Week 1)

5. Add flow state tracking
2. Add momentum preservation
3. Add context-aware prompts
4. Add workflow shortcuts

### Phase 3: Intelligence (Week 2)

9. Add adaptive rigor
2. Add intelligent progress tracking
3. Add productivity pattern analysis
4. Add learning from history

## Acceptance Criteria

This optimization is successful when:

- Solo devs can ship 2x faster without sacrificing quality
- Flow state is preserved (fewer interruptions)
- Velocity is visible and improving
- Blocked tasks don't kill momentum
- Quick changes take < 2 minutes end-to-end
- The loop adapts to your working style
- You feel encouraged, not frustrated

## Non-Goals

- Don't sacrifice correctness for speed
- Don't remove safety nets (gates still available)
- Don't force solo devs into team workflows
- Don't add complexity that slows down simple cases

## Success Metrics

Track these to measure improvement:

- Tasks per hour (target: 4-6 in flow state)
- Time to first commit (target: < 5 min)
- Blocked task rate (target: < 10%)
- Flow state duration (target: 60+ min sessions)
- Developer satisfaction (target: "feels fast")
