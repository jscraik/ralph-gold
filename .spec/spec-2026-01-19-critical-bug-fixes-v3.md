# PRD: Critical Bug Fixes for Ralph Gold v0.8.0 (Third Revision)

**Date:** 2026-01-19
**Priority:** CRITICAL (BLOCKS ALL PROGRESS)
**Status:** Planning
**Owner:** Ralph Gold Maintainer
**Revision:** v3 - Corrected exit mechanism and added missing method specifications

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2026-01-19 | Initial PRD after adversarial review |
| v2 | 2026-01-19 | Incorporated adversarial feedback |
| **v3** | **2026-01-19** | **Corrected exit mechanism per second-order review** |

---

## Executive Summary

After 93 iterations across multiple test runs, three critical bugs were identified that prevent Ralph Gold from operating reliably. These are not edge cases - they block normal operation and must be fixed before any feature development can proceed.

**Impact:**
- Claude runner completely broken (100% failure rate for Claude users)
- Infinite loops waste API credits when tasks are blocked
- Status reports may be misleading (needs verification)

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

### Bug 3: Misleading Status Reports (HIGH - NEEDS VERIFICATION)

**Severity:** HIGH - May mislead users about progress

**Reported State:**
`ralph status` is reported to count blocked tasks as "done," inflating progress numbers.

**Evidence from Issue Report:**
```
$ ralph status
Progress: 13/13 tasks done  # Reported as WRONG

# Claimed reality:
$ grep -E "^- \[x\]" .ralph/PRD.md | wc -l
3  # Actually done

$ grep -E "^- \[-\]" .ralph/PRD.md | wc -l
10  # Blocked, not done
```

**⚠️ IMPORTANT NOTE:** This bug is reported in `.ralph/GOLD_STANDARD_FIXES.md` but has **NOT been verified through code inspection**. The status calculation location needs to be identified and the behavior verified before implementing a fix.

**Impact (if verified):**
- Users think they're done when they're not
- Hides actual blocking issues
- Makes debugging impossible

**Root Cause (claimed):**
Status calculation may count both `[x]` (done) and `[-]` (blocked) as "completed."

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

### US-3: As a Ralph user, I want accurate progress reports (if verified)

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

- [ ] Add `all_blocked()` method to tracker interface (`src/ralph_gold/trackers.py`)
- [ ] Implement `all_blocked()` in markdown tracker
- [ ] Implement `all_blocked()` in YAML tracker (if applicable)
- [ ] Implement `all_blocked()` in GitHub tracker (if applicable)
- [ ] Update `src/ralph_gold/loop.py:2462` exit condition
- [ ] When `story_id is None`, check `tracker.all_done()` and `tracker.all_blocked()`
- [ ] Use `break` to exit loop (let cli.py determine exit code)
- [ ] Test: Create PRD with all blocked tasks, verify loop exits with code 1
- [ ] Test: Create PRD with all done tasks, verify loop exits with code 0
- [ ] Test: Verify zero `story_id=None` iterations

### Bug 3: Status Reporting Fix (CONDITIONAL - Verification Required)

**⚠️ PRELIMINARY:** Do not implement until bug is verified.

**Verification Steps:**
1. Find where status calculation occurs (likely in `src/ralph_gold/prd.py` or `src/ralph_gold/cli.py`)
2. Confirm that blocked tasks are counted as done
3. Identify the exact function responsible
4. Then proceed with fixes:

- [ ] **VERIFY:** Status calculation location identified
- [ ] **VERIFY:** Bug confirmed - blocked tasks counted as done
- [ ] Update status calculation to separate counts
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

### Fix 2: Exit Logic and Tracker Enhancement (45 minutes)

#### Step 2a: Add `all_blocked()` to Tracker Interface

**File:** `src/ralph_gold/trackers.py`

**Add to interface (around line 38):**
```python
class Tracker(Protocol):
    # ... existing methods ...

    def all_done(self) -> bool: ...

    def all_blocked(self) -> bool: ...  # NEW METHOD
```

#### Step 2b: Implement `all_blocked()` in Markdown Tracker

**File:** `src/ralph_gold/trackers.py` (MarkdownTracker class, around line 80)

