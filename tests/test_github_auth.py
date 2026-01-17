"""Tests for GitHub authentication layer."""

from __future__ import annotations

import json
import os
import subprocess
from unittest.mock import Mock, patch

import pytest

from ralph_gold.github_auth import (
    GhCliAuth,
    GitHubAuthError,
    TokenAuth,
    create_auth,
)


class TestGhCliAuth:
    """Tests for gh CLI authentication."""

    def test_init_gh_not_installed(self):
        """Test initialization fails when gh CLI is not installed."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with pytest.raises(GitHubAuthError, match="gh CLI is not installed"):
                GhCliAuth()

    def test_init_gh_installed(self):
        """Test initialization succeeds when gh CLI is installed."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            auth = GhCliAuth()
            assert auth is not None
            assert repr(auth) == "GhCliAuth()"

    def test_validate_authenticated(self):
        """Test validate returns True when authenticated."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            # Mock gh --version check
            mock_run.return_value = Mock(returncode=0)
            auth = GhCliAuth()

            # Mock gh api /user check
            mock_run.return_value = Mock(
                returncode=0, stdout='{"login": "testuser"}', stderr=""
            )

            assert auth.validate() is True

    def test_validate_not_authenticated(self):
        """Test validate returns False when not authenticated."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            # Mock gh --version check
            mock_run.return_value = Mock(returncode=0)
            auth = GhCliAuth()

            # Mock gh api /user check fails
            mock_run.side_effect = subprocess.CalledProcessError(1, "gh")

            assert auth.validate() is False

    def test_validate_invalid_json(self):
        """Test validate handles invalid JSON response."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            # Mock gh --version check
            mock_run.return_value = Mock(returncode=0)
            auth = GhCliAuth()

            # Mock gh api /user returns invalid JSON
            mock_run.return_value = Mock(returncode=0, stdout="invalid json", stderr="")

            assert auth.validate() is False

    def test_validate_timeout(self):
        """Test validate handles timeout."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            # Mock gh --version check
            mock_run.return_value = Mock(returncode=0)
            auth = GhCliAuth()

            # Mock gh api /user times out
            mock_run.side_effect = subprocess.TimeoutExpired("gh", 10)

            assert auth.validate() is False

    def test_api_call_get(self):
        """Test API call with GET method."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            # Mock gh --version check
            mock_run.return_value = Mock(returncode=0)
            auth = GhCliAuth()

            # Mock API call
            mock_run.return_value = Mock(
                returncode=0, stdout='{"data": "test"}', stderr=""
            )

            result = auth.api_call("GET", "/repos/owner/repo/issues")

            assert result == {"data": "test"}
            # Verify command
            call_args = mock_run.call_args[0][0]
            assert "gh" in call_args
            assert "api" in call_args
            assert "/repos/owner/repo/issues" in call_args
            assert "-X" in call_args
            assert "GET" in call_args

    def test_api_call_post_with_data(self):
        """Test API call with POST method and data."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            # Mock gh --version check
            mock_run.return_value = Mock(returncode=0)
            auth = GhCliAuth()

            # Mock API call
            mock_run.return_value = Mock(returncode=0, stdout='{"id": 1}', stderr="")

            data = {"title": "Test Issue"}
            result = auth.api_call("POST", "/repos/owner/repo/issues", data)

            assert result == {"id": 1}
            # Verify data was passed as stdin
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["input"] == json.dumps(data)

    def test_api_call_empty_response(self):
        """Test API call with empty response."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            # Mock gh --version check
            mock_run.return_value = Mock(returncode=0)
            auth = GhCliAuth()

            # Mock API call with empty response
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = auth.api_call("DELETE", "/repos/owner/repo/issues/1")

            assert result == {}

    def test_api_call_authentication_error(self):
        """Test API call handles authentication errors."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            # Mock gh --version check
            mock_run.return_value = Mock(returncode=0)
            auth = GhCliAuth()

            # Mock API call fails with auth error
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "gh", stderr="authentication failed"
            )

            with pytest.raises(GitHubAuthError, match="authentication failed"):
                auth.api_call("GET", "/user")

    def test_api_call_not_found_error(self):
        """Test API call handles not found errors."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            # Mock gh --version check
            mock_run.return_value = Mock(returncode=0)
            auth = GhCliAuth()

            # Mock API call fails with not found
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "gh", stderr="not found"
            )

            with pytest.raises(GitHubAuthError, match="not found"):
                auth.api_call("GET", "/repos/invalid/repo")

    def test_api_call_rate_limit_error(self):
        """Test API call handles rate limit errors."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            # Mock gh --version check
            mock_run.return_value = Mock(returncode=0)
            auth = GhCliAuth()

            # Mock API call fails with rate limit
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "gh", stderr="rate limit exceeded"
            )

            with pytest.raises(GitHubAuthError, match="rate limit"):
                auth.api_call("GET", "/user")

    def test_api_call_timeout(self):
        """Test API call handles timeout."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            # Mock gh --version check
            mock_run.return_value = Mock(returncode=0)
            auth = GhCliAuth()

            # Mock API call times out
            mock_run.side_effect = subprocess.TimeoutExpired("gh", 30)

            with pytest.raises(GitHubAuthError, match="timed out"):
                auth.api_call("GET", "/user")

    def test_api_call_invalid_json_response(self):
        """Test API call handles invalid JSON response."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            # Mock gh --version check
            mock_run.return_value = Mock(returncode=0)
            auth = GhCliAuth()

            # Mock API call returns invalid JSON
            mock_run.return_value = Mock(returncode=0, stdout="invalid json", stderr="")

            with pytest.raises(GitHubAuthError, match="Failed to parse"):
                auth.api_call("GET", "/user")


