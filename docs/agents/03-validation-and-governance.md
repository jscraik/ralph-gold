# Validation and governance

## Working with project instructions
- Global scope: Codex reads `/Users/jamiecraik/.codex/AGENTS.override.md` if present; otherwise `/Users/jamiecraik/.codex/AGENTS.md`.
- Project scope: discover instruction files from repo root to working directory.
- Per-directory order: `AGENTS.override.md`, `AGENTS.md`, then fallback names in `project_doc_fallback_filenames`.
- Use `CODEX_HOME` to switch profiles when needed.

## ExecPlans
- For complex features or major refactors, follow:
  - `/Users/jamiecraik/.codex/instructions/plans.md`
  - `/Users/jamiecraik/dev/ralph-gold/.agent/PLANS.md` (if present)

## Security and configuration
- Treat `.ralph/*` logs as sensitive.
- Do not store secrets in prompts or logs.
- Prefer least-privilege environments for long-running loops.

## AI assistance governance (Model A)
When a PR uses AI assistance:
1. Save artifacts:
   - Prompt: `/Users/jamiecraik/dev/ralph-gold/ai/prompts/YYYY-MM-DD-<slug>.yaml`
   - Session: `/Users/jamiecraik/dev/ralph-gold/ai/sessions/YYYY-MM-DD-<slug>.json`
2. Commit both files.
3. Reference exact artifact paths in the PR body.
4. Do not paste prompt/log excerpts into PR descriptions.
5. Abort if artifacts cannot be created and committed.

Templates:
- `/Users/jamiecraik/dev/ralph-gold/ai/prompts/.template.yaml`
- `/Users/jamiecraik/dev/ralph-gold/ai/sessions/.template.json`

PR template:
- `/Users/jamiecraik/dev/ralph-gold/.github/PULL_REQUEST_TEMPLATE.md`

## Scaffold checks
- Plan graph lint:
  - `python3 /Users/jamiecraik/.codex/scripts/plan-graph-lint.py /Users/jamiecraik/dev/ralph-gold/.agent/PLANS.md`
- Canonical verification:
  - `/Users/jamiecraik/.codex/scripts/verify-work.sh`
