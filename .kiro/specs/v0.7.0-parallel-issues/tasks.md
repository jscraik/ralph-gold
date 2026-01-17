# Ralph-Gold v0.7.0: Implementation Tasks

## Phase 1: YAML Tracker

### 1.1 YAML Tracker Core Implementation

- [x] Create `src/ralph_gold/trackers/` package structure with `__init__.py`
- [x] Implement `YamlTracker` class in `src/ralph_gold/trackers/yaml_tracker.py`
  - [x] Add YAML loading with PyYAML/ruamel.yaml
  - [x] Implement schema validation (version, tasks structure)
  - [x] Implement `peek_next_task()` method
  - [x] Implement `claim_next_task()` method
  - [x] Implement `counts()` method
  - [x] Implement `all_done()` method
  - [x] Implement `is_task_done()` method
  - [x] Implement `force_task_open()` method
  - [x] Implement `branch_name()` method
  - [x] Implement `get_parallel_groups()` method (returns dict[str, list[SelectedTask]])
- [x] Update `make_tracker()` in `trackers.py` to support "yaml" kind
- [x] Add PyYAML dependency to `pyproject.toml`

**Validates Requirements:** 3 (YAML tracker with parallel grouping)

**Acceptance:**

- YamlTracker implements full Tracker protocol
- Can load valid tasks.yaml files with version, metadata, and tasks
- Invalid YAML raises clear validation errors
- Parallel groups extracted from task "group" field
- Tasks without group field default to "default" group

### 1.2 YAML Tracker Tests

- [x] Create `tests/test_yaml_tracker.py`
- [x] Write unit tests for YAML loading (valid and invalid files)
- [x] Write unit tests for schema validation
- [x] Write unit tests for parallel group extraction
- [x] Write unit tests for task claiming and completion
- [x] Write tests for error cases (missing fields, malformed YAML)
- [x] Write tests for edge cases (empty tasks, duplicate IDs)

**Validates Requirements:** 3

**Acceptance:**

- 100% code coverage for YamlTracker
- All Tracker protocol methods tested
- Error messages validated

### 1.3 YAML Migration Tool

- [x] Add `convert` subcommand to CLI in `cli.py`
- [x] Implement JSON → YAML converter
- [x] Implement Markdown → YAML converter
- [x] Add validation of converted YAML
- [x] Add `--output` flag for output file path
- [x] Add `--infer-groups` flag for optional group inference

**Validates Requirements:** 8 (Migration from existing PRDs)

**Acceptance:**

- `ralph convert prd.json tasks.yaml` works
- `ralph convert PRD.md tasks.yaml` works
- Conversion preserves all task data
- Generated YAML is valid and readable

### 1.4 YAML Documentation & Templates

- [x] Create `docs/YAML_TRACKER.md` with format reference
- [x] Add YAML examples to README
- [x] Add `--format yaml` flag to `ralph init` command
- [x] Create `tasks.yaml` template in `src/ralph_gold/templates/`
- [x] Update scaffold.py to support YAML format

**Validates Requirements:** 3

**Acceptance:**

- Documentation covers YAML schema and examples
- `ralph init --format yaml` creates valid tasks.yaml
- Template includes comments and examples

## Phase 2: GitHub Issues Tracker

### 2.1 GitHub Authentication Layer

- [x] Create `src/ralph_gold/github_auth.py`
- [x] Implement `GitHubAuth` base class/protocol
- [x] Implement `GhCliAuth` class
  - [x] Use `gh api` commands for API calls
  - [x] Validate gh CLI is installed and authenticated
  - [x] Handle gh CLI errors gracefully
- [x] Implement `TokenAuth` class
  - [x] Read token from environment variable
  - [x] Use requests library for API calls
  - [x] Add proper headers (Authorization, User-Agent)
- [x] Add token security measures
  - [x] Never log tokens
  - [x] Use `__repr__` to hide tokens
  - [x] Clear tokens on cleanup
- [x] Add `--check-github` flag to `ralph doctor` command

**Validates Requirements:** 2 (GitHub authentication)

**Acceptance:**

- gh CLI auth works when gh is installed
- Token auth works with GITHUB_TOKEN env var
- Auth failures provide clear error messages
- Tokens never appear in logs or output
- `ralph doctor --check-github` validates auth

