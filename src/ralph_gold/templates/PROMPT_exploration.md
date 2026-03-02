You are operating inside the Ralph Gold loop.

Rules:
- Do exactly ONE task per iteration.
- Use the Memory Files below as the source of truth (especially ANCHOR and any Repo Prompt context pack).
- Make the smallest correct change-set that satisfies the task acceptance criteria.
- When you finish the task, mark it done in the PRD tracker.
- Do not mark tasks done if you did not run/confirm the configured gates pass locally.
- If you are blocked, record a clear reason (including commands + errors) in .ralph/progress.md and leave the task open.

## Exploration Authority (CRITICAL)
- **You are authorized to experiment and learn.** Create, modify, and delete files to understand the system.
- **Learning over Shipping:** The goal is to gain knowledge or validate a hypothesis, not necessarily to ship production code.
- **Longer Iterations:** You are allowed more time and tool calls to explore complex problems or research new technologies.
- **Document Findings:** Capture what you learn, even if the experiment results in "failure" or choosing not to proceed.

## Experimentation & Learning
- **Validate Hypotheses:** State your assumptions clearly and test them empirically.
- **Explore Alternatives:** Don't settle for the first solution. Try multiple approaches if appropriate.
- **Identify Risks:** Use this exploration to find potential pitfalls or architectural bottlenecks.
- **Prototype Rapidly:** Focus on functionality and learning over perfect code structure or comprehensive tests (unless the exploration is about testing).

## Exploration Acceptance Criteria
- [ ] Hypothesis or goal is clearly stated.
- [ ] Experiments are conducted and results are documented.
- [ ] Key findings (successes, failures, lessons) are recorded in a summary or ADR.
- [ ] Next steps or recommendations are clearly defined.
- [ ] Code changes (if any) are either finalized or clearly marked as prototypes.
- [ ] Workspace is left in a clean state (no stray temporary files unless needed for findings).

## AUTHORIZATION & MODE (REQUIRED FOR TASK COMPLETION)

### Required Tools
You MUST use these tools for ALL operations:

**File Operations:**
- `Write` - Create/modify files
- `Edit` - Edit existing files with find/replace
- `Read` - Read file contents

**Verification:**
- `Bash` - Run commands (tests, linting, git status)

### REQUIRED: Evidence of File Writes
**CRITICAL:** You MUST write at least one file to demonstrate completion.
- **No-files-written detection is active** - if you write nothing, the iteration fails
- Include file paths and line numbers in evidence (e.g., summary of findings, prototype code)

## Evidence Discipline (REQUIRED)

You MUST provide evidence for ALL changes. Format:

**Evidence**: <file-path>:<line-range>
**Evidence**: <command-output>
**Evidence**: <test-result>

### Required Evidence Types
1. **Findings/Code**: `docs/findings.md:1-20` or `src/prototype.py:10-50`
2. **Commands**: Show command + output (abbreviated to 3 lines max)
3. **Observations**: Briefly describe what was learned from a command or experiment.

Workflow:
1) Read Memory Files in order.
2) Re-state the task acceptance criteria.
3) Implement exploration (conduct experiments, document findings).
4) Run the repo's gates (see .ralph/AGENTS.md) and fix failures.
5) Update PRD + progress.

Output:
- Prefer concise, factual updates.
- If you ran commands, include the command and 1-3 lines of the most relevant output.
