"""Diagnostics module for Ralph Gold.

Validates configuration, PRD format, and tests gate commands.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

try:
    import tomllib  # py>=3.11
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from .config import Config, load_config
from .prd import is_markdown_prd
from .trackers import make_tracker


@dataclass
class DiagnosticResult:
    """Result of a diagnostic check."""

    check_name: str
    passed: bool
    message: str
    suggestions: List[str]
    severity: str  # error|warning|info


def validate_config(project_root: Path) -> List[DiagnosticResult]:
    """Validate ralph.toml syntax and schema.

    Args:
        project_root: Path to the project root directory

    Returns:
        List of diagnostic results for configuration validation
    """
    results: List[DiagnosticResult] = []

    # Check for config file existence
    config_paths = [
        project_root / ".ralph" / "ralph.toml",
        project_root / "ralph.toml",
    ]

    config_exists = any(p.exists() for p in config_paths)

    if not config_exists:
        results.append(
            DiagnosticResult(
                check_name="config_exists",
                passed=False,
                message="No ralph.toml configuration file found",
                suggestions=[
                    "Create .ralph/ralph.toml or ralph.toml in project root",
                    "Run 'ralph init' to create default configuration",
                ],
                severity="warning",
            )
        )
        # Return early - can't validate syntax if file doesn't exist
        return results

    # Config exists - add success result
    results.append(
        DiagnosticResult(
            check_name="config_exists",
            passed=True,
            message="Configuration file found",
            suggestions=[],
            severity="info",
        )
    )

    # Try to load and parse TOML
    for config_path in config_paths:
        if not config_path.exists():
            continue

        try:
            content = config_path.read_text(encoding="utf-8")
            tomllib.loads(content)
            results.append(
                DiagnosticResult(
                    check_name="toml_syntax",
                    passed=True,
                    message=f"Configuration file {config_path.name} has valid TOML syntax",
                    suggestions=[],
                    severity="info",
                )
            )
        except tomllib.TOMLDecodeError as e:
            results.append(
                DiagnosticResult(
                    check_name="toml_syntax",
                    passed=False,
                    message=f"Invalid TOML syntax in {config_path.name}: {e}",
                    suggestions=[
                        "Check TOML syntax at the reported line",
                        "Ensure proper quoting of strings",
                        "Verify array and table syntax",
                    ],
                    severity="error",
                )
            )
            # Return early - can't validate schema if syntax is invalid
            return results
        except Exception as e:
            results.append(
                DiagnosticResult(
                    check_name="toml_syntax",
                    passed=False,
                    message=f"Error reading {config_path.name}: {e}",
                    suggestions=[
                        "Check file permissions",
                        "Verify file encoding (should be UTF-8)",
                    ],
                    severity="error",
                )
            )
            return results

    # Try to load config with schema validation
    try:
        cfg = load_config(project_root)
        results.append(
            DiagnosticResult(
                check_name="config_schema",
                passed=True,
                message="Configuration schema is valid",
                suggestions=[],
                severity="info",
            )
        )

        # Validate that at least one runner is configured
        if not cfg.runners:
            results.append(
                DiagnosticResult(
                    check_name="runners_configured",
                    passed=False,
                    message="No runners configured",
                    suggestions=[
                        "Add at least one runner in [runners] section",
                        "Example: [runners.codex] with argv configuration",
                    ],
                    severity="error",
                )
            )
        else:
            results.append(
                DiagnosticResult(
                    check_name="runners_configured",
                    passed=True,
                    message=f"Found {len(cfg.runners)} configured runner(s)",
                    suggestions=[],
                    severity="info",
                )
            )

    except ValueError as e:
        results.append(
            DiagnosticResult(
                check_name="config_schema",
                passed=False,
                message=f"Configuration validation error: {e}",
                suggestions=[
                    "Check configuration values match expected types",
                    "Review ralph.toml documentation for valid options",
                ],
                severity="error",
            )
        )
    except Exception as e:
        results.append(
            DiagnosticResult(
                check_name="config_schema",
                passed=False,
                message=f"Unexpected error loading configuration: {e}",
                suggestions=[
                    "Check for syntax errors in configuration",
                    "Verify all required fields are present",
                ],
                severity="error",
            )
        )

    return results


def validate_prd(project_root: Path, cfg: Config) -> List[DiagnosticResult]:
    """Validate PRD file format (JSON/Markdown/YAML).

    Args:
        project_root: Path to the project root directory
        cfg: Loaded configuration

    Returns:
        List of diagnostic results for PRD validation
    """
    results: List[DiagnosticResult] = []

    prd_path = project_root / cfg.files.prd

    # Check if PRD file exists
    if not prd_path.exists():
        results.append(
            DiagnosticResult(
                check_name="prd_exists",
                passed=False,
                message=f"PRD file not found: {cfg.files.prd}",
                suggestions=[
                    f"Create PRD file at {cfg.files.prd}",
                    "Run 'ralph init' to create default PRD",
                    "Check files.prd configuration in ralph.toml",
                ],
                severity="error",
            )
        )
        return results

    results.append(
        DiagnosticResult(
            check_name="prd_exists",
            passed=True,
            message=f"PRD file found: {cfg.files.prd}",
            suggestions=[],
            severity="info",
        )
    )

    # Detect PRD format
    is_markdown = is_markdown_prd(prd_path)
    prd_format = "markdown" if is_markdown else "json/yaml"

    # Try to parse PRD using the tracker
    try:
        tracker = make_tracker(project_root, cfg)
        results.append(
            DiagnosticResult(
                check_name="prd_format",
                passed=True,
                message=f"PRD file has valid {prd_format} format",
                suggestions=[],
                severity="info",
            )
        )

        # Try to get task counts to verify structure
        try:
            done, total = tracker.counts()
            results.append(
                DiagnosticResult(
                    check_name="prd_structure",
                    passed=True,
                    message=f"PRD structure is valid ({done}/{total} tasks complete)",
                    suggestions=[],
                    severity="info",
                )
            )
        except Exception as e:
            results.append(
                DiagnosticResult(
                    check_name="prd_structure",
                    passed=False,
                    message=f"PRD structure validation failed: {e}",
                    suggestions=[
                        "Verify task format matches expected structure",
                        "Check for required fields in tasks",
                    ],
                    severity="warning",
                )
            )

    except json.JSONDecodeError as e:
        results.append(
            DiagnosticResult(
                check_name="prd_format",
                passed=False,
                message=f"Invalid JSON in PRD file: {e}",
                suggestions=[
                    "Check JSON syntax",
                    "Verify proper quoting and comma placement",
                    "Use a JSON validator to identify the error",
                ],
                severity="error",
            )
        )
    except Exception as e:
        results.append(
            DiagnosticResult(
                check_name="prd_format",
                passed=False,
                message=f"Error parsing PRD file: {e}",
                suggestions=[
                    "Verify PRD file format matches tracker configuration",
                    "Check for syntax errors in the file",
                    "Ensure file encoding is UTF-8",
                ],
                severity="error",
            )
        )

    return results


def check_gates(project_root: Path, cfg: Config) -> List[DiagnosticResult]:
    """Test each gate command individually.

    Args:
        project_root: Path to the project root directory
        cfg: Loaded configuration

    Returns:
        List of diagnostic results for gate command testing
    """
    results: List[DiagnosticResult] = []

    if not cfg.gates.commands:
        results.append(
            DiagnosticResult(
                check_name="gates_configured",
                passed=True,
                message="No gate commands configured (this is optional)",
                suggestions=[
                    "Add gate commands in [gates] section if you want automated checks",
                    "Example: commands = ['npm test', 'npm run lint']",
                ],
                severity="info",
            )
        )
        return results

    results.append(
        DiagnosticResult(
            check_name="gates_configured",
            passed=True,
            message=f"Found {len(cfg.gates.commands)} gate command(s) configured",
            suggestions=[],
            severity="info",
        )
    )

    # Test each gate command
    for idx, cmd in enumerate(cfg.gates.commands, 1):
        try:
            # Determine shell based on platform
            import os
            import shutil

            if os.name == "nt":
                shell_argv = ["cmd", "/c", cmd]
            elif shutil.which("bash"):
                shell_argv = ["bash", "-lc", cmd]
            else:
                shell_argv = ["sh", "-lc", cmd]

            # Run the command with a timeout
            result = subprocess.run(
                shell_argv,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout for diagnostics
            )

            if result.returncode == 0:
                results.append(
                    DiagnosticResult(
                        check_name=f"gate_{idx}",
                        passed=True,
                        message=f"Gate command {idx} passed: {cmd}",
                        suggestions=[],
                        severity="info",
                    )
                )
            else:
                # Truncate output for readability
                stderr_preview = (result.stderr or "")[:200]
                if len(result.stderr or "") > 200:
                    stderr_preview += "..."

                results.append(
                    DiagnosticResult(
                        check_name=f"gate_{idx}",
                        passed=False,
                        message=f"Gate command {idx} failed (exit code {result.returncode}): {cmd}",
                        suggestions=[
                            "Fix the issues reported by the gate command",
                            f"Error output: {stderr_preview}"
                            if stderr_preview
                            else "Check command output for details",
                            "Run the command manually to see full output",
                        ],
                        severity="error",
                    )
                )

        except subprocess.TimeoutExpired:
            results.append(
                DiagnosticResult(
                    check_name=f"gate_{idx}",
                    passed=False,
                    message=f"Gate command {idx} timed out (>30s): {cmd}",
                    suggestions=[
                        "Command may be hanging or taking too long",
                        "Check if command requires user input",
                        "Consider optimizing the command for faster execution",
                    ],
                    severity="error",
                )
            )
        except FileNotFoundError:
            results.append(
                DiagnosticResult(
                    check_name=f"gate_{idx}",
                    passed=False,
                    message=f"Gate command {idx} not found: {cmd}",
                    suggestions=[
                        "Verify the command is installed and in PATH",
                        "Check command spelling",
                        "Install required dependencies",
                    ],
                    severity="error",
                )
            )
        except Exception as e:
            results.append(
                DiagnosticResult(
                    check_name=f"gate_{idx}",
                    passed=False,
                    message=f"Error running gate command {idx}: {e}",
                    suggestions=[
                        "Check command syntax",
                        "Verify command is executable",
                        "Check for permission issues",
                    ],
                    severity="error",
                )
            )

    return results


def check_dependencies(project_root: Path, cfg: Config) -> List[DiagnosticResult]:
    """Check for circular dependencies in task dependencies.

    Args:
        project_root: Path to the project root directory
        cfg: Loaded configuration

    Returns:
        List of diagnostic results for dependency checking
    """
    results: List[DiagnosticResult] = []

    try:
        from .dependencies import build_dependency_graph, detect_circular_dependencies
        from .prd import get_all_tasks

        # Get PRD path from config
        prd_path = project_root / cfg.files.prd

        if not prd_path.exists():
            results.append(
                DiagnosticResult(
                    check_name="dependencies_check",
                    passed=True,
                    message="PRD file not found, skipping dependency check",
                    suggestions=[],
                    severity="info",
                )
            )
            return results

        # Load all tasks
        tasks = get_all_tasks(prd_path)

        if not tasks:
            results.append(
                DiagnosticResult(
                    check_name="dependencies_check",
                    passed=True,
                    message="No tasks found, skipping dependency check",
                    suggestions=[],
                    severity="info",
                )
            )
            return results

        # Check if any tasks have dependencies
        has_dependencies = any(task.get("depends_on") for task in tasks)

        if not has_dependencies:
            results.append(
                DiagnosticResult(
                    check_name="dependencies_check",
                    passed=True,
                    message="No task dependencies defined",
                    suggestions=[],
                    severity="info",
                )
            )
            return results

        # Build dependency graph
        graph = build_dependency_graph(tasks)

        # Detect circular dependencies
        cycles = detect_circular_dependencies(graph)

        if not cycles:
            results.append(
                DiagnosticResult(
                    check_name="circular_dependencies",
                    passed=True,
                    message=f"No circular dependencies found ({len(graph.nodes)} tasks checked)",
                    suggestions=[],
                    severity="info",
                )
            )
        else:
            # Format cycle information
            cycle_descriptions = []
            for i, cycle in enumerate(cycles, 1):
                cycle_str = " → ".join(cycle)
                cycle_descriptions.append(f"Cycle {i}: {cycle_str}")

            results.append(
                DiagnosticResult(
                    check_name="circular_dependencies",
                    passed=False,
                    message=f"Found {len(cycles)} circular dependency cycle(s)",
                    suggestions=[
                        "Remove circular dependencies to allow tasks to execute",
                        "Circular dependencies detected:",
                        *cycle_descriptions,
                        "Break the cycle by removing one or more 'depends_on' relationships",
                    ],
                    severity="error",
                )
            )

    except Exception as e:
        results.append(
            DiagnosticResult(
                check_name="dependencies_check",
                passed=False,
                message=f"Error checking dependencies: {e}",
                suggestions=[
                    "Verify task dependency format",
                    "Check that all referenced task IDs exist",
                ],
                severity="warning",
            )
        )

    return results


def run_diagnostics(
    project_root: Path, test_gates_flag: bool = False
) -> Tuple[List[DiagnosticResult], int]:
    """Run all diagnostic checks.

    Args:
        project_root: Path to the project root directory
        test_gates_flag: Whether to test gate commands

    Returns:
        Tuple of (results list, exit code)
        Exit code: 0 if all checks pass, 2 if any issues found
    """
    all_results: List[DiagnosticResult] = []

    # Always validate configuration
    config_results = validate_config(project_root)
    all_results.extend(config_results)

    # Check if config file exists (not just if validation passed)
    config_exists = any(
        r.check_name == "config_exists" and r.passed for r in config_results
    )

    # Check if config validation has errors (not warnings)
    config_has_errors = any(
        r.severity == "error" and not r.passed for r in config_results
    )

    # Only proceed with PRD and gate validation if config exists and has no errors
    if config_exists and not config_has_errors:
        try:
            cfg = load_config(project_root)

            # Validate PRD
            prd_results = validate_prd(project_root, cfg)
            all_results.extend(prd_results)

            # Check for circular dependencies
            dependency_results = check_dependencies(project_root, cfg)
            all_results.extend(dependency_results)

            # Test gates if requested
            if test_gates_flag:
                gate_results = check_gates(project_root, cfg)
                all_results.extend(gate_results)

        except Exception as e:
            all_results.append(
                DiagnosticResult(
                    check_name="diagnostics_error",
                    passed=False,
                    message=f"Unexpected error during diagnostics: {e}",
                    suggestions=[
                        "Check configuration and PRD files",
                        "Run with --verbose for more details",
                    ],
                    severity="error",
                )
            )

    # Determine exit code
    # Exit code 0: all checks passed (or only warnings/info)
    # Exit code 2: at least one error found
    has_errors = any(r.severity == "error" and not r.passed for r in all_results)
    exit_code = 2 if has_errors else 0

    return all_results, exit_code
