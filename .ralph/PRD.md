# PRD: Solo Dev Optimizations (Plan)

## Overview

Plan for solo-dev optimizations based on `.ralph/specs/solo-dev-optimizations.md` and
`.spec/PHASE1_QUICK_WINS.md`, aligned to current implementation gaps in `src/ralph_gold/`.

## Tasks

- [ ] Add loop mode config schema + parsing
  - Parse `loop.mode` and `loop.modes.*` into new config types (no breaking changes).
  - Provide safe defaults when modes are absent or incomplete.
  - Unknown mode names produce a clear config error.
  - `uv run pytest -q tests/test_config_loop_modes.py` passes.

- [ ] Apply loop mode overrides at runtime
  - Merge selected mode overrides into loop settings before execution.
  - Record the resolved mode in `state.json` history for each iteration.
  - Dry-run output includes the resolved mode.
  - `uv run pytest -q tests/test_loop_mode_runtime.py` passes.

- [ ] Add CLI support for `--mode` on `ralph run` and `ralph step`
  - CLI accepts `--mode {speed,quality,exploration}` and passes it into config.
  - Invalid mode names exit with a single clear error message.
  - Shell completion includes `--mode` and enum values.
  - `uv run pytest -q tests/test_cli_mode.py` passes.

- [ ] Implement smart gate selection (config + runtime)
  - Add `gates.smart.enabled` and `gates.smart.skip_gates_for` in config parsing.
  - Use `git diff --name-only HEAD` to compute changed files (graceful fallback if missing).
  - Skip gates when all changed files match `skip_gates_for` patterns.
  - `uv run pytest -q tests/test_smart_gates.py` passes.

- [ ] Add solo-dev defaults + `ralph init --solo`
  - Update `src/ralph_gold/templates/ralph.toml` with solo defaults and mode blocks.
  - `ralph init --solo` writes the solo template variant with `mode = "speed"`.
  - Defaults include smart gate skip patterns for docs/config-only changes.
  - `uv run pytest -q tests/test_scaffold_solo.py` passes.

- [ ] Implement workflow shortcut flags (`--quick`, `--batch`, `--explore`, `--hotfix`, `--task`)
  - Shortcut flags map to mode/prompt behavior with no hidden side effects.
  - Shortcuts are mutually exclusive with `--mode` (clear error).
  - Completion script includes new flags and descriptions.
  - `uv run pytest -q tests/test_cli_shortcuts.py` passes.

- [ ] Enable quick task batching for `[QUICK]` tasks
  - PRD parsing identifies `[QUICK]` tasks and returns batches (max 3).
  - Batch selection respects `Depends on:` and blocked tasks.
  - Loop executes a batch in one iteration while keeping receipts consistent.
  - `uv run pytest -q tests/test_quick_batching.py` passes.

- [ ] Add flow + momentum tracking (velocity + blocked handling)
  - Extend stats to calculate tasks/hour and blocked-task rate.
  - Add `ralph stats --flow` output (text + JSON) and handle empty history.
  - Record flow/momentum data in `state.json` for later use.
  - `uv run pytest -q tests/test_stats_flow.py` passes.

- [ ] Add context-aware prompts (docs/hotfix/exploration)
  - Add prompt templates under `src/ralph_gold/templates/` for each context.
  - Detect task type from title/tags and select the correct prompt.
  - Docs tasks can optionally skip gates when configured.
  - `uv run pytest -q tests/test_prompt_selection.py` passes.

- [ ] Implement adaptive rigor based on history
  - Add `loop.adaptive` config with deterministic risk heuristics.
  - Track per-area failures and tighten gate requirements for risky areas.
  - Mixed-change iterations follow the strictest path.
  - `uv run pytest -q tests/test_adaptive_rigor.py` passes.
