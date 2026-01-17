# Parallel Execution Configuration

## Overview

Ralph Gold v0.7.0 introduces parallel execution support, allowing multiple tasks to run concurrently in isolated git worktrees. This feature is **opt-in** and **disabled by default** for safety.

## Configuration

Add a `[parallel]` section to your `.ralph/ralph.toml` or `ralph.toml`:

```toml
[parallel]
enabled = false              # opt-in, disabled by default
max_workers = 3              # concurrent agents
worktree_root = ".ralph/worktrees"
strategy = "queue"           # queue|group
merge_policy = "manual"      # manual|auto_merge
```

## Configuration Fields

### `enabled` (bool, default: `false`)

Controls whether parallel execution is enabled. Must be explicitly set to `true` to use parallel mode.

**Safety:** Disabled by default to prevent accidental parallel execution.

### `max_workers` (int, default: `3`)

Maximum number of concurrent workers. Each worker runs in an isolated git worktree.

**Validation:** Must be >= 1.

**Recommendation:** Start with 3 workers and adjust based on your system resources and task complexity.

### `worktree_root` (str, default: `".ralph/worktrees"`)

Directory where git worktrees are created (relative to project root).

**Note:** Each worktree requires ~500MB of disk space. Ensure sufficient disk space for `max_workers` worktrees.

### `strategy` (str, default: `"queue"`)

Task scheduling strategy:

- **`"queue"`**: Flatten all task groups and run tasks in FIFO order
- **`"group"`**: Run groups sequentially, but tasks within each group run in parallel

**Validation:** Must be either `"queue"` or `"group"` (case-insensitive).

### `merge_policy` (str, default: `"manual"`)

How to handle successful task branches:

- **`"manual"`**: Preserve all branches, no automatic merging (safest, recommended)
- **`"auto_merge"`**: Automatically merge successful tasks to the main branch

**Validation:** Must be either `"manual"` or `"auto_merge"` (case-insensitive).

**Safety:** Manual merge policy is recommended to review changes before merging.

## Examples

### Minimal Configuration (Parallel Disabled)

```toml
# No [parallel] section needed - defaults to disabled
[loop]
max_iterations = 10
```

### Enable Parallel Execution

```toml
[parallel]
enabled = true
max_workers = 3
```

### Custom Configuration

```toml
[parallel]
enabled = true
max_workers = 5
worktree_root = ".ralph/custom_worktrees"
strategy = "group"
merge_policy = "auto_merge"
```

## Validation

The configuration loader validates all parallel settings:

- **Invalid strategy**: Raises `ValueError` with clear message
- **Invalid merge_policy**: Raises `ValueError` with clear message
- **Invalid max_workers**: Raises `ValueError` if < 1

Example error messages:

```
ValueError: Invalid parallel.strategy: 'invalid'. Must be 'queue' or 'group'.
ValueError: Invalid parallel.merge_policy: 'bad'. Must be 'manual' or 'auto_merge'.
ValueError: Invalid parallel.max_workers: 0. Must be >= 1.
```

## Backward Compatibility

Existing configurations without a `[parallel]` section continue to work unchanged. The parallel configuration has safe defaults:

- `enabled = false` (parallel execution disabled)
- `max_workers = 3`
- `worktree_root = ".ralph/worktrees"`
- `strategy = "queue"`
- `merge_policy = "manual"`

## Usage with CLI

```bash
# Run with parallel mode (if enabled in config)
ralph run --parallel

# Override max_workers from CLI
ralph run --parallel --max-workers 5

# Sequential mode (default)
ralph run
```

## Safety Features

1. **Opt-in by default**: Parallel execution must be explicitly enabled
2. **Manual merge policy**: Default merge policy preserves branches for review
3. **Isolated worktrees**: Each worker runs in a separate git worktree
4. **Validation**: All configuration values are validated on load
5. **Clear error messages**: Invalid configurations provide actionable feedback

## See Also

- [PARALLEL_CONFIG_EXAMPLE.toml](./PARALLEL_CONFIG_EXAMPLE.toml) - Complete example configuration
- [v0.7.0 Requirements](../.kiro/specs/v0.7.0-parallel-issues/requirements.md) - Full feature specification
- [v0.7.0 Design](../.kiro/specs/v0.7.0-parallel-issues/design.md) - Architecture and design decisions
