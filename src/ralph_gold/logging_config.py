"""Structured logging configuration for Ralph Gold.

This module provides centralized logging configuration that:
- Sets up structured logging with consistent format
- Configures file and console handlers
- Suppresses noisy third-party logs
- Provides both verbose and normal modes

Security Considerations (NIST AI RMF 1.0):
- Logging is essential for monitoring AI system behavior
- Helps detect anomalous behavior and security incidents
- Provides audit trail for AI decisions and actions

Usage:
    >>> setup_logging(verbose=True)
    >>> logger = logging.getLogger(__name__)
    >>> logger.info("Agent started", extra={"agent": "codex"})
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional


# Module-level logger that can be used throughout the codebase
_logger: Optional[logging.Logger] = None


def setup_logging(
    verbose: bool = False,
    log_file: Optional[Path] = None,
    quiet: bool = False,
) -> logging.Logger:
    """Configure structured logging for Ralph Gold.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO level
        log_file: Optional path to a log file for persistent logging
        quiet: If True, suppress all output except errors

    Returns:
        The configured root logger

    Example:
        >>> setup_logging(verbose=True, log_file=Path("ralph.log"))
        >>> logging.info("Starting Ralph loop")
    """
    global _logger

    # Determine log level
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    # Configure handlers
    handlers: list[logging.Handler] = []

    # Console handler (stderr to avoid interfering with stdout)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)

    # File handler (if specified)
    if log_file:
        # Ensure parent directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # Always log DEBUG to file
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add our handlers
    for handler in handlers:
        root_logger.addHandler(handler)

    # Suppress noisy third-party logs
    _configure_third_party_loggers()

    _logger = root_logger
    return root_logger


def _configure_third_party_loggers() -> None:
    """Suppress verbose logging from third-party packages.

    Many third-party libraries are overly verbose at INFO level.
    We suppress them unless explicitly needed for debugging.
    """
    # HTTP libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Git-related
    logging.getLogger("git").setLevel(logging.WARNING)

    # Async frameworks
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    This is a convenience function that ensures logging is configured.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        A logger instance

    Example:
        >>> from ralph_gold.logging_config import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing task", extra={"task_id": "123"})
    """
    if _logger is None:
        # Configure with defaults if not yet configured
        setup_logging()

    return logging.getLogger(name)


class LoggerMixin:
    """Mixin class to add logging capabilities to any class.

    Example:
        >>> class MyProcessor(LoggerMixin):
        ...     def process(self):
        ...         self.logger.debug("Processing started")
        ...         # Do work
        ...         self.logger.info("Processing complete")
    """

    @property
    def logger(self) -> logging.Logger:
        """Get a logger for this class."""
        name = self.__class__.__name__
        return get_logger(f"ralph_gold.{name}")
