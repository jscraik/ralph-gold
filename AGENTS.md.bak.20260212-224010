schema_version: 1
# Repository Guidelines

## Project Structure & Module Organization

- Core code: `src/ralph_gold/`
- Tests: `tests/`
- Docs: `docs/`
- VS Code bridge extension: `vscode/ralph-bridge/`
- Install helpers: `scripts/`

## Build, Test, and Development Commands

- `uv sync`: install dependencies into the local env.
- `uv run pytest -q`: run the test suite.
- `uv run python -m ralph_gold.cli --help`: smoke-check the CLI.
- `uv tool install -e .`: install the CLI as a global-ish tool.

## Coding Style & Naming Conventions

- Python code lives under `src/ralph_gold/`.
- Prefer small, single-purpose functions and clear error handling.
- Use `snake_case` for functions/variables and `PascalCase` for classes.
- Follow existing patterns in adjacent modules; avoid new dependencies without approval.

## Testing Guidelines

- Tests use `pytest` under `tests/`.
- Name tests `test_*.py` and keep fixtures local to the test file.
- Run `uv run pytest -q` before opening a PR.

## Commit & Pull Request Guidelines

- Commit message convention: not observed in this repo; keep messages clear and scoped.
- PRs should include a short summary, test results, and any doc updates for behavior changes.

## Working With Project Instructions

- Global scope: Codex reads `~/.codex/AGENTS.override.md` if present; otherwise `~/.codex/AGENTS.md`.
- Also check `~/.codex/instructions/` for applicable global standards and guidance.
- Project scope: Codex discovers instruction files from repo root down to the working directory.
- Per-directory order: `AGENTS.override.md`, then `AGENTS.md`, then fallback names in `project_doc_fallback_filenames`.
- Size limit: `project_doc_max_bytes` caps combined instructions (32 KiB default). This is a byte limit, not a token window.
- Use `CODEX_HOME` to switch profiles (for example, per-project settings).
- Troubleshoot: empty files are ignored; higher-level overrides win; increase max bytes if truncated.

## ExecPlans

- For complex features or significant refactors, follow ExecPlans (`/Users/jamiecraik/.codex/instructions/plans.md` or `.agent/PLANS.md` if present).

## Philosophy

This codebase will outlive you. Every shortcut becomes someone else's burden. Every hack compounds into technical debt that slows the whole team down. Fight entropy. Leave the codebase better than you found it.

## Security & Configuration Tips

- Treat `.ralph/*` logs as sensitive; do not store secrets in prompts or logs.
- Prefer least-privilege environments for long-running loops.
---

# AI Assistance Governance (Model A)

This project follows **Model A** AI artifact governance: prompts and session logs are committed artifacts in the repository.

## When creating PRs with AI assistance

Claude must:

1. **Save artifacts to `ai/` directory**:
   - Final prompt → `ai/prompts/YYYY-MM-DD-<slug>.yaml`
   - Session summary → `ai/sessions/YYYY-MM-DD-<slug>.json`

2. **Commit both files in the PR branch**:
   ```bash
   git add ai/prompts/YYYY-MM-DD-<slug>.yaml ai/sessions/YYYY-MM-DD-<slug>.json
   ```

3. **Reference exact paths in PR body**:
   - Under **AI assistance** section:
     - Prompt: `ai/prompts/YYYY-MM-DD-<slug>.yaml`
     - Session: `ai/sessions/YYYY-MM-DD-<slug>.json`
   - In **AI Session Log** details:
     - Log file: `ai/sessions/YYYY-MM-DD-<slug>.json`
     - Prompt file: `ai/prompts/YYYY-MM-DD-<slug>.yaml`

4. **Do NOT**:
   - Embed prompt/log excerpts in the PR body
   - Link to external logs or pastebins
   - Skip creating artifacts when AI assistance is acknowledged

5. **Abort** if artifacts cannot be created and committed.

## Artifact Templates

See `ai/prompts/.template.yaml` and `ai/sessions/.template.json` for required fields.

## PR Template

All PRs must use `.github/PULL_REQUEST_TEMPLATE.md` which includes required AI disclosure sections.
