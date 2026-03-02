"""Unit tests for the PRD update gate."""

import pytest
from pathlib import Path
from ralph_gold.loop import _check_prd_update

def test_prd_update_gate_passes_when_marked_done(tmp_path: Path):
    """Test that the gate passes when a task is marked as done with [x]."""
    project_root = tmp_path
    prd_path = project_root / "PRD.md"
    task_id = "42"
    
    # Task marked done with [x]
    prd_path.write_text("- [x] Task 42\n", encoding="utf-8")
    
    ok, message = _check_prd_update(project_root, prd_path, task_id)
    assert ok is True
    assert "marked done" in message

def test_prd_update_gate_passes_when_checkbox_nearby(tmp_path: Path):
    """Test that the gate passes when the checkbox is on the same line as the ID."""
    project_root = tmp_path
    prd_path = project_root / "PRD.md"
    task_id = "S42"
    
    # Task marked done with [x] and id in text
    prd_path.write_text("- [x] Implement feature S42\n", encoding="utf-8")
    
    ok, message = _check_prd_update(project_root, prd_path, task_id)
    assert ok is True
    assert "marked done" in message

def test_prd_update_gate_fails_when_not_marked_done(tmp_path: Path):
    """Test that the gate fails when a task is not marked as done."""
    project_root = tmp_path
    prd_path = project_root / "PRD.md"
    task_id = "42"
    
    # Task NOT marked done
    prd_path.write_text("- [ ] Task 42\n", encoding="utf-8")
    
    ok, message = _check_prd_update(project_root, prd_path, task_id)
    assert ok is False
    assert "not marked done" in message

def test_prd_update_gate_passes_on_any_change_if_provided_before(tmp_path: Path):
    """Test that the gate passes if the PRD was modified at all, even if not marked done."""
    project_root = tmp_path
    prd_path = project_root / "PRD.md"
    task_id = "42"
    
    content_before = "- [ ] Task 42\n"
    # Content changed but not marked done
    prd_path.write_text("- [ ] Task 42 (updated description)\n", encoding="utf-8")
    
    ok, message = _check_prd_update(project_root, prd_path, task_id, prd_content_before=content_before)
    assert ok is True
    assert "modified" in message

def test_prd_update_gate_fails_on_no_change_if_provided_before(tmp_path: Path):
    """Test that the gate fails if the PRD content is identical to before iteration."""
    project_root = tmp_path
    prd_path = project_root / "PRD.md"
    task_id = "42"
    
    content = "- [ ] Task 42\n"
    prd_path.write_text(content, encoding="utf-8")
    
    ok, message = _check_prd_update(project_root, prd_path, task_id, prd_content_before=content)
    assert ok is False
    assert "not updated" in message

def test_prd_update_gate_fails_if_missing(tmp_path: Path):
    """Test that the gate fails if the PRD file does not exist."""
    project_root = tmp_path
    prd_path = project_root / "PRD.md"
    
    ok, message = _check_prd_update(project_root, prd_path, "42")
    assert ok is False
    assert "not found" in message
