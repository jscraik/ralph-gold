<div align="center">
  <img src="docs/assets/ralph-brand-logo.png" alt="Ralph Gold Logo" width="400"/>
</div>

# ralph-gold (uv-first)

A Golden Ralph Loop orchestrator that runs fresh CLI-agent sessions (Codex, Claude Code, Copilot) in a deterministic loop, using the repo filesystem as durable memory.

Doc requirements:

- Audience: users and contributors (intermediate CLI + git experience)
- Scope: installing, configuring, and operating the loop; contributor workflow; support/security paths
- Owner: jscraik
- Review cadence: quarterly or when CLI behavior changes
- Last updated: 2026-01-15

## TL;DR

The problem: agent runs drift without durable state, reproducible gates, or exit rules.

The solution: a loop that selects one task per iteration, runs gates, logs state to disk, and only exits when the tracker is complete and the agent says it is done.

Why use ralph-gold:

- File-based memory under `.ralph/` keeps state and logs deterministic.
- Runner-agnostic invocation with stdin-first prompt handling.
- Optional TUI and VS Code bridge for operator visibility.
- Receipts + context snapshots per iteration for auditability and review.
- Optional review gate to require a final `SHIP` decision before exit.

---

## Quickstart

```bash
uv tool install -e .
ralph init
ralph step --agent codex
```

## Prerequisites

- git
- uv
- At least one agent CLI (`codex`, `claude`, or `copilot`)
- Optional: `prek` (universal gate runner)
- Optional: `rp-cli` (RepoPrompt context packs and review backend)

## Install (with uv)

```bash
uv tool install -e .
uv tool update-shell   # optional: add uv tool bin dir to PATH
```

Verify:

```bash
ralph --help
```

---

## Initialize a repo

From your project root:

```bash
ralph init
```

This creates the recommended default layout:

- `.ralph/ralph.toml` (config)
- `.ralph/PRD.md` (task tracker, Markdown)
- `.ralph/AGENTS.md` (build/test/run commands for your repo)
- `.ralph/progress.md` (append-only progress log)
- `.ralph/specs/` (requirement specs)
- `.ralph/PROMPT_build.md` / `.ralph/PROMPT_plan.md` / `.ralph/PROMPT_judge.md` / `.ralph/PROMPT_review.md`
- `.ralph/FEEDBACK.md` (operator feedback + review notes)
- `.ralph/logs/` (per-iteration logs)
- `.ralph/receipts/` (command receipts per iteration)
- `.ralph/context/` (anchor/context snapshots per iteration)
- `.ralph/attempts/` (attempt records per task)
- `.ralph/state.json` (session state)

You can switch trackers by changing `files.prd` in `.ralph/ralph.toml`.

**Re-initializing with `--force`:** If you need to reset your `.ralph` directory, use `ralph init --force`. This automatically archives existing files to `.ralph/archive/<timestamp>/` before creating fresh templates, preventing accidental data loss. See [docs/INIT_ARCHIVING.md](docs/INIT_ARCHIVING.md) for details.

---

## Run the loop

Run N iterations:

```bash
ralph run --agent codex --max-iterations 10
```

Exit codes:

- 0: loop completed successfully (EXIT_SIGNAL true, gates/judge/review ok)
- 1: loop ended without a successful exit (e.g., max iterations / no-progress)
- 2: one or more iterations failed (non-zero return code, gate failure, judge failure, or review BLOCK)

Run a single iteration:

```bash
ralph step --agent claude
```

Run a single iteration with interactive task selection:

```bash
ralph step --interactive
```

In interactive mode, you'll see a list of available tasks and can:

- Select a task by number
- Search/filter tasks with `s <keyword>`
- View task details with `d <number>`
- Clear search filter with `c`
- Quit without selecting with `q`

Show status:

```bash
ralph status
```

Logs are written under `.ralph/logs/`.

Receipts and context snapshots (anchor + optional RepoPrompt pack) live under:

- `.ralph/receipts/`
- `.ralph/context/`

---

## TUI (interactive control surface)

```bash
ralph tui
```

Keys:

- `s` step once
- `r` run `loop.max_iterations` iterations
- `a` cycle agent
- `p` pause/resume (between iterations)
- `q` quit

---

## Branch automation

Enable in `.ralph/ralph.toml`:

```toml
[git]
branch_strategy = "per_prd"   # per_prd|none
branch_prefix = "ralph/"
auto_commit = true
amend_if_needed = true
```

Add PRD metadata:

### Markdown (`.ralph/PRD.md`)

Put near the top:

```md
Branch: ralph/my-feature
```

### JSON (`.ralph/prd.json`)

Use:

```json
{"branchName": "ralph/my-feature", "stories": [...]}
```

If no branch is specified, a fallback branch is generated from the repo name using `branch_prefix`.

---

## Review gate (optional)

Enable a cross-model review that must end with `SHIP`:

```toml
[gates.review]
enabled = true
backend = "runner" # runner|repoprompt
agent = "claude"
required_token = "SHIP"
```

