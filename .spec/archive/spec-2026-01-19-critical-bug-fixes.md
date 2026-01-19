# PRD: Critical Bug Fixes for Ralph Gold v0.8.0

**Date:** 2026-01-19
**Priority:** CRITICAL (BLOCKS ALL PROGRESS)
**Status:** Planning
**Owner:** Ralph Gold Maintainer

---

## Executive Summary

After 93 iterations across multiple test runs, three critical bugs were identified that prevent Ralph Gold from operating reliably. These are not edge cases - they block normal operation and must be fixed before any feature development can proceed.

**Impact:**
- Claude runner completely broken (100% failure rate for Claude users)
- Infinite loops waste API credits when tasks are blocked
- Misleading status reports hide actual progress

**Estimated Effort:** 2-3 hours (all fixes)

---

## Problem Statement

### Bug 1: Claude Runner Configuration Incompatible (CRITICAL)

**Severity:** CRITICAL - Blocks all Claude agent work

**Current State:**
The default runner configuration in `config.py` and `ralph_solo.toml` template uses incompatible flags:

```toml
# BROKEN (config.py:546, ralph_solo.toml:155)
argv = ["claude", "--output-format", "stream-json", "-p"]
```

**Error:**
```
Error: When using --print, --output-format=stream-json requires --verbose
```

**Impact:**
- 100% of Claude agent runs fail immediately
- Users cannot use Claude Code with Ralph
- Affects anyone using the default configuration

**Evidence:**
- `src/ralph_gold/config.py:546` - Default runner has incompatible flags
- `src/ralph_gold/templates/ralph_solo.toml:155` - Solo template has bug
- `src/ralph_gold/templates/ralph.toml:155` - Main template is CORRECT (`["claude", "-p"]`)

**Root Cause:**
The Claude CLI changed its flag requirements. The `stream-json` output format now requires `--verbose` when used with `-p` (prompt flag).

### Bug 2: Infinite Loop When No Task Selected (CRITICAL)

**Severity:** CRITICAL - Wastes 42+ iterations per run

**Current State:**
When all tasks are blocked or done, the loop continues indefinitely with `story_id=None` instead of exiting.

**Evidence from Code:**
```python
# src/ralph_gold/loop.py:2462
if res.story_id is None and res.exit_signal is True:
    break
```

**Problem:**
This exit condition requires BOTH `story_id is None` AND `exit_signal is True`. When no task is selected, the agent can't respond with `EXIT_SIGNAL: true`, so `exit_signal` remains `False`, causing infinite loops.

**Impact:**
- Wasted API credits (42 documented wasted iterations)
- No clear error message
- Users must manually kill the process
- Masks actual task completion status

**Test Case:**
```markdown
# PRD with all blocked tasks
## Tasks
- [-] 1. Blocked task
  - Depends on: nonexistent task

# Expected: Loop exits immediately with error
# Actual: Loop continues infinitely with story_id=None
```

### Bug 3: Misleading Status Reports (HIGH)

**Severity:** HIGH - Misleads users about progress

**Current State:**
`ralph status` reports blocked tasks as "done", inflating progress numbers.

**Example:**
```
$ ralph status
Progress: 13/13 tasks done  # WRONG

# Reality:
$ grep -E "^- \[x\]" .ralph/PRD.md | wc -l
3  # Actually done

$ grep -E "^- \[-\]" .ralph/PRD.md | wc -l
10  # Blocked, not done
```

**Impact:**
- Users think they're done when they're not
- Hides actual blocking issues
- Makes debugging impossible

**Root Cause:**
Status calculation counts both `[x]` (done) and `[-]` (blocked) as "completed."

---

## User Stories

### US-1: As a Ralph user, I want Claude agent to work

**Given:** I have Claude Code installed and configured
**When:** I run `ralph step --agent claude`
**Then:** The agent executes without CLI errors
**Acceptance:**
- Claude runner uses compatible flags
- No "output-format" errors
- Agent receives prompt correctly

### US-2: As a Ralph user, I want loops to exit when tasks are blocked

**Given:** All tasks in my PRD are blocked or done
**When:** The loop runs
**Then:** The loop exits immediately with appropriate exit code
**Acceptance:**
- Exit code 0 when all tasks done
- Exit code 1 when all tasks blocked
- Exit code 2 when configuration error
- Zero iterations with `story_id=None`

