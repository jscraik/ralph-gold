---
last_validated: 2026-03-04
---

# Simple vs Expert UX Mode (v1.1 policy)

## Table of Contents

- [Purpose](#purpose)
- [Simple mode](#simple-mode)
- [Expert mode](#expert-mode)
- [Default and compatibility posture](#default-and-compatibility-posture)
- [Rollout path](#rollout-path)
- [Operator guidance](#operator-guidance)

## Purpose

Define a clear UX policy that reduces day-1 friction for humans and agent operators while preserving the complete advanced command surface.

## Simple mode

Simple mode is the default posture. It emphasizes a minimal workflow:

1. `ralph init`
2. `ralph step --agent codex`
3. `ralph status`

Simple mode guidance should prioritize safe defaults, short help examples, and fewer required decisions.

## Expert mode

Expert mode keeps full capability access for advanced operators:

- advanced orchestration (`run`, `supervise`, `watch`, `harness`)
- troubleshooting and diagnostics (`doctor`, `diagnose`, `stats`, `interventions`)
- power workflows (bridge, snapshots/rollback, tracker conversions, task template operations)

Expert mode is opt-in in operator behavior and docs posture, not a removal of existing commands.

## Default and compatibility posture

- Default policy: `ux.mode = "simple"` in scaffolded `.ralph/ralph.toml`.
- Compatibility: no command removals for v1.1.
- Existing scripts and automation should continue to work unchanged.

## Rollout path

1. Ship policy and help text first (non-breaking).
2. Add guided onboarding command (`quickstart`) in a later slice.
3. Standardize machine-facing JSON behavior in a later slice.
4. Consider stricter simple/expert toggles only after telemetry and migration guidance.

## Operator guidance

- New users: start with the simple workflow.
- Existing advanced users: keep using current commands and flags.
- Agent integrations: rely on explicit command contracts, not implicit help prose.
