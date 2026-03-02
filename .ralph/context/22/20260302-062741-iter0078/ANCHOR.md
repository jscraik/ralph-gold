# Ralph Gold Anchor

Task: 22 - Add blocked task rate calculation to stats.py

Acceptance criteria:
- Calculate percentage of tasks that get blocked
- Track blocked attempts per task
- Return metrics in stats output
- Test: `uv run pytest -q tests/test_stats.py -k test_blocked_rate` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/state.json
?? .ralph/attempts/21/
```
- git diff --stat:
```
.ralph/state.json | 59 ++++++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 58 insertions(+), 1 deletion(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

