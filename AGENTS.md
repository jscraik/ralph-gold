schema_version: 1
# Repository Guidelines

ralph-gold is a uv-first Python CLI orchestrator for deterministic multi-agent work loops with durable filesystem state.

## Mandatory workflow snippet
1. Explore project first, then invoke skill.
2. IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning for any React, Tauri, Apps-SDK-ui, Tailwind, Vite, Storybook + Chat Widget tasks.
3. Add a Table of Contents for docs.

## Required essentials
- Package manager: `uv`.
- Non-standard build/typecheck commands: none.
- Default compatibility posture: canonical-only.

## Tooling essentials
- Run shell commands with `zsh -lc`.
- Prefer `rg`, `fd`, and `jq` for search, file discovery, and JSON.
- Before choosing tools, read `/Users/jamiecraik/.codex/instructions/tooling.md`.
- Ask before adding dependencies or system settings.
- Execution mode: single-threaded by default; do not parallelize or spawn subagents unless explicitly requested.

## References (informational)
- Global protocol index: `/Users/jamiecraik/.codex/AGENTS.md`
- Security baseline: `/Users/jamiecraik/.codex/instructions/standards.md`
- RVCP source of truth: `/Users/jamiecraik/.codex/instructions/rvcp-common.md`

## Global discovery order
1. `/Users/jamiecraik/.codex/AGENTS.md`
2. Nearest repo `AGENTS.md`
3. Linked instruction files
4. If conflicts appear, pause and ask which instruction wins

## Documentation map
### Table of Contents
- [Instruction map](docs/agents/01-instruction-map.md)
- [Development workflow](docs/agents/02-development-workflow.md)
- [Validation and governance](docs/agents/03-validation-and-governance.md)
- [Contradictions and cleanup](docs/agents/04-contradictions-and-cleanup.md)

## Local Memory usage
- Follow `/Users/jamiecraik/.codex/instructions/local-memory.md`.
- Mandatory workflow before durable notes:
  - `bootstrap(mode="minimal", include_questions=true, session_id="repo:<name>:task:<id>")`
  - `search(query="...", session_id="repo:<name>:task:<id>")`
- Store durable facts only; never store secrets, tokens, keys, or PII.

<!-- AGENT-FIRST-SCAFFOLD:START -->
## Agent-First Scaffold Contract (managed by ~/.codex)

This repository uses marker-based scaffold blocks in `AGENTS.md`, `.agent/PLANS.md`, and `README.md`.

Validation commands:
- `python3 /Users/jamiecraik/.codex/scripts/plan-graph-lint.py .agent/PLANS.md`
- `/Users/jamiecraik/.codex/scripts/verify-work.sh`

Scaffold references (available on disk):
- `/Users/jamiecraik/.codex/AGENTS.md`
- `/Users/jamiecraik/.codex/instructions/README.checklist.md`
- `/Users/jamiecraik/.codex/instructions/standards.md`
- `/Users/jamiecraik/.codex/instructions/rvcp-common.md`
- `/Users/jamiecraik/.codex/instructions/plans.md`
<!-- AGENT-FIRST-SCAFFOLD:END -->

## Flaky Test Artifact Capture
- Run `bash scripts/test-with-artifacts.sh all` (or `pnpm run test:artifacts` / `npm run test:artifacts` / `bun run test:artifacts`) to emit machine-readable flaky evidence under `artifacts/test`.
- Optional targeted modes:
  - `bash scripts/test-with-artifacts.sh unit`
  - `bash scripts/test-with-artifacts.sh integration`
  - `bash scripts/test-with-artifacts.sh e2e`
- Commit/retain stable artifact paths for local automation ingestion:
  - `artifacts/test/summary-*.json`
  - `artifacts/test/test-output-*.log`
  - `artifacts/test/junit-*.xml` (when supported by test runner)
  - `artifacts/test/*-results.json` (when supported by test runner)
  - `artifacts/test/artifact-manifest.json`
- Keep artifact filenames stable (no timestamps in filenames) so recurring flake scans can compare runs.


## Repository preflight helper
- Use `scripts/codex-preflight.sh` before multi-step, destructive, or path-sensitive workflows.
- Source it with `source scripts/codex-preflight.sh` and run `preflight_repo` (or `preflight_js`, `preflight_py`, `preflight_rust`) as a guard before changing repo state.