class TestTokenAuth:
    """Tests for token-based authentication."""

    def test_init_with_token(self):
        """Test initialization with explicit token."""
        auth = TokenAuth(token="ghp_test123456789")
        assert auth is not None
        assert repr(auth) == "TokenAuth(***)"

    def test_init_from_env(self):
        """Test initialization from environment variable."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test123456789"}):
            auth = TokenAuth()
            assert auth is not None

    def test_init_custom_env_var(self):
        """Test initialization from custom environment variable."""
        with patch.dict(os.environ, {"MY_TOKEN": "ghp_test123456789"}):
            auth = TokenAuth(token_env="MY_TOKEN")
            assert auth is not None

    def test_init_no_token(self):
        """Test initialization fails when no token provided."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(GitHubAuthError, match="token not found"):
                TokenAuth()

    def test_init_validates_token_format(self):
        """Test initialization accepts various token formats."""
        # Modern token formats
        TokenAuth(token="ghp_test123456789")
        TokenAuth(token="gho_test123456789")
        TokenAuth(token="ghs_test123456789")

        # Classic token (no prefix) should also work
        TokenAuth(token="1234567890abcdef")

    def test_repr_hides_token(self):
        """Test __repr__ doesn't expose token."""
        auth = TokenAuth(token="ghp_secret123456789")
        repr_str = repr(auth)

        assert "ghp_secret123456789" not in repr_str
        assert "***" in repr_str

    def test_del_clears_token(self):
        """Test __del__ clears token from memory."""
        auth = TokenAuth(token="ghp_test123456789")
        assert hasattr(auth, "_token")

        auth.__del__()
        # Token should be None after cleanup
        assert auth._token is None

    def test_token_never_logged(self):
        """Test that token is never exposed in string representation."""
        token = "ghp_secret_token_12345"
        auth = TokenAuth(token=token)

        # Check repr
        assert token not in repr(auth)

        # Check str
        assert token not in str(auth)


class TestCreateAuth:
    """Tests for create_auth factory function."""

    def test_create_gh_cli_auth(self):
        """Test creating gh CLI auth."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            auth = create_auth(auth_method="gh_cli")

            assert isinstance(auth, GhCliAuth)

    def test_create_token_auth(self):
        """Test creating token auth."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test123456789"}):
            auth = create_auth(auth_method="token")

            assert isinstance(auth, TokenAuth)

    def test_create_token_auth_custom_env(self):
        """Test creating token auth with custom env var."""
        with patch.dict(os.environ, {"MY_TOKEN": "ghp_test123456789"}):
            auth = create_auth(auth_method="token", token_env="MY_TOKEN")

            assert isinstance(auth, TokenAuth)

    def test_create_invalid_method(self):
        """Test creating auth with invalid method."""
        with pytest.raises(GitHubAuthError, match="Unknown auth method"):
            create_auth(auth_method="invalid")

    def test_create_gh_cli_not_installed(self):
        """Test creating gh CLI auth when not installed."""
        with patch("ralph_gold.github_auth.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with pytest.raises(GitHubAuthError, match="gh CLI is not installed"):
                create_auth(auth_method="gh_cli")

    def test_create_token_auth_no_token(self):
        """Test creating token auth when no token available."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(GitHubAuthError, match="token not found"):
                create_auth(auth_method="token")
