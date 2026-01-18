"""Unit tests for the dependencies module."""

from ralph_gold.dependencies import (
    build_dependency_graph,
    detect_circular_dependencies,
    format_dependency_graph,
    get_ready_tasks,
)


def test_build_dependency_graph_empty():
    """Test building graph with no tasks."""
    graph = build_dependency_graph([])
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0


def test_build_dependency_graph_single_task():
    """Test building graph with single task and no dependencies."""
    tasks = [{"id": "task-1", "depends_on": []}]
    graph = build_dependency_graph(tasks)

    assert len(graph.nodes) == 1
    assert "task-1" in graph.nodes
    assert graph.nodes["task-1"].depends_on == []
    assert len(graph.edges) == 0


def test_build_dependency_graph_with_dependencies():
    """Test building graph with multiple tasks and dependencies."""
    tasks = [
        {"id": "task-1", "depends_on": []},
        {"id": "task-2", "depends_on": ["task-1"]},
        {"id": "task-3", "depends_on": ["task-1", "task-2"]},
    ]
    graph = build_dependency_graph(tasks)

    assert len(graph.nodes) == 3
    assert graph.nodes["task-1"].depends_on == []
    assert graph.nodes["task-2"].depends_on == ["task-1"]
    assert graph.nodes["task-3"].depends_on == ["task-1", "task-2"]

    # Check edges
    assert ("task-1", "task-2") in graph.edges
    assert ("task-1", "task-3") in graph.edges
    assert ("task-2", "task-3") in graph.edges


def test_build_dependency_graph_missing_depends_on():
    """Test that tasks without depends_on field are handled correctly."""
    tasks = [
        {"id": "task-1"},  # No depends_on field
        {"id": "task-2", "depends_on": ["task-1"]},
    ]
    graph = build_dependency_graph(tasks)

    assert len(graph.nodes) == 2
    assert graph.nodes["task-1"].depends_on == []
    assert graph.nodes["task-2"].depends_on == ["task-1"]


def test_build_dependency_graph_invalid_depends_on():
    """Test that invalid depends_on values are handled gracefully."""
    tasks = [
        {"id": "task-1", "depends_on": "not-a-list"},  # Invalid type
        {"id": "task-2", "depends_on": []},
    ]
    graph = build_dependency_graph(tasks)

    assert len(graph.nodes) == 2
    assert graph.nodes["task-1"].depends_on == []  # Should default to empty


def test_detect_circular_dependencies_no_cycle():
    """Test circular dependency detection with no cycles."""
    tasks = [
        {"id": "task-1", "depends_on": []},
        {"id": "task-2", "depends_on": ["task-1"]},
        {"id": "task-3", "depends_on": ["task-2"]},
    ]
    graph = build_dependency_graph(tasks)
    cycles = detect_circular_dependencies(graph)

    assert len(cycles) == 0


def test_detect_circular_dependencies_simple_cycle():
    """Test circular dependency detection with a simple 2-task cycle."""
    tasks = [
        {"id": "task-1", "depends_on": ["task-2"]},
        {"id": "task-2", "depends_on": ["task-1"]},
    ]
    graph = build_dependency_graph(tasks)
    cycles = detect_circular_dependencies(graph)

    assert len(cycles) > 0
    # Should detect the cycle
    cycle = cycles[0]
    assert len(cycle) >= 2


def test_detect_circular_dependencies_complex_cycle():
    """Test circular dependency detection with a longer cycle."""
    tasks = [
        {"id": "task-1", "depends_on": ["task-3"]},
        {"id": "task-2", "depends_on": ["task-1"]},
        {"id": "task-3", "depends_on": ["task-2"]},
    ]
    graph = build_dependency_graph(tasks)
    cycles = detect_circular_dependencies(graph)

    assert len(cycles) > 0


def test_get_ready_tasks_no_dependencies():
    """Test getting ready tasks when no dependencies exist."""
    tasks = [
        {"id": "task-1", "depends_on": []},
        {"id": "task-2", "depends_on": []},
    ]
    graph = build_dependency_graph(tasks)
    ready = get_ready_tasks(graph, set())

    assert len(ready) == 2
    assert "task-1" in ready
    assert "task-2" in ready


def test_get_ready_tasks_with_dependencies():
    """Test getting ready tasks with dependencies."""
    tasks = [
        {"id": "task-1", "depends_on": []},
        {"id": "task-2", "depends_on": ["task-1"]},
        {"id": "task-3", "depends_on": ["task-2"]},
    ]
    graph = build_dependency_graph(tasks)

    # Initially, only task-1 is ready
    ready = get_ready_tasks(graph, set())
    assert ready == ["task-1"]

    # After completing task-1, task-2 is ready
    ready = get_ready_tasks(graph, {"task-1"})
    assert ready == ["task-2"]

    # After completing task-1 and task-2, task-3 is ready
    ready = get_ready_tasks(graph, {"task-1", "task-2"})
    assert ready == ["task-3"]