### US-3: As a Ralph user, I want accurate progress reports

**Given:** I have a mix of done, blocked, and open tasks
**When:** I run `ralph status`
**Then:** I see accurate counts for each state
**Acceptance:**
- Display format: "X/Y done (A blocked, B open)"
- Only `[x]` tasks counted as done
- `[-]` tasks shown as blocked
- `[ ]` tasks shown as open

---

## Acceptance Criteria

### Bug 1: Claude Runner Fix

- [ ] Update `src/ralph_gold/config.py:546` to use `["claude", "-p"]`
- [ ] Update `src/ralph_gold/templates/ralph_solo.toml:155` to use `["claude", "-p"]`
- [ ] Verify `ralph.toml` main template is correct (already is)
- [ ] Test: `echo "test" | claude -p` works
- [ ] Test: `ralph step --agent claude` executes without errors
- [ ] Add comment explaining flag choice for future maintainers

### Bug 2: Exit Logic Fix

- [ ] Update `src/ralph_gold/loop.py:2462` exit condition
- [ ] When `story_id is None`, check `tracker.all_done()` and `tracker.all_blocked()`
- [ ] Exit code 0 if `all_done()` returns True
- [ ] Exit code 1 if `all_blocked()` returns True
- [ ] Exit code 2 if neither (configuration error)
- [ ] Test: Create PRD with all blocked tasks, verify exit code 1
- [ ] Test: Create PRD with all done tasks, verify exit code 0
- [ ] Test: Verify zero `story_id=None` iterations

### Bug 3: Status Reporting Fix

- [ ] Update status calculation in relevant tracker module
- [ ] Count only `[x]` tasks as done
- [ ] Count `[-]` tasks as blocked
- [ ] Count `[ ]` tasks as open
- [ ] Update display format to show all three counts
- [ ] Test: Block all tasks, verify "0/N done (N blocked)"
- [ ] Test: Mix of states, verify accurate counts

---

## Technical Implementation

### Fix 1: Claude Runner (5 minutes)

**Files:**
- `src/ralph_gold/config.py:546`
- `src/ralph_gold/templates/ralph_solo.toml:155`

**Change:**
```python
# Before (BROKEN):
"claude": RunnerConfig(argv=["claude", "--output-format", "stream-json", "-p"]),

# After (WORKING):
"claude": RunnerConfig(argv=["claude", "-p"]),
```

**Verification:**
```bash
# Test Claude CLI directly
echo "test" | claude -p

# Test with Ralph
ralph step --agent claude
```

### Fix 2: Exit Logic (30 minutes)

**File:** `src/ralph_gold/loop.py:2462`

**Current Code:**
```python
if res.story_id is None and res.exit_signal is True:
    break
```

**New Code:**
```python
# Exit immediately if no task was selected
if res.story_id is None:
    # Determine why no task was selected
    try:
        all_done = tracker.all_done()
        all_blocked = tracker.all_blocked()
    except Exception:
        all_done = False
        all_blocked = False

    if all_done:
        logger.info("All tasks completed successfully")
        # Return exit code 0 by not breaking (will be handled below)
        break
    elif all_blocked:
        logger.error("All remaining tasks are blocked")
        # Exit with code 1 to indicate incomplete state
        raise SystemExit(1)
    else:
        logger.error("No task selected but tasks remain (configuration error)")
        # Exit with code 2 to indicate error
        raise SystemExit(2)
```

**Note:** Need to verify the exact exit mechanism used in the loop function.

### Fix 3: Status Calculation (15 minutes)

**File:** TBD (needs code inspection to find where status is calculated)

**Approach:**
1. Find the function that calculates progress summary
2. Separate counts for `done`, `blocked`, and `open` tasks
3. Update display format

**Example:**
```python
def get_progress_summary(self):
    total = len(self.tasks)
    done = len([t for t in self.tasks if t.status == 'done'])      # [x]
    blocked = len([t for t in self.tasks if t.status == 'blocked']) # [-]
    open = len([t for t in self.tasks if t.status == 'open'])       # [ ]

    return {
        'total': total,
        'done': done,
        'blocked': blocked,
        'open': open,
        'progress_pct': (done / total * 100) if total > 0 else 0
    }
```

**Display:**
```
Progress: 3/13 done (10 blocked, 0 open)
```

---

