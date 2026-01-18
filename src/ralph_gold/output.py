"""Output control module for Ralph Gold.

This module provides verbosity control and output formatting for CLI commands.
Supports quiet mode (minimal output), normal mode (standard output), and verbose
mode (detailed output), as well as JSON output formatting.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional

# -------------------------
# Dataclasses
# -------------------------


@dataclass
class OutputConfig:
    """Output configuration for controlling verbosity and format.

    Attributes:
        verbosity: Output level - "quiet", "normal", or "verbose"
        format: Output format - "text" or "json"
        color: Whether to enable ANSI color codes (future use)
    """

    verbosity: str = "normal"  # quiet|normal|verbose
    format: str = "text"  # text|json
    color: bool = True  # Enable ANSI colors (future use)


# -------------------------
# Global state
# -------------------------

# Global output configuration (set by CLI)
_output_config: Optional[OutputConfig] = None


# -------------------------
# Core functions
# -------------------------


def get_output_config() -> OutputConfig:
    """Get the current output configuration.

    Returns the global output config if set, otherwise creates a default
    configuration based on environment variables and CLI arguments.

    Returns:
        OutputConfig: Current output configuration
    """
    global _output_config

    if _output_config is not None:
        return _output_config

    # Default configuration
    verbosity = os.environ.get("RALPH_VERBOSITY", "normal")
    format_type = os.environ.get("RALPH_FORMAT", "text")

    # Validate values
    if verbosity not in ("quiet", "normal", "verbose"):
        verbosity = "normal"
    if format_type not in ("text", "json"):
        format_type = "text"

    return OutputConfig(verbosity=verbosity, format=format_type, color=True)


def set_output_config(config: OutputConfig) -> None:
    """Set the global output configuration.

    Args:
        config: OutputConfig to use for all subsequent output
    """
    global _output_config
    _output_config = config


def print_output(message: str, level: str = "normal", file: Any = None, end: str = "\n") -> None:
    """Print output respecting the current verbosity level.

    Messages are only printed if the current verbosity level is appropriate:
    - "error" messages: always printed (regardless of verbosity)
    - "quiet" messages: printed in quiet, normal, and verbose modes
    - "normal" messages: printed in normal and verbose modes (suppressed in quiet)
    - "verbose" messages: only printed in verbose mode

    Args:
        message: The message to print
        level: Message level - "error", "quiet", "normal", or "verbose"
        file: File object to write to (default: stdout for normal, stderr for error)
        end: String to append after message (default: newline)
    """
    config = get_output_config()

    # JSON format suppresses all text output (handled separately)
    if config.format == "json":
        return

    # Determine if we should print based on verbosity level
    should_print = False

    if level == "error":
        # Errors always print
        should_print = True
        if file is None:
            file = sys.stderr
    elif level == "quiet":
        # Quiet-level messages print in all modes
        should_print = True
    elif level == "normal":
        # Normal messages print in normal and verbose modes
        should_print = config.verbosity in ("normal", "verbose")
    elif level == "verbose":
        # Verbose messages only print in verbose mode
        should_print = config.verbosity == "verbose"
    else:
        # Unknown level, treat as normal
        should_print = config.verbosity in ("normal", "verbose")

    if should_print:
        if file is None:
            file = sys.stdout
        print(message, file=file, end=end)


def format_json_output(data: Dict[str, Any]) -> str:
    """Format data as JSON output.

    Produces pretty-printed JSON with consistent formatting for CLI output.

    Args:
        data: Dictionary to format as JSON

    Returns:
        str: JSON-formatted string
    """
    return json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False)


def print_json_output(data: Dict[str, Any]) -> None:
    """Print data as JSON output if in JSON format mode.

    This is a convenience function that checks the output format and
    prints JSON if appropriate.

    Args:
        data: Dictionary to output as JSON
    """
    config = get_output_config()
    if config.format == "json":
        print(format_json_output(data))