When enabled, `ralph run` will not exit until the review returns `SHIP`.

---

## Codex prompt transport (fix)

`codex exec --full-auto` expects the prompt via **stdin** (or an explicit prompt argument).

Default runner config in `.ralph/ralph.toml` uses:

```toml
[runners.codex]
argv = ["codex", "exec", "--full-auto", "-"]
```

The `-` means "read prompt from stdin".

---

## Tracker plugins

Built-ins:

- **Markdown tracker**: checkbox tasks in `PRD.md`
- **JSON tracker**: `prd.json`
- **YAML tracker**: `tasks.yaml` with parallel execution support

Select via:

```toml
[tracker]
kind = "auto"    # auto|markdown|json|yaml|beads
```

`beads` is supported as an optional tracker (requires the `bd` CLI to be installed).

Blocked tasks:

- Markdown tracker: `[-]` marks a blocked task.
- YAML tracker: set `blocked: true` on a task.

### YAML Tracker

The YAML tracker provides structured task tracking with native parallel execution grouping:

```yaml
version: 1
metadata:
  project: my-app
  branch: ralph/my-feature

tasks:
  - id: 1
    title: Implement authentication API
    group: backend
    completed: false
    acceptance:
      - User can login with email/password
      - JWT token returned on success
      
  - id: 2
    title: Create login UI component
    group: frontend
    completed: false
    acceptance:
      - Login form with email and password fields
      - Error messages displayed on failure
```

**Initialize with YAML:**

```bash
ralph init --format yaml
```

**Convert existing PRD to YAML:**

```bash
# From JSON
ralph convert .ralph/prd.json tasks.yaml

# From Markdown
ralph convert .ralph/PRD.md tasks.yaml

# With automatic group inference
ralph convert .ralph/prd.json tasks.yaml --infer-groups
```

**Benefits:**

- Structured schema with validation
- Parallel execution groups (tasks in different groups can run concurrently)
- Comments support for documentation
- Machine-editable format

See [docs/YAML_TRACKER.md](docs/YAML_TRACKER.md) for complete documentation.

---

## Task Dependencies

Ralph supports task dependencies to enforce execution order. Tasks with unmet dependencies are automatically skipped until their dependencies are completed.

### Defining Dependencies

**Markdown tracker (`PRD.md`):**

Add a `Depends on:` line in the task's acceptance criteria with task numbers:

```markdown
## Tasks

- [ ] 1. Setup database schema
  - Create users table
  - Create posts table

- [ ] 2. Implement user authentication
  - Depends on: 1
  - User can register
  - User can login

- [ ] 3. Create post API
  - Depends on: 1, 2
  - User can create posts
  - User can view their posts
```

**JSON tracker (`prd.json`):**

Add a `depends_on` array with task IDs:

```json
{
  "stories": [
    {
      "id": "1",
      "title": "Setup database schema",
      "acceptance": ["Create users table", "Create posts table"]
    },
    {
      "id": "2",
      "title": "Implement user authentication",
      "depends_on": ["1"],
      "acceptance": ["User can register", "User can login"]
    },
    {
      "id": "3",
      "title": "Create post API",
      "depends_on": ["1", "2"],
      "acceptance": ["User can create posts"]
    }
  ]
}
```

**YAML tracker (`tasks.yaml`):**

Add a `depends_on` list with task IDs:

```yaml
tasks:
  - id: 1
    title: Setup database schema
    completed: false
    
  - id: 2
    title: Implement user authentication
    depends_on: [1]
    completed: false
    
  - id: 3
    title: Create post API
    depends_on: [1, 2]
    completed: false
```

### Visualizing Dependencies

View the dependency graph:

```bash
ralph status --graph
```

Example output:

```
============================================================
Task Dependency Graph
============================================================

Level 0:
  ○ 1
      
Level 1:
  ○ 2
      depends on: 1

Level 2:
  ○ 3
      depends on: 1, 2

============================================================
Total tasks: 3
Total dependencies: 3
============================================================
```

### Circular Dependency Detection

Ralph automatically detects circular dependencies during diagnostics:

```bash
ralph diagnose
```

If circular dependencies are found, you'll see:

```
ERRORS:
  ✗ Found 1 circular dependency cycle(s)
    → Remove circular dependencies to allow tasks to execute
    → Circular dependencies detected:
    → Cycle 1: task-2 → task-3 → task-2
    → Break the cycle by removing one or more 'depends_on' relationships
```

### How It Works

- Tasks are only selected when all their dependencies are marked complete
- The loop automatically skips tasks with unmet dependencies
- Dependencies are checked on every iteration
- Circular dependencies prevent the loop from making progress and must be fixed

---

## Runner configuration

Runners are configured in `.ralph/ralph.toml`.

Prompt transport rules:

- `codex`: if argv contains `-`, prompt is sent via stdin
- `claude`: if argv contains `-p`, prompt is inserted immediately after `-p`
- `copilot`: if argv contains `--prompt`, prompt is inserted immediately after `--prompt`
- You can also use `{prompt}` in argv to inline

