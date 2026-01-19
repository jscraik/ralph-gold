# Ralph Gold Anchor

Task: 11 - Fix story_id=None infinite loop bug

Acceptance criteria:
- When all tasks are blocked/done, Ralph loops with `story_id=None` instead of exiting.
- Add check in `src/ralph_gold/loop.py` to exit cleanly when no tasks available.
- Exit with code 0 (success) when all tasks done, code 1 when all blocked.
- Add test: `uv run pytest -q tests/test_loop_exit_conditions.py` passes.

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
 M src/ralph_gold/scaffold.py
 M src/ralph_gold/templates/ralph.toml
 M src/ralph_gold/tui.py
?? .ralph/attempts/1/20260119-111750-iter0026.json
?? .ralph/attempts/1/20260119-111759-iter0021.json
?? .ralph/attempts/10/
?? .ralph/attempts/2/20260119-112051-iter0027.json
?? .ralph/attempts/2/20260119-112107-iter0022.json
?? .ralph/attempts/2/20260119-112250-iter0022.json
?? .ralph/attempts/3/20260119-113011-iter0028.json
?? .ralph/attempts/3/20260119-113537-iter0023.json
?? .ralph/attempts/3/20260119-113608-iter0023.json
?? .ralph/attempts/4/20260119-113948-iter0029.json
?? .ralph/attempts/4/20260119-114331-iter0024.json
?? .ralph/attempts/5/
?? .ralph/attempts/6/
?? .ralph/attempts/7/
?? .ralph/attempts/8/
?? .ralph/attempts/9/
?? .ralph/context/10/
?? .ralph/context/2/20260119-112051-iter0027/
?? .ralph/context/2/20260119-112107-iter0022/
?? .ralph/context/2/20260119-112250-iter0022/
?? .ralph/context/3/20260119-113011-iter0028/
?? .ralph/context/3/20260119-113537-iter0023/
?? .ralph/context/3/20260119-113608-iter0023/
?? .ralph/context/4/20260119-113948-iter0029/
?? .ralph/context/4/20260119-114331-iter0024/
?? .ralph/context/5/
?? .ralph/context/6/
?? .ralph/context/7/
?? .ralph/context/8/
?? .ralph/context/9/
?? .ralph/receipts/1/20260119-111750-iter0026/runner.json
?? .ralph/receipts/1/20260119-111759-iter0021/runner.json
?? .ralph/receipts/10/
?? .ralph/receipts/2/20260119-112051-iter0027/
?? .ralph/receipts/2/20260119-112107-iter0022/
?? .ralph/receipts/2/20260119-112250-iter0022/
?? .ralph/receipts/3/20260119-113011-iter0028/
?? .ralph/receipts/3/20260119-113537-iter0023/
?? .ralph/receipts/3/20260119-113608-iter0023/
?? .ralph/receipts/4/20260119-113948-iter0029/
?? .ralph/receipts/4/20260119-114331-iter0024/
?? .ralph/receipts/5/
?? .ralph/receipts/6/
?? .ralph/receipts/7/
?? .ralph/receipts/8/
?? .ralph/receipts/9/
?? src/ralph_gold/templates/ralph_solo.toml
?? tests/test_cli_mode.py
?? tests/test_loop_mode_runtime.py
?? tests/test_scaffold_solo.py
```
- git diff --stat:
```
.ralph/PRD.md                       |  18 +-
 .ralph/progress.md                  |  65 +++
 .ralph/state.json                   | 766 +++++++++++++++++++++++++++++++++++-
 src/ralph_gold/bridge.py            |   7 +-
 src/ralph_gold/cli.py               |  80 +++-
 src/ralph_gold/completion.py        |  14 +-
 src/ralph_gold/config.py            |  25 ++
 src/ralph_gold/loop.py              |  54 ++-
 src/ralph_gold/scaffold.py          |   9 +-
 src/ralph_gold/templates/ralph.toml |  31 +-
 src/ralph_gold/tui.py               |   3 +-
 11 files changed, 1039 insertions(+), 33 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

