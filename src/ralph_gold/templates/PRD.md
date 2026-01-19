# PRD

# Optional (only used if git.branch_strategy = "per_prd")

# Branch: ralph/example-project

## Overview

(Write a 3-8 sentence overview of what you want built.)

## Task Breakdown Guidelines

**CRITICAL:** Tasks must be atomic (5-15 minutes each) with specific acceptance criteria.

### ✅ GOOD Task Example

- [ ] Add UserConfig dataclass to config.py
  - Add `UserConfig` with `name: str` and `email: str` fields
  - Add `user: UserConfig` to main `Config` class
  - Parse `[user]` section in `load_config()`
  - Test: `uv run pytest -q tests/test_config.py -k test_user_config` passes

**Why good:** One file, one change, one test, clear acceptance

### ❌ BAD Task Example

- [ ] Implement user management
  - Add user configuration
  - Create user database
  - Add authentication
  - Add user API endpoints

**Why bad:** Multiple files, vague scope, no specific tests, 2+ hours of work

## Tasks

- [ ] Define the project structure and scaffolding
  - [Specific acceptance criterion 1]
  - [Specific test command]

- [ ] Implement the first thin vertical slice
  - [Specific acceptance criterion 1]
  - [Specific test command]

- [ ] Add tests and quality gates
  - [Specific acceptance criterion 1]
  - [Specific test command]

- [ ] Polish, docs, and smoke test
  - [Specific acceptance criterion 1]
  - [Specific test command]

# Notes

# - Mark done:   - [x]

# - Mark blocked: - [-]

# - Dependencies (optional): add an acceptance bullet like

# - Depends on: 1, 2
