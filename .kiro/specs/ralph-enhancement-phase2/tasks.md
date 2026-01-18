# Ralph Gold Phase 2 Enhancements - Implementation Tasks

**Feature:** ralph-enhancement-phase2  
**Status:** Ready for Implementation  
**Total Tasks:** 48 (12 features × 4 phases)

## Task Organization

Tasks are organized by implementation phase (2A-2D) as defined in the design document. Each feature has 4 standard tasks:

1. Core implementation
2. Unit tests
3. Property-based tests
4. CLI integration & documentation

---

## Phase 2A: High Priority Features

### Feature 1: Diagnostics Module

- [x] 1.1 Implement diagnostics core module
  - Create `src/ralph_gold/diagnostics.py`
  - Implement `DiagnosticResult` dataclass
  - Implement `validate_config()` function
  - Implement `validate_prd()` function
  - Implement `test_gates()` function
  - Implement `run_diagnostics()` function with exit code logic

- [x] 1.2 Write unit tests for diagnostics
  - Create `tests/test_diagnostics.py`
  - Test config validation with valid/invalid TOML
  - Test PRD validation for JSON/Markdown/YAML formats
  - Test gate command execution
  - Test suggestion generation
  - Test exit code mapping

- [x] 1.3 Write property-based tests for diagnostics
  - Property 1: Configuration validation correctness
  - Property 2: Diagnostic exit code mapping
  - Property 3: Gate command execution fidelity
  - Property 4: Suggestion completeness
  - Use `hypothesis` with 100+ examples per property

- [x] 1.4 Integrate diagnostics CLI command
  - Add `cmd_diagnose()` to `cli.py`
  - Add `--test-gates` flag
  - Add output formatting
  - Update README with `ralph diagnose` usage
  - Add help text and examples

### Feature 2: Stats & Tracking

- [x] 2.1 Implement stats core module
  - Create `src/ralph_gold/stats.py`
  - Implement `IterationStats` and `TaskStats` dataclasses
  - Implement `calculate_stats()` function
  - Implement `export_stats_csv()` function
  - Implement `format_stats_report()` function
  - Extend `loop.py` to track `duration_seconds` in history

- [x] 2.2 Write unit tests for stats
  - Create `tests/test_stats.py`
  - Test stats calculation with various history data
  - Test CSV export and parsing
  - Test report formatting
  - Test edge cases (empty history, single iteration)
  - Test stats caching logic

- [x] 2.3 Write property-based tests for stats
  - Property 5: Statistical calculation correctness
  - Property 6: Duration tracking persistence
  - Property 7: CSV export round-trip
  - Use `hypothesis` with numeric strategies

- [x] 2.4 Integrate stats CLI command
  - Add `cmd_stats()` to `cli.py`
  - Add `--by-task` flag
  - Add `--export <file>` flag
  - Update README with `ralph stats` usage
  - Add help text and examples

### Feature 3: Dry-Run Mode

- [x] 3.1 Implement dry-run functionality
  - Modify `loop.py` to accept `dry_run` parameter
  - Implement `dry_run_loop()` function
  - Implement `DryRunResult` dataclass
  - Skip agent execution when dry_run=True
  - Validate configuration and show execution plan

- [x] 3.2 Write unit tests for dry-run
  - Create `tests/test_dry_run.py`
  - Test that no agents are executed
  - Test that no files are modified
  - Test configuration validation
  - Test execution plan generation
  - Test duration estimation

- [x] 3.3 Write property-based tests for dry-run
  - Property 8: Dry-run safety
  - Property 9: Dry-run prediction accuracy
  - Use process monitoring to verify no agent spawns

- [x] 3.4 Integrate dry-run CLI flag
  - Add `--dry-run` flag to `ralph run` command
  - Add `--dry-run` flag to `ralph step` command
  - Update output formatting for dry-run mode
  - Update README with dry-run usage
  - Add help text and examples

---

## Phase 2B: Medium Priority Features

### Feature 4: Interactive Task Selection

- [x] 4.1 Implement interactive selection module
  - Create `src/ralph_gold/interactive.py`
  - Implement `TaskChoice` dataclass
  - Implement `select_task_interactive()` function
  - Implement `format_task_list()` function
  - Add search/filter functionality

