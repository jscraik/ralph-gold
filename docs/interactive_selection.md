---
last_validated: 2026-02-28
---

# Interactive Task Selection

The interactive task selection module allows users to manually choose which task to work on from a list of available tasks.

## Features

- **Numbered List Display**: Shows all available tasks with IDs, titles, and priorities
- **Blocked Task Filtering**: Filters out blocked tasks by default (can be shown with flag)
- **Search/Filter**: Search tasks by keyword in ID, title, or acceptance criteria
- **Task Details**: View full acceptance criteria for any task
- **Automatic Selection**: If only one task is available, it's automatically selected
- **User-Friendly Commands**: Simple command interface (number to select, s to search, q to quit)

## Usage

### Basic Interactive Selection

```python
from ralph_gold.interactive import (
    TaskChoice,
    select_task_interactive,
    convert_selected_task_to_choice
)
from ralph_gold.trackers import make_tracker

# Get tasks from tracker
tracker = make_tracker(project_root, cfg)
all_tasks = []  # Collect tasks from tracker

# Convert to TaskChoice format
task_choices = [
    convert_selected_task_to_choice(task)
    for task in all_tasks
]

# Let user select interactively
selected = select_task_interactive(task_choices)

if selected:
    print(f"User selected: {selected.task_id}")
else:
    print("User cancelled selection")
```

### CLI Integration (Future)

The interactive mode will be integrated into the CLI with an `--interactive` flag:

```bash
# Interactive task selection for single step
ralph step --interactive

# Interactive mode for loop (select task each iteration)
ralph run --interactive --max-iterations 5
```

## API Reference

### TaskChoice

Dataclass representing a task available for selection.

**Attributes:**

- `task_id` (str): Unique identifier for the task
- `title` (str): Human-readable task title
- `priority` (str): Task priority (high, medium, low, etc.)
- `status` (str): Current task status
- `blocked` (bool): Whether the task is blocked
- `acceptance_criteria` (List[str]): List of acceptance criteria

### select_task_interactive()

Display interactive task selector and return user choice.

**Parameters:**

- `tasks` (List[TaskChoice]): List of available tasks
- `show_blocked` (bool): Whether to show blocked tasks (default: False)

**Returns:**

- `Optional[TaskChoice]`: Selected task, or None if cancelled

**Commands:**

- `<number>`: Select task by number
- `s <text>`: Search/filter tasks by keyword
- `c`: Clear search filter
- `d <num>`: Show details for task number
- `q`: Quit/cancel selection

### format_task_list()

Format tasks as a numbered list with details.

**Parameters:**

- `tasks` (List[TaskChoice]): List of tasks to format
- `show_blocked` (bool): Whether to include blocked tasks (default: False)
- `show_criteria` (bool): Whether to show acceptance criteria (default: False)

**Returns:**

- `str`: Formatted string representation of the task list

### filter_tasks_by_keyword()

Filter tasks by keyword search (case-insensitive).

**Parameters:**

- `tasks` (List[TaskChoice]): List of tasks to filter
- `keyword` (str): Search keyword

**Returns:**

- `List[TaskChoice]`: Filtered list of tasks matching the keyword

### convert_selected_task_to_choice()

Convert a SelectedTask to a TaskChoice for interactive selection.

**Parameters:**

- `task` (SelectedTask): The SelectedTask to convert
- `priority` (str): Task priority (default: "medium")
- `status` (str): Task status (default: "ready")
- `blocked` (bool): Whether task is blocked (default: False)

**Returns:**

- `TaskChoice`: TaskChoice instance

## Example Session

```
Available tasks:

1. task-1: Implement login feature [HIGH]
2. task-2: Add unit tests for authentication [MEDIUM]
3. task-4: Update documentation [LOW]

Commands:
  <number>  - Select task by number
  s <text>  - Search/filter tasks
  c         - Clear search filter
  d <num>   - Show details for task number
  q         - Quit/cancel

Select task (or command): d 1

============================================================
Task: task-1
Title: Implement login feature
Priority: high
Status: ready
Blocked: No

Acceptance Criteria:
  1. User can log in with email and password
  2. Invalid credentials show error message
  3. Successful login redirects to dashboard
============================================================

Press Enter to continue...

Select task (or command): 1

Selected: task-1: Implement login feature
```

## Design Decisions

### Simple Text-Based UI

The implementation uses a simple text-based interface rather than a full TUI (like `curses`) to:

- Avoid external dependencies
- Work in all terminal environments
- Keep the codebase simple and maintainable
- Ensure compatibility with CI/CD environments

### Automatic Selection for Single Task

When only one task is available, it's automatically selected to avoid unnecessary user interaction. This makes the tool more efficient for common cases.

### Blocked Task Filtering

Blocked tasks are filtered by default to reduce clutter and help users focus on actionable work. Users can still view blocked tasks with the `--show-blocked` flag if needed.

### Search in Multiple Fields

The search functionality looks in task IDs, titles, and acceptance criteria to provide comprehensive filtering. This helps users quickly find relevant tasks in large task lists.

## Testing

The module includes comprehensive unit tests covering:

- Task list formatting with various options
- Keyword filtering (case-insensitive, multiple fields)
- Interactive selection with all commands
- Edge cases (empty lists, single task, blocked tasks)
- Error handling (invalid input, keyboard interrupt)

Run tests with:

```bash
uv run pytest tests/test_interactive.py -v
```

## Future Enhancements

Potential improvements for future versions:

- Color-coded priorities (using ANSI colors)
- Task grouping by priority or status
- Multi-select mode for batch operations
- Integration with task dependencies (show dependency tree)
- Persistent search history
- Configurable display format
