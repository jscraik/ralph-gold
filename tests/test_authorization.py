"""Tests for authorization module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ralph_gold.authorization import (
    AuthorizationChecker,
    FilePermission,
    load_authorization_checker,
)


class TestFilePermission:
    """Tests for FilePermission dataclass."""

    def test_file_permission_creation(self) -> None:
        """Test creating a FilePermission."""
        perm = FilePermission(
            pattern="*.py",
            allow_write=True,
            reason="Python source files"
        )
        assert perm.pattern == "*.py"
        assert perm.allow_write is True
        assert perm.reason == "Python source files"

    def test_file_permission_defaults(self) -> None:
        """Test FilePermission default values."""
        perm = FilePermission(pattern="*.md")
        assert perm.allow_write is True  # default
        assert perm.reason == ""  # default


class TestAuthorizationChecker:
    """Tests for AuthorizationChecker dataclass."""

    def test_authorization_config_defaults(self) -> None:
        """Test AuthorizationChecker default values."""
        config = AuthorizationChecker()
        assert config.enabled is False
        assert config.fallback_to_full_auto is False
        assert config.permissions == []

    def test_authorization_config_with_permissions(self) -> None:
        """Test AuthorizationChecker with permissions."""
        perms = [
            FilePermission(pattern="*.py", allow_write=True),
            FilePermission(pattern="*.md", allow_write=True),
        ]
        config = AuthorizationChecker(
            enabled=True,
            fallback_to_full_auto=True,
            permissions=perms
        )
        assert config.enabled is True
        assert config.fallback_to_full_auto is True
        assert len(config.permissions) == 2

    def test_check_write_permission_disabled(self) -> None:
        """Test check_write_permission when disabled."""
        config = AuthorizationChecker(enabled=False)
        allowed, reason = config.check_write_permission(
            Path("test.py"),
            ["codex", "exec", "-"]
        )
        assert allowed is True
        assert reason == "Authorization disabled"

    def test_check_write_permission_fallback(self) -> None:
        """Test check_write_permission with --full-auto fallback."""
        config = AuthorizationChecker(
            enabled=True,
            fallback_to_full_auto=True,
            permissions=[]
        )
        allowed, reason = config.check_write_permission(
            Path("test.py"),
            ["codex", "exec", "--full-auto", "-"]
        )
        assert allowed is True
        assert "--full-auto" in reason

    def test_check_write_permission_allowed_pattern(self) -> None:
        """Test check_write_permission with matching allow pattern."""
        config = AuthorizationChecker(
            enabled=True,
            permissions=[
                FilePermission(pattern="*.py", allow_write=True, reason="Allowed")
            ]
        )
        allowed, reason = config.check_write_permission(
            Path("test.py"),
            ["codex", "exec", "-"]
        )
        assert allowed is True
        assert "Allowed" in reason

    def test_check_write_permission_denied_pattern(self) -> None:
        """Test check_write_permission with matching deny pattern."""
        config = AuthorizationChecker(
            enabled=True,
            permissions=[
                FilePermission(pattern="*", allow_write=False, reason="Blocked")
            ]
        )
        allowed, reason = config.check_write_permission(
            Path("test.py"),
            ["codex", "exec", "-"]
        )
        assert allowed is False
        assert "Blocked" in reason

    def test_check_write_permission_no_match(self) -> None:
        """Test check_write_permission with no matching pattern (fail-open)."""
        config = AuthorizationChecker(
            enabled=True,
            permissions=[]  # Empty patterns
        )
        allowed, reason = config.check_write_permission(
            Path("test.py"),
            ["codex", "exec", "-"]
        )
        assert allowed is True  # Fail-open default
        assert "no matching patterns" in reason


class TestLoadAuthorizationChecker:
    """Tests for load_authorization_checker function."""

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading when file doesn't exist."""
        config = load_authorization_checker(tmp_path)
        assert config.enabled is False
        assert config.permissions == []

    def test_load_valid_json(self, tmp_path: Path) -> None:
        """Test loading valid JSON."""
        perm_path = tmp_path / ".ralph" / "permissions.json"
        perm_path.parent.mkdir(parents=True, exist_ok=True)
        perm_path.write_text(json.dumps({
            "enabled": True,
            "fallback_to_full_auto": True,
            "permissions": [
                {
                    "pattern": "*.py",
                    "allow_write": True,
                    "reason": "Python files"
                }
            ]
        }))

        config = load_authorization_checker(tmp_path)
        assert config.enabled is True
        assert config.fallback_to_full_auto is True
        assert len(config.permissions) == 1
        assert config.permissions[0].pattern == "*.py"

    def test_load_invalid_json(self, tmp_path: Path) -> None:
        """Test loading invalid JSON returns disabled config."""
        perm_path = tmp_path / ".ralph" / "permissions.json"
        perm_path.parent.mkdir(parents=True, exist_ok=True)
        perm_path.write_text("invalid json {")

        config = load_authorization_checker(tmp_path)
        assert config.enabled is False  # Fail-safe
        assert config.permissions == []

    def test_load_partial_config(self, tmp_path: Path) -> None:
        """Test loading partial config uses defaults."""
        perm_path = tmp_path / ".ralph" / "permissions.json"
        perm_path.parent.mkdir(parents=True, exist_ok=True)
        perm_path.write_text(json.dumps({
            "enabled": True
            # Missing fallback_to_full_auto and permissions
        }))

        config = load_authorization_checker(tmp_path)
        assert config.enabled is True
        assert config.fallback_to_full_auto is False  # Default
        assert config.permissions == []  # Default


class TestIntegration:
    """Integration tests for authorization."""

    def test_full_flow(self, tmp_path: Path) -> None:
        """Test full authorization flow."""
        # Create permissions.json
        perm_path = tmp_path / ".ralph" / "permissions.json"
        perm_path.parent.mkdir(parents=True, exist_ok=True)
        perm_path.write_text(json.dumps({
            "enabled": True,
            "fallback_to_full_auto": False,
            "permissions": [
                {
                    "pattern": "src/**",
                    "allow_write": True,
                    "reason": "Source code"
                },
                {
                    "pattern": ".git/**",
                    "allow_write": False,
                    "reason": "Git internals"
                }
            ]
        }))

        # Load and check
        config = load_authorization_checker(tmp_path)

        # Source file should be allowed
        allowed, reason = config.check_write_permission(
            tmp_path / "src" / "main.py",
            ["codex", "exec", "-"]
        )
        assert allowed is True
        assert "Source code" in reason

        # Git file should be denied
        allowed, reason = config.check_write_permission(
            tmp_path / ".git" / "config",
            ["codex", "exec", "-"]
        )
        assert allowed is False
        assert "Git internals" in reason
