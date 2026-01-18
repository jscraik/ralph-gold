# Ralph Gold Phase 2 Configuration Guide

This document describes the configuration options added in Phase 2 enhancements.

## Table of Contents

- [Diagnostics Configuration](#diagnostics-configuration)
- [Stats Configuration](#stats-configuration)
- [Watch Mode Configuration](#watch-mode-configuration)
- [Progress Visualization Configuration](#progress-visualization-configuration)
- [Templates Configuration](#templates-configuration)
- [Output Control Configuration](#output-control-configuration)

---

## Diagnostics Configuration

The `[diagnostics]` section controls configuration validation and testing features.

### Options

```toml
[diagnostics]
enabled = true        # Enable diagnostics features
check_gates = true    # Test gate commands during diagnostics
validate_prd = true   # Validate PRD file format
```

### Details

- **`enabled`** (boolean, default: `true`)
  - Enables the diagnostics system
  - When enabled, `ralph diagnose` command is available
  - Validates configuration, PRD format, and optionally tests gates

- **`check_gates`** (boolean, default: `true`)
  - When true, `ralph diagnose --test-gates` will test each gate command
  - Useful for verifying gate commands work before running the loop
  - Each gate is tested individually with a 30-second timeout

- **`validate_prd`** (boolean, default: `true`)
  - Validates PRD file format (JSON/Markdown/YAML)
  - Checks for syntax errors and structural issues
  - Provides actionable suggestions for fixing problems

### Usage Examples

```bash
# Run all diagnostics
ralph diagnose

# Run diagnostics including gate tests
ralph diagnose --test-gates

# Disable diagnostics in config
[diagnostics]
enabled = false
```

---

## Stats Configuration

The `[stats]` section controls iteration statistics tracking and analysis.

### Options

```toml
[stats]
track_duration = true   # Track iteration duration
track_cost = false      # Track API costs (future feature)
```

### Details

- **`track_duration`** (boolean, default: `true`)
  - Automatically tracks duration of each iteration
  - Stores `duration_seconds` in state.json history
  - Required for stats calculation and reporting

- **`track_cost`** (boolean, default: `false`)
  - Future feature: track API costs per iteration
  - Currently not implemented
  - Reserved for future cost tracking functionality

### Usage Examples

```bash
# View iteration statistics
ralph stats

# View per-task breakdown
ralph stats --by-task

# Export to CSV
ralph stats --export stats.csv

# Disable duration tracking
[stats]
track_duration = false
```

### Data Tracked

When `track_duration = true`, each iteration in `state.json` includes:

```json
{
  "iteration": 1,
  "timestamp": "2024-01-15T10:30:00Z",
  "duration_seconds": 45.2,
  "task_id": "task-1",
  "success": true
}
```

---

## Watch Mode Configuration

The `[watch]` section controls file watching and auto-execution features.

### Options

```toml
[watch]
enabled = false                      # Enable watch mode
patterns = ["**/*.py", "**/*.md"]   # File patterns to watch
debounce_ms = 500                    # Debounce delay in milliseconds
auto_commit = false                  # Auto-commit on success
```

### Details

- **`enabled`** (boolean, default: `false`)
  - Enables watch mode functionality
  - When true, `ralph watch` command is available
  - Watch mode is opt-in for safety

- **`patterns`** (list of strings, default: `["**/*.py", "**/*.md"]`)
  - Glob patterns for files to watch
  - Uses standard glob syntax (`**` for recursive, `*` for wildcard)
  - Respects `.gitignore` patterns
  - Examples:
    - `"**/*.py"` - all Python files recursively
    - `"src/**/*.ts"` - TypeScript files in src/
    - `"*.json"` - JSON files in root only

- **`debounce_ms`** (integer, default: `500`)
  - Delay in milliseconds before triggering gate run
  - Prevents excessive runs during rapid file changes
  - Recommended: 300-1000ms depending on project size

- **`auto_commit`** (boolean, default: `false`)
  - Automatically commit changes when gates pass
  - Only commits if all gates succeed
  - Uses configured commit message template
  - **Warning**: Use with caution in production

### Usage Examples

```bash
# Start watch mode (gates only)
ralph watch --gates-only

# Watch with auto-commit
ralph watch --auto-commit

# Custom watch patterns
[watch]
enabled = true
patterns = [
  "src/**/*.py",
  "tests/**/*.py",
  "*.toml"
]
debounce_ms = 1000
```

### Safety Notes

- Watch mode respects `.gitignore` by default
- Ctrl+C gracefully shuts down watch mode
- Auto-commit is disabled by default for safety
- Gates must pass before auto-commit triggers

---

## Progress Visualization Configuration

The `[progress]` section controls progress metrics and visualization.

### Options

```toml
[progress]
show_velocity = true    # Show tasks/day velocity
show_burndown = true    # Show burndown chart
chart_width = 60        # ASCII chart width in characters
```

### Details

- **`show_velocity`** (boolean, default: `true`)
  - Calculate and display velocity (tasks completed per day)
  - Requires iteration history with timestamps
  - Used for ETA calculation

- **`show_burndown`** (boolean, default: `true`)
  - Generate ASCII burndown chart
  - Shows remaining tasks over time
  - Requires multiple days of history for meaningful chart

- **`chart_width`** (integer, default: `60`)
  - Width of ASCII charts in characters
  - Recommended: 40-80 depending on terminal width
  - Affects burndown chart and progress bars

### Usage Examples

```bash
# View progress with default settings
ralph status

# View detailed progress with charts
ralph status --detailed

# View burndown chart
ralph status --chart

# Customize chart width
[progress]
chart_width = 80
```

### Progress Metrics

The progress system calculates:

- **Completion percentage**: `(completed / total) * 100`
- **Velocity**: `completed_tasks / days_elapsed`
- **ETA**: `remaining_tasks / velocity` (in days)

### Example Output

```
Progress: [████████████░░░░░░░░] 60% (12/20 tasks)
Velocity: 2.5 tasks/day
ETA: 3.2 days
```

---

## Templates Configuration

The `[templates]` section controls task template features.

### Options

```toml
[templates]
builtin = ["bug-fix", "feature", "refactor"]  # Built-in templates to enable
custom_dir = ".ralph/templates"                # Directory for custom templates
```

### Details

- **`builtin`** (list of strings, default: `["bug-fix", "feature", "refactor"]`)
  - Built-in templates to make available
  - Options: `"bug-fix"`, `"feature"`, `"refactor"`
  - Can disable by providing empty list: `builtin = []`

- **`custom_dir`** (string, default: `".ralph/templates"`)
  - Directory containing custom template files
  - Templates should be JSON files: `my-template.json`
  - Custom templates override built-in templates with same name

### Built-in Templates

#### bug-fix Template

```json
{
  "name": "bug-fix",
  "title_template": "Fix: {title}",
  "priority": "high",
  "acceptance_criteria": [
    "Bug is reproducible with test case",
    "Root cause is identified",
    "Fix is implemented and tested",
    "Regression test added"
  ]
}
```

#### feature Template

```json
{
  "name": "feature",
  "title_template": "Feature: {title}",
  "priority": "medium",
  "acceptance_criteria": [
    "Requirements are documented",
    "Implementation is complete",
    "Tests are passing",
    "Documentation is updated"
  ]
}
```

#### refactor Template

```json
{
  "name": "refactor",
  "title_template": "Refactor: {title}",
  "priority": "low",
  "acceptance_criteria": [
    "Code is cleaner and more maintainable",
    "All existing tests still pass",
    "No functional changes",
    "Performance is maintained or improved"
  ]
}
```

### Custom Templates

Create custom templates in `.ralph/templates/`:

```json
{
  "name": "security-fix",
  "description": "Security vulnerability fix",
  "title_template": "Security: {title}",
  "priority": "critical",
  "acceptance_criteria": [
    "Vulnerability is confirmed and documented",
    "Fix is implemented and tested",
    "Security review completed",
    "CVE filed if applicable"
  ],
  "variables": ["title", "cve_id"]
}
```

### Usage Examples

```bash
# List available templates
ralph task templates

# Create task from template
ralph task add --template bug-fix --title "Login fails on Safari"

# Create task from custom template
ralph task add --template security-fix --title "XSS in search"

# Disable built-in templates
[templates]
builtin = []
custom_dir = ".ralph/my-templates"
```

---

## Output Control Configuration

The `[output]` section controls verbosity and output format.

### Options

```toml
[output]
verbosity = "normal"  # quiet|normal|verbose
format = "text"       # text|json
```

### Details

- **`verbosity`** (string, default: `"normal"`)
  - Controls output verbosity level
  - Options:
    - `"quiet"`: Only errors and final summary
    - `"normal"`: Standard progress output
    - `"verbose"`: Detailed debug information
  - Can be overridden with CLI flags: `--quiet`, `--verbose`

- **`format`** (string, default: `"text"`)
  - Controls output format
  - Options:
    - `"text"`: Human-readable text output
    - `"json"`: Machine-parseable JSON output
  - Can be overridden with CLI flag: `--format json`

### Verbosity Levels

#### Quiet Mode (`verbosity = "quiet"`)

- Only shows errors and final summary
- No progress indicators
- Minimal output for CI/CD
- Errors always displayed regardless of verbosity

Example output:

```
Error: Gate command failed
Summary: 0/5 tasks completed
```

#### Normal Mode (`verbosity = "normal"`)

- Standard progress output
- Gate results
- Iteration summaries
- Default mode for interactive use

Example output:

```
Starting iteration 1...
Running gates...
✓ Gate 1: npm test (passed)
✓ Gate 2: npm run lint (passed)
Iteration 1 complete (45.2s)
```

#### Verbose Mode (`verbosity = "verbose"`)

- All normal output plus:
- Debug information
- Detailed gate output
- Timing information
- Useful for troubleshooting

Example output:

```
[DEBUG] Loading config from .ralph/ralph.toml
[DEBUG] Found 3 runners: codex, claude, copilot
Starting iteration 1...
[DEBUG] Selected task: task-1 (priority: high)
Running gates...
[DEBUG] Executing: npm test
✓ Gate 1: npm test (passed in 12.3s)
[DEBUG] Executing: npm run lint
✓ Gate 2: npm run lint (passed in 3.1s)
[DEBUG] All gates passed
Iteration 1 complete (45.2s)
```

### JSON Output Format

When `format = "json"`, all commands output structured JSON:

```json
{
  "status": "success",
  "iteration": 1,
  "duration_seconds": 45.2,
  "gates_passed": true,
  "task": {
    "id": "task-1",
    "title": "Implement feature X"
  }
}
```

### Usage Examples

```bash
# Run in quiet mode
ralph run --quiet

# Run in verbose mode
ralph run --verbose

# Get JSON output
ralph status --format json

# Configure default verbosity
[output]
verbosity = "verbose"
format = "text"
```

### Environment Variables

Output settings can also be controlled via environment variables:

```bash
# Set verbosity
export RALPH_VERBOSITY=quiet

# Set format
export RALPH_FORMAT=json

# Run with environment settings
ralph run
```

Priority order (highest to lowest):

1. CLI flags (`--quiet`, `--verbose`, `--format json`)
2. Environment variables (`RALPH_VERBOSITY`, `RALPH_FORMAT`)
3. Configuration file (`ralph.toml`)
4. Default values

---

## Complete Configuration Example

Here's a complete `ralph.toml` with all Phase 2 features configured:

```toml
# Ralph Gold Configuration - Phase 2 Features

[loop]
max_iterations = 50
no_progress_limit = 3
max_attempts_per_task = 3
skip_blocked_tasks = true

[files]
prd = ".ralph/PRD.md"
progress = ".ralph/progress.md"
specs_dir = ".ralph/specs"

[diagnostics]
enabled = true
check_gates = true
validate_prd = true

[stats]
track_duration = true
track_cost = false

[watch]
enabled = false
patterns = ["**/*.py", "**/*.md", "**/*.toml"]
debounce_ms = 500
auto_commit = false

[progress]
show_velocity = true
show_burndown = true
chart_width = 60

[templates]
builtin = ["bug-fix", "feature", "refactor"]
custom_dir = ".ralph/templates"

[output]
verbosity = "normal"
format = "text"

[gates]
commands = ["npm test", "npm run lint"]

[git]
auto_commit = false
branch_strategy = "none"

[runners.codex]
argv = ["codex", "exec", "--full-auto", "-"]

[runners.claude]
argv = ["claude", "--output-format", "stream-json", "-p"]
```

---

## Migration from Phase 1

All Phase 2 configuration options have sensible defaults and are backward compatible:

- **No breaking changes**: Existing configurations continue to work
- **Opt-in features**: New features like watch mode are disabled by default
- **Automatic defaults**: Missing sections use default values
- **Gradual adoption**: Enable features one at a time as needed

### Migration Steps

1. **No action required**: Your existing `ralph.toml` continues to work
2. **Optional**: Add new sections to enable Phase 2 features
3. **Optional**: Run `ralph diagnose` to validate configuration
4. **Optional**: Customize settings based on your workflow

### Validation

After updating your configuration, validate it:

```bash
# Check configuration validity
ralph diagnose

# Test with dry-run
ralph run --dry-run

# View current configuration
ralph config show  # (if implemented)
```

---

## Troubleshooting

### Configuration Not Loading

**Problem**: New configuration options not recognized

**Solution**:

- Ensure you're using the latest version of Ralph Gold
- Check for typos in section names (case-sensitive)
- Validate TOML syntax: `ralph diagnose`

### Invalid Configuration Values

**Problem**: Error messages about invalid configuration

**Solution**:

- Check value types (boolean, string, integer, list)
- Verify enum values (e.g., `verbosity` must be `quiet`, `normal`, or `verbose`)
- Review error message for specific field causing issue

### Watch Mode Not Working

**Problem**: Watch mode not detecting file changes

**Solution**:

- Verify `watch.enabled = true` in configuration
- Check `watch.patterns` match your files
- Ensure files are not in `.gitignore` (unless intended)
- Try increasing `debounce_ms` if changes are too rapid

### Stats Not Tracking

**Problem**: No statistics available

**Solution**:

- Ensure `stats.track_duration = true`
- Check that iterations have completed (history exists)
- Verify `state.json` contains `duration_seconds` fields
- Run at least one iteration to generate data

---

## Best Practices

### Development Workflow

```toml
[output]
verbosity = "verbose"  # See detailed output

[watch]
enabled = true
patterns = ["src/**/*.py", "tests/**/*.py"]
auto_commit = false  # Manual review before commit

[diagnostics]
enabled = true
check_gates = true
```

### CI/CD Workflow

```toml
[output]
verbosity = "quiet"  # Minimal output
format = "json"      # Machine-parseable

[diagnostics]
enabled = true
check_gates = true  # Validate before running

[stats]
track_duration = true  # Track performance
```

### Production Workflow

```toml
[output]
verbosity = "normal"

[watch]
enabled = false  # Disable auto-execution

[gates]
commands = ["npm test", "npm run lint", "npm run security-check"]

[git]
auto_commit = false  # Manual review required
```

---

## See Also

- [Main Configuration Guide](configuration.md) - Phase 1 configuration options
- [CLI Reference](cli-reference.md) - Command-line interface documentation
- [Phase 2 Features](phase2-features.md) - Overview of Phase 2 enhancements
- [Diagnostics Guide](diagnostics.md) - Using the diagnostics system
- [Stats Guide](stats.md) - Understanding iteration statistics
