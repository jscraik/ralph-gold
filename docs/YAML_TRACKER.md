---
last_validated: 2026-02-28
---

# YAML Tracker

The YAML tracker provides a structured, machine-editable task format with native support for parallel execution grouping.

## Overview

YAML tracker is one of the built-in task trackers in ralph-gold. It offers:

- **Human-readable format**: Easy to read and edit in any text editor
- **Structured data**: Consistent schema with validation
- **Parallel grouping**: First-class support for organizing tasks into parallel execution groups
- **Comments**: YAML supports comments for documentation
- **Type safety**: Schema validation catches errors early

## When to Use YAML Tracker

Use YAML tracker when you:

- Want structured task data with validation
- Need parallel execution grouping
- Prefer explicit schema over freeform markdown
- Want to programmatically generate or manipulate tasks
- Need to track additional metadata per task

Use Markdown tracker when you:

- Prefer simple checkbox lists
- Don't need parallel execution
- Want minimal structure

## File Format

### Basic Structure

```yaml
version: 1
metadata:
  project: my-project
  created: 2024-01-15
  branch: ralph/my-feature

tasks:
  - id: 1
    title: Task title
    description: Optional detailed description
    group: default
    priority: 1
    completed: false
    acceptance:
      - Acceptance criterion 1
      - Acceptance criterion 2
```

### Required Fields

#### Root Level

- `version` (integer): Schema version, must be `1`
- `tasks` (array): List of task objects

#### Task Level

- `id` (string or integer): Unique task identifier
- `title` (string): Short task description

### Optional Fields

#### Root Level

- `metadata` (object): Project metadata
  - `project` (string): Project name
  - `created` (string): Creation date
  - `branch` (string): Git branch name for this task set
  - Any other custom fields

#### Task Level

- `description` (string): Detailed task description
- `group` (string): Parallel execution group (default: "default")
- `priority` (integer): Task priority for sorting
- `completed` (boolean): Completion status (default: false)
- `blocked` (boolean): Marks a task as blocked (treated as done for loop exit)
- `blocked_reason` (string): Optional reason for block
- `acceptance` (array of strings): Acceptance criteria

## Schema Validation

The YAML tracker validates files on load:

### Valid Example

```yaml
version: 1
metadata:
  project: user-auth
  
tasks:
  - id: 1
    title: Implement login endpoint
    completed: false
```

### Invalid Examples

**Missing version:**

```yaml
tasks:
  - id: 1
    title: Task
```

Error: `Unsupported YAML version: None (expected 1)`

**Missing tasks:**

```yaml
version: 1
metadata:
  project: test
```

Error: `YAML must have 'tasks' field`

**Tasks not a list:**

```yaml
version: 1
tasks:
  task1: "Do something"
```

Error: `YAML 'tasks' field must be a list`

**Missing required task fields:**

```yaml
version: 1
tasks:
  - title: Task without ID
```

Error: `Task at index 0 missing required 'id' field`

## Parallel Execution Groups

Tasks can be organized into groups for parallel execution. Tasks in the same group run sequentially, while tasks in different groups can run in parallel.

### Group Field

```yaml
version: 1
tasks:
  - id: 1
    title: Implement authentication API
    group: backend
    completed: false
    
  - id: 2
    title: Create login UI component
    group: frontend
    completed: false
    
  - id: 3
    title: Add authentication tests
    group: backend
    completed: false
```

In this example:

- Tasks 1 and 3 are in the `backend` group (run sequentially)
- Task 2 is in the `frontend` group (can run in parallel with backend tasks)

### Default Group

Tasks without a `group` field default to the `"default"` group:

```yaml
version: 1
tasks:
  - id: 1
    title: Sequential task 1
    completed: false
    
  - id: 2
    title: Sequential task 2
    completed: false
```

Both tasks are in the `"default"` group and run sequentially.

### Group Naming Conventions

Common group names:

- `backend` - Backend/API tasks
- `frontend` - UI/frontend tasks
- `database` - Database schema/migration tasks
- `testing` - Test implementation tasks
- `docs` - Documentation tasks
- `infra` - Infrastructure/deployment tasks

Use descriptive names that reflect the area of the codebase being modified.

## Usage Examples

### Basic Task List

```yaml
version: 1
metadata:
  project: todo-app
  created: 2024-01-15

tasks:
  - id: 1
    title: Create database schema
    description: Design and implement the initial database schema
    priority: 1
    completed: false
    acceptance:
      - Schema includes users, tasks, and tags tables
      - Foreign keys properly defined
      - Indexes on frequently queried columns
      
  - id: 2
    title: Implement CRUD API
    description: REST API for task management
    priority: 2
    completed: false
    acceptance:
      - GET /tasks returns all tasks
      - POST /tasks creates a new task
      - PUT /tasks/:id updates a task
      - DELETE /tasks/:id deletes a task
      
  - id: 3
    title: Add authentication
    priority: 3
    completed: false
    acceptance:
      - Users can register
      - Users can login
      - JWT tokens issued on login
```

### Parallel Execution Example

