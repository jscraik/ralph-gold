# Ralph-Gold Improvement Suggestions

Based on session 2026-03-02 where 10 tasks were completed and 7 blocked tasks were found to be already done.

## Summary

| Issue | Impact | Frequency |
|-------|--------|-----------|
| Agents complete work but don't mark PRD done | High | 7/8 blocked tasks |
| Blocked state doesn't sync with PRD status | Medium | Stale entries persist |
| No automatic verification of task completion | High | False blocks |
| Agents introduce syntax errors | Critical | 1/10 iterations |

## Root Cause Analysis

### 1. Agent Doesn't Mark PRD Done (Critical)

**Problem:** Agents run successfully (`return_code: 0`, files written) but fail to update the PRD `[ ]` → `[x]` checkbox.

**Evidence:**
- Tasks 6-9: Code exists in `loop.py`, tests pass, but PRD still showed `[-]` (blocked)
- Task had `runner_ok: true` but wasn't marked complete

**Why it happens:**
1. Agent reaches end of prompt context before updating PRD
2. Agent thinks "work is done" and exits with success signal
3. Ralph detects no PRD change and counts as incomplete

**Recommended fixes:**

```toml
# Option A: Gate that requires PRD update
[gates.prd_update]
enabled = true
check_command = "git diff --exit-code .ralph/PRD.md"
failure_message = "Task must update PRD status checkbox"

# Option B: Post-iteration PRD sync
[loop]
auto_sync_prd = true  # If files changed but PRD unchanged, prompt agent to update
```

### 2. Blocked State Desynchronizes from PRD (Medium)

**Problem:** `state.json` stores blocked tasks independently of PRD content. When PRD is manually fixed, state remains stale.

**Evidence:**
- Tasks 1-3, 6-9 marked done in PRD but still in `state.json["blocked_tasks"]`
- `ralph blocked` showed 8 tasks when only 1 was actually blocked

**Recommended fixes:**

```python
# In loop.py or prd.py
def sync_blocked_state(prd_path: Path, state_path: Path) -> None:
    """Remove blocked entries for tasks that are now done in PRD."""
    prd_tasks = parse_prd_tasks(prd_path)
    state = load_state(state_path)

    for task_id in list(state.get("blocked_tasks", {}).keys()):
        if prd_tasks.get(task_id, {}).get("status") == "done":
            del state["blocked_tasks"][task_id]

    save_state(state_path, state)
```

### 3. No Automatic Completion Verification (High)

**Problem:** Ralph trusts agent's `EXIT_SIGNAL` but doesn't verify work was actually done.

**Evidence:**
- Iteration 76: Agent returned `EXIT_SIGNAL: true` but introduced syntax errors
- Multiple iterations: Agent claimed success but didn't update PRD

**Recommended fixes:**

```toml
[loop]
# Require gates to pass before accepting completion
require_gates_for_completion = true

# Verify PRD was updated
require_prd_update = true

# Run syntax check on modified files
syntax_check_command = "python -m py_compile"
```

### 4. Syntax Errors from Agent Edits (Critical)

**Problem:** Gemini introduced literal newlines in strings, breaking Python syntax.

**Evidence:**
- `loop.py:3419` had `anchor_text + "\n"` split across lines as actual newline
- Required `git restore` to recover

**Recommended fixes:**

```toml
[gates.syntax]
enabled = true
commands = [
    "python -m py_compile src/ralph_gold/*.py",
    "ruff check src/ralph_gold/"
]
```

## Quick Wins

### 1. Add `ralph sync` command

```bash
ralph sync  # Reconcile state.json with PRD, remove stale blocks
```

### 2. Add `ralph unblock <task_id>` command

```bash
ralph unblock 6  # Clear blocked status for a task
```

### 3. Enable auto-commit by default

Current session showed auto-commit prevents catastrophic loss when syntax errors occur.

### 4. Add PRD gate

Before accepting task as complete, verify PRD checkbox changed from `[ ]` to `[x]`.

## Implementation Priority

| Priority | Fix | Effort |
|----------|-----|--------|
| P0 | Add syntax check gate | Low |
| P0 | Enable auto-commit by default | Trivial |
| P1 | Add `ralph sync` command | Medium |
| P1 | Add PRD update gate | Medium |
| P2 | Auto-detect completed work (file changes) | High |
| P2 | Blocked state auto-sync | Medium |

## Session Stats

- **Tasks completed:** 10 (iter 66-75)
- **False blocks fixed:** 7 (tasks done but not marked)
- **Real blocks:** 1 (task 20 - batch execution)
- **Syntax errors:** 1 (fixed with git restore)
- **Progress:** 14% → 53% (+39%)
