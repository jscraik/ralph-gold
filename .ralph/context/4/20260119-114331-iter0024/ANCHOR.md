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
 M src/ralph_gold/bridge.py
 M src/ralph_gold/cli.py
 M src/ralph_gold/completion.py
 M src/ralph_gold/config.py
 M src/ralph_gold/loop.py
 M src/ralph_gold/tui.py
?? .ralph/attempts/1/20260119-111750-iter0026.json
?? .ralph/attempts/1/20260119-111759-iter0021.json
?? .ralph/attempts/2/20260119-112051-iter0027.json
?? .ralph/attempts/2/20260119-112107-iter0022.json
?? .ralph/attempts/2/20260119-112250-iter0022.json
?? .ralph/attempts/3/20260119-113011-iter0028.json
?? .ralph/attempts/3/20260119-113537-iter0023.json
?? .ralph/context/2/20260119-112051-iter0027/
?? .ralph/context/2/20260119-112107-iter0022/
?? .ralph/context/2/20260119-112250-iter0022/
?? .ralph/context/3/20260119-113011-iter0028/
?? .ralph/context/3/20260119-113537-iter0023/
?? .ralph/context/3/20260119-113608-iter0023/
?? .ralph/context/4/20260119-113948-iter0029/
?? .ralph/receipts/1/20260119-111750-iter0026/runner.json
?? .ralph/receipts/1/20260119-111759-iter0021/runner.json
?? .ralph/receipts/2/20260119-112051-iter0027/
?? .ralph/receipts/2/20260119-112107-iter0022/
?? .ralph/receipts/2/20260119-112250-iter0022/
?? .ralph/receipts/3/20260119-113011-iter0028/
?? .ralph/receipts/3/20260119-113537-iter0023/
?? .ralph/receipts/3/20260119-113608-iter0023/
?? .ralph/receipts/4/20260119-113948-iter0029/
?? tests/test_cli_mode.py
?? tests/test_loop_mode_runtime.py
```
- git diff --stat:
```
.ralph/PRD.md                |   4 +-
 .ralph/progress.md           |  16 +++++++
 .ralph/state.json            | 108 ++++++++++++++++++++++++++++++++++++++++---
 src/ralph_gold/bridge.py     |   7 ++-
 src/ralph_gold/cli.py        |  68 +++++++++++++++++++++++++--
 src/ralph_gold/completion.py |  11 ++++-
 src/ralph_gold/config.py     |   1 +
 src/ralph_gold/loop.py       |  54 +++++++++++++++++++++-
 src/ralph_gold/tui.py        |   3 +-
 9 files changed, 253 insertions(+), 19 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

