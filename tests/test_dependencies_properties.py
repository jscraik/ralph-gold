"""Property-based tests for the dependencies module.

This module contains property-based tests using hypothesis to verify
correctness properties across a wide range of inputs.
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from ralph_gold.dependencies import (
    build_dependency_graph,
    detect_circular_dependencies,
    get_ready_tasks,
)


# Custom strategies for generating test data
@st.composite
def task_id_strategy(draw: st.DrawFn) -> str:
    """Generate a valid task ID."""
    return draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pd")),
            min_size=1,
            max_size=20,
        ).filter(lambda x: x and x.strip())
    )


@st.composite
def task_dict_strategy(
    draw: st.DrawFn, task_id: str, available_ids: list[str]
) -> dict[str, Any]:
    """Generate a task dictionary with optional dependencies."""
    # Randomly decide if this task has dependencies
    has_deps = draw(st.booleans())

    if has_deps and available_ids:
        # Select a subset of available task IDs as dependencies
        num_deps = draw(st.integers(min_value=0, max_value=min(3, len(available_ids))))
        depends_on = draw(st.lists(st.sampled_from(available_ids), max_size=num_deps))
    else:
        depends_on = []

    return {"id": task_id, "depends_on": depends_on}


@st.composite
def task_list_strategy(
    draw: st.DrawFn, min_size: int = 1, max_size: int = 20
) -> list[dict[str, Any]]:
    """Generate a list of task dictionaries with dependencies."""
    num_tasks = draw(st.integers(min_value=min_size, max_value=max_size))

    # Generate unique task IDs
    task_ids = [f"task-{i}" for i in range(num_tasks)]

    tasks = []
    for i, task_id in enumerate(task_ids):
        # Only allow dependencies on tasks that come before this one
        # This prevents cycles in most cases
        available_ids = task_ids[:i] if i > 0 else []
        task = draw(task_dict_strategy(task_id, available_ids))
        tasks.append(task)

    return tasks


@st.composite
def cyclic_task_list_strategy(
    draw: st.DrawFn, min_size: int = 2, max_size: int = 10
) -> list[dict[str, Any]]:
    """Generate a list of tasks with at least one cycle."""
    cycle_length = draw(st.integers(min_value=min_size, max_value=max_size))

    tasks = []
    for i in range(cycle_length):
        next_task = (i + 1) % cycle_length
        task = {"id": f"task-{i}", "depends_on": [f"task-{next_task}"]}
        tasks.append(task)

    return tasks


# Property 12: Dependency Satisfaction
@given(task_list_strategy(min_size=2, max_size=15))
@settings(max_examples=100)
def test_property_12_dependency_satisfaction(tasks: list[dict[str, Any]]):
    """**Validates: Requirements US-5.1**

    Feature: ralph-enhancement-phase2, Property 12
    For any task with dependencies, it should only be selectable when all tasks
    in its depends_on list are marked complete.
    """
    graph = build_dependency_graph(tasks)

    # Test with no completed tasks
    ready = get_ready_tasks(graph, set())

    # Verify that only tasks with no dependencies are ready
    for task_id in ready:
        node = graph.nodes[task_id]
        assert len(node.depends_on) == 0, (
            f"Task {task_id} is ready but has dependencies: {node.depends_on}"
        )

    # Test with progressively completing tasks
    completed: set[str] = set()

    for task in tasks:
        task_id = task["id"]
        depends_on = task.get("depends_on", [])

        # Get ready tasks
        ready = get_ready_tasks(graph, completed)

        # If all dependencies are completed, task should be ready
        all_deps_met = all(dep in completed for dep in depends_on)

        if all_deps_met and task_id not in completed:
            assert task_id in ready, (
                f"Task {task_id} should be ready (all deps met: {depends_on}), "
                f"but not in ready list: {ready}"
            )
        elif task_id in completed:
            assert task_id not in ready, (
                f"Task {task_id} is completed but still in ready list"
            )
        else:
            # Some dependencies not met
            assert task_id not in ready, (
                f"Task {task_id} is ready but has unmet dependencies. "
                f"Depends on: {depends_on}, Completed: {completed}"
            )

        # Mark task as completed if it's ready
        if task_id in ready:
            completed.add(task_id)


@given(st.integers(min_value=1, max_value=10))
@settings(max_examples=100)
def test_property_12_task_not_ready_until_all_deps_complete(num_deps: int):
    """**Validates: Requirements US-5.1**

    Feature: ralph-enhancement-phase2, Property 12
    A task should not be ready until ALL of its dependencies are complete.
    """
    # Create a task with unique dependencies
    dep_ids = [f"dep-{i}" for i in range(num_deps)]
    task = {"id": "task-1", "depends_on": dep_ids}

    # Add the dependency tasks
    all_tasks = [task]
    for dep_id in dep_ids:
        all_tasks.append({"id": dep_id, "depends_on": []})

    graph = build_dependency_graph(all_tasks)

    # Task should not be ready with no completed tasks
    ready = get_ready_tasks(graph, set())
    assert "task-1" not in ready, "Task should not be ready with no completed deps"

    # Complete dependencies one by one
    completed: set[str] = set()
    for dep_id in dep_ids[:-1]:  # All but last
        completed.add(dep_id)
        ready = get_ready_tasks(graph, completed)
        assert "task-1" not in ready, (
            f"Task should not be ready with incomplete deps. "
            f"Completed: {completed}, Needs: {dep_ids}"
        )

    # Complete the last dependency
    completed.add(dep_ids[-1])
    ready = get_ready_tasks(graph, completed)
    assert "task-1" in ready, "Task should be ready when all dependencies are complete"


# Property 13: Circular Dependency Detection
@given(cyclic_task_list_strategy(min_size=2, max_size=10))
@settings(max_examples=100)
def test_property_13_circular_dependency_detection_finds_cycles(
    tasks: list[dict[str, Any]],
):
    """**Validates: Requirements US-5.3**

    Feature: ralph-enhancement-phase2, Property 13
    For any dependency graph with a cycle, circular dependencies should be detected.
    """
    graph = build_dependency_graph(tasks)
    cycles = detect_circular_dependencies(graph)

    # Should detect at least one cycle
    assert len(cycles) > 0, (
        f"Circular dependency not detected. Tasks: {tasks}, Cycles: {cycles}"
    )

    # Each cycle should contain at least 2 tasks
    for cycle in cycles:
        assert len(cycle) >= 2, f"Invalid cycle detected: {cycle}"


@given(task_list_strategy(min_size=1, max_size=15))
@settings(max_examples=100)
def test_property_13_no_false_positives_for_acyclic_graphs(
    tasks: list[dict[str, Any]],
):
    """**Validates: Requirements US-5.3**

    Feature: ralph-enhancement-phase2, Property 13
    For acyclic dependency graphs, no circular dependencies should be detected.
    """
    # task_list_strategy generates acyclic graphs by construction
    # (tasks can only depend on earlier tasks)
    graph = build_dependency_graph(tasks)
    cycles = detect_circular_dependencies(graph)

    # Should not detect any cycles
    assert len(cycles) == 0, (
        f"False positive: cycles detected in acyclic graph. "
        f"Tasks: {tasks}, Cycles: {cycles}"
    )


@given(st.integers(min_value=2, max_value=10))
@settings(max_examples=100)
def test_property_13_self_dependency_is_detected(cycle_length: int):
    """**Validates: Requirements US-5.3**

    Feature: ralph-enhancement-phase2, Property 13
    A task depending on itself should be detected as a circular dependency.
    """
    # Create a task that depends on itself
    tasks = [{"id": "self-ref", "depends_on": ["self-ref"]}]

    # Add some other tasks to make it more realistic
    for i in range(cycle_length - 1):
        tasks.append({"id": f"task-{i}", "depends_on": []})

    graph = build_dependency_graph(tasks)
    cycles = detect_circular_dependencies(graph)

    # Should detect the self-reference as a cycle
    assert len(cycles) > 0, "Self-reference not detected as circular dependency"

    # At least one cycle should involve the self-referencing task
    self_ref_in_cycle = any("self-ref" in cycle for cycle in cycles)
    assert self_ref_in_cycle, (
        f"Self-referencing task not found in detected cycles: {cycles}"
    )


# Property 14: Dependency Format Consistency
@given(task_list_strategy(min_size=1, max_size=10))
@settings(max_examples=100)
def test_property_14_dependency_format_consistency_json(
    tasks: list[dict[str, Any]],
):
    """**Validates: Requirements US-5.1**

    Feature: ralph-enhancement-phase2, Property 14
    For any dependency specification in JSON format, parsing should produce
    consistent dependency relationships.
    """
    # Build graph from JSON-style task list
    graph = build_dependency_graph(tasks)

    # Verify all dependencies are correctly represented
    for task in tasks:
        task_id = task["id"]
        expected_deps = task.get("depends_on", [])

        if task_id in graph.nodes:
            node = graph.nodes[task_id]
            assert node.depends_on == expected_deps, (
                f"Dependencies mismatch for {task_id}. "
                f"Expected: {expected_deps}, Got: {node.depends_on}"
            )


@given(task_list_strategy(min_size=1, max_size=10))
@settings(max_examples=100)
def test_property_14_missing_depends_on_field_handled(tasks: list[dict[str, Any]]):
    """**Validates: Requirements US-5.1**

    Feature: ralph-enhancement-phase2, Property 14
    Tasks without a depends_on field should be treated as having no dependencies.
    """
    # Remove depends_on field from some tasks
    modified_tasks = []
    for task in tasks:
        if task.get("depends_on", []):
            # Keep some with depends_on, remove from others
            modified_task = {"id": task["id"]}
            # 50% chance to keep depends_on
            if hash(task["id"]) % 2 == 0:
                modified_task["depends_on"] = task["depends_on"]
            modified_tasks.append(modified_task)
        else:
            modified_tasks.append(task)

    graph = build_dependency_graph(modified_tasks)

    # Verify tasks without depends_on field have empty dependencies
    for task in modified_tasks:
        task_id = task["id"]
        if task_id in graph.nodes:
            node = graph.nodes[task_id]
            expected_deps = task.get("depends_on", [])
            assert node.depends_on == expected_deps, (
                f"Task {task_id} dependencies mismatch. "
                f"Expected: {expected_deps}, Got: {node.depends_on}"
            )


@given(task_list_strategy(min_size=1, max_size=10))
@settings(max_examples=100)
def test_property_14_invalid_depends_on_type_handled(tasks: list[dict[str, Any]]):
    """**Validates: Requirements US-5.1**

    Feature: ralph-enhancement-phase2, Property 14
    Invalid depends_on values (non-list) should be handled gracefully.
    """
    # Corrupt some depends_on fields with invalid types
    modified_tasks = []
    for i, task in enumerate(tasks):
        modified_task = {"id": task["id"]}
        # Every 3rd task gets an invalid depends_on
        if i % 3 == 0:
            modified_task["depends_on"] = "not-a-list"  # Invalid type
        else:
            modified_task["depends_on"] = task.get("depends_on", [])
        modified_tasks.append(modified_task)

    # Should not raise an exception
    graph = build_dependency_graph(modified_tasks)

    # Tasks with invalid depends_on should have empty dependencies
    for i, task in enumerate(modified_tasks):
        task_id = task["id"]
        if task_id in graph.nodes:
            node = graph.nodes[task_id]
            if i % 3 == 0:
                # Invalid depends_on should default to empty list
                assert node.depends_on == [], (
                    f"Task {task_id} with invalid depends_on should have empty deps"
                )


# Property 15: Backward Compatibility
@given(
    st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
            min_size=1,
            max_size=20,
        ),
        min_size=1,
        max_size=15,
        unique=True,
    )
)
@settings(max_examples=100)
def test_property_15_backward_compatibility_no_depends_on(task_ids: list[str]):
    """**Validates: General criteria 1**

    Feature: ralph-enhancement-phase2, Property 15
    For any task without a depends_on field, it should be treated as having
    no dependencies (always ready when not blocked by other criteria).
    """
    # Create tasks without depends_on field
    tasks = [{"id": task_id} for task_id in task_ids]

    graph = build_dependency_graph(tasks)

    # All tasks should be ready (no dependencies)
    ready = get_ready_tasks(graph, set())

    assert len(ready) == len(task_ids), (
        f"All tasks without depends_on should be ready. "
        f"Expected {len(task_ids)}, got {len(ready)}"
    )

    # Verify all task IDs are in ready list
    for task_id in task_ids:
        assert task_id in ready, f"Task {task_id} without depends_on should be ready"


@given(task_list_strategy(min_size=1, max_size=10))
@settings(max_examples=100)
def test_property_15_empty_depends_on_same_as_missing(tasks: list[dict[str, Any]]):
    """**Validates: General criteria 1**

    Feature: ralph-enhancement-phase2, Property 15
    Tasks with empty depends_on list should behave identically to tasks
    without the depends_on field.
    """
    # Create two versions: one with empty depends_on, one without the field
    tasks_with_empty = []
    tasks_without_field = []

    for task in tasks:
        task_id = task["id"]
        # Version with empty depends_on
        tasks_with_empty.append({"id": task_id, "depends_on": []})
        # Version without depends_on field
        tasks_without_field.append({"id": task_id})

    graph1 = build_dependency_graph(tasks_with_empty)
    graph2 = build_dependency_graph(tasks_without_field)

    # Both should produce identical ready task lists
    ready1 = get_ready_tasks(graph1, set())
    ready2 = get_ready_tasks(graph2, set())

    assert set(ready1) == set(ready2), (
        f"Empty depends_on and missing depends_on should produce same results. "
        f"With empty: {ready1}, Without field: {ready2}"
    )

    # Both should have same number of nodes
    assert len(graph1.nodes) == len(graph2.nodes)

    # All nodes should have empty dependencies
    for task_id in graph1.nodes:
        assert graph1.nodes[task_id].depends_on == []
        assert graph2.nodes[task_id].depends_on == []


@given(task_list_strategy(min_size=2, max_size=10))
@settings(max_examples=100)
def test_property_15_mixed_legacy_and_new_format(tasks: list[dict[str, Any]]):
    """**Validates: General criteria 1**

    Feature: ralph-enhancement-phase2, Property 15
    A mix of tasks with and without depends_on should work correctly together.
    """
    # Mix tasks: some with depends_on, some without
    mixed_tasks = []
    for i, task in enumerate(tasks):
        if i % 2 == 0:
            # Keep depends_on
            mixed_tasks.append(task)
        else:
            # Remove depends_on (legacy format)
            mixed_tasks.append({"id": task["id"]})

    # Should not raise an exception
    graph = build_dependency_graph(mixed_tasks)

    # Get ready tasks
    ready = get_ready_tasks(graph, set())

    # Verify legacy tasks (without depends_on) are ready
    for i, task in enumerate(mixed_tasks):
        task_id = task["id"]
        if i % 2 == 1:  # Legacy task
            assert task_id in ready, (
                f"Legacy task {task_id} without depends_on should be ready"
            )


# Additional property: Nonexistent dependencies don't crash
@given(task_list_strategy(min_size=1, max_size=10))
@settings(max_examples=100)
def test_property_nonexistent_dependencies_handled_gracefully(
    tasks: list[dict[str, Any]],
):
    """**Validates: General criteria 4**

    Feature: ralph-enhancement-phase2
    Tasks with dependencies on nonexistent tasks should be handled gracefully.
    """
    # Add some nonexistent dependencies
    modified_tasks = []
    for task in tasks:
        modified_task = task.copy()
        # Add a nonexistent dependency
        deps = task.get("depends_on", []).copy()
        deps.append("nonexistent-task-xyz")
        modified_task["depends_on"] = deps
        modified_tasks.append(modified_task)

    # Should not crash
    graph = build_dependency_graph(modified_tasks)

    # Tasks with nonexistent dependencies should not be ready
    ready = get_ready_tasks(graph, set())

    for task in modified_tasks:
        task_id = task["id"]
        # Task should not be ready because it has an unmet dependency
        assert task_id not in ready, (
            f"Task {task_id} with nonexistent dependency should not be ready"
        )


# Additional property: Graph building is deterministic
@given(task_list_strategy(min_size=1, max_size=10))
@settings(max_examples=100)
def test_property_graph_building_is_deterministic(tasks: list[dict[str, Any]]):
    """**Validates: General criteria 1**

    Feature: ralph-enhancement-phase2
    Building a graph multiple times from the same tasks should produce
    identical results.
    """
    graph1 = build_dependency_graph(tasks)
    graph2 = build_dependency_graph(tasks)

    # Should have same number of nodes and edges
    assert len(graph1.nodes) == len(graph2.nodes)
    assert len(graph1.edges) == len(graph2.edges)

    # Nodes should have identical properties
    for task_id in graph1.nodes:
        assert task_id in graph2.nodes
        node1 = graph1.nodes[task_id]
        node2 = graph2.nodes[task_id]
        assert node1.task_id == node2.task_id
        assert node1.depends_on == node2.depends_on
        assert node1.depth == node2.depth

    # Edges should be identical
    assert set(graph1.edges) == set(graph2.edges)


# Additional property: Ready tasks are consistent
@given(task_list_strategy(min_size=1, max_size=10))
@settings(max_examples=100)
def test_property_ready_tasks_consistency(tasks: list[dict[str, Any]]):
    """**Validates: Requirements US-5.1**

    Feature: ralph-enhancement-phase2
    Getting ready tasks multiple times with the same completed set should
    produce identical results.
    """
    graph = build_dependency_graph(tasks)

    # Try with different completed sets
    completed_sets = [
        set(),
        {tasks[0]["id"]} if tasks else set(),
        {t["id"] for t in tasks[: len(tasks) // 2]},
    ]

    for completed in completed_sets:
        ready1 = get_ready_tasks(graph, completed)
        ready2 = get_ready_tasks(graph, completed)

        assert set(ready1) == set(ready2), (
            f"Ready tasks should be consistent. "
            f"First call: {ready1}, Second call: {ready2}"
        )
