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

## Secret scanning

This project uses **gitleaks** to prevent accidental secret commits in two layers:

### 1. Pre-commit hook (local)

Before each commit, gitleaks scans staged files for secrets:
- API keys, tokens, credentials
- Private keys (SSH, PGP, etc.)
- High-entropy strings that might be secrets

If a secret is detected, the commit is **blocked** with instructions for remediation.

**Emergency bypass (unsafe)**:
```bash
git commit --no-verify
# or
RALPH_DISABLE_SECRET_SCAN=1 git commit
```

**Installation**: The pre-commit hook is installed at `.git/hooks/pre-commit`. To reinstall:
```bash
# Copy from .git/hooks/pre-commit.sample or recreate from spec
```

### 2. GitHub Actions CI (remote)

Every push and pull request runs gitleaks in CI, providing defense-in-depth:
- Catches secrets that bypass local checks (e.g., `--no-verify`)
- Runs on full repository history
- Blocks PRs that contain secrets
- Uploads scan reports as artifacts (30-day retention)

### False positives?

If a legitimate pattern is flagged, add it to `.gitleaks.toml` under `[allowlist]`:

```toml
[allowlist]
regexes = [
    '''your_benign_pattern_here''',
]
```

### Secret rotation

If you accidentally commit a real secret:
1. **Rotate it immediately** at the source (GitHub, AWS, etc.)
2. **Remove it from git history**: `git filter-repo` or BFG Repo-Cleaner
3. **Consider the secret compromised** - rotation is critical

### Reference

See `.gitleaks.toml` for full configuration and `.github/workflows/secret-scan.yml` for CI setup.
