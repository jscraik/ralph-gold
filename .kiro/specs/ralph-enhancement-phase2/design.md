# Ralph Gold Phase 2 Enhancements - Design Document

## Overview

This design document specifies the technical architecture for 12 enhancement features that build on Ralph Gold's existing foundation. The features are organized into four implementation phases (2A-2D) and follow established patterns from the codebase.

**Spec Workflow Context:**

This design follows the requirements-first workflow:

1. ✅ Requirements defined in `requirements.md`
2. ✅ Design specified in this document
3. ⏭️ Next: Create `tasks.md` with implementation tasks after design approval

**Core Design Principles:**

- Modular architecture: each feature in its own module
- Backward compatibility: no breaking changes
- Consistent CLI patterns: follow existing command structure
- Comprehensive testing: >95% coverage target
- Type safety: full type hints throughout

**Implementation Phases:**

- **Phase 2A (High Priority):** Diagnostics, Stats, Dry-Run
- **Phase 2B (Medium Priority):** Interactive Selection, Dependencies, Quiet Mode
- **Phase 2C (Advanced Features):** Snapshots, Watch Mode, Progress Visualization
- **Phase 2D (Polish):** Environment Variables, Templates, Shell Completion

## Architecture

### Module Organization

Following the established pattern, each major feature gets its own module:

```
src/ralph_gold/
├── diagnostics.py      # Configuration validation and testing
├── stats.py            # Iteration statistics and analysis
├── interactive.py      # Interactive task selection UI
├── dependencies.py     # Task dependency graph management
├── snapshots.py        # Git-based snapshot/rollback
├── watch.py            # File watching and auto-execution
├── progress.py         # Progress visualization and metrics
├── envvars.py          # Environment variable expansion
├── templates.py        # Task template management
└── completion.py       # Shell completion generation
```

**Shared Functionality:**

- `cli.py`: Register all new commands with `cmd_<name>` functions
- `config.py`: Extend configuration dataclasses as needed
- `loop.py`: Integrate dry-run and quiet mode into existing loop
- `trackers.py`: Extend for dependency support

### State Management

Extend `.ralph/state.json` schema to support new tracking requirements:

```python
{
  "createdAt": "ISO-8601",
  "session_id": "YYYYMMDD-HHMMSS",
  "history": [
    {
      "iteration": int,
      "timestamp": "ISO-8601",
      "duration_seconds": float,  # NEW: for stats
      "task_id": str,
      "success": bool,
      "gates_passed": bool,
      "attempt_number": int  # NEW: for retry tracking
    }
  ],
  "invocations": [...],
  "noProgressStreak": int,
  "snapshots": [  # NEW: for snapshot feature
    {
      "name": str,
      "timestamp": "ISO-8601",
      "git_stash_ref": str,
      "state_backup_path": str
    }
  ],
  "stats_cache": {  # NEW: for performance
    "last_calculated": "ISO-8601",
    "total_iterations": int,
    "avg_duration": float,
    "success_rate": float
  }
}
```

### Configuration Extensions

Extend `ralph.toml` with new sections:

```toml
[diagnostics]
enabled = true
check_gates = true
validate_prd = true

[stats]
track_duration = true
track_cost = false  # Future: API cost tracking

[watch]
enabled = false
patterns = ["**/*.py", "**/*.md"]
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
verbosity = "normal"  # quiet|normal|verbose
format = "text"  # text|json
```

## Components and Interfaces

### 1. Diagnostics Module (`diagnostics.py`)

**Purpose:** Validate configuration, PRD format, and test gate commands.

**Core Functions:**

```python
@dataclass
class DiagnosticResult:
    """Result of a diagnostic check."""
    check_name: str
    passed: bool
    message: str
    suggestions: List[str]
    severity: str  # error|warning|info

def validate_config(project_root: Path) -> List[DiagnosticResult]:
    """Validate ralph.toml syntax and schema."""
    pass

def validate_prd(project_root: Path, cfg: Config) -> List[DiagnosticResult]:
    """Validate PRD file format (JSON/MD/YAML)."""
    pass

def test_gates(project_root: Path, cfg: Config) -> List[DiagnosticResult]:
    """Test each gate command individually."""
    pass

def run_diagnostics(
    project_root: Path,
    test_gates: bool = False
) -> Tuple[List[DiagnosticResult], int]:
    """Run all diagnostic checks. Returns (results, exit_code)."""
    pass
```

**Integration Points:**

- Uses `config.load_config()` to validate configuration
- Uses `trackers.make_tracker()` to validate PRD format
- Executes gate commands from `cfg.gates.commands`
- Returns exit code 0 (all pass) or 2 (issues found)

**Error Handling:**

- Catches TOML parsing errors with line numbers
- Validates required fields in configuration
- Tests gate commands in isolated subprocess
- Provides actionable fix suggestions

### 2. Stats Module (`stats.py`)

**Purpose:** Track and analyze iteration statistics.

**Core Functions:**

```python
@dataclass
class IterationStats:
    """Statistics for iterations."""
    total_iterations: int
    successful_iterations: int
    failed_iterations: int
    avg_duration_seconds: float
    min_duration_seconds: float
    max_duration_seconds: float
    success_rate: float
    task_stats: Dict[str, TaskStats]  # task_id -> stats

@dataclass
class TaskStats:
    """Statistics for a specific task."""
    task_id: str
    attempts: int
    successes: int
    failures: int
    avg_duration_seconds: float
    total_duration_seconds: float

def calculate_stats(state: Dict[str, Any]) -> IterationStats:
    """Calculate statistics from state.json history."""
    pass

def export_stats_csv(stats: IterationStats, output_path: Path) -> None:
    """Export statistics to CSV format."""
    pass

def format_stats_report(stats: IterationStats, by_task: bool = False) -> str:
    """Format statistics as human-readable report."""
    pass
```

