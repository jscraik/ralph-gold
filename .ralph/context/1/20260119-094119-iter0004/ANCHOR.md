# Ralph Gold Anchor

Task: 1 - Add loop mode config schema + parsing

Acceptance criteria:
- Parse `loop.mode` and `loop.modes.*` into new config types (no breaking changes).
- Provide safe defaults when modes are absent or incomplete.
- Unknown mode names produce a clear config error.
- `uv run pytest -q tests/test_config_loop_modes.py` passes.

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/progress.md
 M .ralph/state.json
?? .ralph/attempts/
?? .ralph/context/
?? .ralph/receipts/
```
- git diff --stat:
```
.ralph/progress.md |  3 +++
 .ralph/state.json  | 75 +++++++++++++++++++++++++++++++++++++++++++++++++++---
 2 files changed, 75 insertions(+), 3 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