- [x] 4.2 Write unit tests for interactive selection
  - Create `tests/test_interactive.py`
  - Test task list formatting
  - Test blocked task filtering
  - Test search functionality
  - Test single task fallback
  - Test user input handling

- [x] 4.3 Write property-based tests for interactive selection
  - Property 10: Task filtering correctness
  - Property 11: Search filter accuracy
  - Use `hypothesis` with list and string strategies

- [x] 4.4 Integrate interactive CLI flag
  - Add `--interactive` flag to `ralph step` command
  - Modify `loop.py` to call interactive selector
  - Update README with interactive mode usage
  - Add help text and examples

### Feature 5: Task Dependencies

- [x] 5.1 Implement dependencies core module
  - Create `src/ralph_gold/dependencies.py`
  - Implement `DependencyGraph` and `TaskNode` dataclasses
  - Implement `build_dependency_graph()` function
  - Implement `detect_circular_dependencies()` function (DFS)
  - Implement `get_ready_tasks()` function
  - Implement `format_dependency_graph()` function (ASCII art)

- [x] 5.2 Extend trackers for dependency support
  - Modify `trackers.py` to parse `depends_on` field
  - Update JSON tracker schema
  - Update Markdown tracker parsing
  - Update YAML tracker parsing
  - Ensure backward compatibility (no depends_on = no deps)

- [x] 5.3 Write unit tests for dependencies
  - Create `tests/test_dependencies.py`
  - Test graph building
  - Test circular dependency detection
  - Test ready task calculation
  - Test topological sort
  - Test all tracker formats

- [x] 5.4 Write property-based tests for dependencies
  - Property 12: Dependency satisfaction
  - Property 13: Circular dependency detection
  - Property 14: Dependency format consistency
  - Property 15: Backward compatibility
  - Use `hypothesis` with graph generation strategies

- [x] 5.5 Integrate dependencies into loop and CLI
  - Modify `loop.py` task selection to respect dependencies
  - Add `ralph status --graph` command to visualize
  - Add circular dependency check to diagnostics
  - Update README with dependency usage
  - Add help text and examples

### Feature 6: Quiet Mode

- [x] 6.1 Implement output control module
  - Create output configuration system
  - Implement `OutputConfig` dataclass
  - Implement `get_output_config()` function
  - Implement `print_output()` function with level checking
  - Implement `format_json_output()` function

- [x] 6.2 Update all output statements
  - Modify `loop.py` to respect verbosity
  - Modify all CLI commands to check verbosity
  - Ensure errors always print
  - Add JSON formatters for all commands

- [x] 6.3 Write unit tests for quiet mode
  - Create `tests/test_output.py`
  - Test quiet mode suppression
  - Test verbose mode output
  - Test JSON output validity
  - Test error preservation

- [x] 6.4 Write property-based tests for quiet mode
  - Property 31: Quiet mode output suppression
  - Property 32: JSON output validity
  - Property 33: Error preservation
  - Use `hypothesis` with output capture

- [x] 6.5 Integrate quiet mode CLI flags
  - Add `--quiet` global flag
  - Add `--verbose` global flag
  - Add `--format json` global flag
  - Update README with output control usage
  - Add help text and examples

---

## Phase 2C: Advanced Features

### Feature 7: Snapshot & Rollback

- [ ] 7.1 Implement snapshots core module
  - Create `src/ralph_gold/snapshots.py`
  - Implement `Snapshot` dataclass
  - Implement `create_snapshot()` function (git stash)
  - Implement `list_snapshots()` function
  - Implement `rollback_snapshot()` function
  - Implement `cleanup_old_snapshots()` function

- [ ] 7.2 Extend state.json schema
  - Add `snapshots` array to state schema
  - Implement state backup/restore logic
  - Add snapshot metadata tracking

- [ ] 7.3 Write unit tests for snapshots
  - Create `tests/test_snapshots.py`
  - Test snapshot creation with git
  - Test snapshot listing
  - Test rollback functionality
  - Test dirty tree protection
  - Test cleanup logic

