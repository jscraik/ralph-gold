---
last_validated: 2026-04-11
---

# Instruction map

## Purpose
Use this map to find task-level guidance quickly.

## Table of Contents
- [Development workflow](02-development-workflow.md)
- [Validation and governance](03-validation-and-governance.md)
- [Hook governance scope defaults](hook-governance-scope-defaults.md)
- [Contradictions and cleanup](04-contradictions-and-cleanup.md)
- [Tooling inventory](tooling.md)

## Suggested docs folder structure
```text
/Users/jamiecraik/dev/ralph-gold/docs/agents/
  01-instruction-map.md
  02-development-workflow.md
  03-validation-and-governance.md
  hook-governance-scope-defaults.md
  04-contradictions-and-cleanup.md
  tooling.md
```

## Discovery order
1. `/Users/jamiecraik/.codex/AGENTS.md`
2. `/Users/jamiecraik/dev/ralph-gold/AGENTS.md`
3. Linked docs in `/Users/jamiecraik/dev/ralph-gold/docs/agents/`
4. If instructions conflict, stop and ask which one wins

## Scope split
- Root `AGENTS.md`: always-on essentials only.
- `02-development-workflow.md`: project structure, commands, style, tests, PR flow.
- `03-validation-and-governance.md`: validation, security notes, AI artifact policy, scaffold checks.
- `hook-governance-scope-defaults.md`: project-local default scope and workspace opt-in for hook-governance runs.
- `04-contradictions-and-cleanup.md`: known conflicts, resolution questions, and deletion candidates.
- `tooling.md`: repo-canonical tooling inventory used by `scripts/check-environment.sh`.
