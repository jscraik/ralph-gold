# Ralph Gold - Project Setup

This directory contains your Ralph Loop configuration and state.

## Files

### Configuration Files (edit these)

- **`ralph.toml`** - Main configuration
  - Loop settings (max iterations, no-progress limits)
  - File paths
  - Runner commands for different agents (codex, claude, copilot)
  - Optional quality gates

- **`PROMPT.md`** - Loop instructions
  - Main prompt given to the agent each iteration
  - Guardrails and constraints
  - Exit signal instructions

- **`AGENTS.md`** - Project-specific instructions
  - How to build/test/run YOUR project
  - Stack-specific commands
  - Project conventions

- **`prd.json`** or **`PRD.md`** - Your task list
  - JSON format: stories with id, title, description, acceptance criteria
  - Markdown format: checkbox tasks for VS Code/Copilot workflows
  - Choose one format and configure in `ralph.toml`

### State Files (auto-managed)

- **`progress.md`** - Append-only memory
  - Records what happened each iteration
  - Agents read this to understand context

- **`logs/`** - Iteration logs
  - One log file per iteration
  - Contains full agent output and metadata

## Quick Start

1. Edit `AGENTS.md` to match your project's build/test commands
2. Edit your PRD (JSON or Markdown) with your tasks
3. Run: `ralph run --agent codex`

## Commands

```bash
# Run the loop
ralph run --agent codex --max-iterations 10

# Single iteration
ralph step --agent claude

# Check status
ralph status

# Generate/update PRD
ralph plan --agent codex --desc "Build a REST API with tests"

# Check prerequisites
ralph doctor
```

## How It Works

1. Ralph reads the next incomplete task from your PRD
2. Builds a prompt combining PROMPT.md + AGENTS.md + progress.md + current task
3. Runs your chosen agent CLI (codex/claude/copilot)
4. Updates progress.md and PRD based on agent output
5. Repeats until all tasks are done or max iterations reached

## Exit Conditions

The loop stops when:

- All tasks are marked done/passing, AND
- Agent prints `EXIT_SIGNAL: true`

This dual gate prevents premature exits.

## Customization

- Add custom runners in `ralph.toml` under `[runners.myagent]`
- Add quality gates (tests, lints) in `[gates]` section
- Adjust rate limiting and sleep timers in `[loop]` section

## Learn More

- Main repo: <https://github.com/jscraik/ralph-gold>
- VS Code extension: `vscode/ralph-bridge/`
- Protocol docs: `docs/VSCODE_BRIDGE_PROTOCOL.md`
