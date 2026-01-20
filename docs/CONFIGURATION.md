# Configuration Reference

**Version:** 1.0
**Last Updated:** 2026-01-20
**Review Cadence:** Quarterly
**Audience:** Users configuring ralph-gold

---

## Overview

Ralph-gold is configured via `.ralph/ralph.toml` in your project root. Configuration uses TOML format and is organized into sections.

### Configuration File Priority

Configuration is loaded in this order (later files override earlier ones):

1. `.ralph/ralph.toml` (project-local, preferred)
2. `ralph.toml` (project root override)
3. `$RALPH_CONFIG` environment variable (absolute path)

All configuration files are merged (deep merge) with later values taking precedence.

---

`★ Insight ─────────────────────────────────────`
**Configuration Architecture:**
1. **Frozen dataclasses** - All config is immutable after loading
2. **Validation on load** - Invalid values raise `ValueError` immediately
3. **Safe defaults** - All options have reasonable defaults
4. **Auto-resolution** - Common filename variations are handled automatically
`─────────────────────────────────────────────────`

---

## Quick Reference

| Section | Purpose | Required |
|---------|---------|----------|
| `[loop]` | Iteration control and timeouts | No |
| `[files]` | Path configuration for Ralph files | No |
| `[runners.*]` | Agent runner configuration | No |
| `[gates]` | Test/validation gates | No |
| `[git]` | Branch and commit automation | No |
| `[tracker]` | Task tracker (Markdown/YAML/GitHub) | No |
| `[parallel]` | Parallel execution settings | No |
| `[authorization]` | File write permissions | No |
| `[watch]` | File watching and auto-gates | No |
| `[output]` | Verbosity and format control | No |
| `[state]` | State validation and cleanup | No |
| `[init]` | Re-initialization behavior | No |

---

## Complete Reference

### `[loop]` - Loop Control

Controls iteration behavior, timeouts, and execution limits.

```toml
[loop]
mode = "speed"                      # speed|quality|exploration
max_iterations = 10                 # Max iterations per run (1-1000)
no_progress_limit = 3               # Stop after N iterations without progress
rate_limit_per_hour = 0             # Max iterations per hour (0=disabled)
sleep_seconds_between_iters = 0     # Sleep between iterations
runner_timeout_seconds = 900        # Agent timeout in seconds (1-86400)
max_attempts_per_task = 3           # Max attempts per task (1-100)
skip_blocked_tasks = true           # Skip tasks with unmet dependencies

# Mode-specific overrides (optional)
[loop.modes.speed]
max_iterations = 20
runner_timeout_seconds = 600

[loop.modes.quality]
max_iterations = 5
runner_timeout_seconds = 1800

[loop.modes.exploration]
max_iterations = 50
runner_timeout_seconds = 1200
```

**Settings:**

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| `mode` | string | `"speed"` | speed/quality/exploration | Active loop mode |
| `max_iterations` | int | `10` | 1-1000 | Maximum iterations before exit |
| `no_progress_limit` | int | `3` | 1-100 | Stop after N iterations without task completion |
| `rate_limit_per_hour` | int | `0` | 0-1000 | Rate limit (0 = disabled) |
| `sleep_seconds_between_iters` | int | `0` | 0-3600 | Delay between iterations |
| `runner_timeout_seconds` | int | `900` | 1-86400 | Agent timeout (15 min default) |
| `max_attempts_per_task` | int | `3` | 1-100 | Maximum retry attempts per task |
| `skip_blocked_tasks` | bool | `true` | - | Automatically skip tasks with unmet dependencies |

**Loop Modes:**

- **speed**: Fast iterations, shorter timeouts (default)
- **quality**: Fewer iterations, longer timeouts for careful work
- **exploration**: Many iterations, balanced timeouts

---

### `[files]` - File Paths

Paths to Ralph's durable memory files. All paths are relative to project root.

