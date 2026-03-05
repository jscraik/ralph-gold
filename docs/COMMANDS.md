---
last_validated: 2026-03-05
---

# Commands Reference

**Version:** 1.1
**Last Updated:** 2026-03-05
**Review Cadence:** Quarterly
**Audience:** Users

---

## Table of Contents

- [Overview](#overview)
- [Quick Reference](#quick-reference)
- [Setup Commands](#setup-commands)
- [Execution Commands](#execution-commands)
- [Global Options](#global-options)
- [Exit Codes Summary](#exit-codes-summary)
- [Environment Variables](#environment-variables)
- [Related Documentation](#related-documentation)

## Overview

Ralph-gold provides a comprehensive CLI for managing the development loop. This document provides a complete reference for all commands.

Simple vs expert usage posture:

- **Simple mode (default guidance):** Start with `init`, `step`, `run`, and `status`.
- **Expert mode (full surface):** Use advanced commands and flags as needed.

See `docs/SIMPLE_EXPERT_MODE.md` for policy and rollout details.

Machine-readable output contract:

- Use global `--format json` (or `RALPH_FORMAT=json`) for script/agent-safe output.
- JSON command envelopes are versioned with `schema_version: "ralph.cli.v1"`.
- Standard top-level fields are: `schema_version`, `cmd`, `exit_code`, `timestamp`.

---

`★ Insight ─────────────────────────────────────`
**Command Organization:**
1. **Setup commands** - `init`, `doctor`, `diagnose` for getting started
2. **Execution commands** - `run`, `step`, `resume` for running the loop
3. **Visibility commands** - `status`, `stats`, `tui` for monitoring
4. **Management commands** - `task`, `specs`, `state`, `snapshot`, `harness` for management
`─────────────────────────────────────────────────`

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `ralph init` | Initialize Ralph in a project |
| `ralph quickstart` | Initialize with recommended defaults |
| `ralph doctor` | Check local prerequisites |
| `ralph diagnose` | Run diagnostics on config and PRD |
| `ralph run` | Run the loop for N iterations |
| `ralph step` | Run exactly one iteration |
| `ralph resume` | Resume interrupted iterations |
| `ralph status` | Show PRD progress and last iteration |
| `ralph explain` | Explain task selection, blockers, and next actions |
| `ralph stats` | Display iteration statistics |
| `ralph harness` | Collect/evaluate/report harness artifacts |
| `ralph tui` | Interactive control surface |
| `ralph task` | Manage tasks in the PRD |
| `ralph specs` | Work with specs directory |
| `ralph snapshot` | Create/list git snapshots |
| `ralph rollback` | Rollback to a snapshot |
| `ralph watch` | Watch files and run gates automatically |
| `ralph clean` | Clean old logs and artifacts |
| `ralph state` | State management commands |
| `ralph sync` | Reconcile state.json with PRD |
| `ralph interventions` | View intervention recommendations |
| `ralph completion` | Generate shell completion scripts |
| `ralph convert` | Convert PRD between formats |
| `ralph bridge` | VS Code JSON-RPC bridge |
| `ralph serve` | HTTP health endpoint |

---

## Setup Commands

### `ralph init`

Initialize Ralph files in the current repository.

```bash
ralph init [--force] [--format FORMAT]
```

**Options:**
- `--force`: Archive existing `.ralph/` and reinitialize
- `--format`: Tracker format (`markdown` or `yaml`, default: `markdown`)

**Creates:**
- `.ralph/ralph.toml` - Configuration file
- `.ralph/PRD.md` - Task tracker (or JSON/YAML based on format)
- `.ralph/AGENTS.md` - Repo-specific commands
- `.ralph/progress.md` - Progress log
- `.ralph/PROMPT_*.md` - Prompt templates
- `.ralph/specs/` - Specs directory
- `.ralph/templates/` - Custom templates directory

**Re-initialization:**
- Normal `init`: Merges config with existing (preserves user settings)
- `init --force`: Archives existing `.ralph/` to `.ralph/archive/<timestamp>/` and creates fresh templates

**See also:** `docs/INIT_ARCHIVING.md`

---

### `ralph quickstart`

Initialize Ralph with recommended defaults and print the next commands to run.

```bash
ralph quickstart [--profile simple|expert] [--agent codex] [--interactive] [--force]
```

**Options:**
- `--profile`: UX posture preset (`simple` or `expert`, default: `simple`)
- `--agent`: Recommended agent shown in next-step guidance (default: `codex`)
- `--interactive`: Prompt for profile and preferred agent
- `--force`: Archive existing `.ralph/` files before reinitializing
- `--format`: Tracker format (`markdown` or `yaml`)
- `--solo`: Use solo-dev optimized defaults

**Behavior:**
- Runs the same scaffold initialization flow as `ralph init`
- Applies `ux.mode` policy metadata in `.ralph/ralph.toml`
- Prints a recommended first iteration command and status check

**Example:**
```bash
ralph quickstart --profile expert --agent claude --interactive
```

---

### `ralph doctor`

Check local prerequisites for running Ralph.

```bash
ralph doctor [--github]
```

**Options:**
- `--github`: Include GitHub authentication checks

**Checks:**
- Git installation and version
- Python/uv installation
- Agent CLI availability (codex, claude, copilot)
- Optional: GitHub CLI authentication

**Exit codes:**
- `0`: All checks passed
- `1`: One or more checks failed

**Example output:**
```
============================================================
Ralph Prerequisites Check
============================================================

✓ git 2.39.0 installed
✓ uv 0.1.0 installed
✓ Python 3.12.0 installed

Agent CLIs:
  ✗ codex not found (install with: uv tool install codex-cli)
  ✓ claude available
  ✗ copilot not found (install with: gh extension install github/gh-copilot)

============================================================
Summary: 3/5 checks passed
============================================================
```

---

### `ralph diagnose`

Run diagnostic checks on Ralph configuration and PRD.

```bash
ralph diagnose [--test-gates]
```

**Options:**
- `--test-gates`: Test each gate command individually

**Validates:**
- Configuration file existence and syntax
- Configuration schema validity
- PRD file existence and format
- PRD structure validation
- (Optional) Gate command execution

**Exit codes:**
- `0`: All diagnostics passed
- `2`: Issues found (errors or warnings)

**Example output:**
```
============================================================
Ralph Diagnostics Report
============================================================

PASSED:
  ✓ Configuration file found
  ✓ Configuration file ralph.toml has valid TOML syntax
  ✓ Configuration schema is valid
  ✓ Found 2 configured runner(s)
  ✓ PRD file found: PRD.md
  ✓ PRD file has valid markdown format
  ✓ PRD structure is valid (3/10 tasks complete)

============================================================
Summary: 7/7 checks passed
✓ All diagnostics passed!
```

---

## Execution Commands

### `ralph run`

Run the loop for N iterations.

```bash
ralph run --agent AGENT [OPTIONS]
```

**Options:**
- `--agent AGENT`: Agent to use (`codex`, `claude`, `copilot`, custom)
- `--max-iterations N`: Maximum iterations to run (default: from config)
- `--mode MODE`: Loop mode (`speed`, `quality`, `exploration`)
- `--prompt-file PATH`: Custom prompt file
- `--prd-file PATH`: Custom PRD file
- `--parallel`: Enable parallel execution
- `--dry-run`: Simulate without running agents
- `--stream`: Stream runner output live during execution (sequential runs only; ignored with `--parallel`)
- `--format FORMAT`: Output format (`text`, `json`)

**Exit codes:**
- `0`: Loop completed successfully
- `1`: Loop ended without successful exit (max iterations, no-progress)
- `2`: One or more iterations failed

**Examples:**
```bash
# Run with default settings
ralph run --agent codex

# Run 20 iterations
ralph run --agent claude --max-iterations 20

# Run in quality mode
ralph run --agent codex --mode quality

# Stream iteration output while running
ralph run --agent codex --stream

# Dry run to see what would happen
ralph run --agent codex --dry-run
```

---

### `ralph supervise`

Run a long-lived supervisor loop (heartbeat + policy stops + OS notifications by default).

```bash
ralph supervise --agent AGENT [OPTIONS]
```

**Options:**
- `--agent AGENT`: Agent to use for execution iterations (default: `codex`)
- `--mode MODE`: Loop mode (`speed`, `quality`, `exploration`)
- `--max-runtime-seconds N`: Stop after N seconds (0/unset = unlimited)
- `--heartbeat-seconds N`: Print heartbeat every N seconds
- `--sleep-seconds-between-runs N`: Sleep between iterations
- `--on-no-progress-limit stop|continue`: Policy when no-progress limit is hit
- `--on-rate-limit wait|stop`: Policy when rate limit is hit
- `--notify/--no-notify`: Enable/disable OS notifications
- `--notify-backend auto|macos|linux|windows|command|none`: Notification backend
- `--notify-command ...`: Command argv when backend is `command` (appends title + message)

**Exit codes:**
- `0`: Completed successfully
- `1`: Stopped/incomplete (policy stop)
- `2`: Error

**Example:**
```bash
ralph supervise --agent codex
```

---

### `ralph step`

Run exactly one iteration.

```bash
ralph step --agent AGENT [OPTIONS]
```

**Options:**
- `--agent AGENT`: Agent to use
- `--interactive`: Interactive task selection
- `--task-id TASK_ID`: Run a specific task directly
- `--allow-done-target`: Allow running a task marked done
- `--allow-blocked-target`: Allow running a task marked blocked
- `--reopen-target`: Attempt to reopen the target task first
- `--prompt-file PATH`: Custom prompt file
- `--prd-file PATH`: Custom PRD file
- `--dry-run`: Simulate without running agents
- `--format FORMAT`: Output format

**Interactive mode:**
- Press `s <keyword>` to search/filter tasks
- Press `d <number>` to view task details
- Press `c` to clear search filter
- Press `q` to quit without selecting

**Exit codes:**
- `0`: Iteration completed
- `1`: Iteration failed
- `2`: Task is blocked

**Examples:**
```bash
# Run one iteration
ralph step --agent codex

# Interactive task selection
ralph step --interactive

# Explicit target task
ralph step --task-id 42
```

---

### `ralph resume`

Detect and resume interrupted iterations.

```bash
ralph resume [OPTIONS]
```

**Options:**
- `--auto`: Resume automatically without prompting
- `--clear`: Clear interrupted state without resuming

**Behavior:**
- Detects interrupted iterations from state.json
- Offers to resume from last safe point
- Useful after crashes or interruptions

**Example:**
```bash
ralph resume --auto
```

---

## Visibility Commands

Visibility defaults:
- `status` is the state snapshot
- `explain` is the reasoning snapshot ("why this task / why blocked / what next")

### `ralph status`

Show PRD progress and last iteration summary.

```bash
ralph status [OPTIONS]
```

**Options:**
- `--detailed`: Show detailed metrics (velocity, ETA)
- `--chart`: Show ASCII burndown chart
- `--graph`: Show task dependency graph
- `--format FORMAT`: Output format

**Output includes:**
- Task completion progress
- Current task
- Last iteration summary
- (Optional) Velocity and ETA
- (Optional) Burndown chart
- (Optional) Dependency graph

**Examples:**
```bash
# Basic status
ralph status

# Detailed with velocity
ralph status --detailed

# Dependency graph
ralph status --graph
```

---

### `ralph explain`

Explain why Ralph picked the next task, summarize blocker context, and suggest next commands.

```bash
ralph explain [--agent AGENT]
```

**Options:**
- `--agent AGENT`: Agent name used in suggested next-step commands (default: `codex`)

**Output includes:**
- Why the next task was selected
- Blocked/dependency-wait summary
- Suggested next commands

**Examples:**
```bash
# Explain current loop context
ralph explain

# Suggest next steps using a preferred agent label
ralph explain --agent claude
```

---

### `ralph stats`

Display iteration statistics from Ralph history.

```bash
ralph stats [OPTIONS]
```

**Options:**
- `--by-task`: Show per-task breakdown
- `--export PATH`: Export to CSV file

**Output includes:**
- Total iterations (successful and failed)
- Success rate
- Duration statistics (average, min, max)
- (Optional) Per-task breakdown

**Examples:**
```bash
# Overall statistics
ralph stats

# Per-task breakdown
ralph stats --by-task

# Export for analysis
ralph stats --export stats.csv
```

---

### `ralph harness`

Collect, evaluate, and report harness artifacts for regression tracking.

```bash
ralph harness <collect|run|report|doctor> [OPTIONS]
```

**Subcommands:**
- `collect`: Build a dataset from `.ralph/state.json` and receipts
- `run`: Evaluate dataset and produce aggregate quality metrics (historical or live)
- `report`: Render run output as text, JSON, or CSV
- `doctor`: Validate harness config and artifact schemas

**Examples:**
```bash
# Build dataset
ralph harness collect --days 30 --limit 200

# Evaluate dataset and save run output
ralph harness run --dataset .ralph/harness/cases.json

# Live execution against explicit task IDs from the dataset
ralph harness run --dataset .ralph/harness/cases.json --execution-mode live --strict-targeting

# Report latest run in CSV format
ralph harness report --format csv
```

---

### `ralph tui`

Interactive control surface (TUI).

```bash
ralph tui
```

**Key bindings:**
- `s`: Step once
- `r`: Run `loop.max_iterations` iterations
- `a`: Cycle agent
- `p`: Pause/resume
- `q`: Quit

**Features:**
- Real-time status display
- Keyboard-driven control
- Agent cycling
- Pause/resume support

---

## Management Commands

### `ralph task`

Manage tasks in the PRD.

```bash
ralph task <subcommand> [OPTIONS]
```

**Subcommands:**
- `ralph task add`: Add a new task
- `ralph task templates`: List available templates

**`ralph task add`:**
```bash
ralph task add --template TEMPLATE --title TITLE [OPTIONS]
```

Options:
- `--template TEMPLATE`: Template to use
- `--title TITLE`: Task title
- `--var KEY=VALUE`: Template variables

**`ralph task templates`:**
```bash
ralph task templates
```

Lists built-in and custom templates with descriptions.

**Examples:**
```bash
# Add bug fix task
ralph task add --template bug-fix --title "Login fails on Safari"

# List templates
ralph task templates

# Add with custom variables
ralph task add --template api-endpoint --title "Create user endpoint" --var component=auth
```

---

### `ralph specs`

Work with specs directory.

```bash
ralph specs <subcommand> [OPTIONS]
```

**Subcommands:**
- `ralph specs check`: Check spec files against limits

**`ralph specs check`:**
```bash
ralph specs check [--strict]
```

Options:
- `--strict`: Fail on warnings (not just errors)

**Validates:**
- Spec file count (default max: 20)
- Total character count (default max: 50000)
- Single file size (default max: 10000)
- File naming conventions

**Exit codes:**
- `0`: All checks passed
- `2`: Issues found

**Examples:**
```bash
# Check specs
ralph specs check

# Strict mode (warnings as errors)
ralph specs check --strict
```

---

### `ralph state`

State management commands.

```bash
ralph state <subcommand> [OPTIONS]
```

**Subcommands:**
- `ralph state cleanup`: Clean stale task IDs from state

**`ralph state cleanup`:**
```bash
ralph state cleanup [OPTIONS]
```

Options:
- `--dry-run`: Show what would be removed without removing
- `--force`: Remove without confirmation

**Behavior:**
- Removes task IDs that no longer exist in PRD
- Respects `state.protect_current_task` and `state.protect_recent_hours`
- Requires confirmation unless `--force` is used

**Examples:**
```bash
# Dry run to see what would be cleaned
ralph state cleanup --dry-run

# Force cleanup without prompts
ralph state cleanup --force
```

---

### `ralph sync`

Reconcile state.json with PRD to fix inconsistent task states.

```bash
ralph sync [OPTIONS]
```

**Options:**
- `--dry-run`: Show what would change without making changes
- `--force`: Make changes without confirmation

**Behavior:**
- Compares task states between state.json and PRD
- Identifies tasks marked complete in PRD but not in state (and vice versa)
- Optionally syncs blocked states based on PRD dependencies
- Updates state.json to match PRD reality

**When to use:**
- After manual PRD edits
- When tasks show incorrect status
- After importing/merging PRD changes
- To fix "false blocked" task states

**Examples:**
```bash
# Preview what would change
ralph sync --dry-run

# Sync state with PRD
ralph sync

# Force sync without prompts
ralph sync --force
```

---

### `ralph interventions`

View intervention recommendations from the adaptive intervention engine.

```bash
ralph interventions [OPTIONS]
```

**Options:**
- `--latest`: Show only the latest recommendation
- `--all`: Show all recommendations
- `--json`: Output as JSON

**Behavior:**
- Displays recommendations generated from failure pattern analysis
- Shows category, confidence, rationale, and suggested actions
- Includes prompt patches, timeout hints, and mode hints

**Recommendation Categories:**
- `no_files_reinforcement`: Agent not writing files
- `gate_failure_pattern`: Repeated gate failures
- `timeout_churn`: Repeated timeouts
- `low_evidence_completion`: Complete but no evidence
- `syntax_error_pattern`: Repeated syntax errors

**Configuration:**
Enable in `.ralph/ralph.toml`:
```toml
[interventions]
enabled = true
policy_mode = "recommend-only"
lookback_iterations = 30
confidence_threshold = "medium"
```

**Examples:**
```bash
# View latest recommendation
ralph interventions --latest

# View all recommendations
ralph interventions --all

# JSON output for scripting
ralph interventions --json
```

---

### `ralph snapshot`

Create or list git-based snapshots for safe rollback.

```bash
ralph snapshot <name> [OPTIONS]
ralph snapshot --list
```

**Create snapshot:**
```bash
ralph snapshot <name> [--description DESC]
```

Options:
- `--description DESC`: Snapshot description
- `--list`: List all snapshots instead of creating

**List snapshots:**
```bash
ralph snapshot --list
```

**What gets snapshotted:**
- Git working tree state (via `git stash`)
- Ralph state.json backup
- Metadata in `snapshots/<name>/metadata.json`

**Examples:**
```bash
# Create snapshot
ralph snapshot before-refactor --description "Before major refactoring"

# List all snapshots
ralph snapshot --list

# View snapshot metadata
cat .ralph/snapshots/before-refactor/metadata.json | jq .
```

---

### `ralph rollback`

Rollback to a previous snapshot.

```bash
ralph rollback <name> [--force]
```

**Options:**
- `--force`: Skip confirmation prompt

**What gets restored:**
- Git working tree from stash
- Ralph state from backup

**Behavior:**
- Requires clean working tree (unless `--force`)
- Prompts for confirmation (unless `--force`)
- Restores both git state and Ralph state

**Examples:**
```bash
# Rollback with confirmation
ralph rollback before-refactor

# Force rollback without prompt
ralph rollback before-refactor --force
```

---

### `ralph watch`

Watch files and automatically run gates on changes.

```bash
ralph watch [OPTIONS]
```

**Options:**
- `--auto-commit`: Auto-commit changes when gates pass

**Configuration:**
Requires `watch.enabled = true` in `.ralph/ralph.toml`:

```toml
[watch]
enabled = true
patterns = ["**/*.py", "**/*.md"]
debounce_ms = 500
auto_commit = false
```

**Behavior:**
- Monitors files matching configured patterns
- Runs gates when files change (after debounce)
- Shows real-time gate results
- Optionally auto-commits when gates pass

**Exit:** Ctrl+C to stop

**Examples:**
```bash
# Watch mode (gates only)
ralph watch

# Auto-commit when gates pass
ralph watch --auto-commit
```

---

### `ralph clean`

Clean old logs, archives, and other workspace artifacts.

```bash
ralph clean [OPTIONS]
```

**Options:**
- `--dry-run`: Show what would be removed without removing
- `--logs-days N`: Remove logs older than N days
- `--archives-days N`: Remove archives older than N days
- `--receipts-days N`: Remove receipts older than N days
- `--context-days N`: Remove context files older than N days

**Examples:**
```bash
# Clean with defaults
ralph clean

# Dry run
ralph clean --dry-run

# Adjust thresholds
ralph clean --logs-days 7 --archives-days 30
```

---

## Utility Commands

### `ralph completion`

Generate shell completion scripts.

```bash
ralph completion <shell> > <file>
```

**Shells:**
- `bash`: Bash completion
- `zsh`: Zsh completion

**Installation:**

**Bash:**
```bash
# Generate and install
ralph completion bash > ~/.ralph-completion.sh
echo "source ~/.ralph-completion.sh" >> ~/.bashrc
source ~/.bashrc

# System-wide
sudo ralph completion bash > /etc/bash_completion.d/ralph
```

**Zsh:**
```bash
# Create completion directory
mkdir -p ~/.zsh/completion

# Generate and install
ralph completion zsh > ~/.zsh/completion/_ralph

# Add to ~/.zshrc if not present
echo "fpath=(~/.zsh/completion \$fpath)" >> ~/.zshrc
echo "autoload -Uz compinit && compinit" >> ~/.zshrc

# Reload
source ~/.zshrc
```

---

### `ralph convert`

Convert PRD files between formats.

```bash
ralph convert <input> <output>
```

**Supported conversions:**
- Markdown → YAML
- JSON → YAML
- YAML → Markdown (planned)

**Examples:**
```bash
# Convert Markdown to YAML
ralph convert .ralph/PRD.md .ralph/tasks.yaml

# Convert JSON to YAML
ralph convert .ralph/prd.json .ralph/tasks.yaml
```

---

### `ralph plan`

Generate/update PRD from a description.

```bash
ralph plan --desc "Description" [OPTIONS]
```

**Options:**
- `--desc DESC`: Task description (required)
- `--agent AGENT`: Agent to use (default: from config)
- `--prd-file PATH`: Custom PRD file

**Behavior:**
- Runs the agent once with the description
- Agent generates/updates the PRD
- Useful for initial project planning

**Example:**
```bash
ralph plan --desc "Build a REST API for user authentication with JWT tokens"
```

---

### `ralph regen-plan`

Regenerate IMPLEMENTATION_PLAN.md from specs and codebase gap analysis.

```bash
ralph regen-plan [OPTIONS]
```

**Options:**
- `--agent AGENT`: Agent to use (default: from config)
- `--prd-file PATH`: Custom PRD file

**Behavior:**
- Analyzes specs in `.ralph/specs/`
- Performs codebase gap analysis
- Regenerates implementation plan

---

### `ralph bridge`

Start a JSON-RPC bridge over stdio (for VS Code).

```bash
ralph bridge
```

**Purpose:**
- Provides JSON-RPC interface for VS Code extension
- Enables real-time status updates and control
- Used by `vscode/ralph-bridge/` extension

**See also:** `docs/VSCODE_BRIDGE_PROTOCOL.md`

---

### `ralph serve`

Serve a minimal HTTP health endpoint.

```bash
ralph serve [OPTIONS]
```

**Options:**
- `--port PORT`: Port to listen on (default: 8080)
- `--host HOST`: Host to bind to (default: 127.0.0.1)

**Endpoint:**
- `GET /health`: Returns health status

**Example output:**
```json
{
  "status": "healthy",
  "version": "0.8.2",
  "uptime": 12345
}
```

---

## Global Options

These options work with all commands:

| Option | Description |
|--------|-------------|
| `--help` | Show command help and exit |
| `--version` | Show version and exit |
| `--format FORMAT` | Output format (`text`, `json`) |
| `--verbosity LEVEL` | Output verbosity (`quiet`, `normal`, `verbose`) |

---

## Exit Codes Summary

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Failure / Incomplete |
| `2` | Validation errors / Issues found |

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `RALPH_CONFIG` | Path to override config file |
| `RALPH_FORMAT` | Default output format when global `--format` is not supplied |
| `RALPH_VERBOSITY` | Default verbosity when global `--verbosity` is not supplied |
| `GITHUB_TOKEN` | GitHub authentication token |
| `RALPH_DEBUG` | Enable debug logging (set to `1`) |
| `RALPH_DISABLE_SECRET_SCAN` | Disable gitleaks secret scanning |

---

## Related Documentation

- **Configuration:** `docs/CONFIGURATION.md` - All configuration options
- **Troubleshooting:** `docs/TROUBLESHOOTING.md` - Common issues and solutions
- **Project Structure:** `docs/PROJECT_STRUCTURE.md` - Directory layout
- **Authorization:** `docs/AUTHORIZATION.md` - Permission system

---

**Document Owner:** maintainers
**Next Review:** 2026-04-20
**Change Log:**
- 2026-01-20: Initial version (v1.0)
- 2026-03-05: Added v1.1 updates for quickstart/explain posture, global output controls, and JSON envelope guidance.
