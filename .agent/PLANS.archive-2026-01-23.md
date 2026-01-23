# Integrate ralph-gold-uv v0.8.0 into ralph-gold

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository uses `.agent/PLANS.md`. This document must be maintained in accordance with `/Users/jamiecraik/.codex/instructions/plans.md`.

## Purpose / Big Picture

Bring the new v0.8.0 release features (Repo Prompt context packs, receipts-based gating, re-anchoring, and SHIP/BLOCK review gate) into `/Users/jamiecraik/dev/ralph-gold` so the CLI and loop behavior match the v0.8.0 capabilities while preserving existing repo-specific features (parallel execution, YAML and GitHub trackers). After this change, a user can run `ralph init`, `ralph step`, and `ralph run` and observe receipts, context packs, and review gating behavior in `.ralph/` as described by the v0.8.0 README, without regressions to existing commands.

## Progress

- [x] (2026-01-17 16:10Z) Read standards, engineering guidance, work rules, and CODESTYLE requirements.
- [x] (2026-01-17 16:12Z) Inventory v0.8.0 package and current repo tree; capture a diff summary to scope changes.
- [x] Update `.agent/PLANS.md` to this ExecPlan and keep it current as work proceeds.
- [x] Add/merge v0.8.0 features into core modules (`config.py`, `loop.py`, `cli.py`, `trackers.py`, `prd.py`, `bridge.py`, `tui.py`, `scaffold.py`).
- [x] Add new modules (`repoprompt.py`, `receipts.py`) and templates (`FEEDBACK.md`, `PROMPT_review.md`), update existing templates and `README.md`.
- [x] Update tests to align with new behavior; run `uv run pytest -q` (via `uv run --with pytest pytest -q`) and CLI smoke checks.
- [x] Produce verification evidence and summarize outcomes.

## Surprises & Discoveries

- Observation: v0.8.0 sources show internal inconsistencies (loop imports for receipts/repoprompt do not match the provided modules). Evidence: `src/ralph_gold/loop.py` references `CommandReceipt` and `build_context_pack` signatures that do not exist in `receipts.py` and `repoprompt.py`.

## Decision Log

- Decision: Integrate v0.8.0 features into the existing repo rather than replacing the entire codebase. Rationale: the repo already contains additional supported features (parallel execution, YAML and GitHub trackers) that are not present in the v0.8.0 package, and a full overwrite would remove them and break existing tests. Date/Author: 2026-01-17 (Codex).
- Decision: Reconcile v0.8.0 inconsistencies by aligning `loop.py` with corrected `receipts.py` and `repoprompt.py` APIs rather than copying the mismatched files verbatim. Rationale: keeps the integration functional and testable while still honoring the v0.8.0 README feature set. Date/Author: 2026-01-17 (Codex).

## Outcomes & Retrospective

- Pending. Will be completed after integration and validation.

## Context and Orientation

The target repo is `/Users/jamiecraik/dev/ralph-gold`. Source reference is `/Users/jamiecraik/Downloads/ralph-gold-uv-v0.8.0`. Core runtime is under `src/ralph_gold/` and templates live in `src/ralph_gold/templates/`. The loop orchestrator is implemented in `src/ralph_gold/loop.py` and invoked by `src/ralph_gold/cli.py`, `src/ralph_gold/tui.py`, and `src/ralph_gold/bridge.py`. Task selection and tracker IO are in `src/ralph_gold/prd.py` and `src/ralph_gold/trackers.py`, with optional trackers in `src/ralph_gold/trackers/`. The scaffolding entry point is `src/ralph_gold/scaffold.py`. Tests live under `tests/`.

The v0.8.0 release introduces a receipts system (structured JSON artifacts stored under `.ralph/receipts/`), re-anchoring (per-iteration ANCHOR.md under `.ralph/context/`), optional Repo Prompt context packs (rp-cli integration, stored under `.ralph/context/`), and an optional SHIP/BLOCK review gate. These must be represented in config (`.ralph/ralph.toml`), templates, and runtime behavior.

## Plan of Work

