# Foundation Spec

> Use for `.spec/foundation-2026-01-23-ralph-gold-prd.md`.  
> Every paragraph ends with `Evidence:` or `Evidence gap:`.

## 0) PRD Summary

Ralph Gold is a CLI loop orchestrator that runs fresh agent sessions in deterministic iterations with durable repo-backed state, gates, receipts, and optional review gates for auditability and controlled exit.  
Evidence: README.md (TL;DR, Why use ralph-gold), docs/GOLDEN_LOOP.md.

## 1) Problem & Job (JTBD-lite)

- Primary user: a solo developer who runs AI-agent loops weekly and needs deterministic exits to avoid drift and repeated work.  
- Job to be done: run AI-assisted task iterations with durable state, clear exit criteria, and audit-friendly artifacts that reduce rework.  
- Current workaround: ad-hoc agent runs without durable state, repeatable gates, or consistent exit rules.  
- Why now: rising agent usage and multi-iteration workflows demand reproducibility and accountability.  
Evidence: README.md (audience + problem/solution); user interview 2026-01-23.

## 2) Success Criteria

- Primary metric (target + time window): >= 80% of `ralph run` sessions exit with EXIT_SIGNAL true within configured max_iterations, measured weekly.  
- Activation definition: within 15 minutes of install, a user completes `ralph init` + `ralph step` and sees receipts/context artifacts.  
- Guardrail metrics: gate failure rate < 20%; no-progress exits < 10%; auto-commit usage < 25% unless explicitly enabled.  
Evidence: README.md (exit codes, receipts/context), docs/PROJECT_STRUCTURE.md; user interview 2026-01-23.

Measurement method: compute weekly counts from `.ralph/state.json` and receipts; use `ralph status --format json` to extract completion and blocked signals for reporting.  
Evidence: docs/PROJECT_STRUCTURE.md (state.json), docs/PROGRESS.md (status --format json); user interview 2026-01-23 (measurement decision).

## 3) Scope

### In-scope (MVP)

- CLI orchestration for init/run/step/status with deterministic iterations.  
- Repo-backed durable state under `.ralph/` (config, PRD tracker, logs, receipts, context).  
- Optional review gate requiring `SHIP` (or configured token) before exit.  
- Interaction surfaces: interactive task selection, TUI control surface.  
- Watch mode for auto-running gates on file changes (opt-in).  
- Authorization rules to constrain file writes during loop execution.  
Evidence: README.md (commands, TUI, watch mode, review gate), docs/PROJECT_STRUCTURE.md, docs/COMMANDS.md, docs/AUTHORIZATION.md.

### Out-of-scope (Explicit)

- Hosted SaaS runner or multi-tenant dashboards.  
- Full GUI editor or web UI for loop control.  
- Auto-provisioning credentials or secrets management.  
- VS Code bridge protocol work beyond existing implementation (treated as optional integration).  
Evidence: docs/VSCODE_BRIDGE_PROTOCOL.md; user interview 2026-01-23 (out-of-scope decision).

## 4) Primary Journey (Happy Path Only)

1) Install CLI via `uv tool install -e .` and verify `ralph --help`.  
2) Initialize repo with `ralph init` to create the `.ralph/` scaffold.  
3) Run a loop with `ralph run --agent <agent> --max-iterations N`.  
4) Monitor progress with `ralph status` or TUI.  
5) If review gate enabled, provide required token (`SHIP`) to exit.  
6) Inspect receipts and context snapshots under `.ralph/receipts/` and `.ralph/context/`.  
Evidence: README.md (Quickstart, run/step/status, review gate), docs/PROJECT_STRUCTURE.md.

## 5) User Stories (Top 5–10)

- As a solo developer, I want `ralph init` to scaffold a predictable `.ralph/` layout so that the loop has durable state and templates.  
  Acceptance Criteria: `ralph init` creates `.ralph/ralph.toml`, `.ralph/PRD.md`, `.ralph/progress.md`, and prompt files.  
  Evidence: README.md (Initialize a repo), docs/PROJECT_STRUCTURE.md.

- As a solo developer, I want `ralph step --agent <agent>` to run exactly one iteration so that I can control progress in small increments.  
  Acceptance Criteria: single iteration runs and returns documented exit codes; status is queryable afterward.  
  Evidence: README.md (step), docs/TROUBLESHOOTING.md.

- As a solo developer, I want `ralph run --agent <agent> --max-iterations N` to stop after N iterations so that runs are bounded.  
  Acceptance Criteria: loop respects max iterations and exit codes reflect outcome.  
  Evidence: README.md (run), docs/COMMANDS.md.

- As a reviewer, I want a review gate that requires a `SHIP` token so that the loop cannot exit without explicit approval.  
  Acceptance Criteria: when `review.enabled = true`, loop exit requires `review.required_token` and fails without it.  
  Evidence: README.md (review gate), docs/CONFIGURATION.md.

- As a solo developer, I want receipts and context snapshots per iteration so that I can audit what happened.  
  Acceptance Criteria: `.ralph/receipts/` contains command/evidence JSON and `.ralph/context/` contains ANCHOR snapshots per iteration.  
  Evidence: README.md; docs/PROJECT_STRUCTURE.md; docs/EVIDENCE.md.

