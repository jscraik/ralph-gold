# Ralph Gold Anchor

Task: 18 - Add [QUICK] tag detection to PRD parser

Acceptance criteria:
- Detect `[QUICK]` prefix in task titles
- Add `is_quick: bool` field to task objects
- Parse and preserve quick flag
- Test: `uv run pytest -q tests/test_converters.py -k test_quick_tag` passes

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
 M src/ralph_gold/loop.py
 M src/ralph_gold/receipts.py
 M tests/test_cli_mode.py
 M tests/test_gates_enhanced.py
?? .ralph/attempts/10/20260302-043949-iter0066.json
?? .ralph/attempts/11/20260302-044408-iter0067.json
?? .ralph/attempts/12/20260302-044811-iter0068.json
?? .ralph/attempts/13/20260302-045136-iter0069.json
?? .ralph/attempts/14/
?? .ralph/attempts/15/
?? .ralph/attempts/16/
?? .ralph/attempts/17/
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
?? .ralph/receipts/6/20260302-042100-iter0062/
?? .ralph/receipts/7/20260302-042135-iter0063/
?? .ralph/receipts/8/20260302-042642-iter0064/
?? .ralph/receipts/9/20260302-043811-iter0065/
?? docs/brainstorms/2026-03-01-adaptive-intervention-engine-brainstorm.md
?? docs/plans/2026-03-01-feat-adaptive-intervention-recommendation-engine-plan.md
?? ops/
?? src/ralph_gold/gates.py
?? tests/test_config.py
```
- git diff --stat:
```
.ralph/PRD.md                |  24 +-
 .ralph/progress.md           | 204 +++---------
 .ralph/ralph.toml            |   5 +
 .ralph/state.json            | 720 ++++++++++++++++++++++++++++++++++++++++++-
 src/ralph_gold/cli.py        | 130 +++++++-
 src/ralph_gold/completion.py |  21 +-
 src/ralph_gold/config.py     |  14 +-
 src/ralph_gold/loop.py       | 157 +++++-----
 src/ralph_gold/receipts.py   |  24 +-
 tests/test_cli_mode.py       | 341 ++++++++++++++++++++
 tests/test_gates_enhanced.py | 156 +++++++++-
 11 files changed, 1504 insertions(+), 292 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

