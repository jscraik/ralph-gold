# Ralph Gold Anchor

Task: 36 - Add --strict flag to ralph regen-plan

Acceptance criteria:
- Fail if any validation warnings found
- Exit with code 1 and clear error message
- Show how to fix each issue
- Test: `uv run pytest -q tests/test_cli_templates.py -k test_strict` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/state.json
?? .ralph/attempts/35/
```
- git diff --stat:
```
.ralph/state.json | 842 +++++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 839 insertions(+), 3 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