def test_get_ready_tasks_multiple_dependencies():
    """Test getting ready tasks when a task has multiple dependencies."""
    tasks = [
        {"id": "task-1", "depends_on": []},
        {"id": "task-2", "depends_on": []},
        {"id": "task-3", "depends_on": ["task-1", "task-2"]},
    ]
    graph = build_dependency_graph(tasks)

    # Initially, task-1 and task-2 are ready
    ready = get_ready_tasks(graph, set())
    assert len(ready) == 2
    assert "task-1" in ready
    assert "task-2" in ready

    # After completing only task-1, task-3 is still not ready
    ready = get_ready_tasks(graph, {"task-1"})
    assert "task-2" in ready
    assert "task-3" not in ready

    # After completing both task-1 and task-2, task-3 is ready
    ready = get_ready_tasks(graph, {"task-1", "task-2"})
    assert ready == ["task-3"]


def test_get_ready_tasks_excludes_completed():
    """Test that completed tasks are not included in ready tasks."""
    tasks = [
        {"id": "task-1", "depends_on": []},
        {"id": "task-2", "depends_on": []},
    ]
    graph = build_dependency_graph(tasks)

    # Mark task-1 as completed
    ready = get_ready_tasks(graph, {"task-1"})
    assert len(ready) == 1
    assert "task-2" in ready
    assert "task-1" not in ready


def test_format_dependency_graph_empty():
    """Test formatting an empty graph."""
    graph = build_dependency_graph([])
    output = format_dependency_graph(graph)

    assert "No tasks in dependency graph" in output


def test_format_dependency_graph_simple():
    """Test formatting a simple graph."""
    tasks = [
        {"id": "task-1", "depends_on": []},
        {"id": "task-2", "depends_on": ["task-1"]},
    ]
    graph = build_dependency_graph(tasks)
    output = format_dependency_graph(graph)

    assert "task-1" in output
    assert "task-2" in output
    assert "Total tasks: 2" in output
    assert "Total dependencies: 1" in output


def test_format_dependency_graph_with_cycle():
    """Test formatting a graph with circular dependencies."""
    tasks = [
        {"id": "task-1", "depends_on": ["task-2"]},
        {"id": "task-2", "depends_on": ["task-1"]},
    ]
    graph = build_dependency_graph(tasks)
    output = format_dependency_graph(graph)

    assert "Circular dependencies detected" in output or "WARNING" in output


def test_depth_calculation():
    """Test that depth is calculated correctly."""
    tasks = [
        {"id": "task-1", "depends_on": []},
        {"id": "task-2", "depends_on": ["task-1"]},
        {"id": "task-3", "depends_on": ["task-2"]},
    ]
    graph = build_dependency_graph(tasks)

    assert graph.nodes["task-1"].depth == 0
    assert graph.nodes["task-2"].depth == 1
    assert graph.nodes["task-3"].depth == 2


def test_depth_calculation_multiple_paths():
    """Test depth calculation with multiple paths to a node."""
    tasks = [
        {"id": "task-1", "depends_on": []},
        {"id": "task-2", "depends_on": []},
        {"id": "task-3", "depends_on": ["task-1"]},
        {"id": "task-4", "depends_on": ["task-2", "task-3"]},
    ]
    graph = build_dependency_graph(tasks)

    assert graph.nodes["task-1"].depth == 0
    assert graph.nodes["task-2"].depth == 0
    assert graph.nodes["task-3"].depth == 1
    # task-4 depends on task-3 (depth 1), so it should be depth 2
    assert graph.nodes["task-4"].depth == 2


def test_blocked_by_tracking():
    """Test that blocked_by relationships are tracked correctly."""
    tasks = [
        {"id": "task-1", "depends_on": []},
        {"id": "task-2", "depends_on": ["task-1"]},
        {"id": "task-3", "depends_on": ["task-1", "task-2"]},
    ]
    graph = build_dependency_graph(tasks)

    assert graph.nodes["task-1"].blocked_by == []
    assert "task-1" in graph.nodes["task-2"].blocked_by
    assert "task-1" in graph.nodes["task-3"].blocked_by
    assert "task-2" in graph.nodes["task-3"].blocked_by


def test_topological_ordering_via_depth():
    """Test that topological ordering is correct via depth calculation.

    This indirectly tests _topological_sort since depth calculation
    depends on processing nodes in topological order.
    """
    tasks = [
        {"id": "task-1", "depends_on": []},
        {"id": "task-2", "depends_on": []},
        {"id": "task-3", "depends_on": ["task-1"]},
        {"id": "task-4", "depends_on": ["task-2"]},
        {"id": "task-5", "depends_on": ["task-3", "task-4"]},
    ]
    graph = build_dependency_graph(tasks)

    # Root nodes should have depth 0
    assert graph.nodes["task-1"].depth == 0
    assert graph.nodes["task-2"].depth == 0

    # Second level nodes should have depth 1
    assert graph.nodes["task-3"].depth == 1
    assert graph.nodes["task-4"].depth == 1

    # Final node depends on second level, so depth 2
    assert graph.nodes["task-5"].depth == 2


