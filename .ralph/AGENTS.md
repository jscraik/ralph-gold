# AGENTS.md

This file is **project-specific operational memory**.
Keep it short and deterministic. Add only what you repeatedly need.

## Stack

- Language: (e.g. Python 3.12, TypeScript 5.x, Go 1.22)
- Framework: (e.g. FastAPI, Next.js, Gin)
- Package manager: (e.g. uv, pnpm, go mod)

## Repo Commands

### Install

```bash
# Example: uv sync
```

### Build

```bash
# Example: uv run python -m build
```

### Test

```bash
# Example: uv run pytest -q
```

### Lint / Format

```bash
# Example: uv run ruff check . && uv run ruff format --check .
```

### Type Check

```bash
# Example: uv run mypy src/
```

## Quality Gates

Commands that MUST pass before marking a task done:

```bash
# 1. Compile check
uv run python -m compileall .

# 2. Tests
uv run pytest -q

# 3. Lint
uv run ruff check .
```

## Conventions

- Write small, focused commits
- One task per iteration
- Prefer editing existing code over creating parallel implementations
- Run quality gates before committing

## Project-Specific Notes

(Add any project-specific context the agent needs to know)