---

## Specs checker

```bash
ralph specs check
ralph specs check --strict
```

Uses `files.specs_dir` from config by default.

---

## Troubleshooting

### Diagnostics Command

Run diagnostic checks to validate your Ralph configuration:

```bash
ralph diagnose
```

This command checks:

- Configuration file existence and syntax (`.ralph/ralph.toml`)
- TOML syntax validation
- Configuration schema validation
- Runner configuration
- PRD file existence and format
- PRD structure validation

**Test gate commands:**

```bash
ralph diagnose --test-gates
```

This runs each configured gate command individually to verify they work correctly. Useful for debugging gate failures before running the loop.

**Exit codes:**

- `0`: All diagnostics passed
- `2`: Issues found (errors or warnings)

**Example output:**

```
Ralph Diagnostics Report
============================================================

PASSED:
  ✓ Configuration file found
  ✓ Configuration file ralph.toml has valid TOML syntax
  ✓ Configuration schema is valid
  ✓ Found 2 configured runner(s)
  ✓ PRD file found: PRD.md
  ✓ PRD file has valid markdown format
  ✓ PRD structure is valid (3/10 tasks complete)

============================================================
Summary: 7/7 checks passed

✓ All diagnostics passed!
```

### Statistics Command

View iteration statistics to understand loop performance:

```bash
ralph stats
```

This command displays:

- Total iterations (successful and failed)
- Success rate
- Duration statistics (average, min, max)

**Show per-task breakdown:**

```bash
ralph stats --by-task
```

This shows detailed statistics for each task, including:

- Number of attempts per task
- Success/failure counts
- Average and total duration per task
- Tasks sorted by total duration (slowest first)

**Export to CSV:**

```bash
ralph stats --export stats.csv
```

Exports statistics to a CSV file for analysis in spreadsheet tools or custom scripts. The CSV includes both overall statistics and per-task breakdowns.

**Example output:**

```
============================================================
Ralph Gold - Iteration Statistics
============================================================

Overall Statistics:
  Total Iterations:      15
  Successful:            12
  Failed:                3
  Success Rate:          80.0%

Duration Statistics:
  Average:               245.50s
  Minimum:               120.30s
  Maximum:               450.75s

============================================================
```

**Use cases:**

- Identify slow tasks that need optimization
- Track success rates over time
- Estimate time for remaining work
- Export data for trend analysis

### Snapshot and Rollback Commands

Create git-based snapshots before risky changes and rollback if needed:

**Create a snapshot:**

```bash
ralph snapshot my-snapshot-name
```

Optionally add a description:

```bash
ralph snapshot before-refactor --description "Snapshot before major refactoring"
```

**List all snapshots:**

```bash
ralph snapshot --list
```

**Rollback to a snapshot:**

```bash
ralph rollback my-snapshot-name
```

The rollback command will ask for confirmation before proceeding. To skip confirmation:

```bash
ralph rollback my-snapshot-name --force
```

**How it works:**

- Snapshots use `git stash` to save your working tree state
- Ralph state (`.ralph/state.json`) is backed up separately
- Rollback restores both git state and Ralph state
- Snapshots are stored in `.ralph/snapshots/` with metadata in `state.json`

**Example workflow:**

```bash
# Before making risky changes
ralph snapshot before-experiment -d "Before trying new approach"

# Make changes, run iterations
ralph step --agent codex

# If something goes wrong, rollback
ralph rollback before-experiment

# Or if everything works, continue and the snapshot remains available
```

**Use cases:**

- Create checkpoints before major refactoring
- Save state before experimenting with new approaches
- Quick recovery from failed iterations
- Safe exploration of different solutions

**Notes:**

- Rollback requires a clean working tree (or use `--force`)
- Snapshot names must use only letters, numbers, hyphens, and underscores
- Old snapshots can be cleaned up manually from `.ralph/snapshots/`

### Common Issues

- `git` errors: ensure you are inside a git repository and have at least one commit.
- `Unknown agent`: check `runners.*` in `.ralph/ralph.toml` or install the CLI.
- `No prompt provided` from Codex: ensure runner argv includes `-` so stdin is used.

---

## Risks and assumptions

- Assumption: agents run with least-privilege credentials and do not write secrets into `.ralph/*`.
- Risk: long-running loops can produce large logs; prune `.ralph/logs/` if needed.
- Risk: auto-commit may amend unintended changes if the worktree is dirty; review git status before running unattended loops.

---

## Security notes

- Treat prompts and logs as potentially sensitive. Avoid storing secrets in `.ralph/*`.
- Run long loops in a least-privilege environment (container or isolated dev VM).

---

## Contributing

See `CONTRIBUTING.md`.

## Security

See `SECURITY.md` for vulnerability reporting.

## Support

See `SUPPORT.md`.

## Code of Conduct

See `CODE_OF_CONDUCT.md`.