**Integration Points:**

- Reads from `.ralph/state.json` history
- Extends `loop.py` to track `duration_seconds` in history entries
- Caches calculations in `state.stats_cache` for performance
- Supports CSV export for external analysis

**Performance Considerations:**

- Cache stats calculations (invalidate on new iterations)
- Limit history analysis to last N iterations (configurable)
- Use efficient aggregation algorithms

### 3. Dry-Run Mode

**Purpose:** Preview loop execution without running agents.

**Implementation Strategy:**

- Add `--dry-run` flag to `ralph run` and `ralph step` commands
- Modify `loop.py` to skip agent execution when dry_run=True
- Validate all configuration and show execution plan

**Core Functions:**

```python
def dry_run_loop(
    project_root: Path,
    cfg: Config,
    max_iterations: int
) -> DryRunResult:
    """Simulate loop execution without running agents."""
    pass

@dataclass
class DryRunResult:
    """Result of dry-run simulation."""
    tasks_to_execute: List[str]
    gates_to_run: List[str]
    estimated_duration_seconds: float
    estimated_cost: float  # Future
    config_valid: bool
    issues: List[str]
```

**Integration Points:**

- Modify `run_loop()` in `loop.py` to accept `dry_run` parameter
- Use `stats.calculate_stats()` for duration estimation
- Validate configuration using `diagnostics.validate_config()`
- Show task selection logic without execution

### 4. Interactive Task Selection (`interactive.py`)

**Purpose:** Allow users to manually select which task to work on.

**Core Functions:**

```python
@dataclass
class TaskChoice:
    """A task available for selection."""
    task_id: str
    title: str
    priority: str
    status: str
    blocked: bool
    acceptance_criteria: List[str]

def select_task_interactive(
    tasks: List[TaskChoice],
    show_blocked: bool = False
) -> Optional[TaskChoice]:
    """Display interactive task selector and return user choice."""
    pass

def format_task_list(tasks: List[TaskChoice]) -> str:
    """Format tasks as numbered list with details."""
    pass
```

**UI Design:**

- Simple numbered list (no external dependencies like `curses`)
- Show task ID, title, priority, status
- Filter blocked tasks by default
- Support search/filter by keyword
- Fallback to automatic selection if only one task

**Integration Points:**

- Modify `loop.py` task selection to call `select_task_interactive()` when `--interactive` flag is set
- Use existing `trackers.make_tracker()` to get task list
- Respect `skip_blocked_tasks` configuration

### 5. Task Dependencies (`dependencies.py`)

**Purpose:** Define and enforce task execution order.

**Core Functions:**

```python
@dataclass
class DependencyGraph:
    """Task dependency graph."""
    nodes: Dict[str, TaskNode]
    edges: List[Tuple[str, str]]  # (from_task, to_task)

@dataclass
class TaskNode:
    """Node in dependency graph."""
    task_id: str
    depends_on: List[str]
    blocked_by: List[str]
    ready: bool

def build_dependency_graph(tasks: List[Dict]) -> DependencyGraph:
    """Build dependency graph from task list."""
    pass

def detect_circular_dependencies(graph: DependencyGraph) -> List[List[str]]:
    """Detect circular dependencies using DFS."""
    pass

def get_ready_tasks(graph: DependencyGraph, completed: Set[str]) -> List[str]:
    """Get tasks with all dependencies satisfied."""
    pass

def format_dependency_graph(graph: DependencyGraph) -> str:
    """Format graph as ASCII art."""
    pass
```

**PRD Schema Extension:**

For JSON tracker:

```json
{
  "tasks": [
    {
      "id": "task-1",
      "title": "...",
      "depends_on": ["task-0"]  // NEW field
    }
  ]
}
```

For Markdown tracker:

```markdown
## Task: task-1
**Depends On:** task-0, task-2
```

**Integration Points:**

- Extend `trackers.py` to parse `depends_on` field
- Modify task selection in `loop.py` to filter by dependencies
- Add `ralph status --graph` command to visualize
- Run circular dependency check in `diagnostics.py`

**Algorithm:**

- Use topological sort for execution order
- DFS for circular dependency detection
- O(V + E) complexity for graph operations

### 6. Snapshot & Rollback (`snapshots.py`)

**Purpose:** Create git-based snapshots for safe rollback.

**Core Functions:**

```python
@dataclass
class Snapshot:
    """A snapshot of project state."""
    name: str
    timestamp: str
    git_stash_ref: str
    state_backup_path: str
    description: str

def create_snapshot(
    project_root: Path,
    name: str,
    description: str = ""
) -> Snapshot:
    """Create a snapshot using git stash."""
    pass

def list_snapshots(project_root: Path) -> List[Snapshot]:
    """List all available snapshots."""
    pass

def rollback_snapshot(
    project_root: Path,
    name: str,
    force: bool = False
) -> bool:
    """Rollback to a specific snapshot."""
    pass

def cleanup_old_snapshots(
    project_root: Path,
    keep_count: int = 10
) -> int:
    """Remove old snapshots, keeping most recent N."""
    pass
```

**Implementation Details:**

