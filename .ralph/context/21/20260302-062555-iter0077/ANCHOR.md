# Ralph Gold Anchor

Task: 21 - Add velocity calculation to stats.py

Acceptance criteria:
- Calculate tasks/hour from iteration history
- Handle empty history gracefully
- Return 0.0 for insufficient data
- Test: `uv run pytest -q tests/test_stats.py -k test_velocity` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M src/ralph_gold/loop.py
```
- git diff --stat:
```
src/ralph_gold/loop.py | 1 +
 1 file changed, 1 insertion(+)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

