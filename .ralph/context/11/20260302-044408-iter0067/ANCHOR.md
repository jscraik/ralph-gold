# Ralph Gold Anchor

Task: 11 - Add get_changed_files() function to gates.py

Acceptance criteria:
- Use `git diff --name-only HEAD` to get changed files
- Return empty list on error (fail-open for safety)
- Handle case when not in git repo gracefully
- Test: `uv run pytest -q tests/test_gates_enhanced.py -k test_changed_files` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/PRD.md
 M .ralph/progress.md
 M .ralph/ralph.toml
 M .ralph/state.json
 M src/ralph_gold/config.py
 M tests/test_gates_enhanced.py
?? .ralph/attempts/10/20260302-043949-iter0066.json
?? .ralph/attempts/6/20260302-042100-iter0062.json
?? .ralph/attempts/7/20260302-042135-iter0063.json
?? .ralph/attempts/8/20260302-042642-iter0064.json
?? .ralph/attempts/9/20260302-043811-iter0065.json
?? .ralph/context/10/20260302-043949-iter0066/
?? .ralph/context/6/20260302-042100-iter0062/
?? .ralph/context/7/20260302-042135-iter0063/
?? .ralph/context/8/20260302-042642-iter0064/
?? .ralph/context/9/20260302-043811-iter0065/
?? .ralph/receipts/10/20260302-043949-iter0066/
?? .ralph/receipts/6/20260302-042100-iter0062/
?? .ralph/receipts/7/20260302-042135-iter0063/
?? .ralph/receipts/8/20260302-042642-iter0064/
?? .ralph/receipts/9/20260302-043811-iter0065/
?? docs/brainstorms/2026-03-01-adaptive-intervention-engine-brainstorm.md
?? docs/plans/2026-03-01-feat-adaptive-intervention-recommendation-engine-plan.md
?? ops/
?? tests/test_config.py
```
- git diff --stat:
```
.ralph/PRD.md                |  10 +-
 .ralph/progress.md           | 186 ++++---------------------
 .ralph/ralph.toml            |   5 +
 .ralph/state.json            | 317 ++++++++++++++++++++++++++++++++++++++++++-
 src/ralph_gold/config.py     |   6 +-
 tests/test_gates_enhanced.py |  10 +-
 6 files changed, 356 insertions(+), 178 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

