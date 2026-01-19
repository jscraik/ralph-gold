# ADR 0001: Exit Signal Logic and Task Completion State

**Status:** Proposed
**Date:** 2026-01-19
**Context:** Loop exit behavior when no tasks are available
**Related:** PRD spec-2026-01-19-critical-bug-fixes-v3
**Revision:** v3 - Corrected exit mechanism per second-order review

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2026-01-19 | Initial ADR after adversarial review |
| **v3** | **2026-01-19** | **Corrected: use break, not return; added all_blocked() method spec** |

---

## Context

Ralph Gold runs in a loop, selecting one task per iteration until completion. When tasks become blocked or done, the loop must exit cleanly. The current implementation has a bug where it continues infinitely when no task is selected (`story_id=None`).

**Current Code** (`src/ralph_gold/loop.py:2462`):
```python
# Exit immediately if no task was selected (all done or all blocked)
if res.story_id is None and res.exit_signal is True:
    break
```

**Problem:** This condition requires BOTH `story_id is None` AND `exit_signal is True`. When no task is selected, the agent cannot respond with `EXIT_SIGNAL: true`, so `exit_signal` remains `False`, causing infinite loops.

**Evidence:** 42 wasted iterations documented in `.ralph/GOLD_STANDARD_FIXES.md`

**Architecture Understanding (from second-order review):**
- `run_loop()` returns `List[IterationResult]`, not an exit code
- Exit codes are calculated in `cli.py:922-928` after the loop completes
- Therefore, the loop should use `break` to exit, not `return` or `raise SystemExit()`

---

## Decision

### Part 1: Add `all_blocked()` Method to Tracker Interface

**Rationale:** The current tracker interface only has `all_done()`. To distinguish between "all tasks completed" and "all tasks blocked," we need `all_blocked()`.

**Interface Addition** (`src/ralph_gold/trackers.py:38`):
```python
class Tracker(Protocol):
    # ... existing methods ...

    def all_done(self) -> bool: ...
    def all_blocked(self) -> bool: ...  # NEW
```

**Implementation (Markdown Tracker):**
```python
def all_blocked(self) -> bool:
    """
    Return True if all remaining (non-done) tasks are marked as blocked.

    A task is blocked if it cannot be worked on due to unmet dependencies
    or other blockers. Tasks that are already done are excluded from this check.
    """
    remaining_tasks = [t for t in self.prd.tasks if t.status != "done"]
    if not remaining_tasks:
        return False  # No remaining tasks means done, not blocked
    return all(t.status == "blocked" for t in remaining_tasks)
```

### Part 2: Exit Condition Update

**New Logic** (`src/ralph_gold/loop.py:2462`):
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

**Key Decision:** Use `break` (not `return` or `raise SystemExit()`) because:
1. `run_loop()` returns `List[IterationResult]`
2. The loop must exit cleanly to return results
3. Exit codes are determined by `cli.py` based on the results

### Rationale

1. **Check `story_id is None` first** - No task means we need to exit
2. **Determine the reason** - Are we done? Blocked? Or configuration error?
3. **Use `break` to exit** - Preserves normal flow, lets cli.py calculate exit code
4. **Log appropriately** - Users see why the loop exited

### Exit Code Semantics

| Code | Meaning | How It's Determined |
|------|---------|---------------------|
| 0 | Success | `cli.py:926`: last.exit_signal is True |
| 1 | Incomplete | `cli.py:928`: default when not complete and no failures |
| 2 | Error | `cli.py:924`: any iteration failed |

This matches the README documentation:
```
Exit codes (ralph run):
- 0: successful completion
- 1: incomplete exit (e.g., max iterations / no-progress)
- 2: iteration failed (non-zero return, gate failure, judge failure, or review BLOCK)
```

**Important:** The "all blocked" case will result in exit code 1 because:
- No iterations failed (no `any_failed`)
- No `exit_signal=True` (no task was selected)
- Therefore, default to exit code 1

---

## Consequences

### Positive

1. **No more infinite loops** - Clean exit when tasks are blocked/done
2. **Clear error messages** - Users know why the loop exited
3. **Meaningful exit codes** - Scripts can distinguish success/failure/error
4. **Saves API credits** - No wasted iterations
5. **Architecturally correct** - Uses proper exit mechanism (`break`)

### Negative

1. **Behavior change** - Existing scripts may expect infinite loop (unlikely)
2. **New method required** - `all_blocked()` must be added to all trackers

