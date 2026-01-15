from __future__ import annotations

from pathlib import Path

from ralph_gold.trackers import BeadsTracker


def test_beads_peek_does_not_claim(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    tracker = BeadsTracker(project_root=tmp_path, ready_args=["ready", "--json"])

    def fake_ready_json():
        return [{"id": "bd-1", "title": "Example"}]

    def fake_run(argv):
        calls.append(argv)
        class Dummy:
            returncode = 0
            stdout = "[]"
            stderr = ""
        return Dummy()

    tracker._ready_json = fake_ready_json  # type: ignore[assignment]
    tracker._run = fake_run  # type: ignore[assignment]

    task = tracker.peek_next_task()
    assert task is not None
    assert task.id == "bd-1"

    # No update/claim should have been issued.
    assert not any("update" in part for call in calls for part in call)


def test_beads_claim_marks_in_progress(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    tracker = BeadsTracker(project_root=tmp_path, ready_args=["ready", "--json"])

    def fake_ready_json():
        return [{"id": "bd-2", "title": "Example 2"}]

    def fake_run(argv):
        calls.append(argv)
        class Dummy:
            returncode = 0
            stdout = "[]"
            stderr = ""
        return Dummy()

    tracker._ready_json = fake_ready_json  # type: ignore[assignment]
    tracker._run = fake_run  # type: ignore[assignment]

    task = tracker.claim_next_task()
    assert task is not None
    assert task.id == "bd-2"

    assert any("update" in part for call in calls for part in call)
