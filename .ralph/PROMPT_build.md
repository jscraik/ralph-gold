You are operating inside the Ralph Gold loop.

## CRITICAL: You MUST write code, not plans

**DO NOT** just describe what needs to be done.
**DO NOT** just list steps or create an implementation plan.
**YOU MUST** actually edit files, write code, run tests, and commit changes.

## Rules

- Do exactly ONE task per iteration.
- Use the Memory Files below as the source of truth (especially ANCHOR and any Repo Prompt context pack).
- Make the smallest correct change-set that satisfies the task acceptance criteria.
- When you finish the task, mark it done in the PRD tracker.
- Do not mark tasks done if you did not run/confirm the configured gates pass locally.
- If you are blocked, record a clear reason (including commands + errors) in .ralph/progress.md and leave the task open.

## Workflow

1) Read Memory Files in order.
2) Re-state the task acceptance criteria.
3) **IMPLEMENT** - Edit actual files, write actual code, create actual tests.
4) Run the repo's gates (see .ralph/AGENTS.md) and fix failures.
5) Update PRD + progress.
6) Commit your changes with `git add -A && git commit -m "message"`.

## What "IMPLEMENT" means

- Edit `src/ralph_gold/config.py` to add dataclasses
- Edit `src/ralph_gold/loop.py` to add logic
- Create `tests/test_*.py` files with actual test functions
- Run `uv run pytest -q` to verify tests pass
- Use file editing tools to make changes
- DO NOT just describe the changes

## Output format

- Show the actual commands you ran: `uv run pytest -q tests/test_config.py`
- Show the actual file edits you made
- Show test results
- Prefer concise, factual updates.

## Example of GOOD output

```
Edited src/ralph_gold/config.py:
- Added LoopModeConfig dataclass
- Added mode field to LoopConfig

Created tests/test_config_loop_modes.py:
- test_loop_modes_config()
- test_mode_defaults()

Ran: uv run pytest -q tests/test_config_loop_modes.py
Result: 2 passed in 0.5s

Updated PRD.md: marked task 1 as done
Committed changes
```

## Example of BAD output (DO NOT DO THIS)

```
The implementation will:
1. Add LoopModeConfig dataclass
2. Parse loop.modes.* sections
3. Provide safe defaults

EXIT_SIGNAL: false
```

This is just planning. You must actually DO the work, not describe it.
