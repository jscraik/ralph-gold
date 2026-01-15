# ralph-gold (uv-first)

A *Golden Ralph Loop* orchestrator that runs **fresh CLI-agent sessions** (Codex, Claude Code, Copilot) in a deterministic loop until your PRD is complete.

This repo is intentionally small:

- **Python CLI** (`ralph`) you install with **uv**
- **File-based memory** (PRD + progress + agents doc)
- **Runner adapters** for `codex`, `claude`, `copilot`

> Safety: don’t run autonomous loops with broad permissions on your host machine. Prefer a container / isolated dev VM.

---

## Install (with uv)

1) Install uv (see [uv installation guide](https://docs.astral.sh/uv/))

2) From this repo root:

```bash
uv tool install -e .
uv tool update-shell   # optional: adds uv tool bin dir to your shell PATH
```

Open a new shell, then:

```bash
ralph --help
```

To uninstall:

```bash
uv tool uninstall ralph-gold
```

---

## Project setup

From your project root:

```bash
ralph init
```

This creates a `.ralph/` directory with:

- `prd.json` (task list, JSON format)
- `PRD.md` (task list, Markdown checkbox format for Copilot/VS Code workflows)
- `PROMPT.md` (main loop instructions / guardrails)
- `AGENTS.md` (how to build/test/run in *your* repo)
- `progress.md` (append-only memory across iterations)
- `ralph.toml` (runner config)
- `logs/` (state + logs)

Edit the PRD format you want to use (JSON or Markdown) and `AGENTS.md` to match your stack.

By default, the loop reads whatever `files.prd` points to in `ralph.toml`.

---

## Run the loop

Run N iterations:

```bash
ralph run --agent codex --max-iterations 10
```

Or a single iteration:

```bash
ralph step --agent claude
```

Logs land in `.ralph/logs/`.

---

## PRD generation

Generate/update your PRD from a description (one-off agent run):

```bash
ralph plan --agent codex --desc "Build a small FastAPI service with health endpoint and tests"
```

You can also pipe multi-line text:

```bash
cat idea.md | ralph plan --agent claude
```

---

## Status

Quick progress and last iteration summary:

```bash
ralph status
```

---

## Configure runners (ralph.toml)

`ralph` does not vendor agent CLIs — you install them separately.
You can fully customize runner argv in `ralph.toml`.

Example:

```toml
[loop]
max_iterations = 25
no_progress_limit = 3

[files]
prd = ".ralph/prd.json"
progress = ".ralph/progress.md"

[runners.codex]
argv = ["codex", "exec", "--full-auto"]

[runners.claude]
argv = ["claude", "-p", "--output-format", "text"]

[runners.copilot]
argv = ["copilot", "--prompt"]
```

Notes:

- `codex exec` gets the prompt as the final CLI arg.
- `claude -p` expects the prompt *immediately after* `-p`.
- `copilot --prompt` expects the prompt after `--prompt`.

---

## PRD format

`ralph-gold` supports **two** PRD formats:

1) JSON: `prd.json` (minimal Ralph-style stories list)
2) Markdown: `PRD.md` (checkbox tasks, compatible with VS Code/Copilot "PRD.md" conventions)

### JSON PRD

Each story can be either:

- `passes: true|false` (snarktank style)
- OR `status: "open"|"in_progress"|"done"` (iannuttall style)

`ralph` will update whichever field exists.

### Markdown PRD

Use a `## Tasks` section with checkbox lines:

```md
## Tasks
- [ ] Task 1
- [ ] Task 2
```

---

## Exit behavior

The loop stops when:

- all stories are marked done/passing, AND
- the agent prints `EXIT_SIGNAL: true`

This dual gate avoids premature exits.

If you configure `gates.commands` in `ralph.toml`, the orchestrator will also run them after each iteration.

---

## Development

```bash
uv sync
uv run python -m ralph_gold.cli --help
```

---

## VS Code Bridge (optional)

`ralph-gold` includes an optional **VS Code extension** (`vscode/ralph-bridge`) that controls the loop via a JSON-RPC bridge over stdio.

Start the bridge manually:

```bash
ralph bridge
```

Or install the VS Code extension and use the command palette:

- Ralph: Start Bridge
- Ralph: Step / Run / Stop

Protocol documentation:

- `docs/VSCODE_BRIDGE_PROTOCOL.md`

Extension sources:

- `vscode/ralph-bridge/`
