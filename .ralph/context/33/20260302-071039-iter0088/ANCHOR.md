# Ralph Gold Anchor

Task: 33 - Add task complexity detector to prd.py

Acceptance criteria:
- Detect vague tasks (e.g., "Define structure", "Implement feature")
- Count acceptance criteria lines
- Flag tasks without test commands
- Test: `uv run pytest -q tests/test_converters.py -k test_complexity` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/PRD.md
 M .ralph/progress.md
 M .ralph/state.json
?? .ralph/attempts/32/
```
- git diff --stat:
```
.ralph/PRD.md      |   2 +-
 .ralph/progress.md |   1 +
 .ralph/state.json  | 659 ++++++++++++++++++++++++++++++++++++++++++++++++++++-
 3 files changed, 658 insertions(+), 4 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

