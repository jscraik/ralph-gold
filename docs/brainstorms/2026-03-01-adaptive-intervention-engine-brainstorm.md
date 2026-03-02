---
date: 2026-03-01
topic: adaptive-intervention-engine
last_validated: 2026-03-01
---

# Adaptive Intervention Engine Brainstorm

## Table of Contents

- [What We’re Building](#what-were-building)
- [Why This Approach](#why-this-approach)
- [Approaches Considered](#approaches-considered)
- [Key Decisions](#key-decisions)
- [Open Questions](#open-questions)
- [Resolved Questions](#resolved-questions)
- [Next Steps](#next-steps)

## What We’re Building

We want a new engine that converts iteration failures into explicit, reusable guidance for the next iteration, without changing Ralph’s deterministic filesystem-first model.

The engine will read existing signals already produced by Ralph (for example `no_files_written` receipts, gate failures, evidence counts, and harness trends), compute a concise intervention recommendation, and persist it as a versioned profile. In v1, recommendations are surfaced in operator-visible artifacts and injected into prompt context through existing feedback plumbing rather than silently changing runtime behavior.

This keeps the loop behavior auditable while making failures progressively more informative and actionable.

## Why This Approach

Approach A (recommend-only coach) is the best v1 because it creates compounding learning value with the lowest regression risk.

Ralph already has strong primitives in place: no-files detection in `src/ralph_gold/loop.py`, prompt feedback ingestion in `build_prompt`, and rich receipts/harness artifacts. The missing link is automated synthesis of those signals into next-step policy guidance.

Starting with recommendations (instead of autonomous mutation) gives operators control, preserves trust, and creates clean data for a later auto-apply phase if warranted.

## Approaches Considered

### Approach A: Recommend-only Coach (selected)
Generate intervention suggestions + rationale; do not auto-apply policy.

**Pros:** safest rollout, high auditability, fastest delivery.  
**Cons:** requires operator action to apply recommendations.  
**Best when:** introducing learning behavior in a reliability-sensitive CLI.

### Approach B: Auto-apply low-risk interventions
Auto-apply prompt and timeout adjustments under guardrails.

**Pros:** faster operational gains.  
**Cons:** greater regression/debug burden.  
**Best when:** recommendation quality has already proven stable.

### Approach C: Autonomous policy controller
Dynamic runner/mode/gate tuning from historical outcomes.

**Pros:** maximum adaptive potential.  
**Cons:** highest complexity and risk.  
**Best when:** mature intervention governance and extensive benchmark coverage exist.

## Key Decisions

- Choose **Approach A** for v1 (recommend-only coach).
- Primary success metric: reduce no-files + auto-blocked iteration rate over rolling 20–30 iterations.
- Learning window: recent 20–30 iterations plus harness trend signals.
- Intervention scope in v1: prompt constraints + timeout/mode hints, but surfaced as recommendations only.
- Keep task semantics, gate semantics, and completion semantics unchanged.

## Open Questions

- None for v1 scope.

## Resolved Questions

- Should v1 modify runtime policies directly? **No**; recommendations first.
- What is the core success target? **Reduce blocked/no-files iterations**.
- What evidence horizon should drive policy advice? **Recent 20–30 iterations + harness trends**.
- Which adaptation surface comes first? **Prompt + timeout policy guidance**.

## Next Steps

Proceed to `/prompts:workflow-plan` to define acceptance criteria, interfaces, rollout guardrails, and validation commands.
