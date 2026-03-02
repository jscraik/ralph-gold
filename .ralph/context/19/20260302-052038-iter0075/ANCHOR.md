# Ralph Gold Anchor

Task: 19 - Add get_quick_batch() function to tracker

Acceptance criteria:
- Return up to 3 quick tasks that are ready
- Respect dependencies and blocked tasks
- Return None if no quick tasks available
- Test: `uv run pytest -q tests/test_progress.py -k test_quick_batch` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/PRD.md
 M .ralph/progress.md
 M .ralph/ralph.toml
 M .ralph/state.json
 M src/ralph_gold/cli.py
 M src/ralph_gold/completion.py
 M src/ralph_gold/config.py
 M src/ralph_gold/converters.py
 M src/ralph_gold/loop.py
 M src/ralph_gold/prd.py
 M src/ralph_gold/receipts.py
 M tests/test_cli_mode.py
 M tests/test_converters.py
 M tests/test_gates_enhanced.py
?? .ralph/attempts/10/20260302-043949-iter0066.json
?? .ralph/attempts/11/20260302-044408-iter0067.json
?? .ralph/attempts/12/20260302-044811-iter0068.json
?? .ralph/attempts/13/20260302-045136-iter0069.json
?? .ralph/attempts/14/
?? .ralph/attempts/15/
?? .ralph/attempts/16/
?? .ralph/attempts/17/
?? .ralph/attempts/18/
?? .ralph/attempts/6/20260302-042100-iter0062.json
?? .ralph/attempts/7/20260302-042135-iter0063.json
?? .ralph/attempts/8/20260302-042642-iter0064.json
?? .ralph/attempts/9/20260302-043811-iter0065.json
?? .ralph/context/10/20260302-043949-iter0066/
?? .ralph/context/11/20260302-044408-iter0067/
?? .ralph/context/12/20260302-044811-iter0068/
?? .ralph/context/13/20260302-045136-iter0069/
?? .ralph/context/14/
?? .ralph/context/15/
?? .ralph/context/16/
?? .ralph/context/17/
?? .ralph/context/18/
?? .ralph/context/6/20260302-042100-iter0062/
?? .ralph/context/7/20260302-042135-iter0063/
?? .ralph/context/8/20260302-042642-iter0064/
?? .ralph/context/9/20260302-043811-iter0065/
?? .ralph/receipts/10/20260302-043949-iter0066/
?? .ralph/receipts/11/20260302-044408-iter0067/
?? .ralph/receipts/12/20260302-044811-iter0068/
?? .ralph/receipts/13/20260302-045136-iter0069/
?? .ralph/receipts/14/
?? .ralph/receipts/15/
?? .ralph/receipts/16/
?? .ralph/receipts/17/
?? .ralph/receipts/18/
?? .ralph/receipts/6/20260302-042100-iter0062/
?? .ralph/receipts/7/20260302-042135-iter0063/
?? .ralph/receipts/8/20260302-042642-iter0064/
?? .ralph/receipts/9/20260302-043811-iter0065/
?? converters_head.py
?? docs/brainstorms/2026-03-01-adaptive-intervention-engine-brainstorm.md
?? docs/plans/2026-03-01-feat-adaptive-intervention-recommendation-engine-plan.md
?? ops/
?? prd_head.py
?? src/ralph_gold/gates.py
?? tests/test_config.py
```
- git diff --stat:
```
.ralph/PRD.md                |  26 +-
 .ralph/progress.md           | 207 +++---------
 .ralph/ralph.toml            |   5 +
 .ralph/state.json            | 779 ++++++++++++++++++++++++++++++++++++++++++-
 src/ralph_gold/cli.py        | 130 +++++++-
 src/ralph_gold/completion.py |  21 +-
 src/ralph_gold/config.py     |  14 +-
 src/ralph_gold/converters.py |   4 +
 src/ralph_gold/loop.py       | 157 ++++-----
 src/ralph_gold/prd.py        |  25 +-
 src/ralph_gold/receipts.py   |  24 +-
 tests/test_cli_mode.py       | 341 +++++++++++++++++++
 tests/test_converters.py     |  47 +++
 tests/test_gates_enhanced.py | 156 ++++++++-
 14 files changed, 1637 insertions(+), 299 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