```yaml
version: 1
metadata:
  project: e-commerce
  branch: ralph/v2-features

tasks:
  # Backend group - runs sequentially
  - id: 1
    title: Add product search API
    group: backend
    priority: 1
    completed: false
    acceptance:
      - Search by product name
      - Filter by category
      - Pagination support
      
  - id: 2
    title: Add shopping cart API
    group: backend
    priority: 2
    completed: false
    acceptance:
      - Add items to cart
      - Update quantities
      - Calculate totals
      
  # Frontend group - runs in parallel with backend
  - id: 3
    title: Create product search UI
    group: frontend
    priority: 1
    completed: false
    acceptance:
      - Search input with autocomplete
      - Category filters
      - Results grid with pagination
      
  - id: 4
    title: Create shopping cart UI
    group: frontend
    priority: 2
    completed: false
    acceptance:
      - Cart icon with item count
      - Cart drawer with item list
      - Quantity controls
      
  # Testing group - runs in parallel with both
  - id: 5
    title: Add integration tests
    group: testing
    priority: 1
    completed: false
    acceptance:
      - Test search functionality
      - Test cart operations
      - Test checkout flow
```

With parallel execution enabled, this would run:

- Backend tasks 1 and 2 sequentially
- Frontend tasks 3 and 4 sequentially
- Testing task 5 independently
- All three groups in parallel (3x speedup potential)

## Configuration

### Enable YAML Tracker

In `.ralph/ralph.toml`:

```toml
[files]
prd = "tasks.yaml"

[tracker]
kind = "yaml"  # or "auto" to detect from file extension
```

### Initialize with YAML

```bash
ralph init --format yaml
```

This creates a `tasks.yaml` template in your project root.

## Migration from Other Formats

### From JSON

```bash
ralph convert .ralph/prd.json tasks.yaml
```

### From Markdown

```bash
ralph convert .ralph/PRD.md tasks.yaml
```

### With Group Inference

```bash
ralph convert .ralph/prd.json tasks.yaml --infer-groups
```

The `--infer-groups` flag attempts to infer parallel groups from task titles:

- Tasks starting with "API:", "Backend:" → `backend` group
- Tasks starting with "UI:", "Frontend:" → `frontend` group
- Tasks mentioning "database", "schema" → `database` group
- Tasks mentioning "test" → `testing` group
- Others → `default` group

## Tracker Interface

The YAML tracker implements the standard tracker interface:

```python
from ralph_gold.trackers.yaml_tracker import YamlTracker

tracker = YamlTracker(prd_path=Path("tasks.yaml"))

# Get next task
task = tracker.claim_next_task()
if task:
    print(f"Task {task.id}: {task.title}")

# Check completion status
done, total = tracker.counts()
print(f"Progress: {done}/{total}")

# Check if all done
if tracker.all_done():
    print("All tasks complete!")

# Get parallel groups
groups = tracker.get_parallel_groups()
for group_name, tasks in groups.items():
    print(f"Group {group_name}: {len(tasks)} tasks")
```

## Best Practices

### Task Granularity

Keep tasks small and focused:

```yaml
# Good - specific, testable
- id: 1
  title: Add email validation to signup form
  acceptance:
    - Email format validated
    - Error message shown for invalid emails
    - Tests pass

# Too broad
- id: 1
  title: Implement user management
  # This should be multiple tasks
```

### Acceptance Criteria

Write clear, verifiable acceptance criteria:

```yaml
# Good - specific and testable
acceptance:
  - API returns 200 status code
  - Response includes user ID and email
  - Invalid requests return 400 with error message
  - Tests achieve 90%+ coverage

# Too vague
acceptance:
  - API works correctly
  - Tests pass
```

### Group Organization

Group tasks by area of change, not by type:

```yaml
# Good - grouped by feature area
- id: 1
  title: Add user profile API endpoint
  group: user-profile
  
- id: 2
  title: Add user profile UI page
  group: user-profile

# Less ideal - grouped by layer
- id: 1
  title: Add user profile API endpoint
  group: backend
  
- id: 2
  title: Add user profile UI page
  group: frontend
```

Grouping by feature area ensures related changes happen together, reducing merge conflicts.

### Metadata Usage

Use metadata for project-level information:

```yaml
version: 1
metadata:
  project: my-app
  created: 2024-01-15
  branch: ralph/feature-x
  author: team-name
  sprint: 2024-Q1-S3
  
tasks:
  # ...
```

## Troubleshooting

### YAML Syntax Errors

**Problem:** `Invalid YAML syntax: ...`

**Solution:** Check for:

- Proper indentation (use spaces, not tabs)
- Quoted strings with special characters
- Balanced brackets and quotes

Use a YAML validator or linter to check syntax.

### Schema Validation Errors

**Problem:** `Task at index N missing required 'id' field`

**Solution:** Ensure every task has both `id` and `title` fields.

### File Not Found

**Problem:** `YAML file not found: tasks.yaml`

**Solution:**

- Check the file path in `.ralph/ralph.toml`
- Ensure the file exists
- Use `ralph init --format yaml` to create a template

### Parallel Groups Not Working

**Problem:** Tasks run sequentially even with different groups

**Solution:**

- Ensure parallel execution is enabled in config
- Use `ralph run --parallel` flag
- Check that tasks have different `group` values

## See Also

- [Parallel Execution Guide](PARALLEL_EXECUTION.md) - Using parallel execution with YAML tracker
- [Configuration Reference](../README.md#configuration) - Ralph configuration options
- [Tracker Plugins](../README.md#tracker-plugins) - Other tracker formats
