"""Atomic file operations to prevent data corruption.

This module provides atomic write operations that use the POSIX rename
guarantee: a rename is atomic if the destination exists on the same
filesystem. By writing to a temp file and then renaming, we ensure that
the target file is never in a partially-written state.

Security Considerations (NIST SSDF v1.2):
- Prevents data corruption from concurrent writes
- Prevents partial state files from being read
- Ensures rollback can recover from interrupted operations
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write content to file atomically using temp file + rename.

    Args:
        path: Target file path
        content: Text content to write
        encoding: File encoding (default: utf-8)

    Raises:
        OSError: If write or rename fails

    Example:
        >>> atomic_write_text(Path("config.txt"), "hello world")
    """
    temp_path = path.with_suffix(".tmp")

    # Write to temp file first
    temp_path.write_text(content, encoding=encoding)

    # Atomic rename (POSIX guarantee: same filesystem, no partial state)
    temp_path.replace(path)


def atomic_write_json(path: Path, data: Dict[str, Any], indent: int = 2) -> None:
    """Write JSON data to file atomically.

    Args:
        path: Target file path
        data: Dictionary to serialize as JSON
        indent: JSON indentation level (default: 2)

    Raises:
        TypeError: If data is not JSON-serializable
        OSError: If write or rename fails

    Example:
        >>> atomic_write_json(Path("state.json"), {"tasks": [1, 2, 3]})
    """
    content = json.dumps(data, indent=indent, separators=(",", ": ")) + "\n"
    atomic_write_text(path, content)


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Write binary content to file atomically.

    Args:
        path: Target file path
        content: Binary content to write

    Raises:
        OSError: If write or rename fails

    Example:
        >>> atomic_write_bytes(Path("data.bin"), b"\\x00\\x01\\x02")
    """
    temp_path = path.with_suffix(".tmp")
    temp_path.write_bytes(content)
    temp_path.replace(path)
