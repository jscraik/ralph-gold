# Ralph Enhancement Features - Implementation Plan

## Phase 1: Core Reliability Features (This Session)

### 1. Smart Resume ✓ (Started)

- [x] Create resume.py module
- [ ] Add cmd_resume to CLI
- [ ] Add tests for resume detection
- [ ] Add tests for resume workflow
- [ ] Update documentation

### 2. Diagnostics Command

- [ ] Create diagnostics.py module
- [ ] Implement config validation
- [ ] Implement file format checks
- [ ] Implement gate command validation
- [ ] Add cmd_diagnose to CLI
- [ ] Add comprehensive tests
- [ ] Update documentation

### 3. Stats & Tracking

- [ ] Create stats.py module
- [ ] Add duration tracking to state.json
- [ ] Implement stats aggregation
- [ ] Add cmd_stats to CLI
- [ ] Add tests for stats calculation
- [ ] Update documentation

### 4. Clean Command

- [ ] Create clean.py module
- [ ] Implement log cleanup
- [ ] Implement archive cleanup
- [ ] Add cmd_clean to CLI
- [ ] Add tests for cleanup logic
- [ ] Update documentation

### 5. Config Validation

- [ ] Extend config.py with validation
- [ ] Add cmd_config_validate to CLI
- [ ] Add cmd_config_migrate for schema updates
- [ ] Add tests for validation
- [ ] Update documentation

## Phase 2: UX Improvements (Future Session)

### 6. Dry-Run Mode

- [ ] Add --dry-run flag to run command
- [ ] Implement validation without execution
- [ ] Add cost estimation
- [ ] Tests

### 7. Interactive Task Selection

- [ ] Add --interactive flag to step command
- [ ] Implement task picker UI
- [ ] Tests

### 8. Task Dependencies

- [ ] Extend prd.json schema
- [ ] Update tracker logic
- [ ] Add dependency graph visualization
- [ ] Tests

## Phase 3: Advanced Features (Future Session)

### 9. Snapshot & Rollback

- [ ] Create snapshot.py module
- [ ] Implement git stash + state backup
- [ ] Add rollback command
- [ ] Tests

### 10. Watch Mode

- [ ] Create watch.py module
- [ ] Implement file watching
- [ ] Add auto-gate execution
- [ ] Tests

### 11-15. Additional Features

- Better progress visualization
- Environment variable expansion
- Task templates
- Quiet mode
- Shell completion

## Testing Strategy

Each feature must have:

- Unit tests for core logic
- Integration tests for CLI commands
- Edge case coverage
- Documentation updates

## Success Criteria

Phase 1 complete when:

- All 5 features implemented
- All tests passing (>95% coverage for new code)
- Documentation updated
- Manual smoke testing completed
- Git committed and pushed
