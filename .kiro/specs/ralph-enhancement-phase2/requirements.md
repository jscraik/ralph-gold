# Ralph Gold - Phase 2 Enhancements

**Feature Name:** ralph-enhancement-phase2  
**Status:** Planning  
**Priority:** High  
**Estimated Effort:** Large (12 features)

## Overview

Implement remaining enhancement features for Ralph Gold to improve usability, reliability, and developer experience. This builds on Phase 1 (archiving, resume, clean) to deliver a comprehensive set of productivity tools.

## User Stories

### Epic 1: Diagnostics & Validation

#### US-1.1: As a Ralph user, I want to diagnose configuration issues so I can fix problems quickly

- Given I have a Ralph project with potential config issues
- When I run `ralph diagnose`
- Then I see a report of all configuration problems with suggested fixes

#### US-1.2: As a Ralph user, I want to validate my PRD file format so I know it's correct

- Given I have a prd.json or PRD.md file
- When I run `ralph diagnose`
- Then I see validation errors with line numbers and fix suggestions

#### US-1.3: As a Ralph user, I want to test my gate commands individually so I can debug failures

- Given I have gate commands configured
- When I run `ralph diagnose --test-gates`
- Then each gate command is tested and results are shown

### Epic 2: Stats & Tracking

#### US-2.1: As a Ralph user, I want to see iteration statistics so I understand loop performance

- Given I have run multiple iterations
- When I run `ralph stats`
- Then I see total iterations, average duration, success rate, and cost estimates

#### US-2.2: As a Ralph user, I want to identify slow tasks so I can optimize my workflow

- Given I have iteration history
- When I run `ralph stats --by-task`
- Then I see which tasks take longest and have most failures

#### US-2.3: As a Ralph user, I want to export stats to CSV so I can analyze trends

- Given I have iteration history
- When I run `ralph stats --export stats.csv`
- Then a CSV file is created with detailed metrics

### Epic 3: Dry-Run & Preview

#### US-3.1: As a Ralph user, I want to preview what the loop will do without running agents

- Given I have a configured Ralph project
- When I run `ralph run --dry-run`
- Then I see what tasks would be selected, gates that would run, but no agents execute

#### US-3.2: As a Ralph user, I want to validate my configuration before running

- Given I have made config changes
- When I run `ralph run --dry-run`
- Then all config files are validated and issues are reported

#### US-3.3: As a Ralph user, I want to estimate loop duration and cost

- Given I have iteration history
- When I run `ralph run --dry-run --max-iterations 10`
- Then I see estimated time and cost based on historical data

### Epic 4: Interactive Task Selection

#### US-4.1: As a Ralph user, I want to choose which task to work on

- Given I have multiple ready tasks
- When I run `ralph step --interactive`
- Then I see a list of tasks and can select one

#### US-4.2: As a Ralph user, I want to see task details before selecting

- Given I'm in interactive mode
- When I view the task list
- Then I see task ID, title, priority, and acceptance criteria

#### US-4.3: As a Ralph user, I want to skip blocked tasks in the list

- Given some tasks are blocked
- When I run `ralph step --interactive`
- Then blocked tasks are clearly marked and can be filtered out

### Epic 5: Task Dependencies

#### US-5.1: As a Ralph user, I want to define task dependencies so tasks run in order

- Given I have tasks that depend on each other
- When I add `depends_on: ["task-1"]` to task-2 in prd.json
- Then task-2 won't be selected until task-1 is complete

#### US-5.2: As a Ralph user, I want to see a dependency graph

- Given I have tasks with dependencies
- When I run `ralph status --graph`
- Then I see an ASCII dependency graph showing relationships

#### US-5.3: As a Ralph user, I want to detect circular dependencies

- Given I accidentally create circular dependencies
- When I run `ralph diagnose`
- Then circular dependencies are detected and reported

### Epic 6: Snapshot & Rollback

#### US-6.1: As a Ralph user, I want to create snapshots before risky changes

- Given I'm about to make significant changes
- When I run `ralph snapshot "before-refactor"`
- Then a git stash + state backup is created

#### US-6.2: As a Ralph user, I want to rollback to a previous snapshot

- Given I have created snapshots
- When I run `ralph rollback "before-refactor"`
- Then my repo and state are restored to that point

#### US-6.3: As a Ralph user, I want to list available snapshots

- Given I have created multiple snapshots
- When I run `ralph snapshot --list`
- Then I see all snapshots with timestamps and descriptions

### Epic 7: Watch Mode

#### US-7.1: As a Ralph user, I want to auto-run gates when files change

- Given I'm actively developing
- When I run `ralph watch --gates-only`
- Then gates run automatically on file save

#### US-7.2: As a Ralph user, I want to auto-commit when gates pass

- Given I have watch mode enabled
- When I run `ralph watch --auto-commit`
- Then successful gate runs trigger automatic commits

#### US-7.3: As a Ralph user, I want to configure which files trigger watch

- Given I want to watch specific files
- When I configure watch patterns in ralph.toml
- Then only matching files trigger gate runs

