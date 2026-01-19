# Gold Standard Fixes for Ralph Loop Issues

## Executive Summary

After 93 iterations across multiple runs, we identified critical bugs preventing Ralph from completing tasks. This document provides gold standard fixes that MUST be implemented.

## Critical Bugs Identified

### 1. Claude Runner Configuration Bug (CRITICAL - BLOCKS ALL CLAUDE RUNS)

**Problem:** Claude runner uses incompatible flags

```toml
# BROKEN (current)
[runners.claude]
argv = ["claude", "--output-format", "stream-json", "-p"]
```

**Error:** `Error: When using --print, --output-format=stream-json requires --verbose`

**Gold Standard Fix:**

```toml
[runners.claude]
argv = ["claude", "-p", "--output-format", "text"]
```

**Why:** Claude CLI doesn't support `stream-json` with `-p` flag. Use `text` format instead.

**Files to fix:**

- `src/ralph_gold/templates/ralph.toml` (template for new projects)
- `.ralph/ralph.toml` (current project)

**Test:** `echo "test" | claude -p --output-format text` should work

---

### 2. story_id=None Infinite Loop Bug (CRITICAL - WASTES ITERATIONS)

**Problem:** When all tasks are blocked/done, Ralph loops indefinitely with `story_id=None` instead of exiting cleanly.

**Evidence:** 42 wasted iterations (52-93) with `story_id=None rc=1`

**Gold Standard Fix:**

```python
# In src/ralph_gold/loop.py, after task selection:

def run_loop(cfg, ...):
    for iteration in range(max_iterations):
        # ... existing code ...
        
        # Get next task
        task = tracker.next_task()
        
        # CRITICAL: Exit cleanly when no tasks available
        if task is None:
            all_done = tracker.all_tasks_done()
            all_blocked = tracker.all_tasks_blocked()
            
            if all_done:
                logger.info("All tasks completed successfully")
                return 0  # Success
            elif all_blocked:
                logger.error("All remaining tasks are blocked")
                return 1  # Failure
            else:
                logger.error("No task selected but tasks remain")
                return 2  # Configuration error
        
        # ... continue with task execution ...
```

**Acceptance Criteria:**

- Exit code 0 when all tasks done
- Exit code 1 when all tasks blocked
- Exit code 2 when no task but tasks remain (config error)
- No iterations with `story_id=None`

**Test:** Create PRD with all blocked tasks, verify loop exits immediately

---

### 3. Status Command Counts Blocked Tasks as Done (CRITICAL - MISLEADING)

**Problem:** `ralph status` reports "13/13 tasks done" when actually "3 done, 10 blocked"

**Evidence:**

```bash
$ ralph status
Progress: 13/13 tasks done  # WRONG

$ grep -E "^- \[x\]" .ralph/PRD.md | wc -l
3  # CORRECT

$ grep -E "^- \[-\]" .ralph/PRD.md | wc -l
10  # These are BLOCKED, not done
```

**Gold Standard Fix:**

```python
# In src/ralph_gold/tracker.py or wherever status is calculated:

def get_progress_summary(self):
    """Return accurate task counts."""
    total = len(self.tasks)
    done = len([t for t in self.tasks if t.status == 'done'])  # [x]
    blocked = len([t for t in self.tasks if t.status == 'blocked'])  # [-]
    open_tasks = len([t for t in self.tasks if t.status == 'open'])  # [ ]
    
    return {
        'total': total,
        'done': done,  # Only count [x] as done
        'blocked': blocked,
        'open': open_tasks,
        'progress_pct': (done / total * 100) if total > 0 else 0
    }
```

**Display Format:**

```
Progress: 3/13 done (10 blocked, 0 open)
```

**Test:** Block all tasks, verify status shows "0/N done (N blocked)"

---

### 4. Tasks Too Complex for Single Iteration (HIGH PRIORITY)

**Problem:** 10/13 tasks blocked because they're too large for agents to complete in one iteration.

**Evidence:** Tasks like "Implement smart gate selection" have 4+ acceptance criteria requiring multiple file edits, tests, and integration.