- [ ] 7.4 Write property-based tests for snapshots
  - Property 16: Snapshot round-trip
  - Property 17: Dirty tree protection
  - Property 18: Snapshot retention
  - Use `hypothesis` with git repository fixtures

- [ ] 7.5 Integrate snapshots CLI commands
  - Add `ralph snapshot <name>` command
  - Add `ralph snapshot --list` command
  - Add `ralph rollback <name>` command
  - Update README with snapshot usage
  - Add help text and examples

### Feature 8: Watch Mode

- [ ] 8.1 Implement watch core module
  - Create `src/ralph_gold/watch.py`
  - Implement `WatchConfig` dataclass
  - Implement `watch_files()` function
  - Implement `run_watch_mode()` function
  - Add debouncing logic (500ms default)
  - Add graceful shutdown (Ctrl+C)

- [ ] 8.2 Write unit tests for watch mode
  - Create `tests/test_watch.py`
  - Test file watching
  - Test pattern matching
  - Test debouncing
  - Test gate execution on change
  - Test auto-commit functionality

- [ ] 8.3 Write property-based tests for watch mode
  - Property 19: Watch debouncing
  - Property 20: Watch pattern matching
  - Use `hypothesis` with file change simulation

- [ ] 8.4 Integrate watch CLI command
  - Add `ralph watch` command
  - Add `--gates-only` flag
  - Add `--auto-commit` flag
  - Extend `ralph.toml` with watch configuration
  - Update README with watch mode usage
  - Add help text and examples

### Feature 9: Progress Visualization

- [ ] 9.1 Implement progress core module
  - Create `src/ralph_gold/progress.py`
  - Implement `ProgressMetrics` dataclass
  - Implement `calculate_progress()` function
  - Implement `format_progress_bar()` function
  - Implement `format_burndown_chart()` function (ASCII)
  - Implement `calculate_velocity()` function

- [ ] 9.2 Write unit tests for progress
  - Create `tests/test_progress.py`
  - Test progress calculation
  - Test progress bar rendering
  - Test burndown chart rendering
  - Test velocity calculation
  - Test ETA calculation

- [ ] 9.3 Write property-based tests for progress
  - Property 21: Progress bar accuracy
  - Property 22: Velocity calculation
  - Property 23: ETA calculation
  - Use `hypothesis` with numeric strategies

- [ ] 9.4 Integrate progress into status command
  - Extend `ralph status` with `--detailed` flag
  - Add `--chart` flag for burndown chart
  - Update README with progress visualization usage
  - Add help text and examples

---

## Phase 2D: Polish Features

### Feature 10: Environment Variable Expansion

- [x] 10.1 Implement envvars core module
  - Create `src/ralph_gold/envvars.py`
  - Implement `expand_env_vars()` function
  - Implement `validate_required_vars()` function
  - Implement `expand_config()` function
  - Add security validation (no shell execution)

- [x] 10.2 Integrate into config loading
  - Modify `config.load_config()` to expand variables
  - Add validation to diagnostics
  - Handle missing variables gracefully

- [x] 10.3 Write unit tests for envvars
  - Create `tests/test_envvars.py`
  - Test variable expansion
  - Test default values
  - Test missing variable errors
  - Test security (no shell injection)
  - Test nested expansion

- [x] 10.4 Write property-based tests for envvars
  - Property 24: Environment variable expansion
  - Property 25: Default value substitution
  - Property 26: Required variable validation
  - Property 27: Shell injection prevention
  - Use `hypothesis` with string strategies

- [x] 10.5 Document envvars feature
  - Update README with environment variable usage
  - Add examples to documentation
  - Add security notes

### Feature 11: Task Templates

- [ ] 11.1 Implement templates core module
  - Create `src/ralph_gold/templates.py`
  - Implement `TaskTemplate` dataclass
  - Implement `load_builtin_templates()` function
  - Implement `load_custom_templates()` function
  - Implement `create_task_from_template()` function
  - Implement `list_templates()` function

- [ ] 11.2 Create built-in templates
  - Create bug-fix template
  - Create feature template
  - Create refactor template
  - Store in module or data directory

