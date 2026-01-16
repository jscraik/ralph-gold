# YAML Tracker - Requirements

## Overview

Add YAML as a task tracker format, providing a machine-editable, human-friendly middle ground between Markdown and JSON, with first-class support for parallel grouping.

## User Stories

### 1. As a developer, I want to use YAML for task tracking

**So that** I get structured data that's easier to edit than JSON but more machine-friendly than Markdown.

**Acceptance Criteria:**

- Ralph can read tasks from tasks.yaml or TASKS.yaml
- YAML format supports all fields that JSON supports
- YAML format is more readable than JSON
- YAML format supports comments
- YAML format validates on load

### 2. As a developer, I want YAML to support parallel grouping natively

**So that** I can easily declare which tasks can run in parallel.

**Acceptance Criteria:**

- Tasks can have a "group" field
- Tasks without a group run sequentially
- Tasks with the same group run sequentially
- Tasks with different groups can run in parallel
- Groups can be strings or integers

### 3. As a developer, I want YAML to be the recommended format for parallel workflows

**So that** I get the best experience when using parallel execution.

**Acceptance Criteria:**

- ralph init --parallel creates tasks.yaml by default
- Documentation recommends YAML for parallel workflows
- YAML examples show parallel grouping
- Migration tool converts JSON/Markdown to YAML

## YAML Schema

```yaml
# tasks.yaml
version: 1
metadata:
  project: my-project
  created: 2024-01-15
  updated: 2024-01-16

tasks:
  - id: 1
    title: Implement user authentication
    description: Add JWT-based authentication
    group: auth  # parallel group
    priority: 1
    completed: false
    acceptance:
      - User can log in with email/password
      - JWT token is returned on successful login
      - Token expires after 24 hours
    
  - id: 2
    title: Create user profile UI
    description: Build profile page with edit functionality
    group: ui  # different group = can run in parallel with auth
    priority: 2
    completed: false
    acceptance:
      - Profile page displays user info
      - User can edit profile fields
      - Changes are saved to backend
    
  - id: 3
    title: Add password reset flow
    description: Email-based password reset
    group: auth  # same group as task 1 = runs sequentially
    priority: 3
    completed: false
    acceptance:
      - User can request password reset
      - Reset email is sent
      - User can set new password via link
```

## Configuration

```toml
[files]
prd = ".ralph/tasks.yaml"  # or tasks.yaml in root

[tracker]
kind = "yaml"  # or "auto" to detect
```

## CLI Interface

```bash
# Initialize with YAML
ralph init --format yaml

# Convert existing PRD to YAML
ralph convert prd.json tasks.yaml

# Validate YAML
ralph validate tasks.yaml

# Show parallel groups
ralph tasks groups
```

## Tracker Implementation

```python
class YamlTracker(Tracker):
    def __init__(self, project_root: Path, cfg: Config):
        self.path = project_root / cfg.files.prd
        self.data = self._load_yaml()
    
    def _load_yaml(self) -> dict:
        # Load and validate YAML
        # Check version compatibility
        # Return parsed data
        pass
    
    def claim_next_task(self) -> Optional[SelectedTask]:
        # Find first incomplete task
        # Respect group constraints if parallel mode
        pass
    
    def get_parallel_groups(self) -> dict[str, list[SelectedTask]]:
        # Return tasks grouped by group field
        # Tasks without group go in "default" group
        pass
```

## Validation Rules

- `version` must be 1
- `tasks` must be a list
- Each task must have: `id`, `title`, `completed`
- `id` must be unique
- `completed` must be boolean
- `group` must be string or integer (if present)
- `priority` must be integer (if present)
- `acceptance` must be list of strings (if present)

## Migration Tool

```bash
# Convert JSON to YAML
ralph convert .ralph/prd.json tasks.yaml

# Convert Markdown to YAML
ralph convert .ralph/PRD.md tasks.yaml --extract-groups
```

The migration tool should:

- Parse existing format
- Extract all task data
- Infer groups from task titles/descriptions (optional)
- Generate valid YAML
- Preserve comments where possible

## Non-Functional Requirements

### Usability

- YAML should be easier to edit than JSON
- YAML should be easier to parse than Markdown
- YAML should support comments for documentation
- YAML should validate on load with clear error messages

### Compatibility

- YAML tracker should implement same interface as JSON/Markdown
- Existing workflows should work unchanged
- Migration should be lossless

### Performance

- YAML parsing should be < 100ms for 1000 tasks
- YAML writing should be atomic (no partial writes)

## Out of Scope (for v0.7.0)

- YAML schema versioning beyond v1
- YAML includes/references
- YAML anchors/aliases (keep it simple)
- YAML multi-document support

## Dependencies

- PyYAML or ruamel.yaml for parsing
- jsonschema for validation (optional)

## Success Metrics

- YAML format is preferred by 50%+ of users for new projects
- Zero data loss in JSON→YAML→JSON round-trip
- YAML validation catches 100% of schema violations
- Parallel grouping is used in 80%+ of parallel workflows
