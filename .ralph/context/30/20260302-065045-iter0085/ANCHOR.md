# Ralph Gold Anchor

Task: 30 - Add failure tracking to state.json

Acceptance criteria:
- Track failures per file/area
- Calculate risk score based on history
- Store in `area_risk_scores` field
- Test: `uv run pytest -q tests/test_stats.py -k test_risk_tracking` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/state.json
?? .ralph/attempts/29/
```
- git diff --stat:
```
.ralph/state.json | 466 +++++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 464 insertions(+), 2 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