```toml
[files]
prd = ".ralph/PRD.md"
progress = ".ralph/progress.md"
prompt = ".ralph/PROMPT_build.md"
plan = ".ralph/PROMPT_plan.md"
judge = ".ralph/PROMPT_judge.md"
review = ".ralph/PROMPT_review.md"
agents = ".ralph/AGENTS.md"
specs_dir = ".ralph/specs"
feedback = ".ralph/FEEDBACK.md"
```

**Settings:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `prd` | string | `.ralph/PRD.md` | Task tracker file |
| `progress` | string | `.ralph/progress.md` | Append-only progress log |
| `prompt` | string | `.ralph/PROMPT_build.md` | Build prompt template |
| `plan` | string | `.ralph/PROMPT_plan.md` | Planning prompt template |
| `judge` | string | `.ralph/PROMPT_judge.md` | Judge prompt template |
| `review` | string | `.ralph/PROMPT_review.md` | Review prompt template |
| `agents` | string | `.ralph/AGENTS.md` | Agent instructions |
| `specs_dir` | string | `.ralph/specs` | Specification files directory |
| `feedback` | string | `.ralph/FEEDBACK.md` | Operator feedback file |

**Note:** Ralph automatically resolves common filename variations (e.g., `PRD.md` → `.ralph/PRD.md`).

---

### `[runners.*]` - Agent Runners

Configuration for CLI agents (Codex, Claude, Copilot, or custom).

```toml
[runners.codex]
argv = ["codex", "exec", "--full-auto", "-"]

[runners.claude]
argv = ["claude", "-p"]

[runners.copilot]
argv = ["gh", "copilot", "suggest", "--type", "shell", "--prompt"]

[runners.custom]
argv = ["my-agent-wrapper", "--stdin"]
```

**Prompt Transport:**

- **Codex**: Use `-` to read prompt from stdin
- **Claude**: Use `-p` flag (prompt inserted after)
- **Copilot**: Use `--prompt` flag
- **Custom**: Use `{prompt}` placeholder or `-` for stdin

---

### `[gates]` - Test/Validation Gates

Commands that must pass before an iteration is considered successful.

```toml
[gates]
commands = [
    "uv run pytest -q",
    "uv run ruff check .",
]

# LLM judge gate (optional)
[gates.llm_judge]
enabled = false
agent = "claude"
prompt = ".ralph/PROMPT_judge.md"
max_diff_chars = 30000

# Review gate (optional)
[gates.review]
enabled = false
backend = "runner"              # runner|repoprompt
agent = "claude"
prompt = ".ralph/PROMPT_review.md"
max_diff_chars = 30000
required_token = "SHIP"

# Prek gate (optional)
[gates.prek]
enabled = false
argv = ["prek", "run", "--all-files"]

# Smart gates (optional)
[gates.smart]
enabled = false
skip_gates_for = ["setup", "documentation"]

# General settings
precommit_hook = false
fail_fast = true
output_mode = "summary"          # full|summary|errors_only
max_output_lines = 50
```

**Settings:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `commands` | array | `[]` | Gate commands to run |
| `llm_judge.enabled` | bool | `false` | Enable LLM judge gate |
| `llm_judge.agent` | string | `"claude"` | Agent for LLM judge |
| `llm_judge.max_diff_chars` | int | `30000` | Max diff size for judge |
| `review.enabled` | bool | `false` | Enable review gate |
| `review.backend` | string | `"runner"` | Backend: runner or repoprompt |
| `review.required_token` | string | `"SHIP"` | Token required for success |
| `prek.enabled` | bool | `false` | Enable prek gate |
| `smart.enabled` | bool | `false` | Enable smart gate skipping |
| `smart.skip_gates_for` | array | `[]` | Skip gates for these tasks |
| `precommit_hook` | bool | `false` | Install as git pre-commit hook |
| `fail_fast` | bool | `true` | Stop on first gate failure |
| `output_mode` | string | `"summary"` | Gate output verbosity |
| `max_output_lines` | int | `50` | Max lines per gate |

---

### `[git]` - Git Automation

Branch and commit automation settings.

```toml
[git]
branch_strategy = "none"         # none|per_prd|task
base_branch = ""                 # Empty = current HEAD
branch_prefix = "ralph/"
auto_commit = false
commit_message_template = "ralph: {story_id} {title}"
amend_if_needed = true
```

