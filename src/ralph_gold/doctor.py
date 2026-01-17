from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .config import Config


@dataclass
class ToolStatus:
    name: str
    found: bool
    path: Optional[str]
    version: Optional[str]
    hint: Optional[str]


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _version(cmd: List[str]) -> Optional[str]:
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, check=False)
        out = (cp.stdout or "").strip()
        err = (cp.stderr or "").strip()
        text = out if out else err
        if text:
            # first line only
            return text.splitlines()[0][:200]
        return None
    except Exception:
        return None


def check_tools(cfg: Optional[Config] = None) -> List[ToolStatus]:
    checks = [
        ("git", ["git", "--version"], "Install git and run `git init` in your project."),
        ("uv", ["uv", "--version"], "Install uv (https://docs.astral.sh/uv/)."),
        ("codex", ["codex", "--version"], "Install the Codex CLI (see OpenAI Codex docs)."),
        ("claude", ["claude", "--version"], "Install Claude Code CLI (see Anthropic Claude Code docs)."),
        ("copilot", ["copilot", "--version"], "Install GitHub Copilot CLI (or configure a different runner in ralph.toml)."),
        ("gh", ["gh", "--version"], "Optional: GitHub CLI, useful for Copilot workflows."),
    ]

    if cfg is not None:
        if cfg.repoprompt.enabled or cfg.repoprompt.required:
            checks.append(
                (
                    cfg.repoprompt.cli,
                    [cfg.repoprompt.cli, "--help"],
                    "Install rp-cli to enable Repo Prompt integration.",
                )
            )
        if cfg.gates.prek.enabled:
            prek_bin = cfg.gates.prek.argv[0] if cfg.gates.prek.argv else "prek"
            checks.append((prek_bin, [prek_bin, "--version"], "Install prek for gate runner."))

    results: List[ToolStatus] = []
    for name, ver_cmd, hint in checks:
        path = _which(name)
        found = path is not None
        version = _version(ver_cmd) if found else None
        results.append(ToolStatus(name=name, found=found, path=path, version=version, hint=None if found else hint))
    return results


def _detect_project_type(project_root: Path) -> str:
    """Detect project type based on files present."""
    
    if (project_root / "package.json").exists():
        return "node"
    elif (project_root / "pyproject.toml").exists():
        return "python"
    elif (project_root / "Cargo.toml").exists():
        return "rust"
    elif (project_root / "go.mod").exists():
        return "go"
    else:
        return "unknown"


def _detect_package_manager(project_root: Path) -> Optional[str]:
    """Detect Node.js package manager."""
    
    if (project_root / "pnpm-lock.yaml").exists():
        return "pnpm"
    elif (project_root / "yarn.lock").exists():
        return "yarn"
    elif (project_root / "package-lock.json").exists():
        return "npm"
    elif (project_root / "bun.lockb").exists():
        return "bun"
    return None


def _get_check_commands(project_type: str, project_root: Path) -> Tuple[List[str], str]:
    """Return (commands, script_name) for the detected project type."""
    
    if project_type == "node":
        pm = _detect_package_manager(project_root) or "npm"
        
        # Try to detect existing scripts
        package_json = project_root / "package.json"
        existing_scripts = []
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
                scripts = data.get("scripts", {})
                existing_scripts = list(scripts.keys())
            except Exception:
                pass
        
        # Build check command from common patterns
        commands = []
        if "typecheck" in existing_scripts:
            commands.append(f"{pm} -s typecheck")
        elif "tsc" in existing_scripts:
            commands.append(f"{pm} -s tsc")
        
        if "test" in existing_scripts:
            commands.append(f"{pm} -s test")
        
        if "lint" in existing_scripts:
            commands.append(f"{pm} -s lint")
        
        # Fallback: suggest common commands
        if not commands:
            commands = [
                f"{pm} -s typecheck",
                f"{pm} -s test",
                f"{pm} -s lint",
            ]
        
        return commands, "check"
    
    elif project_type == "python":
        commands = []
        
        # Check for common Python tools
        if (project_root / "pyproject.toml").exists():
            pyproject = project_root / "pyproject.toml"
            content = pyproject.read_text(encoding="utf-8")
            
            if "mypy" in content:
                commands.append("uv run mypy .")
            if "pytest" in content:
                commands.append("uv run pytest -q")
            if "ruff" in content:
                commands.append("uv run ruff check .")
        
        # Fallback
        if not commands:
            commands = [
                "uv run pytest -q",
                "uv run ruff check .",
            ]
        
        return commands, "check"
    
    else:
        # Generic fallback
        return ["make test", "make lint"], "check"


