# Ralph Gold Anchor

Task: 31 - Add adaptive gate selection logic

Acceptance criteria:
- Tighten gates for high-risk areas
- Use standard gates for low-risk areas
- Mixed changes follow strictest path
- Test: `uv run pytest -q tests/test_gates_enhanced.py -k test_adaptive` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/state.json
?? .ralph/attempts/30/
```
- git diff --stat:
```
.ralph/state.json | 523 +++++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 521 insertions(+), 2 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

