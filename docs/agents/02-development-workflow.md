---
last_validated: 2026-02-28
---

# Development workflow

## Project structure
- Core code: `/Users/jamiecraik/dev/ralph-gold/src/ralph_gold/`
- Tests: `/Users/jamiecraik/dev/ralph-gold/tests/`
- Docs: `/Users/jamiecraik/dev/ralph-gold/docs/`
- VS Code bridge extension: `/Users/jamiecraik/dev/ralph-gold/vscode/ralph-bridge/`
- Install helpers: `/Users/jamiecraik/dev/ralph-gold/scripts/`

## Build, test, and dev commands
- `uv sync`
- `uv run pytest -q`
- `uv run python -m ralph_gold.cli --help`
- `uv tool install -e .`

## Coding style
- Keep Python code under `src/ralph_gold/`.
- Prefer small single-purpose functions with clear error handling.
- Use `snake_case` for functions and variables; `PascalCase` for classes.
- Follow adjacent module patterns before adding new abstractions.
- Avoid new dependencies without approval.

## Testing guidelines
- Use `pytest` under `tests/`.
- Name tests `test_*.py`.
- Keep fixtures local to each test file unless sharing is required.
- Run `uv run pytest -q` before opening a PR.

## Commit and PR guidance
- Commit message convention: not observed.
- Keep commit messages clear and scoped.
- PRs should include a short summary, test results, and doc updates for behavior changes.