def setup_checks(project_root: Path, dry_run: bool = False) -> dict:
    """Setup canonical check script and configure ralph.toml.
    
    Returns a dict with:
    - project_type: detected type
    - commands: suggested gate commands
    - script_name: name of the check script
    - actions_taken: list of changes made
    - suggestions: list of manual steps needed
    """
    
    project_type = _detect_project_type(project_root)
    commands, script_name = _get_check_commands(project_type, project_root)
    
    actions_taken = []
    suggestions = []
    
    # 1) Update package.json (Node projects)
    if project_type == "node":
        package_json = project_root / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
                scripts = data.setdefault("scripts", {})
                
                # Add check script if not present
                if script_name not in scripts:
                    check_cmd = " && ".join(commands)
                    scripts[script_name] = check_cmd
                    
                    if not dry_run:
                        package_json.write_text(
                            json.dumps(data, indent=2) + "\n",
                            encoding="utf-8"
                        )
                        actions_taken.append(f"Added '{script_name}' script to package.json")
                    else:
                        suggestions.append(f"Would add '{script_name}' script to package.json")
                else:
                    suggestions.append(f"Script '{script_name}' already exists in package.json")
            except Exception as e:
                suggestions.append(f"Could not update package.json: {e}")
    
    # 2) Update .ralph/ralph.toml
    ralph_toml = project_root / ".ralph" / "ralph.toml"
    if ralph_toml.exists():
        try:
            content = ralph_toml.read_text(encoding="utf-8")
            
            # Check if gates are already configured
            if "[gates]" in content and "commands = [" in content:
                suggestions.append("Gates already configured in .ralph/ralph.toml")
            else:
                # Suggest gate configuration
                pm = _detect_package_manager(project_root) if project_type == "node" else None
                gate_config = "\n# Quality gates (auto-configured by ralph doctor)\n[gates]\n"
                
                if project_type == "node" and pm:
                    gate_config += f'commands = ["{pm} -s {script_name}"]\n'
                elif project_type == "python":
                    gate_config += 'commands = [\n'
                    for cmd in commands:
                        gate_config += f'  "{cmd}",\n'
                    gate_config += ']\n'
                else:
                    gate_config += f'commands = ["{commands[0]}"]\n'
                
                gate_config += "precommit_hook = true  # auto-discover .husky/pre-commit or .git/hooks/pre-commit\n"
                gate_config += "fail_fast = true\n"
                gate_config += 'output_mode = "summary"  # full|summary|errors_only\n'
                gate_config += "max_output_lines = 50\n"
                
                if not dry_run:
                    # Append to file
                    with ralph_toml.open("a", encoding="utf-8") as f:
                        f.write("\n" + gate_config)
                    actions_taken.append("Added gates configuration to .ralph/ralph.toml")
                else:
                    suggestions.append("Would add gates configuration to .ralph/ralph.toml")
        except Exception as e:
            suggestions.append(f"Could not update .ralph/ralph.toml: {e}")
    else:
        suggestions.append(".ralph/ralph.toml not found - run 'ralph init' first")
    
    # 3) Suggest Husky setup (Node projects)
    if project_type == "node":
        husky_dir = project_root / ".husky"
        if not husky_dir.exists():
            pm = _detect_package_manager(project_root) or "npm"
            suggestions.append(f"Consider setting up Husky: {pm} add -D husky && {pm} exec husky init")
        else:
            pre_commit = husky_dir / "pre-commit"
            if not pre_commit.exists():
                suggestions.append("Husky installed but no pre-commit hook - create .husky/pre-commit")
            else:
                actions_taken.append("Found existing .husky/pre-commit hook")
    
    return {
        "project_type": project_type,
        "commands": commands,
        "script_name": script_name,
        "actions_taken": actions_taken,
        "suggestions": suggestions,
    }
