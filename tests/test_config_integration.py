"""Integration test for config loading with GitHub tracker."""

from pathlib import Path
from tempfile import TemporaryDirectory

from ralph_gold.config import load_config


def test_config_backward_compatibility():
    """Test that config loading is backward compatible (no GitHub section)."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        # Create a minimal config without GitHub settings
        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[loop]
max_iterations = 5

[tracker]
kind = "json"
""")

        # Load config - should not fail
        config = load_config(project_root)

        # Verify basic config loaded
        assert config.loop.max_iterations == 5
        assert config.tracker.kind == "json"

        # Verify GitHub config has defaults even though not specified
        assert config.tracker.github is not None
        assert config.tracker.github.repo == ""
        assert config.tracker.github.auth_method == "gh_cli"


def test_config_with_github_tracker():
    """Test full config with GitHub tracker."""
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ralph_dir = project_root / ".ralph"
        ralph_dir.mkdir()

        # Create a full config with GitHub settings
        config_file = ralph_dir / "ralph.toml"
        config_file.write_text("""
[loop]
max_iterations = 10

[tracker]
kind = "github_issues"

[tracker.github]
repo = "test-org/test-repo"
auth_method = "token"
token_env = "TEST_TOKEN"
label_filter = "ready-for-dev"
exclude_labels = ["blocked", "wontfix"]
close_on_done = true
comment_on_done = true
add_labels_on_start = ["in-progress", "automated"]
add_labels_on_done = ["completed", "verified"]
cache_ttl_seconds = 600

[gates]
commands = ["pytest"]
""")

        # Load config
        config = load_config(project_root)

        # Verify all sections loaded correctly
        assert config.loop.max_iterations == 10
        assert config.tracker.kind == "github_issues"
        assert config.gates.commands == ["pytest"]

        # Verify GitHub config
        gh = config.tracker.github
        assert gh.repo == "test-org/test-repo"
        assert gh.auth_method == "token"
        assert gh.token_env == "TEST_TOKEN"
        assert gh.label_filter == "ready-for-dev"
        assert gh.exclude_labels == ["blocked", "wontfix"]
        assert gh.close_on_done is True
        assert gh.comment_on_done is True
        assert gh.add_labels_on_start == ["in-progress", "automated"]
        assert gh.add_labels_on_done == ["completed", "verified"]
        assert gh.cache_ttl_seconds == 600
