# Ralph Gold Anchor

Task: 32 - Integrate adaptive rigor into loop

Acceptance criteria:
- Calculate risk before each iteration
- Adjust gate requirements accordingly
- Log risk level and gate adjustments
- Test: `uv run pytest -q tests/test_loop_mode_runtime.py -k test_adaptive` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/state.json
?? .ralph/attempts/31/
```
- git diff --stat:
```
.ralph/state.json | 586 +++++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 584 insertions(+), 2 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