- Use `git stash push -m "ralph-snapshot: {name}"` for git state
- Copy `.ralph/state.json` to `.ralph/snapshots/{name}/state.json`
- Store snapshot metadata in `state.json`
- Prevent rollback if working tree is dirty
- Support automatic cleanup of old snapshots

**Integration Points:**

- Add `ralph snapshot` and `ralph rollback` commands
- Optional: auto-snapshot before risky operations
- Integrate with git operations in `loop.py`

### 7. Watch Mode (`watch.py`)

**Purpose:** Auto-run gates when files change.

**Core Functions:**

```python
@dataclass
class WatchConfig:
    """Configuration for watch mode."""
    patterns: List[str]
    debounce_ms: int
    auto_commit: bool
    gates_only: bool

def watch_files(
    project_root: Path,
    cfg: Config,
    watch_cfg: WatchConfig,
    callback: Callable[[Path], None]
) -> None:
    """Watch files and trigger callback on changes."""
    pass

def run_watch_mode(
    project_root: Path,
    cfg: Config,
    gates_only: bool = True,
    auto_commit: bool = False
) -> None:
    """Run watch mode with gate execution."""
    pass
```

**Implementation Strategy:**

- Use stdlib `watchdog` library (or implement simple polling)
- Debounce rapid changes (500ms default)
- Run gates on file change
- Optional auto-commit on success
- Graceful shutdown on Ctrl+C

**Integration Points:**

- Add `ralph watch` command
- Use existing gate execution from `loop.py`
- Respect `.gitignore` patterns
- Show real-time results

**Performance:**

- Efficient file watching (inotify on Linux, FSEvents on macOS)
- Debouncing to avoid excessive runs
- Background execution without blocking

### 8. Progress Visualization (`progress.py`)

**Purpose:** Show progress metrics and charts.

**Core Functions:**

```python
@dataclass
class ProgressMetrics:
    """Progress tracking metrics."""
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    blocked_tasks: int
    completion_percentage: float
    velocity_tasks_per_day: float
    estimated_completion_date: Optional[str]

def calculate_progress(
    project_root: Path,
    cfg: Config
) -> ProgressMetrics:
    """Calculate progress metrics from task tracker and history."""
    pass

def format_progress_bar(
    completed: int,
    total: int,
    width: int = 60
) -> str:
    """Format ASCII progress bar."""
    pass

def format_burndown_chart(
    history: List[Dict],
    width: int = 60,
    height: int = 20
) -> str:
    """Format ASCII burndown chart."""
    pass

def calculate_velocity(history: List[Dict]) -> float:
    """Calculate tasks completed per day."""
    pass
```

**Visualization Examples:**

Progress bar:

```
Progress: [████████████░░░░░░░░] 60% (12/20 tasks)
```

Burndown chart:

```
Tasks
20 │ ●
   │  ●
15 │   ●●
   │     ●
10 │      ●●
   │        ●
 5 │         ●●
   │           ●
 0 └─────────────────
   Day 1  3  5  7  9
```

**Integration Points:**

- Extend `ralph status` with `--detailed` and `--chart` flags
- Use task tracker for current state
- Use `state.json` history for velocity
- Calculate ETA based on velocity

### 9. Environment Variable Expansion (`envvars.py`)

**Purpose:** Support environment variables in configuration.

**Core Functions:**

```python
def expand_env_vars(value: str) -> str:
    """Expand ${VAR} and ${VAR:-default} syntax."""
    pass

def validate_required_vars(config_dict: Dict) -> List[str]:
    """Find all required env vars and check if set."""
    pass

def expand_config(config_dict: Dict) -> Dict:
    """Recursively expand all env vars in config."""
    pass
```

**Syntax Support:**

- `${VAR}`: Expand variable, error if not set
- `${VAR:-default}`: Expand with default value
- `$$`: Escape literal `$`

**Security:**

- No shell execution (prevent injection)
- Validate variable names (alphanumeric + underscore)
- Clear error messages for missing variables

**Integration Points:**

- Modify `config.load_config()` to expand variables after TOML parsing
- Add validation to `diagnostics.py`
- Document in user guide

**Implementation:**

```python
import os
import re

ENV_VAR_PATTERN = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)(:-([^}]*))?\}')

def expand_env_vars(value: str) -> str:
    """Expand environment variables in string."""
    def replacer(match):
        var_name = match.group(1)
        default = match.group(3)
        
        env_value = os.environ.get(var_name)
        if env_value is not None:
            return env_value
        elif default is not None:
            return default
        else:
            raise ValueError(f"Required environment variable not set: {var_name}")
    
    return ENV_VAR_PATTERN.sub(replacer, value)
```

### 10. Task Templates (`templates.py`)

**Purpose:** Create tasks from reusable templates.

**Core Functions:**

```python
@dataclass
class TaskTemplate:
    """A task template."""
    name: str
    description: str
    title_template: str
    acceptance_criteria: List[str]
    priority: str
    variables: List[str]  # Variables to substitute

def load_builtin_templates() -> Dict[str, TaskTemplate]:
    """Load built-in templates."""
    pass

def load_custom_templates(project_root: Path) -> Dict[str, TaskTemplate]:
    """Load custom templates from .ralph/templates/."""
    pass

def create_task_from_template(
    template: TaskTemplate,
    variables: Dict[str, str],
    tracker: Any
) -> str:
    """Create a new task from template. Returns task ID."""
    pass

def list_templates(project_root: Path) -> List[TaskTemplate]:
    """List all available templates."""
    pass
```

**Built-in Templates:**

