---
title: feat: Add AFK streaming + dead-weight cleanup for core Ralph loop
type: feat
status: active
date: 2026-02-26
origin: docs/brainstorms/2026-02-26-ralph-afk-streaming-and-dead-weight-cleanup-brainstorm.md
---

# 🏗️ Add AFK Streaming + Dead-Weight Cleanup

## Table of Contents

- [Enhancement Summary](#enhancement-summary)
- [Section Manifest](#section-manifest)
- [Research Scan and Inputs](#research-scan-and-inputs)
- [Overview](#overview)
- [Problem Statement / Motivation](#problem-statement--motivation)
- [Brainstorm Carry-Forward](#brainstorm-carry-forward)
- [Proposed Solution](#proposed-solution)
- [Technical Considerations](#technical-considerations)
- [System-Wide Impact](#system-wide-impact)
  - [Interaction Graph](#interaction-graph)
  - [Error & Failure Propagation](#error--failure-propagation)
  - [State Lifecycle Risks](#state-lifecycle-risks)
  - [API Surface Parity](#api-surface-parity)
  - [Integration Test Scenarios](#integration-test-scenarios)
- [Implementation Plan](#implementation-plan)
- [Documentation and Reference Updates](#documentation-and-reference-updates)
  - [Documentation Clarity](#documentation-clarity)
  - [Table of Contents Hygiene](#table-of-contents-hygiene)
  - [User-Facing Docs and Help Updates](#user-facing-docs-and-help-updates)
  - [Docs Quality Validation](#docs-quality-validation)
  - [Reference Coverage](#reference-coverage)
- [Implementation Phases](#implementation-phases)
  - [Phase 1: Stream Mode Plumbing](#phase-1-stream-mode-plumbing)
  - [Phase 2: Dead-Weight Cleanup](#phase-2-dead-weight-cleanup)
  - [Phase 3: Validation & Rollout](#phase-3-validation--rollout)
- [Alternative Approaches Considered](#alternative-approaches-considered)
- [Acceptance Criteria](#acceptance-criteria)
- [Success Metrics](#success-metrics)
- [Dependencies & Risks](#dependencies--risks)
- [Sources](#sources--references)
- [Open vs Resolved Questions](#open-vs-resolved-questions)

## Enhancement Summary

**Deepened on:** 2026-02-26

- Deepened across all major sections with research-backed checkpoints, risk framing, and implementation/validation evidence requirements.
- Added a concrete scope bound: stream mode is transport-only; dead-weight cleanup is docs + runtime hints.
- Added confirmation that no reusable learnings were found in `docs/solutions` or alternate project-learning paths.

### Key Improvements

1. Added explicit deep-dive blocks per section and evidence-backed checkpoints.
2. Added compatibility-first sequencing for `--stream` in `ralph run`.
3. Tightened dead-weight cleanup to bounded docs/runtime paths with migration notes.
4. Added explicit observability vs correctness metrics.

## Section Manifest

1. Overview
2. Problem statement and motivation
3. Brainstorm carry-forward constraints
4. Proposed solution and cleanup scope
5. Technical considerations
6. System-wide impact and failure modes
7. Implementation plan, phase sequencing, and gates
8. Documentation updates and TOC hygiene
9. Alternative approaches and acceptance/risk closure

## Research Scan and Inputs

- Searched implementation points: `src/ralph_gold/cli.py`, `src/ralph_gold/loop.py`, `src/ralph_gold/subprocess_helper.py`, `src/ralph_gold/scaffold.py`.
- Confirmed no `docs/solutions` directory exists in this repo.
- Checked alternate learning dirs `.codex/docs` and `/Users/jamiecraik/.codex/docs`: both missing.
- Inputs used: Python docs (argparse/subprocess), pytest docs, and applicable in-repo skill outputs.

## Overview

Implement a first-class AFK streaming path in Ralph Gold so long-running loop executions remain visible while preserving completion protocol and pruning outdated AFK helper guidance. The `--stream` mode is additive, off by default, and scoped intentionally to `ralph run` in phase 1.

### Research Insights

**Best practices:**
- Keep `--stream` additive and off by default.
- Preserve completion parsing and log contracts.

**Performance:**
- Track time-to-first-visible-line as a primary operator metric.

**Edge cases:**
- Commands with internal buffering can still appear delayed.
- Ensure persisted output is complete even on abrupt exits.

**References:**
- https://docs.python.org/3/library/subprocess.html

## Problem Statement / Motivation

AFK workflows can appear blank because output is captured and not streamed by default, and stale documentation still suggests obsolete wrapper patterns.

### Research Insights

**Best practices:**
- Improve operator trust with live feedback and deterministic completion artifacts.

**Performance:**
- Define observability latency separately from completion correctness.

## Brainstorm Carry-Forward

- Decision adopted: add built-in streaming in `ralph run` and avoid shell-only wrapper dependency. (see brainstorm: docs/brainstorms/2026-02-26-ralph-afk-streaming-and-dead-weight-cleanup-brainstorm.md)
- Decision adopted: keep non-stream semantics unchanged.
- Decision adopted: scoped dead-weight cleanup only (docs/examples + clearly obsolete helpers).

### Research Insights

**Best practices:**
- Preserve decisions as implementation constraints; do not broaden scope without explicit reconsideration.

## Proposed Solution

1. Add an opt-in `--stream` flag to `ralph run` (phase-1 scope; no other command surface changes).
2. Keep existing completion semantics by preserving the current `parse_exit_signal` path.
3. Stream output in real time while teeing output to an ephemeral capture buffer so parsing and receipts remain unchanged.
4. Do not enable stream mode for `supervise`/parallel entrypoints in this phase; evaluate after `ralph run` behavior is stable.

### Dead-weight cleanup scope

1. Remove outdated stream-json guidance.
2. Audit scaffolded loop artifacts for obsolete assumptions.
3. Keep `run_subprocess_live(...)` only if it is explicitly required by a new streaming contract; if unused, document removal rationale with a call-site audit.

### Research Insights

**Best practices:**
- Prefer extending existing runtime entrypoints over maintaining external wrappers.
- Apply cleanup only when it reduces operator confusion.

**References:**
- Python subprocess documentation and existing repo scan.

## Technical Considerations

### Execution path evidence (current architecture)

- CLI path: `src/ralph_gold/cli.py` (`run`, `step`, `supervise`).
- Loop path: `src/ralph_gold/loop.py` (`run_loop`, `run_iteration`) and `src/ralph_gold/subprocess_helper.py`.
- Existing helper `run_subprocess_live(...)` exists and is currently unused; it can become the transport primitive if we preserve tee-based capture for parser compatibility.

### Research Insights

**Best practices:**
- Thread stream mode from CLI arg to `run_iteration` via function signatures.
- Keep existing log/receipt schema untouched.

## System-Wide Impact

### Interaction Graph

`cli.cmd_run` -> `run_loop` -> `run_iteration` -> runner invocation

### Error & Failure Propagation

- Keep timeout / command-not-found behavior in existing deterministic paths.
- Maintain existing fallback when completion token is missing.
- In stream mode, capture must still be available for parser-consumption before task completion evaluation.

### State Lifecycle Risks

- Partial stream output should not create partial-completion false positives.
- Derive completion from parser output only after completion callback.

### Research Insights

**Best practices:**
- Keep parse and state transitions identical in both modes.

## Implementation Plan

### Execution objective and assumptions

- Deliver `ralph run --stream` with no behavior change unless flag is set.

### Suggested task-level sequencing and handoffs

#### Task 1 baseline lock
- [ ] `uv run python -m pytest -q tests/test_cli_mode.py tests/test_loop_mode_runtime.py`
- [ ] Confirm current behavior baseline before edits.

#### Task 2 stream CLI option wiring
- [ ] Add `--stream` to `ralph run` parser and pass through to loop with `stream=False` default.
- [ ] Add explicit command-surface decision in docs: `run`-only in phase 1.
- [ ] `uv run python -m pytest -q tests/test_cli_mode.py -k run`

#### Task 3 runtime streaming path
- [ ] Add stream branch in `run_iteration` using tee-style capture: terminal stream + in-memory/temp-buffer capture for `parse_exit_signal` and receipts.
- [ ] Add tests that assert completion-parsing works in stream mode and that non-stream behavior is unchanged.

#### Task 4 docs cleanup
- [ ] Update stream guidance and TOCs in docs.
- [ ] Remove wrapper-centric language as primary flow and add explicit note that wrapper streaming remains supported only as user customization.

#### Task 5 final validation
- [ ] `uv run python -m pytest -q`
- [ ] Docs QA checks.

### Research Insights

**Best practices:**
- Make each task finish with evidence and acceptance checkpoints.

## Documentation and Reference Updates

### Documentation Clarity

- Use consistent term: stream mode.
- Keep `AFK` in historical context only.

### Table of Contents Hygiene

- Enforce TOC/heading parity in docs updated for stream changes.

### User-Facing Docs and Help Updates

- Add `--stream` in `docs/COMMANDS.md` and `README.md`.
- Update runner config guidance in `docs/configuration-phase2.md`.

### Docs Quality Validation

- Run readability/brand checks and record pass-fail output with file list.

### Reference Coverage

- Link every behavior change to source files and helper modules.

## Implementation Phases

### Phase 1: Stream Mode Plumbing

#### Task sequence

1. Add tests or validation for `run_subprocess_live` path expectations.
2. Route stream flag in `run_iteration`.
3. Preserve `IterationResult` contract.

### Phase 2: Dead-Weight Cleanup

#### Task sequence

1. Update docs/config examples and remove stream-json default assumptions.
2. Audit scaffold artifacts for duplication and clarify deprecation if retained.

### Phase 3: Validation & Rollout

#### Task sequence

1. Add long-running stream tests and timeout/fallback cases.
2. Run full suite and docs QA.
3. Package change set with rollback instructions.

## Alternative Approaches Considered

1. Shell-only AFK wrapper: rejected, too divergent.
2. New afk-only command: rejected, extra surface area.
3. Keep capture-only: rejected, operator observability gap.

### Research Insights

**Best practices:**
- Choose minimal surface-area change and defer non-core command growth.

## Acceptance Criteria

- [ ] `ralph run --stream` exists and works without default-mode change.
- [ ] Non-stream behavior unchanged.
- [ ] `parse_exit_signal` continues under stream (same parsing contract and token semantics as non-stream mode).
- [ ] Docs no longer recommend stream-json wrappers as canonical flow; wrappers may be documented as optional legacy/custom flow.
- [ ] TOC entries match heading order in changed docs and remain machine-checkable.
- [ ] Test suite validates timeout, parse fallback, and stream smoke behavior.

### Research Insights

**Edge cases:**
- Mixed stderr/stdout ordering with token detection.

## Success Metrics

- Reduced first-visible-output latency from end-to-end loop command start in a deterministic smoke harness (target: observe first output chunk within a low single-digit second range for local benchmark).
- No completion regression for PRD-driven tasks in existing parse/token path.
- Stable default logs when `--stream` is omitted.

## Dependencies & Risks

- No external dependencies.
- Risk: some runners may require non-stream mode fallback.
- Risk: wrapper-heavy user environments may need explicit migration notes.

### Research Insights

**Mitigations:**
- Provide config examples and explicit fallback path in docs.

## Sources & References

### Origin

- docs/brainstorms/2026-02-26-ralph-afk-streaming-and-dead-weight-cleanup-brainstorm.md

### Internal References

- /Users/jamiecraik/dev/ralph-gold/src/ralph_gold/cli.py
- /Users/jamiecraik/dev/ralph-gold/src/ralph_gold/loop.py
- /Users/jamiecraik/dev/ralph-gold/src/ralph_gold/subprocess_helper.py
- /Users/jamiecraik/dev/ralph-gold/src/ralph_gold/scaffold.py
- /Users/jamiecraik/dev/ralph-gold/docs/configuration-phase2.md
- /Users/jamiecraik/dev/ralph-gold/README.md
- /Users/jamiecraik/dev/ralph-gold/docs/COMMANDS.md

### External References

- https://docs.python.org/3/library/argparse.html
- https://docs.python.org/3/library/subprocess.html
- https://docs.pytest.org/en/stable/

## Open vs Resolved Questions

- Open: none.
- Resolved:
  - Stream + cleanup in one change set: yes
  - Preserve core semantics: yes
  - Built-in command path preferred over shell wrapper: yes