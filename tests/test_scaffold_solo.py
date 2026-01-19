"""Tests for solo-dev ralph init scaffolding."""

from __future__ import annotations

from pathlib import Path

import tomllib

from ralph_gold.scaffold import init_project


def _load_ralph_toml(project_root: Path) -> dict:
    config_path = project_root / ".ralph" / "ralph.toml"
    return tomllib.loads(config_path.read_text(encoding="utf-8"))


def test_init_project_solo_uses_solo_template(tmp_path: Path) -> None:
    """Solo init should use the solo template variant with speed mode."""
    init_project(tmp_path, solo=True)

    config_path = tmp_path / ".ralph" / "ralph.toml"
    config_text = config_path.read_text(encoding="utf-8")
    assert "solo defaults" in config_text

    data = _load_ralph_toml(tmp_path)
    assert data["loop"]["mode"] == "speed"
    assert set(data["loop"]["modes"].keys()) == {
        "speed",
        "quality",
        "exploration",
    }
    assert "gates" in data
    assert "smart" in data["gates"]
    assert "skip_gates_for" in data["gates"]["smart"]
    skip_patterns = data["gates"]["smart"]["skip_gates_for"]
    assert "**/*.md" in skip_patterns
    assert "**/*.toml" in skip_patterns


def test_init_project_default_uses_standard_template(tmp_path: Path) -> None:
    """Default init should use the standard template variant."""
    init_project(tmp_path, solo=False)

    config_path = tmp_path / ".ralph" / "ralph.toml"
    config_text = config_path.read_text(encoding="utf-8")
    assert "solo defaults" not in config_text
