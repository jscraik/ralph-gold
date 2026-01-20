"""Authorization artifacts for Ralph Gold.

Provides permission-based authorization for agent file operations.
"""

from __future__ import annotations

import fnmatch
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FilePermission:
    """Permission rule for file operations.

    Args:
        pattern: Glob pattern (e.g., "*.py" or ".ralph/**")
        allow_write: Whether write is allowed for this pattern
        reason: Human-readable explanation for this permission
    """
    pattern: str
    allow_write: bool = True
    reason: str = ""


@dataclass(frozen=True)
class AuthorizationChecker:
    """Runtime authorization checker with loaded permissions.

    Args:
        enabled: Whether authorization verification is active
        fallback_to_full_auto: If True, skip auth when --full-auto present in argv
        permissions: List of FilePermission rules
    """
    enabled: bool = False
    fallback_to_full_auto: bool = False
    permissions: List[FilePermission] = field(default_factory=list)

    def check_write_permission(
        self,
        file_path: Path,
        runner_argv: List[str]
    ) -> tuple[bool, str]:
        """Check if file write is allowed.

        Args:
            file_path: Path to file being written
            runner_argv: Runner command arguments (for --full-auto detection)

        Returns:
            (allowed, reason) tuple
        """
        # If disabled, always allow
        if not self.enabled:
            return True, "Authorization disabled"

        # Check fallback to --full-auto flag
        if self.fallback_to_full_auto and "--full-auto" in runner_argv:
            return True, "Allowed: --full-auto flag present"

        # Build list of path strings to try matching against
        # Try both full path and relative path components for patterns like "src/**"
        path_strings = [str(file_path)]
        parts = file_path.parts
        for i in range(len(parts)):
            # Try "src/file.py", "src/subdir/file.py", etc.
            path_strings.append(str(Path(*parts[i:])))

        for perm in self.permissions:
            for path_str in path_strings:
                if fnmatch.fnmatch(path_str, perm.pattern):
                    if perm.allow_write:
                        return True, perm.reason or f"Allowed: matches {perm.pattern}"
                    else:
                        return False, perm.reason or f"Denied: matches {perm.pattern}"

        # Default: allow if no patterns match (fail-open for safety)
        return True, "Allowed: no matching patterns"


def load_authorization_checker(project_root: Path, permissions_file: str = ".ralph/permissions.json") -> AuthorizationChecker:
    """Load .ralph/permissions.json if it exists.

    Args:
        project_root: Project root directory
        permissions_file: Path to permissions file relative to project root

    Returns:
        AuthorizationChecker (default disabled if file doesn't exist)
    """
    perm_path = project_root / permissions_file

    if not perm_path.exists():
        return AuthorizationChecker()

    try:
        data = json.loads(perm_path.read_text(encoding="utf-8"))

        enabled = data.get("enabled", False)
        fallback = data.get("fallback_to_full_auto", False)

        perms = []
        for p in data.get("permissions", []):
            perms.append(FilePermission(
                pattern=p.get("pattern", ""),
                allow_write=p.get("allow_write", True),
                reason=p.get("reason", "")
            ))

        return AuthorizationChecker(
            enabled=enabled,
            fallback_to_full_auto=fallback,
            permissions=perms
        )
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in {perm_path}: {e}")
        return AuthorizationChecker()
    except Exception as e:
        logger.warning(f"Error loading {perm_path}: {e}")
        return AuthorizationChecker()
