from pathlib import Path
from textwrap import dedent

import pytest

from ralph_gold.config import LoopModeConfig, load_config


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    return tmp_path


def _write_config(project_root: Path, content: str) -> None:
    config_path = project_root / ".ralph" / "ralph.toml"
    config_path.write_text(content, encoding="utf-8")


def test_loop_mode_defaults_when_absent(temp_project: Path) -> None:
    _write_config(temp_project, "[loop]\nmax_iterations = 10\n")

    cfg = load_config(temp_project)

    assert cfg.loop.mode == "speed"
    assert set(cfg.loop.modes.keys()) == {"speed", "quality", "exploration"}
    assert cfg.loop.modes["speed"] == LoopModeConfig()
    assert cfg.loop.modes["quality"] == LoopModeConfig()
    assert cfg.loop.modes["exploration"] == LoopModeConfig()


def test_loop_mode_parsing_with_partial_override(temp_project: Path) -> None:
    _write_config(
        temp_project,
        dedent(
            """
            [loop]
            max_iterations = 10
            mode = "quality"

            [loop.modes.quality]
            runner_timeout_seconds = 120
            skip_blocked_tasks = false
            """
        ).strip()
        + "\n",
    )

    cfg = load_config(temp_project)

    assert cfg.loop.mode == "quality"
    assert cfg.loop.modes["quality"].runner_timeout_seconds == 120
    assert cfg.loop.modes["quality"].skip_blocked_tasks is False
    assert cfg.loop.modes["quality"].max_iterations is None


def test_loop_mode_unknown_name_errors(temp_project: Path) -> None:
    _write_config(
        temp_project,
        dedent(
            """
            [loop]
            max_iterations = 10
            mode = "turbo"
            """
        ).strip()
        + "\n",
    )

    with pytest.raises(ValueError, match="Invalid loop.mode"):
        load_config(temp_project)


def test_loop_modes_unknown_section_errors(temp_project: Path) -> None:
    _write_config(
        temp_project,
        dedent(
            """
            [loop]
            max_iterations = 10

            [loop.modes.turbo]
            max_iterations = 5
            """
        ).strip()
        + "\n",
    )

    with pytest.raises(ValueError, match="Invalid loop mode"):
        load_config(temp_project)
