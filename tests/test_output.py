"""Unit tests for output control module.

This module tests the output control functionality including quiet mode,
verbose mode, JSON output, and error preservation.
"""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from ralph_gold.output import (
    OutputConfig,
    format_json_output,
    get_output_config,
    print_json_output,
    print_output,
    set_output_config,
)

# -------------------------
# Fixtures
# -------------------------


@pytest.fixture
def reset_output_config():
    """Reset global output config before and after each test."""
    # Import the module to access the global
    import ralph_gold.output as output_module

    original = output_module._output_config
    output_module._output_config = None
    yield
    output_module._output_config = original


# -------------------------
# OutputConfig Tests
# -------------------------


def test_output_config_defaults():
    """Test OutputConfig default values."""
    config = OutputConfig()
    assert config.verbosity == "normal"
    assert config.format == "text"
    assert config.color is True


def test_output_config_custom_values():
    """Test OutputConfig with custom values."""
    config = OutputConfig(verbosity="quiet", format="json", color=False)
    assert config.verbosity == "quiet"
    assert config.format == "json"
    assert config.color is False


def test_output_config_all_verbosity_levels():
    """Test all valid verbosity levels."""
    for level in ["quiet", "normal", "verbose"]:
        config = OutputConfig(verbosity=level)
        assert config.verbosity == level


def test_output_config_all_formats():
    """Test all valid format types."""
    for fmt in ["text", "json"]:
        config = OutputConfig(format=fmt)
        assert config.format == fmt


# -------------------------
# get_output_config Tests
# -------------------------


def test_get_output_config_default(reset_output_config):
    """Test get_output_config returns default config."""
    config = get_output_config()
    assert config.verbosity == "normal"
    assert config.format == "text"
    assert config.color is True


def test_get_output_config_from_env(reset_output_config, monkeypatch):
    """Test get_output_config reads from environment variables."""
    monkeypatch.setenv("RALPH_VERBOSITY", "quiet")
    monkeypatch.setenv("RALPH_FORMAT", "json")

    config = get_output_config()
    assert config.verbosity == "quiet"
    assert config.format == "json"


def test_get_output_config_invalid_env_values(reset_output_config, monkeypatch):
    """Test get_output_config handles invalid environment values."""
    monkeypatch.setenv("RALPH_VERBOSITY", "invalid")
    monkeypatch.setenv("RALPH_FORMAT", "invalid")

    config = get_output_config()
    # Should fall back to defaults
    assert config.verbosity == "normal"
    assert config.format == "text"


def test_get_output_config_returns_set_config(reset_output_config):
    """Test get_output_config returns previously set config."""
    custom_config = OutputConfig(verbosity="verbose", format="json")
    set_output_config(custom_config)

    config = get_output_config()
    assert config.verbosity == "verbose"
    assert config.format == "json"


# -------------------------
# set_output_config Tests
# -------------------------


def test_set_output_config(reset_output_config):
    """Test set_output_config sets global config."""
    config = OutputConfig(verbosity="quiet", format="json")
    set_output_config(config)

    retrieved = get_output_config()
    assert retrieved.verbosity == "quiet"
    assert retrieved.format == "json"


def test_set_output_config_overrides_env(reset_output_config, monkeypatch):
    """Test set_output_config overrides environment variables."""
    monkeypatch.setenv("RALPH_VERBOSITY", "verbose")

    config = OutputConfig(verbosity="quiet")
    set_output_config(config)

    retrieved = get_output_config()
    assert retrieved.verbosity == "quiet"


# -------------------------
# print_output Tests - Quiet Mode
# -------------------------


def test_print_output_quiet_mode_suppresses_normal(reset_output_config, capsys):
    """Test quiet mode suppresses normal-level messages."""
    set_output_config(OutputConfig(verbosity="quiet"))

    print_output("This should not appear", level="normal")

    captured = capsys.readouterr()
    assert captured.out == ""


def test_print_output_quiet_mode_suppresses_verbose(reset_output_config, capsys):
    """Test quiet mode suppresses verbose-level messages."""
    set_output_config(OutputConfig(verbosity="quiet"))

    print_output("This should not appear", level="verbose")

    captured = capsys.readouterr()
    assert captured.out == ""


def test_print_output_quiet_mode_shows_quiet_messages(reset_output_config, capsys):
    """Test quiet mode shows quiet-level messages."""
    set_output_config(OutputConfig(verbosity="quiet"))

    print_output("This should appear", level="quiet")

    captured = capsys.readouterr()
    assert "This should appear" in captured.out


