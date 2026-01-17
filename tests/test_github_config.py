"""Tests for GitHub tracker configuration parsing."""

from pathlib import Path
from tempfile import TemporaryDirectory

from ralph_gold.config import GitHubTrackerConfig, load_config


def test_github_config_defaults():
    """Test that GitHubTrackerConfig has sensible defaults."""
    config = GitHubTrackerConfig()

    assert config.repo == ""
    assert config.auth_method == "gh_cli"
    assert config.token_env == "GITHUB_TOKEN"
    assert config.label_filter == "ready"
    assert config.exclude_labels == ["blocked"]
    assert config.close_on_done is True
    assert config.comment_on_done is True
    assert config.add_labels_on_start == ["in-progress"]
    assert config.add_labels_on_done == ["completed"]
    assert config.cache_ttl_seconds == 300


def test_github_config_from_toml():
    """Test loading GitHub config from TOML file."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        # Create a config file with GitHub settings
        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[tracker]
kind = "github_issues"

[tracker.github]
repo = "owner/repo"
auth_method = "token"
token_env = "MY_GITHUB_TOKEN"
label_filter = "todo"
exclude_labels = ["wontfix", "duplicate"]
close_on_done = false
comment_on_done = false
add_labels_on_start = ["working"]
add_labels_on_done = ["done", "verified"]
cache_ttl_seconds = 600
""")

        # Load config
        config = load_config(project_root)

        # Verify tracker config
        assert config.tracker.kind == "github_issues"

        # Verify GitHub config
        gh = config.tracker.github
        assert gh.repo == "owner/repo"
        assert gh.auth_method == "token"
        assert gh.token_env == "MY_GITHUB_TOKEN"
        assert gh.label_filter == "todo"
        assert gh.exclude_labels == ["wontfix", "duplicate"]
        assert gh.close_on_done is False
        assert gh.comment_on_done is False
        assert gh.add_labels_on_start == ["working"]
        assert gh.add_labels_on_done == ["done", "verified"]
        assert gh.cache_ttl_seconds == 600


def test_github_config_partial_toml():
    """Test loading GitHub config with only some fields specified."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        # Create a config file with minimal GitHub settings
        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[tracker]
kind = "github_issues"

[tracker.github]
repo = "myorg/myrepo"
""")

        # Load config
        config = load_config(project_root)

        # Verify GitHub config uses defaults for unspecified fields
        gh = config.tracker.github
        assert gh.repo == "myorg/myrepo"
        assert gh.auth_method == "gh_cli"  # default
        assert gh.token_env == "GITHUB_TOKEN"  # default
        assert gh.label_filter == "ready"  # default
        assert gh.exclude_labels == ["blocked"]  # default
        assert gh.close_on_done is True  # default
        assert gh.comment_on_done is True  # default
        assert gh.add_labels_on_start == ["in-progress"]  # default
        assert gh.add_labels_on_done == ["completed"]  # default
        assert gh.cache_ttl_seconds == 300  # default


def test_github_config_no_tracker_section():
    """Test that config loads with defaults when no tracker section exists."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        # Create a config file without tracker section
        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[loop]
max_iterations = 5
""")

        # Load config
        config = load_config(project_root)

        # Verify GitHub config has defaults
        gh = config.tracker.github
        assert gh.repo == ""
        assert gh.auth_method == "gh_cli"
        assert gh.exclude_labels == ["blocked"]


def test_github_config_empty_lists():
    """Test that empty lists are handled correctly."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        # Create a config file with empty lists
        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[tracker.github]
repo = "owner/repo"
exclude_labels = []
add_labels_on_start = []
add_labels_on_done = []
""")

        # Load config
        config = load_config(project_root)

        # Verify empty lists are preserved
        gh = config.tracker.github
        assert gh.exclude_labels == []
        assert gh.add_labels_on_start == []
        assert gh.add_labels_on_done == []
