# Solo Dev Optimizations - Implementation Plan

## Overview

This plan implements the solo developer optimizations from `SOLO_DEV_OPTIMIZATIONS.md` in phases, prioritizing quick wins and high-impact features.

## Phase 1: Quick Wins (Immediate - 1-2 days)

### 1.1 Add Execution Modes to Config

**Impact:** High | **Effort:** Low

Add mode-based configuration to `ralph.toml`:

```toml
[loop]
mode = "speed"  # speed|quality|exploration

[loop.modes.speed]
max_iterations = 20
no_progress_limit = 2
runner_timeout_seconds = 60
skip_gates_for_wip = true
allow_batch_tasks = true
auto_commit = true

[loop.modes.quality]
max_iterations = 10
no_progress_limit = 3
runner_timeout_seconds = 120
skip_gates_for_wip = false
allow_batch_tasks = false
require_tests = true

[loop.modes.exploration]
max_iterations = 5
no_progress_limit = 1
runner_timeout_seconds = 30
skip_gates = true
allow_incomplete = true
auto_branch = true
branch_prefix = "spike/"
```

**Files to modify:**

- `src/ralph_gold/config.py` - Add mode configuration
- `src/ralph_gold/loop.py` - Apply mode settings
- `src/ralph_gold/templates/ralph.toml` - Add mode defaults

**Acceptance Criteria:**

- `ralph run --mode speed` works
- `ralph run --mode quality` works
- `ralph run --mode exploration` works
- Mode settings override base loop settings
- Tests pass

### 1.2 Smart Gate Selection

**Impact:** High | **Effort:** Medium

Only run gates relevant to changed files:

```toml
[gates.smart]
enabled = true
run_tests_if = ["**/*.py", "!**/test_*.py"]
run_lint_if = ["**/*.py", "**/*.ts"]
skip_gates_for = ["**/*.md", "**/*.txt", ".ralph/**"]
```

**Files to modify:**

- `src/ralph_gold/config.py` - Add smart gate config
- `src/ralph_gold/loop.py` - Implement smart gate filtering
- Add file pattern matching logic

**Acceptance Criteria:**

- Gates skip when only docs changed
- Gates run when code changed
- Pattern matching works correctly
- Tests pass

### 1.3 Quick Task Batching

**Impact:** Medium | **Effort:** Medium

Allow batching 2-3 tiny tasks per iteration:

**Files to modify:**

- `src/ralph_gold/loop.py` - Detect and batch tiny tasks
- `src/ralph_gold/prd.py` - Support selecting multiple tasks
- `src/ralph_gold/templates/PROMPT_build.md` - Update prompt for batching

**Acceptance Criteria:**

- Can batch tasks marked with `[QUICK]` prefix
- Max 3 tasks per batch
- Total batch time < 10 min
- Tests pass

### 1.4 Solo Dev Default Config

**Impact:** High | **Effort:** Low

Update default `ralph.toml` template with solo dev optimizations:

**Files to modify:**

- `src/ralph_gold/templates/ralph.toml` - Update defaults
- `src/ralph_gold/scaffold.py` - Add `--solo` flag to `ralph init`

**Acceptance Criteria:**

- `ralph init --solo` creates optimized config
- Default mode is "speed"
- Auto-commit enabled by default
- Tests pass

## Phase 2: Flow Optimization (Week 1 - 3-5 days)

### 2.1 Flow State Tracking

**Impact:** High | **Effort:** Medium

Track velocity and flow state indicators:

**Files to modify:**

- `src/ralph_gold/stats.py` - Add flow state calculations
- `src/ralph_gold/loop.py` - Track iteration timing
- `src/ralph_gold/cli.py` - Add `ralph stats --flow` command

**Acceptance Criteria:**

- Tracks tasks per hour
- Detects flow state (4+ tasks/hour, 80%+ success)
- Shows velocity trends
- `ralph stats --flow` displays flow metrics
- Tests pass

### 2.2 Momentum Preservation

**Impact:** High | **Effort:** Medium

Auto-skip blocked tasks and suggest alternatives:

**Files to modify:**

- `src/ralph_gold/loop.py` - Auto-skip logic
- `src/ralph_gold/trackers.py` - Alternative task suggestions
- `src/ralph_gold/config.py` - Add momentum config

**Acceptance Criteria:**

- Auto-skips tasks blocked > 15 min
- Suggests easier alternative tasks
- Shows completion estimates
- Tests pass