def test_print_output_quiet_mode_shows_errors(reset_output_config, capsys):
    """Test quiet mode shows error messages."""
    set_output_config(OutputConfig(verbosity="quiet"))

    print_output("Error message", level="error")

    captured = capsys.readouterr()
    assert "Error message" in captured.err


# -------------------------
# print_output Tests - Normal Mode
# -------------------------


def test_print_output_normal_mode_shows_normal(reset_output_config, capsys):
    """Test normal mode shows normal-level messages."""
    set_output_config(OutputConfig(verbosity="normal"))

    print_output("Normal message", level="normal")

    captured = capsys.readouterr()
    assert "Normal message" in captured.out


def test_print_output_normal_mode_shows_quiet(reset_output_config, capsys):
    """Test normal mode shows quiet-level messages."""
    set_output_config(OutputConfig(verbosity="normal"))

    print_output("Quiet message", level="quiet")

    captured = capsys.readouterr()
    assert "Quiet message" in captured.out


def test_print_output_normal_mode_suppresses_verbose(reset_output_config, capsys):
    """Test normal mode suppresses verbose-level messages."""
    set_output_config(OutputConfig(verbosity="normal"))

    print_output("Verbose message", level="verbose")

    captured = capsys.readouterr()
    assert captured.out == ""


def test_print_output_normal_mode_shows_errors(reset_output_config, capsys):
    """Test normal mode shows error messages."""
    set_output_config(OutputConfig(verbosity="normal"))

    print_output("Error message", level="error")

    captured = capsys.readouterr()
    assert "Error message" in captured.err


# -------------------------
# print_output Tests - Verbose Mode
# -------------------------


def test_print_output_verbose_mode_shows_all(reset_output_config, capsys):
    """Test verbose mode shows all message levels."""
    set_output_config(OutputConfig(verbosity="verbose"))

    print_output("Quiet message", level="quiet")
    print_output("Normal message", level="normal")
    print_output("Verbose message", level="verbose")

    captured = capsys.readouterr()
    assert "Quiet message" in captured.out
    assert "Normal message" in captured.out
    assert "Verbose message" in captured.out


def test_print_output_verbose_mode_shows_errors(reset_output_config, capsys):
    """Test verbose mode shows error messages."""
    set_output_config(OutputConfig(verbosity="verbose"))

    print_output("Error message", level="error")

    captured = capsys.readouterr()
    assert "Error message" in captured.err


# -------------------------
# print_output Tests - Error Preservation
# -------------------------


def test_print_output_errors_always_shown_quiet(reset_output_config, capsys):
    """Test errors are shown in quiet mode."""
    set_output_config(OutputConfig(verbosity="quiet"))

    print_output("Critical error", level="error")

    captured = capsys.readouterr()
    assert "Critical error" in captured.err


def test_print_output_errors_always_shown_normal(reset_output_config, capsys):
    """Test errors are shown in normal mode."""
    set_output_config(OutputConfig(verbosity="normal"))

    print_output("Critical error", level="error")

    captured = capsys.readouterr()
    assert "Critical error" in captured.err


def test_print_output_errors_always_shown_verbose(reset_output_config, capsys):
    """Test errors are shown in verbose mode."""
    set_output_config(OutputConfig(verbosity="verbose"))

    print_output("Critical error", level="error")

    captured = capsys.readouterr()
    assert "Critical error" in captured.err


def test_print_output_errors_go_to_stderr(reset_output_config, capsys):
    """Test error messages are written to stderr."""
    set_output_config(OutputConfig(verbosity="normal"))

    print_output("Error message", level="error")

    captured = capsys.readouterr()
    assert "Error message" in captured.err
    assert captured.out == ""


def test_print_output_normal_goes_to_stdout(reset_output_config, capsys):
    """Test normal messages are written to stdout."""
    set_output_config(OutputConfig(verbosity="normal"))

    print_output("Normal message", level="normal")

    captured = capsys.readouterr()
    assert "Normal message" in captured.out
    assert captured.err == ""


# -------------------------
# print_output Tests - JSON Format
# -------------------------


def test_print_output_json_format_suppresses_text(reset_output_config, capsys):
    """Test JSON format suppresses all text output."""
    set_output_config(OutputConfig(format="json"))

    print_output("This should not appear", level="normal")
    print_output("This should not appear", level="quiet")
    print_output("This should not appear", level="verbose")

    captured = capsys.readouterr()
    assert captured.out == ""


