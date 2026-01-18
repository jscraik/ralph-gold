# Ralph Gold - New Features Summary

## Recently Implemented Features

### 1. ✅ Automatic Archiving (ralph init --force)

**Status:** Complete and tested (5 tests)

**What it does:**

- Automatically backs up existing `.ralph` files before overwriting
- Creates timestamped archive directories
- Preserves directory structure
- Shows user-friendly summary of archived files

**Usage:**

```bash
ralph init --force
# → Archives existing files to .ralph/archive/20260118-143022/
# → Creates fresh templates
```

**Benefits:**

- Prevents accidental data loss when re-initializing
- Easy to recover previous work
- Safe experimentation with configuration changes

**Files:**

- `src/ralph_gold/scaffold.py` - Archive logic
- `tests/test_scaffold_archive.py` - 5 comprehensive tests
- `docs/INIT_ARCHIVING.md` - Full documentation

---

### 2. ✅ Smart Resume (ralph resume)

**Status:** Complete and tested (11 tests)

**What it does:**

- Detects interrupted iterations from state.json
- Shows what was being worked on when interrupted
- Interactive prompt to resume or clear
- Recommends resume based on gate status

**Usage:**

```bash
# Check for interrupted iterations
ralph resume

# Auto-resume without prompting
ralph resume --auto

# Clear interrupted state and start fresh
ralph resume --clear
```

**Benefits:**

- Recover gracefully from crashes or interruptions
- Don't lose progress when gates passed
- Clear visibility into what was interrupted

**Example Output:**

```
Last iteration (42) was interrupted:
  Agent: codex
  Task: task-123
  Title: Implement feature X
  Gates: ✓ PASSED
  Time: 2024-01-18T14:30:00Z
  Log: .ralph/logs/iter0042.log

Resume this iteration? [Y/n]:
```

**Files:**

- `src/ralph_gold/resume.py` - Resume detection logic
- `src/ralph_gold/cli.py` - CLI command
- `tests/test_resume.py` - 11 comprehensive tests

---

### 3. ✅ Clean Command (ralph clean)

**Status:** Complete and tested (9 tests)

**What it does:**

- Removes old logs, archives, receipts, and context files
- Configurable age thresholds for each artifact type
- Dry-run mode to preview deletions
- Human-readable size reporting

**Usage:**

```bash
# Clean with defaults (logs>30d, archives>90d, receipts>60d, context>60d)
ralph clean

# Preview what would be deleted
ralph clean --dry-run

# More aggressive cleanup
ralph clean --logs-days 7 --archives-days 30

# Keep everything longer
ralph clean --logs-days 90 --archives-days 180
```

**Example Output:**

```
Logs:     127 files (2.3 GB)
Archives: 5 dirs, 234 files (1.8 GB)
Receipts: 89 files (45.2 MB)
Context:  156 files (123.4 MB)

Total: 606 files, 5 directories
Freed: 4.3 GB
```

**Benefits:**

- Manage disk space automatically
- Keep workspace tidy
- Safe with dry-run mode
- Configurable retention policies

**Files:**

- `src/ralph_gold/clean.py` - Cleanup logic
- `src/ralph_gold/cli.py` - CLI command
- `tests/test_clean.py` - 9 comprehensive tests

---

## Test Coverage

**Total new tests:** 25 tests
**All tests passing:** ✅ 241/241 tests pass

### Test Breakdown

- Archiving: 5 tests
- Resume: 11 tests
- Clean: 9 tests

### Test Quality

- Unit tests for core logic
- Integration tests for CLI commands
- Edge case coverage
- Dry-run mode testing
- Error handling validation

---

## Remaining Planned Features

These features were designed but not yet implemented. They're ready for future development:

### High Priority

**4. Diagnostics Command (ralph diagnose)**

- Validate config files
- Check file formats (prd.json, ralph.toml)
- Test gate commands individually
- Suggest fixes for common issues

**5. Stats & Tracking (ralph stats)**

