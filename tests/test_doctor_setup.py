"""Tests for ralph doctor --setup-checks functionality."""

import json
from pathlib import Path
from ralph_gold.doctor import (
    _detect_project_type,
    _detect_package_manager,
    _get_check_commands,
    setup_checks,
)


def test_detect_project_type_node(tmp_path: Path):
    """Test Node.js project detection."""
    (tmp_path / "package.json").write_text("{}")
    assert _detect_project_type(tmp_path) == "node"


def test_detect_project_type_python(tmp_path: Path):
    """Test Python project detection."""
    (tmp_path / "pyproject.toml").write_text("")
    assert _detect_project_type(tmp_path) == "python"


def test_detect_project_type_rust(tmp_path: Path):
    """Test Rust project detection."""
    (tmp_path / "Cargo.toml").write_text("")
    assert _detect_project_type(tmp_path) == "rust"


def test_detect_project_type_go(tmp_path: Path):
    """Test Go project detection."""
    (tmp_path / "go.mod").write_text("")
    assert _detect_project_type(tmp_path) == "go"


def test_detect_project_type_unknown(tmp_path: Path):
    """Test unknown project type."""
    assert _detect_project_type(tmp_path) == "unknown"


def test_detect_package_manager_pnpm(tmp_path: Path):
    """Test pnpm detection."""
    (tmp_path / "pnpm-lock.yaml").write_text("")
    assert _detect_package_manager(tmp_path) == "pnpm"


def test_detect_package_manager_yarn(tmp_path: Path):
    """Test yarn detection."""
    (tmp_path / "yarn.lock").write_text("")
    assert _detect_package_manager(tmp_path) == "yarn"


def test_detect_package_manager_npm(tmp_path: Path):
    """Test npm detection."""
    (tmp_path / "package-lock.json").write_text("")
    assert _detect_package_manager(tmp_path) == "npm"


def test_detect_package_manager_bun(tmp_path: Path):
    """Test bun detection."""
    (tmp_path / "bun.lockb").write_text("")
    assert _detect_package_manager(tmp_path) == "bun"


def test_detect_package_manager_none(tmp_path: Path):
    """Test no package manager."""
    assert _detect_package_manager(tmp_path) is None


def test_get_check_commands_node_with_scripts(tmp_path: Path):
    """Test check command generation for Node.js with existing scripts."""
    package_json = {
        "scripts": {
            "typecheck": "tsc --noEmit",
            "test": "vitest run",
            "lint": "eslint .",
        }
    }
    (tmp_path / "package.json").write_text(json.dumps(package_json))
    (tmp_path / "pnpm-lock.yaml").write_text("")
    
    commands, script_name = _get_check_commands("node", tmp_path)
    
    assert script_name == "check"
    assert "pnpm -s typecheck" in commands
    assert "pnpm -s test" in commands
    assert "pnpm -s lint" in commands


def test_get_check_commands_python(tmp_path: Path):
    """Test check command generation for Python."""
    pyproject = """
[project]
dependencies = ["pytest", "mypy", "ruff"]
"""
    (tmp_path / "pyproject.toml").write_text(pyproject)
    
    commands, script_name = _get_check_commands("python", tmp_path)
    
    assert script_name == "check"
    assert any("mypy" in cmd for cmd in commands)
    assert any("pytest" in cmd for cmd in commands)
    assert any("ruff" in cmd for cmd in commands)


def test_setup_checks_node_dry_run(tmp_path: Path):
    """Test setup_checks in dry-run mode for Node.js project."""
    package_json = {"scripts": {}}
    (tmp_path / "package.json").write_text(json.dumps(package_json, indent=2))
    (tmp_path / "pnpm-lock.yaml").write_text("")
    
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    ralph_toml = ralph_dir / "ralph.toml"
    ralph_toml.write_text("[loop]\nmax_iterations = 10\n")
    
    result = setup_checks(tmp_path, dry_run=True)
    
    assert result["project_type"] == "node"
    assert result["script_name"] == "check"
    assert len(result["commands"]) > 0
    assert len(result["suggestions"]) > 0
    
    # Dry run should not modify files
    data = json.loads((tmp_path / "package.json").read_text())
    assert "check" not in data.get("scripts", {})


def test_setup_checks_node_apply(tmp_path: Path):
    """Test setup_checks with actual changes for Node.js project."""
    package_json = {"scripts": {}}
    (tmp_path / "package.json").write_text(json.dumps(package_json, indent=2))
    (tmp_path / "pnpm-lock.yaml").write_text("")
    
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    ralph_toml = ralph_dir / "ralph.toml"
    ralph_toml.write_text("[loop]\nmax_iterations = 10\n")
    
    result = setup_checks(tmp_path, dry_run=False)
    
    assert result["project_type"] == "node"
    assert len(result["actions_taken"]) > 0
    
    # Should have added check script
    data = json.loads((tmp_path / "package.json").read_text())
    assert "check" in data["scripts"]
    
    # Should have added gates config
    toml_content = ralph_toml.read_text()
    assert "[gates]" in toml_content
    assert "precommit_hook" in toml_content


def test_setup_checks_python_apply(tmp_path: Path):
    """Test setup_checks for Python project."""
    pyproject = """
[project]
dependencies = ["pytest", "ruff"]
"""
    (tmp_path / "pyproject.toml").write_text(pyproject)
    
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    ralph_toml = ralph_dir / "ralph.toml"
    ralph_toml.write_text("[loop]\nmax_iterations = 10\n")
    
    result = setup_checks(tmp_path, dry_run=False)
    
    assert result["project_type"] == "python"
    assert len(result["commands"]) > 0
    
    # Should have added gates config
    toml_content = ralph_toml.read_text()
    assert "[gates]" in toml_content
    assert "pytest" in toml_content or "ruff" in toml_content


def test_setup_checks_existing_gates(tmp_path: Path):
    """Test that existing gates configuration is not overwritten."""
    (tmp_path / "package.json").write_text("{}")
    
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    ralph_toml = ralph_dir / "ralph.toml"
    ralph_toml.write_text("""
[loop]
max_iterations = 10

[gates]
commands = ["existing command"]
""")
    
    result = setup_checks(tmp_path, dry_run=False)
    
    # Should suggest that gates are already configured
    assert any("already configured" in s for s in result["suggestions"])
    
    # Should not duplicate gates section
    toml_content = ralph_toml.read_text()
    assert toml_content.count("[gates]") == 1


def test_setup_checks_no_ralph_toml(tmp_path: Path):
    """Test behavior when .ralph/ralph.toml doesn't exist."""
    (tmp_path / "package.json").write_text("{}")
    
    result = setup_checks(tmp_path, dry_run=False)
    
    # Should suggest running ralph init
    assert any("ralph init" in s for s in result["suggestions"])
