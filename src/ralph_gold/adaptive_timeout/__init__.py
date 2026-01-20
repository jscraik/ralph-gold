"""Adaptive timeout and task complexity classification for RALPH.

This module provides:
- TaskComplexity: Classification levels for timeout allocation
- estimate_task_complexity(): Classify task complexity from metadata
- calculate_adaptive_timeout(): Calculate dynamic timeout per task attempt

Phase 5: Adaptive Timeout & Unblock mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from ..config import AdaptiveTimeoutConfig
from ..prd import SelectedTask


class ComplexityLevel(Enum):
    """Task complexity levels for timeout allocation."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    UI_HEAVY = "ui_heavy"


@dataclass(frozen=True)
class TaskComplexity:
    """Task complexity classification with timeout multiplier.

    Attributes:
        level: The complexity level enum
        base_timeout_seconds: Base timeout for this complexity
        multiplier: Multiplier applied to mode timeout
        description: Human-readable description
        keywords: Keywords that trigger this classification
    """
    level: ComplexityLevel
    base_timeout_seconds: int
    multiplier: float
    description: str
    keywords: Tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate complexity values."""
        if self.base_timeout_seconds < 0:
            raise ValueError(f"base_timeout must be >= 0, got {self.base_timeout_seconds}")
        if self.multiplier < 0.5:
            raise ValueError(f"multiplier must be >= 0.5, got {self.multiplier}")


# Default complexity matrix
DEFAULT_COMPLEXITIES: Dict[ComplexityLevel, TaskComplexity] = {
    ComplexityLevel.SIMPLE: TaskComplexity(
        level=ComplexityLevel.SIMPLE,
        base_timeout_seconds=60,
        multiplier=1.0,
        description="Simple fixes, updates, refactors",
        keywords=(
            "fix", "update", "refactor", "rename", "remove", "delete",
            "add", "change", "replace", "correct", "adjust", "simplify"
        ),
    ),
    ComplexityLevel.MEDIUM: TaskComplexity(
        level=ComplexityLevel.MEDIUM,
        base_timeout_seconds=180,
        multiplier=1.5,
        description="Tests, mocks, simple implementations",
        keywords=(
            "test", "mock", "fixture", "stub", "implement", "basic",
            "simple", "straightforward", "add test", "create test"
        ),
    ),
    ComplexityLevel.COMPLEX: TaskComplexity(
        level=ComplexityLevel.COMPLEX,
        base_timeout_seconds=300,
        multiplier=2.0,
        description="CLI, parsers, complex logic, multi-file",
        keywords=(
            "cli", "command", "parser", "parsing", "serializer",
            "complex", "intricate", "integration", "middleware"
        ),
    ),
    ComplexityLevel.UI_HEAVY: TaskComplexity(
        level=ComplexityLevel.UI_HEAVY,
        base_timeout_seconds=600,
        multiplier=3.0,
        description="UI views, charts, dashboards, SwiftUI",
        keywords=(
            "ui", "view", "swiftui", "chart", "dashboard", "widget",
            "component", "interface", "screen", "navigation", "tab",
            "list", "grid", "form", "button", "layout", "rendering"
        ),
    ),
}


def estimate_task_complexity(
    task: SelectedTask,
    custom_complexities: Optional[Dict[ComplexityLevel, TaskComplexity]] = None,
    custom_keywords: Optional[Dict[ComplexityLevel, Set[str]]] = None,
) -> TaskComplexity:
    """Estimate task complexity from task metadata.

    Uses keyword heuristics from title and acceptance criteria:
    - UI-heavy keywords → 3x multiplier (600s base)
    - Complex keywords → 2x multiplier (300s base)
    - Medium keywords → 1.5x multiplier (180s base)
    - Simple/unknown → 1x multiplier (60s base)

    Also considers acceptance criteria count:
    - > 5 criteria → bump up one level

    Args:
        task: The task to classify
        custom_complexities: Optional custom complexity definitions
        custom_keywords: Optional keyword overrides per level

    Returns:
        TaskComplexity classification for the task
    """
    # Use custom complexities if provided, otherwise use defaults
    complexities = custom_complexities or DEFAULT_COMPLEXITIES

    # Build searchable text from title (SelectedTask has no description field)
    searchable_text = task.title.lower()

    # Also search acceptance criteria
    if task.acceptance:
        searchable_text += " " + " ".join(task.acceptance).lower()

    # Score each complexity level by keyword matches
    scores: Dict[ComplexityLevel, int] = {level: 0 for level in ComplexityLevel}

    for level, complexity in complexities.items():
        # Use custom keywords if provided, otherwise use defaults
        keywords = set(complexity.keywords)
        if custom_keywords and level in custom_keywords:
            keywords = custom_keywords[level]

        # Count keyword matches
        for keyword in keywords:
            if keyword.lower() in searchable_text:
                scores[level] += 1

    # Find the level with highest score
    best_level = max(scores.items(), key=lambda x: x[1])[0]

    # Bump up one level if many acceptance criteria (> 5)
    if task.acceptance and len(task.acceptance) > 5:
        level_order = [ComplexityLevel.SIMPLE, ComplexityLevel.MEDIUM, ComplexityLevel.COMPLEX, ComplexityLevel.UI_HEAVY]
        current_index = level_order.index(best_level)
        if current_index < len(level_order) - 1:
            best_level = level_order[current_index + 1]

    return complexities[best_level]


def calculate_adaptive_timeout(
    task: SelectedTask,
    previous_failures: int,
    config: AdaptiveTimeoutConfig,
    mode_timeout: Optional[int] = None,
) -> int:
    """Calculate adaptive timeout for task attempt.

    Formula:
        base_timeout = mode_timeout or config.default_mode_timeout
        complexity_multiplier = estimate_task_complexity(task).multiplier
        failure_multiplier = config.timeout_multiplier_per_failure ** previous_failures
        timeout = base_timeout × complexity_multiplier × failure_multiplier
        timeout = clamp(timeout, config.min_timeout, config.max_timeout)

    Args:
        task: The task being attempted
        previous_failures: Number of previous timeout failures for this task
        config: Adaptive timeout configuration
        mode_timeout: Base timeout from loop mode (speed/quality/exploration)

    Returns:
        Calculated timeout in seconds
    """
    if not config.enabled:
        return mode_timeout or config.default_mode_timeout

    # Get base timeout from mode or config default
    base_timeout = mode_timeout or config.default_mode_timeout

    # Start with base timeout
    timeout = float(base_timeout)

    # Apply complexity scaling if enabled
    if config.enable_complexity_scaling:
        complexity = estimate_task_complexity(task)
        timeout *= complexity.multiplier

    # Apply failure scaling if enabled
    if config.enable_failure_scaling and previous_failures > 0:
        failure_multiplier = config.timeout_multiplier_per_failure ** previous_failures
        timeout *= failure_multiplier

    # Clamp to configured bounds
    timeout = max(config.min_timeout, min(int(timeout), config.max_timeout))

    return timeout


def get_timeout_suggestion(
    task: SelectedTask,
    current_timeout: int,
    previous_failures: int,
    config: AdaptiveTimeoutConfig,
) -> str:
    """Get human-readable suggestion for timeout adjustment.

    Args:
        task: The task being attempted
        current_timeout: Current timeout in seconds
        previous_failures: Number of previous failures
        config: Adaptive timeout configuration

    Returns:
        Human-readable suggestion string
    """
    complexity = estimate_task_complexity(task)

    suggested = calculate_adaptive_timeout(
        task=task,
        previous_failures=previous_failures,
        config=config,
        mode_timeout=current_timeout,
    )

    if suggested <= current_timeout:
        return f"Current timeout ({current_timeout}s) is appropriate for {complexity.level.value} task."

    if previous_failures > 0:
        return (
            f"Task timed out {previous_failures} time(s). "
            f"Suggested timeout: {suggested}s (was {current_timeout}s). "
            f"This is a {complexity.level.value} task ({complexity.description})."
        )

    return (
        f"This {complexity.level.value} task may need more time. "
        f"Suggested timeout: {suggested}s (was {current_timeout}s)."
    )


def classify_batch_tasks(
    tasks: List[SelectedTask],
) -> Dict[ComplexityLevel, List[SelectedTask]]:
    """Classify multiple tasks by complexity level.

    Useful for:
    - Identifying which tasks need more time
    - Balancing task selection (mix simple and complex)
    - Batch unblock operations

    Args:
        tasks: List of tasks to classify

    Returns:
        Dictionary mapping complexity level to list of tasks
    """
    result: Dict[ComplexityLevel, List[SelectedTask]] = {
        level: [] for level in ComplexityLevel
    }

    for task in tasks:
        complexity = estimate_task_complexity(task)
        result[complexity.level].append(task)

    return result
