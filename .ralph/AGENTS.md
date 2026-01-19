# Ralph Gold Agents & Gates

This file is read by Ralph Gold each iteration.

## Gates (backpressure)

Ralph Gold will run gates *after* the agent makes changes. Configure them in `.ralph/ralph.toml`.

Recommended patterns:

### Option A (recommended): `prek` as the universal gate runner

- Put your quality contract in `.pre-commit-config.yaml`
- Then enable the gate:
  - `[gates.prek] enabled = true` (runs `prek run --all-files`)

No git hooks are installed by Ralph Gold.

### Option B: Explicit commands

Examples:
- `uv run ruff check .`
- `uv run mypy src`
- `uv run pytest -q`
- `npm test`

## Review gate (cross-model)

Optionally enable `[gates.review]` to require a reviewer model to return `SHIP`.

## Notes

- Receipts are written under `.ralph/receipts/` each iteration.
- Repo Prompt context packs (if enabled) are written under `.ralph/context/`.