```python
def all_blocked(self) -> bool:
    """
    Return True if all remaining (non-done) tasks are marked as blocked.

    A task is blocked if it cannot be worked on due to unmet dependencies
    or other blockers. Tasks that are already done are excluded from this check.
    """
    # Filter out done tasks, check if all remaining are blocked
    remaining_tasks = [t for t in self.prd.tasks if t.status != "done"]
    if not remaining_tasks:
        return False  # No remaining tasks means done, not blocked
    return all(t.status == "blocked" for t in remaining_tasks)
```

#### Step 2c: Implement `all_blocked()` in Other Trackers

**YAML Tracker:** `src/ralph_gold/trackers/yaml_tracker.py`

```python
def all_blocked(self) -> bool:
    """Return True if all remaining tasks are marked as blocked."""
    remaining = [t for t in self.tasks if not t.get("completed", False)]
    if not remaining:
        return False
    return all(t.get("blocked", False) for t in remaining)
```

**GitHub Tracker:** `src/ralph_gold/trackers/github_issues.py`

```python
def all_blocked(self) -> bool:
    """Return True if all remaining issues are blocked."""
    # For GitHub, check if all open issues have "blocked" label
    # Implementation depends on GitHub API query
    raise NotImplementedError("GitHub tracker all_blocked() not yet implemented")
```

#### Step 2d: Update Exit Logic in Loop

**File:** `src/ralph_gold/loop.py:2462`

**Current Code:**
```python
# Exit immediately if no task was selected (all done or all blocked)
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
        break  # Exit loop; cli.py will set exit_code=0 based on results
    elif all_blocked:
        logger.error("All remaining tasks are blocked")
        # Exit loop; cli.py will set exit_code=1 (default when not complete)
        break
    else:
        logger.error("No task selected but tasks remain (configuration error)")
        # Exit loop; context will determine exit code
        break
```

**IMPORTANT:** We use `break` (not `return` or `raise SystemExit`) because:
1. `run_loop()` returns `List[IterationResult]`, not an exit code
2. Exit codes are calculated in `cli.py:922-928` after the loop completes
3. Breaking allows normal flow to determine the appropriate exit code

**How Exit Codes Are Actually Determined:**
```python
# In cli.py:922-928 (after loop completes)
if any_failed:
    exit_code = 2
elif last and last.exit_signal is True:
    exit_code = 0
else:
    exit_code = 1  # This catches the "all blocked" case
```

### Fix 3: Status Calculation (VERIFICATION REQUIRED)

**⚠️ DO NOT IMPLEMENT UNTIL VERIFIED**

**Step 1: Find Status Calculation Location**
```bash
# Search for status/progress calculation
rg -n "def.*status|def.*progress|Progress:" src/ralph_gold/
```

**Step 2: Verify Behavior**
```bash
# Create test PRD with known states
# Run ralph status
# Compare output with actual PRD state
```

**Step 3: If Bug Confirmed, Implement Fix**

**File:** TBD (after verification)

**Approach:**
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
- Exit codes remain consistent (determined by cli.py)
- Test thoroughly before release
- **CORRECTED:** Using `break` preserves existing exit code flow

### Risk 3: Status Display Changes Break Scripts

**Mitigation:**
- Add `--format json` for script compatibility
- Document migration path if needed
- **CORRECTED:** Not implementing until verified

### Risk 4: New Method `all_blocked()` May Have Edge Cases

**Mitigation:**
- Comprehensive unit tests
- Handle edge cases (empty PRD, all done, no tasks)
- Graceful fallback on errors

---

## Dependencies

### External Dependencies
- Claude CLI (must support `-p` flag)
- No new Python dependencies required

### Internal Dependencies
- `tracker.all_done()` method ✅ **VERIFIED EXISTS** (src/ralph_gold/trackers.py:80)
- `tracker.all_blocked()` method ❌ **MUST BE ADDED** to all trackers
- Status calculation module ❓ **NEEDS VERIFICATION** for Bug 3

---

## Testing Plan

### Unit Tests

1. **Claude Runner Test**
   ```python
   def test_claude_runner_config():
       cfg = load_config(...)
       assert cfg.runners["claude"].argv == ["claude", "-p"]
   ```

