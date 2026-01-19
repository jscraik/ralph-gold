# ADR 0001: Exit Signal Logic and Task Completion State

**Status:** Proposed
**Date:** 2026-01-19
**Context:** Loop exit behavior when no tasks are available
**Related:** PRD spec-2026-01-19-critical-bug-fixes

---

## Context

Ralph Gold runs in a loop, selecting one task per iteration until completion. When tasks become blocked or done, the loop must exit cleanly. The current implementation has a bug where it continues infinitely when no task is selected (`story_id=None`).

**Current Code** (`src/ralph_gold/loop.py:2462`):
```python
# Exit immediately if no task was selected (all done or all blocked)
if res.story_id is None and res.exit_signal is True:
    break
```

**Problem:** This condition requires BOTH `story_id is None` AND `exit_signal is True`. When no task is selected, the agent cannot respond, so `exit_signal` remains `False`, causing infinite loops.

**Evidence:** 42 wasted iterations documented in `.ralph/GOLD_STANDARD_FIXES.md`

---

## Decision

### Exit Condition Update

**New Logic:**
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
        break  # Will return exit code 0
    elif all_blocked:
        logger.error("All remaining tasks are blocked")
        return 1  # Incomplete exit
    else:
        logger.error("No task selected but tasks remain (configuration error)")
        return 2  # Error exit
```

### Rationale

1. **Check `story_id is None` first** - No task means we need to exit
2. **Determine the reason** - Are we done? Blocked? Or is something wrong?
3. **Exit with appropriate code** - Communicate the state to caller

### Exit Code Semantics

| Code | Meaning | Use Case |
|------|---------|----------|
| 0 | Success | All tasks completed |
| 1 | Incomplete | All tasks blocked (can't continue) |
| 2 | Error | No task but tasks remain (config error) |

This matches the README documentation:
```
Exit codes (ralph run):
- 0: successful completion
- 1: incomplete exit (e.g., max iterations / no-progress)
- 2: iteration failed (non-zero return, gate failure, judge failure, or review BLOCK)
```

---

## Consequences

### Positive

1. **No more infinite loops** - Clean exit when tasks are blocked/done
2. **Clear error messages** - Users know why the loop exited
3. **Meaningful exit codes** - Scripts can distinguish success/failure/error
4. **Saves API credits** - No wasted iterations

### Negative

1. **Behavior change** - Existing scripts may expect infinite loop (unlikely)
2. **Requires tracker methods** - `all_done()` and `all_blocked()` must exist

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
    pass

def all_blocked(self) -> bool:
    """Return True if all remaining tasks are marked as blocked."""
    pass
```

**Status Check:**
- `all_done()` - Need to verify if exists
- `all_blocked()` - Need to verify if exists, may need to be added

### Testing

Test cases:
1. All tasks done → Exit code 0
2. All tasks blocked → Exit code 1
3. Mixed states (should not reach this code)
4. Tracker methods missing → Graceful fallback

---

## Alternatives Considered

### Alternative 1: Keep Current Logic (REJECTED)

**Idea:** Keep requiring both `story_id is None AND exit_signal is True`

**Why Rejected:** This causes the infinite loop bug we're trying to fix.

### Alternative 2: Always Exit on story_id=None (REJECTED)

**Idea:** Exit immediately when `story_id is None`, regardless of reason

**Why Rejected:** Doesn't distinguish between "all done" (success) and "all blocked" (failure). We need different exit codes.

### Alternative 3: Add New Exit Code for Blocked (REJECTED)

**Idea:** Use exit code 3 for "all blocked"

**Why Rejected:** Exit code 1 already means "incomplete," which includes blocked tasks. No need for a new code.

---

## References

- `src/ralph_gold/loop.py:2462` - Current exit logic
- `.ralph/GOLD_STANDARD_FIXES.md` - Bug report
- `README.md` - Exit code documentation

---

**Author:** Claude Code (adversarial review)
**Reviewers:** [Pending]
**Approval:** [Pending]