1. **bug-fix**: For bug fixes

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

2. **feature**: For new features

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

3. **refactor**: For refactoring

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

**Custom Templates:**

- Store in `.ralph/templates/*.json`
- Same schema as built-in templates
- Override built-in templates by name

**Integration Points:**

- Add `ralph task add --template <name>` command
- Add `ralph task templates` command to list
- Integrate with all tracker types (MD/JSON/YAML)

### 11. Quiet Mode

**Purpose:** Control output verbosity for different contexts.

**Implementation Strategy:**

- Add global `--quiet`, `--verbose`, `--format json` flags
- Modify all output functions to respect verbosity level
- Ensure CI-friendly exit codes

**Verbosity Levels:**

1. **Quiet** (`--quiet`):
   - Only errors and final summary
   - No progress indicators
   - Minimal output for CI/CD

2. **Normal** (default):
   - Standard progress output
   - Gate results
   - Iteration summaries

3. **Verbose** (`--verbose`):
   - Debug information
   - Detailed gate output
   - Timing information

**JSON Output:**

- `--format json` outputs structured JSON
- All commands support JSON format
- Schema documented for parsing

**Implementation:**

```python
@dataclass
class OutputConfig:
    """Output configuration."""
    verbosity: str  # quiet|normal|verbose
    format: str  # text|json
    color: bool  # Enable ANSI colors

def get_output_config() -> OutputConfig:
    """Get output config from CLI args and environment."""
    pass

def print_output(message: str, level: str = "normal") -> None:
    """Print output respecting verbosity level."""
    pass

def format_json_output(data: Dict) -> str:
    """Format data as JSON output."""
    pass
```

**Integration Points:**

- Add flags to all CLI commands
- Modify `loop.py` to respect quiet mode
- Ensure all print statements check verbosity
- Add JSON formatters for all commands

### 12. Shell Completion (`completion.py`)

**Purpose:** Generate shell completion scripts.

**Core Functions:**

```python
def generate_bash_completion() -> str:
    """Generate bash completion script."""
    pass

def generate_zsh_completion() -> str:
    """Generate zsh completion script."""
    pass

def get_dynamic_completions(command: str, partial: str) -> List[str]:
    """Get dynamic completions (e.g., agent names, templates)."""
    pass
```

**Completion Support:**

- Command names: `ralph <TAB>` → shows all commands
- Flags: `ralph run --<TAB>` → shows all flags
- Dynamic values:
  - `ralph run --agent <TAB>` → shows configured agents
  - `ralph task add --template <TAB>` → shows templates
  - `ralph rollback <TAB>` → shows snapshot names

**Implementation:**

- Generate completion scripts from argparse definitions
- Support both bash and zsh
- Include installation instructions in output
- Dynamic completions via helper function

**Integration Points:**

- Add `ralph completion bash|zsh` command
- Read configuration for dynamic completions
- Document installation in README

## Data Models

### Extended State Schema

```python
@dataclass
class IterationHistory:
    """Extended iteration history entry."""
    iteration: int
    timestamp: str
    duration_seconds: float  # NEW
    task_id: str
    task_title: str  # NEW
    success: bool
    gates_passed: bool
    attempt_number: int  # NEW
    agent: str
    exit_signal: Optional[bool]
    return_code: int

@dataclass
class SnapshotMetadata:
    """Snapshot metadata."""
    name: str
    timestamp: str
    git_stash_ref: str
    state_backup_path: str
    description: str
    git_commit: str  # Commit hash at snapshot time

@dataclass
class StatsCache:
    """Cached statistics."""
    last_calculated: str
    total_iterations: int
    avg_duration: float
    success_rate: float
```

### Dependency Graph Schema

```python
@dataclass
class TaskDependency:
    """Task dependency information."""
    task_id: str
    depends_on: List[str]
    blocked_by: List[str]  # Computed from depends_on
    ready: bool  # All dependencies satisfied
    depth: int  # Depth in dependency tree
```

### Template Schema

