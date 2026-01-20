"""Tests for authorization module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ralph_gold.authorization import (
    AuthorizationChecker,
    AuthorizationError,
    EnforcementMode,
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


class TestEnforcementMode:
    """Tests for EnforcementMode enum."""

    def test_enforcement_mode_values(self) -> None:
        """Test EnforcementMode has correct values."""
        assert EnforcementMode.WARN.value == "warn"
        assert EnforcementMode.BLOCK.value == "block"

    def test_enforcement_mode_from_string(self) -> None:
        """Test creating EnforcementMode from string."""
        mode = EnforcementMode("warn")
        assert mode == EnforcementMode.WARN

        mode = EnforcementMode("block")
        assert mode == EnforcementMode.BLOCK

    def test_enforcement_mode_invalid_string(self) -> None:
        """Test invalid string raises ValueError."""
        with pytest.raises(ValueError):
            EnforcementMode("invalid")


class TestAuthorizationError:
    """Tests for AuthorizationError exception."""

    def test_authorization_error_creation(self) -> None:
        """Test creating AuthorizationError."""
        error = AuthorizationError(Path("/test/file.py"), "Denied by policy")
        assert error.file_path == Path("/test/file.py")
        assert error.reason == "Denied by policy"
        assert "Denied by policy" in str(error)

    def test_authorization_error_message(self) -> None:
        """Test AuthorizationError message format."""
        error = AuthorizationError(Path("/test/file.py"), "Test reason")
        message = str(error)
        assert "Write not permitted" in message
        assert "Test reason" in message


class TestAuthorizationCheckerEnforcementModes:
    """Tests for enforcement mode behavior in AuthorizationChecker."""

    def test_warn_mode_denied_write_returns_false(self) -> None:
        """Test warn mode returns (False, reason) instead of raising."""
        config = AuthorizationChecker(
            enabled=True,
            enforcement_mode=EnforcementMode.WARN,
            permissions=[
                FilePermission(pattern="*.py", allow_write=False, reason="No Python files")
            ]
        )
        allowed, reason = config.check_write_permission(Path("test.py"), [])
        assert allowed is False
        assert "No Python files" in reason

    def test_block_mode_denied_write_raises_exception(self) -> None:
        """Test block mode raises AuthorizationError when denied."""
        config = AuthorizationChecker(
            enabled=True,
            enforcement_mode=EnforcementMode.BLOCK,
            permissions=[
                FilePermission(pattern="*.py", allow_write=False, reason="No Python files")
            ]
        )
        with pytest.raises(AuthorizationError) as exc_info:
            config.check_write_permission(Path("test.py"), [])
        assert "No Python files" in str(exc_info.value)

    def test_block_mode_with_raise_on_block_false(self) -> None:
        """Test block mode with raise_on_block=False returns tuple."""
        config = AuthorizationChecker(
            enabled=True,
            enforcement_mode=EnforcementMode.BLOCK,
            permissions=[
                FilePermission(pattern="*.py", allow_write=False, reason="No Python files")
            ]
        )
        # With raise_on_block=False, should return tuple instead of raising
        allowed, reason = config.check_write_permission(Path("test.py"), [], raise_on_block=False)
        assert allowed is False
        assert "No Python files" in reason

    def test_warn_mode_allowed_write(self) -> None:
        """Test warn mode allows writes when permitted."""
        config = AuthorizationChecker(
            enabled=True,
            enforcement_mode=EnforcementMode.WARN,
            permissions=[
                FilePermission(pattern="*.py", allow_write=True, reason="Allowed")
            ]
        )
        allowed, reason = config.check_write_permission(Path("test.py"), [])
        assert allowed is True
        assert "Allowed" in reason

    def test_block_mode_allowed_write(self) -> None:
        """Test block mode allows writes when permitted."""
        config = AuthorizationChecker(
            enabled=True,
            enforcement_mode=EnforcementMode.BLOCK,
            permissions=[
                FilePermission(pattern="*.py", allow_write=True, reason="Allowed")
            ]
        )
        allowed, reason = config.check_write_permission(Path("test.py"), [])
        assert allowed is True
        assert "Allowed" in reason

    def test_warn_mode_default(self) -> None:
        """Test WARN is the default enforcement mode."""
        config = AuthorizationChecker(enabled=True)
        assert config.enforcement_mode == EnforcementMode.WARN


class TestLoadAuthorizationCheckerWithEnforcementMode:
    """Tests for loading enforcement_mode from config file."""

    def test_load_with_enforcement_mode_warn(self, tmp_path: Path) -> None:
        """Test loading enforcement_mode='warn' from config."""
        perm_path = tmp_path / ".ralph" / "permissions.json"
        perm_path.parent.mkdir(parents=True, exist_ok=True)
        perm_path.write_text(json.dumps({
            "enabled": True,
            "enforcement_mode": "warn",
            "permissions": [
                {"pattern": "*.py", "allow_write": True}
            ]
        }))

        config = load_authorization_checker(tmp_path)
        assert config.enforcement_mode == EnforcementMode.WARN

    def test_load_with_enforcement_mode_block(self, tmp_path: Path) -> None:
        """Test loading enforcement_mode='block' from config."""
        perm_path = tmp_path / ".ralph" / "permissions.json"
        perm_path.parent.mkdir(parents=True, exist_ok=True)
        perm_path.write_text(json.dumps({
            "enabled": True,
            "enforcement_mode": "block",
            "permissions": [
                {"pattern": "*.py", "allow_write": True}
            ]
        }))

        config = load_authorization_checker(tmp_path)
        assert config.enforcement_mode == EnforcementMode.BLOCK

    def test_load_with_invalid_enforcement_mode_defaults_to_warn(self, tmp_path: Path) -> None:
        """Test invalid enforcement_mode defaults to warn."""
        perm_path = tmp_path / ".ralph" / "permissions.json"
        perm_path.parent.mkdir(parents=True, exist_ok=True)
        perm_path.write_text(json.dumps({
            "enabled": True,
            "enforcement_mode": "invalid_mode",
            "permissions": [
                {"pattern": "*.py", "allow_write": True}
            ]
        }))

        config = load_authorization_checker(tmp_path)
        # Should default to WARN when invalid
        assert config.enforcement_mode == EnforcementMode.WARN

    def test_load_without_enforcement_mode_uses_default(self, tmp_path: Path) -> None:
        """Test missing enforcement_mode uses default from parameter."""
        perm_path = tmp_path / ".ralph" / "permissions.json"
        perm_path.parent.mkdir(parents=True, exist_ok=True)
        perm_path.write_text(json.dumps({
            "enabled": True,
            "permissions": [
                {"pattern": "*.py", "allow_write": True}
            ]
        }))

        # Explicitly pass BLOCK as default
        config = load_authorization_checker(
            tmp_path,
            enforcement_mode=EnforcementMode.BLOCK
        )
        assert config.enforcement_mode == EnforcementMode.BLOCK

    def test_load_nonexistent_file_uses_default_enforcement_mode(self, tmp_path: Path) -> None:
        """Test nonexistent file uses default enforcement_mode."""
        config = load_authorization_checker(
            tmp_path,
            enforcement_mode=EnforcementMode.BLOCK
        )
        assert config.enforcement_mode == EnforcementMode.BLOCK
        assert config.enabled is False

    def test_integration_block_mode_blocks_denied_writes(self, tmp_path: Path) -> None:
        """Integration test: block mode actually blocks denied writes."""
        perm_path = tmp_path / ".ralph" / "permissions.json"
        perm_path.parent.mkdir(parents=True, exist_ok=True)
        perm_path.write_text(json.dumps({
            "enabled": True,
            "enforcement_mode": "block",
            "permissions": [
                {
                    "pattern": "src/**",
                    "allow_write": True,
                    "reason": "Source code allowed"
                },
                {
                    "pattern": ".git/**",
                    "allow_write": False,
                    "reason": "Git internals blocked"
                }
            ]
        }))

        config = load_authorization_checker(tmp_path)

        # Source file should be allowed
        allowed, reason = config.check_write_permission(
            tmp_path / "src" / "main.py",
            []
        )
        assert allowed is True

        # Git file should raise exception
        with pytest.raises(AuthorizationError) as exc_info:
            config.check_write_permission(tmp_path / ".git" / "config", [])
        assert "Git internals blocked" in str(exc_info.value)

    def test_integration_warn_mode_logs_denied_writes(self, tmp_path: Path) -> None:
        """Integration test: warn mode logs but allows denied writes."""
        perm_path = tmp_path / ".ralph" / "permissions.json"
        perm_path.parent.mkdir(parents=True, exist_ok=True)
        perm_path.write_text(json.dumps({
            "enabled": True,
            "enforcement_mode": "warn",
            "permissions": [
                {
                    "pattern": ".git/**",
                    "allow_write": False,
                    "reason": "Git internals blocked (warn mode)"
                }
            ]
        }))

        config = load_authorization_checker(tmp_path)

        # Should return denied, not raise
        allowed, reason = config.check_write_permission(
            tmp_path / ".git" / "config",
            []
        )
        assert allowed is False
        assert "Git internals blocked (warn mode)" in reason
