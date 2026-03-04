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
- Run `bash scripts/test-with-artifacts.sh all` to emit machine-readable flaky evidence under `artifacts/test`.
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


## Philosophy

This codebase will outlive you. Every shortcut becomes someone else's burden. Every hack compounds into technical debt that slows the whole team down. Fight entropy. Leave the codebase better than you found it.

## Security & Configuration Tips

- Treat `.ralph/*` logs as sensitive; do not store secrets in prompts or logs.
- Prefer least-privilege environments for long-running loops.
---

# AI Assistance Governance (Model A)

This project follows **Model A** AI artifact governance: prompts and session logs are committed artifacts in the repository.

## When creating PRs with AI assistance

Claude must:

1. **Save artifacts to `ai/` directory**:
   - Final prompt → `ai/prompts/YYYY-MM-DD-<slug>.yaml`
   - Session summary → `ai/sessions/YYYY-MM-DD-<slug>.json`

2. **Commit both files in the PR branch**:
   ```bash
   git add ai/prompts/YYYY-MM-DD-<slug>.yaml ai/sessions/YYYY-MM-DD-<slug>.json
   ```

3. **Reference exact paths in PR body**:
   - Under **AI assistance** section:
     - Prompt: `ai/prompts/YYYY-MM-DD-<slug>.yaml`
     - Session: `ai/sessions/YYYY-MM-DD-<slug>.json`
   - In **AI Session Log** details:
     - Log file: `ai/sessions/YYYY-MM-DD-<slug>.json`
     - Prompt file: `ai/prompts/YYYY-MM-DD-<slug>.yaml`

4. **Do NOT**:
   - Embed prompt/log excerpts in the PR body
   - Link to external logs or pastebins
   - Skip creating artifacts when AI assistance is acknowledged

5. **Abort** if artifacts cannot be created and committed.

## Artifact Templates

See `ai/prompts/.template.yaml` and `ai/sessions/.template.json` for required fields.

## PR Template

All PRs must use `.github/PULL_REQUEST_TEMPLATE.md` which includes required AI disclosure sections.

<!-- AGENT-FIRST-SCAFFOLD:START -->
## Agent-First Scaffold Contract (managed by ~/.codex)

This repository participates in Jamie's global agent-first scaffold program.

Required global references:
- `/Users/jamiecraik/.codex/instructions/openai-agent-workflow-playbook.md`
- `/Users/jamiecraik/.codex/instructions/README.checklist.md`
- `/Users/jamiecraik/.codex/instructions/validator-contracts.md`
- `/Users/jamiecraik/.codex/instructions/strict-toggle-governance.md`
- `/Users/jamiecraik/.codex/instructions/agent-first-scaffold-spec.md`

Repo-level requirements:
- Maintain `.agent/PLANS.md` using `tasks / id / depends_on` contract.
- Validate plan files with:
  `python3 /Users/jamiecraik/.codex/scripts/plan-graph-lint.py <plan-file>`
- Run canonical verification:
  `/Users/jamiecraik/.codex/scripts/verify-work.sh`

State model: `S0 -> S1 -> S2 -> S3 -> S4 -> S5` with rollback to `Sx` on critical governance events.
<!-- AGENT-FIRST-SCAFFOLD:END -->
