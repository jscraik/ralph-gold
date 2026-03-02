# Ralph Gold Anchor

Task: 7 - Apply mode overrides in loop.py before execution

Acceptance criteria:
- Call `resolve_mode_overrides()` at start of `run_loop()`
- Pass resolved config to `run_iteration()`
- Test: `uv run pytest -q tests/test_loop_mode_runtime.py -k test_apply` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/PRD.md
 M .ralph/progress.md
 M .ralph/state.json
?? .ralph/attempts/6/20260302-042100-iter0062.json
?? .ralph/context/6/20260302-042100-iter0062/
?? .ralph/receipts/6/20260302-042100-iter0062/
?? docs/brainstorms/2026-03-01-adaptive-intervention-engine-brainstorm.md
?? docs/plans/2026-03-01-feat-adaptive-intervention-recommendation-engine-plan.md
?? ops/
```
- git diff --stat:
```
.ralph/PRD.md      |  2 +-
 .ralph/progress.md |  2 ++
 .ralph/state.json  | 68 ++++++++++++++++++++++++++++++++++++++++++++++++++++--
 3 files changed, 69 insertions(+), 3 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