```json
{
  "name": "template-name",
  "description": "Template description",
  "title_template": "Prefix: {title}",
  "priority": "medium",
  "acceptance_criteria": [
    "Criterion 1",
    "Criterion 2"
  ],
  "variables": ["title", "component"],
  "metadata": {
    "author": "optional",
    "version": "1.0"
  }
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, I've identified several areas where properties can be consolidated:

**Redundancy Analysis:**

1. Stats calculations (avg, min, max, success rate) can be combined into a single "statistical correctness" property
2. Validation properties across different file types (TOML, PRD formats) share the same validation pattern
3. Verbosity flags (quiet, verbose, json) all test output filtering and can be consolidated
4. Completion generation for bash/zsh follows the same pattern

**Consolidated Properties:**

- Combine individual stat calculations into comprehensive statistical correctness
- Combine format-specific validation into general validation property
- Combine verbosity tests into output control property
- Keep other properties separate as they test distinct behaviors

### Correctness Properties

Based on the prework analysis, here are the testable correctness properties:

**Property 1: Configuration Validation Correctness**
*For any* configuration file (TOML, JSON, YAML), validation should correctly identify all syntax errors and schema violations, and invalid configurations should be rejected while valid ones are accepted.
**Validates: US-1.1, US-1.2 (Diagnostics criteria 1, 2)**

**Property 2: Diagnostic Exit Code Mapping**
*For any* set of diagnostic check results, the exit code should be 0 if all checks pass, and 2 if any check fails.
**Validates: General criteria (Diagnostics criteria 6)**

**Property 3: Gate Command Execution Fidelity**
*For any* gate command, testing it individually should produce the same result (exit code, output) as running it in the normal loop context.
**Validates: US-1.3 (Diagnostics criteria 3)**

**Property 4: Suggestion Completeness**
*For any* detected diagnostic issue, there should be at least one actionable suggestion for fixing it.
**Validates: General criteria 4 (Diagnostics criteria 5)**

**Property 5: Statistical Calculation Correctness**
*For any* set of iteration history data, calculated statistics (average, min, max, success rate) should be mathematically correct according to standard statistical formulas.
**Validates: US-2.1 (Stats criteria 2, 3, 4)**

**Property 6: Duration Tracking Persistence**
*For any* completed iteration, the state.json file should contain a duration_seconds field with a non-negative value.
**Validates: US-2.1 (Stats criteria 1)**

**Property 7: CSV Export Round-Trip**
*For any* statistics data, exporting to CSV then parsing the CSV should preserve all numeric values within floating-point precision.
**Validates: US-2.3 (Stats criteria 5)**

**Property 8: Dry-Run Safety**
*For any* dry-run execution, no agent processes should be spawned and no files outside .ralph/ should be modified.
**Validates: US-3.1 (Dry-run criteria 5)**

**Property 9: Dry-Run Prediction Accuracy**
*For any* project state, the tasks and gates shown in dry-run mode should match what would be selected in a real run with the same state.
**Validates: US-3.1, US-3.2 (Dry-run criteria 2, 3)**

**Property 10: Task Filtering Correctness**
*For any* task list with blocked tasks, enabling the blocked filter should exclude all tasks with unmet dependencies or blocked status.
**Validates: US-4.3 (Interactive criteria 3)**

**Property 11: Search Filter Accuracy**
*For any* search term and task list, filtered results should only include tasks where the search term appears in the task ID, title, or acceptance criteria.
**Validates: US-4.1, US-4.2 (Interactive criteria 5)**

**Property 12: Dependency Satisfaction**
*For any* task with dependencies, it should only be selectable when all tasks in its depends_on list are marked complete.
**Validates: US-5.1 (Dependencies criteria 2)**

**Property 13: Circular Dependency Detection**
*For any* dependency graph, circular dependencies should be detected if and only if there exists a cycle in the directed graph.
**Validates: US-5.3 (Dependencies criteria 4)**

**Property 14: Dependency Format Consistency**
*For any* dependency specification, parsing it from JSON, Markdown, or YAML format should produce equivalent dependency relationships.
**Validates: US-5.1 (Dependencies criteria 5)**

**Property 15: Backward Compatibility**
*For any* task without a depends_on field, it should be treated as having no dependencies (always ready when not blocked by other criteria).
**Validates: General criteria 1 (Dependencies criteria 6)**

**Property 16: Snapshot Round-Trip**
*For any* clean working tree state, creating a snapshot then immediately rolling back should restore the exact same git state and Ralph state.
**Validates: US-6.1, US-6.2 (Snapshot criteria 4)**

**Property 17: Dirty Tree Protection**
*For any* working tree with uncommitted changes, rollback operations should be rejected with a clear error message.
**Validates: US-6.2 (Snapshot criteria 5)**

**Property 18: Snapshot Retention**
*For any* snapshot list exceeding the configured retention limit, cleanup should remove the oldest snapshots while preserving the most recent N snapshots.
**Validates: US-6.3 (Snapshot criteria 6)**

**Property 19: Watch Debouncing**
*For any* sequence of file changes within the debounce window, only one gate execution should be triggered after the window expires.
**Validates: US-7.1 (Watch criteria 3)**

**Property 20: Watch Pattern Matching**
*For any* file change, the watch callback should be triggered if and only if the file path matches at least one configured watch pattern.
**Validates: US-7.3 (Watch criteria 1)**

**Property 21: Progress Bar Accuracy**
*For any* completion ratio (completed/total), the progress bar should visually represent the percentage with correct proportions.
**Validates: US-8.1 (Progress criteria 1)**

**Property 22: Velocity Calculation**
*For any* history of task completions with timestamps, velocity (tasks/day) should be calculated as total_completed / days_elapsed.
**Validates: US-8.2 (Progress criteria 2)**

**Property 23: ETA Calculation**
*For any* current progress and velocity, ETA should be calculated as remaining_tasks / velocity (in days from now).
**Validates: US-8.2 (Progress criteria 3)**

**Property 24: Environment Variable Expansion**
*For any* environment variable VAR with value V, the string "${VAR}" in configuration should be replaced with V.
**Validates: US-9.1 (Env vars criteria 1)**

**Property 25: Default Value Substitution**
*For any* undefined environment variable VAR, the string "${VAR:-default}" should be replaced with "default".
**Validates: US-9.2 (Env vars criteria 2)**

**Property 26: Required Variable Validation**
*For any* configuration containing "${VAR}" (without default) where VAR is not set, validation should report VAR as a missing required variable.
**Validates: US-9.3 (Env vars criteria 3)**

**Property 27: Shell Injection Prevention**
*For any* configuration value containing shell metacharacters, environment variable expansion should not execute shell commands.
**Validates: General criteria 4 (Env vars criteria 5)**

**Property 28: Template Variable Substitution**
*For any* template with variables and provided values, all occurrences of {variable} in the template should be replaced with the corresponding value.
**Validates: US-10.1 (Templates criteria 3)**

**Property 29: Template Format Validation**
*For any* template file, validation should accept valid JSON templates and reject malformed ones with clear error messages.
**Validates: US-10.2 (Templates criteria 5)**

**Property 30: Tracker Format Compatibility**
*For any* task created from a template, it should be correctly formatted for the active tracker type (JSON/Markdown/YAML).
**Validates: US-10.1 (Templates criteria 6)**

**Property 31: Quiet Mode Output Suppression**
*For any* command executed with --quiet flag, output should only include errors and final summary (no progress indicators or verbose logs).
**Validates: US-11.1 (Quiet mode criteria 1)**

**Property 32: JSON Output Validity**
*For any* command executed with --format json, the output should be valid JSON that can be parsed without errors.
**Validates: Quiet mode criteria 3**

**Property 33: Error Preservation**
*For any* error condition, error messages should be displayed regardless of verbosity level (quiet, normal, or verbose).
**Validates: Quiet mode criteria 5**

**Property 34: Completion Script Validity**
*For any* generated completion script (bash or zsh), it should be syntactically valid for the target shell.
**Validates: Completion criteria 1, 2**

**Property 35: Dynamic Completion Accuracy**
*For any* completion context requiring dynamic values (agents, templates, snapshots), the completion suggestions should match the currently available values from configuration or state.
**Validates: Completion criteria 5**

## Error Handling

### Error Categories

**1. Configuration Errors**

- Invalid TOML syntax → Show line number and syntax error
- Missing required fields → List missing fields with examples
- Invalid field values → Show expected type/format
- Missing environment variables → List undefined variables

**2. File System Errors**

- Missing .ralph directory → Suggest `ralph init`
- Permission denied → Show path and suggest chmod/chown
- Disk full → Clear error message with cleanup suggestions
- File not found → Show expected path

**3. Git Errors**

- Not a git repository → Suggest `git init`
- Dirty working tree (when required clean) → Show `git status` summary
- Merge conflicts → Suggest resolving conflicts first
- Detached HEAD → Warn and suggest checking out branch

**4. Validation Errors**

- Invalid PRD format → Show format errors with line numbers
- Circular dependencies → Show cycle path
- Invalid template → Show schema validation errors
- Malformed JSON/YAML → Show parsing error with context

**5. Runtime Errors**

- Gate command failed → Show command, exit code, and output
- Agent timeout → Show timeout duration and suggest increasing
- Rate limit exceeded → Show wait time
- Network errors → Suggest retry with backoff

### Error Handling Patterns

**Graceful Degradation:**

```python
def load_stats_cache(state: Dict) -> Optional[StatsCache]:
    """Load stats cache, return None if invalid."""
    try:
        cache_data = state.get("stats_cache", {})
        return StatsCache(**cache_data)
    except Exception as e:
        # Log warning but don't fail
        logger.warning(f"Invalid stats cache, will recalculate: {e}")
        return None
