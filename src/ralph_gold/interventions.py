"""
Adaptive Intervention Recommendation Engine.

Analyzes failure patterns from loop iterations and generates structured
recommendations for prompt/timeout/mode adjustments. All recommendations
are advisory-only in v1 (not auto-applied).

This module provides:
- Signal extraction from state history, receipts, and harness metrics
- Recommendation synthesis with confidence scoring
- Artifact persistence with schema versioning
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter

logger = logging.getLogger(__name__)

# Schema version for intervention artifacts
INTERVENTION_SCHEMA_VERSION = "1.0.0"

# Recommendation categories
CATEGORY_NO_FILES = "no_files_reinforcement"
CATEGORY_GATE_FAILURE = "gate_failure_pattern"
CATEGORY_TIMEOUT_CHURN = "timeout_churn"
CATEGORY_LOW_EVIDENCE = "low_evidence_completion"
CATEGORY_SYNTAX_ERROR = "syntax_error_pattern"

# Confidence levels
CONFIDENCE_LOW = "low"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_HIGH = "high"


@dataclass
class InterventionEvent:
    """Normalized failure signal from a single iteration."""
    iteration: int
    task_id: str
    no_files_written: bool = False
    gates_ok: Optional[bool] = None
    evidence_count: int = 0
    timed_out: bool = False
    syntax_error: bool = False
    dominant_failure: Optional[str] = None
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterventionEvent":
        return cls(**data)


@dataclass
class InterventionRecommendation:
    """Structured recommendation for iteration adjustment."""
    recommendation_id: str
    category: str
    rationale: str
    prompt_patch: Optional[str] = None
    timeout_hint: Optional[int] = None
    mode_hint: Optional[str] = None
    confidence: float = 0.5
    confidence_level: str = CONFIDENCE_MEDIUM
    source_evidence_paths: List[str] = field(default_factory=list)
    source_iterations: List[int] = field(default_factory=list)
    created_at: str = ""
    schema_version: str = INTERVENTION_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterventionRecommendation":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class InterventionProfile:
    """Profile containing intervention configuration and state."""
    schema: str = INTERVENTION_SCHEMA_VERSION
    policy_mode: str = "recommend-only"
    lookback_iterations: int = 30
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def generate_recommendation_id(category: str, task_id: str, timestamp: str) -> str:
    """Generate a unique recommendation ID."""
    ts = timestamp.replace(":", "-").replace(".", "-")[:19]
    return f"rec-{category[:8]}-{task_id}-{ts}"


def extract_signals_from_history(
    state_history: List[Dict[str, Any]],
    receipts_dir: Optional[Path] = None,
    lookback: int = 30,
) -> List[InterventionEvent]:
    """Extract normalized failure signals from state history.

    Args:
        state_history: List of iteration history entries from state.json
        receipts_dir: Optional path to receipts directory for additional signal extraction
        lookback: Number of recent iterations to analyze

    Returns:
        List of InterventionEvent objects representing failure signals
    """
    events = []

    # Take only the most recent iterations
    recent_history = state_history[-lookback:] if len(state_history) > lookback else state_history

    for entry in recent_history:
        if not isinstance(entry, dict):
            continue

        iteration = entry.get("iteration", 0)
        task_id = entry.get("story_id", "") or entry.get("task_id", "")

        # Skip entries without valid task IDs
        if not task_id:
            continue

        event = InterventionEvent(
            iteration=iteration,
            task_id=str(task_id),
            timestamp=entry.get("timestamp", "") or entry.get("ended_at", ""),
        )

        # Extract failure signals from entry
        runner_result = entry.get("runner_result", {}) or {}
        gate_results = entry.get("gate_results", []) or []

        # Check for no files written
        if runner_result.get("no_files_written") or entry.get("no_files_written"):
            event.no_files_written = True

        # Check gate status
        if gate_results:
            event.gates_ok = all(
                g.get("return_code", 0) == 0 for g in gate_results if isinstance(g, dict)
            )
        elif "gates_ok" in entry:
            event.gates_ok = entry["gates_ok"]

        # Check for timeout
        if runner_result.get("timed_out") or entry.get("timed_out"):
            event.timed_out = True

        # Extract evidence count
        evidence = entry.get("evidence", {}) or {}
        event.evidence_count = len(evidence.get("files", [])) if isinstance(evidence, dict) else 0

        # Determine dominant failure
        failures = []
        if event.no_files_written:
            failures.append(CATEGORY_NO_FILES)
        if event.gates_ok is False:
            failures.append(CATEGORY_GATE_FAILURE)
        if event.timed_out:
            failures.append(CATEGORY_TIMEOUT_CHURN)
        if event.evidence_count == 0 and event.gates_ok is True:
            failures.append(CATEGORY_LOW_EVIDENCE)

        # Check for syntax errors in gate results
        for g in gate_results:
            if isinstance(g, dict) and "syntax" in g.get("cmd", "").lower():
                if g.get("return_code", 0) != 0:
                    event.syntax_error = True
                    failures.append(CATEGORY_SYNTAX_ERROR)
                    break

        if failures:
            event.dominant_failure = failures[0]  # Primary failure
            events.append(event)

    return events


def classify_failure_pattern(
    events: List[InterventionEvent],
    task_id: Optional[str] = None,
) -> Tuple[str, int, float]:
    """Classify the dominant failure pattern from events.

    Args:
        events: List of intervention events
        task_id: Optional task ID to filter events

    Returns:
        Tuple of (category, count, confidence)
    """
    if task_id:
        events = [e for e in events if e.task_id == task_id]

    if not events:
        return "", 0, 0.0

    # Count failure categories
    categories = [e.dominant_failure for e in events if e.dominant_failure]
    if not categories:
        return "", 0, 0.0

    counter = Counter(categories)
    dominant, count = counter.most_common(1)[0]

    # Calculate confidence based on frequency
    confidence = min(1.0, count / max(len(events), 1))

    return dominant, count, confidence


def generate_recommendation(
    category: str,
    task_id: str,
    count: int,
    confidence: float,
    source_iterations: List[int],
    source_evidence_paths: List[str],
) -> Optional[InterventionRecommendation]:
    """Generate a recommendation based on failure pattern.

    Args:
        category: Failure category
        task_id: Task ID
        count: Number of occurrences
        confidence: Confidence score (0-1)
        source_iterations: List of source iteration numbers
        source_evidence_paths: List of evidence file paths

    Returns:
        InterventionRecommendation or None if no recommendation applicable
    """
    if not category:
        return None

    timestamp = utc_now_iso()
    rec_id = generate_recommendation_id(category, task_id, timestamp)

    # Determine confidence level
    if confidence >= 0.7:
        confidence_level = CONFIDENCE_HIGH
    elif confidence >= 0.4:
        confidence_level = CONFIDENCE_MEDIUM
    else:
        confidence_level = CONFIDENCE_LOW

    # Build recommendation based on category
    rationale = ""
    prompt_patch = None
    timeout_hint = None
    mode_hint = None

    if category == CATEGORY_NO_FILES:
        rationale = f"Task {task_id} has had {count} iterations with no files written. Consider adding explicit file output requirements."
        prompt_patch = "IMPORTANT: You must write at least one file to complete this task. Ensure you create or modify the necessary files before exiting."
        timeout_hint = None  # No timeout adjustment needed

    elif category == CATEGORY_GATE_FAILURE:
        rationale = f"Task {task_id} has failed gates {count} times. Review gate failures and ensure all quality checks pass."
        prompt_patch = "Ensure all modified files pass syntax checks and tests before marking complete."

    elif category == CATEGORY_TIMEOUT_CHURN:
        rationale = f"Task {task_id} has timed out {count} times. Consider increasing timeout or simplifying the task."
        timeout_hint = 600  # Suggest 10 minutes extra
        mode_hint = "quality"  # Quality mode has longer timeouts

    elif category == CATEGORY_LOW_EVIDENCE:
        rationale = f"Task {task_id} completed with no evidence files {count} times. Verify work was actually done."
        prompt_patch = "Provide evidence of your work by creating test files or documentation."

    elif category == CATEGORY_SYNTAX_ERROR:
        rationale = f"Task {task_id} introduced syntax errors {count} times. Be more careful with string literals and indentation."
        prompt_patch = "Run syntax checks on your changes before marking complete. Be especially careful with multi-line strings."

    else:
        return None

    return InterventionRecommendation(
        recommendation_id=rec_id,
        category=category,
        rationale=rationale,
        prompt_patch=prompt_patch,
        timeout_hint=timeout_hint,
        mode_hint=mode_hint,
        confidence=confidence,
        confidence_level=confidence_level,
        source_evidence_paths=source_evidence_paths,
        source_iterations=source_iterations,
        created_at=timestamp,
    )


def synthesize_recommendation(
    state_history: List[Dict[str, Any]],
    task_id: Optional[str] = None,
    receipts_dir: Optional[Path] = None,
    lookback: int = 30,
    confidence_threshold: str = CONFIDENCE_MEDIUM,
) -> Optional[InterventionRecommendation]:
    """Synthesize a recommendation from recent failure patterns.

    This is the main entry point for recommendation generation.

    Args:
        state_history: List of iteration history entries
        task_id: Optional task ID to focus recommendation
        receipts_dir: Optional receipts directory path
        lookback: Number of iterations to analyze
        confidence_threshold: Minimum confidence level to emit recommendation

    Returns:
        InterventionRecommendation or None if no significant pattern found
    """
    # Extract signals
    events = extract_signals_from_history(
        state_history, receipts_dir, lookback
    )

    if not events:
        return None

    # Classify failure pattern
    category, count, confidence = classify_failure_pattern(events, task_id)

    if not category or count < 2:
        return None  # Need at least 2 occurrences for a pattern

    # Check confidence threshold
    threshold_map = {CONFIDENCE_LOW: 0.0, CONFIDENCE_MEDIUM: 0.3, CONFIDENCE_HIGH: 0.6}
    min_confidence = threshold_map.get(confidence_threshold, 0.3)

    if confidence < min_confidence:
        return None

    # Build source evidence paths
    source_iterations = [e.iteration for e in events if e.dominant_failure == category][:5]
    source_evidence_paths = []
    if receipts_dir:
        for iter_num in source_iterations:
            receipt_path = receipts_dir / f"iter{iter_num:04d}" / "runner.json"
            if receipt_path.exists():
                source_evidence_paths.append(str(receipt_path))

    # Generate recommendation
    target_task = task_id or (events[0].task_id if events else "unknown")

    return generate_recommendation(
        category=category,
        task_id=target_task,
        count=count,
        confidence=confidence,
        source_iterations=source_iterations,
        source_evidence_paths=source_evidence_paths,
    )


# Artifact persistence functions

def ensure_interventions_dir(project_root: Path) -> Path:
    """Ensure interventions directory exists and return path."""
    interventions_dir = project_root / ".ralph" / "interventions"
    interventions_dir.mkdir(parents=True, exist_ok=True)
    return interventions_dir


def write_profile(interventions_dir: Path, profile: InterventionProfile) -> None:
    """Write intervention profile to disk."""
    profile_path = interventions_dir / "profile.json"
    profile.updated_at = utc_now_iso()

    # Atomic write
    temp_path = profile_path.with_suffix(".tmp")
    try:
        temp_path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
        os.replace(temp_path, profile_path)
    except Exception as e:
        logger.warning(f"Failed to write intervention profile: {e}")
        if temp_path.exists():
            temp_path.unlink()


def read_profile(interventions_dir: Path) -> Optional[InterventionProfile]:
    """Read intervention profile from disk."""
    profile_path = interventions_dir / "profile.json"
    if not profile_path.exists():
        return None

    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        return InterventionProfile(**data)
    except Exception as e:
        logger.warning(f"Failed to read intervention profile: {e}")
        return None


def append_event(interventions_dir: Path, event: InterventionEvent) -> None:
    """Append an event to the events log (JSONL format)."""
    events_path = interventions_dir / "events.jsonl"

    try:
        with events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict()) + "\n")
    except Exception as e:
        logger.warning(f"Failed to append intervention event: {e}")


def read_events(interventions_dir: Path, limit: int = 100) -> List[InterventionEvent]:
    """Read recent events from the events log."""
    events_path = interventions_dir / "events.jsonl"
    if not events_path.exists():
        return []

    events = []
    try:
        with events_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-limit:]  # Read only last N lines
            for line in lines:
                line = line.strip()
                if line:
                    events.append(InterventionEvent.from_dict(json.loads(line)))
    except Exception as e:
        logger.warning(f"Failed to read intervention events: {e}")

    return events


def write_recommendation(
    interventions_dir: Path,
    recommendation: InterventionRecommendation
) -> Path:
    """Write recommendation to disk and return path."""
    # Write as latest recommendation
    latest_path = interventions_dir / "latest-recommendation.json"

    # Also write to history with ID as filename
    history_path = interventions_dir / f"{recommendation.recommendation_id}.json"

    content = json.dumps(recommendation.to_dict(), indent=2)

    try:
        # Write latest
        temp_latest = latest_path.with_suffix(".tmp")
        temp_latest.write_text(content, encoding="utf-8")
        os.replace(temp_latest, latest_path)

        # Write history
        temp_history = history_path.with_suffix(".tmp")
        temp_history.write_text(content, encoding="utf-8")
        os.replace(temp_history, history_path)

        return latest_path
    except Exception as e:
        logger.warning(f"Failed to write recommendation: {e}")
        raise


def read_latest_recommendation(interventions_dir: Path) -> Optional[InterventionRecommendation]:
    """Read the latest recommendation from disk."""
    latest_path = interventions_dir / "latest-recommendation.json"
    if not latest_path.exists():
        return None

    try:
        data = json.loads(latest_path.read_text(encoding="utf-8"))
        return InterventionRecommendation.from_dict(data)
    except Exception as e:
        logger.warning(f"Failed to read latest recommendation: {e}")
        return None


def list_recommendations(
    interventions_dir: Path,
    limit: int = 20
) -> List[InterventionRecommendation]:
    """List recent recommendations."""
    recommendations = []

    # Find all recommendation files (excluding latest)
    rec_files = sorted(
        interventions_dir.glob("rec-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )[:limit]

    for rec_file in rec_files:
        try:
            data = json.loads(rec_file.read_text(encoding="utf-8"))
            recommendations.append(InterventionRecommendation.from_dict(data))
        except Exception as e:
            logger.debug(f"Failed to read recommendation {rec_file}: {e}")

    return recommendations


def cleanup_old_recommendations(
    interventions_dir: Path,
    retention_days: int = 30
) -> int:
    """Remove recommendations older than retention period.

    Returns:
        Number of files removed
    """
    import time

    cutoff = time.time() - (retention_days * 86400)
    removed = 0

    for rec_file in interventions_dir.glob("rec-*.json"):
        try:
            if rec_file.stat().st_mtime < cutoff:
                rec_file.unlink()
                removed += 1
        except Exception as e:
            logger.debug(f"Failed to check/remove {rec_file}: {e}")

    return removed


def format_recommendation_summary(recommendation: InterventionRecommendation) -> str:
    """Format a recommendation for human-readable output."""
    # Extract task ID from recommendation ID safely
    parts = recommendation.recommendation_id.split('-')
    task_id = parts[2] if len(parts) >= 3 else 'unknown'

    lines = [
        f"Category: {recommendation.category}",
        f"Confidence: {recommendation.confidence_level} ({recommendation.confidence:.0%})",
        f"Task: {task_id}",
        "",
        f"Rationale: {recommendation.rationale}",
    ]

    if recommendation.prompt_patch:
        lines.append("")
        lines.append("Suggested prompt addition:")
        lines.append(f"  {recommendation.prompt_patch}")

    if recommendation.timeout_hint:
        lines.append("")
        lines.append(f"Timeout hint: {recommendation.timeout_hint}s")

    if recommendation.mode_hint:
        lines.append(f"Mode hint: {recommendation.mode_hint}")

    lines.append("")
    lines.append(f"Created: {recommendation.created_at}")

    return "\n".join(lines)
