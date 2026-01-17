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
