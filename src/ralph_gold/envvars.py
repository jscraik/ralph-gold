"""Environment variable expansion for configuration files.

This module provides secure environment variable expansion with support for:
- ${VAR} syntax for required variables
- ${VAR:-default} syntax for optional variables with defaults
- Security validation to prevent shell injection
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List

# Pattern to match ${VAR} or ${VAR:-default}
ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(:-([^}]*))?\}")

# Pattern to validate variable names (alphanumeric + underscore only)
VAR_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class EnvVarError(Exception):
    """Error during environment variable expansion."""

    pass


def expand_env_vars(value: str) -> str:
    """Expand environment variables in a string.

    Supports two syntaxes:
    - ${VAR}: Required variable, raises EnvVarError if not set
    - ${VAR:-default}: Optional variable with default value

    Args:
        value: String potentially containing environment variable references

    Returns:
        String with all environment variables expanded

    Raises:
        EnvVarError: If a required variable is not set or has invalid name

    Examples:
        >>> os.environ['MY_VAR'] = 'hello'
        >>> expand_env_vars('Value is ${MY_VAR}')
        'Value is hello'
        >>> expand_env_vars('Value is ${MISSING:-default}')
        'Value is default'
    """

    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(3)  # None if no default specified

        # Validate variable name for security
        if not VAR_NAME_PATTERN.match(var_name):
            raise EnvVarError(
                f"Invalid environment variable name: {var_name}. "
                "Only alphanumeric characters and underscores are allowed."
            )

        # Get value from environment
        env_value = os.environ.get(var_name)

        if env_value is not None:
            return env_value
        elif default is not None:
            return default
        else:
            raise EnvVarError(
                f"Required environment variable not set: {var_name}. "
                f"Either set {var_name} or use ${{{{var_name}}:-default}} syntax."
            )

    return ENV_VAR_PATTERN.sub(replacer, value)


def validate_required_vars(config_dict: Dict[str, Any]) -> List[str]:
    """Find all required environment variables in a config dict.

    Scans the configuration recursively for ${VAR} patterns (without defaults)
    and returns a list of variables that are not currently set.

    Args:
        config_dict: Configuration dictionary to scan

    Returns:
        List of missing required variable names

    Examples:
        >>> config = {'key': '${REQUIRED_VAR}', 'optional': '${OPT:-default}'}
        >>> validate_required_vars(config)
        ['REQUIRED_VAR']  # if REQUIRED_VAR not set
    """
    missing: List[str] = []

    def scan_value(value: Any) -> None:
        """Recursively scan for environment variable references."""
        if isinstance(value, str):
            # Find all ${VAR} patterns without defaults
            for match in ENV_VAR_PATTERN.finditer(value):
                var_name = match.group(1)
                default = match.group(3)

                # Only check required vars (no default)
                if default is None and var_name not in os.environ:
                    if var_name not in missing:
                        missing.append(var_name)

        elif isinstance(value, dict):
            for v in value.values():
                scan_value(v)

        elif isinstance(value, list):
            for item in value:
                scan_value(item)

    scan_value(config_dict)
    return missing


def expand_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively expand all environment variables in a config dict.

    Args:
        config_dict: Configuration dictionary with potential env var references

    Returns:
        New dictionary with all environment variables expanded

    Raises:
        EnvVarError: If a required variable is not set

    Examples:
        >>> os.environ['DB_HOST'] = 'localhost'
        >>> config = {'database': {'host': '${DB_HOST}'}}
        >>> expand_config(config)
        {'database': {'host': 'localhost'}}
    """

    def expand_value(value: Any) -> Any:
        """Recursively expand environment variables in any value."""
        if isinstance(value, str):
            return expand_env_vars(value)

        elif isinstance(value, dict):
            return {k: expand_value(v) for k, v in value.items()}

        elif isinstance(value, list):
            return [expand_value(item) for item in value]

        else:
            # Return other types unchanged
            return value

    return expand_value(config_dict)