def test_nonexistent_dependency():
    """Test that dependencies referencing non-existent tasks are handled gracefully."""
    tasks = [
        {"id": "task-1", "depends_on": ["nonexistent-task"]},
        {"id": "task-2", "depends_on": []},
    ]
    graph = build_dependency_graph(tasks)

    # Graph should still be built
    assert len(graph.nodes) == 2

    # task-1 should not be ready since its dependency doesn't exist
    ready = get_ready_tasks(graph, set())
    assert "task-2" in ready
    # task-1 has unmet dependency (even though it doesn't exist)
    assert "task-1" not in ready


def test_self_dependency():
    """Test that a task depending on itself is detected as a cycle."""
    tasks = [
        {"id": "task-1", "depends_on": ["task-1"]},
    ]
    graph = build_dependency_graph(tasks)
    cycles = detect_circular_dependencies(graph)

    # Should detect self-reference as a cycle
    assert len(cycles) > 0


def test_diamond_dependency_pattern():
    """Test diamond dependency pattern (common ancestor, multiple paths).
    
    Structure:
        task-1
       /      \\
    task-2  task-3
       \\      /
        task-4
    """
    tasks = [
        {"id": "task-1", "depends_on": []},
        {"id": "task-2", "depends_on": ["task-1"]},
        {"id": "task-3", "depends_on": ["task-1"]},
        {"id": "task-4", "depends_on": ["task-2", "task-3"]},
    ]
    graph = build_dependency_graph(tasks)

    # Verify structure
    assert len(graph.nodes) == 4
    assert len(graph.edges) == 4

    # Test ready tasks at each stage
    ready = get_ready_tasks(graph, set())
    assert ready == ["task-1"]

    ready = get_ready_tasks(graph, {"task-1"})
    assert set(ready) == {"task-2", "task-3"}

    ready = get_ready_tasks(graph, {"task-1", "task-2"})
    assert "task-4" not in ready  # Still waiting for task-3

    ready = get_ready_tasks(graph, {"task-1", "task-2", "task-3"})
    assert ready == ["task-4"]


def test_empty_task_id():
    """Test that tasks with empty IDs are skipped gracefully."""
    tasks = [
        {"id": "", "depends_on": []},
        {"id": "task-1", "depends_on": []},
    ]
    graph = build_dependency_graph(tasks)

    # Only task-1 should be in the graph
    assert len(graph.nodes) == 1
    assert "task-1" in graph.nodes


def test_format_dependency_graph_shows_ready_status():
    """Test that formatted graph shows ready status correctly."""
    tasks = [
        {"id": "task-1", "depends_on": []},
        {"id": "task-2", "depends_on": ["task-1"]},
    ]
    graph = build_dependency_graph(tasks)

    # Mark ready tasks
    get_ready_tasks(graph, set())

    output = format_dependency_graph(graph)

    # Should show task-1 as ready (✓) and task-2 as not ready (○)
    assert "task-1" in output
    assert "task-2" in output


def test_large_dependency_chain():
    """Test a long chain of dependencies to verify scalability."""
    # Create a chain: task-1 -> task-2 -> ... -> task-10
    tasks = []
    for i in range(1, 11):
        depends_on = [f"task-{i - 1}"] if i > 1 else []
        tasks.append({"id": f"task-{i}", "depends_on": depends_on})

    graph = build_dependency_graph(tasks)

    # Verify chain structure
    assert len(graph.nodes) == 10
    assert len(graph.edges) == 9

    # Verify depths
    for i in range(1, 11):
        assert graph.nodes[f"task-{i}"].depth == i - 1

    # Verify only first task is ready
    ready = get_ready_tasks(graph, set())
    assert ready == ["task-1"]

    # Verify sequential unlocking
    completed = set()
    for i in range(1, 11):
        ready = get_ready_tasks(graph, completed)
        assert ready == [f"task-{i}"]
        completed.add(f"task-{i}")


def test_multiple_independent_chains():
    """Test multiple independent dependency chains."""
    tasks = [
        # Chain 1: A -> B -> C
        {"id": "task-A", "depends_on": []},
        {"id": "task-B", "depends_on": ["task-A"]},
        {"id": "task-C", "depends_on": ["task-B"]},
        # Chain 2: X -> Y -> Z
        {"id": "task-X", "depends_on": []},
        {"id": "task-Y", "depends_on": ["task-X"]},
        {"id": "task-Z", "depends_on": ["task-Y"]},
    ]
    graph = build_dependency_graph(tasks)

    # Both root tasks should be ready
    ready = get_ready_tasks(graph, set())
    assert set(ready) == {"task-A", "task-X"}

    # Complete one chain partially
    ready = get_ready_tasks(graph, {"task-A"})
    assert set(ready) == {"task-B", "task-X"}

    # Complete both chains partially
    ready = get_ready_tasks(graph, {"task-A", "task-X"})
    assert set(ready) == {"task-B", "task-Y"}