2. **all_blocked() Tests**
   ```python
   def test_all_blocked_when_all_blocked():
       # Setup tracker with all tasks blocked
       # Assert all_blocked() returns True

   def test_all_blocked_when_mixed():
       # Setup tracker with mixed states
       # Assert all_blocked() returns False

   def test_all_blocked_when_all_done():
       # Setup tracker with all tasks done
       # Assert all_blocked() returns False (done != blocked)
   ```

3. **Exit Logic Tests**
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

### Before Fixes (from one documented test run)
- Claude agent success rate: 0%
- Wasted iterations per run: 42+
- Status accuracy: unknown (needs verification)

### After Fixes (Target)
- Claude agent success rate: 100%
- Wasted iterations per run: 0
- Status accuracy: 100% (if bug verified)

### Validation
- [ ] All Claude runs succeed
- [ ] Loop exits on blocked tasks (no infinite loops)
- [ ] Status shows accurate done/blocked/open counts (if bug exists)
- [ ] All tests pass
- [ ] No regressions in existing functionality

---

## Rollout Plan

### Phase 1: Code Changes (Day 1)
1. Fix Claude runner in config.py and ralph_solo.toml
2. Add all_blocked() to tracker interface and implementations
3. Fix exit logic in loop.py (using break, not return)

### Phase 2: Testing (Day 1-2)
1. Run unit tests
2. Run integration tests
3. Manual testing with real PRDs

### Phase 3: Bug 3 Verification (Day 2)
1. Locate status calculation code
2. Verify if bug exists
3. Implement fix if confirmed
4. Test status accuracy

### Phase 4: Release (Day 2-3)
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

1. **Status Calculation Location:** Where exactly is progress status calculated? (Needs code inspection for Bug 3)
2. **all_blocked() for GitHub Tracker:** What's the correct implementation for GitHub issues? (Needs API review)
3. **Backward Compatibility:** Do any existing scripts parse the old status format? (Needs user research)

---

## References

- `.ralph/GOLD_STANDARD_FIXES.md` - Original bug report
- `.spec/SECOND_ORDER_REVIEW.md` - Second-order review findings
- `src/ralph_gold/loop.py:2462` - Exit logic location
- `src/ralph_gold/cli.py:922-928` - Exit code calculation
- `src/ralph_gold/config.py:546` - Runner configuration
- `src/ralph_gold/trackers.py:38` - Tracker interface

---

## Scope

### In Scope

This PRD covers **ONLY** the following bug fixes:

1. **Bug 1:** Fix Claude runner configuration (2 files)
   - `src/ralph_gold/config.py:546` - Update default runner
   - `src/ralph_gold/templates/ralph_solo.toml:155` - Update solo template

2. **Bug 2:** Fix infinite loop when no task selected
   - Add `all_blocked()` method to tracker interface (1 file)
   - Implement `all_blocked()` in tracker implementations (3 files)
   - Update exit logic in loop.py (1 file)

3. **Bug 3:** Fix status reporting **IF VERIFIED**
   - Status calculation location identification
   - Status counting fix **ONLY IF** bug is confirmed to exist
   - Display format update **ONLY IF** bug is confirmed to exist

### Out of Scope

The following are **EXPLICITLY OUT OF SCOPE** for this PRD:

- New features or enhancements
- Performance optimizations (beyond fixing infinite loop)
- UI/UX improvements
- Documentation updates (beyond code comments)
- Test suite enhancements (beyond tests for these specific fixes)
- Phase 2 enhancements (YAML tracker, GitHub tracker, parallel execution, etc.)
- Refactoring or code quality improvements
- Any other bugs not explicitly listed above

### Scope Decision Log

| Decision | Date | Rationale |
|----------|------|-----------|
| Limit to 3 bugs only | 2026-01-19 | Focus on critical blockers; prevent scope creep |
| Bug 3 conditional on verification | 2026-01-19 | May not exist as reported; don't fix unverified issues |
| No feature work included | 2026-01-19 | Bugs block progress; defer features until bugs fixed |
| No refactoring included | 2026-01-19 | Keep changes minimal; reduces risk |
| No documentation updates | 2026-01-19 | Focus on code fixes only; docs can follow |

### Feature Creep Guardrails

**48-Hour Rule:** Any new items proposed after 2026-01-21 23:59 UTC must be deferred to a future PRD to maintain focus on critical bug fixes.

**Displacement Policy:** Any proposed addition must displace an existing item of equal or greater effort. Since all 3 bugs are critical, no additions will be accepted.

