---
last_validated: 2026-04-11
---

# Hook Governance Scope Defaults

## Table of Contents

- [Intent](#intent)
- [Agent Mutation Default](#agent-mutation-default)
- [Changes Implemented (2026-04-11)](#changes-implemented-2026-04-11)
- [Scope Policy By Script](#scope-policy-by-script)
- [Required Invocation Pattern](#required-invocation-pattern)
- [Rollout Checklist For Other Projects](#rollout-checklist-for-other-projects)
- [Why This Matters](#why-this-matters)

## Intent

This document defines how hook-governance commands should scope repository checks.

- Local developer workflows should default to project-local scope.
- Cross-repo governance reporting should remain available as an explicit workspace mode.
- Standalone scripts should require explicit input paths so they do not silently fall back to workspace artifacts.

## Agent Mutation Default

These defaults are mandatory when an agent is asked to implement changes:

1. The agent must apply code and config mutations in the target local project by default.
2. Workspace-level or cross-repo mutation is opt-in only, and must be explicitly requested (for example via `--workspace-governance` or equivalent scope flag).
3. If no target project path is clear, the agent must stop and ask for the exact local project root instead of mutating shared workspace artifacts.
4. In project-local mode, generated governance outputs must be temporary or local to that project and must not overwrite shared tracked governance reports.
5. When documentation and execution scope diverge, the executable project-local contract (`verify-work` wrapper + explicit script inputs) takes precedence over inferred workspace defaults.

## Changes Implemented (2026-04-11)

1. `scripts/verify-work.sh`
- Default scope is `project-local`.
- `--project-governance` keeps local-only checks.
- `--workspace-governance` enables cross-repo checks from `repo-scope.manifest.json`.
- In project-local mode, generated governance artifacts are written to temp files by the canonical verifier.

2. `/Users/jamiecraik/.codex/scripts/hook-governance/rollout_check.py`
- `--inventory` is required.
- No default `docs/hooks-governance/repo-profile-matrix.json` fallback.

3. `/Users/jamiecraik/.codex/scripts/hook-governance/evaluate_docstring_ratchet.py`
- `--classification` is required.
- `--metrics` is required.
- No default fallback to workspace-level docs artifacts.

## Scope Policy By Script

1. Workspace-by-design scripts:
- `inventory_repos.py`
- `generate_conformance.py` (when fed workspace manifest/inventory)
- `validate_conformance.py` (when fed workspace manifest/inventory)

2. Scope-inherited scripts (recommended to stay input-driven):
- `validate_gate_registry.py`
- `verify_gate_taxonomy.py`
- `classify_public_api.py`
- `rollout_check.py`
- `evaluate_docstring_ratchet.py`

3. Entry-point behavior:
- `scripts/verify-work.sh` stays project-local by default.
- Workspace validation is explicit via `--workspace-governance`.

## Required Invocation Pattern

Always pass explicit scope artifacts in direct script runs:

```bash
python3 /Users/jamiecraik/.codex/scripts/hook-governance/rollout_check.py \
  --inventory /Users/jamiecraik/dev/configs/codex/docs/hooks-governance/repo-profile-matrix.json \
  --recovery-slo-hours 24 \
  --out /Users/jamiecraik/dev/configs/codex/docs/hooks-governance/rollout-check-report.json

python3 /Users/jamiecraik/.codex/scripts/hook-governance/evaluate_docstring_ratchet.py \
  --classification /Users/jamiecraik/dev/configs/codex/docs/hooks-governance/public-api-classification.json \
  --metrics /Users/jamiecraik/dev/configs/codex/docs/hooks-governance/docstring-ratchet-metrics.json \
  --window-days 14 \
  --out /Users/jamiecraik/dev/configs/codex/docs/hooks-governance/docstring-ratchet-report.json
```

For project-local validation via wrapper:

```bash
bash scripts/verify-work.sh --fast
```

For explicit workspace governance:

```bash
bash scripts/verify-work.sh --fast --workspace-governance
```

## Rollout Checklist For Other Projects

1. Update the local `verify-work` equivalent to default to project-local governance.
2. Add an explicit workspace flag for full governed-estate checks.
3. Remove implicit workspace defaults from standalone governance scripts.
4. Require explicit `--manifest` or `--inventory` style arguments where scope matters.
5. Ensure project-local mode writes temporary outputs, not shared tracked reports.
6. Add a short scope-policy markdown in each repo so the default is discoverable.
7. Validate both paths:
- project-local run passes when unrelated repos are stale.
- workspace run fails when any governed repo is stale.

## Why This Matters

Project-local defaults prevent unrelated-repo drift from blocking normal feature work.
Workspace mode preserves governance visibility for release audits and periodic estate checks.