```

**Clear Error Messages:**

```python
def validate_snapshot_name(name: str) -> None:
    """Validate snapshot name format."""
    if not name:
        raise ValueError("Snapshot name cannot be empty")
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        raise ValueError(
            f"Invalid snapshot name '{name}'. "
            "Use only letters, numbers, hyphens, and underscores."
        )
```

**Actionable Suggestions:**

```python
def check_git_repo(project_root: Path) -> DiagnosticResult:
    """Check if project is a git repository."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=project_root,
            check=True,
            capture_output=True
        )
        return DiagnosticResult(
            check_name="git_repository",
            passed=True,
            message="Project is a git repository",
            suggestions=[],
            severity="info"
        )
    except subprocess.CalledProcessError:
        return DiagnosticResult(
            check_name="git_repository",
            passed=False,
            message="Project is not a git repository",
            suggestions=[
                "Run 'git init' to initialize a repository",
                "Ralph requires git for version control and snapshots"
            ],
            severity="error"
        )
```

### Exit Codes

Consistent exit codes across all commands:

- **0**: Success
- **1**: General error (unexpected exception)
- **2**: Validation error (config, PRD, dependencies)
- **3**: Gate failure
- **4**: User cancellation (Ctrl+C in interactive mode)
- **130**: SIGINT (Ctrl+C in watch mode)

## Testing Strategy

### Dual Testing Approach

All features require both unit tests and property-based tests:

**Unit Tests:**

- Specific examples demonstrating correct behavior
- Edge cases (empty lists, missing files, etc.)
- Error conditions (invalid input, permission errors)
- Integration points between modules

**Property-Based Tests:**

- Universal properties across all inputs
- Randomized input generation
- Minimum 100 iterations per property test
- Each test tagged with property number from design

### Testing Framework

**Property-Based Testing Library:**

- **Framework:** `hypothesis` (Python property-based testing library)
- **Configuration:** `@given(st.text(), st.integers(), etc.)`
- **Settings:** `@settings(max_examples=100)` minimum
- **Annotation Format:** All property tests must include a comment linking to the requirement:
  - Format: `# **Validates: Requirements X.Y**` or in docstring
  - Example: `# **Validates: Requirements 1.1, 1.2**`

**Test Organization:**

```
tests/
├── test_diagnostics.py       # Unit + property tests
├── test_stats.py              # Unit + property tests
├── test_interactive.py        # Unit + property tests
├── test_dependencies.py       # Unit + property tests
├── test_snapshots.py          # Unit + property tests
├── test_watch.py              # Unit + property tests
├── test_progress.py           # Unit + property tests
├── test_envvars.py            # Unit + property tests
├── test_templates.py          # Unit + property tests
├── test_completion.py         # Unit + property tests
└── test_integration.py        # End-to-end tests
```

### Property Test Examples

**Example 1: Statistical Correctness (Property 5)**

```python
from hypothesis import given, strategies as st
import statistics

@given(st.lists(st.floats(min_value=0, max_value=10000), min_size=1))
@settings(max_examples=100)
def test_stats_calculation_correctness(durations: List[float]):
    """
    **Validates: Requirements 2.1, 2.2**
    
    Feature: ralph-enhancement-phase2, Property 5
    For any set of iteration durations, calculated statistics should match
    standard statistical formulas.
    """
    # Create mock history
    history = [
        {"duration_seconds": d, "success": True}
        for d in durations
    ]
    
    # Calculate stats
    stats = calculate_stats({"history": history})
    
    # Verify correctness
    assert stats.avg_duration_seconds == statistics.mean(durations)
    assert stats.min_duration_seconds == min(durations)
    assert stats.max_duration_seconds == max(durations)
```

**Example 2: Environment Variable Expansion (Property 24)**

```python
from hypothesis import given, strategies as st

@given(
    st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll')), min_size=1),
    st.text(min_size=0)
)
@settings(max_examples=100)
def test_env_var_expansion(var_name: str, var_value: str):
    """
    **Validates: Requirements 9.1**
    
    Feature: ralph-enhancement-phase2, Property 24
    For any environment variable with a value, ${VAR} should be replaced
    with the value.
    """
    # Set environment variable
    os.environ[var_name] = var_value
    
    try:
        # Test expansion
        config_str = f"test = \"${{{var_name}}}\""
        result = expand_env_vars(config_str)
        
        assert result == f'test = "{var_value}"'
    finally:
        # Cleanup
        del os.environ[var_name]
```

**Example 3: Circular Dependency Detection (Property 13)**

```python
from hypothesis import given, strategies as st

@given(st.integers(min_value=3, max_value=10))
@settings(max_examples=100)
def test_circular_dependency_detection(cycle_length: int):
    """
    **Validates: Requirements 5.3**
    
    Feature: ralph-enhancement-phase2, Property 13
    For any dependency graph with a cycle, circular dependencies should
    be detected.
    """
    # Create a cycle: task-0 -> task-1 -> ... -> task-N -> task-0
    tasks = []
    for i in range(cycle_length):
        next_task = (i + 1) % cycle_length
        tasks.append({
            "id": f"task-{i}",
            "depends_on": [f"task-{next_task}"]
        })
    
    # Build graph
    graph = build_dependency_graph(tasks)
    
    # Detect cycles
    cycles = detect_circular_dependencies(graph)
    
    # Should find at least one cycle
    assert len(cycles) > 0
    # Cycle should involve all tasks
    assert len(cycles[0]) == cycle_length
```

### Unit Test Examples

**Example 1: Snapshot Creation**

```python
def test_create_snapshot_creates_git_stash(tmp_path: Path):
    """Test that snapshot creates a git stash."""
    # Setup git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path)
    
    # Create a file and commit
    (tmp_path / "test.txt").write_text("content")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True)
    
    # Create snapshot
    snapshot = create_snapshot(tmp_path, "test-snapshot", "Test description")
    
    # Verify stash was created
    result = subprocess.run(
        ["git", "stash", "list"],
        cwd=tmp_path,
        capture_output=True,
        text=True
    )
    assert "ralph-snapshot: test-snapshot" in result.stdout
    assert snapshot.name == "test-snapshot"
```

**Example 2: Dry-Run Safety**

```python
def test_dry_run_does_not_execute_agents(tmp_path: Path, monkeypatch):
    """Test that dry-run mode doesn't execute agents."""
    # Track subprocess calls
    calls = []
    original_run = subprocess.run
    
    def mock_run(*args, **kwargs):
        calls.append(args[0])
        return original_run(*args, **kwargs)
    
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Run dry-run
    result = dry_run_loop(tmp_path, config, max_iterations=5)
    
    # Verify no agent processes were spawned
    agent_calls = [c for c in calls if "codex" in str(c) or "claude" in str(c)]
    assert len(agent_calls) == 0
