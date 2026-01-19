# Phase 1: Solo Dev Quick Wins

## Overview

Implement the highest-impact, lowest-effort improvements to Ralph for solo developers. Focus on speed and flow state preservation.

## Acceptance Criteria

### 1. Execution Modes

- [ ] Add `[loop.modes.speed]`, `[loop.modes.quality]`, `[loop.modes.exploration]` config sections
- [ ] Add `mode = "speed"` setting to `[loop]` section
- [ ] Mode settings override base loop settings at runtime
- [ ] `ralph run --mode speed` works
- [ ] Tests pass: `uv run pytest tests/test_config_phase2.py -k mode`

### 2. Smart Gate Selection

- [ ] Add `[gates.smart]` config section with `enabled`, `skip_gates_for` patterns
- [ ] Gates skip when only matching files changed (e.g., `**/*.md`)
- [ ] Use `git diff --name-only HEAD` to detect changed files
- [ ] Tests pass: `uv run pytest tests/ -k smart_gate`

### 3. Solo Dev Defaults

- [ ] Update `src/ralph_gold/templates/ralph.toml` with solo-optimized defaults
- [ ] Add `ralph init --solo` flag to scaffold with speed mode enabled
- [ ] Default `mode = "speed"`, `max_iterations = 20`, `runner_timeout_seconds = 120`
- [ ] Tests pass: `uv run pytest tests/test_scaffold*.py`

## Implementation Tasks

Each task should take 5-15 minutes and result in one commit.

### Task 1: Add Loop Mode Config Schema

- Add `LoopModeConfig` dataclass to `src/ralph_gold/config.py`
- Add `modes: Dict[str, LoopModeConfig]` to `LoopConfig`
- Add `mode: str` field to `LoopConfig`
- Parse `[loop.modes.*]` sections in `load_config()`
- Tests: Add `test_loop_modes_config()` to `tests/test_config_phase2.py`

### Task 2: Apply Mode Overrides at Runtime

- In `src/ralph_gold/loop.py`, apply mode overrides before loop execution
- If `cfg.loop.mode` is set, merge `cfg.loop.modes[mode]` into `cfg.loop`
- Tests: Add `test_mode_override_application()` to `tests/test_loop_progress.py`

### Task 3: Add CLI --mode Flag

- Add `--mode` argument to `ralph run` command in `src/ralph_gold/cli.py`
- Pass mode to loop execution
- Tests: Add `test_cli_mode_flag()` to `tests/test_cli_interactive.py`

### Task 4: Add Smart Gate Config

- Add `SmartGateConfig` dataclass to `src/ralph_gold/config.py`
- Add `smart: SmartGateConfig` to `GatesConfig`
- Parse `[gates.smart]` section with `enabled`, `skip_gates_for` patterns
- Tests: Add `test_smart_gate_config()` to `tests/test_config_phase2.py`

### Task 5: Implement Smart Gate Filtering

- In `src/ralph_gold/loop.py`, detect changed files via `git diff --name-only HEAD`
- Match changed files against `skip_gates_for` patterns using `fnmatch`
- Skip gates if all changed files match skip patterns
- Tests: Add `test_smart_gate_filtering()` to `tests/test_gates_enhanced.py`

### Task 6: Update Default Config Template

- Update `src/ralph_gold/templates/ralph.toml` with solo dev defaults
- Add `mode = "speed"` to `[loop]`
- Add `[loop.modes.speed]`, `[loop.modes.quality]`, `[loop.modes.exploration]` sections
- Add `[gates.smart]` section with common skip patterns
- Tests: Verify via `test_scaffold_archive.py`

### Task 7: Add --solo Flag to ralph init

- Add `--solo` flag to `cmd_init()` in `src/ralph_gold/cli.py`
- When `--solo` is set, use solo-optimized template values
- Tests: Add `test_init_solo_flag()` to `tests/test_scaffold_archive.py`

## Non-Goals

- Flow state tracking (Phase 2)
- Task batching (Phase 2)
- Context-aware prompts (Phase 2)
- Adaptive rigor (Phase 3)

## Success Metrics

- All 7 tasks completed in 2-3 hours
- All tests pass: `uv run pytest -q`
- `ralph init --solo` creates optimized config
- `ralph run --mode speed` skips gates for doc changes
