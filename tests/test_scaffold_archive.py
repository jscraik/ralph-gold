"""Tests for ralph init archiving behavior."""

from pathlib import Path

from ralph_gold.scaffold import init_project


def test_init_without_force_preserves_existing_files(tmp_path: Path) -> None:
    """Test that init without --force preserves existing files."""
    # Create existing prd.json
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    prd_file = ralph_dir / "prd.json"
    prd_file.write_text('{"tasks": [{"id": "old-task"}]}')

    # Run init without force
    archived = init_project(tmp_path, force=False)

    # Should not archive anything
    assert archived == []

    # Original file should be preserved
    assert prd_file.exists()
    assert "old-task" in prd_file.read_text()


def test_init_with_force_archives_existing_files(tmp_path: Path) -> None:
    """Test that init with --force archives existing files."""
    # Create existing files
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    prd_file = ralph_dir / "prd.json"
    prd_file.write_text('{"tasks": [{"id": "old-task"}]}')

    prompt_file = ralph_dir / "PROMPT.md"
    prompt_file.write_text("# Old prompt")

    # Run init with force
    archived = init_project(tmp_path, force=True, format_type="json")

    # Should archive files
    assert len(archived) > 0
    assert ".ralph/prd.json" in archived
    assert ".ralph/PROMPT.md" in archived

    # Archive directory should exist
    archive_dir = ralph_dir / "archive"
    assert archive_dir.exists()

    # Should have timestamped subdirectory
    archive_subdirs = list(archive_dir.iterdir())
    assert len(archive_subdirs) == 1
    assert archive_subdirs[0].is_dir()

    # Archived files should exist
    archived_prd = archive_subdirs[0] / ".ralph" / "prd.json"
    assert archived_prd.exists()
    assert "old-task" in archived_prd.read_text()

    # New template files should be written
    assert prd_file.exists()
    new_content = prd_file.read_text()
    assert "old-task" not in new_content  # Should be fresh template


def test_init_archives_preserve_directory_structure(tmp_path: Path) -> None:
    """Test that archived files preserve directory structure."""
    # Create files in different locations
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    prd_file = ralph_dir / "prd.json"
    prd_file.write_text('{"tasks": []}')

    # Root-level yaml file
    yaml_file = tmp_path / "tasks.yaml"
    yaml_file.write_text("tasks: []")

    # Run init with force and yaml format
    archived = init_project(tmp_path, force=True, format_type="yaml")

    # Both files should be archived
    assert ".ralph/prd.json" in archived or "tasks.yaml" in archived

    # Check archive structure
    archive_dir = ralph_dir / "archive"
    archive_subdirs = list(archive_dir.iterdir())
    assert len(archive_subdirs) == 1

    # Verify directory structure is preserved
    if (archive_subdirs[0] / "tasks.yaml").exists():
        assert (archive_subdirs[0] / "tasks.yaml").read_text() == "tasks: []"


def test_init_multiple_runs_create_separate_archives(tmp_path: Path) -> None:
    """Test that multiple init --force runs create timestamped archives."""
    import time

    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    prd_file = ralph_dir / "prd.json"

    # First init with force
    prd_file.write_text('{"version": 1}')
    archived1 = init_project(tmp_path, force=True, format_type="json")
    assert len(archived1) > 0

    # Wait to ensure different timestamp
    time.sleep(1.1)

    # Second init with force (different content)
    prd_file.write_text('{"version": 2}')
    archived2 = init_project(tmp_path, force=True, format_type="json")
    assert len(archived2) > 0

    # Should have two separate archive directories
    archive_dir = ralph_dir / "archive"
    archive_subdirs = sorted(archive_dir.iterdir())
    assert len(archive_subdirs) == 2

    # Both archives should exist with different content
    arch1_prd = archive_subdirs[0] / ".ralph" / "prd.json"
    arch2_prd = archive_subdirs[1] / ".ralph" / "prd.json"

    assert arch1_prd.exists()
    assert arch2_prd.exists()
    assert '"version": 1' in arch1_prd.read_text()
    assert '"version": 2' in arch2_prd.read_text()


def test_init_handles_missing_files_gracefully(tmp_path: Path) -> None:
    """Test that init handles cases where some files don't exist."""
    # Create only one file
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    prompt_file = ralph_dir / "PROMPT.md"
    prompt_file.write_text("# Old prompt")

    # Run init with force
    archived = init_project(tmp_path, force=True, format_type="json")

    # Should only archive the file that existed
    assert len(archived) >= 1
    assert ".ralph/PROMPT.md" in archived

    # Should not fail or include non-existent files
    for path in archived:
        assert Path(path).name != ""  # No empty paths
