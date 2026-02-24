"""Watch mode for automatic gate execution on file changes."""

from __future__ import annotations

import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Set

from .config import Config, WatchConfig
from .loop import run_gates


@dataclass
class WatchState:
    """State for watch mode execution."""

    last_run_time: float
    pending_changes: Set[Path]
    running: bool


def _matches_pattern(file_path: Path, patterns: List[str]) -> bool:
    """Check if file path matches any of the watch patterns.

    Args:
        file_path: Path to check
        patterns: List of glob patterns (e.g., ["**/*.py", "**/*.md"])

    Returns:
        True if file matches any pattern, False otherwise
    """
    for pattern in patterns:
        if file_path.match(pattern):
            return True
    return False


def _should_ignore_path(file_path: Path, project_root: Path) -> bool:
    """Check if path should be ignored (e.g., .ralph/, .git/, __pycache__).

    Args:
        file_path: Path to check
        project_root: Project root directory

    Returns:
        True if path should be ignored, False otherwise
    """
    # Get relative path
    try:
        rel_path = file_path.relative_to(project_root)
    except ValueError:
        # Path is outside project root
        return True

    # Ignore common directories
    ignore_dirs = {".ralph", ".git", "__pycache__", "node_modules", ".venv", "venv"}

    for part in rel_path.parts:
        if part in ignore_dirs or part.startswith("."):
            return True

    return False


def _poll_for_changes(
    project_root: Path, patterns: List[str], last_check: float
) -> Set[Path]:
    """Poll filesystem for changes since last check.

    This is a simple polling implementation that checks file modification times.
    For production use, consider using watchdog library for OS-native file watching.

    Args:
        project_root: Project root directory
        patterns: List of glob patterns to watch
        last_check: Timestamp of last check

    Returns:
        Set of changed file paths
    """
    changed_files: Set[Path] = set()

    # Walk matching files for each configured glob pattern.
    # Use Path.glob(pattern) directly so patterns like "**/*.py" are handled
    # correctly. Stripping the pattern prefix (e.g., "**/") can break matching.
    for pattern in patterns:
        for file_path in project_root.glob(pattern):
            if not file_path.is_file():
                continue

            # Skip ignored paths
            if _should_ignore_path(file_path, project_root):
                continue

            # Check modification time
            try:
                mtime = file_path.stat().st_mtime
                if mtime >= last_check:
                    changed_files.add(file_path)
            except OSError:
                # File might have been deleted or is inaccessible
                pass

    return changed_files


def _try_import_watchdog() -> Optional[object]:
    """Try to import watchdog library.

    Returns:
        watchdog module if available, None otherwise
    """
    try:
        import watchdog  # type: ignore

        return watchdog
    except ImportError:
        return None


def watch_files(
    project_root: Path,
    cfg: Config,
    watch_cfg: WatchConfig,
    callback: Callable[[Path], None],
) -> None:
    """Watch files and trigger callback on changes.

    This function uses OS-native file watching if watchdog is available,
    otherwise falls back to polling.

    Args:
        project_root: Project root directory
        cfg: Full configuration
        watch_cfg: Watch-specific configuration
        callback: Function to call when files change (receives changed file path)
    """
    watchdog = _try_import_watchdog()

    if watchdog:
        # Use watchdog for efficient OS-native file watching
        _watch_with_watchdog(project_root, watch_cfg, callback)
    else:
        # Fall back to polling
        _watch_with_polling(project_root, watch_cfg, callback)


def _watch_with_polling(
    project_root: Path,
    watch_cfg: WatchConfig,
    callback: Callable[[Path], None],
) -> None:
    """Watch files using polling (fallback method).

    Args:
        project_root: Project root directory
        watch_cfg: Watch configuration
        callback: Function to call when files change
    """
    state = WatchState(last_run_time=time.time(), pending_changes=set(), running=True)

    # Poll interval in seconds (1 second)
    poll_interval = 1.0
    last_check = time.time()

    print(
        f"Watch mode started (polling). Watching patterns: {', '.join(watch_cfg.patterns)}"
    )
    print("Press Ctrl+C to stop.")

    try:
        while state.running:
            # Poll for changes
            changed_files = _poll_for_changes(
                project_root, watch_cfg.patterns, last_check
            )
            last_check = time.time()

            if changed_files:
                # Add to pending changes
                state.pending_changes.update(changed_files)

                # Check if debounce period has elapsed
                time_since_last_run = time.time() - state.last_run_time
                debounce_seconds = watch_cfg.debounce_ms / 1000.0

                if time_since_last_run >= debounce_seconds:
                    # Trigger callback for each changed file
                    for file_path in state.pending_changes:
                        callback(file_path)

                    # Reset state
                    state.pending_changes.clear()
                    state.last_run_time = time.time()

            # Sleep before next poll
            time.sleep(poll_interval)

    except KeyboardInterrupt:
        print("\nWatch mode stopped.")
        state.running = False


