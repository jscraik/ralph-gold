from __future__ import annotations

import json
from pathlib import Path

from ralph_gold.prd import (
    force_task_open,
    get_quick_batch,
    select_task_by_id,
    task_status_by_id,
)


def test_markdown_get_quick_batch(tmp_path: Path) -> None:
    prd_path = tmp_path / "PRD.md"
    prd_path.write_text(
        """# PRD

## Tasks

- [x] Done task
- [ ] [QUICK] Quick 1
- [ ] Regular task
- [ ] [QUICK] Quick 2
- [ ] [QUICK] Blocked Quick
  - Depends on: 3
""",
        encoding="utf-8",
    )

    batch = get_quick_batch(prd_path, limit=3)
    assert batch is not None
    assert len(batch) == 2
    assert batch[0].title == "[QUICK] Quick 1"
    assert batch[1].title == "[QUICK] Quick 2"
    # Blocked Quick should not be in batch because it depends on 3 (Regular task) which is not done


def test_json_get_quick_batch(tmp_path: Path) -> None:
    prd_path = tmp_path / "PRD.json"
    prd_path.write_text(
        json.dumps(
            {
                "stories": [
                    {"id": "1", "title": "[QUICK] Quick 1"},
                    {"id": "2", "title": "Regular task"},
                    {"id": "3", "title": "[QUICK] Quick 2"},
                ]
            }
        ),
        encoding="utf-8",
    )

    batch = get_quick_batch(prd_path, limit=2)
    assert batch is not None
    assert len(batch) == 2
    assert batch[0].title == "[QUICK] Quick 1"
    assert batch[1].title == "[QUICK] Quick 2"
    prd_path = tmp_path / "PRD.md"
    prd_path.write_text(
        """# PRD

## Tasks

- [x] Done task
- [-] Blocked task
- [ ] Open task
""",
        encoding="utf-8",
    )

    selected = select_task_by_id(prd_path, "3")
    assert selected is not None
    assert selected.id == "3"
    assert selected.title == "Open task"

    assert task_status_by_id(prd_path, "1") == "done"
    assert task_status_by_id(prd_path, "2") == "blocked"
    assert task_status_by_id(prd_path, "3") == "open"
    assert task_status_by_id(prd_path, "999") == "missing"


def test_json_task_lookup_and_status(tmp_path: Path) -> None:
    prd_path = tmp_path / "PRD.json"
    prd_path.write_text(
        json.dumps(
            {
                "stories": [
                    {"id": "a", "title": "Done by passes", "passes": True},
                    {"id": "b", "title": "Blocked by status", "status": "blocked"},
                    {"story_id": "c", "title": "Open by story_id"},
                ]
            }
        ),
        encoding="utf-8",
    )

    selected = select_task_by_id(prd_path, "c")
    assert selected is not None
    assert selected.id == "c"
    assert selected.title == "Open by story_id"

    assert task_status_by_id(prd_path, "a") == "done"
    assert task_status_by_id(prd_path, "b") == "blocked"
    assert task_status_by_id(prd_path, "c") == "open"
    assert task_status_by_id(prd_path, "missing") == "missing"


def test_force_task_open_reopens_blocked_markdown_task(tmp_path: Path) -> None:
    prd_path = tmp_path / "PRD.md"
    prd_path.write_text(
        """# PRD

## Tasks

- [x] Done task
- [-] Blocked task
""",
        encoding="utf-8",
    )

    changed = force_task_open(prd_path, "2")
    assert changed is True
    assert task_status_by_id(prd_path, "2") == "open"


def test_force_task_open_reopens_blocked_json_story(tmp_path: Path) -> None:
    prd_path = tmp_path / "PRD.json"
    prd_path.write_text(
        json.dumps(
            {
                "stories": [
                    {"id": "a", "title": "Blocked story", "status": "blocked"},
                ]
            }
        ),
        encoding="utf-8",
    )

    changed = force_task_open(prd_path, "a")
    assert changed is True
    assert task_status_by_id(prd_path, "a") == "open"