### 2.2 GitHub Issues Tracker Core

- [x] Create `src/ralph_gold/trackers/github_issues.py`
- [x] Implement `GitHubIssuesTracker` class
  - [x] Implement all Tracker protocol methods
  - [x] Add `_sync_cache()` method for issue fetching
  - [x] Add `_load_cache()` method
  - [x] Add `_save_cache()` method
  - [x] Add `_cache_is_fresh()` method with TTL check
  - [x] Add `_issue_to_task()` converter
  - [x] Add `_extract_group_from_labels()` for parallel grouping
- [x] Implement issue fetching with label filtering
- [x] Implement cache to `.ralph/github_cache.json`
- [x] Add rate limit detection from response headers
- [x] Implement priority sorting (milestone, then created_at)
- [x] Implement `get_parallel_groups()` using "group:*" labels

**Validates Requirements:** 2, 5 (GitHub Issues with parallel grouping)

**Acceptance:**

- Issues fetched and cached correctly
- Label filtering works (include/exclude)
- Cache reduces API calls by 90%+
- Rate limits respected
- Priority sorting works
- Parallel groups extracted from labels

### 2.3 GitHub Issues Updates

- [x] Add `mark_task_done()` method to GitHubIssuesTracker
- [x] Implement issue closing via API
- [x] Implement comment posting with iteration results
- [x] Implement label management (add/remove)
- [x] Add commit SHA linking in comments
- [x] Handle API failures gracefully (log but don't crash)
- [x] Add update logging to `.ralph/logs/github-api.log`

**Validates Requirements:** 2

**Acceptance:**

- Issues closed when tasks complete
- Comments include gate results and duration
- Labels updated correctly
- Failed updates logged but don't crash loop
- All API calls logged

### 2.4 GitHub Configuration

- [x] Extend `Config` dataclass in `config.py`
  - [x] Add `GitHubTrackerConfig` dataclass
  - [x] Add `github` field to `TrackerConfig`
  - [x] Parse `[tracker.github]` section from TOML
- [x] Add configuration fields:
  - [x] `repo` (required)
  - [x] `auth_method` (gh_cli|token)
  - [x] `token_env` (default: GITHUB_TOKEN)
  - [x] `label_filter` (required label)
  - [x] `exclude_labels` (list)
  - [x] `close_on_done` (bool)
  - [x] `comment_on_done` (bool)
  - [x] `add_labels_on_start` (list)
  - [x] `add_labels_on_done` (list)
  - [x] `cache_ttl_seconds` (default: 300)

**Validates Requirements:** 2

**Acceptance:**

- Config loads GitHub settings from TOML
- All fields have sensible defaults
- Invalid config raises clear errors

### 2.5 GitHub Issues Tests

- [x] Create `tests/test_github_auth.py`
  - [x] Test GhCliAuth with mocked subprocess
  - [x] Test TokenAuth with mocked requests
  - [x] Test token security (no logging)
- [x] Create `tests/test_github_issues.py`
  - [x] Test issue fetching with mocked API
  - [x] Test caching logic
  - [x] Test TTL expiration
  - [x] Test rate limit handling
  - [x] Test label filtering
  - [x] Test priority sorting
  - [x] Test parallel group extraction
  - [x] Test issue updates
  - [x] Test error handling

**Validates Requirements:** 2, 7

**Acceptance:**

- 100% code coverage for GitHub tracker
- All API interactions mocked
- Error cases tested
- Security measures validated

### 2.6 GitHub Issues CLI & Documentation

- [ ] Add `issues` subcommand group to CLI
  - [ ] Add `ralph issues list` command
  - [ ] Add `ralph issues show <number>` command
  - [ ] Add `ralph issues sync` command (force cache refresh)
- [ ] Add `--tracker github_issues` support to `ralph run`
- [ ] Create `docs/GITHUB_ISSUES.md`
  - [ ] Setup instructions (gh CLI vs token)
  - [ ] Configuration examples
  - [ ] Label conventions for parallel grouping
  - [ ] Troubleshooting section
- [ ] Update README with GitHub Issues feature

**Validates Requirements:** 2

**Acceptance:**

- All CLI commands work
- Documentation complete and clear
- Examples tested

## Phase 3: Parallel Execution Core

### 3.1 Configuration Extension

- [x] Extend `Config` dataclass in `config.py`
  - [x] Add `ParallelConfig` dataclass with fields:
    - [x] `enabled` (bool, default False)
    - [x] `max_workers` (int, default 3)
    - [x] `worktree_root` (str, default ".ralph/worktrees")
    - [x] `strategy` (str, default "queue") # queue|group
    - [x] `merge_policy` (str, default "manual") # manual|auto_merge
  - [x] Add `parallel` field to `Config`
  - [x] Parse `[parallel]` section from TOML
- [x] Add config validation
- [x] Add safe defaults (parallel disabled by default)

**Validates Requirements:** 1, 4 (Parallel execution configuration)

**Acceptance:**

- Config loads parallel settings correctly
- Invalid config raises clear errors
- Defaults are safe (parallel disabled)
- All fields documented

### 3.2 Git Worktree Manager

- [x] Create `src/ralph_gold/worktree.py`
- [x] Implement `WorktreeManager` class
  - [x] `__init__(project_root, worktree_root)`
  - [x] `create_worktree(task, worker_id)` → (path, branch_name)
  - [x] `remove_worktree(worktree_path)`
  - [x] `_generate_branch_name(task, worker_id)` → str
  - [x] `list_worktrees()` → list[Path]
  - [x] `cleanup_stale_worktrees()`
- [x] Add unique branch name generation (ralph/worker-{id}-task-{task_id})
- [x] Add error handling for git worktree operations
- [x] Preserve failed worktrees for debugging

**Validates Requirements:** 1, 4 (Worker isolation)

**Acceptance:**

- Worktrees created in isolated directories
- Branch names unique and predictable
- Worktrees cleaned up after success
- Failed worktrees preserved
- Stale worktrees can be cleaned manually

### 3.3 Parallel Executor Core

- [x] Create `src/ralph_gold/parallel.py`
- [x] Implement `WorkerState` dataclass
  - [x] Fields: worker_id, task, worktree_path, branch_name, status, started_at, completed_at, iteration_result, error
- [x] Implement `ParallelExecutor` class
  - [x] `__init__(project_root, cfg)`
  - [x] `run_parallel(agent, tracker)` → list[IterationResult]
  - [x] `_run_worker(worker_id, task, agent)` → IterationResult
  - [x] `_flatten_groups(groups)` → list[SelectedTask]
  - [x] `_schedule_by_groups(groups)` → list[SelectedTask]
  - [x] `_merge_worker(worker)` (for auto_merge policy)
- [x] Use ThreadPoolExecutor for worker pool
- [x] Add task scheduling strategies:
  - [x] "queue": flatten all groups, run FIFO
  - [x] "group": run groups sequentially, tasks within group in parallel
- [x] Add worker state tracking
- [x] Isolate worker failures (don't kill other workers)

**Validates Requirements:** 1, 5 (Parallel execution engine)

**Acceptance:**

- Workers run in parallel
- Workers isolated (no interference)
- Task scheduling respects groups
- Worker state tracked accurately
- Failed workers don't kill others

### 3.4 Parallel State Management

- [ ] Extend `.ralph/state.json` schema
  - [ ] Add `parallel` section with:
    - [ ] `enabled` (bool)
    - [ ] `last_run` (timestamp)
    - [ ] `workers` (list of worker metadata)
- [ ] Update `save_state()` in `loop.py` to include parallel data
- [ ] Update `load_state()` to handle parallel data
- [ ] Add parallel metrics (speedup, success rate)
- [ ] Ensure backward compatibility

**Validates Requirements:** 1

**Acceptance:**

- State includes parallel execution data
- State survives process restarts
- Metrics accurate
- Backward compatible with v0.6.0

### 3.5 Loop Integration

- [x] Update `run_loop()` in `loop.py` to support parallel mode
  - [x] Add `parallel` parameter (bool)
  - [x] Detect parallel mode from config
  - [x] Delegate to ParallelExecutor when enabled
  - [x] Keep sequential mode unchanged
- [x] Add `--parallel` flag to `ralph run` command in CLI
- [x] Add `--max-workers` flag to `ralph run` command
- [x] Add parallel execution logging to `.ralph/logs/parallel-{timestamp}.log`
- [x] Ensure sequential mode still works (no breaking changes)

**Validates Requirements:** 1

**Acceptance:**

- `ralph run --parallel` works
- Sequential mode unchanged
- Config-based parallel mode works
- Logs show parallel execution details

### 3.6 Merge Management

- [ ] Implement merge logic in ParallelExecutor
  - [ ] Add `_merge_worker(worker)` method
  - [ ] Implement "manual" policy (preserve branches, no merge)
  - [ ] Implement "auto_merge" policy (merge on success)
  - [ ] Add merge conflict detection
  - [ ] Add merge failure handling
  - [ ] Add branch cleanup after successful merge
- [ ] Log all merge operations
- [ ] Preserve branches on merge failure

**Validates Requirements:** 1, 4 (Safe merging)

**Acceptance:**

- Manual policy preserves all branches
- Auto-merge merges successful workers
- Merge conflicts detected and reported
- Failed merges preserve both branches
- Successful merges clean up worktrees

### 3.7 Parallel Execution Tests

- [ ] Create `tests/test_worktree.py`
  - [ ] Test worktree creation
  - [ ] Test worktree removal
  - [ ] Test branch name generation
  - [ ] Test cleanup of stale worktrees
- [ ] Create `tests/test_parallel.py`
  - [ ] Test ParallelExecutor initialization
  - [ ] Test queue strategy
  - [ ] Test group strategy
  - [ ] Test worker isolation
  - [ ] Test failure handling
  - [ ] Test merge policies
- [ ] Create `tests/test_integration_parallel.py`
  - [ ] Test end-to-end parallel execution
  - [ ] Test YAML + parallel
  - [ ] Test GitHub Issues + parallel
  - [ ] Test failure recovery
- [ ] Add performance tests
  - [ ] Measure parallel speedup
  - [ ] Measure worktree overhead

**Validates Requirements:** 1, 4

**Acceptance:**

- 100% code coverage for parallel code
- Worker isolation verified
- Speedup meets 3x target for 3 tasks
- All failure scenarios tested

## Phase 4: TUI + CLI + Documentation

### 4.1 Parallel TUI Display

- [ ] Create `ParallelStatusPanel` class in `tui.py`
  - [ ] Add real-time worker status display
  - [ ] Add worker progress indicators (⏳⚙✓✗)
  - [ ] Add worker error display
  - [ ] Add keyboard shortcuts for worker logs
  - [ ] Add refresh rate configuration
- [ ] Update main TUI to detect and show parallel mode
- [ ] Add worker log viewing capability
- [ ] Test TUI in both sequential and parallel modes

**Validates Requirements:** 6 (Real-time visibility)

**Acceptance:**

- TUI shows all active workers
- Status updates in real-time (< 2s lag)
- Worker errors clearly visible
- User can view individual worker logs
- Works in both modes

### 4.2 Parallel CLI Commands

- [ ] Add `parallel` subcommand group to CLI
  - [ ] Add `ralph parallel list` (list active worktrees)
  - [ ] Add `ralph parallel clean` (cleanup stale worktrees)
  - [ ] Add `ralph parallel status` (show worker status)
- [ ] Update `ralph status` to show parallel info
- [ ] Add `--dry-run` support for parallel mode
- [ ] Add proper error messages and help text

**Validates Requirements:** 1

**Acceptance:**

- All commands work correctly
- Output clear and formatted
- Dry-run shows what would happen
- Status shows current parallel state

### 4.3 Tracker Refactoring

- [ ] Move existing tracker implementations to `trackers/` package
  - [ ] Create `src/ralph_gold/trackers/file_tracker.py` (move FileTracker)
  - [ ] Create `src/ralph_gold/trackers/beads_tracker.py` (move BeadsTracker)
  - [ ] Update imports in `trackers/__init__.py`
- [ ] Update `make_tracker()` to use new package structure
- [ ] Add auto-detection for tracker kind
- [ ] Ensure backward compatibility (no breaking changes)
- [ ] Update tests to use new structure

**Validates Requirements:** N/A (refactoring)

**Acceptance:**

- All existing trackers work unchanged
- New package structure is clean
- Auto-detection works correctly
- No breaking changes for users
- All tests pass

### 4.4 Integration Testing

- [ ] Create `tests/test_integration_yaml_parallel.py`
  - [ ] Test end-to-end YAML + parallel execution
  - [ ] Test 3 tasks in 2 groups
  - [ ] Verify parallel speedup
- [ ] Create `tests/test_integration_github.py`
  - [ ] Test GitHub Issues + sequential
  - [ ] Test GitHub Issues + parallel
  - [ ] Test with mocked GitHub API
- [ ] Create `tests/test_integration_failure_recovery.py`
  - [ ] Test mixed success/failure scenarios
  - [ ] Test worktree preservation on failure
  - [ ] Test state recovery
- [ ] Create `tests/test_migration.py`
  - [ ] Test migration from v0.6.0 configs
  - [ ] Test backward compatibility

**Validates Requirements:** All

**Acceptance:**

- All integration tests pass
- Real-world scenarios covered
- Failure recovery works
- Migration seamless

### 4.5 Performance Testing

- [ ] Create `tests/test_performance.py`
  - [ ] Benchmark parallel speedup (3 tasks)
  - [ ] Benchmark parallel speedup (5 tasks)
  - [ ] Benchmark worktree creation overhead
  - [ ] Benchmark GitHub API cache efficiency
  - [ ] Benchmark YAML parsing performance
- [ ] Document performance results in test output
- [ ] Add performance targets as assertions

**Validates Requirements:** Performance targets from requirements

**Acceptance:**

- Parallel achieves 3x+ speedup for 3 tasks
- Worktree overhead < 2s per worker
- GitHub cache reduces API calls by 90%+
- YAML parsing < 100ms for 1000 tasks
- All targets met or exceeded

### 4.6 Documentation

- [ ] Create `docs/PARALLEL_EXECUTION.md`
  - [ ] Architecture overview
  - [ ] Configuration guide
  - [ ] Usage examples
  - [ ] Troubleshooting
- [ ] Create `docs/YAML_TRACKER.md` (if not done in Phase 1)
- [ ] Create `docs/GITHUB_ISSUES.md` (if not done in Phase 2)
- [ ] Update `README.md` with v0.7.0 features
  - [ ] Feature overview
  - [ ] Quick start examples
  - [ ] Links to detailed docs
- [ ] Update `docs/GOLDEN_LOOP.md` with parallel workflow
- [ ] Create migration guide from v0.6.0
  - [ ] Breaking changes (none expected)
  - [ ] New features
  - [ ] Configuration updates
- [ ] Add FAQ section
- [ ] Update all code examples

**Validates Requirements:** All

**Acceptance:**

- Documentation complete and accurate
- All examples tested
- Migration guide clear
- Troubleshooting covers common issues

### 4.7 Release Preparation

- [ ] Update version to 0.7.0 in `pyproject.toml`
- [ ] Update `__version__` in `__init__.py`
- [ ] Write CHANGELOG.md entry for v0.7.0
  - [ ] New features
  - [ ] Bug fixes
  - [ ] Breaking changes (if any)
  - [ ] Migration notes
- [ ] Write release notes
- [ ] Run full test suite (`uv run pytest`)
- [ ] Run type checking (`uv run mypy src/ralph_gold`)
- [ ] Run linting (`uv run ruff check src/ralph_gold`)
- [ ] Test installation from source
- [ ] Create git tag v0.7.0
- [ ] Prepare PyPI release

**Validates Requirements:** N/A (release process)

**Acceptance:**

- All tests pass
- Version numbers correct
- CHANGELOG complete
- Release notes clear
- Installation works

## Optional Tasks (Post-v0.7.0)

These tasks are deferred to v0.8.0 or later based on design decisions.

### Optional: Lifecycle Hooks System

- [ ]* Create `src/ralph_gold/hooks.py`
- [ ]* Implement `HooksConfig` dataclass
- [ ]* Implement `HooksManager` class
- [ ]* Add hook execution for lifecycle events
- [ ]* Integrate with loop
- [ ]* Add CLI support
- [ ]* Add documentation

**Note:** Deferred to v0.8.0. Users can use shell scripts and cron for now.

### Optional: Session Management

- [ ]* Create `src/ralph_gold/session.py`
- [ ]* Implement `SessionManager` class
- [ ]* Add session creation and resumption
- [ ]* Add session listing and cleanup
- [ ]* Integrate with loop
- [ ]* Add CLI support
- [ ]* Add documentation

**Note:** Deferred to v0.8.0. Current state.json provides basic resumption.

### Optional: Feedback Channel

- [ ]* Create `src/ralph_gold/feedback.py`
- [ ]* Implement `FeedbackChannel` class
- [ ]* Add feedback injection into prompts
- [ ]* Add CLI support
- [ ]* Add documentation

**Note:** Deferred to v0.8.0. Users can edit PROMPT.md directly for now.

### Optional: AI-Powered Merge Conflict Resolution

- [ ]* Implement conflict detection in merge logic
- [ ]* Add AI agent invocation for conflict resolution
- [ ]* Add conflict resolution prompt template
- [ ]* Test conflict resolution accuracy
- [ ]* Document conflict resolution feature

**Note:** Deferred to v0.8.0. Manual resolution is safer for initial release.

### Optional: Dynamic Worker Scaling

- [ ]* Implement system resource monitoring
- [ ]* Add dynamic max_workers adjustment
- [ ]* Add worker scaling configuration
- [ ]* Test scaling behavior

**Note:** Deferred to v0.8.0. Fixed max_workers is simpler and predictable.

### Optional: GitHub Projects Integration

- [ ]* Add GitHub Projects API support
- [ ]* Implement project board tracking
- [ ]* Add column-based task filtering
- [ ]* Document Projects integration

**Note:** Deferred to v0.8.0. Issues are sufficient for most teams.

## Task Dependencies

```
Phase 1 (YAML Tracker)
  └─ No dependencies (can start immediately)

Phase 2 (GitHub Issues)
  └─ No dependencies (can run parallel with Phase 1)

Phase 3 (Parallel Execution)
  ├─ Depends on: Phase 1 complete (for parallel groups in YAML)
  └─ Depends on: Phase 2 complete (for parallel groups in GitHub Issues)

Phase 4 (Integration)
  └─ Depends on: Phases 1, 2, 3 complete (all features implemented)
```

## Implementation Strategy

### Recommended Order

1. **Start with Phase 1 (YAML Tracker)** - This is the foundation for parallel grouping
2. **Parallel with Phase 2 (GitHub Issues)** - Can be developed independently
3. **Phase 3 (Parallel Execution)** - Requires both Phase 1 and 2 for full testing
4. **Phase 4 (Integration)** - Final polish, testing, and documentation

### Critical Path

The critical path for parallel execution is:

1. YAML Tracker with `get_parallel_groups()` method
2. Worktree Manager for isolation
3. Parallel Executor for orchestration
4. Integration testing

### Testing Strategy

- **Unit tests** for each component as it's built
- **Integration tests** after Phase 3 is complete
- **Performance tests** to validate speedup targets
- **Migration tests** to ensure backward compatibility

## Success Criteria

- [ ] All unit tests pass (100% coverage for new code)
- [ ] All integration tests pass
- [ ] Performance targets met (3x speedup for 3 tasks)
- [ ] Documentation complete
- [ ] Zero breaking changes from v0.6.0
- [ ] All examples tested and working
- [ ] Release notes written
- [ ] CHANGELOG updated

## Estimated Effort

- **Phase 1 (YAML):** 3-5 days
- **Phase 2 (GitHub):** 4-6 days
- **Phase 3 (Parallel):** 5-7 days
- **Phase 4 (Integration):** 3-5 days
- **Total:** 15-23 days (3-5 weeks)

## Risk Mitigation

### High Risk: Parallel execution complexity

- **Mitigation:** Extensive testing, start with simple queue strategy
- **Fallback:** Disable parallel mode if critical bugs found

### Medium Risk: GitHub API rate limits

- **Mitigation:** Aggressive caching, rate limit monitoring
- **Fallback:** Increase cache TTL, reduce API calls

### Medium Risk: Worktree disk space

- **Mitigation:** Automatic cleanup, clear warnings
- **Fallback:** Manual cleanup command, documentation

### Low Risk: Migration issues

- **Mitigation:** Backward compatibility testing, migration guide
- **Fallback:** Rollback instructions, v0.6.0 still available
