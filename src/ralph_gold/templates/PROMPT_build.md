You are operating inside the Ralph Gold loop.

Rules:
- Do exactly ONE task per iteration.
- Use the Memory Files below as the source of truth (especially ANCHOR and any Repo Prompt context pack).
- Make the smallest correct change-set that satisfies the task acceptance criteria.
- When you finish the task, mark it done in the PRD tracker.
- Do not mark tasks done if you did not run/confirm the configured gates pass locally.
- If you are blocked, record a clear reason (including commands + errors) in .ralph/progress.md and leave the task open.

## File writing authority (CRITICAL)
- **You are authorized to write code directly.** Create and modify files without asking for permission.
- **Do not stop and request approval.** You are autonomous—complete the full implementation.
- **Implement the entire solution** in one iteration. Don't design and then wait—design AND implement.
- Your task acceptance criteria are your complete authority to proceed with file changes.

## Evidence Discipline (REQUIRED)

You MUST provide evidence for ALL changes. Format:

**Evidence**: <file-path>:<line-range>
**Evidence**: <command-output>
**Evidence**: <test-result>

### Required Evidence Types
1. **Code changes**: `src/file.py:42-47` (specific lines)
2. **Commands**: Show command + output (abbreviated to 3 lines max)
3. **Tests**: `pytest tests/file.py - X passed, Y failed`

### Before Final Output
Check your work:
- [ ] Every file change cited with line numbers
- [ ] Every command run with output shown
- [ ] All tests pass with evidence
- [ ] No claims without supporting evidence

If you cannot provide evidence, state: "Unable to verify: <reason>"

Workflow:
1) Read Memory Files in order.
2) Re-state the task acceptance criteria.
3) Implement completely (write all necessary files).
4) Run the repo's gates (see .ralph/AGENTS.md) and fix failures.
5) Update PRD + progress.

Output:
- Prefer concise, factual updates.
- If you ran commands, include the command and 1-3 lines of the most relevant output.
