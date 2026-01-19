# ADR 0002: Task State Reporting and Progress Display

**Status:** Proposed
**Date:** 2026-01-19
**Context:** Status command accuracy and task state semantics
**Related:** PRD spec-2026-01-19-critical-bug-fixes

---

## Context

The `ralph status` command currently reports blocked tasks as "done," misleading users about actual progress. This happens because the status calculation doesn't distinguish between "completed" (`[x]`) and "blocked" (`[-]`) tasks.

**Current Behavior:**
```
$ ralph status
Progress: 13/13 tasks done  # WRONG - actually 3 done, 10 blocked
```

**Actual State in PRD.md:**
```markdown
- [x] 1. Done task
- [x] 2. Done task
- [x] 3. Done task
- [-] 4. Blocked task  (depends on nonexistent)
- [-] 5. Blocked task
...
```

**Problem:** Users think they're done when they're actually blocked.

---

## Decision

### Task State Semantics

We define three distinct task states:

| State | Checkbox | Meaning | Counted As |
|-------|----------|---------|------------|
| **Done** | `[x]` | Task completed and verified | "Done" |
| **Blocked** | `[-]` | Task cannot proceed (dependencies/ blockers) | "Blocked" |
| **Open** | `[ ]` | Task ready to be worked on | "Open" |

### Progress Calculation

```python
def get_progress_summary(self) -> ProgressSummary:
    """
    Calculate accurate task counts by state.

    Returns:
        ProgressSummary with total, done, blocked, open, and percentage
    """
    total = len(self.tasks)
    done = len([t for t in self.tasks if t.status == 'done'])      # [x]
    blocked = len([t for t in self.tasks if t.status == 'blocked']) # [-]
    open = len([t for t in self.tasks if t.status == 'open'])       # [ ]

    return ProgressSummary(
        total=total,
        done=done,
        blocked=blocked,
        open=open,
        progress_pct=(done / total * 100) if total > 0 else 0
    )
```

### Display Format

**New Format:**
```
Progress: 3/13 done (10 blocked, 0 open)
```

**Components:**
- `3/13 done` - Actual completed tasks
- `(10 blocked, 0 open)` - Additional state breakdown in parentheses

**Benefits:**
- Clear distinction between done and blocked
- Helps users identify blocking issues
- Prevents false sense of completion

---

## Consequences

### Positive

1. **Accurate reporting** - Users see true progress
2. **Debugging aid** - Blocked tasks are visible
3. **No false completion** - Clear when work remains
4. **Actionable** - Users know to unblock tasks

### Negative

1. **Breaking change** - Scripts parsing status may need updates
2. **Longer output** - More information per line

### Mitigations

1. **JSON format** - Add `--format json` for script compatibility
2. **Migration guide** - Document format change in changelog
3. **Backward compat** - Consider `--format old` flag if needed

---

## Implementation

### File Locations (To Be Determined)

The status calculation happens in one of these locations (needs verification):
- `src/ralph_gold/prd.py` - PRD parsing and status
- `src/ralph_gold/trackers/base.py` - Base tracker class
- `src/ralph_gold/trackers/markdown.py` - Markdown tracker
- `src/ralph_gold/cli.py` - Status command

**Action:** Inspect code to find exact location before implementing.

### Changes Required

1. **Update progress calculation** - Separate counts for done/blocked/open
2. **Update display format** - Show all three states
3. **Add tests** - Verify accuracy with mixed states
4. **Update docs** - Document new format

---

## Testing

### Test Cases

1. **All Done**
   ```
   Input: 5 tasks, all [x]
   Output: 5/5 done (0 blocked, 0 open)
   ```

2. **All Blocked**
   ```
   Input: 10 tasks, all [-]
   Output: 0/10 done (10 blocked, 0 open)
   ```

3. **Mixed States**
   ```
   Input: 13 tasks (3 [x], 10 [-], 0 [ ])
   Output: 3/13 done (10 blocked, 0 open)
   ```

4. **Empty PRD**
   ```
   Input: 0 tasks
   Output: 0/0 done (0 blocked, 0 open)
   ```

### Unit Tests

```python
def test_status_counts_blocked_separately():
    tracker = MarkdownTracker(prd_with_mixed_states)
    summary = tracker.get_progress_summary()

    assert summary.done == 3
    assert summary.blocked == 10
    assert summary.open == 0
    assert summary.total == 13
```

---

## Alternatives Considered

### Alternative 1: Keep Current Behavior (REJECTED)

**Idea:** Continue counting blocked tasks as "done"

**Why Rejected:** Misleads users, masks problems, defeats purpose of status tracking.

### Alternative 2: Add Separate "Blocked" Command (REJECTED)

**Idea:** Keep `status` as-is, add `ralph blocked` command

**Why Rejected:** Fragments UX, users expect comprehensive status in one place.

### Alternative 3: Show Detailed Task List (REJECTED)

**Idea:** Always show full task list in status

**Why Rejected:** Too verbose for quick status checks. Summary line + optional detail is better.

---

## Display Mockups

### Terminal Output

```
$ ralph status

============================================================
Ralph Gold Status
============================================================

Progress: 3/13 done (10 blocked, 0 open)  [███░░░░░░░░░] 23%

Tasks:
  ✓ 3 completed
  ✗ 10 blocked
  ○ 0 open

Most Recent Iteration:
  Iteration: 52
  Task: None (no task selected)
  Exit Signal: false
  Status: Failed

============================================================
```

### JSON Output

```json
{
  "progress": {
    "total": 13,
    "done": 3,
    "blocked": 10,
    "open": 0,
    "percentage": 23.08
  },
  "last_iteration": {
    "iteration": 52,
    "task_id": null,
    "exit_signal": false
  }
}
```

---

## References

- `.ralph/GOLD_STANDARD_FIXES.md` - Original bug report
- `src/ralph_gold/prd.py` - PRD parsing (likely location)
- `src/ralph_gold/cli.py` - Status command (likely location)

---

**Author:** Claude Code (adversarial review)
**Reviewers:** [Pending]
**Approval:** [Pending]
