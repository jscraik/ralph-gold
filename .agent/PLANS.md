# Sync ralph-gold-uv to v0.5.0

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repo does not include a `.agent/PLANS.md` file yet, so this document is created per `/Users/jamiecraik/.codex/instructions/plans.md` and must be maintained accordingly.

## Purpose / Big Picture

Align the working tree in `/Users/jamiecraik/dev/ralph-gold-uv-v0.3.0` to match the contents of `/Users/jamiecraik/dev/ralph-gold-uv-v0.5.0`, so the project reflects the latest version. After the update, the file set and contents (excluding local environment artifacts) match v0.5.0 and the project can be validated with its normal Python tooling.

## Progress

- [x] (2026-01-15 19:57Z) Inspect v0.5.0 tree and compare to v0.3.0 to determine sync scope and exclusions.
- [x] (2026-01-15 19:58Z) Sync repository files from v0.5.0 into v0.3.0, excluding local environment artifacts (e.g., `.venv/`, caches).
- [x] (2026-01-15 20:00Z) Review the working tree diff to ensure only expected changes remain.
- [x] (2026-01-15 20:09Z) Run uv sync, compileall, pytest (no tests), and ruff check; fix lint errors.
- [x] (2026-01-15 20:10Z) Summarize verification artifacts and outcomes in final response.

## Surprises & Discoveries

- Observation: rsync --delete removed `.agent/PLANS.md`, requiring recreation after sync.
  Evidence: file missing immediately after rsync; recreated in this step.

## Decision Log

- Decision: Use `rsync` with explicit excludes for local environment artifacts to align repo files while avoiding deletion of developer-local caches.
  Rationale: Ensures the repo content matches v0.5.0 without wiping local virtual environments or caches.
  Date/Author: 2026-01-15 (Codex).

- Decision: Remove unused imports introduced by sync so ruff passes.
  Rationale: The synced v0.5.0 content failed ruff F401; removing unused imports keeps behavior unchanged while meeting lint standards.
  Date/Author: 2026-01-15 (Codex).

## Outcomes & Retrospective

- Synced repository files to v0.5.0; removed unused imports to satisfy ruff; ran uv sync, compileall, pytest (no tests collected), and ruff.

## Context and Orientation

The current project root is `/Users/jamiecraik/dev/ralph-gold-uv-v0.3.0`. The desired source of truth is `/Users/jamiecraik/dev/ralph-gold-uv-v0.5.0`. Both contain a Python project with `pyproject.toml`, `src/`, `docs/`, `scripts/`, and `vscode/`. The sync must update files under these paths and remove files that no longer exist in v0.5.0, while leaving developer-local artifacts (such as `.venv/`, `.mypy_cache/`, `.ralph/`, `.DS_Store`, and `__pycache__`/`.pyc`) intact.

## Plan of Work

First, compare the directory trees to confirm which repo files differ and identify artifacts that should be excluded. Next, use a guarded `rsync` from v0.5.0 into v0.3.0 with `--delete` to remove files absent from v0.5.0, but add excludes for local environment artifacts and Python bytecode. Then review `git status` (or equivalent) and a concise diff to confirm the changes match expectations. Finally, run the repo’s Python quality gates if feasible (or document why they were not run) and record verification outputs.

## Concrete Steps

Run the following commands from the v0.3.0 repo root:

  rsync -a --delete --exclude '.git/' --exclude '.venv/' --exclude '.mypy_cache/' --exclude '.ralph/' --exclude '__pycache__/' --exclude '*.pyc' --exclude '.DS_Store' /Users/jamiecraik/dev/ralph-gold-uv-v0.5.0/ /Users/jamiecraik/dev/ralph-gold-uv-v0.3.0/

Then verify changes:

  git status --short
  rg --files

If checks are run, do so via uv (if configured):

  uv run python -m compileall .
  uv run pytest -q
  uv run ruff check .

## Validation and Acceptance

Acceptance means the updated working tree matches the v0.5.0 file set (excluding local artifacts), and quality gate commands either pass or are explicitly recorded as not run with reasons. A reviewer should be able to inspect `git status --short` and see only the expected version-update changes and no unintended local artifact updates.

## Idempotence and Recovery

The rsync step is idempotent; re-running it yields the same results. If the sync introduces unexpected changes, recover by re-running rsync after correcting exclude patterns, or by copying the original v0.3.0 tree from backup if needed.

## Artifacts and Notes

Capture a short `git status --short` summary after sync and note any deviations.

## Interfaces and Dependencies

No new dependencies are introduced. The update should keep the Python packaging metadata aligned with v0.5.0’s `pyproject.toml` and follow uv lockfile expectations (if present).

---
Plan updated: recreated after rsync removal; progress updated with completed steps.