## Risks and Mitigations

### Risk 1: Breaking Existing Configurations

**Mitigation:**
- Changes are backward compatible
- New flags work with existing Claude CLI versions
- Document changes in changelog

### Risk 2: Exit Logic Changes Affect Existing Workflows

**Mitigation:**
- New behavior is MORE correct (exits instead of looping)
- Exit codes are meaningful and documented
- Test thoroughly before release

### Risk 3: Status Display Changes Break Scripts

**Mitigation:**
- Add both old and new formats initially
- Document migration path
- Consider `--format json` for script compatibility

---

## Dependencies

### External Dependencies
- Claude CLI (must support `-p` flag)
- No new Python dependencies required

### Internal Dependencies
- `tracker.all_done()` method must exist
- `tracker.all_blocked()` method must exist or be added
- Status calculation module must be identified

---

## Testing Plan

### Unit Tests

1. **Claude Runner Test**
   ```python
   def test_claude_runner_config():
       cfg = load_config(...)
       assert cfg.runners["claude"].argv == ["claude", "-p"]
   ```

2. **Exit Logic Tests**
   ```python
   def test_exit_when_all_done():
       # Setup tracker with all tasks done
       # Run loop
       # Assert exit code 0

   def test_exit_when_all_blocked():
       # Setup tracker with all tasks blocked
       # Run loop
       # Assert exit code 1
   ```

3. **Status Calculation Tests**
   ```python
   def test_status_counts_blocked_separately():
       # Setup tracker with mixed states
       # Get status summary
       # Assert counts are correct
   ```

### Integration Tests

1. **End-to-End Claude Run**
   - Create PRD with one simple task
   - Run `ralph step --agent claude`
   - Verify task completes

2. **Blocked Task Loop**
   - Create PRD with all blocked tasks
   - Run `ralph run`
   - Verify immediate exit with code 1

3. **Status Accuracy**
   - Create PRD with known task states
   - Run `ralph status`
   - Verify output matches actual state

---

## Success Metrics

### Before Fixes
- Claude agent success rate: 0%
- Wasted iterations per run: 42+
- Status accuracy: 23% (3/13 correct)

### After Fixes (Target)
- Claude agent success rate: 100%
- Wasted iterations per run: 0
- Status accuracy: 100%

### Validation
- [ ] All Claude runs succeed
- [ ] Loop exits on blocked tasks (no infinite loops)
- [ ] Status shows accurate done/blocked/open counts
- [ ] All tests pass
- [ ] No regressions in existing functionality

---

## Rollout Plan

### Phase 1: Code Changes (Day 1)
1. Fix Claude runner in config.py and ralph_solo.toml
2. Fix exit logic in loop.py
3. Fix status calculation (location TBD)

### Phase 2: Testing (Day 1-2)
1. Run unit tests
2. Run integration tests
3. Manual testing with real PRDs

### Phase 3: Release (Day 2)
1. Update version to 0.8.1
2. Update CHANGELOG.md
3. Create git tag
4. Publish release

---

## Post-Launch Monitoring

### Metrics to Track
- Claude agent success rate
- Loop exit codes distribution
- Status command usage
- Bug reports related to these fixes

### Support Considerations
- Update troubleshooting guide
- Add known issues section
- Document new exit codes
- Provide migration guide if needed

---

## Open Questions

1. **Status Calculation Location:** Where exactly is progress status calculated? (Needs code inspection)
2. **all_blocked() Method:** Does `tracker.all_blocked()` exist? If not, needs to be added.
3. **Exit Mechanism:** Should we use `raise SystemExit()` or `return exit_code`? (Needs code inspection)
4. **Backward Compatibility:** Do any existing scripts parse the old status format?

---

## References

- `.ralph/GOLD_STANDARD_FIXES.md` - Original bug report
- `src/ralph_gold/loop.py` - Exit logic location
- `src/ralph_gold/config.py` - Runner configuration
- `src/ralph_gold/templates/ralph_solo.toml` - Solo template

---

**Decision Log:**

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-19 | Prioritize bug fixes over features | Bugs block all progress |
| 2026-01-19 | Use `["claude", "-p"]` for runner | Simple, works, no need for stream-json |
| 2026-01-19 | Exit codes: 0=success, 1=incomplete, 2=error | Matches README documentation |

---

**Schema Version:** 1