**Settings:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `branch_strategy` | string | `"none"` | Branch automation: none/per_prd/task |
| `base_branch` | string | `""` | Base branch for PRD branches |
| `branch_prefix` | string | `"ralph/"` | Prefix for auto-created branches |
| `auto_commit` | bool | `false` | Auto-commit after successful iterations |
| `commit_message_template` | string | `ralph: {story_id} {title}` | Commit message template |
| `amend_if_needed` | bool | `true` | Amend previous commit if needed |

**Branch Strategies:**

- **none**: No automatic branch management
- **per_prd**: Create one branch per PRD/project
- **task**: Create one branch per task (not fully implemented)

---

### `[tracker]` - Task Tracker

Configuration for task tracking (Markdown, YAML, GitHub Issues, or custom).

```toml
[tracker]
kind = "auto"                    # auto|markdown|yaml|github_issues
plugin = ""                      # Optional: module:callable

# GitHub Issues tracker
[tracker.github]
repo = "owner/repo"
auth_method = "gh_cli"           # gh_cli|token
token_env = "GITHUB_TOKEN"
label_filter = "ready"
exclude_labels = ["blocked"]
close_on_done = true
comment_on_done = true
add_labels_on_start = ["in-progress"]
add_labels_on_done = ["completed"]
cache_ttl_seconds = 300
```

**Settings:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `kind` | string | `"auto"` | Tracker type |
| `plugin` | string | `""` | Custom tracker plugin |
| `github.repo` | string | `""` | GitHub repository (owner/repo) |
| `github.auth_method` | string | `"gh_cli"` | Auth: gh_cli or token |
| `github.token_env` | string | `"GITHUB_TOKEN"` | Token environment variable |
| `github.label_filter` | string | `"ready"` | Label for ready tasks |
| `github.exclude_labels` | array | `["blocked"]` | Labels to exclude |
| `github.close_on_done` | bool | `true` | Close issues when done |
| `github.cache_ttl_seconds` | int | `300` | Cache TTL for GitHub API |

---

### `[parallel]` - Parallel Execution

Settings for parallel task execution with git worktrees.

```toml
[parallel]
enabled = false
max_workers = 3
worktree_root = ".ralph/worktrees"
strategy = "queue"                # queue|group
merge_policy = "manual"            # manual|auto_merge
```

**Settings:**

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| `enabled` | bool | `false` | - | Enable parallel execution |
| `max_workers` | int | `3` | 1+ | Maximum parallel workers |
| `worktree_root` | string | `.ralph/worktrees` | - | Directory for worktrees |
| `strategy` | string | `"queue"` | queue/group | Task selection strategy |
| `merge_policy` | string | `"manual"` | manual/auto_merge | How to merge work |

**See also:** `docs/PARALLEL_CONFIG.md` for detailed parallel execution guide.

---

### `[authorization]` - File Write Permissions

Control what files agents can write.

```toml
[authorization]
enabled = false
enforcement_mode = "warn"         # warn|block
fallback_to_full_auto = false
permissions_file = ".ralph/permissions.json"
```

**Settings:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | `false` | Enable authorization checks |
| `enforcement_mode` | string | `"warn"` | warn or block |
| `fallback_to_full_auto` | bool | `false` | Bypass when --full-auto present |
| `permissions_file` | string | `.ralph/permissions.json` | Path to permissions JSON |

**See also:** `docs/AUTHORIZATION.md` for complete authorization system documentation.

---

### `[watch]` - Watch Mode

File watching and automatic gate execution.

```toml
[watch]
enabled = false
patterns = ["**/*.py", "**/*.md"]
debounce_ms = 500
auto_commit = false
```

**Settings:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | `false` | Enable watch mode |
| `patterns` | array | `["**/*.py", "**/*.md"]` | File patterns to watch |
| `debounce_ms` | int | `500` | Debounce delay in milliseconds |
| `auto_commit` | bool | `false` | Auto-commit when gates pass |

---

### `[output]` - Output Control