```

**Example 3: Template Variable Substitution**

```python
def test_template_variable_substitution():
    """Test that template variables are correctly substituted."""
    template = TaskTemplate(
        name="test",
        description="Test template",
        title_template="Fix: {title} in {component}",
        acceptance_criteria=["Test {component}"],
        priority="high",
        variables=["title", "component"]
    )
    
    variables = {
        "title": "Login bug",
        "component": "Auth module"
    }
    
    # Create task (mock tracker)
    mock_tracker = MockTracker()
    task_id = create_task_from_template(template, variables, mock_tracker)
    
    # Verify substitution
    task = mock_tracker.get_task(task_id)
    assert task["title"] == "Fix: Login bug in Auth module"
    assert "Test Auth module" in task["acceptance_criteria"]
```

### Integration Tests

**End-to-End Workflow Tests:**

```python
def test_full_workflow_with_dependencies(tmp_path: Path):
    """Test complete workflow with task dependencies."""
    # Initialize project
    init_project(tmp_path)
    
    # Create PRD with dependencies
    prd = {
        "tasks": [
            {"id": "task-1", "title": "Foundation", "depends_on": []},
            {"id": "task-2", "title": "Feature", "depends_on": ["task-1"]},
            {"id": "task-3", "title": "Tests", "depends_on": ["task-2"]}
        ]
    }
    (tmp_path / ".ralph" / "prd.json").write_text(json.dumps(prd))
    
    # Run diagnostics
    results, exit_code = run_diagnostics(tmp_path)
    assert exit_code == 0
    
    # Check task selection respects dependencies
    tracker = make_tracker(tmp_path, config)
    ready_tasks = get_ready_tasks_with_dependencies(tracker, set())
    assert len(ready_tasks) == 1
    assert ready_tasks[0].id == "task-1"
    
    # Mark task-1 complete
    tracker.mark_complete("task-1")
    ready_tasks = get_ready_tasks_with_dependencies(tracker, {"task-1"})
    assert len(ready_tasks) == 1
    assert ready_tasks[0].id == "task-2"
