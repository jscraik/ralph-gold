"""Tests for intervention engine."""

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone

from ralph_gold.interventions import (
    InterventionEvent,
    InterventionRecommendation,
    InterventionProfile,
    extract_signals_from_history,
    classify_failure_pattern,
    generate_recommendation,
    synthesize_recommendation,
    generate_recommendation_id,
    format_recommendation_summary,
    ensure_interventions_dir,
    write_profile,
    read_profile,
    append_event,
    read_events,
    write_recommendation,
    read_latest_recommendation,
    list_recommendations,
    CATEGORY_NO_FILES,
    CATEGORY_GATE_FAILURE,
    CATEGORY_TIMEOUT_CHURN,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_HIGH,
)
from ralph_gold.config import InterventionConfig


class TestInterventionEvent:
    """Tests for InterventionEvent dataclass."""

    def test_event_creation(self) -> None:
        """Test basic event creation."""
        event = InterventionEvent(
            iteration=1,
            task_id="task-1",
            no_files_written=True,
            gates_ok=False,
            evidence_count=0,
        )
        assert event.iteration == 1
        assert event.task_id == "task-1"
        assert event.no_files_written is True
        assert event.gates_ok is False

    def test_event_to_dict(self) -> None:
        """Test event serialization."""
        event = InterventionEvent(
            iteration=1,
            task_id="task-1",
            no_files_written=True,
            dominant_failure=CATEGORY_NO_FILES,
        )
        data = event.to_dict()
        assert data["iteration"] == 1
        assert data["task_id"] == "task-1"
        assert data["no_files_written"] is True

    def test_event_from_dict(self) -> None:
        """Test event deserialization."""
        data = {
            "iteration": 2,
            "task_id": "task-2",
            "no_files_written": False,
            "gates_ok": True,
            "evidence_count": 3,
            "timed_out": False,
            "syntax_error": False,
            "dominant_failure": None,
            "timestamp": "",
        }
        event = InterventionEvent.from_dict(data)
        assert event.iteration == 2
        assert event.task_id == "task-2"
        assert event.gates_ok is True
        assert event.evidence_count == 3


class TestInterventionRecommendation:
    """Tests for InterventionRecommendation dataclass."""

    def test_recommendation_creation(self) -> None:
        """Test basic recommendation creation."""
        rec = InterventionRecommendation(
            recommendation_id="rec-test-123",
            category=CATEGORY_NO_FILES,
            rationale="Test rationale",
            confidence=0.8,
        )
        assert rec.recommendation_id == "rec-test-123"
        assert rec.category == CATEGORY_NO_FILES
        assert rec.confidence == 0.8

    def test_recommendation_serialization(self) -> None:
        """Test recommendation round-trip serialization."""
        rec = InterventionRecommendation(
            recommendation_id="rec-test-456",
            category=CATEGORY_GATE_FAILURE,
            rationale="Gate failed",
            prompt_patch="Fix the gate",
            timeout_hint=600,
            confidence=0.9,
            confidence_level=CONFIDENCE_HIGH,
        )
        data = rec.to_dict()
        rec2 = InterventionRecommendation.from_dict(data)
        assert rec2.recommendation_id == rec.recommendation_id
        assert rec2.category == rec.category
        assert rec2.prompt_patch == rec.prompt_patch
        assert rec2.timeout_hint == rec.timeout_hint


class TestSignalExtraction:
    """Tests for signal extraction from history."""

    def test_extract_signals_empty_history(self) -> None:
        """Test extraction with empty history."""
        events = extract_signals_from_history([])
        assert events == []

    def test_extract_signals_no_failures(self) -> None:
        """Test extraction with successful iterations."""
        history = [
            {"iteration": 1, "story_id": "task-1", "gates_ok": True, "evidence": {"files": ["test.py"]}},
            {"iteration": 2, "story_id": "task-2", "gates_ok": True, "evidence": {"files": ["test2.py"]}},
        ]
        events = extract_signals_from_history(history)
        assert len(events) == 0  # No failure events

    def test_extract_signals_with_no_files(self) -> None:
        """Test extraction with no_files_written flag."""
        history = [
            {"iteration": 1, "story_id": "task-1", "no_files_written": True},
        ]
        events = extract_signals_from_history(history)
        assert len(events) == 1
        assert events[0].no_files_written is True
        assert events[0].dominant_failure == CATEGORY_NO_FILES

    def test_extract_signals_with_gate_failure(self) -> None:
        """Test extraction with gate failures."""
        history = [
            {
                "iteration": 1,
                "story_id": "task-1",
                "gate_results": [{"return_code": 1}],
            },
        ]
        events = extract_signals_from_history(history)
        assert len(events) == 1
        assert events[0].gates_ok is False

    def test_extract_signals_lookback_limit(self) -> None:
        """Test that lookback limits history analysis."""
        history = [
            {"iteration": i, "story_id": f"task-{i}", "no_files_written": True}
            for i in range(50)
        ]
        events = extract_signals_from_history(history, lookback=10)
        # Only last 10 should be analyzed
        assert len(events) == 10


