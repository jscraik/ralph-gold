"""Shell completion generation for Ralph Gold.

This module provides functionality for generating shell completion scripts
for bash and zsh. Completions are generated from argparse definitions and
include support for dynamic values like agent names and templates.
"""

from __future__ import annotations

import json
import logging

from pathlib import Path
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .config import Config


def load_completion_data(completion_path: Path) -> list[dict]:
    """Load completion data from a JSON file.

    Args:
        completion_path: Path to the completion data file

    Returns:
        List of completion entries, or empty list if loading fails
    """
    try:
        completion_data = json.loads(completion_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Failed to load completion data: %s", e)
        return []


def save_completion_data(completion_path: Path, completion_data: list[dict]) -> None:
    """Save completion data to a JSON file.

    Args:
        completion_path: Path to the completion data file
        completion_data: List of completion entries to save
    """
    try:
        completion_path.write_text(json.dumps(completion_data), encoding="utf-8")
    except OSError as e:
        logger.debug("Failed to save completion data: %s", e)


def generate_bash_completion() -> str:
    """Generate bash completion script for Ralph commands.

    Returns:
        Bash completion script as a string

    Examples:
        >>> script = generate_bash_completion()
        >>> assert '_ralph_completion()' in script
    """
    # Bash completion script using complete builtin
    # This provides basic command and flag completion
    script = r"""# Bash completion for ralph-gold
# Source this file or add to ~/.bashrc:
#   source ~/.ralph-completion.sh
# Or install system-wide:
#   sudo cp ~/.ralph-completion.sh /etc/bash_completion.d/ralph

_ralph_completion() {
    local cur prev words cword
    _init_completion || return

    # Main commands
    local commands="init doctor diagnose stats resume clean step run supervise status tui serve specs plan regen-plan snapshot rollback watch task bridge convert completion"
    
    # Global flags
    local global_flags="--version --quiet --verbose --format"
    
    # Command-specific flags
    local init_flags="--force --format --solo"
    local doctor_flags="--setup-checks --dry-run --check-github"
    local diagnose_flags="--test-gates"
    local stats_flags="--by-task --export"
    local resume_flags="--clear --auto"
    local clean_flags="--logs-days --archives-days --receipts-days --context-days --dry-run"
    local step_flags="--agent --mode --prompt-file --prd-file --dry-run --interactive"
    local run_flags="--agent --mode --max-iterations --prompt-file --prd-file --parallel --max-workers --dry-run"
    local supervise_flags="--agent --mode --max-runtime-seconds --heartbeat-seconds --sleep-seconds-between-runs --on-no-progress-limit --on-rate-limit --notify --no-notify --notify-backend --notify-command"
    local status_flags="--graph --detailed --chart"
    local serve_flags="--host --port"
    local plan_flags="--agent --desc --desc-file --prd-file"
    local regen_flags="--agent --prd-file --specs-dir --no-specs-check"
    local snapshot_flags="--list --description"
    local rollback_flags="--force"
    local watch_flags="--gates-only --auto-commit"
    local task_flags="add templates"
    local task_add_flags="--template --title --var"
    local specs_flags="check"
    local specs_check_flags="--specs-dir --strict"
    local convert_flags="--infer-groups"
    
    # Agent names for --agent flag
    local agents="codex claude claude-zai claude-kimi copilot"
    local modes="speed quality exploration"
    
    # Format values for --format flag
    local formats="text json"
    
    # Tracker formats for init --format
    local tracker_formats="markdown json yaml"

    # Get the command (first non-flag argument)
    local command=""
    local i
    for (( i=1; i < ${#words[@]}; i++ )); do
        if [[ ${words[i]} != -* ]]; then
            command=${words[i]}
            break
        fi
    done

    # If no command yet, complete commands
    if [[ -z "$command" || "$cword" -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
        return 0
    fi

    # Handle subcommands
    case "$command" in
        specs)
            if [[ "$cword" -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "$specs_flags" -- "$cur") )
                return 0
            elif [[ "${words[2]}" == "check" ]]; then
                COMPREPLY=( $(compgen -W "$specs_check_flags" -- "$cur") )
                return 0
            fi
            ;;
        task)
            if [[ "$cword" -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "$task_flags" -- "$cur") )
                return 0
            elif [[ "${words[2]}" == "add" ]]; then
                case "$prev" in
                    --agent)
                        COMPREPLY=( $(compgen -W "$agents" -- "$cur") )
                        return 0
                        ;;
                    --template|-t)
                        # Dynamic completion for templates
                        local templates=$(ralph task templates 2>/dev/null | grep -E '^\s+\*' | awk '{print $2}' | tr '\n' ' ')
                        COMPREPLY=( $(compgen -W "$templates" -- "$cur") )
                        return 0
                        ;;
                    *)
                        COMPREPLY=( $(compgen -W "$task_add_flags" -- "$cur") )
                        return 0
                        ;;
                esac
            fi
            ;;
    esac

    # Handle flag-specific completions
    case "$prev" in
        --agent)
            COMPREPLY=( $(compgen -W "$agents" -- "$cur") )
            return 0
            ;;
        --mode)
            COMPREPLY=( $(compgen -W "$modes" -- "$cur") )
            return 0
            ;;
        --format)
            if [[ "$command" == "init" ]]; then
                COMPREPLY=( $(compgen -W "$tracker_formats" -- "$cur") )
            else
                COMPREPLY=( $(compgen -W "$formats" -- "$cur") )
            fi
            return 0
            ;;
        --export|--prompt-file|--prd-file|--desc-file|--specs-dir)
            # File completion
            COMPREPLY=( $(compgen -f -- "$cur") )
            return 0
            ;;
        --logs-days|--archives-days|--receipts-days|--context-days|--max-iterations|--max-workers|--port|--max-runtime-seconds|--heartbeat-seconds|--sleep-seconds-between-runs)
            # Numeric completion - no suggestions
            return 0
            ;;
        --host)
            # Common host values
            COMPREPLY=( $(compgen -W "127.0.0.1 0.0.0.0 localhost" -- "$cur") )
            return 0
            ;;
        rollback)
            # Dynamic completion for snapshot names
            local snapshots=$(ralph snapshot --list 2>/dev/null | grep -E '^\s+\*' | awk '{print $2}' | tr '\n' ' ')
            COMPREPLY=( $(compgen -W "$snapshots" -- "$cur") )
            return 0
            ;;
    esac

    # Command-specific flag completion
    case "$command" in
        init)
            COMPREPLY=( $(compgen -W "$init_flags" -- "$cur") )
            ;;
        doctor)
            COMPREPLY=( $(compgen -W "$doctor_flags" -- "$cur") )
            ;;
        diagnose)
            COMPREPLY=( $(compgen -W "$diagnose_flags" -- "$cur") )
            ;;
        stats)
            COMPREPLY=( $(compgen -W "$stats_flags" -- "$cur") )
            ;;
        resume)
            COMPREPLY=( $(compgen -W "$resume_flags" -- "$cur") )
            ;;
        clean)
            COMPREPLY=( $(compgen -W "$clean_flags" -- "$cur") )
            ;;
        step)
            COMPREPLY=( $(compgen -W "$step_flags" -- "$cur") )
            ;;
        run)
            COMPREPLY=( $(compgen -W "$run_flags" -- "$cur") )
            ;;
        supervise)
            COMPREPLY=( $(compgen -W "$supervise_flags" -- "$cur") )
            ;;
        status)
            COMPREPLY=( $(compgen -W "$status_flags" -- "$cur") )
            ;;
        serve)
            COMPREPLY=( $(compgen -W "$serve_flags" -- "$cur") )
            ;;
        plan)
            COMPREPLY=( $(compgen -W "$plan_flags" -- "$cur") )
            ;;
        regen-plan)
            COMPREPLY=( $(compgen -W "$regen_flags" -- "$cur") )
            ;;
        snapshot)
            COMPREPLY=( $(compgen -W "$snapshot_flags" -- "$cur") )
            ;;
        rollback)
            COMPREPLY=( $(compgen -W "$rollback_flags" -- "$cur") )
            ;;
        watch)
            COMPREPLY=( $(compgen -W "$watch_flags" -- "$cur") )
            ;;
        convert)
            COMPREPLY=( $(compgen -W "$convert_flags" -- "$cur") )
            ;;
        *)
            COMPREPLY=( $(compgen -W "$global_flags" -- "$cur") )
            ;;
    esac
}

complete -F _ralph_completion ralph
"""
    return script


def generate_zsh_completion() -> str:
    """Generate zsh completion script for Ralph commands.

    Returns:
        Zsh completion script as a string

    Examples:
        >>> script = generate_zsh_completion()
        >>> assert '#compdef ralph' in script
    """
    # Zsh completion script using compdef
    # This provides more sophisticated completion with descriptions
    script = r"""#compdef ralph
# Zsh completion for ralph-gold
# Install by placing in a directory in your $fpath, e.g.:
#   mkdir -p ~/.zsh/completion
#   cp _ralph ~/.zsh/completion/
#   Add to ~/.zshrc: fpath=(~/.zsh/completion $fpath)
#   Then run: compinit

_ralph() {
    local curcontext="$curcontext" state line
    typeset -A opt_args

    local -a commands
    commands=(
        'init:Initialize Ralph files in the current repo'
        'doctor:Check local prerequisites (git, uv, agent CLIs)'
        'diagnose:Run diagnostic checks on configuration and PRD'
        'stats:Display iteration statistics from Ralph history'
        'resume:Detect and resume interrupted iterations'
        'clean:Clean old logs, archives, and other workspace artifacts'
        'step:Run exactly one iteration'
        'run:Run the loop for N iterations'
        'supervise:Run supervisor loop (heartbeat + notifications)'
        'status:Show PRD progress + last iteration summary'
        'tui:Interactive control surface (TUI)'
        'serve:Serve a minimal HTTP health endpoint'
        'specs:Work with specs/*'
        'plan:Generate/update PRD from a description'
        'regen-plan:Regenerate IMPLEMENTATION_PLAN.md from specs/*'
        'snapshot:Create or list git-based snapshots for safe rollback'
        'rollback:Rollback to a previous snapshot'
        'watch:Watch files and automatically run gates on changes'
        'task:Manage tasks in the PRD'
        'bridge:Start a JSON-RPC bridge over stdio (for VS Code)'
        'convert:Convert PRD files (JSON or Markdown) to YAML format'
        'completion:Generate shell completion scripts'
    )

    _arguments -C \
        '(- *)--version[Show version information]' \
        '--quiet[Minimal output for CI/CD]' \
        '--verbose[Detailed debug output]' \
        '--format[Output format]:format:(text json)' \
        '1: :->command' \
        '*::arg:->args'

    case $state in
        command)
            _describe -t commands 'ralph commands' commands
            ;;
        args)
            case $line[1] in
                init)
                    _arguments \
                        '--force[Overwrite existing files]' \
                        '--solo[Use solo-dev optimized defaults for ralph.toml]' \
                        '--format[Task tracker format]:format:(markdown json yaml)'
                    ;;
                doctor)
                    _arguments \
                        '--setup-checks[Auto-configure quality gates for your project]' \
                        '--dry-run[Preview changes without applying them]' \
                        '--check-github[Check GitHub authentication]'
                    ;;
                diagnose)
                    _arguments \
                        '--test-gates[Test each gate command individually]'
                    ;;
                stats)
                    _arguments \
                        '--by-task[Show detailed per-task breakdown]' \
                        '--export[Export statistics to CSV file]:file:_files'
                    ;;
                resume)
                    _arguments \
                        '--clear[Clear the interrupted iteration without resuming]' \
                        '--auto[Resume automatically without prompting]'
                    ;;
                clean)
                    _arguments \
                        '--logs-days[Remove logs older than N days]:days:' \
                        '--archives-days[Remove archives older than N days]:days:' \
                        '--receipts-days[Remove receipts older than N days]:days:' \
                        '--context-days[Remove context files older than N days]:days:' \
                        '--dry-run[Preview what would be deleted]'
                    ;;
                step)
                    _arguments \
                        '--agent[Runner to use]:agent:(codex claude claude-zai claude-kimi copilot)' \
                        '--mode[Override loop.mode]:mode:(speed quality exploration)' \
                        '--prompt-file[Override files.prompt]:file:_files' \
                        '--prd-file[Override files.prd]:file:_files' \
                        '--dry-run[Simulate execution without running agents]' \
                        '--interactive[Interactively select which task to work on]'
                    ;;
                run)
                    _arguments \
                        '--agent[Runner to use]:agent:(codex claude claude-zai claude-kimi copilot)' \
                        '--mode[Override loop.mode]:mode:(speed quality exploration)' \
                        '--max-iterations[Override loop.max_iterations]:iterations:' \
                        '--prompt-file[Override files.prompt]:file:_files' \
                        '--prd-file[Override files.prd]:file:_files' \
                        '--parallel[Enable parallel execution with git worktrees]' \
                        '--max-workers[Number of parallel workers]:workers:' \
                        '--dry-run[Simulate execution without running agents]'
                    ;;
                supervise)
                    _arguments \
                        '--agent[Runner to use]:agent:(codex claude claude-zai claude-kimi copilot)' \
                        '--mode[Override loop.mode]:mode:(speed quality exploration)' \
                        '--max-runtime-seconds[Stop after N seconds]:seconds:' \
                        '--heartbeat-seconds[Heartbeat interval seconds]:seconds:' \
                        '--sleep-seconds-between-runs[Sleep between iterations]:seconds:' \
                        '--on-no-progress-limit[Policy when no-progress limit hit]:policy:(stop continue)' \
                        '--on-rate-limit[Policy when rate limit hit]:policy:(wait stop)' \
                        '--notify[Enable OS notifications]' \
                        '--no-notify[Disable OS notifications]' \
                        '--notify-backend[Notification backend]:backend:(auto macos linux windows command none)' \
                        '--notify-command[Command argv when backend=command]:command:_files'
                    ;;
                status)
                    _arguments \
                        '--graph[Display task dependency graph visualization]' \
                        '--detailed[Show detailed progress metrics]' \
                        '--chart[Display ASCII burndown chart]'
                    ;;
                serve)
                    _arguments \
                        '--host[Bind host]:host:(127.0.0.1 0.0.0.0 localhost)' \
                        '--port[Bind port]:port:'
                    ;;
                specs)
                    local -a specs_commands
                    specs_commands=(
                        'check:Lint/check specs/*.md'
                    )
                    _arguments \
                        '1: :->specs_command' \
                        '*::arg:->specs_args'
                    
                    case $state in
                        specs_command)
                            _describe -t specs_commands 'specs commands' specs_commands
                            ;;
                        specs_args)
                            case $line[1] in
                                check)
                                    _arguments \
                                        '--specs-dir[Specs directory]:dir:_directories' \
                                        '--strict[Treat warnings as errors]'
                                    ;;
                            esac
                            ;;
                    esac
                    ;;
                plan)
                    _arguments \
                        '--agent[Runner to use]:agent:(codex claude claude-zai claude-kimi copilot)' \
                        '--desc[Short description text]:description:' \
                        '--desc-file[Path to description file]:file:_files' \
                        '--prd-file[Target file to write]:file:_files'
                    ;;
                regen-plan)
                    _arguments \
                        '--agent[Runner to use]:agent:(codex claude claude-zai claude-kimi copilot)' \
                        '--prd-file[Target plan file]:file:_files' \
                        '--specs-dir[Specs directory]:dir:_directories' \
                        '--no-specs-check[Do not run specs check before generating]'
                    ;;
                snapshot)
                    _arguments \
                        '--list[List all available snapshots]' \
                        '--description[Optional description for the snapshot]:description:' \
                        '1:name:'
                    ;;
                rollback)
                    _arguments \
                        '--force[Force rollback even with uncommitted changes]' \
                        '1:name:_ralph_snapshots'
                    ;;
                watch)
                    _arguments \
                        '--gates-only[Only run gates (default behavior)]' \
                        '--auto-commit[Automatically commit changes when gates pass]'
                    ;;
                task)
                    local -a task_commands
                    task_commands=(
                        'add:Add a new task from a template'
                        'templates:List available task templates'
                    )
                    _arguments \
                        '1: :->task_command' \
                        '*::arg:->task_args'
                    
                    case $state in
                        task_command)
                            _describe -t task_commands 'task commands' task_commands
                            ;;
                        task_args)
                            case $line[1] in
                                add)
                                    _arguments \
                                        '(--template -t)'{--template,-t}'[Template name]:template:_ralph_templates' \
                                        '--title[Task title]:title:' \
                                        '*--var[Additional template variables]:variable:'
                                    ;;
                            esac
                            ;;
                    esac
                    ;;
                convert)
                    _arguments \
                        '--infer-groups[Infer parallel groups from task titles]' \
                        '1:input_file:_files' \
                        '2:output_file:_files'
                    ;;
                completion)
                    _arguments \
                        '1:shell:(bash zsh)'
                    ;;
            esac
            ;;
    esac
}

# Helper function to complete snapshot names
_ralph_snapshots() {
    local -a snapshots
    snapshots=(${(f)"$(ralph snapshot --list 2>/dev/null | grep -E '^\s+\*' | awk '{print $2}')"})
    _describe 'snapshots' snapshots
}

# Helper function to complete template names
_ralph_templates() {
    local -a templates
    templates=(${(f)"$(ralph task templates 2>/dev/null | grep -E '^\s+\*' | awk '{print $2}')"})
    _describe 'templates' templates
}

_ralph "$@"
"""
    return script


def get_dynamic_completions(
    project_root: Path, cfg: Config, completion_type: str, partial: str = ""
) -> list[str]:
    """Get dynamic completion values based on current configuration.

    This function provides context-aware completions for values that depend
    on the current project configuration or state.

    Args:
        project_root: Root directory of the Ralph project
        cfg: Loaded Ralph configuration
        completion_type: Type of completion requested (e.g., 'agents', 'templates', 'snapshots')
        partial: Partial string to filter completions (optional)

    Returns:
        List of completion values matching the partial string

    Examples:
        >>> completions = get_dynamic_completions(Path('/project'), cfg, 'agents', 'co')
        >>> assert 'codex' in completions
    """
    completions: list[str] = []

    if completion_type == "agents":
        # Get configured agent names
        # Default agents
        completions = ["codex", "claude", "claude-zai", "claude-kimi", "copilot"]

        # Add custom runners from config if available
        if hasattr(cfg, "runners") and cfg.runners:
            for runner_name in cfg.runners.keys():
                if runner_name not in completions:
                    completions.append(runner_name)

    elif completion_type == "templates":
        # Get available template names
        try:
            from .templates import list_templates

            templates = list_templates(project_root)
            completions = [t.name for t in templates]
        except (ImportError, OSError) as e:
            logger.debug("Failed to load templates: %s", e)
            completions = ["bug-fix", "feature", "refactor"]

    elif completion_type == "snapshots":
        # Get available snapshot names
        try:
            from .snapshots import list_snapshots

            snapshots = list_snapshots(project_root)
            completions = [s.name for s in snapshots]
        except (ImportError, OSError) as e:
            logger.debug("Failed to load snapshots: %s", e)
            return []

    elif completion_type == "formats":
        # Output formats
        completions = ["text", "json"]

    elif completion_type == "tracker_formats":
        # Tracker formats for init command
        completions = ["markdown", "json", "yaml"]

    # Filter by partial string if provided
    if partial:
        completions = [c for c in completions if c.startswith(partial)]

    return sorted(completions)