Control verbosity and output format.

```toml
[output]
verbosity = "normal"              # quiet|normal|verbose
format = "text"                   # text|json
```

**Settings:**

| Setting | Type | Default | Options | Description |
|---------|------|---------|---------|-------------|
| `verbosity` | string | `"normal"` | quiet/normal/verbose | Output verbosity level |
| `format` | string | `"text"` | text/json | Output format |

---

### `[state]` - State Management

State validation and cleanup behavior.

```toml
[state]
auto_cleanup_stale = false        # Auto-remove stale task IDs
validate_on_startup = true        # Validate state against PRD
warn_on_prd_modified = true       # Warn if PRD modified after state
protect_current_task = true       # Never cleanup current task
protect_recent_hours = 1          # Protect tasks completed in last N hours
```

**Settings:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `auto_cleanup_stale` | bool | `false` | Automatically remove stale tasks |
| `validate_on_startup` | bool | `true` | Validate state on startup |
| `warn_on_prd_modified` | bool | `true` | Warn if PRD changed externally |
| `protect_current_task` | bool | `true` | Always protect current task |
| `protect_recent_hours` | int | `1` | Protection window for recent tasks |

---

### `[init]` - Initialization Behavior

Control how `ralph init --force` handles existing configuration.

```toml
[init]
merge_config_on_reinit = true     # Merge config on re-init
merge_strategy = "user_wins"      # user_wins|template_wins|ask
preserve_sections = [             # Sections never overwritten
    "runners.custom",
    "tracker.github",
    "authorization",
]
merge_sections = [                 # Sections merged (user wins)
    "loop",
    "gates",
    "files",
    "prompt",
    "state",
    "output_control",
]
```

**Settings:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `merge_config_on_reinit` | bool | `true` | Merge config when re-running init |
| `merge_strategy` | string | `"user_wins"` | Merge strategy |
| `preserve_sections` | array | `["runners.custom", ...]` | Never override these |
| `merge_sections` | array | `["loop", "gates", ...]` | Merge these sections |

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `RALPH_CONFIG` | Path to override config file |
| `GITHUB_TOKEN` | GitHub authentication token |
| `RALPH_DEBUG` | Enable debug logging (set to `1`) |
| `RALPH_DISABLE_SECRET_SCAN` | Disable gitleaks secret scanning |

---

## Validation

Configuration values are validated on load. Invalid values raise `ValueError` with descriptive messages.

**Example validation errors:**

```
ValueError: max_iterations suspiciously large: 5000 (limit: 1000)
ValueError: Invalid loop mode: 'fast'. Must be one of: speed, quality, exploration.
ValueError: Invalid parallel.strategy: 'random'. Must be 'queue' or 'group'.
```

**Run diagnostics to validate configuration:**

```bash
ralph diagnose
```

---

## Examples

### Minimal Configuration

```toml
[runners.codex]
argv = ["codex", "exec", "--full-auto", "-"]

[gates]
commands = ["make test"]
```

### Full Configuration

```toml
[loop]
mode = "quality"
max_iterations = 5
runner_timeout_seconds = 1800

[runners.codex]
argv = ["codex", "exec", "--full-auto", "-"]

[runners.claude]
argv = ["claude", "-p"]

[gates]
commands = [
    "uv run pytest -q",
    "uv run ruff check .",
]
fail_fast = true

[gates.review]
enabled = true
backend = "runner"
agent = "claude"

[git]
branch_strategy = "per_prd"
auto_commit = true

[authorization]
enabled = true
enforcement_mode = "warn"

[watch]
enabled = true
patterns = ["**/*.py", "**/*.md"]
```

---

## Related Documentation

- **Authorization System:** `docs/AUTHORIZATION.md`
- **Parallel Execution:** `docs/PARALLEL_CONFIG.md`
- **Phase 2 Config:** `docs/configuration-phase2.md`
- **Troubleshooting:** `docs/TROUBLESHOOTING.md`

---

**Document Owner:** maintainers
**Next Review:** 2026-04-20
**Change Log:**
- 2026-01-20: Initial version (v1.0)
