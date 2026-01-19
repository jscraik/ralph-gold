# Task Breakdown Standards

## Core Principle

**Every task must be atomic, verifiable, and completable in a single iteration.**

## Task Sizing Rules

### Maximum Task Scope

- One task = one commit
- One task = one iteration (typically 5-15 minutes of focused work)
- One task = one clear acceptance criterion (or tightly related set)

### Task Must Be

1. **Atomic** - Cannot be meaningfully subdivided
2. **Verifiable** - Has objective pass/fail criteria
3. **Isolated** - Minimal dependencies on other incomplete tasks
4. **Reversible** - Can be rolled back without breaking the system

## Breaking Down Large Tasks

If a task feels too large, decompose it using this pattern:

### Bad (Too Large)

```
- [ ] 1. Implement user authentication system
```

### Good (Atomic)

```
- [ ] 1. Add User model with password hashing
- [ ] 2. Create login endpoint (POST /auth/login)
- [ ] 3. Add JWT token generation
- [ ] 4. Add authentication middleware
- [ ] 5. Add logout endpoint (POST /auth/logout)
- [ ] 6. Add integration tests for auth flow
```

## Acceptance Criteria Standards

Each task must have:

- **Clear validation** - Specific commands to verify completion
- **Observable outcome** - Tests pass, endpoint returns expected data, etc.
- **No ambiguity** - Anyone should be able to verify if it's done

### Examples

**Good acceptance criteria:**

- `pytest tests/test_auth.py` passes
- `curl localhost:8000/health` returns `{"status": "ok"}`
- `mypy src/` reports no errors
- File `src/models/user.py` exists with `User` class

**Bad acceptance criteria:**

- "Authentication works" (too vague)
- "Code is clean" (subjective)
- "System is secure" (unmeasurable)

## Task Dependencies

When tasks have dependencies:

1. **Explicit ordering** - Use `depends_on: ["task-1"]` in JSON/YAML
2. **Minimize coupling** - Prefer parallel-safe tasks
3. **Stub interfaces** - Create interfaces first, implementations later

## Red Flags (Task Too Large)

Break down further if:

- Task description uses "and" more than once
- Acceptance criteria has more than 3 items
- Implementation requires changes to more than 3 files
- You can't describe the task in one sentence
- Estimated time > 20 minutes

## Iteration Drift Prevention

To keep iterations tight:

- **Run gates after every task** - Don't accumulate technical debt
- **Commit immediately** - One task = one commit
- **Update progress** - Document learnings in `.ralph/progress.md`
- **Block early** - If stuck after 2 attempts, mark task BLOCKED

## Planning Phase Requirements

When creating tasks during `ralph plan`:

1. **Start with specs** - Read `.spec/*` thoroughly
2. **Gap analysis** - Compare specs to existing code
3. **Decompose** - Break features into smallest verifiable units
4. **Prioritize** - Order by dependencies and risk
5. **Validate** - Each task should have clear acceptance criteria

## Enforcement

Ralph enforces:

- ✅ One task per iteration (hard rule in build loop)
- ✅ Gates must pass before marking done
- ✅ Max 3 attempts before blocking task
- ✅ No progress limit (stops after 3 unproductive iterations)

You must enforce:

- ⚠️ Task sizing during planning phase
- ⚠️ Clear acceptance criteria
- ⚠️ Proper task decomposition

## Examples by Task Type

### Feature Implementation

```
Bad:  - [ ] Add search functionality
Good: - [ ] Add search endpoint (GET /api/search?q=term)
      - [ ] Add search query parser
      - [ ] Add search results formatter
      - [ ] Add search integration tests
```

### Bug Fix

```
Bad:  - [ ] Fix login issues
Good: - [ ] Fix: Login fails with empty password (add validation)
      - [ ] Add test case for empty password login
```

### Refactoring

```
Bad:  - [ ] Improve code quality
Good: - [ ] Extract user validation to separate function
      - [ ] Add type hints to auth module
      - [ ] Remove duplicate error handling code
```

### Testing

```
Bad:  - [ ] Add tests
Good: - [ ] Add unit tests for User model (5 test cases)
      - [ ] Add integration test for login flow
      - [ ] Add edge case tests for token expiry
```

## Acceptance Criteria

This standard is met when:

- All tasks in PRD are atomic (single commit scope)
- Each task has clear, verifiable acceptance criteria
- No task requires more than 20 minutes to complete
- Task dependencies are explicit and minimal
- Planning phase consistently produces well-decomposed tasks
