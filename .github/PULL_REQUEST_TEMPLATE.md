# Pull request checklist

## Summary

- What changed (brief):
- Why this change was needed:
- Risk and rollback plan:

## Checklist

- [ ] I did not push directly to `main`; this PR is from a dedicated branch.
- [ ] Branch name follows policy (`codex/*` for agent-created branches).
- [ ] Required local gates run: `npm run lint`, `npm run typecheck`, `npm run test`, `npm run audit`, `npm run check`, `test -f memory.json && jq -e '.meta.version == "1.0" and (.preamble.bootstrap | type == "boolean") and (.preamble.search | type == "boolean") and (.entries | type == "array")' memory.json >/dev/null`.
- [ ] Required CI security gate passed: `security-scan` (gitleaks + trivy + semgrep).
- [ ] Greptile setup verified with `grepfile` skill and `.greptile/config.json`, `.greptile/rules.md`, `.greptile/files.json`.
- [ ] Greptile review completed and findings handled (or explicitly waived).
- [ ] Codex review completed and findings handled (or explicitly waived).
- [ ] Greptile review was performed by an independent reviewer (not the coding agent).
- [ ] Greptile confidence score is `>= 4/5` for merge eligibility.
- [ ] Merge is blocked until all required checks pass.
- [ ] I will delete branch/worktree after merge.

## Testing

- Command: `npm run lint` -> pass/fail
- Command: `npm run typecheck` -> pass/fail
- Command: `npm run test` -> pass/fail
- Command: `npm run audit` -> pass/fail
- Command: `npm run check` -> pass/fail
- Command: `security-scan` (CI check) -> pass/fail
- Command: `test -f memory.json && jq -e '.meta.version == "1.0" and (.preamble.bootstrap | type == "boolean") and (.preamble.search | type == "boolean") and (.entries | type == "array")' memory.json >/dev/null` -> pass/fail
- Any other command(s):

## Review artifacts

- Greptile: <link / artifact path / comment ID>
- Greptile confidence score: <0-5>
- Independent reviewer evidence: <reviewer + link>
- Codex: <link / artifact path / comment ID>
- Additional evidence (if any):

## Notes

Add one-paragraph merge rationale here.
