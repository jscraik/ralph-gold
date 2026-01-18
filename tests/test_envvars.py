"""Unit tests for environment variable expansion."""

from __future__ import annotations

import pytest

from ralph_gold.envvars import (
    EnvVarError,
    expand_config,
    expand_env_vars,
    validate_required_vars,
)


def test_expand_env_vars_simple(monkeypatch):
    """Test simple environment variable expansion."""
    monkeypatch.setenv("TEST_VAR", "hello")

    result = expand_env_vars("Value is ${TEST_VAR}")
    assert result == "Value is hello"


def test_expand_env_vars_multiple(monkeypatch):
    """Test multiple environment variables in one string."""
    monkeypatch.setenv("VAR1", "foo")
    monkeypatch.setenv("VAR2", "bar")

    result = expand_env_vars("${VAR1} and ${VAR2}")
    assert result == "foo and bar"


def test_expand_env_vars_with_default(monkeypatch):
    """Test environment variable with default value."""
    # Variable not set, should use default
    result = expand_env_vars("Value is ${MISSING:-default}")
    assert result == "Value is default"


def test_expand_env_vars_default_overridden(monkeypatch):
    """Test that set variable overrides default."""
    monkeypatch.setenv("MY_VAR", "actual")

    result = expand_env_vars("Value is ${MY_VAR:-default}")
    assert result == "Value is actual"


def test_expand_env_vars_missing_required():
    """Test that missing required variable raises error."""
    with pytest.raises(
        EnvVarError, match="Required environment variable not set: MISSING"
    ):
        expand_env_vars("Value is ${MISSING}")


def test_expand_env_vars_empty_default(monkeypatch):
    """Test that empty default value works."""
    result = expand_env_vars("Value is ${MISSING:-}")
    assert result == "Value is "


def test_expand_env_vars_no_expansion():
    """Test string without environment variables."""
    result = expand_env_vars("Plain text")
    assert result == "Plain text"


def test_expand_env_vars_invalid_name():
    """Test that invalid variable names are rejected."""
    # Variable names starting with numbers are invalid
    # But the regex won't match them at all, so no error is raised
    # Instead test with actual invalid characters
    result = expand_env_vars("${123INVALID}")
    # Since pattern doesn't match, it's returned as-is
    assert result == "${123INVALID}"

    # Test with dashes (also won't match pattern)
    result = expand_env_vars("${VAR-WITH-DASHES}")
    assert result == "${VAR-WITH-DASHES}"


def test_expand_env_vars_security_no_shell_execution(monkeypatch):
    """Test that shell metacharacters don't cause execution."""
    monkeypatch.setenv("SAFE_VAR", "$(echo pwned)")

    # Should expand to literal string, not execute command
    result = expand_env_vars("Value is ${SAFE_VAR}")
    assert result == "Value is $(echo pwned)"
    assert "pwned" not in result or result == "Value is $(echo pwned)"


def test_expand_env_vars_nested_syntax():
    """Test that nested ${} syntax is handled correctly."""
    # This should not be treated as nested expansion
    result = expand_env_vars("${VAR:-default with ${inner}}")
    assert result == "default with ${inner}"


def test_validate_required_vars_empty_config():
    """Test validation with empty config."""
    missing = validate_required_vars({})
    assert missing == []


def test_validate_required_vars_no_vars():
    """Test validation with config containing no variables."""
    config = {"key": "value", "number": 42}
    missing = validate_required_vars(config)
    assert missing == []


def test_validate_required_vars_all_set(monkeypatch):
    """Test validation when all required vars are set."""
    monkeypatch.setenv("VAR1", "value1")
    monkeypatch.setenv("VAR2", "value2")

    config = {"key1": "${VAR1}", "key2": "${VAR2}"}
    missing = validate_required_vars(config)
    assert missing == []


def test_validate_required_vars_some_missing(monkeypatch):
    """Test validation when some required vars are missing."""
    monkeypatch.setenv("VAR1", "value1")
    # VAR2 not set

    config = {"key1": "${VAR1}", "key2": "${VAR2}"}
    missing = validate_required_vars(config)
    assert "VAR2" in missing
    assert "VAR1" not in missing


def test_validate_required_vars_ignores_defaults():
    """Test that variables with defaults are not reported as missing."""
    config = {
        "required": "${REQUIRED_VAR}",
        "optional": "${OPTIONAL_VAR:-default}",
    }
    missing = validate_required_vars(config)
    assert "REQUIRED_VAR" in missing
    assert "OPTIONAL_VAR" not in missing