### Epic 8: Progress Visualization

#### US-8.1: As a Ralph user, I want to see a progress bar for task completion

- Given I have tasks in my PRD
- When I run `ralph status`
- Then I see an ASCII progress bar showing completion percentage

#### US-8.2: As a Ralph user, I want to see velocity metrics

- Given I have iteration history
- When I run `ralph status --detailed`
- Then I see tasks/day velocity and ETA to completion

#### US-8.3: As a Ralph user, I want to see a burndown chart

- Given I have been working for several days
- When I run `ralph status --chart`
- Then I see an ASCII burndown chart of remaining tasks

### Epic 9: Environment Variable Expansion

#### US-9.1: As a Ralph user, I want to use environment variables in config

- Given I have sensitive values in environment variables
- When I use `${VAR_NAME}` in ralph.toml
- Then the value is expanded from the environment

#### US-9.2: As a Ralph user, I want default values for missing variables

- Given an environment variable might not be set
- When I use `${VAR:-default}` in ralph.toml
- Then the default value is used if VAR is not set

#### US-9.3: As a Ralph user, I want validation for required variables

- Given I use environment variables in config
- When I run `ralph diagnose`
- Then missing required variables are reported

### Epic 10: Task Templates

#### US-10.1: As a Ralph user, I want to create tasks from templates

- Given I have common task patterns
- When I run `ralph task add --template bug-fix --title "Fix login"`
- Then a new task is created with the template structure

#### US-10.2: As a Ralph user, I want to define custom templates

- Given I want project-specific templates
- When I create `.ralph/templates/my-template.json`
- Then it's available for `ralph task add --template my-template`

#### US-10.3: As a Ralph user, I want to list available templates

- Given I have templates configured
- When I run `ralph task templates`
- Then I see all available templates with descriptions

### Epic 11: Quiet Mode

#### US-11.1: As a Ralph user, I want minimal output for CI/CD

- Given I'm running Ralph in CI
- When I run `ralph run --quiet`
- Then only errors and final summary are shown

#### US-11.2: As a Ralph user, I want to control verbosity levels

- Given I want different output levels
- When I use `--quiet`, `--verbose`, or default
- Then output is adjusted accordingly

#### US-11.3: As a Ralph user, I want JSON output for parsing

- Given I want to parse Ralph output
- When I run `ralph status --format json`
- Then output is valid JSON

### Epic 12: Shell Completion

#### US-12.1: As a Ralph user, I want bash completion for commands

- Given I use bash
- When I run `ralph completion bash > ~/.ralph-completion.sh`
- Then tab completion works for all commands and flags

#### US-12.2: As a Ralph user, I want zsh completion

- Given I use zsh
- When I run `ralph completion zsh > ~/.ralph-completion.zsh`
- Then tab completion works in zsh

#### US-12.3: As a Ralph user, I want completion for dynamic values

- Given I'm typing a command
- When I tab-complete after `--agent`
- Then I see available agent names from my config

## Acceptance Criteria

### General Criteria (All Features)

1. **Code Quality**
   - All code follows project style guide
   - Type hints throughout
   - Comprehensive docstrings
   - No breaking changes to existing functionality

2. **Testing**
   - Unit tests for all core logic
   - Integration tests for CLI commands
   - Edge case coverage
   - All tests passing (>95% coverage for new code)

3. **Documentation**
   - User-facing documentation for each feature
   - Code comments for complex logic
   - Updated README with new commands
   - Migration guide if needed

4. **Error Handling**
   - Clear error messages
   - Graceful degradation
   - Helpful suggestions for fixes
   - No silent failures

5. **Performance**
   - Minimal overhead (<100ms for most operations)
   - Efficient file operations
   - No blocking operations in main thread
   - Progress indicators for long operations

### Feature-Specific Criteria

#### Diagnostics

- [ ] Validates ralph.toml syntax and schema
- [ ] Validates PRD file format (JSON/Markdown/YAML)
- [ ] Tests each gate command individually
- [ ] Checks for common misconfigurations
- [ ] Suggests fixes for all detected issues
- [ ] Exit code 0 if all checks pass, 2 if issues found

#### Stats & Tracking

- [ ] Tracks iteration duration in state.json
- [ ] Calculates average, min, max durations
- [ ] Shows success rate and failure patterns
- [ ] Identifies slowest tasks
- [ ] Exports to CSV format
- [ ] Handles missing or incomplete data gracefully

#### Dry-Run Mode

- [ ] Validates all config files
- [ ] Shows which tasks would be selected
- [ ] Lists gates that would run
- [ ] Estimates duration based on history
- [ ] Does not execute any agents
- [ ] Exit code matches what would happen in real run

#### Interactive Task Selection

- [ ] Shows all ready tasks with details
- [ ] Allows arrow key navigation
- [ ] Filters blocked tasks
- [ ] Shows acceptance criteria on demand
- [ ] Supports search/filter
- [ ] Falls back to automatic selection if only one task

