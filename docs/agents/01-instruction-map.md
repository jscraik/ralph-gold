---
last_validated: 2026-02-28
---

# Instruction map

## Purpose
Use this map to find task-level guidance quickly.

## Table of Contents
- [Development workflow](02-development-workflow.md)
- [Validation and governance](03-validation-and-governance.md)
- [Contradictions and cleanup](04-contradictions-and-cleanup.md)

## Suggested docs folder structure
```text
/Users/jamiecraik/dev/ralph-gold/docs/agents/
  01-instruction-map.md
  02-development-workflow.md
  03-validation-and-governance.md
  04-contradictions-and-cleanup.md
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
- `04-contradictions-and-cleanup.md`: known conflicts, resolution questions, and deletion candidates.
