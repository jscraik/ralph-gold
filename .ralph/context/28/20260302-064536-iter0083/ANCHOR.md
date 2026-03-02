# Ralph Gold Anchor

Task: 28 - Add prompt selection logic to loop.py

Acceptance criteria:
- Detect task type from title/tags
- Select appropriate prompt template
- Fall back to default PROMPT_build.md
- Test: `uv run pytest -q tests/test_loop_mode_runtime.py -k test_prompt_select` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/state.json
?? .ralph/attempts/27/
```
- git diff --stat:
```
.ralph/state.json | 352 +++++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 350 insertions(+), 2 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