```

### Coverage Requirements

- **Target:** >95% coverage for all new code
- **Measurement:** Use `pytest-cov`
- **Command:** `uv run pytest --cov=ralph_gold --cov-report=term-missing`
- **Exclusions:** Only exclude truly untestable code (e.g., `if __name__ == "__main__"`)

### Test Execution

**Local Development:**

```bash
# Run all tests
uv run pytest -q

# Run specific feature tests
uv run pytest tests/test_diagnostics.py -v

# Run with coverage
uv run pytest --cov=ralph_gold --cov-report=html

# Run only property tests
uv run pytest -k "property" -v
```

**CI/CD:**

- Run full test suite on every PR
- Require >95% coverage
- Run property tests with increased iterations (500+)
- Test on multiple Python versions (3.11, 3.12)

## Implementation Notes

### Performance Considerations

**1. Stats Calculation Caching:**

- Cache calculated stats in `state.json`
- Invalidate cache on new iterations
- Lazy recalculation only when requested

**2. Watch Mode Efficiency:**

- Use OS-native file watching (inotify, FSEvents)
- Debounce to avoid excessive gate runs
- Efficient pattern matching

**3. Dependency Graph:**

- Build graph once, reuse for multiple queries
- O(V + E) algorithms for traversal
- Cache ready tasks between iterations

**4. Progress Visualization:**

- Limit history analysis to recent data
- Pre-calculate velocity periodically
- Efficient ASCII rendering

### Backward Compatibility

**State Migration:**

```python
def migrate_state_schema(state: Dict) -> Dict:
    """Migrate old state.json to new schema."""
    # Add new fields with defaults
    if "snapshots" not in state:
        state["snapshots"] = []
    
    if "stats_cache" not in state:
        state["stats_cache"] = {}
    
    # Migrate history entries
    for entry in state.get("history", []):
        if "duration_seconds" not in entry:
            entry["duration_seconds"] = 0.0
        if "attempt_number" not in entry:
            entry["attempt_number"] = 1
    
    return state
```

**Configuration Defaults:**

- All new config sections have sensible defaults
- Missing sections don't cause errors
- Gradual adoption of new features

### Security Considerations

**1. Environment Variable Expansion:**

- No shell execution
- Validate variable names (alphanumeric + underscore only)
- Prevent injection attacks

**2. Watch Mode:**

- Respect `.gitignore` patterns
- Don't watch sensitive directories
- Rate limit gate executions

**3. Snapshot/Rollback:**

- Verify git stash integrity
- Prevent rollback to untrusted snapshots
- Validate state.json before restore

**4. Template Loading:**

- Validate template JSON schema
- Sanitize user input in variables
- Prevent path traversal in custom templates

### Dependencies

**No New External Dependencies:**

- Use Python stdlib where possible
- `watchdog` for watch mode (optional, fallback to polling)
- `hypothesis` for property testing (dev dependency)

**Stdlib Modules Used:**

- `argparse`: CLI parsing
- `json`, `tomllib`: Configuration
- `subprocess`: Git and gate commands
- `pathlib`: File operations
- `re`: Pattern matching
- `statistics`: Stats calculations
- `csv`: CSV export
- `os`, `sys`: Environment and system

## Migration Guide

### For Users

**Upgrading from Phase 1:**

1. No breaking changes - all existing functionality preserved
2. New commands available immediately after upgrade
3. Optional: Configure new features in `ralph.toml`
4. State.json automatically migrated on first run

**Enabling New Features:**

```toml
# Add to ralph.toml to enable new features

[diagnostics]
enabled = true

[watch]
enabled = false  # Opt-in for watch mode
patterns = ["**/*.py"]

[progress]
show_velocity = true
```

### For Developers

**Adding New Diagnostic Checks:**

```python
def check_custom_rule(project_root: Path) -> DiagnosticResult:
    """Add custom diagnostic check."""
    # Implement check logic
    return DiagnosticResult(...)

# Register in diagnostics.py
DIAGNOSTIC_CHECKS = [
    validate_config,
    validate_prd,
    check_custom_rule,  # Add here
]
```

**Adding New Templates:**

```python
# Create .ralph/templates/my-template.json
{
  "name": "my-template",
  "description": "Custom template",
  "title_template": "Custom: {title}",
  "acceptance_criteria": ["Criterion 1"],
  "priority": "medium",
  "variables": ["title"]
}
```

## Future Enhancements

**Phase 3 Possibilities:**

- Cost tracking and budgeting
- Multi-agent orchestration
- Advanced analytics dashboard
- Cloud state synchronization
- Team collaboration features
- Plugin system for extensions

**Extensibility Points:**

- Diagnostic check registry
- Template system
- Output formatters
- Tracker backends
- Gate types

---

**Document Version:** 1.0  
**Last Updated:** 2024  
**Status:** Ready for Implementation