class TestFailureClassification:
    """Tests for failure pattern classification."""

    def test_classify_empty_events(self) -> None:
        """Test classification with no events."""
        category, count, confidence = classify_failure_pattern([])
        assert category == ""
        assert count == 0
        assert confidence == 0.0

    def test_classify_single_category(self) -> None:
        """Test classification with single failure type."""
        events = [
            InterventionEvent(iteration=1, task_id="t1", no_files_written=True, dominant_failure=CATEGORY_NO_FILES),
            InterventionEvent(iteration=2, task_id="t1", no_files_written=True, dominant_failure=CATEGORY_NO_FILES),
            InterventionEvent(iteration=3, task_id="t1", no_files_written=True, dominant_failure=CATEGORY_NO_FILES),
        ]
        category, count, confidence = classify_failure_pattern(events)
        assert category == CATEGORY_NO_FILES
        assert count == 3
        assert confidence == 1.0

    def test_classify_mixed_categories(self) -> None:
        """Test classification with mixed failure types."""
        events = [
            InterventionEvent(iteration=1, task_id="t1", dominant_failure=CATEGORY_NO_FILES),
            InterventionEvent(iteration=2, task_id="t1", dominant_failure=CATEGORY_NO_FILES),
            InterventionEvent(iteration=3, task_id="t1", dominant_failure=CATEGORY_GATE_FAILURE),
        ]
        category, count, confidence = classify_failure_pattern(events)
        assert category == CATEGORY_NO_FILES  # Most common
        assert count == 2

    def test_classify_filter_by_task(self) -> None:
        """Test classification filtered by task ID."""
        events = [
            InterventionEvent(iteration=1, task_id="task-1", dominant_failure=CATEGORY_NO_FILES),
            InterventionEvent(iteration=2, task_id="task-2", dominant_failure=CATEGORY_GATE_FAILURE),
        ]
        category, count, confidence = classify_failure_pattern(events, task_id="task-1")
        assert category == CATEGORY_NO_FILES
        assert count == 1


class TestRecommendationGeneration:
    """Tests for recommendation generation."""

    def test_generate_no_files_recommendation(self) -> None:
        """Test recommendation for no-files pattern."""
        rec = generate_recommendation(
            category=CATEGORY_NO_FILES,
            task_id="task-1",
            count=3,
            confidence=0.8,
            source_iterations=[1, 2, 3],
            source_evidence_paths=[],
        )
        assert rec is not None
        assert rec.category == CATEGORY_NO_FILES
        assert "no files" in rec.rationale.lower()
        assert rec.prompt_patch is not None

    def test_generate_timeout_recommendation(self) -> None:
        """Test recommendation for timeout pattern."""
        rec = generate_recommendation(
            category=CATEGORY_TIMEOUT_CHURN,
            task_id="task-2",
            count=2,
            confidence=0.6,
            source_iterations=[1, 2],
            source_evidence_paths=[],
        )
        assert rec is not None
        assert rec.category == CATEGORY_TIMEOUT_CHURN
        assert rec.timeout_hint == 600
        assert rec.mode_hint == "quality"

    def test_generate_unknown_category(self) -> None:
        """Test that unknown category returns None."""
        rec = generate_recommendation(
            category="unknown_category",
            task_id="task-1",
            count=1,
            confidence=0.5,
            source_iterations=[1],
            source_evidence_paths=[],
        )
        assert rec is None


class TestSynthesizeRecommendation:
    """Tests for recommendation synthesis."""

    def test_synthesize_no_pattern(self) -> None:
        """Test synthesis with no failure pattern."""
        history = [
            {"iteration": 1, "story_id": "task-1", "gates_ok": True},
        ]
        rec = synthesize_recommendation(history)
        assert rec is None

    def test_synthesize_single_occurrence(self) -> None:
        """Test that single occurrence doesn't trigger recommendation."""
        history = [
            {"iteration": 1, "story_id": "task-1", "no_files_written": True},
        ]
        rec = synthesize_recommendation(history)
        assert rec is None  # Need at least 2 occurrences

    def test_synthesize_with_pattern(self) -> None:
        """Test synthesis with clear failure pattern."""
        history = [
            {"iteration": i, "story_id": "task-1", "no_files_written": True}
            for i in range(3)
        ]
        rec = synthesize_recommendation(history)
        assert rec is not None
        assert rec.category == CATEGORY_NO_FILES

    def test_synthesize_with_confidence_threshold(self) -> None:
        """Test confidence threshold filtering."""
        history = [
            {"iteration": i, "story_id": "task-1", "no_files_written": True}
            for i in range(5)
        ]
        # High confidence - should pass (5/5 = 100%)
        rec = synthesize_recommendation(history, confidence_threshold=CONFIDENCE_HIGH)
        assert rec is not None

        # Now test with mixed history - low confidence
        mixed_history = [
            {"iteration": 1, "story_id": "task-1", "no_files_written": True},
            {"iteration": 2, "story_id": "task-1"},  # No failure
            {"iteration": 3, "story_id": "task-1"},  # No failure
        ]
        rec = synthesize_recommendation(mixed_history, confidence_threshold=CONFIDENCE_HIGH)
        assert rec is None  # Only 1/3 = 33% confidence


