"""Task dependency graph management for Ralph Gold.

This module provides functionality to build, analyze, and visualize task
dependencies, enabling ordered task execution and circular dependency detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple


@dataclass
class TaskNode:
    """Node in dependency graph representing a task."""

    task_id: str
    depends_on: List[str] = field(default_factory=list)
    blocked_by: List[str] = field(default_factory=list)
    ready: bool = False
    depth: int = 0


@dataclass
class DependencyGraph:
    """Task dependency graph."""

    nodes: Dict[str, TaskNode] = field(default_factory=dict)
    edges: List[Tuple[str, str]] = field(default_factory=list)


def build_dependency_graph(tasks: List[Dict[str, Any]]) -> DependencyGraph:
    """Build dependency graph from task list.

    Args:
        tasks: List of task dictionaries, each optionally containing a
               'depends_on' field with a list of task IDs

    Returns:
        DependencyGraph with nodes and edges populated

    Example:
        >>> tasks = [
        ...     {"id": "task-1", "depends_on": []},
        ...     {"id": "task-2", "depends_on": ["task-1"]},
        ... ]
        >>> graph = build_dependency_graph(tasks)
        >>> len(graph.nodes)
        2
    """
    graph = DependencyGraph()

    # First pass: create all nodes
    for task in tasks:
        task_id = task.get("id", "")
        if not task_id:
            continue

        depends_on = task.get("depends_on", [])
        if not isinstance(depends_on, list):
            depends_on = []

        node = TaskNode(
            task_id=task_id,
            depends_on=depends_on.copy(),
            blocked_by=[],
            ready=False,
            depth=0,
        )
        graph.nodes[task_id] = node

    # Second pass: build edges and blocked_by relationships
    for task_id, node in graph.nodes.items():
        for dep_id in node.depends_on:
            # Add edge from dependency to dependent task
            graph.edges.append((dep_id, task_id))

            # Track which tasks are blocking this task
            if dep_id in graph.nodes:
                node.blocked_by.append(dep_id)

    # Third pass: calculate depth (for visualization)
    _calculate_depths(graph)

    return graph


def _calculate_depths(graph: DependencyGraph) -> None:
    """Calculate depth of each node in the dependency graph.

    Depth is the longest path from a root node (no dependencies) to this node.
    Uses topological sort to ensure dependencies are processed first.

    Args:
        graph: The dependency graph to update with depth information
    """
    # Find nodes with no dependencies (depth 0)
    for node in graph.nodes.values():
        if not node.depends_on:
            node.depth = 0

    # Process nodes in topological order
    visited: Set[str] = set()
    for task_id in _topological_sort(graph):
        node = graph.nodes[task_id]
        visited.add(task_id)

        # Calculate depth as max(dependency depths) + 1
        if node.depends_on:
            max_dep_depth = 0
            for dep_id in node.depends_on:
                if dep_id in graph.nodes:
                    max_dep_depth = max(max_dep_depth, graph.nodes[dep_id].depth)
            node.depth = max_dep_depth + 1


def _topological_sort(graph: DependencyGraph) -> List[str]:
    """Perform topological sort on the dependency graph.

    Args:
        graph: The dependency graph to sort

    Returns:
        List of task IDs in topological order (dependencies before dependents)

    Note:
        If the graph has cycles, this will return a partial ordering.
    """
    # Calculate in-degree for each node
    in_degree: Dict[str, int] = {task_id: 0 for task_id in graph.nodes}
    for _, to_task in graph.edges:
        if to_task in in_degree:
            in_degree[to_task] += 1

    # Start with nodes that have no dependencies
    queue: List[str] = [task_id for task_id, degree in in_degree.items() if degree == 0]
    result: List[str] = []

    while queue:
        # Process node with no remaining dependencies
        current = queue.pop(0)
        result.append(current)

        # Reduce in-degree for dependent nodes
        for from_task, to_task in graph.edges:
            if from_task == current and to_task in in_degree:
                in_degree[to_task] -= 1
                if in_degree[to_task] == 0:
                    queue.append(to_task)

    return result


def detect_circular_dependencies(graph: DependencyGraph) -> List[List[str]]:
    """Detect circular dependencies using depth-first search.

    Args:
        graph: The dependency graph to check for cycles

    Returns:
        List of cycles found, where each cycle is a list of task IDs forming
        the circular dependency. Empty list if no cycles found.

    Example:
        >>> tasks = [
        ...     {"id": "task-1", "depends_on": ["task-2"]},
        ...     {"id": "task-2", "depends_on": ["task-1"]},
        ... ]
        >>> graph = build_dependency_graph(tasks)
        >>> cycles = detect_circular_dependencies(graph)
        >>> len(cycles) > 0
        True
    """
    cycles: List[List[str]] = []
    visited: Set[str] = set()
    rec_stack: Set[str] = set()
    path: List[str] = []

    def dfs(task_id: str) -> bool:
        """DFS helper that returns True if a cycle is found."""
        visited.add(task_id)
        rec_stack.add(task_id)
        path.append(task_id)

        # Check all dependencies
        node = graph.nodes.get(task_id)
        if node:
            for dep_id in node.depends_on:
                if dep_id not in graph.nodes:
                    # Dependency doesn't exist, skip
                    continue

                if dep_id not in visited:
                    if dfs(dep_id):
                        return True
                elif dep_id in rec_stack:
                    # Found a cycle - extract the cycle from path
                    cycle_start = path.index(dep_id)
                    cycle = path[cycle_start:] + [dep_id]
                    cycles.append(cycle)
                    return True

        path.pop()
        rec_stack.remove(task_id)
        return False

    # Run DFS from each unvisited node
    for task_id in graph.nodes:
        if task_id not in visited:
            dfs(task_id)

    return cycles


def get_ready_tasks(graph: DependencyGraph, completed: Set[str]) -> List[str]:
    """Get tasks with all dependencies satisfied.

    Args:
        graph: The dependency graph
        completed: Set of task IDs that have been completed

    Returns:
        List of task IDs that are ready to be executed (all dependencies met)

    Example:
        >>> tasks = [
        ...     {"id": "task-1", "depends_on": []},
        ...     {"id": "task-2", "depends_on": ["task-1"]},
        ... ]
        >>> graph = build_dependency_graph(tasks)
        >>> ready = get_ready_tasks(graph, set())
        >>> "task-1" in ready
        True
        >>> "task-2" in ready
        False
    """
    ready: List[str] = []

    for task_id, node in graph.nodes.items():
        # Skip if already completed
        if task_id in completed:
            continue

        # Check if all dependencies are satisfied
        all_deps_met = True
        for dep_id in node.depends_on:
            if dep_id not in completed:
                all_deps_met = False
                break

        if all_deps_met:
            node.ready = True
            ready.append(task_id)
        else:
            node.ready = False

    return ready


def format_dependency_graph(graph: DependencyGraph) -> str:
    """Format graph as ASCII art visualization.

    Args:
        graph: The dependency graph to visualize

    Returns:
        String containing ASCII art representation of the dependency graph

    Example:
        >>> tasks = [
        ...     {"id": "task-1", "depends_on": []},
        ...     {"id": "task-2", "depends_on": ["task-1"]},
        ... ]
        >>> graph = build_dependency_graph(tasks)
        >>> output = format_dependency_graph(graph)
        >>> "task-1" in output
        True
    """
    if not graph.nodes:
        return "No tasks in dependency graph"

    lines: List[str] = []
    lines.append("=" * 60)
    lines.append("Task Dependency Graph")
    lines.append("=" * 60)
    lines.append("")

    # Group tasks by depth for visualization
    tasks_by_depth: Dict[int, List[str]] = {}
    max_depth = 0

    for task_id, node in graph.nodes.items():
        depth = node.depth
        if depth not in tasks_by_depth:
            tasks_by_depth[depth] = []
        tasks_by_depth[depth].append(task_id)
        max_depth = max(max_depth, depth)

    # Render each depth level
    for depth in range(max_depth + 1):
        tasks = tasks_by_depth.get(depth, [])
        if not tasks:
            continue

        # Show depth level
        lines.append(f"Level {depth}:")

        for task_id in sorted(tasks):
            node = graph.nodes[task_id]

            # Show task with status indicator
            status = "✓" if node.ready else "○"
            lines.append(f"  {status} {task_id}")

            # Show dependencies
            if node.depends_on:
                deps_str = ", ".join(sorted(node.depends_on))
                lines.append(f"      depends on: {deps_str}")

        lines.append("")

    # Show summary
    lines.append("=" * 60)
    lines.append(f"Total tasks: {len(graph.nodes)}")
    lines.append(f"Total dependencies: {len(graph.edges)}")

    # Check for cycles
    cycles = detect_circular_dependencies(graph)
    if cycles:
        lines.append("")
        lines.append("⚠️  WARNING: Circular dependencies detected!")
        for i, cycle in enumerate(cycles, 1):
            cycle_str = " → ".join(cycle)
            lines.append(f"  Cycle {i}: {cycle_str}")

    lines.append("=" * 60)

    return "\n".join(lines)
