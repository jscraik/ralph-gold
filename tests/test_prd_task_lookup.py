from __future__ import annotations

import json
from pathlib import Path

from ralph_gold.prd import select_task_by_id, task_status_by_id


def test_markdown_task_lookup_and_status(tmp_path: Path) -> None:
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
