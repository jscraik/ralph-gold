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
- `.ralph/PROMPT_build.md` / `.ralph/PROMPT_plan.md` / `.ralph/PROMPT_judge.md`
- `.ralph/logs/` (per-iteration logs)
- `.ralph/state.json` (session state)

You can switch trackers by changing `files.prd` in `.ralph/ralph.toml`.

---

## Run the loop

Run N iterations:

```bash
ralph run --agent codex --max-iterations 10
```

Exit codes:
- 0: loop completed successfully (EXIT_SIGNAL true, gates/judge ok)
- 1: loop ended without a successful exit (e.g., max iterations / no-progress)
- 2: one or more iterations failed (non-zero return code, gate failure, or judge failure)

Run a single iteration:

```bash
ralph step --agent claude
```

Show status:

```bash
ralph status
```

Logs are written under `.ralph/logs/`.

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
- Markdown tracker: checkbox tasks in `PRD.md`
- JSON tracker: `prd.json`

Select via:

```toml
[tracker]
kind = "auto"    # auto|markdown|json|beads
```

`beads` is supported as an optional tracker (requires the `bd` CLI to be installed).

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