**Gold Standard Fix:** Break tasks into atomic units

**BAD (current):**

```markdown
- [ ] Implement smart gate selection (config + runtime)
  - Add `gates.smart.enabled` and `gates.smart.skip_gates_for` in config parsing.
  - Use `git diff --name-only HEAD` to compute changed files.
  - Skip gates when all changed files match patterns.
  - `uv run pytest -q tests/test_smart_gates.py` passes.
```

**GOOD (atomic):**

```markdown
- [ ] Add SmartGateConfig dataclass to config.py
  - Add `SmartGateConfig` with `enabled: bool` and `skip_gates_for: List[str]` fields.
  - Add `smart: SmartGateConfig` to `GatesConfig`.
  - Parse `[gates.smart]` section in `load_config()`.
  - Test: `uv run pytest -q tests/test_config_smart_gates.py -k test_parse` passes.

- [ ] Implement changed file detection for smart gates
  - Add `get_changed_files()` function in `src/ralph_gold/gates.py`.
  - Use `git diff --name-only HEAD` with graceful fallback if git unavailable.
  - Return empty list on error (fail-open for safety).
  - Test: `uv run pytest -q tests/test_gates.py -k test_changed_files` passes.

- [ ] Implement smart gate filtering logic
  - Add `should_skip_gates(changed_files, patterns)` function.
  - Use `fnmatch` to match files against patterns.
  - Skip only if ALL changed files match skip patterns.
  - Test: `uv run pytest -q tests/test_gates.py -k test_skip_logic` passes.

- [ ] Integrate smart gates into loop execution
  - Call smart gate check before running gates in `loop.py`.
  - Log skip reason when gates are skipped.
  - Record skip decision in iteration receipts.
  - Test: `uv run pytest -q tests/test_loop_smart_gates.py` passes.
```

**Rules for Atomic Tasks:**

- One file edit OR one function OR one test file per task
- 5-15 minutes of work maximum
- Single, specific acceptance criterion
- One test command that tests ONLY this task

---

### 5. Prompt Template Needs Stronger Implementation Emphasis (MEDIUM)

**Problem:** Even with "CRITICAL: write code" section, agents sometimes plan instead of implement.

**Gold Standard Enhancement:**

```markdown
# At the top of PROMPT_build.md:

## CRITICAL: You MUST write code, not plans

**STOP** - Before you respond, ask yourself:
1. Am I about to describe what I will do? ❌ WRONG
2. Am I about to list implementation steps? ❌ WRONG  
3. Am I about to show actual file edits? ✅ CORRECT

**YOU MUST:**
- Use `fsWrite` or `strReplace` tools to edit files
- Use `executeBash` to run commands
- Show actual test output
- Commit changes with git

**YOU MUST NOT:**
- Say "I will add..." (just add it!)
- Say "The implementation will..." (just implement it!)
- Describe changes without making them

## Workflow (DO THIS EVERY TIME)

1. Read ANCHOR for task acceptance criteria
2. Edit the actual file (use fsWrite/strReplace)
3. Create the actual test file (use fsWrite)
4. Run the actual test (use executeBash)
5. Fix failures (repeat 2-4 until passing)
6. Update PRD.md (mark task [x])
7. Commit (use executeBash: git add -A && git commit -m "...")
8. Output: "Task N complete. Test passed. Committed."

## Example of CORRECT output

```

Used strReplace on src/ralph_gold/config.py:

- Added SmartGateConfig dataclass

Used fsWrite to create tests/test_config_smart_gates.py:

- Added test_parse_smart_gate_config()

Ran: uv run pytest -q tests/test_config_smart_gates.py
Output: 1 passed in 0.3s

Updated .ralph/PRD.md: marked task 4 as [x]

Ran: git add -A && git commit -m "Add SmartGateConfig parsing"
Output: [main abc1234] Add SmartGateConfig parsing

EXIT_SIGNAL: true

```

## Example of WRONG output (DO NOT DO THIS)

```

To complete this task, I will:

