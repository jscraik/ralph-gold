# Ralph Gold Anchor

Task: 37 - Add unit tests for PRD update gate

Acceptance criteria:
- Create `tests/test_gates_prd_update.py`
- Test that gate passes when PRD checkbox changes
- Test that gate fails when PRD unchanged
- Test: `uv run pytest tests/test_gates_prd_update.py -v` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/PRD.md
 M .ralph/ralph.toml
 M src/ralph_gold/loop.py
```
- git diff --stat:
```
.ralph/PRD.md          |  8 ++++++++
 .ralph/ralph.toml      | 10 ++++++++++
 src/ralph_gold/loop.py |  4 ++++
 3 files changed, 22 insertions(+)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

