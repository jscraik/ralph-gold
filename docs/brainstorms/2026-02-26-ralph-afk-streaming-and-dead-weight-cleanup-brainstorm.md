---
date: 2026-02-26
topic: ralph-afk-streaming-and-dead-weight-cleanup
last_validated: 2026-02-28
---

# Ralph AFK Streaming + Dead-Weight Cleanup

## Table of Contents

- [What We’re Building](#what-were-building)
- [Why This Approach](#why-this-approach)
- [Approaches Considered](#approaches-considered)
- [Key Decisions](#key-decisions)
- [Open Questions](#open-questions)
- [Resolved Questions](#resolved-questions)
- [Next Steps](#next-steps)

## What We’re Building

We want to close the gap between current Ralph Gold behavior and the Ralph article “How to Stream Claude Code with AFK Ralph.”

The goal is to provide a built-in AFK experience that keeps users informed during long iterations while still preserving robust loop control and completion checks. In parallel, we will remove implementation and documentation dead weight that is no longer required for that workflow.

Specifically, this should:

- keep the core loop (`ralph step/run/supervise`) intact,
- add an explicit, safe streaming path for long-lived runs,
- and trim obsolete artifacts (e.g., legacy shell-loop assumptions, outdated docs/examples that encourage broken `stream-json` usage, and unused stream helpers).

## Why This Approach

This is a targeted, high-value improvement: it addresses the primary user pain from AFK runs (blank output visibility) while staying inside the existing architecture. The dead-weight cleanup is constrained to non-essential, clear-to-cut items so we don’t destabilize scheduling, trackers, gates, or task selection.

We are not proposing a full UX redesign or a new execution engine.

## Approaches Considered

### Approach A: Add a built-in `--stream` mode to core loop execution (Recommended)

Add a new CLI option (initially on `ralph run`, with optional inheritance to `step`/`supervise`) that runs the runner process with live output enabled, streams stdout/stderr to terminal, and writes the complete output to the existing per-iteration log for completion parsing and receipts. This can reuse the existing helper path by extending subprocess handling to support dual-mode run (live + capture).

**Pros:**
- Directly addresses AFK visibility with minimal behavior change to loop logic.
- Keeps single source of truth in the CLI instead of external scripts.
- Works with existing gating, state updates, and completion checks.

**Cons:**
- A small increase in subprocess plumbing complexity (buffering and capture).
- Needs careful handling for runner compatibility (e.g., codex vs claude output format differences).

**Best when:**
- You want first-class AFK UX in the product, not a workaround script.

### Approach B: Keep core loop unchanged and ship external AFK wrapper docs/scripts

Document (or ship an updated `.ralph/loop.sh`) that pipes runner output through a local script (`grep`/`tee`/`jq` equivalent) to display live progress while capturing final results.

**Pros:**
- Fastest to implement.
- No risk of changing core agent execution behavior.

**Cons:**
- Hard to standardize across runners.
- Harder to debug/test centrally; UX remains ad-hoc.
- Doesn’t solve visibility across non-scripted invocations.

**Best when:**
- You only need a temporary workaround while keeping strict backward compatibility.

### Approach C: Build a separate `afk` subcommand and keep default behavior unchanged

Create a dedicated long-run entrypoint (for example, `ralph afk`) that orchestrates `run` internally and handles output routing/heartbeats.

**Pros:**
- Clean separation from existing command semantics.
- Can include richer AFK UX features (heartbeats, compact summaries).

**Cons:**
- Increases surface area with a new command mode.
- Requires extra docs/tests and may duplicate loop flags.

**Best when:**
- You need a long-running UX with explicit AFK affordances beyond logs.

### Dead-weight cleanup options (included in scope)

- Remove outdated `--output-format stream-json` guidance and historical remnants that conflict with current Claude invocation behavior.
- Consolidate helper and template drift where only scaffolding artifacts remain (`.ralph/loop.sh` / template variant) and decide whether to keep as compatibility shim, deprecate, or remove.
- Keep dead-weight cuts bounded to low-risk files only (`docs`, example snippets, unused helper paths tied to obsolete flow).

## Key Decisions

- Decision: Implement Approach A and expose it under `ralph run` first (then evaluate `step`/`supervise` parity).  
  Rationale: strongest user value for AFK visibility with least architectural churn.

- Decision: Preserve `run`/`step` iteration semantics, state updates, and gate/judge/review enforcement unchanged.  
  Rationale: avoid regressions while adding streaming.

- Decision: Add cleanup scope narrowly (docs/examples + compatibility artifacts tied only to deprecated AFK strategy).  
  Rationale: align with user’s request to remove non-required dead weight without risking core behavior.

- Decision: Defer deep architectural refactors (new output protocol, terminal UI) until post-plan validation.  
  Rationale: YAGNI; keep improvements boring and verifiable.

## Open Questions

- None (for this brainstorm): the feature scope is intentionally limited to core CLI streaming + scoped dead-weight cleanup.

## Resolved Questions

- Include both “AFK streaming UX” and “dead-weight cleanup” in the same implementation stream: **Yes** (user preference for option A plus include 2).
- Use core CLI path instead of external shell-only workaround: **Yes**.
- Keep improvements focused on required behavior and avoid broader UX rewrites: **Yes**.

## Next Steps

- Proceed to `/prompts:workflow-plan` for detailed task breakdown and acceptance tests.
