# Ralph Gold Anchor

Task: 3 - Add CLI support for `--mode` on `ralph run` and `ralph step`

Acceptance criteria:
- CLI accepts `--mode {speed,quality,exploration}` and passes it into config.
- Invalid mode names exit with a single clear error message.
- Shell completion includes `--mode` and enum values.
- `uv run pytest -q tests/test_cli_mode.py` passes.

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
?? .ralph/attempts/2/20260119-112250-iter0022.json
?? .ralph/context/2/20260119-112051-iter0027/
?? .ralph/context/2/20260119-112107-iter0022/
?? .ralph/context/2/20260119-112250-iter0022/
?? .ralph/context/3/20260119-113011-iter0028/
?? .ralph/receipts/1/20260119-111750-iter0026/runner.json
?? .ralph/receipts/1/20260119-111759-iter0021/runner.json
?? .ralph/receipts/2/20260119-112051-iter0027/
?? .ralph/receipts/2/20260119-112107-iter0022/
?? .ralph/receipts/2/20260119-112250-iter0022/
?? .ralph/receipts/3/20260119-113011-iter0028/
?? tests/test_loop_mode_runtime.py
```
- git diff --stat:
```
.ralph/PRD.md                |  2 +-
 .ralph/progress.md           | 10 ++++++
 .ralph/state.json            | 76 ++++++++++++++++++++++++++++++++++++++++----
 src/ralph_gold/bridge.py     |  7 ++--
 src/ralph_gold/cli.py        | 22 ++++++++++++-
 src/ralph_gold/completion.py | 11 +++++--
 src/ralph_gold/config.py     |  1 +
 src/ralph_gold/loop.py       | 54 +++++++++++++++++++++++++++++--
 src/ralph_gold/tui.py        |  3 +-
 9 files changed, 171 insertions(+), 15 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

