# Contributing to ralph-gold

Doc requirements:
- Audience: contributors (intermediate Python + git)
- Scope: local setup, tests, style, PR flow
- Owner: maintainers
- Review cadence: quarterly
- Last updated: 2026-01-15

## Quick start

```bash
uv sync
uv run pytest -q
```

## Repository layout

- `src/ralph_gold/`: CLI and loop implementation
- `docs/`: usage and protocol references
- `tests/`: pytest test suite

## Development workflow

1) Create a branch from `main`.
2) Make focused changes with minimal scope.
3) Run tests:

```bash
uv run pytest -q
```

4) Update docs if behavior changes (README or `docs/`).
5) Open a pull request with a concise summary.

## Commit signing

Commits must be signed via the 1Password SSH agent (repo policy). If you cannot sign, call it out explicitly in the PR description.

## Reporting issues

Use GitHub Issues for bugs and feature requests.

## Code style

Follow existing patterns; keep functions small and avoid hidden side effects.
