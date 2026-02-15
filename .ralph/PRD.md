# PRD: Solo Dev Optimizations (Plan)

## Overview

Plan for solo-dev optimizations based on `.ralph/specs/solo-dev-optimizations.md` and
`.spec/PHASE1_QUICK_WINS.md`, aligned to current implementation gaps in `src/ralph_gold/`.

## Tasks

### Completed

- [x] Add loop mode config schema + parsing
  - Parse `loop.mode` and `loop.modes.*` into new config types (no breaking changes).
  - Provide safe defaults when modes are absent or incomplete.
  - Unknown mode names produce a clear config error.
  - `uv run pytest -q tests/test_config_loop_modes.py` passes.

- [x] Add CLI support for `--mode` on `ralph run` and `ralph step`
  - CLI accepts `--mode {speed,quality,exploration}` and passes it into config.
  - Invalid mode names exit with a single clear error message.
  - Shell completion includes `--mode` and enum values.
  - `uv run pytest -q tests/test_cli_mode.py` passes.

- [x] Add solo-dev defaults + `ralph init --solo`
  - Update `src/ralph_gold/templates/ralph.toml` with solo defaults and mode blocks.
  - `ralph init --solo` writes the solo template variant with `mode = "speed"`.
  - Defaults include smart gate skip patterns for docs/config-only changes.
  - `uv run pytest -q tests/test_scaffold_solo.py` passes.

- [x] Fix story_id=None infinite loop bug
  - Fixed `src/ralph_gold/prd.py` to not count blocked tasks as done
  - Fixed `src/ralph_gold/loop.py` to exit immediately when story_id is None
  - Exit with code 0 (success) when all tasks done, code 1 when all blocked
  - Test: `uv run pytest -q tests/test_loop_exit_conditions.py` passes

- [x] Improve PRD template with context and task breakdown guidance
  - Updated `src/ralph_gold/templates/PRD.md` with examples of good vs bad tasks
  - Added guidance: "Break tasks into 5-15 minute iterations with clear acceptance criteria"
  - Included example tasks showing proper granularity and specificity
  - Test: `uv run pytest -q tests/test_templates.py` passes

### Loop Mode Runtime (Task 2 - Broken Down)

- [-] Add LoopModeOverride dataclass to config.py
  - Add `LoopModeOverride` with fields for max_iterations, gates, etc.
  - Add `resolve_mode_overrides()` function to merge mode into config
  - Test: `uv run pytest -q tests/test_config_loop_modes.py -k test_resolve` passes

- [ ] Apply mode overrides in loop.py before execution
  - Call `resolve_mode_overrides()` at start of `run_loop()`
  - Pass resolved config to `run_iteration()`
  - Test: `uv run pytest -q tests/test_loop_mode_runtime.py -k test_apply` passes

- [ ] Record resolved mode in state.json
  - Add `resolved_mode` field to iteration state
  - Save mode name and overrides applied
  - Test: `uv run pytest -q tests/test_loop_mode_runtime.py -k test_record` passes

- [ ] Show resolved mode in dry-run output
  - Add mode info to dry_run_loop() result
  - Display in dry-run summary
  - Test: `uv run pytest -q tests/test_dry_run.py -k test_mode` passes

### Smart Gate Selection (Task 4 - Broken Down)

- [ ] Add SmartGateConfig dataclass to config.py
  - Add `SmartGateConfig` with `enabled: bool` and `skip_gates_for: List[str]`
  - Add `smart: SmartGateConfig` to `GatesConfig`
  - Parse `[gates.smart]` section in `load_config()`
  - Test: `uv run pytest -q tests/test_config.py -k test_smart_gate_config` passes

- [ ] Add get_changed_files() function to gates.py
  - Use `git diff --name-only HEAD` to get changed files
  - Return empty list on error (fail-open for safety)
  - Handle case when not in git repo gracefully
  - Test: `uv run pytest -q tests/test_gates_enhanced.py -k test_changed_files` passes

- [ ] Add should_skip_gates() function to gates.py
  - Use `fnmatch` to match files against patterns
  - Skip only if ALL changed files match skip patterns
  - Return False if no patterns or no changed files
  - Test: `uv run pytest -q tests/test_gates_enhanced.py -k test_skip_logic` passes

- [ ] Integrate smart gates into loop execution
  - Call smart gate check before running gates in `run_iteration()`
  - Log skip reason when gates are skipped
  - Record skip decision in iteration receipts
  - Test: `uv run pytest -q tests/test_gates_enhanced.py -k test_integration` passes

### Workflow Shortcut Flags (Task 6 - Broken Down)

- [ ] Add --quick flag to CLI
  - Add `--quick` flag to `ralph run` and `ralph step` commands
  - Map to `mode="speed"` with `max_iterations=1`
  - Mutually exclusive with `--mode` flag
  - Test: `uv run pytest -q tests/test_cli_mode.py -k test_quick` passes

- [ ] Add --batch flag to CLI
  - Add `--batch` flag for batch task execution
  - Map to `mode="speed"` with batch selection enabled
  - Mutually exclusive with other shortcut flags
  - Test: `uv run pytest -q tests/test_cli_mode.py -k test_batch` passes

- [ ] Add --explore flag to CLI
  - Add `--explore` flag for exploration mode
  - Map to `mode="exploration"` with extended timeouts
  - Mutually exclusive with other shortcut flags
  - Test: `uv run pytest -q tests/test_cli_mode.py -k test_explore` passes

