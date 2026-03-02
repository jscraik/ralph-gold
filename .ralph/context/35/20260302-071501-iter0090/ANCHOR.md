# Ralph Gold Anchor

Task: 35 - Add validation to ralph regen-plan command

Acceptance criteria:
- Run validation after plan generation
- Display warnings to user
- Continue unless --strict flag used
- Test: `uv run pytest -q tests/test_cli_templates.py -k test_validate` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/state.json
?? .ralph/attempts/34/
```
- git diff --stat:
```
.ralph/state.json | 781 +++++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 778 insertions(+), 3 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