### 2.3 Context-Aware Prompts

**Impact:** Medium | **Effort:** Medium

Adjust prompts based on task type:

**Files to modify:**

- `src/ralph_gold/templates/PROMPT_build_docs.md` - Docs prompt
- `src/ralph_gold/templates/PROMPT_build_hotfix.md` - Hotfix prompt
- `src/ralph_gold/templates/PROMPT_build_exploration.md` - Exploration prompt
- `src/ralph_gold/loop.py` - Select prompt based on task type

**Acceptance Criteria:**

- Detects task type from title/tags
- Uses appropriate prompt
- Docs tasks skip tests
- Hotfix tasks are minimal
- Tests pass

### 2.4 Workflow Shortcuts

**Impact:** Medium | **Effort:** Low

Add convenience CLI flags:

**Files to modify:**

- `src/ralph_gold/cli.py` - Add shortcut flags

**Acceptance Criteria:**

- `ralph run --quick` works (speed mode, skip gates)
- `ralph run --batch` works (allow batching)
- `ralph run --explore` works (exploration mode)
- `ralph run --hotfix` works (minimal process)
- `ralph run --task task-5` works (focus on one task)
- Tests pass

## Phase 3: Intelligence (Week 2 - 5-7 days)

### 3.1 Adaptive Rigor

**Impact:** Medium | **Effort:** High

Automatically adjust rigor based on context:

**Files to modify:**

- `src/ralph_gold/config.py` - Add adaptive config
- `src/ralph_gold/loop.py` - Implement adaptive logic
- Add risk detection (auth, security, data)

**Acceptance Criteria:**

- Relaxes rigor for docs/tests/config
- Increases rigor for auth/security/data
- Learns from past failures
- Tests pass

### 3.2 Intelligent Progress Tracking

**Impact:** High | **Effort:** Medium

Better visibility into productivity:

**Files to modify:**

- `src/ralph_gold/stats.py` - Enhanced stats
- `src/ralph_gold/cli.py` - Add `ralph stats --blockers`, `--eta`, `--patterns`

**Acceptance Criteria:**

- Shows blockers and time stuck
- Shows ETA to completion
- Shows productivity patterns (best times)
- Suggests breaks
- Tests pass

### 3.3 Learning from History

**Impact:** Medium | **Effort:** High

Track what breaks often and adjust:

**Files to modify:**

- `src/ralph_gold/loop.py` - Track failures by file/area
- `src/ralph_gold/config.py` - Store learned patterns
- Add failure pattern detection

**Acceptance Criteria:**

- Remembers files that break often
- Increases rigor for problematic areas
- Suggests extra tests for risky changes
- Tests pass

## Implementation Order

### Week 1 (Days 1-2): Quick Wins

1. ✅ Execution modes (1.1)
2. ✅ Smart gate selection (1.2)
3. ✅ Solo dev defaults (1.4)

### Week 1 (Days 3-5): Flow Optimization

4. ✅ Quick task batching (1.3)
2. ✅ Flow state tracking (2.1)
3. ✅ Workflow shortcuts (2.4)

### Week 2 (Days 1-3): More Flow

7. ✅ Momentum preservation (2.2)
2. ✅ Context-aware prompts (2.3)

### Week 2 (Days 4-7): Intelligence

9. ✅ Intelligent progress tracking (3.2)
2. ✅ Adaptive rigor (3.1)
3. ✅ Learning from history (3.3)

## Testing Strategy

For each feature:

1. Unit tests for new functions
2. Integration tests for CLI commands
3. Manual testing with real projects
4. Property-based tests for complex logic

## Rollout Strategy

1. **Alpha** - Test with ralph-gold itself
2. **Beta** - Release as opt-in feature flag
3. **GA** - Make default for new projects
4. **Migration** - Provide migration guide for existing projects

## Success Metrics

Track these before/after:

- Average tasks per hour
- Time to first commit
- Blocked task rate
- Flow state duration
- Developer satisfaction (survey)

**Target improvements:**

- 2x tasks per hour in flow state
- 50% reduction in time to first commit
- 50% reduction in blocked task rate
- 2x flow state duration

## Acceptance Criteria

This implementation is complete when:

- All Phase 1 features are implemented and tested
- All Phase 2 features are implemented and tested
- All Phase 3 features are implemented and tested
- Documentation is updated
- Migration guide is written
- Success metrics show 2x improvement
- Solo devs report "feels fast"
