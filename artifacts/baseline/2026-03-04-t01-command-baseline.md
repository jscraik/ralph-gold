# T01 Baseline Command Snapshots (2026-03-04)

## Table of Contents

- [Scope](#scope)
- [Environment](#environment)
- [Text-mode command baselines](#text-mode-command-baselines)
- [JSON-mode attempts via RALPH_FORMAT=json](#json-mode-attempts-via-ralph_formatjson)
- [Key observations](#key-observations)

## Scope

Baseline outputs for T01 task graph item in `.agent/PLANS.md`.

## Environment

- Captured at (UTC): 2026-03-04 23:34:48Z
- Command project: `/Users/jamiecraik/dev/ralph-gold`
- Temporary test repo: `/var/folders/tl/6bt8_lsn31b2j3sc_q5yr05c0000gn/T/ralph-baseline-i_5x1dvp`

## Text-mode command baselines

### version

- Exit code: `0`
- Command: `uv run --project /Users/jamiecraik/dev/ralph-gold ralph --version`

stdout:

    ralph-gold 1.0.0

stderr:

    <empty>

### init

- Exit code: `0`
- Command: `uv run --project /Users/jamiecraik/dev/ralph-gold ralph init`

stdout:

    Initialized Ralph files in: /private/var/folders/tl/6bt8_lsn31b2j3sc_q5yr05c0000gn/T/ralph-baseline-i_5x1dvp/.ralph

stderr:

    <empty>

### doctor

- Exit code: `2`
- Command: `uv run --project /Users/jamiecraik/dev/ralph-gold ralph doctor`

stdout:

    [OK]   git: git version 2.53.0
    [OK]   uv: uv 0.10.8 (Homebrew 2026-03-03)
    [OK]   codex: codex-cli 0.108.0-alpha.3
    [OK]   claude: 2.1.68 (Claude Code)
    [OK]   copilot: copilot version: 1.34.1
    [OK]   gh: gh version 2.87.3 (2026-02-23)
    [MISS] claude-zai: Install 'claude-zai' or adjust [runners.*].argv in ralph.toml.
    [MISS] claude-kimi: Install 'claude-kimi' or adjust [runners.*].argv in ralph.toml.

stderr:

    <empty>

### diagnose

- Exit code: `0`
- Command: `uv run --project /Users/jamiecraik/dev/ralph-gold ralph diagnose`

stdout:

    Ralph Diagnostics Report
    ============================================================
    
    ============================================================
    Summary: 9/9 checks passed
    
    ✓ All diagnostics passed!

stderr:

    <empty>

### status

- Exit code: `0`
- Command: `uv run --project /Users/jamiecraik/dev/ralph-gold ralph status`

stdout:

    PRD: .ralph/PRD.md
    Progress: 0/4 done (0 blocked, 4 open)
    Next: id=1 title=Define the project structure and scaffolding

stderr:

    <empty>

### step-dry-run

- Exit code: `0`
- Command: `uv run --project /Users/jamiecraik/dev/ralph-gold ralph step --agent codex --dry-run`

stdout:

    ============================================================
    DRY-RUN MODE - No agents will be executed
    ============================================================
    
    Configuration: VALID
    Resolved loop mode: speed
    Total tasks: 4
    Completed tasks: 0
    
    Next task that would be executed:
      • 1: Define the project structure and scaffolding
    
    ============================================================
    Dry-run complete. No changes were made.
    ============================================================

stderr:

    <empty>

### run-dry-run

- Exit code: `0`
- Command: `uv run --project /Users/jamiecraik/dev/ralph-gold ralph run --agent codex --dry-run --max-iterations 1`

stdout:

    ============================================================
    DRY-RUN MODE - No agents will be executed
    ============================================================
    
    Configuration: VALID
    Resolved loop mode: speed
    Total tasks: 4
    Completed tasks: 0
    Remaining tasks: 4
    
    Tasks that would be executed (up to 1 iterations):
      1. 1: Define the project structure and scaffolding
    
    No gates configured.
    
    Estimated duration: 60.0 seconds
    Estimated cost: $0.00
    
    ============================================================
    Dry-run complete. No changes were made.
    ============================================================

stderr:

    <empty>

## JSON-mode attempts via RALPH_FORMAT=json

### doctor-json-attempt

- Exit code: `2`
- Command: `RALPH_FORMAT=json uv run --project /Users/jamiecraik/dev/ralph-gold ralph doctor`

stdout:

    [OK]   git: git version 2.53.0
    [OK]   uv: uv 0.10.8 (Homebrew 2026-03-03)
    [OK]   codex: codex-cli 0.108.0-alpha.3
    [OK]   claude: 2.1.68 (Claude Code)
    [OK]   copilot: copilot version: 1.34.1
    [OK]   gh: gh version 2.87.3 (2026-02-23)
    [MISS] claude-zai: Install 'claude-zai' or adjust [runners.*].argv in ralph.toml.
    [MISS] claude-kimi: Install 'claude-kimi' or adjust [runners.*].argv in ralph.toml.

stderr:

    <empty>

### diagnose-json-attempt

- Exit code: `0`
- Command: `RALPH_FORMAT=json uv run --project /Users/jamiecraik/dev/ralph-gold ralph diagnose`

stdout:

    Ralph Diagnostics Report
    ============================================================
    
    ============================================================
    Summary: 9/9 checks passed
    
    ✓ All diagnostics passed!

stderr:

    <empty>

### status-json-attempt

- Exit code: `0`
- Command: `RALPH_FORMAT=json uv run --project /Users/jamiecraik/dev/ralph-gold ralph status`

stdout:

    PRD: .ralph/PRD.md
    Progress: 0/4 done (0 blocked, 4 open)
    Next: id=1 title=Define the project structure and scaffolding

stderr:

    <empty>

### step-json-attempt

- Exit code: `0`
- Command: `RALPH_FORMAT=json uv run --project /Users/jamiecraik/dev/ralph-gold ralph step --agent codex --dry-run`

stdout:

    ============================================================
    DRY-RUN MODE - No agents will be executed
    ============================================================
    
    Configuration: VALID
    Resolved loop mode: speed
    Total tasks: 4
    Completed tasks: 0
    
    Next task that would be executed:
      • 1: Define the project structure and scaffolding
    
    ============================================================
    Dry-run complete. No changes were made.
    ============================================================

stderr:

    <empty>

### run-json-attempt

- Exit code: `0`
- Command: `RALPH_FORMAT=json uv run --project /Users/jamiecraik/dev/ralph-gold ralph run --agent codex --dry-run --max-iterations 1`

stdout:

    ============================================================
    DRY-RUN MODE - No agents will be executed
    ============================================================
    
    Configuration: VALID
    Resolved loop mode: speed
    Total tasks: 4
    Completed tasks: 0
    Remaining tasks: 4
    
    Tasks that would be executed (up to 1 iterations):
      1. 1: Define the project structure and scaffolding
    
    No gates configured.
    
    Estimated duration: 60.0 seconds
    Estimated cost: $0.00
    
    ============================================================
    Dry-run complete. No changes were made.
    ============================================================

stderr:

    <empty>

## Key observations

- Baseline text-mode behavior captured for: version, init, doctor, diagnose, status, step --dry-run, run --dry-run.
- `RALPH_FORMAT=json` did not produce JSON payloads for the sampled commands.
- `doctor` exits non-zero (`2`) because optional runner binaries (`claude-zai`, `claude-kimi`) are missing in this environment.
- This establishes the machine-interface inconsistency baseline for task `T07`.