def test_print_output_json_format_suppresses_errors(reset_output_config, capsys):
    """Test JSON format suppresses error text output."""
    set_output_config(OutputConfig(format="json"))

    print_output("Error message", level="error")

    captured = capsys.readouterr()
    assert captured.err == ""


# -------------------------
# print_output Tests - Unknown Level
# -------------------------


def test_print_output_unknown_level_treated_as_normal(reset_output_config, capsys):
    """Test unknown message level is treated as normal."""
    set_output_config(OutputConfig(verbosity="normal"))

    print_output("Unknown level message", level="unknown")

    captured = capsys.readouterr()
    assert "Unknown level message" in captured.out


def test_print_output_unknown_level_suppressed_in_quiet(reset_output_config, capsys):
    """Test unknown message level is suppressed in quiet mode."""
    set_output_config(OutputConfig(verbosity="quiet"))

    print_output("Unknown level message", level="unknown")

    captured = capsys.readouterr()
    assert captured.out == ""


# -------------------------
# format_json_output Tests
# -------------------------


def test_format_json_output_simple_dict():
    """Test format_json_output with simple dictionary."""
    data = {"key": "value", "number": 42}
    result = format_json_output(data)

    # Should be valid JSON
    parsed = json.loads(result)
    assert parsed == data


def test_format_json_output_nested_dict():
    """Test format_json_output with nested dictionary."""
    data = {
        "level1": {
            "level2": {
                "key": "value",
            }
        }
    }
    result = format_json_output(data)

    parsed = json.loads(result)
    assert parsed == data


def test_format_json_output_with_lists():
    """Test format_json_output with lists."""
    data = {
        "items": [1, 2, 3],
        "names": ["alice", "bob"],
    }
    result = format_json_output(data)

    parsed = json.loads(result)
    assert parsed == data


def test_format_json_output_pretty_printed():
    """Test format_json_output produces pretty-printed output."""
    data = {"key": "value"}
    result = format_json_output(data)

    # Pretty-printed JSON should have newlines and indentation
    assert "\n" in result
    assert "  " in result  # Indentation


def test_format_json_output_unicode():
    """Test format_json_output handles unicode characters."""
    data = {"message": "Hello 世界 🌍"}
    result = format_json_output(data)

    parsed = json.loads(result)
    assert parsed == data
    # Should preserve unicode, not escape it
    assert "世界" in result
    assert "🌍" in result


def test_format_json_output_special_values():
    """Test format_json_output handles special values."""
    data = {
        "null": None,
        "boolean": True,
        "number": 42.5,
        "string": "text",
    }
    result = format_json_output(data)

    parsed = json.loads(result)
    assert parsed == data


def test_format_json_output_empty_dict():
    """Test format_json_output with empty dictionary."""
    data: Dict[str, Any] = {}
    result = format_json_output(data)

    parsed = json.loads(result)
    assert parsed == data


# -------------------------
# print_json_output Tests
# -------------------------


def test_print_json_output_in_json_mode(reset_output_config, capsys):
    """Test print_json_output prints JSON in JSON mode."""
    set_output_config(OutputConfig(format="json"))

    data = {"status": "success", "count": 42}
    print_json_output(data)

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed == data


def test_print_json_output_in_text_mode(reset_output_config, capsys):
    """Test print_json_output does nothing in text mode."""
    set_output_config(OutputConfig(format="text"))

    data = {"status": "success"}
    print_json_output(data)

    captured = capsys.readouterr()
    assert captured.out == ""


def test_print_json_output_complex_data(reset_output_config, capsys):
    """Test print_json_output with complex data structure."""
    set_output_config(OutputConfig(format="json"))

    data = {
        "tasks": [
            {"id": "task-1", "status": "complete"},
            {"id": "task-2", "status": "pending"},
        ],
        "summary": {
            "total": 2,
            "complete": 1,
        },
    }
    print_json_output(data)

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed == data


# -------------------------
# Integration Tests
# -------------------------


