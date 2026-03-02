# Ralph Gold Anchor

Task: 34 - Add validate_prd() function

Acceptance criteria:
- Check all tasks for complexity issues
- Return list of warnings
- Suggest breaking down complex tasks
- Test: `uv run pytest -q tests/test_converters.py -k test_validate` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/state.json
?? .ralph/attempts/33/
```
- git diff --stat:
```
.ralph/state.json | 720 +++++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 717 insertions(+), 3 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

