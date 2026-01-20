"""Service Level Objectives (SLO) module for Ralph Gold Loop.

This module provides:
- SLODefinition: Definition of a single SLO with target and description
- ErrorBudget: Calculates remaining error budget based on SLO compliance
- ErrorBudgetTracker: Tracks multiple SLOs and calculates budgets

Phase 5: SLO tracking with error budget calculation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .metrics import MetricsSnapshot


@dataclass(frozen=True)
class SLODefinition:
    """Definition of a Service Level Objective.

    Attributes:
        name: Unique identifier for the SLO (e.g., "write_success_rate")
        target: Target value to achieve (0-1 for rates)
        description: Human-readable description of what this measures
    """
    name: str
    target: float
    description: str

    def __post_init__(self) -> None:
        """Validate SLO values."""
        if not 0 <= self.target <= 1:
            raise ValueError(
                f"SLO target must be between 0 and 1, got {self.target}"
            )


# Default SLOs for Ralph Gold Loop
DEFAULT_SLOS: List[SLODefinition] = [
    SLODefinition(
        name="write_success_rate",
        target=0.95,  # 95% target
        description="Percentage of iterations where files were written",
    ),
    SLODefinition(
        name="truncation_rate",
        target=0.10,  # Max 10% truncation rate
        description="Maximum percentage of spec characters truncated",
    ),
]


@dataclass(frozen=True)
class ErrorBudget:
    """Error budget for a single SLO.

    The error budget represents how much "failure" allowance remains
    before the SLO is considered breached.

    Attributes:
        slo_name: Name of the SLO this budget is for
        budget_remaining: Percentage of budget remaining (0-1)
        is_breached: Whether the SLO has been breached (budget <= 0)
        current_value: Current actual value for the metric
        target_value: The SLO target value
    """
    slo_name: str
    budget_remaining: float
    is_breached: bool
    current_value: float
    target_value: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "slo_name": self.slo_name,
            "budget_remaining": round(self.budget_remaining, 4),
            "is_breached": self.is_breached,
            "current_value": round(self.current_value, 4),
            "target_value": round(self.target_value, 4),
        }


@dataclass
class ErrorBudgetTracker:
    """Tracks SLOs and calculates error budgets.

    Usage:
        tracker = ErrorBudgetTracker()
        budgets = tracker.check_all_slos(metrics_snapshot)
        for budget in budgets:
            if budget.is_breached:
                print(f"SLO {budget.slo_name} BREACHED!")
    """

    slos: List[SLODefinition] = field(default_factory=lambda: DEFAULT_SLOS.copy())

    def calculate_budget_remaining(
        self,
        slo: SLODefinition,
        current_value: float,
        total_measurements: int,
    ) -> float:
        """Calculate remaining error budget for an SLO.

        For rate-based SLOs (higher is better), error budget is calculated as:
        - At/above target: full budget (1.0)
        - Below target: (current / target) - 1 (negative deficit)

        For threshold-based SLOs (lower is better, like truncation_rate):
        - At/below target: full budget (1.0)
        - Above target: 1 - (current / target) (negative overage)

        Args:
            slo: The SLO definition
            current_value: Current actual metric value
            total_measurements: Total number of data points

        Returns:
            Remaining budget as float between -1 and 1 (can be negative if breached)
        """
        if total_measurements == 0:
            return 1.0  # Full budget when no data

        # truncation_rate is special: lower is better (we want it <= target)
        if slo.name == "truncation_rate":
            # Lower is better
            if current_value <= slo.target:
                return 1.0  # Full budget for being within threshold
            else:
                # Above target - negative budget
                return 1.0 - (current_value / slo.target)
        else:
            # For other SLOs (like write_success_rate), higher is better
            if current_value >= slo.target:
                return 1.0  # Full budget for meeting/exceeding target
            else:
                # Below target - calculate deficit as negative proportion
                return (current_value / slo.target) - 1.0

    def is_breached(
        self,
        slo: SLODefinition,
        current_value: float,
        total_measurements: int = 1,
    ) -> bool:
        """Check if an SLO is currently breached.

        Args:
            slo: The SLO definition
            current_value: Current actual metric value
            total_measurements: Total number of data points

        Returns:
            True if the SLO is breached (budget <= 0), False otherwise
        """
        budget = self.calculate_budget_remaining(slo, current_value, total_measurements)
        return budget <= 0

    def check_single_slo(
        self,
        slo: SLODefinition,
        current_value: float,
        total_measurements: int = 1,
    ) -> ErrorBudget:
        """Check error budget for a single SLO.

        Args:
            slo: The SLO definition to check
            current_value: Current actual metric value
            total_measurements: Total number of data points

        Returns:
            ErrorBudget with status information
        """
        budget_remaining = self.calculate_budget_remaining(
            slo, current_value, total_measurements
        )
        is_breached = self.is_breached(slo, current_value, total_measurements)

        return ErrorBudget(
            slo_name=slo.name,
            budget_remaining=budget_remaining,
            is_breached=is_breached,
            current_value=current_value,
            target_value=slo.target,
        )

    def check_all_slos(self, snapshot: MetricsSnapshot) -> List[ErrorBudget]:
        """Check error budgets for all configured SLOs.

        Args:
            snapshot: Current metrics snapshot

        Returns:
            List of ErrorBudget objects, one per SLO
        """
        budgets: List[ErrorBudget] = []

        total_iterations = snapshot.total_iterations

        for slo in self.slos:
            current_value = 0.0

            # Map SLO names to snapshot values
            if slo.name == "write_success_rate":
                current_value = snapshot.write_success_rate
            elif slo.name == "truncation_rate":
                current_value = snapshot.truncation_rate
            else:
                # Unknown SLO - skip
                continue

            budget = self.check_single_slo(
                slo, current_value, total_iterations or 1
            )
            budgets.append(budget)

        return budgets

    def get_breached_slos(self, snapshot: MetricsSnapshot) -> List[ErrorBudget]:
        """Get only the SLOs that are currently breached.

        Args:
            snapshot: Current metrics snapshot

        Returns:
            List of breached ErrorBudget objects
        """
        all_budgets = self.check_all_slos(snapshot)
        return [b for b in all_budgets if b.is_breached]

    def add_slo(self, name: str, target: float, description: str) -> None:
        """Add a custom SLO to track.

        Args:
            name: Unique identifier for the SLO
            target: Target value (0-1 for rates)
            description: Human-readable description

        Raises:
            ValueError: If SLO with same name exists
        """
        # Check for duplicate names
        if any(s.name == name for s in self.slos):
            raise ValueError(f"SLO with name '{name}' already exists")

        self.slos.append(SLODefinition(name=name, target=target, description=description))

    def remove_slo(self, name: str) -> bool:
        """Remove an SLO by name.

        Args:
            name: Name of the SLO to remove

        Returns:
            True if SLO was found and removed, False otherwise
        """
        for i, slo in enumerate(self.slos):
            if slo.name == name:
                self.slos.pop(i)
                return True
        return False

    def get_summary(self, snapshot: MetricsSnapshot) -> Dict[str, Any]:
        """Get a summary of SLO status.

        Args:
            snapshot: Current metrics snapshot

        Returns:
            Dictionary with SLO status summary
        """
        budgets = self.check_all_slos(snapshot)

        breached_count = sum(1 for b in budgets if b.is_breached)
        total_count = len(budgets)

        return {
            "total_slos": total_count,
            "breached_slos": breached_count,
            "all_met": breached_count == 0,
            "budgets": [b.to_dict() for b in budgets],
        }
