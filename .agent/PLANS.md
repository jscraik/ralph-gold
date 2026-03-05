# Ralph Gold v1.1 Simplification + Architecture Hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository uses `.agent/PLANS.md`. This document must be maintained in accordance with `/Users/jamiecraik/.codex/instructions/plans.md`.

## Table of Contents

- [Purpose / Big Picture](#purpose--big-picture)
- [Progress](#progress)
- [Surprises & Discoveries](#surprises--discoveries)
- [Decision Log](#decision-log)
- [Outcomes & Retrospective](#outcomes--retrospective)
- [Context and Orientation](#context-and-orientation)
- [Plan of Work](#plan-of-work)
- [Task Graph Contract](#task-graph-contract)
- [Concrete Steps](#concrete-steps)
- [Validation and Acceptance](#validation-and-acceptance)
- [Idempotence and Recovery](#idempotence-and-recovery)
- [Artifacts and Notes](#artifacts-and-notes)
- [Interfaces and Dependencies](#interfaces-and-dependencies)

## Purpose / Big Picture

Enable a v1.1 release that is easier to use for humans, easier to automate for AI agents, and easier to maintain for contributors. After this change, users should be able to start with a low-friction default workflow (`quickstart` + simple mode), while advanced users retain full control via expert mode. Agents and integrations should see stable JSON contracts across commands. Maintainers should work with smaller modules instead of monolithic orchestration files.

## Progress

- [x] (2026-03-04 00:00Z) Capture high-level v1.1 goals from stakeholder discussion.
- [x] (2026-03-04 00:00Z) Replace legacy plan with dependency-based task graph contract.
- [x] (2026-03-04 23:40Z) Record baseline command behavior and JSON outputs before refactors; saved command transcripts to `artifacts/baseline/2026-03-04-t01-command-baseline.md`.
- [x] (2026-03-04 23:48Z) Deliver T02 simple/expert policy slice (help text + config template metadata + docs); see `docs/SIMPLE_EXPERT_MODE.md`.
- [x] (2026-03-04 23:56Z) Deliver T03 quickstart command slice with profile presets (`simple|expert`) and next-step guidance; added CLI integration tests.
- [x] (2026-03-05 00:03Z) Deliver T04 explainability command slice (`ralph explain`) with text and JSON parity for why-selected, blocker context, and next actions.
- [x] (2026-03-05 01:22Z) Deliver CLI and loop modularization slices: command families now extracted under `src/ralph_gold/commands/` with compatibility-preserving parser wiring and green targeted/full test suites.
- [x] (2026-03-04 23:59Z) Continue T05 by extracting maintenance/state command family (`resume`, `clean`, `state cleanup`, `blocked`, `unblock`, `retry-blocked`, `sync`, `interventions`) into `src/ralph_gold/commands/maintenance.py`; parser/flags unchanged and targeted suite remains green.
- [x] (2026-03-05 00:06Z) Continue T05 by extracting planning/specs/snapshot/watch/task handlers into `src/ralph_gold/commands/planning.py`; parser wiring unchanged and targeted CLI suite + help smoke remain green.
- [x] (2026-03-05 00:12Z) Continue T05 by extracting loop command logic (`step`, `run`, `supervise`) into `src/ralph_gold/commands/loop_runtime.py` while keeping `cli.py` compatibility wrappers for monkeypatch-based tests and parser stability.
- [x] (2026-03-05 00:16Z) Continue T05 by extracting utility command family (`bridge`, `tui`, `serve`, `completion`, `convert`) into `src/ralph_gold/commands/utilities.py`; verified parser/help and CLI harness/completion suites remain green.
- [x] (2026-03-05 00:20Z) Continue T05 by extracting harness command family into `src/ralph_gold/commands/harness.py` (`collect`, `run`, `report`, `pin`, `ci`, `doctor`) while preserving command names/flags and CI-facing behavior.
- [x] (2026-03-05 00:26Z) Start T07 JSON contract unification: added global `--format/--verbosity` overrides, versioned JSON envelope (`schema_version=ralph.cli.v1`), and JSON fallback emission when a command lacks an explicit JSON branch.
- [x] (2026-03-05 00:40Z) Extend T07 with maintenance JSON contract coverage (`clean`, `sync`, `interventions`) and targeted JSON regression tests; command-level and output-contract suites are green.
- [x] (2026-03-05 00:47Z) Resolve full-suite verification regressions: restored stream-mode runner behavior in `loop.py`, fixed missing `get_quick_batch` test import, tightened gitleaks rules/allowlist, and updated CONTRIBUTING secret-scanning language.
- [x] (2026-03-05 01:22Z) Deliver JSON schema unification and contract tests: global `--format/--verbosity`, `schema_version=ralph.cli.v1`, fallback JSON emission, and JSON contract tests across diagnose/maintenance/general output helpers.
- [x] (2026-03-05 01:03Z) Deliver T08 version discipline and CI enforcement slice: switched to dynamic Hatch version sourcing from `src/ralph_gold/__init__.py`, aligned runtime version to changelog (`0.8.2`), added `scripts/check_version_sync.py`, CI `version-sync` gate, and version contract tests.
- [x] (2026-03-05 01:16Z) Deliver T09 authorization coverage expansion slice: added post-run write-effect authorization checks (tracked+untracked git paths), allow/deny receipts (`authorization_prewrite_anchor.json`, `authorization_post_write_effects.json`), block-mode failure propagation, and loop runtime tests for warn/block behavior.
- [x] (2026-03-05 01:24Z) Run full verification and update user-facing docs (`README.md`, `docs/COMMANDS.md`, `docs/CONFIGURATION.md`, `docs/AUTHORIZATION.md`) for v1.1 posture, machine interface, and authorization scope.
- [x] (2026-03-05 01:24Z) Complete outcomes and retrospective summary.

## Surprises & Discoveries

- Observation: Current codebase already contains broad capabilities, but core entrypoints are very large (`cli.py`, `loop.py`), so incremental extraction is safer than top-down rewrite.
  Evidence: local file-size scan and AST function-size scan run on 2026-03-04.
- Observation: `scripts/codex-preflight.sh` assumes Bash internals and fails when sourced directly in `zsh`.
  Evidence: `scripts/codex-preflight.sh:119: BASH_SOURCE[0]: parameter not set`; running via `bash -lc \"source scripts/codex-preflight.sh && preflight_repo\"` succeeds.
- Observation: `RALPH_FORMAT=json` does not currently guarantee JSON payloads across sampled commands (`doctor`, `diagnose`, `status`, `step --dry-run`, `run --dry-run`).
  Evidence: baseline transcript captured in `artifacts/baseline/2026-03-04-t01-command-baseline.md`.
- Observation: Moving recently added UX handlers into `src/ralph_gold/commands/ux.py` preserved behavior with no regressions in the targeted CLI suite.
  Evidence: `uv run pytest -q tests/test_cli_explain.py tests/test_cli_quickstart.py tests/test_cli_diagnose.py tests/test_cli_watch.py tests/test_cli_stats.py tests/test_cli_status.py tests/test_config.py tests/test_templates.py` → `70 passed`.
- Observation: Monitoring command extraction (`status`, `stats`, `diagnose`) into `src/ralph_gold/commands/monitoring.py` preserved CLI behavior and help surface.
  Evidence: same targeted suite remains green (`70 passed`) and `uv run ralph --help` still lists unchanged command names/flags.
- Observation: Maintenance/state command extraction into `src/ralph_gold/commands/maintenance.py` did not alter CLI parser wiring or sync semantics.
  Evidence: `uv run pytest -q tests/test_cli_sync.py tests/test_cli_mode.py tests/test_cli_interactive.py tests/test_cli_diagnose.py tests/test_cli_stats.py tests/test_cli_status.py tests/test_cli_quickstart.py tests/test_cli_explain.py tests/test_config.py tests/test_templates.py tests/test_cli_watch.py` → `90 passed`.
- Observation: Planning/specs/snapshot/watch/task extraction into `src/ralph_gold/commands/planning.py` preserved command help surface and targeted behavior.
  Evidence: same targeted suite remains green (`90 passed`) and help smoke succeeded for `plan`, `regen-plan`, `snapshot`, `rollback`, `task`, and `watch`.
- Observation: Loop command extraction required compatibility wrappers in `cli.py` to preserve tests that monkeypatch `ralph_gold.cli.run_loop`/`run_iteration`/`dry_run_loop`.
  Evidence: `tests/test_cli_mode.py` and `tests/test_cli_interactive.py` remain green after wrapper-based extraction (`90 passed` targeted suite).
- Observation: Utility command extraction has no side effects on harness or completion generation behavior.
  Evidence: `uv run pytest -q tests/test_cli_harness.py tests/test_completion.py ...` (full targeted command suite) → `144 passed`.
- Observation: Harness extraction required package-relative import correction (`..harness`, `..harness_store`, `..loop`) because command modules live under `ralph_gold.commands`.
  Evidence: initial lint/import checks failed until import paths were adjusted; post-fix targeted suite remained green (`144 passed`).
- Observation: JSON-mode latent bug in `diagnose` surfaced once `RALPH_FORMAT`/global `--format json` began taking effect (`DiagnosticResult.name` vs `check_name`).
  Evidence: local smoke run failed with `'DiagnosticResult' object has no attribute 'name'`; fixed by using `check_name`, then contract tests passed.
- Observation: Gitleaks default detections on this machine did not flag standalone AWS key IDs or private-key headers, so explicit repo-local rules were required for deterministic scanner tests.
  Evidence: ad-hoc scans with and without `.gitleaks.toml` on temporary files returned `rc=0` until custom rules were added; after updates, `uv run pytest -q tests/test_gitleaks_config.py` passed.
- Observation: Full-suite verification issues from the prior checkpoint are now resolved.
  Evidence: `uv run pytest -q tests/test_prd_task_lookup.py tests/test_loop_mode_runtime.py tests/test_gitleaks_config.py` → `25 passed, 3 skipped`; full `uv run pytest -q` → `1218 passed, 3 skipped`.
- Observation: Version metadata drift existed across packaging/runtime/changelog (`pyproject=0.8.1`, runtime `__version__=1.0.0`, changelog latest `0.8.2`) and required explicit canonicalization.
  Evidence: repo scan on 2026-03-05; after T08 changes `uv run python scripts/check_version_sync.py` reports `Version sync OK: 0.8.2`, and full suite is green (`1223 passed, 3 skipped`).
- Observation: Authorization enforcement previously covered only anchor writes; post-run write effects (including untracked files) were unchecked.
  Evidence: code inspection around `run_iteration` authorization flow; T09 adds `_get_write_effect_files` and `authorization_post_write_effects` receipt coverage with targeted tests (`53 passed`).
- Observation: Documentation drift existed for CLI global flags/output controls and authorization scope (anchor-only wording).
  Evidence: Updated `README.md`, `docs/COMMANDS.md`, `docs/CONFIGURATION.md`, and `docs/AUTHORIZATION.md`; full regression run remains green (`1223 passed, 3 skipped`).

## Decision Log

- Decision: Use incremental PR slices with explicit dependencies rather than a single large rewrite.
  Rationale: Reduces regression risk and keeps behavior verifiable at each merge point.
  Date/Author: 2026-03-04 (Codex).

- Decision: Prioritize UX simplification and machine-contract stability before deeper architecture refactors.
  Rationale: Delivers immediate user/agent value while creating clearer guardrails for internal changes.
  Date/Author: 2026-03-04 (Codex).

- Decision: Ship `[ux]` as non-breaking policy metadata first, then add behavior changes in later slices.
  Rationale: Allows docs/help improvements immediately without disrupting existing automation or command flows.
  Date/Author: 2026-03-04 (Codex).

- Decision: Implement quickstart as an additive command that reuses `init_project` and applies profile metadata post-init.
  Rationale: Minimizes risk by avoiding scaffold duplication while still wiring profile presets into initialization flow.
  Date/Author: 2026-03-04 (Codex).

- Decision: Implement explainability as a dedicated `ralph explain` command rather than overloading `status`.
  Rationale: Preserves existing `status` behavior while delivering a single-purpose explainability surface with stable text/JSON fields.
  Date/Author: 2026-03-05 (Codex).

- Decision: Start T05 modularization by extracting the newest UX-focused commands first (`quickstart`, `explain`) before moving legacy command families.
  Rationale: Low-risk decomposition path with immediate reduction in `cli.py` surface area and clear, test-backed boundaries.
  Date/Author: 2026-03-05 (Codex).

- Decision: Extract monitoring command family next (`diagnose`, `stats`, `status`) into a dedicated module before tackling harness/loop-heavy areas.
  Rationale: This cluster has clear boundaries, strong test coverage, and minimal coupling to execution orchestration internals.
  Date/Author: 2026-03-05 (Codex).

- Decision: Extract maintenance/state command family before loop handler extraction.
  Rationale: It meaningfully reduces `cli.py` size with low coupling risk, while preserving existing tests that monkeypatch loop internals on `ralph_gold.cli`.
  Date/Author: 2026-03-04 (Codex).

- Decision: Extract planning/specs/snapshot/watch/task handlers before loop runtime handlers.
  Rationale: These handlers have low coupling to loop internals and can move cleanly without disturbing monkeypatch-based loop mode tests.
  Date/Author: 2026-03-05 (Codex).

- Decision: Use dependency-injected wrappers for `step`/`run`/`supervise` instead of importing these handlers directly from module scope.
  Rationale: Preserves external test and tooling expectations on `ralph_gold.cli` symbols while still moving most implementation code out of the monolith.
  Date/Author: 2026-03-05 (Codex).

- Decision: Extract low-coupling utility commands before harness decomposition.
  Rationale: Keeps momentum with minimal regression risk while setting up a clean pattern for final command-family extraction.
  Date/Author: 2026-03-05 (Codex).

- Decision: Move full harness family in one slice rather than partial wrappers.
  Rationale: These commands share `_resolve_path` and internal collect/run composition (`cmd_harness_ci` calling collect/run), so cohesive extraction reduces cross-module churn.
  Date/Author: 2026-03-05 (Codex).

- Decision: Enforce a single CLI JSON envelope via centralized normalization + fallback emission in `main`.
  Rationale: Guarantees machine-readable output even for commands that currently have text-only paths, while allowing incremental per-command JSON enrichment.
  Date/Author: 2026-03-05 (Codex).

- Decision: Use `src/ralph_gold/__init__.py` `__version__` as the canonical release source via Hatch dynamic versioning, with changelog parity enforced by a dedicated check script and CI step.
  Rationale: Removes multi-file manual bumps and turns version/changelog drift into a deterministic CI failure.
  Date/Author: 2026-03-05 (Codex).

- Decision: Enforce write authorization in two phases: prewrite (anchor) and post-run write-effect scan, with block mode turning denied writes into iteration failure (`return_code=73`) and a dedicated gate entry.
  Rationale: Preserves existing warn-mode observability while extending safety coverage to real agent write effects without invasive per-write wrappers.
  Date/Author: 2026-03-05 (Codex).

- Decision: Add explicit docs-first v1.1 migration posture (simple/expert guidance, global output precedence, and authorization receipts) before finalizing verification.
  Rationale: Reduces operator confusion and gives both humans and agent integrations a stable contract surface to target.
  Date/Author: 2026-03-05 (Codex).

## Outcomes & Retrospective

- Outcome: v1.1 simplification + hardening goals are implemented as merge-safe slices with end-to-end verification.
- What improved for humans: quickstart onboarding, simple/expert guidance, clearer explainability (`ralph explain`), and updated docs with table-of-contents/navigation refresh.
- What improved for agents: stable JSON envelope (`ralph.cli.v1`), global machine-output controls (`--format`, `--verbosity`, env fallbacks), and deterministic version-sync checks in CI.
- What improved for safety/operations: authorization now covers post-run write effects with path-level allow/deny receipts and block-mode enforcement, plus preserved warn-mode observability.
- Verification evidence: `uv run python scripts/check_version_sync.py` → `Version sync OK: 0.8.2`; `uv run pytest -q` → `1223 passed, 3 skipped`; targeted lint/test slices stayed green throughout.

## Context and Orientation

Core CLI entrypoint is `/Users/jamiecraik/dev/ralph-gold/src/ralph_gold/cli.py`. Core loop runtime is `/Users/jamiecraik/dev/ralph-gold/src/ralph_gold/loop.py`. JSON output helpers are in `/Users/jamiecraik/dev/ralph-gold/src/ralph_gold/json_response.py` and `/Users/jamiecraik/dev/ralph-gold/src/ralph_gold/output.py`. Authorization behavior currently lives in `/Users/jamiecraik/dev/ralph-gold/src/ralph_gold/authorization.py` and is invoked in loop execution. User docs are primarily `/Users/jamiecraik/dev/ralph-gold/README.md` and `/Users/jamiecraik/dev/ralph-gold/docs/COMMANDS.md`.

In this plan, a “slice” means a merge-safe, independently testable change set. “Simple mode” means reduced cognitive load defaults; “Expert mode” means complete command/flag surface and advanced controls. “Machine contract” means versioned and stable JSON response fields suitable for automation.

## Plan of Work

First capture baseline behavior for core commands and JSON output so refactors have objective before/after comparisons. Then ship UX simplification in additive form: introduce explicit simple/expert posture and a `quickstart` command without removing existing expert workflows. Next, extract CLI command handlers into modules and split loop responsibilities into focused services while keeping runtime behavior stable through compatibility tests. After that, normalize JSON output contracts and add schema-version checks in tests. Then enforce a single version source and CI consistency checks to prevent release drift. Finally, extend authorization checks to all write effects and provide explicit allow/deny evidence in receipts and user-visible output. End with full validation and docs updates.

## Task Graph Contract

```yaml
tasks:
  - id: T01
    title: Establish baseline behavior and contract snapshots
    depends_on: []
    pr_slice: "PR-1 baseline"
    deliverables:
      - "Captured text + JSON outputs for key commands (init, step, run, status, doctor, diagnose)."
      - "Baseline notes for current version/reporting behavior."

  - id: T02
    title: Define simple mode and expert mode UX policy
    depends_on: [T01]
    pr_slice: "PR-2 mode policy"
    deliverables:
      - "Documented mode semantics and defaults in config + help text."
      - "No-breaking-change rollout path for existing users."

  - id: T03
    title: Add guided onboarding command (ralph quickstart)
    depends_on: [T02]
    pr_slice: "PR-3 onboarding"
    deliverables:
      - "Interactive/non-interactive quickstart command for first-run setup."
      - "Recommended profile presets wired into initialization flow."

  - id: T04
    title: Add explainability UX surface for next action reasoning
    depends_on: [T02]
    pr_slice: "PR-4 explainability"
    deliverables:
      - "Single command output showing why selected, why blocked, and what next."
      - "Parity between text output and JSON output for explainability fields."

  - id: T05
    title: Modularize CLI command handlers
    depends_on: [T01, T02]
    pr_slice: "PR-5 cli modularization"
    deliverables:
      - "Move command implementations out of cli.py into command modules."
      - "Keep parser compatibility and existing flags stable."

  - id: T06
    title: Modularize loop orchestration into focused services
    depends_on: [T01, T05]
    pr_slice: "PR-6 loop modularization"
    deliverables:
      - "Extract task selection, prompt build, execution, gate evaluation, and state transition services."
      - "Keep run/step behavior consistent with baseline acceptance tests."

  - id: T07
    title: Unify machine interface with versioned JSON schemas
    depends_on: [T05, T06]
    pr_slice: "PR-7 json contracts"
    deliverables:
      - "Consistent --format json behavior across command surface."
      - "Stable schema_version field in machine responses."
      - "Contract tests for backward compatibility expectations."

  - id: T08
    title: Enforce release version single source of truth
    depends_on: [T01]
    pr_slice: "PR-8 release discipline"
    deliverables:
      - "One canonical version source used by package metadata and runtime version output."
      - "CI check failing on version/changelog drift."

  - id: T09
    title: Expand authorization checks to all write effects
    depends_on: [T06]
    pr_slice: "PR-9 auth hardening"
    deliverables:
      - "Authorization applied to all write-side effects, not only prep artifacts."
      - "Explicit allow/deny receipts and actionable error messaging."

  - id: T10
    title: Update docs and migration notes for v1.1 behavior
    depends_on: [T03, T04, T07, T08, T09]
    pr_slice: "PR-10 docs"
    deliverables:
      - "README and command/config docs updated for simple/expert, quickstart, explainability, JSON contracts, and release policy."
      - "Migration notes for existing users and automation consumers."

  - id: T11
    title: Run full verification and publish completion evidence
    depends_on: [T10]
    pr_slice: "PR-11 verification"
    deliverables:
      - "Test + lint + smoke verification output captured."
      - "Retrospective updates in this plan and release-ready summary."
```

## Concrete Steps

Run from `/Users/jamiecraik/dev/ralph-gold` using `zsh -lc`:

    uv run ralph --help
    uv run ralph --version
    uv run pytest -q
    python3 /Users/jamiecraik/.codex/scripts/plan-graph-lint.py .agent/PLANS.md
    /Users/jamiecraik/.codex/scripts/verify-work.sh

For each slice, capture before/after behavior with exact commands and concise outputs.

## Validation and Acceptance

Acceptance is met when all task IDs in the graph are complete and behavior is demonstrably improved:

- New users can run `ralph quickstart` and reach first successful iteration with minimal decisions.
- Advanced users still access the full command and flag surface without regressions.
- JSON output is consistent and versioned across the intended command surface.
- Version output, package metadata, and changelog policy are synchronized by automation.
- Authorization behavior clearly reports and records allow/deny decisions for write actions.
- Project verification commands pass, or any failures are documented with exact remediation.

## Idempotence and Recovery

This plan is additive and slice-based. If a slice fails validation, revert only that slice and rerun its tests before proceeding. Keep each PR slice small enough to rollback independently. Avoid destructive operations on `.ralph/` runtime artifacts unless explicitly required by a test scenario.

## Artifacts and Notes

Record these artifacts as slices complete:

    git status --short
    uv run pytest -q
    uv run ralph --help
    uv run ralph --version
    python3 /Users/jamiecraik/.codex/scripts/plan-graph-lint.py .agent/PLANS.md
    artifacts/baseline/2026-03-04-t01-command-baseline.md

## Interfaces and Dependencies

Maintain compatibility for existing entrypoints in `/Users/jamiecraik/dev/ralph-gold/src/ralph_gold/cli.py` and `/Users/jamiecraik/dev/ralph-gold/src/ralph_gold/loop.py` while introducing modular internals. Ensure JSON helpers in `/Users/jamiecraik/dev/ralph-gold/src/ralph_gold/json_response.py` and `/Users/jamiecraik/dev/ralph-gold/src/ralph_gold/output.py` carry versioned response metadata. Ensure authorization enforcement in `/Users/jamiecraik/dev/ralph-gold/src/ralph_gold/authorization.py` is applied wherever writes are orchestrated.

Plan change note: Replaced legacy 2026-01-23 implementation narrative with an execution-ready dependency graph for the v1.1 simplification and hardening program, per stakeholder request for phased low-risk delivery.

<!-- AGENT-FIRST-PLANS:START -->
## Plan Contract (Agent-first)

All significant implementation plans MUST use task graphs with explicit dependencies.

Validation command:

```bash
python3 /Users/jamiecraik/.codex/scripts/plan-graph-lint.py .agent/PLANS.md
```

Valid sample plan:

```yaml
tasks:
  - id: T1
    title: Define scope and constraints
    depends_on: []
  - id: T2
    title: Implement scaffold updates
    depends_on: [T1]
  - id: T3
    title: Run verification and publish report
    depends_on: [T2]
```

Optional cross-plan reference:

```yaml
external_dep: "/absolute/repo/path#T12"
```
<!-- AGENT-FIRST-PLANS:END -->
