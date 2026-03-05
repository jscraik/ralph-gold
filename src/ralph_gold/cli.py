from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from . import __version__
from .commands.maintenance import (
    cmd_blocked,
    cmd_clean,
    cmd_interventions,
    cmd_resume,
    cmd_retry_blocked,
    cmd_state_cleanup,
    cmd_sync,
    cmd_unblock,
)
from .commands.loop_runtime import (
    run_run_command,
    run_step_command,
    run_supervise_command,
)
from .commands.harness import (
    cmd_harness_ci,
    cmd_harness_collect,
    cmd_harness_doctor,
    cmd_harness_pin,
    cmd_harness_report,
    cmd_harness_run,
)
from .commands.monitoring import cmd_diagnose, cmd_stats, cmd_status
from .commands.planning import (
    cmd_plan,
    cmd_regen_plan,
    cmd_rollback,
    cmd_snapshot,
    cmd_specs_check,
    cmd_task_add,
    cmd_task_templates,
    cmd_watch,
)
from .commands.utilities import (
    cmd_bridge,
    cmd_completion,
    cmd_convert,
    cmd_serve,
    cmd_tui,
)
from .commands.ux import cmd_explain, cmd_quickstart
from .config import LOOP_MODE_NAMES, load_config
from .doctor import check_tools, setup_checks
from .json_response import build_json_response
from .logging_config import setup_logging
from .loop import (
    dry_run_loop,
    next_iteration_number,
    run_iteration,
    run_loop,
)
from .output import (
    OutputConfig,
    has_json_output_emitted,
    get_output_config,
    print_json_output,
    print_output,
    reset_json_output_emitted,
    set_output_config,
)
from .path_utils import validate_project_path
from .scaffold import init_project
from .trackers import make_tracker

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    return Path(os.getcwd()).resolve()


def _normalize_cli_mode(value: str | None) -> str | None:
    if value is None:
        return None
    mode = value.strip().lower()
    if not mode:
        raise ValueError(
            "Invalid --mode: ''. Must be one of: "
            f"{', '.join(LOOP_MODE_NAMES)}."
        )
    if mode not in LOOP_MODE_NAMES:
        raise ValueError(
            f"Invalid --mode: {value!r}. Must be one of: "
            f"{', '.join(LOOP_MODE_NAMES)}."
        )
    return mode


class _RalphArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.exit(2, f"Error: {message}\n")


# -------------------------
# init / doctor
# -------------------------