**Complexity Budget:** Total estimated effort is 2-3 hours. Any item that would push this beyond 4 hours must be deferred.

**Bug-Only Scope:** This PRD is intentionally limited to bug fixes. New features, however valuable, belong in separate PRDs.

---

## Launch & Rollback Guardrails

### Pre-Launch Checklist

Before releasing v0.8.1 with these fixes:

- [ ] All three bugs fixed (or Bug 3 verified and deferred)
- [ ] Unit tests pass for all changes
- [ ] Integration tests pass for all changes
- [ ] Manual testing completed with real PRDs
- [ ] Exit codes verified (0 for done, 1 for blocked, 2 for failed)
- [ ] No regressions in existing functionality
- [ ] CHANGELOG.md updated
- [ ] Version bumped to 0.8.1

### Rollback Plan

If critical issues are discovered post-launch:

1. **Immediate Rollback:** Revert to v0.8.0 via git tag
2. **Rollback Criteria:**
   - Claude agent failures increase
   - New infinite loops introduced
   - Exit codes no longer match documented behavior
   - Breaking changes to tracker interface

3. **Rollback Process:**
   ```bash
   git checkout v0.8.0
   git tag -f v0.8.1-rollback
   git push origin v0.8.1-rollback
   ```

4. **Hotfix Process:** If rollback is needed, create hotfix PRD that:
   - Identifies the regression
   - Specifies the fix
   - Includes verification steps
   - Goes through full testing before re-release

### Go/No-Go Metrics

**Go Conditions (ALL must be true):**
- [ ] Claude agent success rate ≥ 95% (from 0%)
- [ ] Infinite loops eliminated (0 iterations with story_id=None)
- [ ] Exit codes match documented behavior
- [ ] Test coverage ≥ 95% for changed code
- [ ] No new critical bugs introduced

**No-Go Conditions (ANY means stop):**
- [ ] Claude agent success rate < 90%
- [ ] Infinite loops still present
- [ ] Exit codes don't match documentation
- [ ] Breaking changes to existing workflows
- [ ] Critical bugs in new code

---

## Kill Criteria

**If ANY of these occur, immediately stop and rollback:**

1. **Claude agent completely broken** - Success rate < 50%
2. **New infinite loops** - More than 5 story_id=None iterations in test runs
3. **Exit code regression** - Scripts relying on exit codes break
4. **Data loss** - Any PRD data corruption
5. **Breaking changes** - Existing configurations stop working
6. **Performance degradation** - Loop takes >2x longer than v0.8.0

**Kill Process:**
1. Stop deployment immediately
2. Revert to v0.8.0
3. Assess root cause
4. Create hotfix PRD if appropriate
5. Re-test thoroughly before re-deployment

---

## Data Lifecycle & Retention

### Data Affected by These Fixes

1. **Iteration receipts** - `.ralph/receipts/` - No changes to format
2. **State file** - `.ralph/state.json` - No changes to format
3. **PRD files** - `.ralph/PRD.md`, `.ralph/prd.json` - No changes to format
4. **Logs** - `.ralph/logs/` - May contain additional debug messages

### Data Retention

- No changes to data retention policies
- No changes to log rotation
- No changes to archival processes

### Data Deletion

- No changes to data deletion policies
- No user data is processed or stored by these fixes

---

## Support / Ops Impact

### Support Impact

**Expected Support Load:** Minimal (bug fixes should reduce support requests)

**New Support Requests Expected:**
- "Why does my loop exit now when tasks are blocked?" (Expected: this is correct behavior)
- "Why did exit code change?" (Clarification: codes are the same, just more reliable)

**Documentation Updates Required:**
- Update troubleshooting guide with new exit behavior
- Add known issues section for v0.8.0 bugs
- Document new `all_blocked()` method in tracker documentation

### Ops Impact