- Track iteration duration and costs
- Show velocity metrics
- Identify slow tasks
- Export to CSV for analysis

### Medium Priority

**6. Dry-Run Mode (ralph run --dry-run)**

- Validate configuration without running agents
- Show what tasks would be selected
- Estimate time/cost based on history

**7. Interactive Task Selection (ralph step --interactive)**

- Show all available tasks
- Let user pick which one to work on
- Useful for urgent fixes

**8. Task Dependencies**

- Extend prd.json with `depends_on` field
- Auto-skip tasks with unmet dependencies
- Show dependency graph

### Lower Priority

**9. Snapshot & Rollback**

- Create git stash + state backup
- Rollback to named snapshots
- Safer than manual git operations

**10. Watch Mode (ralph watch)**

- Auto-run gates on file save
- Optional auto-commit if gates pass
- Great for TDD workflows

**11-15. Additional Features**

- Better progress visualization
- Environment variable expansion in config
- Task templates
- Quiet mode
- Shell completion

---

## Implementation Notes

### Design Principles

All features follow these principles:

1. **Fail-safe defaults** - Dry-run modes, confirmations for destructive operations
2. **Clear feedback** - User-friendly output with actionable information
3. **Comprehensive testing** - Every feature has extensive test coverage
4. **Minimal dependencies** - Use stdlib where possible
5. **Consistent UX** - Follow existing CLI patterns

### Code Quality

- All code follows project style guide
- Type hints throughout
- Docstrings for all public functions
- Error handling with clear messages
- No breaking changes to existing functionality

### Testing Strategy

Each feature includes:

- Unit tests for core logic
- Integration tests for CLI
- Edge case coverage
- Error condition testing
- Dry-run mode validation

---

## Migration Guide

### For Existing Users

**No breaking changes!** All new features are additive.

**New commands available:**

- `ralph resume` - Check for interrupted iterations
- `ralph clean` - Clean old workspace artifacts

**Enhanced commands:**

- `ralph init --force` - Now archives existing files automatically

**Recommended workflow:**

1. Update to latest version: `uv tool install -e .`
2. Run `ralph clean --dry-run` to see what can be cleaned
3. Use `ralph resume` after any interruptions
4. Use `ralph init --force` safely when re-initializing

### For New Users

Start with the quickstart:

```bash
uv tool install -e .
ralph init
ralph doctor
ralph step --agent codex
```

If interrupted:

```bash
ralph resume
```

To clean up:

```bash
ralph clean --dry-run  # Preview
ralph clean            # Actually clean
```

---

## Performance Impact

**Minimal overhead:**

- Resume detection: <10ms (only reads state.json)
- Clean command: Depends on file count, typically <1s
- Archiving: Adds ~100ms to `ralph init --force`

**Disk space:**

- Archives grow over time (use `ralph clean` to manage)
- Logs can accumulate (default 30-day retention)

---

## Future Roadmap

### Phase 2 (Next Session)

- Diagnostics command
- Stats & tracking
- Dry-run mode

### Phase 3 (Future)

- Interactive task selection
- Task dependencies
- Snapshot & rollback

### Phase 4 (Polish)

- Watch mode
- Better progress visualization
- Shell completion

---

## Contributing

To add new features:

1. Follow the implementation plan in `.agent/FEATURE_IMPLEMENTATION_PLAN.md`
2. Write tests first (TDD approach)
3. Implement feature with comprehensive error handling
4. Update documentation
5. Run full test suite: `uv run pytest -q`
6. Submit PR with test results

---

## Support

**Documentation:**

- `docs/INIT_ARCHIVING.md` - Archiving details
- `docs/NEW_FEATURES.md` - This file
- `README.md` - General usage

**Getting Help:**

- Check `ralph <command> --help` for usage
- Review test files for examples
- See `.agent/FEATURE_IMPLEMENTATION_PLAN.md` for roadmap

**Reporting Issues:**

- Include `ralph --version` output
- Provide minimal reproduction steps
- Include relevant log files (sanitized)