def cmd_init(args: argparse.Namespace) -> int:
    root = _project_root()
    format_type = getattr(args, "format", None)
    no_merge_config = getattr(args, "no_merge_config", False)
    merge_strategy = getattr(args, "merge_strategy", "user_wins")

    archived = init_project(
        root,
        force=bool(args.force),
        format_type=format_type,
        solo=bool(getattr(args, "solo", False)),
        merge_config=not no_merge_config,
        merge_strategy=merge_strategy,
        no_merge_config=no_merge_config,
    )

    print_output(f"Initialized Ralph files in: {root / '.ralph'}", level="quiet")

    if archived:
        print_output(
            f"\n✓ Archived {len(archived)} existing file(s) to .ralph/archive/",
            level="quiet",
        )
        for path in archived[:5]:  # Show first 5
            print_output(f"  - {path}", level="quiet")
        if len(archived) > 5:
            print_output(f"  ... and {len(archived) - 5} more", level="quiet")

    if format_type == "yaml":
        print_output("Created tasks.yaml template (YAML tracker)", level="quiet")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Route doctor subcommands."""
    root = _project_root()

    if args.setup_checks:
        return _doctor_setup_checks(root, args)
    if args.check_github:
        return _doctor_check_github(root, args)
    return _doctor_tools(root)


def _doctor_setup_checks(project_root: Path, args: argparse.Namespace) -> int:
    """Handle doctor --setup-checks mode.

    Auto-configure quality gates for the project based on detected type.
    """
    result = setup_checks(project_root, dry_run=args.dry_run)

    # JSON output for setup_checks mode
    if get_output_config().format == "json":
        payload = build_json_response(
            "doctor",
            mode="setup_checks",
            exit_code=0,
            result={
                "project_type": result["project_type"],
                "script_name": result["script_name"],
                "actions_taken": result["actions_taken"],
                "suggestions": result["suggestions"],
                "commands": result["commands"],
            },
        )
        print_json_output(payload)
        return 0

    # Text output
    print_output(f"Project type: {result['project_type']}", level="normal")
    print_output(f"Check script: {result['script_name']}", level="normal")
    print_output("\nSuggested gate commands:", level="normal")
    for cmd in result["commands"]:
        print_output(f"  - {cmd}", level="normal")

    if result["actions_taken"]:
        print_output("\n✓ Actions taken:", level="normal")
        for action in result["actions_taken"]:
            print_output(f"  - {action}", level="normal")

    if result["suggestions"]:
        print_output("\n→ Suggestions:", level="normal")
        for suggestion in result["suggestions"]:
            print_output(f"  - {suggestion}", level="normal")

    if args.dry_run:
        print_output("\n(Dry run - no changes made)", level="normal")

    return 0


def _doctor_check_github(project_root: Path, args: argparse.Namespace) -> int:
    """Handle doctor --check-github mode.

    Check GitHub authentication (gh CLI or token).
    """
    from .github_auth import GhCliAuth, GitHubAuthError, TokenAuth

    logger = logging.getLogger(__name__)

    # JSON output for check_github mode
    if get_output_config().format == "json":
        gh_cli_result = {"ok": False, "user": None, "error": None}
        token_result = {"ok": False, "user": None, "error": None}

        # Try gh CLI
        try:
            gh_auth = GhCliAuth()
            if gh_auth.validate():
                gh_cli_result["ok"] = True
                try:
                    user_data = gh_auth.api_call("GET", "/user")
                    gh_cli_result["user"] = user_data.get("login")
                except Exception as e:
                    logger.debug("Failed to get gh CLI user data: %s", e)
            else:
                gh_cli_result["error"] = "installed but not authenticated"
        except GitHubAuthError as e:
            gh_cli_result["error"] = str(e)

        # Try token auth
        try:
            token_auth = TokenAuth()
            if token_auth.validate():
                token_result["ok"] = True
                try:
                    user_data = token_auth.api_call("GET", "/user")
                    token_result["user"] = user_data.get("login")
                except Exception as e:
                    logger.debug("Failed to get token user data: %s", e)
            else:
                token_result["error"] = "invalid or expired"
        except GitHubAuthError as e:
            token_result["error"] = str(e)

        # Exit code 0 if either auth method is ok
        exit_code = 0 if (gh_cli_result["ok"] or token_result["ok"]) else 2

        payload = build_json_response(
            "doctor",
            mode="check_github",
            exit_code=exit_code,
            auth={"gh_cli": gh_cli_result, "token": token_result},
        )
        print_json_output(payload)
        return exit_code

    # Text output
    print_output("Checking GitHub authentication...\n", level="normal")

    # Try gh CLI first
    print_output("[1/2] Checking gh CLI authentication...", level="normal")
    try:
        gh_auth = GhCliAuth()
        if gh_auth.validate():
            print_output("[OK]   gh CLI: authenticated", level="normal")

            # Get user info to show who's authenticated
            try:
                user_data = gh_auth.api_call("GET", "/user")
                print_output(
                    f"       User: {user_data.get('login', 'unknown')}",
                    level="normal",
                )
            except Exception as e:
                logger.debug("Failed to get gh CLI user data: %s", e)

            return 0
        else:
            print_output(
                "[WARN] gh CLI: installed but not authenticated", level="normal"
            )
            print_output(
                "       Run 'gh auth login' to authenticate", level="normal"
            )
    except GitHubAuthError as e:
        print_output(f"[MISS] gh CLI: {e}", level="normal")

    # Try token auth
    print_output("\n[2/2] Checking token authentication...", level="normal")
    try:
        token_auth = TokenAuth()
        if token_auth.validate():
            print_output(
                "[OK]   Token: authenticated (GITHUB_TOKEN)", level="normal"
            )

            # Get user info to show who's authenticated
            try:
                user_data = token_auth.api_call("GET", "/user")
                print_output(
                    f"       User: {user_data.get('login', 'unknown')}",
                    level="normal",
                )
            except OSError as e:
                logger.debug("State load failed: %s", e)

            return 0
        else:
            print_output("[WARN] Token: invalid or expired", level="normal")
    except GitHubAuthError as e:
        print_output(f"[MISS] Token: {e}", level="normal")

    print_output("\n✗ No valid GitHub authentication found", level="error")
    print_output("\nTo authenticate:", level="normal")
    print_output("  Option 1 (recommended): gh auth login", level="normal")
    print_output(
        "  Option 2: Set GITHUB_TOKEN environment variable", level="normal"
    )
    print_output(
        "            Get a token from https://github.com/settings/tokens",
        level="normal",
    )

    return 2


def _doctor_tools(project_root: Path) -> int:
    """Handle default doctor mode - check available tools.

    Lists status of git, uv, codex, claude, copilot, gh, and configured tools.
    """
    cfg = load_config(project_root)
    statuses = check_tools(cfg)

    # JSON output for tools mode
    if get_output_config().format == "json":
        ok = all(st.found for st in statuses)
        exit_code = 0 if ok else 2
        statuses_payload = [
            {
                "name": st.name,
                "found": st.found,
                "version": st.version,
                "path": st.path,
                "hint": st.hint,
            }
            for st in statuses
        ]
        payload = build_json_response(
            "doctor",
            mode="tools",
            exit_code=exit_code,
            statuses=statuses_payload,
        )
        print_json_output(payload)
        return exit_code

    # Text output
    ok = True
    for st in statuses:
        if st.found:
            print_output(
                f"[OK]   {st.name}: {st.version or st.path or 'found'}", level="normal"
            )
        else:
            ok = False
            print_output(f"[MISS] {st.name}: {st.hint or 'not found'}", level="normal")
    return 0 if ok else 2





# -------------------------
# loop
# -------------------------


def cmd_step(args: argparse.Namespace) -> int:
    return run_step_command(
        args,
        project_root_fn=_project_root,
        load_config_fn=load_config,
        normalize_mode_fn=_normalize_cli_mode,
        validate_project_path_fn=validate_project_path,
        dry_run_loop_fn=dry_run_loop,
        make_tracker_fn=make_tracker,
        next_iteration_number_fn=next_iteration_number,
        run_iteration_fn=run_iteration,
        get_output_config_fn=get_output_config,
        print_json_output_fn=print_json_output,
        print_output_fn=print_output,
        logger=logger,
    )


def cmd_run(args: argparse.Namespace) -> int:
    return run_run_command(
        args,
        project_root_fn=_project_root,
        load_config_fn=load_config,
        normalize_mode_fn=_normalize_cli_mode,
        validate_project_path_fn=validate_project_path,
        run_loop_fn=run_loop,
        get_output_config_fn=get_output_config,
        print_json_output_fn=print_json_output,
        print_output_fn=print_output,
    )


def cmd_supervise(args: argparse.Namespace) -> int:
    return run_supervise_command(
        args,
        project_root_fn=_project_root,
        load_config_fn=load_config,
        normalize_mode_fn=_normalize_cli_mode,
        get_output_config_fn=get_output_config,
        print_output_fn=print_output,
    )


# -------------------------
# argparse
# -------------------------


def build_parser() -> argparse.ArgumentParser:
    p = _RalphArgumentParser(
        prog="ralph",
        description="ralph-gold: Golden Ralph Loop orchestrator (uv-first)",
        epilog=(
            "Simple workflow (default): ralph init -> ralph step --agent codex -> ralph status\n"
            "Expert workflow: use advanced subcommands and flags via `ralph <command> --help`."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"ralph-gold {__version__}")
    p.add_argument(
        "--format",
        dest="global_format",
        choices=["text", "json"],
        default=None,
        help="Global output format override (text|json)",
    )
    p.add_argument(
        "--verbosity",
        dest="global_verbosity",
        choices=["quiet", "normal", "verbose"],
        default=None,
        help="Global verbosity override (quiet|normal|verbose)",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Initialize Ralph files in the current repo")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing files")
    p_init.add_argument(
        "--solo",
        action="store_true",
        help="Use solo-dev optimized defaults for ralph.toml",
    )
    p_init.add_argument(
        "--format",
        choices=["markdown", "yaml"],
        default=None,
        help="Task tracker format (default: markdown)",
    )
    p_init.add_argument(
        "--no-merge-config",
        action="store_true",
        help="Disable config merging on --force (overwrite instead of merge)",
    )
    p_init.add_argument(
        "--merge-strategy",
        choices=["user_wins", "template_wins", "ask"],
        default="user_wins",
        help="Config merge strategy when using --force (default: user_wins)",
    )
    p_init.set_defaults(func=cmd_init)

    p_quickstart = sub.add_parser(
        "quickstart",
        help="Initialize Ralph with recommended defaults and next-step guidance",
        description="Initialize Ralph with recommended defaults and next-step guidance",
    )
    p_quickstart.add_argument(
        "--force",
        action="store_true",
        help="Archive existing .ralph files and reinitialize",
    )
    p_quickstart.add_argument(
        "--solo",
        action="store_true",
        help="Use solo-dev optimized defaults for ralph.toml",
    )
    p_quickstart.add_argument(
        "--format",
        choices=["markdown", "yaml"],
        default=None,
        help="Task tracker format (default: markdown)",
    )
    p_quickstart.add_argument(
        "--profile",
        choices=["simple", "expert"],
        default="simple",
        help="Quickstart posture preset (default: simple)",
    )
    p_quickstart.add_argument(
        "--agent",
        default="codex",
        help="Recommended agent for your next step command (default: codex)",
    )
    p_quickstart.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for profile and preferred agent",
    )
    p_quickstart.set_defaults(func=cmd_quickstart)

    p_doc = sub.add_parser(
        "doctor", help="Check local prerequisites (git, uv, agent CLIs)"
    )
    p_doc.add_argument(
        "--setup-checks",
        action="store_true",
        help="Auto-configure quality gates for your project",
    )
    p_doc.add_argument(
        "--dry-run", action="store_true", help="Preview changes without applying them"
    )
    p_doc.add_argument(
        "--check-github",
        action="store_true",
        help="Check GitHub authentication (gh CLI or token)",
    )
    p_doc.set_defaults(func=cmd_doctor)

    p_diagnose = sub.add_parser(
        "diagnose",
        help="Run diagnostic checks on configuration and PRD",
    )
    p_diagnose.add_argument(
        "--test-gates",
        action="store_true",
        help="Test each gate command individually",
    )
    p_diagnose.set_defaults(func=cmd_diagnose)

    p_stats = sub.add_parser(
        "stats",
        help="Display iteration statistics from Ralph history",
    )
    p_stats.add_argument(
        "--by-task",
        action="store_true",
        help="Show detailed per-task breakdown",
    )
    p_stats.add_argument(
        "--flow",
        action="store_true",
        help="Display velocity and blocked task rate metrics",
    )
    p_stats.add_argument(
        "--format",
        choices=["text", "json"],
        help="Output format (overrides config)",
    )
    p_stats.add_argument(
        "--export",
        metavar="FILE",
        default=None,
        help="Export statistics to CSV file",
    )
    p_stats.set_defaults(func=cmd_stats)

    # Harness commands
    p_harness = sub.add_parser(
        "harness",
        help="Collect/evaluate/report harness artifacts for regression tracking",
    )
    p_harness_sub = p_harness.add_subparsers(
        dest="harness_subcommand",
        title="harness subcommands",
        required=True,
    )

    p_harness_collect = p_harness_sub.add_parser(
        "collect",
        help="Collect harness cases from .ralph state and receipts",
    )
    p_harness_collect.add_argument(
        "--days",
        type=int,
        default=None,
        help="Only include cases from the last N days (default: from config)",
    )
    p_harness_collect.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of cases to include (default: from config)",
    )
    p_harness_collect.add_argument(
        "--output",
        default=None,
        help="Dataset output path (default: harness.dataset_path)",
    )
    p_harness_collect.add_argument(
        "--include-failures",
        action="store_true",
        default=True,
        help="Include failed cases (default: true)",
    )
    p_harness_collect.add_argument(
        "--exclude-failures",
        dest="include_failures",
        action="store_false",
        help="Exclude failed cases",
    )
    p_harness_collect.add_argument(
        "--redact",
        action="store_true",
        default=True,
        help="Redact long/sensitive fields where possible (default: true)",
    )
    p_harness_collect.add_argument(
        "--pinned-input",
        default=None,
        help="Pinned dataset path (default: harness.pinned_dataset_path)",
    )
    p_harness_collect.add_argument(
        "--append-pinned",
        dest="append_pinned",
        action="store_true",
        default=None,
        help="Append pinned cases to collected dataset (default: from config)",
    )
    p_harness_collect.add_argument(
        "--no-append-pinned",
        dest="append_pinned",
        action="store_false",
        help="Do not append pinned cases",
    )
    p_harness_collect.add_argument(
        "--max-cases-per-task",
        type=int,
        default=None,
        help="Cap collected cases per task_id (default: harness.max_cases_per_task)",
    )
    p_harness_collect.set_defaults(func=cmd_harness_collect)

    p_harness_run = p_harness_sub.add_parser(
        "run",
        help="Evaluate harness dataset and produce run metrics",
    )
    p_harness_run.add_argument(
        "--dataset",
        default=None,
        help="Input dataset path (default: harness.dataset_path)",
    )
    p_harness_run.add_argument(
        "--agent",
        default="codex",
        help="Agent label for run metadata (default: codex)",
    )
    p_harness_run.add_argument(
        "--mode",
        choices=LOOP_MODE_NAMES,
        default=None,
        help="Mode label for run metadata (default: loop.mode)",
    )
    p_harness_run.add_argument(
        "--isolation",
        choices=["worktree", "snapshot"],
        default=None,
        help="Replay isolation strategy label (default: harness.replay.default_isolation)",
    )
    p_harness_run.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Evaluate only the first N cases",
    )
    p_harness_run.add_argument(
        "--baseline",
        default=None,
        help="Baseline harness run JSON for regression comparison",
    )
    p_harness_run.add_argument(
        "--output",
        default=None,
        help="Run output path (default: harness.runs_dir/<timestamp>.json)",
    )
    p_harness_run.add_argument(
        "--enforce-regression-threshold",
        action="store_true",
        help="Exit non-zero when run is regressed vs baseline",
    )
    p_harness_run.add_argument(
        "--execution-mode",
        choices=["historical", "live"],
        default="historical",
        help="Evaluation mode: historical replay or live targeted execution (default: historical)",
    )
    p_harness_run.add_argument(
        "--bucket",
        choices=["all", "small", "medium", "large"],
        default="all",
        help="Only evaluate a bucket subset (default: all)",
    )
    p_harness_run.add_argument(
        "--report-breakdown",
        dest="report_breakdown",
        action="store_true",
        default=True,
        help="Include per-bucket breakdown in report output (default: true)",
    )
    p_harness_run.add_argument(
        "--no-report-breakdown",
        dest="report_breakdown",
        action="store_false",
        help="Disable per-bucket breakdown in report output",
    )
    p_harness_run.add_argument(
        "--strict-targeting",
        action="store_true",
        default=True,
        help="In live mode, fail targeted case when target is done/blocked/missing (default: true)",
    )
    p_harness_run.add_argument(
        "--allow-non-strict-targeting",
        dest="strict_targeting",
        action="store_false",
        help="In live mode, allow done/blocked target execution",
    )
    p_harness_run.add_argument(
        "--continue-on-target-error",
        action="store_true",
        default=True,
        help="In live mode, continue batch even if a case target fails (default: true)",
    )
    p_harness_run.add_argument(
        "--stop-on-target-error",
        dest="continue_on_target_error",
        action="store_false",
        help="In live mode, stop on first target resolution failure",
    )
    p_harness_run.set_defaults(func=cmd_harness_run)

    p_harness_pin = p_harness_sub.add_parser(
        "pin",
        help="Promote failing run cases into pinned harness dataset",
    )
    p_harness_pin.add_argument(
        "--run",
        required=True,
        help="Harness run JSON path to source failing cases from",
    )
    p_harness_pin.add_argument(
        "--dataset",
        default=None,
        help="Optional dataset path for enriching pinned cases",
    )
    p_harness_pin.add_argument(
        "--output",
        default=None,
        help="Pinned dataset output path (default: harness.pinned_dataset_path)",
    )
    p_harness_pin.add_argument(
        "--status",
        action="append",
        default=[],
        help="Filter by run status (repeatable)",
    )
    p_harness_pin.add_argument(
        "--failure-category",
        action="append",
        default=[],
        help="Filter by failure category (repeatable)",
    )
    p_harness_pin.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Pin at most N matching cases",
    )
    p_harness_pin.add_argument(
        "--redact",
        action="store_true",
        default=True,
        help="Redact long/sensitive fields where possible (default: true)",
    )
    p_harness_pin.set_defaults(func=cmd_harness_pin)

    p_harness_ci = p_harness_sub.add_parser(
        "ci",
        help="Run collect + evaluate in one CI-friendly command",
    )
    p_harness_ci.add_argument(
        "--days",
        type=int,
        default=None,
        help="Only include cases from last N days (default: harness.default_days)",
    )
    p_harness_ci.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of collected cases (default: harness.default_limit)",
    )
    p_harness_ci.add_argument(
        "--dataset",
        default=None,
        help="Dataset output path (default: harness.dataset_path)",
    )
    p_harness_ci.add_argument(
        "--output",
        default=None,
        help="Run output path (default: harness.runs_dir/ci-<timestamp>.json)",
    )
    p_harness_ci.add_argument(
        "--baseline",
        default=None,
        help="Baseline run path override (default: harness.baseline_run_path)",
    )
    p_harness_ci.add_argument(
        "--agent",
        default="codex",
        help="Agent label for run metadata (default: codex)",
    )
    p_harness_ci.add_argument(
        "--mode",
        choices=LOOP_MODE_NAMES,
        default=None,
        help="Mode label for run metadata (default: loop.mode)",
    )
    p_harness_ci.add_argument(
        "--isolation",
        choices=["worktree", "snapshot"],
        default=None,
        help="Replay isolation strategy label (default: harness.replay.default_isolation)",
    )
    p_harness_ci.add_argument(
        "--execution-mode",
        choices=["historical", "live"],
        default=None,
        help="Execution mode (default: harness.ci.execution_mode)",
    )
    p_harness_ci.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Max evaluated cases (default: harness.ci.max_cases)",
    )
    p_harness_ci.add_argument(
        "--bucket",
        choices=["all", "small", "medium", "large"],
        default="all",
        help="Only evaluate a bucket subset (default: all)",
    )
    p_harness_ci.add_argument(
        "--enforce-regression-threshold",
        dest="enforce_regression_threshold",
        action="store_true",
        default=None,
        help="Fail CI when run regresses versus baseline (default: harness.ci.enforce_regression_threshold)",
    )
    p_harness_ci.add_argument(
        "--no-enforce-regression-threshold",
        dest="enforce_regression_threshold",
        action="store_false",
        help="Do not fail CI on regression threshold breach",
    )
    p_harness_ci.add_argument(
        "--require-baseline",
        dest="require_baseline",
        action="store_true",
        default=None,
        help="Require baseline run availability (default: harness.ci.require_baseline)",
    )
    p_harness_ci.add_argument(
        "--allow-missing-baseline",
        dest="require_baseline",
        action="store_false",
        help="Allow CI run when baseline is missing",
    )
    p_harness_ci.add_argument(
        "--baseline-missing-policy",
        choices=["fail", "warn"],
        default=None,
        help="Policy when baseline missing and required (default: harness.ci.baseline_missing_policy)",
    )
    p_harness_ci.add_argument(
        "--include-failures",
        action="store_true",
        default=True,
        help="Include failed cases while collecting dataset (default: true)",
    )
    p_harness_ci.add_argument(
        "--exclude-failures",
        dest="include_failures",
        action="store_false",
        help="Exclude failed cases while collecting dataset",
    )
    p_harness_ci.add_argument(
        "--redact",
        action="store_true",
        default=True,
        help="Redact long/sensitive fields where possible (default: true)",
    )
    p_harness_ci.add_argument(
        "--pinned-input",
        default=None,
        help="Pinned dataset input path (default: harness.pinned_dataset_path)",
    )
    p_harness_ci.add_argument(
        "--append-pinned",
        dest="append_pinned",
        action="store_true",
        default=None,
        help="Append pinned cases to collected dataset (default: from config)",
    )
    p_harness_ci.add_argument(
        "--no-append-pinned",
        dest="append_pinned",
        action="store_false",
        help="Do not append pinned cases",
    )
    p_harness_ci.add_argument(
        "--max-cases-per-task",
        type=int,
        default=None,
        help="Cap collected cases per task_id (default: harness.max_cases_per_task)",
    )
    p_harness_ci.add_argument(
        "--strict-targeting",
        action="store_true",
        default=True,
        help="In live mode, fail targeted case when target is done/blocked/missing (default: true)",
    )
    p_harness_ci.add_argument(
        "--allow-non-strict-targeting",
        dest="strict_targeting",
        action="store_false",
        help="In live mode, allow done/blocked target execution",
    )
    p_harness_ci.add_argument(
        "--continue-on-target-error",
        action="store_true",
        default=True,
        help="In live mode, continue batch even if a case target fails (default: true)",
    )
    p_harness_ci.add_argument(
        "--stop-on-target-error",
        dest="continue_on_target_error",
        action="store_false",
        help="In live mode, stop on first target resolution failure",
    )
    p_harness_ci.set_defaults(func=cmd_harness_ci)

    p_harness_report = p_harness_sub.add_parser(
        "report",
        help="Render harness run report",
    )
    p_harness_report.add_argument(
        "--input",
        default=None,
        help="Harness run JSON path (default: latest run in harness.runs_dir)",
    )
    p_harness_report.add_argument(
        "--baseline",
        default=None,
        help="Optional baseline run JSON for comparison",
    )
    p_harness_report.add_argument(
        "--format",
        dest="report_format",
        choices=["text", "json", "csv"],
        default="text",
        help="Report output format (default: text)",
    )
    p_harness_report.set_defaults(func=cmd_harness_report)

    p_harness_doctor = p_harness_sub.add_parser(
        "doctor",
        help="Validate harness config and artifact schema integrity",
    )
    p_harness_doctor.add_argument(
        "--max-run-files",
        type=int,
        default=10,
        help="Maximum run files to validate in harness.runs_dir (default: 10)",
    )
    p_harness_doctor.set_defaults(func=cmd_harness_doctor)

    p_resume = sub.add_parser(
        "resume",
        help="Detect and resume interrupted iterations",
    )
    p_resume.add_argument(
        "--clear",
        action="store_true",
        help="Clear the interrupted iteration without resuming",
    )
    p_resume.add_argument(
        "--auto",
        action="store_true",
        help="Resume automatically without prompting",
    )
    p_resume.set_defaults(func=cmd_resume)

    p_clean = sub.add_parser(
        "clean",
        help="Clean old logs, archives, and other workspace artifacts",
    )
    p_clean.add_argument(
        "--logs-days",
        type=int,
        default=30,
        help="Remove logs older than N days (default: 30)",
    )
    p_clean.add_argument(
        "--archives-days",
        type=int,
        default=90,
        help="Remove archives older than N days (default: 90)",
    )
    p_clean.add_argument(
        "--receipts-days",
        type=int,
        default=60,
        help="Remove receipts older than N days (default: 60)",
    )
    p_clean.add_argument(
        "--context-days",
        type=int,
        default=60,
        help="Remove context files older than N days (default: 60)",
    )
    p_clean.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be deleted without actually deleting",
    )
    p_clean.set_defaults(func=cmd_clean)

    # State management subcommands
    p_state = sub.add_parser(
        "state",
        help="State management commands",
    )
    p_state_sub = p_state.add_subparsers(
        dest="state_subcommand",
        title="state subcommands",
        required=True,
    )

    p_cleanup = p_state_sub.add_parser(
        "cleanup",
        help="Remove stale task IDs from state.json",
    )
    p_cleanup.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be removed without actually removing",
    )
    p_cleanup.set_defaults(func=cmd_state_cleanup)

    p_step = sub.add_parser("step", help="Run exactly one iteration")
    p_step.add_argument(
        "--agent",
        default="codex",
        help="Runner to use (codex|claude|copilot or custom runner name)",
    )

    p_step_mode = p_step.add_mutually_exclusive_group()
    p_step_mode.add_argument(
        "--mode",
        choices=LOOP_MODE_NAMES,
        help="Override loop.mode (speed|quality|exploration)",
    )
    p_step_mode.add_argument(
        "--quick",
        action="store_true",
        help="Run exactly one iteration in speed mode (mode=speed, max_iterations=1)",
    )
    p_step_mode.add_argument(
        "--batch",
        action="store_true",
        help="Run multiple quick tasks in speed mode (mode=speed, batch_enabled=true)",
    )
    p_step_mode.add_argument(
        "--explore",
        action="store_true",
        help="Run in exploration mode with extended timeouts (mode=exploration, timeout=3600s)",
    )
    p_step_mode.add_argument(
        "--hotfix",
        action="store_true",
        help="Run in speed mode and skip all quality gates (mode=speed, skip_gates=true)",
    )

    p_step.add_argument(
        "--prompt-file",
        default=None,
        help="Override files.prompt for this run (e.g. PROMPT_plan.md)",
    )
    p_step.add_argument(
        "--prd-file",
        default=None,
        help="Override files.prd for this run (e.g. IMPLEMENTATION_PLAN.md)",
    )
    p_step.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without running agents (validate config and show execution plan)",
    )
    p_step.add_argument(
        "--interactive",
        action="store_true",
        help="Interactively select which task to work on from available tasks",
    )
    p_step.add_argument(
        "--task-id",
        "--task",
        default=None,
        help="Execute a specific task ID instead of auto-selecting next task",
    )
    p_step.add_argument(
        "--allow-done-target",
        action="store_true",
        help="Allow targeting a task currently marked done",
    )
    p_step.add_argument(
        "--allow-blocked-target",
        action="store_true",
        help="Allow targeting a task currently marked blocked",
    )
    p_step.add_argument(
        "--reopen-target",
        action="store_true",
        help="Attempt to reopen target task before running",
    )
    p_step.set_defaults(func=cmd_step)

    p_run = sub.add_parser(
        "run",
        help="Run the loop for N iterations (default from ralph.toml). Exit codes: 0=success, 1=incomplete, 2=failed.",
    )
    p_run.add_argument(
        "--agent",
        default="codex",
        help="Runner to use (codex|claude|copilot or custom)",
    )

    p_run_mode = p_run.add_mutually_exclusive_group()
    p_run_mode.add_argument(
        "--mode",
        choices=LOOP_MODE_NAMES,
        help="Override loop.mode (speed|quality|exploration)",
    )
    p_run_mode.add_argument(
        "--quick",
        action="store_true",
        help="Run exactly one iteration in speed mode (mode=speed, max_iterations=1)",
    )
    p_run_mode.add_argument(
        "--batch",
        action="store_true",
        help="Run multiple quick tasks in speed mode (mode=speed, batch_enabled=true)",
    )
    p_run_mode.add_argument(
        "--explore",
        action="store_true",
        help="Run in exploration mode with extended timeouts (mode=exploration, timeout=3600s)",
    )
    p_run_mode.add_argument(
        "--hotfix",
        action="store_true",
        help="Run in speed mode and skip all quality gates (mode=speed, skip_gates=true)",
    )

    p_run.add_argument(
        "--task-id",
        "--task",
        default=None,
        help="Execute a specific task ID instead of auto-selecting next task",
    )
    p_run.add_argument(
        "--max-iterations", type=int, default=None, help="Override loop.max_iterations"
    )
    p_run.add_argument(
        "--prompt-file", default=None, help="Override files.prompt for this run"
    )
    p_run.add_argument(
        "--prd-file", default=None, help="Override files.prd for this run"
    )
    p_run.add_argument(
        "--parallel",
        action="store_true",
        help="Enable parallel execution with git worktrees (overrides config)",
    )
    p_run.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Number of parallel workers (requires --parallel, overrides config)",
    )
    p_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without running agents (validate config and show execution plan)",
    )
    p_run.add_argument(
        "--stream",
        action="store_true",
        help="Stream runner output live instead of buffering it (sequential mode only)",
    )
    p_run.set_defaults(func=cmd_run)

    p_supervise = sub.add_parser(
        "supervise",
        help="Run a long-lived supervisor loop (heartbeat + policy stops + notifications).",
    )
    p_supervise.add_argument(
        "--agent",
        default="codex",
        help="Runner to use for execution iterations (default: codex)",
    )
    p_supervise.add_argument(
        "--mode",
        choices=LOOP_MODE_NAMES,
        help="Override loop.mode (speed|quality|exploration)",
    )
    p_supervise.add_argument(
        "--max-runtime-seconds",
        type=int,
        default=None,
        help="Stop after N seconds (0/unset = unlimited)",
    )
    p_supervise.add_argument(
        "--heartbeat-seconds",
        type=int,
        default=None,
        help="Print a heartbeat every N seconds (default: from supervisor config)",
    )
    p_supervise.add_argument(
        "--sleep-seconds-between-runs",
        type=int,
        default=None,
        help="Sleep N seconds between iterations (default: from supervisor config)",
    )
    p_supervise.add_argument(
        "--on-no-progress-limit",
        choices=["stop", "continue"],
        default=None,
        help="Policy when no-progress limit is reached (default: from supervisor config)",
    )
    p_supervise.add_argument(
        "--on-rate-limit",
        choices=["wait", "stop"],
        default=None,
        help="Policy when rate limit is reached (default: from supervisor config)",
    )

    notify_group = p_supervise.add_mutually_exclusive_group()
    notify_group.add_argument(
        "--notify",
        action="store_true",
        help="Enable OS notifications (default: enabled)",
    )
    notify_group.add_argument(
        "--no-notify",
        action="store_true",
        help="Disable OS notifications",
    )
    p_supervise.add_argument(
        "--notify-backend",
        choices=["auto", "macos", "linux", "windows", "command", "none"],
        default=None,
        help="Notification backend (default: from supervisor config)",
    )
    p_supervise.add_argument(
        "--notify-command",
        nargs="+",
        default=None,
        help="Command argv to invoke for notifications when backend=command (appends title + message)",
    )
    p_supervise.set_defaults(func=cmd_supervise)

    p_status = sub.add_parser(
        "status", help="Show PRD progress + last iteration summary"
    )
    p_status.add_argument(
        "--graph",
        action="store_true",
        help="Display task dependency graph visualization",
    )
    p_status.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed progress metrics including velocity and ETA",
    )
    p_status.add_argument(
        "--chart",
        action="store_true",
        help="Display ASCII burndown chart of task completion over time",
    )
    p_status.set_defaults(func=cmd_status)

    p_explain = sub.add_parser(
        "explain",
        help="Explain why the next task was selected, blocker context, and next actions",
    )
    p_explain.add_argument(
        "--agent",
        default="codex",
        help="Suggested agent in generated next-step commands (default: codex)",
    )
    p_explain.set_defaults(func=cmd_explain)

    # Blocked tasks management
    p_blocked = sub.add_parser("blocked", help="Show blocked tasks with suggestions")
    p_blocked.add_argument(
        "--suggest",
        action="store_true",
        help="Show unblock suggestions for each blocked task",
    )
    p_blocked.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )
    p_blocked.set_defaults(func=cmd_blocked)

    p_unblock = sub.add_parser("unblock", help="Unblock a task for retry")
    p_unblock.add_argument(
        "task_id",
        help="Task ID to unblock (e.g., 'task-22' or '22')",
    )
    p_unblock.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="New timeout for retry in seconds (default: suggested based on complexity)",
    )
    p_unblock.add_argument(
        "--reason",
        default="Manual unblock",
        help="Reason for unblocking (recorded in attempt history)",
    )
    p_unblock.set_defaults(func=cmd_unblock)

    p_retry_blocked = sub.add_parser(
        "retry-blocked",
        help="Retry all blocked tasks with increased timeouts"
    )
    p_retry_blocked.add_argument(
        "--filter",
        choices=["timeout", "no_files", "gate_failure", "ui_heavy", "all"],
        default="timeout",
        help="Only retry tasks with this block reason",
    )
    p_retry_blocked.add_argument(
        "--timeout-multiplier",
        type=float,
        default=1.0,
        help="Multiply suggested timeout by this factor (default: 1.0 = use suggested)",
    )
    p_retry_blocked.add_argument(
        "--max-attempts",
        type=int,
        default=1,
        help="Maximum number of retry attempts per task (default: 1)",
    )
    p_retry_blocked.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually unblocking",
    )
    p_retry_blocked.set_defaults(func=cmd_retry_blocked)

    # Sync command: reconcile state.json with PRD
    p_sync = sub.add_parser(
        "sync",
        help="Sync state.json with PRD to remove stale blocked entries"
    )
    p_sync.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output including removed task IDs",
    )
    p_sync.add_argument(
        "--clean-attempts",
        action="store_true",
        help="Also remove attempt history for synced tasks",
    )
    p_sync.set_defaults(func=cmd_sync)

    # Interventions command: view intervention recommendations
    p_interventions = sub.add_parser(
        "interventions",
        help="Show intervention recommendations from failure pattern analysis"
    )
    p_interventions.add_argument(
        "--latest",
        action="store_true",
        help="Show only the latest recommendation with full details",
    )
    p_interventions.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format for machine consumption",
    )
    p_interventions.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of recommendations to show (default: 20)",
    )
    p_interventions.set_defaults(func=cmd_interventions)

    p_tui = sub.add_parser("tui", help="Interactive control surface (TUI)")
    p_tui.set_defaults(func=cmd_tui)

    p_serve = sub.add_parser("serve", help="Serve a minimal HTTP health endpoint")
    p_serve.add_argument(
        "--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)"
    )
    p_serve.add_argument(
        "--port", type=int, default=8080, help="Bind port (default: 8080)"
    )
    p_serve.set_defaults(func=cmd_serve)

    # Specs
    p_specs = sub.add_parser("specs", help="Work with specs/*")
    specs_sub = p_specs.add_subparsers(dest="specs_cmd", required=True)

    p_specs_check = specs_sub.add_parser("check", help="Lint/check specs/*.md")
    p_specs_check.add_argument(
        "--specs-dir", default=None, help="Specs directory (default: from config)"
    )
    p_specs_check.add_argument(
        "--strict", action="store_true", help="Treat warnings as errors"
    )
    p_specs_check.set_defaults(func=cmd_specs_check)

    # Planning helpers
    p_plan = sub.add_parser(
        "plan",
        help="Generate/update PRD from a description (runs the chosen agent once)",
    )
    p_plan.add_argument(
        "--agent",
        default=None,
        help="Runner to use (defaults to claude-zai/claude-kimi/claude/codex if configured)",
    )
    p_plan.add_argument("--desc", default=None, help="Short description text")
    p_plan.add_argument(
        "--desc-file",
        default=None,
        help="Path to a text/markdown file containing the description",
    )
    p_plan.add_argument(
        "--prd-file",
        default=None,
        help="Target file to write (defaults to files.prd from ralph.toml)",
    )
    p_plan.set_defaults(func=cmd_plan)

    p_regen = sub.add_parser(
        "regen-plan",
        help="Regenerate IMPLEMENTATION_PLAN.md from specs/* + codebase gap analysis",
    )
    p_regen.add_argument(
        "--agent",
        default=None,
        help="Runner to use (defaults to claude-zai/claude-kimi/claude/codex if configured)",
    )
    p_regen.add_argument(
        "--prd-file", default=None, help="Target plan file (defaults to files.prd)"
    )
    p_regen.add_argument(
        "--specs-dir", default=None, help="Specs directory (default: from config)"
    )
    p_regen.add_argument(
        "--no-specs-check",
        action="store_true",
        help="Don't run specs check before generating prompt",
    )
    p_regen.add_argument(
        "--strict",
        action="store_true",
        help="Fail if validation warnings are found in the regenerated plan",
    )
    p_regen.set_defaults(func=cmd_regen_plan)

    # Snapshots
    p_snapshot = sub.add_parser(
        "snapshot",
        help="Create or list git-based snapshots for safe rollback",
    )
    p_snapshot.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Name for the snapshot (use only letters, numbers, hyphens, underscores)",
    )
    p_snapshot.add_argument(
        "--list",
        action="store_true",
        help="List all available snapshots",
    )
    p_snapshot.add_argument(
        "--description",
        "-d",
        default=None,
        help="Optional description for the snapshot",
    )
    p_snapshot.set_defaults(func=cmd_snapshot)

    p_rollback = sub.add_parser(
        "rollback",
        help="Rollback to a previous snapshot",
    )
    p_rollback.add_argument(
        "name",
        help="Name of the snapshot to rollback to",
    )
    p_rollback.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force rollback even with uncommitted changes",
    )
    p_rollback.set_defaults(func=cmd_rollback)

    # Watch mode
    p_watch = sub.add_parser(
        "watch",
        help="Watch files and automatically run gates on changes",
    )
    p_watch.add_argument(
        "--gates-only",
        action="store_true",
        default=True,
        help="Only run gates (don't run full loop) - default behavior",
    )
    p_watch.add_argument(
        "--auto-commit",
        action="store_true",
        help="Automatically commit changes when gates pass",
    )
    p_watch.set_defaults(func=cmd_watch)

    # Task management
    p_task = sub.add_parser("task", help="Manage tasks in the PRD")
    task_sub = p_task.add_subparsers(dest="task_cmd", required=True)

    p_task_add = task_sub.add_parser(
        "add",
        help="Add a new task from a template",
    )
    p_task_add.add_argument(
        "--template",
        "-t",
        required=True,
        help="Template name (use 'ralph task templates' to list available templates)",
    )
    p_task_add.add_argument(
        "--title",
        required=True,
        help="Task title (will be substituted into template)",
    )
    p_task_add.add_argument(
        "--var",
        dest="variables",
        action="append",
        help="Additional template variables in format VAR=value (can be used multiple times)",
    )
    p_task_add.set_defaults(func=cmd_task_add)

    p_task_templates = task_sub.add_parser(
        "templates",
        help="List available task templates",
    )
    p_task_templates.set_defaults(func=cmd_task_templates)

    p_bridge = sub.add_parser(
        "bridge", help="Start a JSON-RPC bridge over stdio (for VS Code)"
    )
    p_bridge.set_defaults(func=cmd_bridge)

    # Completion
    p_completion = sub.add_parser(
        "completion", help="Generate shell completion scripts"
    )
    p_completion.add_argument(
        "shell",
        choices=["bash", "zsh"],
        help="Shell type (bash or zsh)",
    )
    p_completion.set_defaults(func=cmd_completion)

    # Convert
    p_convert = sub.add_parser(
        "convert", help="Convert PRD files (JSON or Markdown) to YAML format"
    )
    p_convert.add_argument("input_file", help="Input PRD file (JSON or Markdown)")
    p_convert.add_argument("output_file", help="Output YAML file path")
    p_convert.add_argument(
        "--infer-groups",
        action="store_true",
        help="Infer parallel groups from task titles",
    )
    p_convert.set_defaults(func=cmd_convert)

    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    # Apply output config from TOML before dispatching to command
    try:
        root = Path(os.getcwd()).resolve()
        cfg = load_config(root)
        env_format = os.environ.get("RALPH_FORMAT", "").strip().lower()
        env_verbosity = os.environ.get("RALPH_VERBOSITY", "").strip().lower()

        resolved_format = (
            args.global_format
            or (env_format if env_format in {"text", "json"} else None)
            or cfg.output.format
        )
        resolved_verbosity = (
            args.global_verbosity
            or (env_verbosity if env_verbosity in {"quiet", "normal", "verbose"} else None)
            or cfg.output.verbosity
        )
        output_cfg = OutputConfig(
            verbosity=resolved_verbosity,
            format=resolved_format,
            color=True,  # Default for now
        )
        set_output_config(output_cfg)
        reset_json_output_emitted()

        # Setup logging based on verbosity
        verbose = output_cfg.verbosity == "verbose"
        quiet = output_cfg.verbosity == "quiet"
        setup_logging(verbose=verbose, quiet=quiet)

        # Log startup
        logger = logging.getLogger(__name__)
        logger.debug(f"Ralph Gold v{__version__} starting")
        logger.debug(f"Command: {getattr(args, 'cmd', 'unknown')}")

        exit_code = int(args.func(args))
        if output_cfg.format == "json" and not has_json_output_emitted():
            print_json_output(
                build_json_response(
                    str(getattr(args, "cmd", "unknown")),
                    exit_code=exit_code,
                )
            )
        return exit_code
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error("%s", e)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
