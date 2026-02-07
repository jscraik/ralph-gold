"""Tracker implementations for ralph-gold.

This package contains various tracker implementations that provide different
backends for task tracking:

- FileTracker: File-based tracker for Markdown/JSON PRDs (legacy)
- BeadsTracker: Tracker backed by Beads CLI
- YamlTracker: YAML-based tracker with native parallel grouping support
- GitHubIssuesTracker: GitHub Issues-based tracker
- WebTracker: Web Analysis tracker for discovering web-related tasks

All trackers implement the Tracker protocol defined in the parent module.
"""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

_trackers_module: ModuleType | None = None


def _load_trackers_module() -> ModuleType:
    global _trackers_module
    if _trackers_module is not None:
        return _trackers_module
    module_path = Path(__file__).resolve().parent.parent / "trackers.py"
    spec = spec_from_file_location("ralph_gold._trackers_file", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load trackers module at {module_path}")
    module = module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _trackers_module = module
    return module


if TYPE_CHECKING:
    from ralph_gold.trackers import BeadsTracker, FileTracker, Tracker
    from ralph_gold.trackers import make_tracker
else:
    _mod = _load_trackers_module()
    Tracker = _mod.Tracker
    FileTracker = _mod.FileTracker
    BeadsTracker = _mod.BeadsTracker
    make_tracker = _mod.make_tracker

__all__: list[str] = [
    "Tracker",
    "FileTracker",
    "BeadsTracker",
    "make_tracker",
]