- [ ] Add --hotfix and --task flags to CLI
  - Add `--hotfix` for urgent fixes (skip gates)
  - Add `--task ID` to work on specific task
  - Update shell completion with new flags
  - Test: `uv run pytest -q tests/test_cli_mode.py -k test_shortcuts` passes

### Quick Task Batching (Task 7 - Broken Down)

- [ ] Add [QUICK] tag detection to PRD parser
  - Detect `[QUICK]` prefix in task titles
  - Add `is_quick: bool` field to task objects
  - Parse and preserve quick flag
  - Test: `uv run pytest -q tests/test_converters.py -k test_quick_tag` passes

- [ ] Add get_quick_batch() function to tracker
  - Return up to 3 quick tasks that are ready
  - Respect dependencies and blocked tasks
  - Return None if no quick tasks available
  - Test: `uv run pytest -q tests/test_progress.py -k test_quick_batch` passes

- [ ] Execute quick batches in single iteration
  - Modify loop to handle batch execution
  - Keep separate receipts for each task in batch
  - Update progress for all tasks in batch
  - Test: `uv run pytest -q tests/test_loop_mode_runtime.py -k test_batch_exec` passes

### Flow & Momentum Tracking (Task 8 - Broken Down)

- [ ] Add velocity calculation to stats.py
  - Calculate tasks/hour from iteration history
  - Handle empty history gracefully
  - Return 0.0 for insufficient data
  - Test: `uv run pytest -q tests/test_stats.py -k test_velocity` passes

- [ ] Add blocked task rate calculation to stats.py
  - Calculate percentage of tasks that get blocked
  - Track blocked attempts per task
  - Return metrics in stats output
  - Test: `uv run pytest -q tests/test_stats.py -k test_blocked_rate` passes

- [ ] Add ralph stats --flow command
  - Add `--flow` flag to stats command
  - Display velocity and blocked rate
  - Support JSON output format
  - Test: `uv run pytest -q tests/test_cli_stats.py -k test_flow` passes

- [ ] Record flow metrics in state.json
  - Add `flow_metrics` field to state
  - Update after each iteration
  - Include velocity and momentum indicators
  - Test: `uv run pytest -q tests/test_stats.py -k test_flow_state` passes

### Context-Aware Prompts (Task 9 - Broken Down)

- [ ] Create PROMPT_docs.md template
  - Add template for documentation tasks
  - Emphasize clarity and examples
  - Include docs-specific acceptance criteria
  - Test: `uv run pytest -q tests/test_templates.py -k test_prompt_docs` passes

- [ ] Create PROMPT_hotfix.md template
  - Add template for urgent fixes
  - Emphasize minimal changes and testing
  - Skip non-critical quality checks
  - Test: `uv run pytest -q tests/test_templates.py -k test_prompt_hotfix` passes

- [ ] Create PROMPT_exploration.md template
  - Add template for exploration tasks
  - Emphasize learning and experimentation
  - Allow longer iterations
  - Test: `uv run pytest -q tests/test_templates.py -k test_prompt_explore` passes

- [ ] Add prompt selection logic to loop.py
  - Detect task type from title/tags
  - Select appropriate prompt template
  - Fall back to default PROMPT_build.md
  - Test: `uv run pytest -q tests/test_loop_mode_runtime.py -k test_prompt_select` passes

### Adaptive Rigor (Task 10 - Broken Down)

- [ ] Add AdaptiveConfig dataclass to config.py
  - Add `AdaptiveConfig` with `enabled: bool` and risk thresholds
  - Add `adaptive: AdaptiveConfig` to `LoopConfig`
  - Parse `[loop.adaptive]` section
  - Test: `uv run pytest -q tests/test_config.py -k test_adaptive` passes

- [ ] Add failure tracking to state.json
  - Track failures per file/area
  - Calculate risk score based on history
  - Store in `area_risk_scores` field
  - Test: `uv run pytest -q tests/test_stats.py -k test_risk_tracking` passes

- [ ] Add adaptive gate selection logic
  - Tighten gates for high-risk areas
  - Use standard gates for low-risk areas
  - Mixed changes follow strictest path
  - Test: `uv run pytest -q tests/test_gates_enhanced.py -k test_adaptive` passes

- [ ] Integrate adaptive rigor into loop
  - Calculate risk before each iteration
  - Adjust gate requirements accordingly
  - Log risk level and gate adjustments
  - Test: `uv run pytest -q tests/test_loop_mode_runtime.py -k test_adaptive` passes

### Plan Validation (Task 13 - Broken Down)

- [ ] Add task complexity detector to prd.py
  - Detect vague tasks (e.g., "Define structure", "Implement feature")
  - Count acceptance criteria lines
  - Flag tasks without test commands
  - Test: `uv run pytest -q tests/test_converters.py -k test_complexity` passes

- [ ] Add validate_prd() function
  - Check all tasks for complexity issues
  - Return list of warnings
  - Suggest breaking down complex tasks
  - Test: `uv run pytest -q tests/test_converters.py -k test_validate` passes

- [ ] Add validation to ralph regen-plan command
  - Run validation after plan generation
  - Display warnings to user
  - Continue unless --strict flag used
  - Test: `uv run pytest -q tests/test_cli_templates.py -k test_validate` passes

- [ ] Add --strict flag to ralph regen-plan
  - Fail if any validation warnings found
  - Exit with code 1 and clear error message
  - Show how to fix each issue
  - Test: `uv run pytest -q tests/test_cli_templates.py -k test_strict` passes

# Notes

# - Mark done:   - [x]

# - Mark blocked: - [-]

# - Dependencies (optional): add an acceptance bullet like

# - Depends on: 1, 2