1. Add SmartGateConfig to config.py
2. Parse the [gates.smart] section
3. Add tests

The implementation will include...

EXIT_SIGNAL: false

```

**This is planning. You must DO the work, not describe it.**
```

---

### 6. PRD Template Needs Task Breakdown Guidance (HIGH)

**Problem:** Default PRD template has vague tasks like "Define structure", "Implement feature" that agents can't complete.

**Gold Standard Fix:**

```markdown
# In src/ralph_gold/templates/PRD.md:

# PRD: [Project Name]

## Overview

(3-8 sentences describing what you want built)

## Task Breakdown Guidelines

**CRITICAL:** Tasks must be atomic (5-15 minutes each) with specific acceptance criteria.

### ✅ GOOD Task Example

- [ ] Add UserConfig dataclass to config.py
  - Add `UserConfig` with `name: str` and `email: str` fields
  - Add `user: UserConfig` to main `Config` class
  - Parse `[user]` section in `load_config()`
  - Test: `uv run pytest -q tests/test_config.py -k test_user_config` passes

**Why good:** One file, one change, one test, clear acceptance

### ❌ BAD Task Example

- [ ] Implement user management
  - Add user configuration
  - Create user database
  - Add authentication
  - Add user API endpoints

**Why bad:** Multiple files, vague scope, no specific tests, 2+ hours of work

## Tasks

- [ ] [Your first atomic task here]
  - [Specific acceptance criterion 1]
  - [Specific test command]

- [ ] [Your second atomic task here]
  - [Specific acceptance criterion 1]
  - [Specific test command]

## Notes

- Mark done: `- [x] ...`
- Mark blocked: `- [-] ...`
- Dependencies: Add acceptance bullet like `- Depends on: 1, 2`
```

---

## Implementation Priority

1. **IMMEDIATE (blocks all work):**
   - Fix Claude runner config (5 minutes)
   - Fix story_id=None loop bug (30 minutes)

2. **HIGH (prevents task completion):**
   - Fix status command counting (15 minutes)
   - Break down all blocked tasks into atomic units (2 hours)

3. **MEDIUM (improves success rate):**
   - Enhance prompt template (30 minutes)
   - Update PRD template (30 minutes)

## Testing Checklist

After implementing fixes:

- [ ] `echo "test" | claude -p --output-format text` works
- [ ] Loop exits cleanly when all tasks blocked (no story_id=None iterations)
- [ ] `ralph status` shows correct done/blocked counts
- [ ] Sample atomic task completes in one iteration
- [ ] Agent writes actual code, not plans
- [ ] New PRD from template has atomic tasks

## Success Metrics

- **Before fixes:** 3/13 tasks completed, 10 blocked, 93 iterations, 42 wasted
- **After fixes target:** 13/13 tasks completed, 0 blocked, <30 iterations, 0 wasted

## Files to Modify

1. `src/ralph_gold/templates/ralph.toml` - Fix Claude runner
2. `.ralph/ralph.toml` - Fix Claude runner (current project)
3. `src/ralph_gold/loop.py` - Add story_id=None exit logic
4. `src/ralph_gold/tracker.py` - Fix status counting
5. `.ralph/PROMPT_build.md` - Enhance implementation emphasis
6. `src/ralph_gold/templates/PRD.md` - Add task breakdown guidance
7. `.ralph/PRD.md` - Break down all blocked tasks into atomic units

## Validation Commands

```bash
# 1. Test Claude runner
echo "test" | claude -p --output-format text

# 2. Test loop exit (create test PRD with all blocked tasks)
ralph run --agent claude  # Should exit immediately, not loop

# 3. Test status accuracy
ralph status  # Should show "X/Y done (Z blocked)"

# 4. Test atomic task completion
# Create PRD with one atomic task, run loop, verify completion in 1 iteration

# 5. Run full test suite
uv run pytest -q
```

## Notes

- All fixes follow "fight entropy" philosophy - make the codebase better
- Fixes are minimal, focused, and testable
- No breaking changes to existing functionality
- Backward compatible with existing PRDs
