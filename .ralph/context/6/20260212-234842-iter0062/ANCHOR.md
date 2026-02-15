# Ralph Gold Anchor

Task: 6 - Add LoopModeOverride dataclass to config.py

Acceptance criteria:
- Add `LoopModeOverride` with fields for max_iterations, gates, etc.
- Add `resolve_mode_overrides()` function to merge mode into config
- Test: `uv run pytest -q tests/test_config_loop_modes.py -k test_resolve` passes

Repo reality:
- branch: codex/auto-checkpoint/20260212-145749
- git status --porcelain:
```
<clean>
```
- git diff --stat:
```
<no diff>
```

Constraints:
- Work on exactly ONE task per iteration
- Do not claim completion without passing gates
- Prefer minimal diffs; keep repo clean