**Monitoring Changes:** None (bug fixes don't change monitoring needs)

**Runbooks Requiring Updates:**
- Debugging infinite loops runbook (no longer needed)
- Exit code interpretation runbook (clarify, not change)

**Incident Response:** No changes (bug fixes reduce incident frequency)

---

## Compliance & Regulatory Review Triggers

### Regulatory Considerations

**N/A** - Bug fixes to a CLI tool have no regulatory implications.

### Compliance Requirements

- No changes to compliance requirements
- No new data processing (no GDPR/privacy impact)
- No accessibility changes (CLI-only tool)

### Review Triggers

None required - these are internal bug fixes.

---

## Ownership & RACI

| Role | Responsible | Accountable | Consulted | Informed |
|------|-------------|-------------|-----------|----------|
| **Bug Fixes Implementation** | Ralph Gold Maintainer | Ralph Gold Maintainer | - | Users |
| **Code Review** | Ralph Gold Maintainer | Ralph Gold Maintainer | - | - |
| **Testing** | Ralph Gold Maintainer | Ralph Gold Maintainer | - | - |
| **Release Decision** | Ralph Gold Maintainer | Ralph Gold Maintainer | - | Users |

**Solo Project Note:** As a solo project, the maintainer performs all roles. RACI is documented for clarity if project grows.

---

## Security & Privacy Classification

### Security Classification

**Classification:** Internal Bug Fix

**Security Considerations:**
- No new security vulnerabilities introduced
- Fixes infinite loop that could be used for DoS (wasting API credits)
- No changes to authentication or authorization
- No changes to data handling

**Security Review Required:** No (bug fixes to existing code)

### Privacy Classification

**Classification:** N/A (No user data processed)

**Privacy Considerations:**
- No personal data processed
- No changes to logging (logs may contain code snippets, same as before)
- No telemetry or analytics (tool doesn't collect any)

---

## Dependency SLAs & Vendor Risk

### External Dependencies

| Dependency | Version | SLA | Risk Mitigation |
|-------------|---------|-----|-----------------|
| Claude CLI | System | Best effort | Tool requirement, not runtime dep |
| Python stdlib | Built-in | N/A | No risk |

**Vendor Risk:** None - no external vendors beyond standard toolchain.

### Internal Dependencies

| Dependency | Status | SLA | Risk |
|------------|--------|-----|------|
| `tracker.all_done()` | ✅ Exists | N/A | No risk |
| `tracker.all_blocked()` | ❌ Must add | N/A | Low - new method, well-specified |

---

## Cost Model & Budget Guardrails

### Development Cost

**Estimated Effort:** 2-3 hours

**Resource Budget:**
- Developer time: 2-3 hours
- Testing time: 1-2 hours
- Documentation: 0.5 hours (comments, changelog)
- **Total:** 3.5-5.5 hours

### Cost Guardrails

**Budget Cap:** 6 hours maximum. If implementation exceeds 6 hours:
1. Stop and reassess
2. Identify what's taking longer
3. Either simplify approach or defer to future PRD

**Opportunity Cost:** By fixing bugs now, we unblock:
- Reliable Claude agent usage
- Predictable loop behavior
- Accurate status reporting

**Cost of Not Fixing:** Wasted API credits, frustrated users, unreliable loops.

---

## Localization & Internationalization

**N/A** - Bug fixes to internal code have no i18n impact.

---

## Backward Compatibility & Deprecation

### Backward Compatibility

**Maintained:**
- Exit code semantics (0=success, 1=incomplete, 2=error) - **UNCHANGED**
- Tracker interface - **EXTENDED** (added `all_blocked()`)
- PRD formats - **UNCHANGED**
- Configuration file format - **UNCHANGED**

**Breaking Changes:** None

### Deprecation

**Nothing Deprecated** - These are pure bug fixes with no API changes.

---

## Experimentation & Feature Flags

**N/A** - Bug fixes are not experimental; they are critical corrections.

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-19 | Prioritize bug fixes over features | Bugs block all progress |
| 2026-01-19 | Use `["claude", "-p"]` for runner | Simple, works, no need for stream-json |
| 2026-01-19 | Exit codes: 0=success, 1=incomplete, 2=error | Matches README documentation |
| 2026-01-19 | Use `break` not `return` for exit | **v3 correction** - run_loop() returns results, cli.py calculates exit codes |
| 2026-01-19 | Add all_blocked() to all trackers | **v3 correction** - Method doesn't exist, must be added |
| 2026-01-19 | Qualify Bug 3 as unverified | **v3 correction** - Needs code inspection before implementation |

---

**Schema Version:** 1
**Status:** READY FOR IMPLEMENTATION (v3 - all critical issues corrected)
