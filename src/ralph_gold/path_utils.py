"""Path validation and security utilities.

This module provides secure path handling to prevent path traversal attacks
(OWASP Top 10 2025: A01 - Broken Access Control). All user-provided paths
must be validated to ensure they remain within the project root directory.

Security Considerations (OWASP ASVS 5.0.0):
- V5.1.3: Verify that the application validates that the user is authorized
  to access the requested file or resource
- V5.1.4: Verify that the application prevents path traversal

Common Attack Patterns Prevented:
- ../../../etc/passwd
- /absolute/path/outside/project
- symlink traversal to external locations
"""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


def validate_project_path(
    project_root: Path, user_path: Union[str, Path], must_exist: bool = False
) -> Path:
    """Validate that user_path is within project_root (prevents path traversal).

    This function validates user-provided paths to prevent directory traversal
    attacks. It resolves both paths to their absolute form and verifies that
    the user_path is contained within project_root.

    Args:
        project_root: The root directory of the project (trusted boundary)
        user_path: Path provided by user (untrusted input)
        must_exist: If True, raise ValueError if path doesn't exist

    Returns:
        The validated, resolved path (absolute, within project_root)

    Raises:
        ValueError: If path is outside project_root or doesn't exist (when must_exist=True)

    Example:
        >>> root = Path("/my/project")
        >>> validate_project_path(root, "config.toml")
        PosixPath('/my/project/config.toml')
        >>> validate_project_path(root, "../../../etc/passwd")
        ValueError: Path outside project root: ../../../etc/passwd
    """
    user_path = Path(user_path) if isinstance(user_path, str) else user_path

    # Resolve to absolute path (follows symlinks, eliminates . and ..)
    # Use resolve() with strict=False for non-existent paths
    try:
        resolved = (project_root / user_path).resolve(strict=False)
    except OSError as e:
        # If resolve fails for any reason, try absolute path
        logger.debug("Path resolution failed: %s", e)
        resolved = (project_root / user_path).absolute()

    # Verify path is within project_root
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError:
        raise ValueError(f"Path outside project root: {user_path}")

    # Check existence if required
    if must_exist and not resolved.exists():
        raise ValueError(f"Path does not exist: {user_path}")

    return resolved


def validate_output_path(
    project_root: Path, output_path: Union[str, Path], must_exist: bool = False
) -> Path:
    """Validate an output path for file writing operations.

    Similar to validate_project_path but specifically intended for paths that
    will be written to (e.g., log files, state files, generated outputs).

    Args:
        project_root: The root directory of the project
        output_path: Path where output will be written
        must_exist: If True, parent directory must exist

    Returns:
        The validated, resolved path

    Raises:
        ValueError: If path is outside project_root or parent doesn't exist (when must_exist=True)

    Example:
        >>> root = Path("/my/project")
        >>> validate_output_path(root, ".ralph/logs/output.log")
        PosixPath('/my/project/.ralph/logs/output.log')
    """
    output_path = Path(output_path) if isinstance(output_path, str) else output_path
    resolved = validate_project_path(project_root, output_path, must_exist=False)

    # For output paths, check parent directory exists
    if must_exist and not resolved.parent.exists():
        raise ValueError(f"Parent directory does not exist: {resolved.parent}")

    return resolved


def safe_join(project_root: Path, *paths: Union[str, Path]) -> Path:
    """Safely join paths while preventing traversal outside project_root.

    This is a convenience function for constructing paths from multiple components
    while ensuring the result stays within the project boundary.

    Args:
        project_root: The root directory of the project
        *paths: Path components to join

    Returns:
        The validated, resolved path

    Example:
        >>> root = Path("/my/project")
        >>> safe_join(root, ".ralph", "logs", "output.log")
        PosixPath('/my/project/.ralph/logs/output.log')
    """
    if not paths:
        return project_root

    joined = project_root
    for p in paths:
        joined = joined / p

    return validate_project_path(project_root, joined)
