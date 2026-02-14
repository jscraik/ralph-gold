# Implement Ralph Gold PRD (Solo Dev Loop) in slices

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository uses `.agent/PLANS.md`. This document must be maintained in accordance with `/Users/jamiecraik/.codex/instructions/plans.md`.

## Purpose / Big Picture

Enable a solo developer to run deterministic AI-agent loop iterations with clear exit rules, durable receipts/context artifacts, optional review gate, optional watch mode, and an optional VS Code bridge, all aligned to the finalized PRD/UX/Build Plan. A user should be able to run `ralph init`, `ralph step`, and `ralph run`, observe receipts and context snapshots, and verify status and review gating behavior in the terminal.

## Progress

- [ ] (2026-01-23 00:00Z) Read this ExecPlan end-to-end and confirm repo status and current behavior.
- [ ] (2026-01-23 00:00Z) Validate current CLI behavior and record baseline outputs for `ralph init`, `ralph step`, and `ralph status`.
- [ ] (2026-01-23 00:00Z) Implement or verify receipts + context snapshots for each iteration, including schema fields.
- [ ] (2026-01-23 00:00Z) Implement or verify review gate behavior and status visibility.
- [ ] (2026-01-23 00:00Z) Implement or verify watch mode behavior and opt-in safety.
- [ ] (2026-01-23 00:00Z) Implement or verify VS Code bridge JSON-RPC contract alignment with API spec.
- [ ] (2026-01-23 00:00Z) Add or update tests to cover new/verified behaviors.
- [ ] (2026-01-23 00:00Z) Run `uv run pytest -q` and CLI smoke checks; capture evidence.
- [ ] (2026-01-23 00:00Z) Update docs if user-visible behavior changes.
- [ ] (2026-01-23 00:00Z) Complete Outcomes & Retrospective.

## Surprises & Discoveries

- None yet.

## Decision Log

- Decision: Implement in small slices aligned to PRD acceptance criteria and API spec before optimizing or refactoring.
  Rationale: preserves deterministic behavior and reduces regressions.
  Date/Author: 2026-01-23 (Codex).

## Outcomes & Retrospective

- Pending.

## Context and Orientation

This repository is a CLI/devtools project. Core runtime lives under `src/ralph_gold/`. The loop orchestrator is in `src/ralph_gold/loop.py`, CLI entry in `src/ralph_gold/cli.py`, interactive UI in `src/ralph_gold/tui.py`, and VS Code bridge in `src/ralph_gold/bridge.py`. Templates and scaffolding live in `src/ralph_gold/templates/` and are used by `src/ralph_gold/scaffold.py`. Loop state and receipts are stored under `.ralph/` in the project root. The implementation should align with these specs:

- `.spec/foundation-2026-01-23-ralph-gold-prd.md`
- `.spec/ux-2026-01-23-ralph-gold-prd.md`
- `.spec/build-plan-2026-01-23-ralph-gold-prd.md`
- `.spec/foundation-2026-01-23-ralph-gold-prd-api-spec.md`

Key terms:
- "Iteration": one loop run cycle with a single agent invocation.
- "Receipts": JSON artifacts under `.ralph/receipts/` that record command and evidence details.
- "Context snapshot": `.ralph/context/<n>/ANCHOR.md` that captures per-iteration context.
- "Review gate": a rule that requires a `SHIP` token to exit when enabled.

## Plan of Work

First, confirm the current behavior of `ralph init`, `ralph step`, and `ralph status` using the CLI to establish a baseline. Then, verify the receipts and context snapshot outputs match the required schemas from the build plan. If missing or incomplete, update the loop orchestration (`src/ralph_gold/loop.py`) and receipts writers (`src/ralph_gold/receipts.py`) to produce the required fields and paths. Next, ensure the review gate logic is enforced and visible in status outputs; update `src/ralph_gold/loop.py`, `src/ralph_gold/cli.py`, and `src/ralph_gold/status.py` if necessary.

Then, validate watch mode behavior and safety: `ralph watch` should only be available when `watch.enabled = true` in `.ralph/ralph.toml`, and auto-commit must remain opt-in. Update `src/ralph_gold/watch.py` or the watch controller if behavior diverges. Next, align the VS Code bridge JSON-RPC responses to the API spec, ensuring the `status` and `step` payloads match the defined schema and that event payloads include required fields. Update `src/ralph_gold/bridge.py` to normalize field names (`task_id`) and add explicit error responses if needed.

Finally, add or update tests in `tests/` to cover receipts/context outputs, review gating, and bridge schemas. Run `uv run pytest -q` and CLI smoke checks, then update docs if any user-visible behavior changes from current documentation.

## Concrete Steps

Run commands from `/Users/jamiecraik/dev/ralph-gold`:

    rg "receipts" src/ralph_gold
    rg "context" src/ralph_gold
    rg "review" src/ralph_gold
    uv run python -m ralph_gold.cli --help
    ralph init
    ralph step --agent codex
    ralph status

If receipts or context snapshots are missing or incomplete, update the following files (as needed):

    src/ralph_gold/loop.py
    src/ralph_gold/receipts.py
    src/ralph_gold/repoprompt.py
    src/ralph_gold/bridge.py
    src/ralph_gold/tui.py
    src/ralph_gold/scaffold.py
    src/ralph_gold/templates/ralph.toml

Expected evidence examples (trimmed):

    .ralph/receipts/command-<id>.json exists
    .ralph/context/<n>/ANCHOR.md exists
    ralph status shows current task and exit state

## Validation and Acceptance

Run the repo tests and CLI smoke checks:

    uv run pytest -q
    uv run python -m ralph_gold.cli --help

Acceptance is met when:

- A fresh `ralph init` creates `.ralph/` scaffolding including receipts/context directories.
- `ralph step` produces receipts and ANCHOR snapshots per iteration.
- Review gate blocks exit unless the required token is provided.
- `ralph status` reports current task state and exit reason clearly.
- VS Code bridge responses match the API spec schemas.
- `uv run pytest -q` passes or failures are documented.

## Idempotence and Recovery

All steps are safe to repeat. If a change causes regression, revert the specific file to the last known good state and re-apply changes in smaller patches. Avoid deleting `.ralph/` unless explicitly requested; it contains state needed for verification.

## Artifacts and Notes

Record these artifacts in short form:

    git status --short
    uv run pytest -q (pass/fail summary)
    ralph status output after a run

## Interfaces and Dependencies

Key interfaces that must exist after implementation:

    In src/ralph_gold/bridge.py, ensure JSON-RPC responses match `.spec/foundation-2026-01-23-ralph-gold-prd-api-spec.md` with `task_id` and defined event fields.

    In src/ralph_gold/receipts.py, ensure receipts include attempt_id, command, status, timestamp, and citations.

    In src/ralph_gold/loop.py, ensure per-iteration context snapshots are written to `.ralph/context/<n>/ANCHOR.md`.

Plan change note: Created a new ExecPlan for implementing the finalized PRD/UX/Build Plan slices; archived the prior ExecPlan as `.agent/PLANS.archive-2026-01-23.md` to preserve history.