class TestArtifactPersistence:
    """Tests for artifact persistence."""

    def test_ensure_interventions_dir(self, tmp_path: Path) -> None:
        """Test directory creation."""
        interventions_dir = ensure_interventions_dir(tmp_path)
        assert interventions_dir.exists()
        assert interventions_dir.name == "interventions"

    def test_write_and_read_profile(self, tmp_path: Path) -> None:
        """Test profile persistence."""
        interventions_dir = ensure_interventions_dir(tmp_path)
        profile = InterventionProfile(
            policy_mode="recommend-only",
            lookback_iterations=30,
        )
        write_profile(interventions_dir, profile)

        loaded = read_profile(interventions_dir)
        assert loaded is not None
        assert loaded.policy_mode == "recommend-only"
        assert loaded.lookback_iterations == 30

    def test_append_and_read_events(self, tmp_path: Path) -> None:
        """Test event log persistence."""
        interventions_dir = ensure_interventions_dir(tmp_path)

        event1 = InterventionEvent(iteration=1, task_id="task-1", no_files_written=True)
        event2 = InterventionEvent(iteration=2, task_id="task-1", gates_ok=False)

        append_event(interventions_dir, event1)
        append_event(interventions_dir, event2)

        events = read_events(interventions_dir)
        assert len(events) == 2
        assert events[0].iteration == 1
        assert events[1].iteration == 2

    def test_write_and_read_recommendation(self, tmp_path: Path) -> None:
        """Test recommendation persistence."""
        interventions_dir = ensure_interventions_dir(tmp_path)

        rec = InterventionRecommendation(
            recommendation_id="rec-test-123",
            category=CATEGORY_NO_FILES,
            rationale="Test rationale",
            confidence=0.8,
        )

        write_recommendation(interventions_dir, rec)

        loaded = read_latest_recommendation(interventions_dir)
        assert loaded is not None
        assert loaded.recommendation_id == "rec-test-123"

    def test_list_recommendations(self, tmp_path: Path) -> None:
        """Test listing multiple recommendations."""
        interventions_dir = ensure_interventions_dir(tmp_path)

        for i in range(3):
            rec = InterventionRecommendation(
                recommendation_id=f"rec-test-{i}",
                category=CATEGORY_NO_FILES,
                rationale=f"Rationale {i}",
                confidence=0.5,
            )
            write_recommendation(interventions_dir, rec)

        recs = list_recommendations(interventions_dir)
        assert len(recs) == 3


class TestInterventionConfig:
    """Tests for InterventionConfig."""

    def test_config_defaults(self) -> None:
        """Test default configuration values."""
        config = InterventionConfig()
        assert config.enabled is False
        assert config.policy_mode == "recommend-only"
        assert config.lookback_iterations == 30
        assert config.confidence_threshold == "medium"

    def test_config_custom_values(self) -> None:
        """Test custom configuration values."""
        config = InterventionConfig(
            enabled=True,
            lookback_iterations=50,
            confidence_threshold="high",
        )
        assert config.enabled is True
        assert config.lookback_iterations == 50
        assert config.confidence_threshold == "high"


class TestFormatSummary:
    """Tests for recommendation formatting."""

    def test_format_basic(self) -> None:
        """Test basic formatting."""
        rec = InterventionRecommendation(
            recommendation_id="rec-test",
            category=CATEGORY_NO_FILES,
            rationale="Test rationale",
            confidence=0.8,
            confidence_level=CONFIDENCE_HIGH,
        )
        summary = format_recommendation_summary(rec)
        assert "no_files" in summary
        assert "high" in summary.lower()
        assert "Test rationale" in summary

    def test_format_with_hints(self) -> None:
        """Test formatting with timeout and mode hints."""
        rec = InterventionRecommendation(
            recommendation_id="rec-test",
            category=CATEGORY_TIMEOUT_CHURN,
            rationale="Timed out",
            confidence=0.6,
            timeout_hint=600,
            mode_hint="quality",
        )
        summary = format_recommendation_summary(rec)
        assert "600s" in summary
        assert "quality" in summary
