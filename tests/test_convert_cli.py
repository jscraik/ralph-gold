"""Integration tests for the convert CLI command."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def sample_json_prd(tmp_path: Path) -> Path:
    """Create a sample JSON PRD file."""
    prd = {
        "project": "sample-project",
        "stories": [
            {
                "id": 1,
                "title": "API: Add user endpoint",
                "description": "Create REST API endpoint for users",
                "priority": 1,
                "acceptance": ["Endpoint returns user data", "Handles errors"],
                "passes": False,
            },
            {
                "id": 2,
                "title": "UI: Create login form",
                "priority": 2,
                "acceptance": ["Form validates input"],
                "status": "open",
            },
        ],
    }

    path = tmp_path / "prd.json"
    path.write_text(json.dumps(prd, indent=2))
    return path


@pytest.fixture
def sample_md_prd(tmp_path: Path) -> Path:
    """Create a sample Markdown PRD file."""
    content = """# Sample Project

## Tasks

- [ ] API: Add user endpoint
  - Endpoint returns user data
  - Handles errors

- [ ] UI: Create login form
  - Form validates input
"""

    path = tmp_path / "PRD.md"
    path.write_text(content)
    return path


def test_convert_json_to_yaml_cli(sample_json_prd: Path, tmp_path: Path):
    """Test converting JSON to YAML via CLI."""
    output_path = tmp_path / "tasks.yaml"

    result = subprocess.run(
        [
            *_uv_run_cmd(),
            "python",
            "-m",
            "ralph_gold.cli",
            "convert",
            str(sample_json_prd),
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Converted" in result.stdout
    assert output_path.exists()

    # Verify YAML is valid
    with open(output_path) as f:
        data = yaml.safe_load(f)

    assert data["version"] == 1
    assert len(data["tasks"]) == 2


def test_convert_markdown_to_yaml_cli(sample_md_prd: Path, tmp_path: Path):
    """Test converting Markdown to YAML via CLI."""
    output_path = tmp_path / "tasks.yaml"

    result = subprocess.run(
        [
            *_uv_run_cmd(),
            "python",
            "-m",
            "ralph_gold.cli",
            "convert",
            str(sample_md_prd),
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Converted" in result.stdout
    assert output_path.exists()

    # Verify YAML is valid
    with open(output_path) as f:
        data = yaml.safe_load(f)

    assert data["version"] == 1
    assert len(data["tasks"]) == 2


def test_convert_with_infer_groups_cli(sample_json_prd: Path, tmp_path: Path):
    """Test converting with group inference via CLI."""
    output_path = tmp_path / "tasks.yaml"

    result = subprocess.run(
        [
            *_uv_run_cmd(),
            "python",
            "-m",
            "ralph_gold.cli",
            "convert",
            str(sample_json_prd),
            str(output_path),
            "--infer-groups",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Converted" in result.stdout
    assert "Groups inferred" in result.stdout
    assert output_path.exists()

    # Verify groups were added
    with open(output_path) as f:
        data = yaml.safe_load(f)

    tasks = data["tasks"]
    assert all("group" in task for task in tasks)

    # Check specific groups
    assert tasks[0]["group"] == "api"
    assert tasks[1]["group"] == "ui"


def test_convert_missing_file_cli(tmp_path: Path):
    """Test converting a missing file via CLI."""
    input_path = tmp_path / "missing.json"
    output_path = tmp_path / "output.yaml"

    result = subprocess.run(
        [
            *_uv_run_cmd(),
            "python",
            "-m",
            "ralph_gold.cli",
            "convert",
            str(input_path),
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "Error" in result.stdout


def test_convert_shows_summary_cli(sample_json_prd: Path, tmp_path: Path):
    """Test that convert command shows a summary."""
    output_path = tmp_path / "tasks.yaml"

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "ralph_gold.cli",
            "convert",
            str(sample_json_prd),
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Check summary information
    assert "Tasks:" in result.stdout
    assert "2 total" in result.stdout
    assert "0 completed" in result.stdout


def test_convert_shows_groups_summary_cli(sample_json_prd: Path, tmp_path: Path):
    """Test that convert command shows groups summary when inferred."""
    output_path = tmp_path / "tasks.yaml"

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "ralph_gold.cli",
            "convert",
            str(sample_json_prd),
            str(output_path),
            "--infer-groups",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Check groups summary
    assert "Groups:" in result.stdout
    assert "api" in result.stdout
    assert "ui" in result.stdout
def _uv_run_cmd() -> list[str]:
    cmd = ["uv", "run"]
    if os.environ.get("VIRTUAL_ENV"):
        cmd.append("--active")
    return cmd