def test_quiet_mode_workflow(reset_output_config, capsys):
    """Test complete quiet mode workflow."""
    set_output_config(OutputConfig(verbosity="quiet"))

    # Normal messages should be suppressed
    print_output("Starting process...", level="normal")
    print_output("Processing item 1...", level="normal")
    print_output("Processing item 2...", level="normal")

    # Quiet messages should appear
    print_output("Process complete: 2 items", level="quiet")

    # Errors should appear
    print_output("Warning: deprecated feature", level="error")

    captured = capsys.readouterr()

    # Only quiet message in stdout
    assert "Process complete: 2 items" in captured.out
    assert "Starting process" not in captured.out
    assert "Processing item" not in captured.out

    # Error in stderr
    assert "Warning: deprecated feature" in captured.err


def test_verbose_mode_workflow(reset_output_config, capsys):
    """Test complete verbose mode workflow."""
    set_output_config(OutputConfig(verbosity="verbose"))

    print_output("Starting process...", level="normal")
    print_output("Debug: loading config", level="verbose")
    print_output("Debug: connecting to service", level="verbose")
    print_output("Process complete", level="quiet")
    print_output("Error occurred", level="error")

    captured = capsys.readouterr()

    # All non-error messages in stdout
    assert "Starting process" in captured.out
    assert "Debug: loading config" in captured.out
    assert "Debug: connecting to service" in captured.out
    assert "Process complete" in captured.out

    # Error in stderr
    assert "Error occurred" in captured.err


def test_json_mode_workflow(reset_output_config, capsys):
    """Test complete JSON mode workflow."""
    set_output_config(OutputConfig(format="json"))

    # Text output should be suppressed
    print_output("Starting...", level="normal")
    print_output("Processing...", level="verbose")
    print_output("Error!", level="error")

    # JSON output should work
    result_data = {"status": "complete", "items": 5}
    print_json_output(result_data)

    captured = capsys.readouterr()

    # No text output
    assert "Starting" not in captured.out
    assert "Processing" not in captured.out
    assert "Error!" not in captured.out
    assert "Error!" not in captured.err

    # Only JSON output
    parsed = json.loads(captured.out)
    assert parsed == result_data


def test_mixed_verbosity_levels(reset_output_config, capsys):
    """Test mixing different verbosity levels in normal mode."""
    set_output_config(OutputConfig(verbosity="normal"))

    print_output("Quiet level", level="quiet")
    print_output("Normal level", level="normal")
    print_output("Verbose level", level="verbose")

    captured = capsys.readouterr()

    assert "Quiet level" in captured.out
    assert "Normal level" in captured.out
    assert "Verbose level" not in captured.out


def test_config_persistence(reset_output_config, capsys):
    """Test that config persists across multiple calls."""
    set_output_config(OutputConfig(verbosity="quiet"))

    print_output("Message 1", level="normal")
    print_output("Message 2", level="normal")
    print_output("Message 3", level="quiet")

    captured = capsys.readouterr()

    # Only quiet message should appear
    assert "Message 1" not in captured.out
    assert "Message 2" not in captured.out
    assert "Message 3" in captured.out


# -------------------------
# Edge Cases
# -------------------------


def test_empty_message(reset_output_config, capsys):
    """Test print_output with empty message."""
    set_output_config(OutputConfig(verbosity="normal"))

    print_output("", level="normal")

    captured = capsys.readouterr()
    # Should print empty line
    assert captured.out == "\n"


def test_multiline_message(reset_output_config, capsys):
    """Test print_output with multiline message."""
    set_output_config(OutputConfig(verbosity="normal"))

    message = "Line 1\nLine 2\nLine 3"
    print_output(message, level="normal")

    captured = capsys.readouterr()
    assert "Line 1" in captured.out
    assert "Line 2" in captured.out
    assert "Line 3" in captured.out


def test_message_with_special_characters(reset_output_config, capsys):
    """Test print_output with special characters."""
    set_output_config(OutputConfig(verbosity="normal"))

    message = "Special: \t\n\r 世界 🎉"
    print_output(message, level="normal")

    captured = capsys.readouterr()
    assert "Special:" in captured.out
    assert "世界" in captured.out
    assert "🎉" in captured.out


def test_very_long_message(reset_output_config, capsys):
    """Test print_output with very long message."""
    set_output_config(OutputConfig(verbosity="normal"))

    message = "x" * 10000
    print_output(message, level="normal")

    captured = capsys.readouterr()
    assert len(captured.out) >= 10000


def test_format_json_output_with_none_values():
    """Test format_json_output handles None values correctly."""
    data = {
        "key1": None,
        "key2": "value",
        "key3": None,
    }
    result = format_json_output(data)

    parsed = json.loads(result)
    assert parsed == data
    assert parsed["key1"] is None
    assert parsed["key3"] is None