Update `config.py` to add v0.8.0 configuration fields (loop attempt backstop, review gate, prek gate runner, repoprompt config, additional file paths) while preserving existing parallel and GitHub tracker configs. Add new modules `receipts.py` and `repoprompt.py` using corrected APIs that match the new loop behavior. Refactor `loop.py` to add re-anchoring, receipts, repoprompt context pack generation, review gating, and attempt-based auto-blocking; preserve existing exit-signal handling, parallel execution hooks, and repo-clean logic that ignores `.ralph/`. Update `trackers.py` and `prd.py` to support `select_next_task(exclude_ids=...)`, blocked status, and dependency-aware selection while keeping existing YAML/GitHub tracker functionality and parallel grouping.

Update `cli.py`, `bridge.py`, and `tui.py` to use the new tracker selection interface and surface the new loop results without breaking existing subcommands (doctor/setup checks, GitHub auth checks, convert, serve, parallel flags). Update `scaffold.py` to include new default files (`FEEDBACK.md`, `PROMPT_review.md`) and new `.ralph/` subdirectories (`receipts/`, `context/`, `attempts/`). Update templates and docs (README + GOLDEN_LOOP) to document v0.8.0 features and keep existing repo-specific features (parallel execution, YAML/GitHub tracker sections). Update `pyproject.toml` and `__init__.py` version to 0.8.0.

Finally, run `uv run pytest -q` and a CLI smoke check (`uv run python -m ralph_gold.cli --help`) to validate behavior. Document any skipped checks or known deviations.

## Concrete Steps

Run commands from `/Users/jamiecraik/dev/ralph-gold`:

    rg --files
    diff -qr --exclude '__pycache__' --exclude '*.pyc' /Users/jamiecraik/dev/ralph-gold /Users/jamiecraik/Downloads/ralph-gold-uv-v0.8.0

Apply edits to the following files, in this order, keeping changes minimal and testable:

    src/ralph_gold/config.py
    src/ralph_gold/receipts.py (new)
    src/ralph_gold/repoprompt.py (new)
    src/ralph_gold/prd.py
    src/ralph_gold/trackers.py
    src/ralph_gold/loop.py
    src/ralph_gold/cli.py
    src/ralph_gold/bridge.py
    src/ralph_gold/tui.py
    src/ralph_gold/scaffold.py
    src/ralph_gold/templates/AGENTS.md
    src/ralph_gold/templates/FEEDBACK.md (new)
    src/ralph_gold/templates/PROMPT_build.md
    src/ralph_gold/templates/PROMPT_review.md (new)
    src/ralph_gold/templates/ralph.toml
    README.md
    docs/GOLDEN_LOOP.md
    pyproject.toml
    src/ralph_gold/__init__.py

After edits, run:

    uv run pytest -q
    uv run python -m ralph_gold.cli --help

Record outputs (or reasons for not running) under Artifacts and in the final response.

## Validation and Acceptance

Acceptance is met when:

- `ralph init` creates `.ralph/` with new files (`FEEDBACK.md`, `PROMPT_review.md`) and directories (`receipts/`, `context/`, `attempts/`).
- Running a loop iteration produces `ANCHOR.md` and receipts under `.ralph/context/` and `.ralph/receipts/` when tasks exist.
- `gates.review` (when enabled) blocks progress unless the reviewer output ends with `SHIP`.
- Existing features (parallel execution, YAML/GitHub trackers) remain functional and tests pass.
- `uv run pytest -q` passes (or any failures are documented with rationale).

## Idempotence and Recovery

All edits are file-based and can be re-applied safely. If a change introduces regressions, revert the specific file to its prior version and re-apply the v0.8.0-specific edits incrementally. Avoid deleting repo-local artifacts such as `.ralph/`, `.venv/`, or `.agent/`.

## Artifacts and Notes

Capture concise evidence such as `git status --short`, key test outputs, and any new file creation confirmation. Keep snippets short and focused on proving acceptance criteria.

## Interfaces and Dependencies

No new third-party Python dependencies are required. The new optional integration is the external `rp-cli` binary, which must be referenced via config (`[repoprompt].cli`) and checked by `doctor` when enabled. The following interfaces must exist after implementation:

    In src/ralph_gold/config.py, Config must include repoprompt, review gate, and attempt backstop fields.
    In src/ralph_gold/trackers.py, Tracker must expose select_next_task(exclude_ids=None) and block_task(task_id, reason).
    In src/ralph_gold/prd.py, selection must respect blocked tasks and optional dependencies.
    In src/ralph_gold/loop.py, run_iteration must accept task_override and emit receipts + context anchors.

---
Plan updated: 2026-01-17 (Codex). Replaced outdated v0.5.0 sync plan with v0.8.0 integration plan.
