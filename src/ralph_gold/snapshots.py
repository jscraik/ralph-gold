"""Snapshot and rollback functionality using git stash."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class Snapshot:
    """A snapshot of project state."""

    name: str
    timestamp: str
    git_stash_ref: str
    state_backup_path: str
    description: str
    git_commit: str


def _validate_snapshot_name(name: str) -> None:
    """Validate snapshot name format.

    Args:
        name: The snapshot name to validate

    Raises:
        ValueError: If name is invalid
    """
    if not name:
        raise ValueError("Snapshot name cannot be empty")
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise ValueError(
            f"Invalid snapshot name '{name}'. "
            "Use only letters, numbers, hyphens, and underscores."
        )


def _get_git_commit_hash(project_root: Path) -> str:
    """Get current git commit hash.

    Args:
        project_root: Root directory of the project

    Returns:
        Current commit hash

    Raises:
        RuntimeError: If not in a git repository
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get git commit hash: {e.stderr}")


def _is_git_repo(project_root: Path) -> bool:
    """Check if project is a git repository.

    Args:
        project_root: Root directory of the project

    Returns:
        True if git repository, False otherwise
    """
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=project_root,
            capture_output=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _is_working_tree_dirty(project_root: Path) -> bool:
    """Check if working tree has uncommitted changes.

    Args:
        project_root: Root directory of the project

    Returns:
        True if working tree is dirty, False otherwise
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        return False


def create_snapshot(project_root: Path, name: str, description: str = "") -> Snapshot:
    """Create a snapshot using git stash.

    Args:
        project_root: Root directory of the project
        name: Name for the snapshot
        description: Optional description

    Returns:
        Created Snapshot object

    Raises:
        ValueError: If snapshot name is invalid
        RuntimeError: If not in a git repository or snapshot creation fails
    """
    _validate_snapshot_name(name)

    if not _is_git_repo(project_root):
        raise RuntimeError(
            "Project is not a git repository. "
            "Run 'git init' to initialize a repository."
        )

    # Get current commit hash
    git_commit = _get_git_commit_hash(project_root)

    # Create timestamp
    timestamp = datetime.now(timezone.utc).isoformat()

    # Create git stash with descriptive message
    stash_message = f"ralph-snapshot: {name}"
    if description:
        stash_message += f" - {description}"

    try:
        # Create stash (includes untracked files, but exclude .ralph/ directory)
        # We exclude .ralph/ because we manage state and snapshots separately
        subprocess.run(
            [
                "git",
                "stash",
                "push",
                "-u",
                "-m",
                stash_message,
                "--",
                ".",
                ":!.ralph/",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )

        # Get the stash reference (should be stash@{0} after creation)
        result = subprocess.run(
            ["git", "stash", "list"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )

        # Find the stash we just created
        stash_ref = None
        for line in result.stdout.splitlines():
            if stash_message in line:
                # Extract stash@{N} from line like "stash@{0}: On branch: message"
                match = re.match(r"(stash@\{\d+\})", line)
                if match:
                    stash_ref = match.group(1)
                    break

        if not stash_ref:
            raise RuntimeError("Failed to find created stash reference")

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create git stash: {e.stderr}")

    # Backup state.json
    state_path = project_root / ".ralph" / "state.json"
    snapshots_dir = project_root / ".ralph" / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    state_backup_path = snapshots_dir / f"{name}_state.json"

    if state_path.exists():
        try:
            state_backup_path.write_text(
                state_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to backup state.json: {e}")
    else:
        # Create empty backup if state doesn't exist
        state_backup_path.write_text("{}", encoding="utf-8")

    # Create snapshot object
    snapshot = Snapshot(
        name=name,
        timestamp=timestamp,
        git_stash_ref=stash_ref,
        state_backup_path=str(state_backup_path.relative_to(project_root)),
        description=description,
        git_commit=git_commit,
    )

    # Save snapshot metadata to state.json
    if not _save_snapshot_metadata(project_root, snapshot):
        raise RuntimeError("Failed to save snapshot metadata")

    return snapshot


def list_snapshots(project_root: Path) -> List[Snapshot]:
    """List all available snapshots.

    Args:
        project_root: Root directory of the project

    Returns:
        List of Snapshot objects
    """
    state_path = project_root / ".ralph" / "state.json"
    if not state_path.exists():
        return []

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        snapshots_data = state.get("snapshots", [])

        snapshots = []
        for snap_data in snapshots_data:
            if isinstance(snap_data, dict):
                snapshots.append(
                    Snapshot(
                        name=snap_data.get("name", ""),
                        timestamp=snap_data.get("timestamp", ""),
                        git_stash_ref=snap_data.get("git_stash_ref", ""),
                        state_backup_path=snap_data.get("state_backup_path", ""),
                        description=snap_data.get("description", ""),
                        git_commit=snap_data.get("git_commit", ""),
                    )
                )

        return snapshots
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Failed to load snapshot: %s", e)
        return []


def rollback_snapshot(project_root: Path, name: str, force: bool = False) -> bool:
    """Rollback to a specific snapshot.

    Args:
        project_root: Root directory of the project
        name: Name of the snapshot to rollback to
        force: If True, allow rollback even with dirty working tree

    Returns:
        True if rollback successful, False otherwise

    Raises:
        ValueError: If snapshot not found
        RuntimeError: If working tree is dirty (and not force) or rollback fails
    """
    if not _is_git_repo(project_root):
        raise RuntimeError("Project is not a git repository")

    # Check for dirty working tree
    if not force and _is_working_tree_dirty(project_root):
        raise RuntimeError(
            "Working tree has uncommitted changes. "
            "Commit or stash changes before rollback, or use force=True."
        )

    # Find the snapshot
    snapshots = list_snapshots(project_root)
    snapshot = None
    for snap in snapshots:
        if snap.name == name:
            snapshot = snap
            break

    if not snapshot:
        raise ValueError(f"Snapshot '{name}' not found")

    # Apply the git stash
    try:
        subprocess.run(
            ["git", "stash", "apply", snapshot.git_stash_ref],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to apply git stash: {e.stderr}")

    # Restore state.json
    state_backup_path = project_root / snapshot.state_backup_path
    state_path = project_root / ".ralph" / "state.json"

    if state_backup_path.exists():
        try:
            state_path.write_text(
                state_backup_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to restore state.json: {e}")

    return True


def cleanup_old_snapshots(project_root: Path, keep_count: int = 10) -> int:
    """Remove old snapshots, keeping most recent N.

    Args:
        project_root: Root directory of the project
        keep_count: Number of recent snapshots to keep

    Returns:
        Number of snapshots removed
    """
    if keep_count < 1:
        raise ValueError("keep_count must be at least 1")

    snapshots = list_snapshots(project_root)
    if len(snapshots) <= keep_count:
        return 0

    # Sort by timestamp (newest first)
    snapshots.sort(key=lambda s: s.timestamp, reverse=True)

    # Keep the most recent keep_count snapshots
    snapshots_to_remove = snapshots[keep_count:]

    removed_count = 0
    for snapshot in snapshots_to_remove:
        try:
            # Remove git stash
            subprocess.run(
                ["git", "stash", "drop", snapshot.git_stash_ref],
                cwd=project_root,
                capture_output=True,
                check=True,
            )

            # Remove state backup
            state_backup_path = project_root / snapshot.state_backup_path
            if state_backup_path.exists():
                try:
                    state_backup_path.unlink()
                except OSError as e:
                    logger.debug("Failed to remove snapshot: %s", e)
                    # Continue to next snapshot

            # Remove from metadata
            _remove_snapshot_metadata(project_root, snapshot.name)

            removed_count += 1
        except (subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to remove snapshot %s: %s", snapshot.name, e)
            # Continue with next snapshot

    return removed_count


def _save_snapshot_metadata(project_root: Path, snapshot: Snapshot) -> bool:
    """Save snapshot metadata to state.json.

    Args:
        project_root: Root directory of the project
        snapshot: Snapshot to save
    """
    state_path = project_root / ".ralph" / "state.json"

    # Load existing state
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("Failed to load state: %s", e)
            state = {}
    else:
        state = {}

    # Ensure snapshots array exists
    if "snapshots" not in state:
        state["snapshots"] = []

    # Add snapshot metadata
    state["snapshots"].append(
        {
            "name": snapshot.name,
            "timestamp": snapshot.timestamp,
            "git_stash_ref": snapshot.git_stash_ref,
            "state_backup_path": snapshot.state_backup_path,
            "description": snapshot.description,
            "git_commit": snapshot.git_commit,
        }
    )

    # Save state
    try:
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    except OSError as e:
        logger.debug("Failed to update metadata: %s", e)
        return False
    
    return True


def _remove_snapshot_metadata(project_root: Path, name: str) -> None:
    """Remove snapshot metadata from state.json.

    Args:
        project_root: Root directory of the project
        name: Name of snapshot to remove
    """
    state_path = project_root / ".ralph" / "state.json"
    if not state_path.exists():
        return

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        snapshots = state.get("snapshots", [])

        # Filter out the snapshot
        state["snapshots"] = [s for s in snapshots if s.get("name") != name]

        # Save state
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    except OSError as e:
        logger.debug("Failed to update metadata: %s", e)
