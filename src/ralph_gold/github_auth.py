"""GitHub authentication layer for ralph-gold.

Supports two authentication methods:
1. gh CLI (preferred) - uses system keychain, more secure
2. Token-based - reads from environment variable

Security measures:
- Tokens never logged or printed
- __repr__ hides sensitive data
- Tokens cleared on cleanup
"""

from __future__ import annotations

import json
import os
import subprocess
from abc import ABC, abstractmethod
from typing import Any, Optional


class GitHubAuthError(Exception):
    """Base exception for GitHub authentication errors."""

    pass


class GitHubAuth(ABC):
    """Base protocol for GitHub authentication.

    All authentication methods must implement this interface.
    """

    @abstractmethod
    def api_call(
        self, method: str, endpoint: str, data: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Make an authenticated API call to GitHub.

        Args:
            method: HTTP method (GET, POST, PATCH, etc.)
            endpoint: API endpoint (e.g., "/repos/owner/repo/issues")
            data: Optional request body for POST/PATCH requests

        Returns:
            Response data as dict

        Raises:
            GitHubAuthError: If authentication fails or API call fails
        """
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate that authentication is working.

        Returns:
            True if authentication is valid, False otherwise
        """
        pass


class GhCliAuth(GitHubAuth):
    """GitHub authentication using gh CLI.

    This is the preferred method as it uses the system keychain
    and doesn't require managing tokens manually.
    """

    def __init__(self) -> None:
        """Initialize gh CLI authentication.

        Raises:
            GitHubAuthError: If gh CLI is not installed
        """
        if not self._is_gh_installed():
            raise GitHubAuthError(
                "gh CLI is not installed. Install it from https://cli.github.com/ "
                "or use token-based authentication instead."
            )

    def _is_gh_installed(self) -> bool:
        """Check if gh CLI is installed."""
        try:
            subprocess.run(
                ["gh", "--version"], capture_output=True, check=True, timeout=5
            )
            return True
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            return False

    def validate(self) -> bool:
        """Validate that gh CLI is authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        try:
            # Try to get the authenticated user
            result = subprocess.run(
                ["gh", "api", "/user"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )

            # If we got a response, we're authenticated
            data = json.loads(result.stdout)
            return "login" in data

        except (
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            subprocess.TimeoutExpired,
        ):
            return False

    def api_call(
        self, method: str, endpoint: str, data: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Make an authenticated API call using gh CLI.

        Args:
            method: HTTP method (GET, POST, PATCH, etc.)
            endpoint: API endpoint (e.g., "/repos/owner/repo/issues")
            data: Optional request body for POST/PATCH requests

        Returns:
            Response data as dict

        Raises:
            GitHubAuthError: If API call fails
        """
        # Build gh api command
        cmd = ["gh", "api", endpoint, "-X", method]

        # Add request body if provided
        stdin_data = None
        if data is not None:
            stdin_data = json.dumps(data)
            cmd.extend(["--input", "-"])

        try:
            result = subprocess.run(
                cmd,
                input=stdin_data,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )

            # Parse response
            if result.stdout.strip():
                return json.loads(result.stdout)
            return {}

        except subprocess.TimeoutExpired:
            raise GitHubAuthError(f"GitHub API call timed out: {method} {endpoint}")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else "Unknown error"

            # Check for common errors
            if (
                "authentication" in error_msg.lower()
                or "unauthorized" in error_msg.lower()
            ):
                raise GitHubAuthError(
                    "GitHub authentication failed. Run 'gh auth login' to authenticate."
                )
            elif "not found" in error_msg.lower():
                raise GitHubAuthError(f"GitHub API endpoint not found: {endpoint}")
            elif "rate limit" in error_msg.lower():
                raise GitHubAuthError(
                    "GitHub API rate limit exceeded. Try again later."
                )
            else:
                raise GitHubAuthError(f"GitHub API call failed: {error_msg}")
        except json.JSONDecodeError as e:
            raise GitHubAuthError(f"Failed to parse GitHub API response: {e}")

    def __repr__(self) -> str:
        """Safe representation that doesn't expose credentials."""
        return "GhCliAuth()"


class TokenAuth(GitHubAuth):
    """GitHub authentication using personal access token.

    Reads token from environment variable (default: GITHUB_TOKEN).
    Uses requests library for API calls.

    Security measures:
    - Token never logged or printed
    - __repr__ hides token
    - Token cleared on cleanup
    """

    def __init__(
        self, token: Optional[str] = None, token_env: str = "GITHUB_TOKEN"
    ) -> None:
        """Initialize token-based authentication.

        Args:
            token: GitHub personal access token (if None, reads from env)
            token_env: Environment variable name to read token from

        Raises:
            GitHubAuthError: If token is not provided and not in environment
        """
        self._token = token or os.getenv(token_env)

        if not self._token:
            raise GitHubAuthError(
                f"GitHub token not found. Set {token_env} environment variable "
                "or pass token directly. Get a token from https://github.com/settings/tokens"
            )

        # Validate token format (should start with ghp_, gho_, or ghs_)
        if not (
            self._token.startswith("ghp_")
            or self._token.startswith("gho_")
            or self._token.startswith("ghs_")
        ):
            # Could be a classic token (no prefix), which is still valid
            pass

    def validate(self) -> bool:
        """Validate that the token is valid.

        Returns:
            True if token is valid, False otherwise
        """
        try:
            # Try to get the authenticated user
            self.api_call("GET", "/user")
            return True
        except GitHubAuthError:
            return False

    def api_call(
        self, method: str, endpoint: str, data: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Make an authenticated API call using token.

        Args:
            method: HTTP method (GET, POST, PATCH, etc.)
            endpoint: API endpoint (e.g., "/repos/owner/repo/issues")
            data: Optional request body for POST/PATCH requests

        Returns:
            Response data as dict

        Raises:
            GitHubAuthError: If API call fails
        """
        try:
            import requests
        except ImportError:
            raise GitHubAuthError(
                "requests library not installed. Install it with: uv add requests"
            )

        # Build full URL
        base_url = "https://api.github.com"
        url = f"{base_url}{endpoint}"

        # Build headers
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ralph-gold/0.7.0",
        }

        try:
            # Make request
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == "PATCH":
                response = requests.patch(url, headers=headers, json=data, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise GitHubAuthError(f"Unsupported HTTP method: {method}")

            # Check for errors
            if response.status_code == 401:
                raise GitHubAuthError(
                    "GitHub authentication failed. Check your token and try again."
                )
            elif response.status_code == 403:
                # Check if it's a rate limit error
                if "rate limit" in response.text.lower():
                    raise GitHubAuthError(
                        "GitHub API rate limit exceeded. Try again later."
                    )
                else:
                    raise GitHubAuthError(
                        "GitHub API access forbidden. Check your token permissions."
                    )
            elif response.status_code == 404:
                raise GitHubAuthError(f"GitHub API endpoint not found: {endpoint}")
            elif response.status_code >= 400:
                raise GitHubAuthError(
                    f"GitHub API call failed with status {response.status_code}: {response.text}"
                )

            # Parse response
            if response.text.strip():
                return response.json()
            return {}

        except requests.exceptions.Timeout:
            raise GitHubAuthError(f"GitHub API call timed out: {method} {endpoint}")
        except requests.exceptions.RequestException as e:
            raise GitHubAuthError(f"GitHub API call failed: {e}")
        except json.JSONDecodeError as e:
            raise GitHubAuthError(f"Failed to parse GitHub API response: {e}")

    def __del__(self) -> None:
        """Clear token on cleanup."""
        if hasattr(self, "_token"):
            self._token = None

    def __repr__(self) -> str:
        """Safe representation that doesn't expose token."""
        return "TokenAuth(***)"


def create_auth(
    auth_method: str = "gh_cli", token_env: str = "GITHUB_TOKEN"
) -> GitHubAuth:
    """Factory function to create appropriate auth instance.

    Args:
        auth_method: Authentication method ("gh_cli" or "token")
        token_env: Environment variable name for token auth

    Returns:
        GitHubAuth instance

    Raises:
        GitHubAuthError: If authentication setup fails
    """
    if auth_method == "gh_cli":
        return GhCliAuth()
    elif auth_method == "token":
        return TokenAuth(token_env=token_env)
    else:
        raise GitHubAuthError(
            f"Unknown auth method: {auth_method}. Use 'gh_cli' or 'token'."
        )
