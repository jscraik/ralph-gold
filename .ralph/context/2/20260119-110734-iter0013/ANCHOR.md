# Ralph Gold Anchor

Task: 2 - Implement the first thin vertical slice

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/PRD.md
 M .ralph/progress.md
 M .ralph/state.json
?? .ralph/attempts/1/20260119-110658-iter0012.json
?? .ralph/context/1/20260119-110453-iter0012/
?? .ralph/context/1/20260119-110658-iter0012/
?? .ralph/receipts/1/20260119-110453-iter0012/
?? .ralph/receipts/1/20260119-110658-iter0012/
```
- git diff --stat:
```
.ralph/PRD.md      |  2 +-
 .ralph/progress.md |  3 +++
 .ralph/state.json  | 44 ++++++++++++++++++++++++++++++++++++++------
 3 files changed, 42 insertions(+), 7 deletions(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