- As a solo developer, I want interactive task selection so that I can manually pick the next task.  
  Acceptance Criteria: `ralph step --interactive` shows a task list with search/filter and returns a selection.  
  Evidence: README.md (interactive), docs/interactive_selection.md.

- As a solo developer, I want a TUI control surface so that I can run/step/pause without retyping commands.  
  Acceptance Criteria: `ralph tui` starts a UI with documented keybindings (s/r/a/p/q).  
  Evidence: README.md (TUI section), docs/COMMANDS.md.

- As a solo developer, I want authorization rules to restrict writes so that sensitive files are protected.  
  Acceptance Criteria: configured permissions limit which paths can be modified during loop execution.  
  Evidence: docs/AUTHORIZATION.md.

- As a solo developer, I want watch mode to auto-run gates on file changes so that I get rapid feedback.  
  Acceptance Criteria: `watch.enabled = true` enables `ralph watch`, and `--auto-commit` is optional.  
  Evidence: README.md (Watch mode), docs/CONFIGURATION.md.

## 6) Assumptions

- Primary users are intermediate CLI/git users operating on macOS or Linux.  
- Teams value deterministic audit trails enough to adopt `.ralph/` artifacts.  
- Supported agents include codex, claude, and copilot as described in docs.  
- Interview decisions: impact type = ops toil; success signal = behavior + metrics; acceptance criteria style = Given/When/Then; scope bias = balanced; primary constraint = simplicity; failure mode = UX confusion; tradeoff = correctness/clarity.  
Evidence: README.md (audience, agent names); user interview 2026-01-23 (assumption acceptance).

## 7) Risks & Mitigations (Top 3–5)

- Risk: loop stalls due to circular dependencies or no-progress tasks.  
  Mitigation: status visibility and dependency troubleshooting guidance.  
  Evidence: README.md (circular dependencies), docs/TROUBLESHOOTING.md.

- Risk: watch mode auto-commit can capture unintended changes in a dirty worktree.  
  Mitigation: warn users and require explicit enablement.  
  Evidence: README.md (watch mode risk note).

- Risk: unauthorized file writes during automated runs.  
  Mitigation: configurable authorization rules limiting write paths.  
  Evidence: docs/AUTHORIZATION.md.

- Risk: sensitive data may appear in `.ralph/` logs or receipts.  
  Mitigation: treat `.ralph/*` logs as sensitive and avoid secrets in prompts/logs.  
  Evidence: AGENTS.md (Security & Configuration Tips).

- Risk: large context snapshots or receipts increase disk usage and slow runs.  
  Mitigation: cleanup commands and guidance for managing logs/receipts/context.  
  Evidence: docs/PROJECT_STRUCTURE.md; docs/NEW_FEATURES.md.

- Risk: UX confusion causes unclear exit or task state.  
  Mitigation: explicit status output, consistent copy tone, and clear next-step guidance.  
  Evidence: README.md (status/TUI), `.spec/ux-2026-01-23-ralph-gold-prd.md` (UX Acceptance Criteria).  

## 8) Positioning Constraints (NEW / EASY / SAFE / BIG)

- Emphasis: SAFE + EASY.  
- Rationale: deterministic loops, receipts, and review gates reduce risk while CLI/TUI affordances keep usage straightforward.  
Evidence: README.md (deterministic loop, receipts, review gate, TUI); user interview 2026-01-23.

## 9) Diagrams

```mermaid
flowchart TD
  A[START: Install and verify CLI] --> B[Init repo: ralph init]
  B --> C[Configure ralph.toml (optional)]
  C --> D[Run loop: ralph run --agent X --max-iterations N]
  D --> E[Monitor: ralph status / TUI]
  E --> F{Review gate enabled?}
  F -- No --> G[Exit when EXIT_SIGNAL true]
  F -- Yes --> H[Require SHIP token]
  H --> G
  G --> I[Inspect receipts/context]
  I --> J[END]
```
Evidence: README.md (run/step/status/TUI/review), docs/CONFIGURATION.md (review).

## Evidence Gaps

- None for v1; decisions captured in interview with planned validation post-release.  
Evidence: user interview 2026-01-23.

## Evidence Map

| Claim/Section | Evidence | Notes |
| --- | --- | --- |
| PRD Summary | README.md; docs/GOLDEN_LOOP.md | Product definition and loop properties. |
| Problem & Job | README.md; user interview 2026-01-23 | Problem statement and persona confirmed via interview. |
| Success Criteria | README.md; docs/PROJECT_STRUCTURE.md; docs/PROGRESS.md; user interview 2026-01-23 | Targets set by decision with measurement method. |
| Scope (In-scope) | README.md; docs/COMMANDS.md; docs/PROJECT_STRUCTURE.md; docs/AUTHORIZATION.md | CLI surface and artifacts. |
| Scope (Out-of-scope) | docs/VSCODE_BRIDGE_PROTOCOL.md | Optional integration boundary. |
| Primary Journey | README.md; docs/PROJECT_STRUCTURE.md | Quickstart and artifacts. |
| User Stories | README.md; docs/COMMANDS.md; docs/PROJECT_STRUCTURE.md; docs/interactive_selection.md; docs/AUTHORIZATION.md | Feature behaviors. |
| Risks & Mitigations | README.md; docs/TROUBLESHOOTING.md; docs/NEW_FEATURES.md; AGENTS.md | Risks and safety notes. |
| Positioning | README.md | Determinism, auditability, review gate. |
