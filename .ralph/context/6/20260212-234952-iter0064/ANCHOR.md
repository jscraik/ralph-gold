# Ralph Gold Anchor

Task: 6 - Add LoopModeOverride dataclass to config.py

Acceptance criteria:
- Add `LoopModeOverride` with fields for max_iterations, gates, etc.
- Add `resolve_mode_overrides()` function to merge mode into config
- Test: `uv run pytest -q tests/test_config_loop_modes.py -k test_resolve` passes

Repo reality:
- branch: codex/auto-checkpoint/20260212-145749
- git status --porcelain:
```
M .ralph/PRD.md
 M .ralph/progress.md
 M .ralph/state.json
?? .ralph/attempts/6/20260212-234842-iter0062.json
?? .ralph/context/6/20260212-234842-iter0062/
?? .ralph/receipts/6/20260212-234842-iter0062/
```
- git diff --stat:
```
.ralph/PRD.md      |   2 +-
 .ralph/progress.md |   2 +
 .ralph/state.json  | 112 +++++++++++++++++++++++++++++++++++++++++++++++++++--
 3 files changed, 112 insertions(+), 4 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

