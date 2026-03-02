# Ralph Gold Anchor

Task: 25 - Create PROMPT_docs.md template

Acceptance criteria:
- Add template for documentation tasks
- Emphasize clarity and examples
- Include docs-specific acceptance criteria
- Test: `uv run pytest -q tests/test_templates.py -k test_prompt_docs` passes

Repo reality:
- branch: main
- git status --porcelain:
```
M .ralph/state.json
?? .ralph/attempts/23/
```
- git diff --stat:
```
.ralph/state.json | 173 +++++++++++++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 172 insertions(+), 1 deletion(-)
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

