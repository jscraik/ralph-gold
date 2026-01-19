"""Standardized JSON response builders for CLI output.

This module provides consistent JSON response builders used throughout the CLI.
It eliminates code duplication and ensures all JSON responses follow a
consistent structure.

Benefits:
- Consistent response format across all commands
- Reduced code duplication
- Easier to add response fields
- Better type safety with dataclasses
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass
class JsonResponse:
    """Standard JSON response structure.

    Attributes:
        cmd: The command that generated this response
        exit_code: Exit code (0 = success, non-zero = error)
        timestamp: ISO 8601 timestamp of when the response was created
        data: Additional response data (command-specific)
        error: Optional error message if exit_code != 0
    """

    cmd: str
    exit_code: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data: Dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: Dict[str, Any] = {
            "cmd": self.cmd,
            "exit_code": self.exit_code,
            "timestamp": self.timestamp,
        }
        if self.data:
            result.update(self.data)
        if self.error:
            result["error"] = self.error
        return result


def build_json_response(
    cmd: str,
    exit_code: int = 0,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Build a standardized JSON response.

    This is a convenience function for creating JSON responses without
    instantiating the JsonResponse class directly.

    Args:
        cmd: The command that generated this response
        exit_code: Exit code (0 = success, non-zero = error)
        **kwargs: Additional response data (command-specific)

    Returns:
        Dictionary ready for JSON serialization

    Example:
        >>> payload = build_json_response("doctor", mode="tools", statuses=[...])
        >>> print(json.dumps(payload, indent=2))
        {
          "cmd": "doctor",
          "exit_code": 0,
          "timestamp": "2026-01-19T12:34:56",
          "mode": "tools",
          "statuses": [...]
        }
    """
    response = JsonResponse(cmd=cmd, exit_code=exit_code, data=kwargs)
    return response.to_dict()


def build_error_response(
    cmd: str, error: str, exit_code: int = 1, **kwargs: Any
) -> Dict[str, Any]:
    """Build a JSON error response.

    Args:
        cmd: The command that generated this error
        error: Error message
        exit_code: Exit code (default: 1)
        **kwargs: Additional response data

    Returns:
        Dictionary ready for JSON serialization

    Example:
        >>> payload = build_error_response("doctor", "Git not found", exit_code=2)
        >>> print(json.dumps(payload, indent=2))
        {
          "cmd": "doctor",
          "exit_code": 2,
          "timestamp": "2026-01-19T12:34:56",
          "error": "Git not found"
        }
    """
    response = JsonResponse(cmd=cmd, exit_code=exit_code, error=error, data=kwargs)
    return response.to_dict()