- [ ] 11.3 Write unit tests for templates
  - Create `tests/test_templates.py`
  - Test template loading
  - Test variable substitution
  - Test task creation for all tracker types
  - Test custom template loading
  - Test template validation

- [ ] 11.4 Write property-based tests for templates
  - Property 28: Template variable substitution
  - Property 29: Template format validation
  - Property 30: Tracker format compatibility
  - Use `hypothesis` with template generation

- [ ] 11.5 Integrate templates CLI commands
  - Add `ralph task add --template <name>` command
  - Add `ralph task templates` command
  - Update README with template usage
  - Add help text and examples

### Feature 12: Shell Completion

- [ ] 12.1 Implement completion core module
  - Create `src/ralph_gold/completion.py`
  - Implement `generate_bash_completion()` function
  - Implement `generate_zsh_completion()` function
  - Implement `get_dynamic_completions()` function
  - Generate from argparse definitions

- [ ] 12.2 Write unit tests for completion
  - Create `tests/test_completion.py`
  - Test bash script generation
  - Test zsh script generation
  - Test dynamic completion values
  - Test script syntax validity

- [ ] 12.3 Write property-based tests for completion
  - Property 34: Completion script validity
  - Property 35: Dynamic completion accuracy
  - Use `hypothesis` with command generation

- [ ] 12.4 Integrate completion CLI command
  - Add `ralph completion bash` command
  - Add `ralph completion zsh` command
  - Include installation instructions in output
  - Update README with completion setup
  - Add help text and examples

---

## Integration & Polish Tasks

- [ ] 13.1 Update configuration schema
  - Extend `ralph.toml` with all new sections
  - Add configuration validation
  - Document all new config options
  - Provide sensible defaults

- [ ] 13.2 Implement state migration
  - Add `migrate_state_schema()` function
  - Handle old state.json files gracefully
  - Test migration with various state versions

- [ ] 13.3 Update documentation
  - Update main README with all new features
  - Create feature-specific documentation
  - Add usage examples for each feature
  - Update CLI help text

- [ ] 13.4 Integration testing
  - Create `tests/test_integration.py`
  - Test full workflow with all features
  - Test feature interactions
  - Test backward compatibility
  - Test migration paths

- [ ] 13.5 Performance testing
  - Profile stats calculation
  - Profile dependency graph operations
  - Profile watch mode file monitoring
  - Optimize hot paths if needed

- [ ] 13.6 Final polish
  - Run full test suite
  - Verify >95% coverage
  - Fix any remaining issues
  - Update CHANGELOG
  - Prepare release notes

---

## Testing Summary

**Total Property-Based Tests:** 35 properties across all features  
**Testing Framework:** pytest + hypothesis  
**Coverage Target:** >95% for all new code  
**Test Command:** `uv run pytest -q`

**Property Test Requirements:**

- Minimum 100 examples per property
- All tests annotated with `**Validates: Requirements X.Y**`
- Use appropriate hypothesis strategies
- Handle edge cases and invalid inputs

**Unit Test Requirements:**

- Test all public functions
- Test error conditions
- Test edge cases
- Test integration points
- Mock external dependencies appropriately

---

## Implementation Notes

**Development Order:**

1. Phase 2A first (diagnostics, stats, dry-run) - foundation
2. Phase 2B next (interactive, dependencies, quiet) - workflow
3. Phase 2C then (snapshots, watch, progress) - advanced
4. Phase 2D last (envvars, templates, completion) - polish

**Dependencies Between Features:**

- Diagnostics should be implemented first (used by other features)
- Stats tracking requires loop.py modifications
- Dependencies require tracker modifications
- Quiet mode affects all output

**Testing Strategy:**

- Write tests alongside implementation
- Run tests frequently during development
- Use TDD where appropriate
- Property tests help catch edge cases

**Code Review Checklist:**

- [ ] All acceptance criteria met
- [ ] Tests passing (>95% coverage)
- [ ] Documentation updated
- [ ] No breaking changes
- [ ] Type hints throughout
- [ ] Error handling comprehensive
- [ ] Performance acceptable

---

**Document Version:** 1.0  
**Status:** Ready for Implementation  
**Estimated Total Effort:** 18-26 hours
