# Solo Dev Optimizations

## Problem Statement
Ralph Gold is optimized for team workflows. Solo developers need faster iteration
with flexible rigor to preserve flow state while keeping quality gates available
for higher-risk changes.

## Acceptance Criteria
- Modes exist for speed, quality, and exploration, with mode-specific loop settings.
- Smart gate selection skips irrelevant gates based on changed files.
- Quick task batching allows 2-3 tiny tasks per iteration using explicit markers.
- Solo-default config can be scaffolded via `ralph init --solo`.
- Flow and momentum tracking surfaces velocity and blocked-task handling.
- Context-aware prompts exist for docs, hotfix, and exploration work.
- Workflow shortcuts exist for common solo-dev flags (`--quick`, `--batch`, `--explore`, `--hotfix`, `--task`).
- Adaptive rigor and history-based learning tighten gates for higher-risk areas.

## Non-Goals
- Removing safety gates entirely for production changes.
- Hiding failures or marking tasks done without gate verification.
- Implementing team-only workflows or heavyweight process.

## Edge Cases
- No state history available (flow stats should degrade gracefully).
- Only docs/config changes (gates should skip without error).
- Mixed file changes across risk levels (adaptive rigor should apply the strictest path).
- Batch selection with dependencies (batching must respect `Depends on:` entries).
