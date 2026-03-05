# Contributing

## Table of Contents

- [Minimum workflow contract](#minimum-workflow-contract)
- [Why this workflow exists](#why-this-workflow-exists)
- [Branching and PR rule](#branching-and-pr-rule)
- [Branch name policy](#branch-name-policy)
- [Required pre-merge gates](#required-pre-merge-gates)
- [Greptile setup baseline](#greptile-setup-baseline)
- [Greptile config hierarchy](#greptile-config-hierarchy)
- [Greptile merge logic for multi-scope pull requests](#greptile-merge-logic-for-multi-scope-pull-requests)
- [Greptile confidence score policy](#greptile-confidence-score-policy)
- [Greptile strictness policy](#greptile-strictness-policy)
- [Greptile training and feedback loop](#greptile-training-and-feedback-loop)
- [Recommended security scanner baseline](#recommended-security-scanner-baseline)
- [Review artifacts requirement](#review-artifacts-requirement)
- [Credential-safe evidence snippets](#credential-safe-evidence-snippets)
- [Branch protection recommendation](#branch-protection-recommendation)

## Minimum workflow contract

- Branch off `main` for every change.
- No direct push to `main`.
- Pull request required for every merge.
- Required checks must pass before merge.
- Greptile + Codex review artifacts are required before merge.
- Greptile must be configured correctly using the `grepfile` skill with all required Greptile files present.
- The coding agent must not approve its own PR; review must be independent.
- Merge only after all gates pass.
- Delete branch/worktree after merge.

## Why this workflow exists

This workflow keeps delivery auditable, reversible, and consistent even for solo development.

## Branching and PR rule

1. Create a dedicated branch/worktree for each task:
   - Agent-created branch: `git switch -c codex/<short-description>`
   - Agent-created worktree: `git worktree add ../tmp-worktree -b codex/<short-description>`
   - Human-authored optional prefixes: `feat/`, `fix/`, `docs/`, `refactor/`, `chore/`, `test/`
2. Keep commits small and focused.
3. Open a PR to merge into `main`.
4. Do not merge until checks, reviews, and checklist items are complete.
5. After merge, delete the remote branch and remove local worktree/branch.

## Branch name policy

- Use lower-case, kebab-case slugs.
- Agent-created branches must use `codex/<short-description>`.
- Human-authored branches may use: `feat/`, `fix/`, `docs/`, `refactor/`, `chore/`, `test/`.
- Avoid `main`-like names and do not include secrets or issue-pii.

## Required pre-merge gates

- npm run lint
- npm run typecheck
- npm run test
- npm run audit
- npm run check
- security-scan (CI required check)
- test -f memory.json && jq -e '.meta.version == "1.0" and (.preamble.bootstrap | type == "boolean") and (.preamble.search | type == "boolean") and (.entries | type == "array")' memory.json >/dev/null

## Pre-commit hooks

This repository uses `simple-git-hooks` for local quality gates:

| Hook | Purpose |
| --- | --- |
| `pre-commit` | Runs `npm run lint && npm run typecheck` |
| `commit-msg` | Validates conventional commit format |
| `pre-push` | Runs `npm run test` |

### Setup

**Automated setup (recommended):**

After running `harness init`, run the setup script to automatically configure package.json:

```bash
node scripts/setup-git-hooks.js
```

This script:
1. Adds `simple-git-hooks` to devDependencies
2. Adds postinstall script to activate hooks
3. Configures hooks in package.json
4. Runs `npm install` to activate

**Manual setup:**

Add to your `package.json`:

```json
{
  "devDependencies": {
    "simple-git-hooks": "^2.13.1"
  },
  "scripts": {
    "postinstall": "simple-git-hooks"
  },
  "simple-git-hooks": {
    "pre-commit": "npm lint && npm typecheck",
    "commit-msg": "node scripts/validate-commit-msg.js $1",
    "pre-push": "npm test"
  }
}
```

Then run `npm install` to install hooks.

### Commit message format

All commits must follow conventional commit format:

```
type(scope)!: description

Detailed body (optional).

Co-Authored-By: Name <email>
```

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`, `perf`, `ci`, `build`, `revert`

## Greptile setup baseline

- Greptile must be configured correctly before relying on Greptile review gates.
- Use the `grepfile` skill to set up/refresh all required Greptile files for this repository.
- If Greptile files are missing or stale, treat the review gate as blocked and do not merge.
- Required local structure:
  - `.greptile/config.json`
  - `.greptile/rules.md`
  - `.greptile/files.json`
- Independent validation is mandatory: the coding agent cannot approve its own changes.

## Greptile config hierarchy

When settings conflict, use this precedence (highest first):

1. Org-enforced rules from the Greptile dashboard.
2. Directory-scoped `.greptile/` folders (cascading inheritance).
3. `greptile.json` legacy repo-wide config (ignored if `.greptile/` exists in the same directory).
4. Dashboard defaults.

## Greptile merge logic for multi-scope pull requests

For PRs touching multiple directories with different configs:

- Strictness: use the most restrictive value (`MAX`).
- `fileChangeLimit`: use the smallest value (`MIN`).
- Comment types: union all requested comment types.
- Boolean settings: if any scope enables it, treat as enabled (`OR`).

## Greptile confidence score policy

Use confidence score as a merge gate signal:

- `5/5`: production-ready, merge allowed.
- `4/5`: minor polish, merge allowed after non-logic fixes.
- `3/5`: implementation issues, must address feedback and re-review.
- `2/5`: significant bugs, blocked.
- `0-1/5`: critical issues, blocked.

## Greptile strictness policy

- Level 1 (Verbose): required for security-critical directories and new project setup.
- Level 2 (Default): required baseline for PRs targeting `main`/production branches.
- Level 3 (Critical-only): reserved for stable, non-critical internal infrastructure.

Important indexing caveat:

- `ignorePatterns` excludes files from review only; it does **not** exclude indexing.
- Large binaries/assets and `node_modules` must be excluded at repository/dashboard indexing level.

## Greptile training and feedback loop

- Developers must provide regular 👍/👎 feedback on review comments.
- A 👎 should include a brief rationale to train the system.
- Commit analysis and the 3-ignore rule are active signals and must be respected.
- New repositories should expect a 2-3 week calibration period.

Manual trigger standards:

- Use `@greptileai` on draft PRs or when settings/context changed and a forced re-review is needed.
- Use targeted prompts for scoped checks (for example: `@greptileai check for memory leaks`).

## Recommended security scanner baseline

For repositories that use Harness, recommend installing these scanners as project prerequisites:

- Gitleaks
- Trivy
- Semgrep

Recommended policy:

- Secret scanning is required in both local development and CI pipelines.
- Keep scanner binaries available in local development environments and CI runners.
- Run scanner checks in CI on pull requests and pushes to protected branches.
- Treat scanner findings as merge blockers unless explicitly waived with rationale.

## Review artifacts requirement

Each PR must include:

- Greptile review artifact (URL, report, or comment reference).
- Codex review artifact (URL, report, or comment reference).
- Greptile confidence score for the PR.
- Confirmation that reviewer agent is independent from coding agent.

If either artifact is missing, block merge until it is added or explicitly waived by repository policy.

## Credential-safe evidence snippets

- Never use command substitution in commit messages, PR bodies, or evidence notes for secrets.
- Do **not** use `$(gh auth token)` (or similar) inside `git commit -m ...` / `gh pr create --body ...`.
- Use placeholders in text output:
  - ✅ `$GITHUB_TOKEN`
  - ✅ `${GITHUB_TOKEN}`
  - ❌ expanded token values
- If a token value is ever exposed in commit/PR text, treat it as compromised: rotate/revoke, rewrite history where applicable, and document remediation in the issue/PR.

## Branch protection recommendation

Configure GitHub branch protection (or rulesets) on `main`:

- Bootstrap baseline via harness:
  - `harness branch-protect --owner <owner> --repo <repo>`
- Token resolution for `branch-protect`:
  - `--token <PAT>` or env `GITHUB_TOKEN` / `GITHUB_PERSONAL_ACCESS_TOKEN`
- Require pull request before merge.
- Require at least one approval.
- Require status checks: `pr-template`, `lint`, `typecheck`, `test`, `audit`, `check`, `security-scan`, `memory`.
- Block direct pushes to `main`.
