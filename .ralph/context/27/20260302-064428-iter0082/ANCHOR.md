# Ralph Gold Anchor

Task: 27 - Create PROMPT_exploration.md template

Acceptance criteria:
- Add template for exploration tasks
- Emphasize learning and experimentation
- Allow longer iterations
- Test: `uv run pytest -q tests/test_templates.py -k test_prompt_explore` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/state.json
?? .ralph/attempts/26/
```
- git diff --stat:
```
.ralph/state.json | 295 +++++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 293 insertions(+), 2 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