#### Task Dependencies

- [ ] Extends PRD schema with `depends_on` field
- [ ] Skips tasks with unmet dependencies
- [ ] Shows dependency graph in ASCII
- [ ] Detects circular dependencies
- [ ] Works with all tracker types (MD/JSON/YAML)
- [ ] Backward compatible (no `depends_on` = no dependencies)

#### Snapshot & Rollback

- [ ] Creates git stash with descriptive message
- [ ] Backs up state.json
- [ ] Lists all snapshots with metadata
- [ ] Restores git state and Ralph state
- [ ] Prevents rollback if working tree is dirty
- [ ] Cleans up old snapshots (configurable retention)

#### Watch Mode

- [ ] Watches configured file patterns
- [ ] Runs gates on file change
- [ ] Debounces rapid changes (500ms default)
- [ ] Shows real-time gate results
- [ ] Optional auto-commit on success
- [ ] Graceful shutdown on Ctrl+C

#### Progress Visualization

- [ ] ASCII progress bar with percentage
- [ ] Calculates velocity (tasks/day)
- [ ] Estimates ETA to completion
- [ ] Shows burndown chart
- [ ] Handles edge cases (no history, all tasks done)
- [ ] Configurable chart size

#### Environment Variable Expansion

- [ ] Expands `${VAR}` syntax in config
- [ ] Supports `${VAR:-default}` for defaults
- [ ] Validates required variables
- [ ] Works in all config sections
- [ ] Secure (no shell injection)
- [ ] Clear error messages for missing vars

#### Task Templates

- [ ] Built-in templates (bug-fix, feature, refactor)
- [ ] Custom template support
- [ ] Template variables (title, priority, etc.)
- [ ] Lists available templates
- [ ] Validates template format
- [ ] Adds tasks to correct tracker format

#### Quiet Mode

- [ ] `--quiet` flag suppresses non-essential output
- [ ] `--verbose` flag shows debug information
- [ ] `--format json` outputs valid JSON
- [ ] Works with all commands
- [ ] Preserves error messages
- [ ] CI-friendly exit codes

#### Shell Completion

- [ ] Generates bash completion script
- [ ] Generates zsh completion script
- [ ] Completes command names
- [ ] Completes flag names
- [ ] Completes dynamic values (agents, templates)
- [ ] Installation instructions in output

## Technical Design Notes

### Architecture Decisions

1. **Modular Design**
   - Each feature in separate module
   - Clear interfaces between modules
   - Minimal coupling to existing code

2. **Configuration**
   - Extend ralph.toml with new sections as needed
   - Backward compatible defaults
   - Validation on load

3. **State Management**
   - Extend state.json schema for tracking
   - Maintain backward compatibility
   - Migration path for old state files

4. **CLI Design**
   - Consistent flag naming
   - Helpful error messages
   - Progress indicators for long operations

### Implementation Order

**Phase 2A (High Priority):**

1. Diagnostics - Foundation for other features
2. Stats & Tracking - High user value
3. Dry-Run Mode - Safety feature

**Phase 2B (Medium Priority):**
4. Interactive Task Selection - UX improvement
5. Task Dependencies - Workflow enhancement
6. Quiet Mode - CI/CD support

**Phase 2C (Advanced Features):**
7. Snapshot & Rollback - Advanced safety
8. Watch Mode - Development workflow
9. Progress Visualization - UX polish

**Phase 2D (Polish):**
10. Environment Variable Expansion - Configuration flexibility
11. Task Templates - Productivity boost
12. Shell Completion - UX polish

### Testing Strategy

Each feature requires:

- Unit tests (core logic)
- Integration tests (CLI)
- Edge case tests
- Error condition tests
- Performance tests (if applicable)

Target: >95% coverage for new code

### Documentation Requirements

Each feature needs:

- User guide in docs/
- CLI help text
- Code comments
- README updates
- Migration notes (if applicable)

## Dependencies

- Python 3.11+ (existing)
- No new external dependencies preferred
- Use stdlib where possible

## Risks & Mitigations

**Risk:** Feature creep and scope expansion  
**Mitigation:** Strict adherence to acceptance criteria, phased implementation

**Risk:** Breaking existing functionality  
**Mitigation:** Comprehensive test suite, backward compatibility checks

**Risk:** Performance degradation  
**Mitigation:** Performance tests, profiling, optimization

**Risk:** Complex interdependencies between features  
**Mitigation:** Modular design, clear interfaces, phased rollout

## Success Metrics

- All 12 features implemented and tested
- Zero breaking changes
- Test coverage >95% for new code
- All existing tests still passing
- Documentation complete
- User feedback positive

## Timeline Estimate

- Phase 2A: 4-6 hours (3 features)
- Phase 2B: 4-6 hours (3 features)
- Phase 2C: 6-8 hours (3 features)
- Phase 2D: 4-6 hours (3 features)

Total: 18-26 hours of focused development

## Notes

This is an ambitious scope. Consider implementing in phases with user feedback between phases. Each phase delivers standalone value.
