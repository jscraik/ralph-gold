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
M .ralph/progress.md
 M .ralph/ralph.toml
 M .ralph/state.json
 M src/ralph_gold/cli.py
 M src/ralph_gold/loop.py
 M src/ralph_gold/prd.py
 M src/ralph_gold/subprocess_helper.py
 M src/ralph_gold/unblock.py
 M tests/test_prd_task_lookup.py
?? .ralph/attempts/6/20260212-234842-iter0062.json
?? .ralph/attempts/6/20260213-000115-iter0064.json
?? .ralph/context/6/20260212-234842-iter0062/
?? .ralph/context/6/20260212-234952-iter0064/
?? .ralph/context/6/20260212-235917-iter0064/
?? .ralph/context/6/20260213-000010-iter0064/
?? .ralph/context/6/20260213-000115-iter0064/
?? .ralph/context/6/20260213-000201-iter0065/
?? .ralph/receipts/6/20260212-234842-iter0062/
?? .ralph/receipts/6/20260212-234952-iter0064/
?? .ralph/receipts/6/20260212-235917-iter0064/
?? .ralph/receipts/6/20260213-000010-iter0064/
?? .ralph/receipts/6/20260213-000115-iter0064/
?? .ralph/receipts/6/20260213-000201-iter0065/
?? tests/test_cli_unblock.py
?? tests/test_subprocess_helper.py
```
- git diff --stat:
```
.ralph/progress.md                  |   7 ++
 .ralph/ralph.toml                   |   2 +-
 .ralph/state.json                   | 179 +++++++++++++++++++++++++++++++++++-
 src/ralph_gold/cli.py               |  15 ++-
 src/ralph_gold/loop.py              |   9 +-
 src/ralph_gold/prd.py               |   4 +-
 src/ralph_gold/subprocess_helper.py |   4 +
 src/ralph_gold/unblock.py           |  68 +++++++-------
 tests/test_prd_task_lookup.py       |  38 +++++++-
 9 files changed, 283 insertions(+), 43 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