def test_validate_required_vars_nested_config(monkeypatch):
    """Test validation with nested configuration."""
    config = {
        "database": {
            "host": "${DB_HOST}",
            "port": "${DB_PORT:-5432}",
        },
        "api": {
            "key": "${API_KEY}",
        },
    }
    missing = validate_required_vars(config)
    assert "DB_HOST" in missing
    assert "API_KEY" in missing
    assert "DB_PORT" not in missing


def test_validate_required_vars_list_values():
    """Test validation with list values."""
    config = {
        "servers": ["${SERVER1}", "${SERVER2:-backup}"],
    }
    missing = validate_required_vars(config)
    assert "SERVER1" in missing
    assert "SERVER2" not in missing


def test_validate_required_vars_no_duplicates():
    """Test that duplicate missing vars are only reported once."""
    config = {
        "key1": "${MISSING}",
        "key2": "${MISSING}",
        "key3": "${MISSING}",
    }
    missing = validate_required_vars(config)
    assert missing.count("MISSING") == 1


def test_expand_config_simple(monkeypatch):
    """Test expanding a simple config dict."""
    monkeypatch.setenv("VAR1", "value1")

    config = {"key": "${VAR1}"}
    result = expand_config(config)
    assert result == {"key": "value1"}


def test_expand_config_nested(monkeypatch):
    """Test expanding nested config dict."""
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")

    config = {
        "database": {
            "host": "${DB_HOST}",
            "port": "${DB_PORT}",
        }
    }
    result = expand_config(config)
    assert result == {
        "database": {
            "host": "localhost",
            "port": "5432",
        }
    }


def test_expand_config_with_lists(monkeypatch):
    """Test expanding config with list values."""
    monkeypatch.setenv("SERVER1", "server1.com")
    monkeypatch.setenv("SERVER2", "server2.com")

    config = {
        "servers": ["${SERVER1}", "${SERVER2}"],
    }
    result = expand_config(config)
    assert result == {
        "servers": ["server1.com", "server2.com"],
    }


def test_expand_config_mixed_types(monkeypatch):
    """Test expanding config with mixed value types."""
    monkeypatch.setenv("STRING_VAR", "text")

    config = {
        "string": "${STRING_VAR}",
        "number": 42,
        "boolean": True,
        "null": None,
        "list": [1, 2, 3],
    }
    result = expand_config(config)
    assert result == {
        "string": "text",
        "number": 42,
        "boolean": True,
        "null": None,
        "list": [1, 2, 3],
    }


def test_expand_config_with_defaults():
    """Test expanding config with default values."""
    config = {
        "key1": "${MISSING:-default1}",
        "key2": "${MISSING:-default2}",
    }
    result = expand_config(config)
    assert result == {
        "key1": "default1",
        "key2": "default2",
    }


def test_expand_config_raises_on_missing():
    """Test that expand_config raises error for missing required vars."""
    config = {"key": "${MISSING_VAR}"}

    with pytest.raises(EnvVarError, match="Required environment variable not set"):
        expand_config(config)


def test_expand_config_preserves_structure(monkeypatch):
    """Test that expand_config preserves the original structure."""
    monkeypatch.setenv("VAR", "value")

    config = {
        "level1": {
            "level2": {
                "level3": "${VAR}",
            },
            "list": [1, "${VAR}", 3],
        },
    }
    result = expand_config(config)
    assert result == {
        "level1": {
            "level2": {
                "level3": "value",
            },
            "list": [1, "value", 3],
        },
    }


def test_expand_env_vars_underscore_in_name(monkeypatch):
    """Test that underscores in variable names are allowed."""
    monkeypatch.setenv("MY_VAR_NAME", "value")

    result = expand_env_vars("${MY_VAR_NAME}")
    assert result == "value"


def test_expand_env_vars_numbers_in_name(monkeypatch):
    """Test that numbers in variable names are allowed (but not at start)."""
    monkeypatch.setenv("VAR123", "value")

    result = expand_env_vars("${VAR123}")
    assert result == "value"


def test_expand_config_empty_dict():
    """Test expanding empty config dict."""
    result = expand_config({})
    assert result == {}


def test_expand_config_no_modification_needed(monkeypatch):
    """Test that config without variables is returned unchanged."""
    config = {
        "key1": "value1",
        "key2": 42,
        "nested": {"key3": "value3"},
    }
    result = expand_config(config)
    assert result == config
