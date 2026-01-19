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
?? .ralph/attempts/
?? .ralph/context/
?? .ralph/receipts/
```
- git diff --stat:
```
.ralph/PRD.md      |   4 +-
 .ralph/progress.md |  18 ++++
 .ralph/state.json  | 244 ++++++++++++++++++++++++++++++++++++++++++++++++++++-
 3 files changed, 261 insertions(+), 5 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

