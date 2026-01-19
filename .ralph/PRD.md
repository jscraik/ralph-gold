# PRD: Solo Dev Optimizations

## Overview
Implement solo-developer optimizations defined in `.spec/SOLO_DEV_OPTIMIZATIONS.md`
with the phased implementation plan in `.spec/SOLO_DEV_IMPLEMENTATION_PLAN.md`.
Scope covers loop modes, smart gates, batching, solo defaults, flow/momentum
tracking, context-aware prompts, workflow shortcuts, and adaptive rigor.

## Tasks

- [ ] Add loop mode configuration parsing (speed/quality/exploration)
  - Parse `loop.mode` and `loop.modes.*` in `src/ralph_gold/config.py`.
  - Provide defaults when mode blocks are missing.
  - Add unit tests covering default + explicit mode settings.
  - `uv run pytest -q tests/test_loop_modes_config.py` passes.

- [ ] Apply loop mode overrides at runtime
  - Add a mode-resolution helper that merges base loop config with the selected mode.
  - Ensure mode selection is logged in iteration state history.
  - Add unit tests for mode override behavior.
  - `uv run pytest -q tests/test_loop_modes_runtime.py` passes.

- [ ] Add CLI support for `--mode` on `ralph run` and `ralph step`
  - CLI accepts `--mode {speed,quality,exploration}` and passes it into the loop.
  - Errors on unknown modes with a clear message.
  - Update shell completion for the new flag.
  - `uv run pytest -q tests/test_cli_mode.py` passes.

- [ ] Implement workflow shortcut flags (`--quick`, `--explore`, `--hotfix`)
  - Map shortcut flags to defined modes and/or prompt selection rules.
  - Ensure shortcuts are mutually exclusive with `--mode` (clear error).
  - Update completion hints for new flags.
  - `uv run pytest -q tests/test_cli_shortcuts.py` passes.

- [ ] Add smart gate selection with file-pattern rules
  - Add `gates.smart` config parsing (run_tests_if/run_lint_if/skip_gates_for).
  - Implement changed-file detection and pattern matching (no new deps).
  - Gates skip when only docs/config change; run when code changes.
  - `uv run pytest -q tests/test_smart_gates.py` passes.

- [ ] Enable quick task batching for `[QUICK]` tasks
  - Extend PRD parsing to identify `[QUICK]` tasks and return batches (max 3).
  - Ensure batching respects `Depends on:` and blocked tasks.
  - Update loop execution to handle a batch while keeping one iteration.
  - `uv run pytest -q tests/test_quick_batching.py` passes.

- [ ] Add solo-dev defaults and `ralph init --solo`
  - Update `src/ralph_gold/templates/ralph.toml` with solo defaults and mode blocks.
  - Add `--solo` flag in scaffold/init to write the solo defaults template.
  - Document default mode behavior in template comments.
  - `uv run pytest -q tests/test_scaffold_solo.py` passes.

- [ ] Add flow state metrics to stats
  - Extend `src/ralph_gold/stats.py` with tasks/hour and flow-state detection.
  - Add `ralph stats --flow` output (text + JSON) in CLI.
  - Handle empty history gracefully.
  - `uv run pytest -q tests/test_stats_flow.py` passes.

- [ ] Implement momentum preservation (auto-skip blocked + alternative suggestions)
  - Add `loop.momentum` config parsing with skip thresholds.
  - Auto-skip tasks blocked beyond threshold and record in state/progress.
  - Suggest an alternative task when skipping.
  - `uv run pytest -q tests/test_momentum_skip.py` passes.

- [ ] Add context-aware prompts (docs/hotfix/exploration)
  - Add prompt templates under `src/ralph_gold/templates/`.
  - Detect task type from title/tags and select prompt accordingly.
  - Ensure docs tasks can skip tests when configured.
  - `uv run pytest -q tests/test_prompt_selection.py` passes.

- [ ] Add `ralph stats --blockers`, `--eta`, `--patterns`
  - Extend stats calculations for blockers and ETA estimates.
  - Add CLI output (text + JSON) for each flag.
  - Ensure output is stable for empty history.
  - `uv run pytest -q tests/test_stats_extended.py` passes.

- [ ] Implement adaptive rigor and learning from history
  - Add `loop.adaptive` config parsing and risk heuristics.
  - Track per-area failures in state and tighten gates for risky areas.
  - Ensure adaptive logic is deterministic and testable.
  - `uv run pytest -q tests/test_adaptive_rigor.py` passes.

