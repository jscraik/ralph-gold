# Ralph Gold Anchor

Task: 26 - Create PROMPT_hotfix.md template

Acceptance criteria:
- Add template for urgent fixes
- Emphasize minimal changes and testing
- Skip non-critical quality checks
- Test: `uv run pytest -q tests/test_templates.py -k test_prompt_hotfix` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/state.json
?? .ralph/attempts/25/
```
- git diff --stat:
```
.ralph/state.json | 238 +++++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 236 insertions(+), 2 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

