#!/usr/bin/env python3
"""Test make_tracker with YAML files."""

import tempfile
from pathlib import Path

from ralph_gold.config import (
    Config,
    FilesConfig,
    GatesConfig,
    GitConfig,
    LlmJudgeConfig,
    LoopConfig,
    ParallelConfig,
    TrackerConfig,
)
from ralph_gold.trackers import make_tracker


def test_make_tracker_yaml():
    """Test that make_tracker can create YamlTracker."""

    # Create a test YAML file
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        yaml_path = project_root / "tasks.yaml"

        with open(yaml_path, "w") as f:
            f.write("""version: 1
tasks:
  - id: 1
    title: Test task
    completed: false
""")

        # Create config with yaml tracker
        cfg = Config(
            loop=LoopConfig(),
            files=FilesConfig(prd="tasks.yaml"),
            runners={},
            gates=GatesConfig(commands=[], llm_judge=LlmJudgeConfig()),
            git=GitConfig(),
            tracker=TrackerConfig(kind="yaml"),
            parallel=ParallelConfig(),
        )

        # Test explicit yaml kind
        tracker = make_tracker(project_root, cfg)
        print(f"✓ Created tracker with kind='yaml': {tracker.kind}")
        assert tracker.kind == "yaml"

        # Test auto-detection by extension
        cfg_auto = Config(
            loop=LoopConfig(),
            files=FilesConfig(prd="tasks.yaml"),
            runners={},
            gates=GatesConfig(commands=[], llm_judge=LlmJudgeConfig()),
            git=GitConfig(),
            tracker=TrackerConfig(kind="auto"),
            parallel=ParallelConfig(),
        )

        tracker_auto = make_tracker(project_root, cfg_auto)
        print(f"✓ Auto-detected YAML tracker: {tracker_auto.kind}")
        assert tracker_auto.kind == "yaml"

        # Test .yml extension
        yml_path = project_root / "tasks.yml"
        yml_path.write_text(yaml_path.read_text())

        cfg_yml = Config(
            loop=LoopConfig(),
            files=FilesConfig(prd="tasks.yml"),
            runners={},
            gates=GatesConfig(commands=[], llm_judge=LlmJudgeConfig()),
            git=GitConfig(),
            tracker=TrackerConfig(kind="auto"),
            parallel=ParallelConfig(),
        )

        tracker_yml = make_tracker(project_root, cfg_yml)
        print(f"✓ Auto-detected .yml extension: {tracker_yml.kind}")
        assert tracker_yml.kind == "yaml"

        print("\n✅ make_tracker YAML integration tests passed!")


if __name__ == "__main__":
    test_make_tracker_yaml()
