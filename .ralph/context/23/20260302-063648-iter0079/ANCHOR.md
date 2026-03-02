# Ralph Gold Anchor

Task: 23 - Add ralph stats --flow command

Acceptance criteria:
- Add `--flow` flag to stats command
- Display velocity and blocked rate
- Support JSON output format
- Test: `uv run pytest -q tests/test_cli_stats.py -k test_flow` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/state.json
?? .ralph/attempts/22/
```
- git diff --stat:
```
.ralph/state.json | 116 +++++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 115 insertions(+), 1 deletion(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

