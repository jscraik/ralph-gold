# Ralph Gold Anchor

Task: 4 - Implement smart gate selection (config + runtime)

Acceptance criteria:
- Add `gates.smart.enabled` and `gates.smart.skip_gates_for` in config parsing.
- Use `git diff --name-only HEAD` to compute changed files (graceful fallback if missing).
- Skip gates when all changed files match `skip_gates_for` patterns.
- `uv run pytest -q tests/test_smart_gates.py` passes.

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/PRD.md
 M .ralph/progress.md
 M .ralph/state.json
?? .ralph/attempts/
?? .ralph/context/
?? .ralph/receipts/
```
- git diff --stat:
```
.ralph/PRD.md      |   6 +-
 .ralph/progress.md |  20 ++++
 .ralph/state.json  | 318 ++++++++++++++++++++++++++++++++++++++++++++++++++++-
 3 files changed, 339 insertions(+), 5 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

