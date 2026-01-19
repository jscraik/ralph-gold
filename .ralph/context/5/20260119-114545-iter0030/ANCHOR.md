# Ralph Gold Anchor

Task: 5 - Add solo-dev defaults + `ralph init --solo`

Acceptance criteria:
- Update `src/ralph_gold/templates/ralph.toml` with solo defaults and mode blocks.
- `ralph init --solo` writes the solo template variant with `mode = "speed"`.
- Defaults include smart gate skip patterns for docs/config-only changes.
- `uv run pytest -q tests/test_scaffold_solo.py` passes.

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
?? .ralph/attempts/4/20260119-113948-iter0029.json
?? .ralph/attempts/4/20260119-114331-iter0024.json
?? .ralph/attempts/5/
?? .ralph/context/2/20260119-112051-iter0027/
?? .ralph/context/2/20260119-112107-iter0022/
?? .ralph/context/2/20260119-112250-iter0022/
?? .ralph/context/3/20260119-113011-iter0028/
?? .ralph/context/3/20260119-113537-iter0023/
?? .ralph/context/3/20260119-113608-iter0023/
?? .ralph/context/4/20260119-113948-iter0029/
?? .ralph/context/4/20260119-114331-iter0024/
?? .ralph/context/5/
?? .ralph/receipts/1/20260119-111750-iter0026/runner.json
?? .ralph/receipts/1/20260119-111759-iter0021/runner.json
?? .ralph/receipts/2/20260119-112051-iter0027/
?? .ralph/receipts/2/20260119-112107-iter0022/
?? .ralph/receipts/2/20260119-112250-iter0022/
?? .ralph/receipts/3/20260119-113011-iter0028/
?? .ralph/receipts/3/20260119-113537-iter0023/
?? .ralph/receipts/3/20260119-113608-iter0023/
?? .ralph/receipts/4/20260119-113948-iter0029/
?? .ralph/receipts/4/20260119-114331-iter0024/
?? .ralph/receipts/5/
?? tests/test_cli_mode.py
?? tests/test_loop_mode_runtime.py
```
- git diff --stat:
```
.ralph/PRD.md                |   6 +-
 .ralph/progress.md           |  26 +++
 .ralph/state.json            | 466 +++++++++++++++++++++++++++++++++++--------
 src/ralph_gold/bridge.py     |   7 +-
 src/ralph_gold/cli.py        |  68 ++++++-
 src/ralph_gold/completion.py |  11 +-
 src/ralph_gold/config.py     |  25 +++
 src/ralph_gold/loop.py       |  54 ++++-
 src/ralph_gold/tui.py        |   3 +-
 9 files changed, 569 insertions(+), 97 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

