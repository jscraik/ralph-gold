"""Authorization artifacts for Ralph Gold.

Provides permission-based authorization for agent file operations.
"""

from __future__ import annotations

import enum
import fnmatch
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class EnforcementMode(enum.Enum):
    """Authorization enforcement modes.

    WARN: Log warning but allow the operation (soft enforcement)
    BLOCK: Raise exception to block the operation (hard enforcement)
    """
    WARN = "warn"
    BLOCK = "block"


class AuthorizationError(Exception):
    """Raised when authorization check fails in block mode.

    This exception indicates that a file write operation was blocked
    due to authorization rules.
    """

    def __init__(self, file_path: Path, reason: str):
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"Write not permitted: {reason}")


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
        enforcement_mode: How to handle authorization failures (warn or block)
        permissions: List of FilePermission rules
    """
    enabled: bool = False
    fallback_to_full_auto: bool = False
    enforcement_mode: EnforcementMode = EnforcementMode.WARN
    permissions: List[FilePermission] = field(default_factory=list)

    def check_write_permission(
        self,
        file_path: Path,
        runner_argv: List[str],
        *,
        raise_on_block: bool = True,
    ) -> tuple[bool, str]:
        """Check if file write is allowed.

        Args:
            file_path: Path to file being written
            runner_argv: Runner command arguments (for --full-auto detection)
            raise_on_block: If True, raise AuthorizationError in block mode when denied

        Returns:
            (allowed, reason) tuple

        Raises:
            AuthorizationError: If check fails and enforcement_mode is BLOCK
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
                        # Permission denied
                        reason = perm.reason or f"Denied: matches {perm.pattern}"
                        if self.enforcement_mode == EnforcementMode.BLOCK and raise_on_block:
                            raise AuthorizationError(file_path, reason)
                        # Warn mode: return denied but don't raise
                        return False, reason

        # Default: allow if no patterns match (fail-open for safety)
        return True, "Allowed: no matching patterns"


def load_authorization_checker(
    project_root: Path,
    permissions_file: str = ".ralph/permissions.json",
    enforcement_mode: EnforcementMode = EnforcementMode.WARN,
) -> AuthorizationChecker:
    """Load .ralph/permissions.json if it exists.

    Args:
        project_root: Project root directory
        permissions_file: Path to permissions file relative to project root
        enforcement_mode: Default enforcement mode (can be overridden by config)

    Returns:
        AuthorizationChecker (default disabled if file doesn't exist)
    """
    perm_path = project_root / permissions_file

    if not perm_path.exists():
        return AuthorizationChecker(enforcement_mode=enforcement_mode)

    try:
        data = json.loads(perm_path.read_text(encoding="utf-8"))

        enabled = data.get("enabled", False)
        fallback = data.get("fallback_to_full_auto", False)

        # Load enforcement_mode from config, default to provided parameter
        mode_str = data.get("enforcement_mode", enforcement_mode.value)
        try:
            # Handle both string and enum values
            if isinstance(mode_str, str):
                mode = EnforcementMode(mode_str.lower())
            else:
                mode = enforcement_mode
        except ValueError:
            logger.warning(f"Invalid enforcement_mode '{mode_str}' in {perm_path}, using default")
            mode = enforcement_mode

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
            enforcement_mode=mode,
            permissions=perms
        )
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in {perm_path}: {e}")
        return AuthorizationChecker(enforcement_mode=enforcement_mode)
    except Exception as e:
        logger.warning(f"Error loading {perm_path}: {e}")
        return AuthorizationChecker(enforcement_mode=enforcement_mode)
