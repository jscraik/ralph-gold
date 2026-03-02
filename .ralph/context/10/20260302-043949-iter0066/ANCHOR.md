# Ralph Gold Anchor

Task: 10 - Add SmartGateConfig dataclass to config.py

Acceptance criteria:
- Add `SmartGateConfig` with `enabled: bool` and `skip_gates_for: List[str]`
- Add `smart: SmartGateConfig` to `GatesConfig`
- Parse `[gates.smart]` section in `load_config()`
- Test: `uv run pytest -q tests/test_config.py -k test_smart_gate_config` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/PRD.md
 M .ralph/progress.md
 M .ralph/ralph.toml
 M .ralph/state.json
?? .ralph/attempts/6/20260302-042100-iter0062.json
?? .ralph/attempts/7/20260302-042135-iter0063.json
?? .ralph/attempts/8/20260302-042642-iter0064.json
?? .ralph/attempts/9/20260302-043811-iter0065.json
?? .ralph/context/6/20260302-042100-iter0062/
?? .ralph/context/7/20260302-042135-iter0063/
?? .ralph/context/8/20260302-042642-iter0064/
?? .ralph/context/9/20260302-043811-iter0065/
?? .ralph/receipts/6/20260302-042100-iter0062/
?? .ralph/receipts/7/20260302-042135-iter0063/
?? .ralph/receipts/8/20260302-042642-iter0064/
?? .ralph/receipts/9/20260302-043811-iter0065/
?? docs/brainstorms/2026-03-01-adaptive-intervention-engine-brainstorm.md
?? docs/plans/2026-03-01-feat-adaptive-intervention-recommendation-engine-plan.md
?? ops/
```
- git diff --stat:
```
.ralph/PRD.md      |   8 +-
 .ralph/progress.md |   8 ++
 .ralph/ralph.toml  |   5 ++
 .ralph/state.json  | 260 ++++++++++++++++++++++++++++++++++++++++++++++++++++-
 4 files changed, 275 insertions(+), 6 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