### Neutral

1. **Exit code 1 semantics** - Now used for "all blocked" vs "max iterations"
   - This is acceptable; both indicate "incomplete" state

---

## Implementation

### Required Tracker Methods

The tracker interface must provide:

```python
def all_done(self) -> bool:
    """Return True if all tasks are marked as done."""
    # ✅ Already exists in trackers.py:80

def all_blocked(self) -> bool:
    """Return True if all remaining tasks are marked as blocked."""
    # ❌ Must be added to all trackers
```

### Implementations Required

1. **Markdown Tracker** - `src/ralph_gold/trackers.py` (MarkdownTracker class)
2. **YAML Tracker** - `src/ralph_gold/trackers/yaml_tracker.py`
3. **GitHub Tracker** - `src/ralph_gold/trackers/github_issues.py`
4. **JSON Tracker** - Handled via PRD parsing

### Testing

Test cases:
1. All tasks done → Exit code 0
2. All tasks blocked → Exit code 1
3. Mixed states → Loop continues
4. Tracker methods missing → Graceful fallback
5. Empty PRD → Proper handling

---

## Alternatives Considered

### Alternative 1: Keep Current Logic (REJECTED)

**Idea:** Keep requiring both `story_id is None AND exit_signal is True`

**Why Rejected:** This causes the infinite loop bug we're trying to fix.

### Alternative 2: Always Exit on story_id=None (REJECTED)

**Idea:** Exit immediately when `story_id is None`, regardless of reason

**Why Rejected:** Doesn't distinguish between "all done" (success) and "all blocked" (failure). We need different exit codes.

### Alternative 3: Use `return 1` or `raise SystemExit()` (REJECTED)

**Idea:** Return exit code directly from loop or raise SystemExit

**Why Rejected:** **v3 REJECTION** - Second-order review revealed this is architecturally wrong:
- `run_loop()` returns `List[IterationResult]`, not `int`
- Using `return 1` would break the function signature
- Using `raise SystemExit()` bypasses normal exit code calculation in `cli.py`
- Correct approach is `break`, letting cli.py determine exit code

### Alternative 4: Add New Exit Code for Blocked (REJECTED)

**Idea:** Use exit code 3 for "all blocked"

**Why Rejected:** Exit code 1 already means "incomplete," which includes blocked tasks. No need for a new code.

---

## Code Architecture Notes

### How Exit Codes Actually Work

**In `run_loop()`:**
```python
# Loop runs, collects results
for offset in range(limit):
    res = run_iteration(...)
    results.append(res)
    # ... logic ...
    break  # Exit loop

# Return results to caller
return results  # List[IterationResult]
```

**In `cli.py` (caller):**
```python
# Run the loop
results = run_loop(project_root, agent=agent, cfg=cfg, ...)

# Determine exit code from results
any_failed = any(r.return_code != 0 for r in results)
last = results[-1] if results else None

if any_failed:
    exit_code = 2
elif last and last.exit_signal is True:
    exit_code = 0
else:
    exit_code = 1

return exit_code
```

This architecture means:
1. The loop should NOT return exit codes directly
2. The loop should use `break` to exit cleanly
3. Exit codes are calculated AFTER the loop completes
4. The loop's job is to produce `IterationResult` objects

---

## References

- `src/ralph_gold/loop.py:2462` - Current exit logic
- `src/ralph_gold/loop.py:2471` - Function returns `results`
- `src/ralph_gold/cli.py:922-928` - Exit code calculation
- `src/ralph_gold/trackers.py:38` - Tracker interface
- `src/ralph_gold/trackers.py:80` - Existing `all_done()` implementation
- `.ralph/GOLD_STANDARD_FIXES.md` - Bug report
- `README.md` - Exit code documentation
- `.spec/SECOND_ORDER_REVIEW.md` - Second-order review findings

---

## Corrections from v2

| Issue | v2 (Wrong) | v3 (Correct) |
|-------|------------|--------------|
| Exit mechanism | `return 1`, `return 2` | `break` (let cli.py determine exit code) |
| Method status | Assumed `all_blocked()` exists | Specified that it must be added |
| Architecture | Misunderstood how exit codes work | Documented actual code flow |

---

**Author:** Claude Code (second-order review)
**Reviewers:** [Pending]
**Approval:** [Pending]
**Status:** READY FOR IMPLEMENTATION (v3 - all critical issues corrected)
