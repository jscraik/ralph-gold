# Root Cause Analysis: Agents Planning Instead of Implementing

## Problem

Ralph loop ran for 11 iterations with 0 code commits. Tasks 1-3 were blocked after 3 attempts each because the agent (Claude) kept describing implementation plans instead of actually writing code.

## Root Cause

The `.ralph/PROMPT_build.md` template was too minimal (only 17 lines) and lacked explicit instructions to WRITE CODE rather than describe plans.

## Evidence

From `.ralph/logs/20260119T094119Z-iter0004-claude.log`:

```
To proceed with Task 1 (Add loop mode config schema + parsing), I need to:
1. Add `LoopModeConfig` dataclass...
2. Extend `LoopConfig`...

The implementation will:
- Provide safe defaults...
- Allow incomplete mode definitions...

EXIT_SIGNAL: false
```

This is pure planning with no file edits, no test creation, no commands run.

## Fix Applied

Updated `.ralph/PROMPT_build.md` with:

1. **CRITICAL section** at the top: "You MUST write code, not plans"
2. **Clear workflow**: Edit files → Write code → Create tests → Run commands → Commit
3. **Explicit examples** of GOOD vs BAD output
4. **Emphasis on using file editing tools** to make actual changes

## Prevention

The improved prompt template now makes it impossible to misunderstand:

- "DO NOT just describe what needs to be done"
- "DO NOT just list steps or create an implementation plan"
- "YOU MUST actually edit files, write code, run tests, and commit changes"

## Next Steps

1. ✅ Unblocked tasks 1-3 (changed from `[-]` to `[ ]` in PRD.md)
2. Restart loop: `ralph run --agent codex` (codex may be better for implementation)
3. Monitor first iteration to ensure agent actually writes code
4. If still planning, consider adding even more explicit examples

## Lessons Learned

- Prompt templates need to be EXTREMELY explicit about expected behavior
- "Implement" is ambiguous - agents may interpret it as "describe implementation"
- Examples of good/bad output are critical for disambiguation
- The EXIT_SIGNAL protocol was working correctly - the issue was agent behavior