def _watch_with_watchdog(
    project_root: Path,
    watch_cfg: WatchConfig,
    callback: Callable[[Path], None],
) -> None:
    """Watch files using watchdog library (OS-native).

    Args:
        project_root: Project root directory
        watch_cfg: Watch configuration
        callback: Function to call when files change
    """
    try:
        from watchdog.events import FileSystemEvent, FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        # Should not happen since we checked for watchdog availability
        _watch_with_polling(project_root, watch_cfg, callback)
        return

    state = WatchState(last_run_time=time.time(), pending_changes=set(), running=True)

    class ChangeHandler(FileSystemEventHandler):
        """Handle file system events."""

        def on_modified(self, event: FileSystemEvent) -> None:
            """Handle file modification event."""
            if event.is_directory:
                return

            file_path = Path(event.src_path)

            # Check if file should be ignored
            if _should_ignore_path(file_path, project_root):
                return

            # Check if file matches patterns
            if not _matches_pattern(file_path, watch_cfg.patterns):
                return

            # Add to pending changes
            state.pending_changes.add(file_path)

        def on_created(self, event: FileSystemEvent) -> None:
            """Handle file creation event."""
            self.on_modified(event)

    handler = ChangeHandler()
    observer = Observer()
    observer.schedule(handler, str(project_root), recursive=True)
    observer.start()

    print(
        f"Watch mode started (watchdog). Watching patterns: {', '.join(watch_cfg.patterns)}"
    )
    print("Press Ctrl+C to stop.")

    try:
        while state.running:
            # Check if debounce period has elapsed and we have pending changes
            if state.pending_changes:
                time_since_last_run = time.time() - state.last_run_time
                debounce_seconds = watch_cfg.debounce_ms / 1000.0

                if time_since_last_run >= debounce_seconds:
                    # Trigger callback for each changed file
                    for file_path in state.pending_changes:
                        callback(file_path)

                    # Reset state
                    state.pending_changes.clear()
                    state.last_run_time = time.time()

            # Sleep briefly to avoid busy-waiting
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nWatch mode stopped.")
        state.running = False
    finally:
        observer.stop()
        observer.join()


def run_watch_mode(
    project_root: Path,
    cfg: Config,
    gates_only: bool = True,
    auto_commit: bool = False,
) -> None:
    """Run watch mode with gate execution.

    This function watches configured file patterns and automatically runs gates
    when files change. Optionally auto-commits when gates pass.

    Args:
        project_root: Project root directory
        cfg: Full configuration
        gates_only: If True, only run gates (don't run full loop)
        auto_commit: If True, auto-commit when gates pass

    Raises:
        RuntimeError: If watch mode is not enabled in configuration
    """
    if not cfg.watch.enabled:
        raise RuntimeError(
            "Watch mode is not enabled. Set watch.enabled = true in ralph.toml"
        )

    # Setup signal handler for graceful shutdown
    def signal_handler(sig: int, frame: object) -> None:
        """Handle Ctrl+C gracefully."""
        print("\nShutting down watch mode...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Track last gate run result
    last_gates_ok = False

    def on_file_change(file_path: Path) -> None:
        """Callback when files change."""
        nonlocal last_gates_ok

        print(f"\n{'=' * 60}")
        print(f"File changed: {file_path.relative_to(project_root)}")
        print(f"{'=' * 60}")

        if gates_only:
            # Run gates only
            print("Running gates...")
            gates_ok, gate_results = run_gates(
                project_root, cfg.gates.commands, cfg.gates
            )

            # Display results
            if gates_ok:
                print("✓ All gates passed")
                last_gates_ok = True

                # Auto-commit if enabled
                if auto_commit:
                    _auto_commit(project_root, file_path)
            else:
                print("✗ Gates failed")
                last_gates_ok = False

                # Show failed gates
                for result in gate_results:
                    if result.return_code != 0:
                        print(f"  Failed: {result.cmd}")
                        if result.stderr:
                            print(f"  Error: {result.stderr[:200]}")
        else:
            # Full loop execution would go here (future enhancement)
            print("Full loop execution not yet implemented in watch mode")

    # Start watching
    watch_files(project_root, cfg, cfg.watch, on_file_change)


def _auto_commit(project_root: Path, changed_file: Path) -> None:
    """Auto-commit changes when gates pass.

    Args:
        project_root: Project root directory
        changed_file: File that triggered the change
    """
    try:
        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )

        if not result.stdout.strip():
            print("No changes to commit")
            return

        # Stage all changes
        subprocess.run(
            ["git", "add", "-A"],
            cwd=project_root,
            capture_output=True,
            check=True,
        )

        # Commit with descriptive message
        rel_path = changed_file.relative_to(project_root)
        commit_message = f"ralph watch: auto-commit after {rel_path}"

        subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )

        print(f"✓ Auto-committed changes: {commit_message}")

    except subprocess.CalledProcessError as e:
        print(f"✗ Auto-commit failed: {e.stderr if e.stderr else str(e)}")
