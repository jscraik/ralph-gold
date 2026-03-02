# Ralph Gold Anchor

Task: 29 - Add AdaptiveConfig dataclass to config.py

Acceptance criteria:
- Add `AdaptiveConfig` with `enabled: bool` and risk thresholds
- Add `adaptive: AdaptiveConfig` to `LoopConfig`
- Parse `[loop.adaptive]` section
- Test: `uv run pytest -q tests/test_config.py -k test_adaptive` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/state.json
?? .ralph/attempts/28/
```
- git diff --stat:
```
.ralph/state.json | 409 +++++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 407 insertions(+), 2 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

