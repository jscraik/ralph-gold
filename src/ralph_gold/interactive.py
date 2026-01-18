"""Interactive task selection for Ralph Gold.

This module provides functionality for users to manually select which task
to work on from a list of available tasks. It supports filtering, searching,
and displays task details to help users make informed decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .prd import SelectedTask


@dataclass
class TaskChoice:
    """A task available for selection.

    Attributes:
        task_id: Unique identifier for the task
        title: Human-readable task title
        priority: Task priority (high, medium, low, etc.)
        status: Current task status
        blocked: Whether the task is blocked
        acceptance_criteria: List of acceptance criteria for the task
    """

    task_id: str
    title: str
    priority: str
    status: str
    blocked: bool
    acceptance_criteria: List[str]


def format_task_list(
    tasks: List[TaskChoice], show_blocked: bool = False, show_criteria: bool = False
) -> str:
    """Format tasks as a numbered list with details.

    Args:
        tasks: List of tasks to format
        show_blocked: Whether to include blocked tasks in the output
        show_criteria: Whether to show acceptance criteria

    Returns:
        Formatted string representation of the task list
    """
    if not tasks:
        return "(no tasks available)"

    lines: List[str] = []
    lines.append("Available tasks:")
    lines.append("")

    display_num = 1
    for task in tasks:
        # Skip blocked tasks if not showing them
        if task.blocked and not show_blocked:
            continue

        # Format task line
        blocked_marker = " [BLOCKED]" if task.blocked else ""
        priority_marker = f" [{task.priority.upper()}]" if task.priority else ""

        lines.append(
            f"{display_num}. {task.task_id}: {task.title}{priority_marker}{blocked_marker}"
        )

        # Optionally show acceptance criteria
        if show_criteria and task.acceptance_criteria:
            lines.append("   Acceptance criteria:")
            for criterion in task.acceptance_criteria[:5]:  # Limit to first 5
                lines.append(f"   - {criterion}")
            if len(task.acceptance_criteria) > 5:
                lines.append(f"   ... and {len(task.acceptance_criteria) - 5} more")

        display_num += 1
        lines.append("")

    return "\n".join(lines)


def filter_tasks_by_keyword(tasks: List[TaskChoice], keyword: str) -> List[TaskChoice]:
    """Filter tasks by keyword search.

    Searches in task ID, title, and acceptance criteria.

    Args:
        tasks: List of tasks to filter
        keyword: Search keyword (case-insensitive)

    Returns:
        Filtered list of tasks matching the keyword
    """
    if not keyword or not keyword.strip():
        return tasks

    keyword_lower = keyword.strip().lower()
    filtered: List[TaskChoice] = []

    for task in tasks:
        # Search in task ID
        if keyword_lower in task.task_id.lower():
            filtered.append(task)
            continue

        # Search in title
        if keyword_lower in task.title.lower():
            filtered.append(task)
            continue

        # Search in acceptance criteria
        for criterion in task.acceptance_criteria:
            if keyword_lower in criterion.lower():
                filtered.append(task)
                break

    return filtered


def select_task_interactive(
    tasks: List[TaskChoice], show_blocked: bool = False
) -> Optional[TaskChoice]:
    """Display interactive task selector and return user choice.

    This function presents a numbered list of tasks and prompts the user
    to select one. It supports:
    - Filtering blocked tasks (default)
    - Search/filter by keyword
    - Showing acceptance criteria
    - Automatic selection if only one task available

    Args:
        tasks: List of available tasks
        show_blocked: Whether to show blocked tasks (default: False)

    Returns:
        Selected task, or None if user cancels or no tasks available
    """
    from .output import print_output

    if not tasks:
        print_output("No tasks available for selection.", level="normal")
        return None

    # Filter out blocked tasks unless explicitly requested
    available_tasks = [t for t in tasks if not t.blocked] if not show_blocked else tasks

    if not available_tasks:
        print_output("No unblocked tasks available.", level="normal")
        if not show_blocked and any(t.blocked for t in tasks):
            print_output(
                "(Some tasks are blocked. Use --show-blocked to see them.)",
                level="normal",
            )
        return None

    # Automatic selection if only one task
    if len(available_tasks) == 1:
        task = available_tasks[0]
        print_output(
            f"Only one task available: {task.task_id}: {task.title}", level="normal"
        )
        print_output("Automatically selecting this task.", level="normal")
        return task

    # Interactive selection loop
    current_tasks = available_tasks
    search_keyword = ""

    while True:
        # Clear screen (simple approach - just add newlines)
        print_output("\n" * 2, level="normal")

        # Show current filter status
        if search_keyword:
            print_output(
                f"Filter: '{search_keyword}' ({len(current_tasks)} tasks)",
                level="normal",
            )
            print_output("", level="normal")

        # Display task list
        print_output(
            format_task_list(current_tasks, show_blocked=show_blocked), level="normal"
        )

        # Show help
        print_output("Commands:", level="normal")
        print_output("  <number>  - Select task by number", level="normal")
        print_output("  s <text>  - Search/filter tasks", level="normal")
        print_output("  c         - Clear search filter", level="normal")
        print_output("  d <num>   - Show details for task number", level="normal")
        print_output("  q         - Quit/cancel", level="normal")
        print_output("", level="normal")

        # Get user input
        try:
            user_input = input("Select task (or command): ").strip()
        except (EOFError, KeyboardInterrupt):
            print_output("\nSelection cancelled.", level="normal")
            return None

        if not user_input:
            continue

        # Handle quit
        if user_input.lower() in {"q", "quit", "exit"}:
            print_output("Selection cancelled.", level="normal")
            return None

        # Handle clear filter
        if user_input.lower() in {"c", "clear"}:
            current_tasks = available_tasks
            search_keyword = ""
            continue

        # Handle search
        if user_input.lower().startswith("s "):
            keyword = user_input[2:].strip()
            if keyword:
                search_keyword = keyword
                current_tasks = filter_tasks_by_keyword(available_tasks, keyword)
                if not current_tasks:
                    print_output(
                        f"\nNo tasks match '{keyword}'. Press Enter to continue...",
                        level="normal",
                    )
                    input()
                    current_tasks = available_tasks
                    search_keyword = ""
            continue

        # Handle show details
        if user_input.lower().startswith("d "):
            try:
                num = int(user_input[2:].strip())
                if 1 <= num <= len(current_tasks):
                    task = current_tasks[num - 1]
                    print_output("\n" + "=" * 60, level="normal")
                    print_output(f"Task: {task.task_id}", level="normal")
                    print_output(f"Title: {task.title}", level="normal")
                    print_output(f"Priority: {task.priority}", level="normal")
                    print_output(f"Status: {task.status}", level="normal")
                    print_output(
                        f"Blocked: {'Yes' if task.blocked else 'No'}", level="normal"
                    )
                    if task.acceptance_criteria:
                        print_output("\nAcceptance Criteria:", level="normal")
                        for i, criterion in enumerate(task.acceptance_criteria, 1):
                            print_output(f"  {i}. {criterion}", level="normal")
                    print_output("=" * 60, level="normal")
                    print_output("\nPress Enter to continue...", level="normal")
                    input()
                else:
                    print_output(
                        f"\nInvalid task number. Must be 1-{len(current_tasks)}.",
                        level="normal",
                    )
                    print_output("Press Enter to continue...", level="normal")
                    input()
            except ValueError:
                print_output(
                    "\nInvalid command. Press Enter to continue...", level="normal"
                )
                input()
            continue

        # Handle numeric selection
        try:
            num = int(user_input)
            if 1 <= num <= len(current_tasks):
                selected = current_tasks[num - 1]
                print_output(
                    f"\nSelected: {selected.task_id}: {selected.title}", level="normal"
                )
                return selected
            else:
                print_output(
                    f"\nInvalid task number. Must be 1-{len(current_tasks)}.",
                    level="normal",
                )
                print_output("Press Enter to continue...", level="normal")
                input()
        except ValueError:
            print_output(
                "\nInvalid input. Enter a number, or use a command (s/c/d/q).",
                level="normal",
            )
            print_output("Press Enter to continue...", level="normal")
            input()


def convert_selected_task_to_choice(
    task: SelectedTask,
    priority: str = "medium",
    status: str = "ready",
    blocked: bool = False,
) -> TaskChoice:
    """Convert a SelectedTask to a TaskChoice for interactive selection.

    Args:
        task: The SelectedTask to convert
        priority: Task priority (default: "medium")
        status: Task status (default: "ready")
        blocked: Whether task is blocked (default: False)

    Returns:
        TaskChoice instance
    """
    return TaskChoice(
        task_id=task.id,
        title=task.title or task.id,
        priority=priority,
        status=status,
        blocked=blocked,
        acceptance_criteria=task.acceptance or [],
    )
