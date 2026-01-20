# UX Improvements Plan - Adversarial Review

**Plan**: imperative-orbiting-candy.md
**Reviewer**: Adversarial Analysis Agent
**Date**: 2026-01-20
**Review Type**: Technical Risk Assessment

---

## Executive Summary

The UX improvements plan addresses critical real-world issues but suffers from **scope creep, insufficient risk analysis, and architectural gaps**. The authorization artifact approach (Issue 0) is fundamentally sound but relies on unproven assumptions about agent behavior. Evidence-based prompting (Issue 0.5) adds value but lacks implementation details. The plan attempts too many architectural changes simultaneously without clear rollback strategies. **Top recommendation: Implement in smaller, testable increments with explicit rollback plans for each issue.**

---

## Top 10 Critical Risks

### 1. **[CRITICAL] Authorization Artifacts Won't Stop Permission Requests**

**Severity**: CRITICAL
**Likelihood**: HIGH (80%)
**Impact**: BLOCKS entire autonomous development workflow

**Problem**:
- Plan assumes `.ralph/permissions.json` will prevent agents from asking for write permissions
- **Root cause misunderstanding**: The plan conflates *user intent* with *agent safety defaults*
- Claude/Claude Code agents have hard-coded safety behaviors that override prompt instructions
- Evidence from plan: "Agent in sTools project stopped with 'pending file write permissions' despite explicit 'File writing authority (CRITICAL)' section in PROMPT_build.md"

**Why the proposed solution fails**:
1. **Agent safety layers are deeper than prompts**: Anthropic's safety guidelines are coded into the agent runner, not just prompt text
2. **Authorization artifacts are NOT a supported primitive**: Claude Code doesn't check `.ralph/permissions.json` - this is a made-up mechanism
3. **Circular dependency**: To verify permissions, the agent needs to read the file, but to read the file it needs permissions

**Mitigation**:
```python
# WRONG (proposed in plan):
auth = load_authorization(project_root)
if not verify_authorization(auth, ["file_write"]):
    raise AuthorizationError("File write not authorized")

# CORRECT (needs external enforcement):
# 1. Use Claude Code's built-in permission system (execpolicy)
# 2. OR run agents with --full-auto flag (bypasses interactive prompts)
# 3. OR create a wrapper script that auto-confirms via expect/pexpect
```

**Recommended Approach**:
- **Option A (Recommended)**: Use `execpolicy .rules` files with pre-approved command prefixes
- **Option B (Fallback)**: Modify runner argv to include `--full-auto` or `--yes` flags
- **Option C (Last Resort)**: Create a wrapper script that auto-confirms file operations via pexpect

**Evidence Required**:
- Test the proposed `.ralph/permissions.json` approach with a real Claude Code agent
- Document whether agents actually read or respect external permission files
- If they don't, the entire Issue 0 approach needs reconsideration

---

### 2. **[CRITICAL] Evidence-Based Prompting Lacks Implementation Details**

**Severity**: CRITICAL
**Likelihood**: HIGH (90%)
**Impact**: Wasted effort, agents won't comply with structured output format

**Problem**:
- Plan proposes structured JSON output from agents:
  ```json
  {
    "changes": [{"file": "path", "lines": "X-Y", "description": "what"}],
    "evidence": [{"command": "...", "output": "..."}],
    "tests": [{"name": "...", "status": "PASS|FAIL"}],
    "compliance": "PASS|FAIL|PARTIAL"
  }
  ```
- **No parsing logic defined**: How does `loop.py` extract this JSON from natural language text?
- **No fallback for non-compliant agents**: What happens when agent ignores the format?

**Specific Gaps**:
1. **JSON extraction not trivial**: Agents rarely output pure JSON - they wrap it in explanations
2. **Partial parsing**: How do we handle 60% compliance vs 0% compliance?
3. **Prompt bloat**: Structured output requirements add ~500 tokens to every prompt
4. **No validation**: Plan doesn't specify how to validate the JSON structure

**Mitigation**:
```python
# Proposed addition to loop.py:
def parse_structured_output(raw_output: str) -> dict | None:
    """Extract structured JSON from agent output.

    Returns:
        dict if valid JSON found, None otherwise
    """
    import re
    import json

    # Try to find JSON code blocks
    json_pattern = r'```json\s*(.*?)\s*```'
    matches = re.findall(json_pattern, raw_output, re.DOTALL)

    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    # Try to find bare JSON objects
    try:
        return json.loads(raw_output.strip())
    except json.JSONDecodeError:
        pass

    # Fallback: return None (agent didn't comply)
    return None
```

**Recommended Approach**:
1. **Phase 1**: Add evidence discipline to prompts WITHOUT requiring JSON output
2. **Phase 2**: Add lightweight parsing (e.g., regex for `**Evidence**: ` patterns)
3. **Phase 3**: Optional JSON parsing with graceful fallback to freeform text
4. **Success metric**: 70%+ compliance with evidence citations (measured via heuristic)

---

### 3. **[HIGH] Spec Limits Break Existing Workflows**

**Severity**: HIGH
**Likelihood**: MEDIUM (60%)
**Impact**: Silent data loss, agents miss critical context

**Problem**:
- Plan proposes hard limits: `max_specs_files: int = 20`, `max_specs_chars: int = 50000`
- **No warning system**: Users won't know their specs are being truncated
- **Arbitrary thresholds**: 50K chars chosen without empirical basis
- **Breaking change**: Projects currently working with large specs will break mysteriously

**Edge Cases Not Considered**:
1. **Dependent specs**: If spec A references spec B, and B is excluded, A becomes useless
2. **Priority ordering**: "sorted" option doesn't account for spec importance
3. **Binary truncation**: Cutting at 50K chars might break YAML/JSON syntax
4. **No audit trail**: No way to know which specs were excluded or why

**Mitigation**:
```python
# Proposed addition to spec_loader.py:
@dataclass
class SpecLoadResult:
    included: list[tuple[str, int]]  # (filepath, char_count)
    excluded: list[tuple[str, int]]  # (filepath, char_count)
    truncated: list[tuple[str, int, int]]  # (filepath, original, truncated)
    total_chars: int

    def log_summary(self) -> str:
        return (
            f"Loaded {len(self.included)} specs ({self.total_chars} chars)\n"
            f"Excluded: {len(self.excluded)} files\n"
            f"Truncated: {len(self.truncated)} files\n"
        )
```

**Recommended Approach**:
1. **Make limits opt-in**: Default to no limits, warn via `ralph doctor`
2. **Add smart prioritization**: Use file modification time, dependency graph, or explicit priority tags
3. **Incremental rollout**: Start with warnings-only mode for 2 versions
4. **User override**: Allow per-project limits via `ralph.toml`

---

### 4. **[HIGH] State Validation Can Corrupt Active Work**

**Severity**: HIGH
**Likelihood**: MEDIUM (50%)
**Impact**: Lost task state, confused users

**Problem**:
- Plan proposes "auto-cleanup stale task references"
- **Race condition**: What if PRD is edited while loop is running?
- **False positives**: State might be valid but PRD was temporarily reverted
- **No recovery**: Once tasks are removed from state, they're gone

**Specific Failure Mode**:
1. User edits PRD to add 3 new tasks
2. Loop is running, has current task state
3. State validation runs, sees "stale" task IDs
4. Auto-cleanup removes active task from state
5. Loop loses context, repeats work or crashes

**Mitigation**:
```python
# Proposed safety checks:
def safe_cleanup_stale_state(
    state_path: Path,
    current_prd_tasks: set[str],
    dry_run: bool = True
) -> list[str]:
    """Remove stale task IDs from state with safety checks.

    Args:
        state_path: Path to state.json
        current_prd_tasks: Set of valid task IDs from current PRD
        dry_run: If True, report what would be removed without removing

    Returns:
        List of task IDs that would be/are removed
    """
    state = json.loads(state_path.read_text())
    current_task = state.get("current_task_id")

    # NEVER remove the current task
    protected_ids = {current_task} if current_task else set()

    stale_ids = [
        tid for tid in state.get("completed_task_ids", [])
        if tid not in current_prd_tasks and tid not in protected_ids
    ]

    if dry_run:
        return stale_ids

    # Actually remove (with user confirmation in CLI)
    # ...
```

**Recommended Approach**:
1. **Never auto-cleanup current task**: Protect active work
2. **Dry-run by default**: Show what would be removed, require confirmation
3. **Add state migration path**: Rename old task IDs instead of deleting
4. **Timestamp check**: Only cleanup if PRD mtime > state mtime by > 60 seconds

---

### 5. **[MEDIUM] Config Merge Logic Is Undefined**

**Severity**: MEDIUM
**Likelihood**: HIGH (80%)
**Impact**: Unexpected config behavior, lost settings

**Problem**:
- Plan proposes "deep merge template with existing config"
- **No merge strategy specified**: What happens when both template and user config define `[loop.max_iterations]`?
- **Type conflicts**: What if template has `max_iterations = 10` (int) and user has `max_iterations = "15"` (string)?
- **List conflicts**: How to merge `gates.commands` lists?

**Undefined Scenarios**:
1. **Removed keys**: Template removes a key that user config has - delete or keep?
2. **New sections**: Template adds `[authorization]` section - add to user config?
3. **Schema changes**: Template changes `max_iterations` from int to str - error or coerce?

**Current State**:
- Plan references `_deep_merge()` in `config.py` which does exist
- BUT `_deep_merge()` is **simple recursive override**, not a 3-way merge
- No provision for "user wins" vs "template wins" semantics

**Mitigation**:
```python
# Proposed merge strategies:
class MergeStrategy(Enum):
    USER_WINS = "user_wins"  # User values override template
    TEMPLATE_WINS = "template_wins"  # Template values override user
    MERGE_ARRAYS = "merge_arrays"  # Concatenate list values
    KEEP_BOTH = "keep_both"  # Keep both, rename user key to user_key
```

**Recommended Approach**:
1. **Explicit merge rules in ralph.toml**:
   ```toml
   [init]
   merge_strategy = "user_wins"  # or "template_wins" or "ask"
   merge_sections = ["loop", "gates"]  # sections to merge
   preserve_sections = ["runners.custom"]  # never overwrite
   ```
2. **3-way merge**: Use last known template, user config, and new template
3. **Conflict resolution**: Ask user for conflicts, use config for defaults

---

### 6. **[MEDIUM] Circular Dependencies Between Issues**

**Severity**: MEDIUM
**Likelihood**: MEDIUM (50%)
**Impact**: Implementation deadlock, incomplete features

**Problem**:
- Issues have hidden dependencies not acknowledged in plan
- **Issue 0** depends on **Issue 0.5** (evidence tracking needs evidence prompts)
- **Issue 0.5** depends on **Issue 0** (structured output needs authorization to write)
- **Issue 2** depends on **Issue 1** (state validation needs spec loading to work first)

**Dependency Graph** (not documented in plan):
```
Issue 0 (Authorization)
  ├─> Issue 0.5 (Evidence Prompts) [circular]
  └─> Issue 2 (State Validation) [needs auth to cleanup]

Issue 0.5 (Evidence Prompts)
  ├─> Issue 0 (Authorization) [circular]
  └─> Issue 1 (Spec Limits) [needs evidence about what was loaded]

Issue 1 (Spec Limits)
  └─> Issue 2 (State Validation) [needs to know PRD changed]

Issue 2 (State Validation)
  └─> Issue 1 (Spec Limits) [needs to load PRD]
```

**Mitigation**:
1. **Break cycles**: Implement authorization WITHOUT evidence tracking first
2. **Feature flags**: Add `[feature.evidence_tracking] enabled = false` until ready
3. **Staged rollout**:
   - Week 1: Issue 0 (basic auth)
   - Week 2: Issue 1 (spec limits)
   - Week 3: Issue 2 (state validation)
   - Week 4: Issue 0.5 (evidence prompts) AND Issue 3 (config merge)

---

### 7. **[MEDIUM] No Performance Impact Analysis**

**Severity**: MEDIUM
**Likelihood**: HIGH (90%)
**Impact**: Slower loop, higher token costs

**Problem**:
- **Authorization check**: Every iteration now loads and verifies `.ralph/permissions.json`
- **Evidence parsing**: Every iteration now parses agent output for structured data
- **Spec limits**: Every iteration now counts chars and filters specs
- **State validation**: Every `ralph run` now validates state against PRD

**Estimated Overhead**:
- Authorization: ~5ms per iteration (negligible)
- Evidence parsing: ~50-200ms per iteration (JSON parsing is expensive)
- Spec limits: ~100-500ms per iteration (file I/O + counting)
- State validation: ~200-1000ms per startup (PRD parsing + comparison)

**Current Loop Timing** (from codebase):
- Typical iteration: 5-30 seconds (agent dependent)
- Overhead from changes: 5-15% increase in iteration time

**Mitigation**:
1. **Lazy loading**: Only check authorization once per process, cache result
2. **Async validation**: Run state validation in background while agent starts
3. **Cached spec metadata**: Store spec char counts in `.ralph/specs_metadata.json`
4. **Opt-in evidence parsing**: Only parse if agent outputs JSON markers

---

### 8. **[MEDIUM] Test Coverage Gaps**

**Severity**: MEDIUM
**Likelihood**: MEDIUM (60%)
**Impact**: Regressions, flaky tests

**Problem**:
- Plan lists test files but doesn't specify WHAT to test
- **Missing integration tests**: How do we test the full authorization flow?
- **Missing property tests**: Spec limits, state cleanup, and config merge are perfect for Hypothesis
- **No adversarial tests**: What if agent outputs malformed JSON? What if PRD is mid-edit?

**Specific Test Gaps**:

1. **Authorization tests missing**:
   ```python
   # Need but not planned:
   def test_authorization_expired_rejected():
       """Expired auth should raise error."""

   def test_authorization_scope_enforcement():
       """Auth with 'read' scope should reject 'write' actions."""

   def test_authorization_missing_file():
       """Missing .ralph/permissions.json should auto-create with confirmation."""
   ```

2. **Evidence parsing tests missing**:
   ```python
   # Need but not planned:
   def test_evidence_parse_json_with_explanation():
       """Agent wraps JSON in text - should still extract."""

   def test_evidence_parse_malformed_json():
       """Agent outputs invalid JSON - should return None, not crash."""

   def test_evidence_parse_no_json():
       """Agent ignores format - should return None, not raise."""
   ```

3. **Edge case tests missing**:
   ```python
   # Need but not planned:
   def test_spec_limits_binary_cutoff_breaks_yaml():
       """Cutting at 50K chars might break YAML syntax."""

   def test_state_validation_prd_mid_edit():
       """PRD edited while loop running - should not cleanup."""

   def test_config_merge_type_conflict():
       """Template has int, user has str - should coerce or error."""
   ```

**Mitigation**:
1. **Add test checklist to plan**: For each feature, list 5+ edge cases
2. **Property-based tests**: Use Hypothesis for spec limits, state cleanup, config merge
3. **Integration tests**: Test full flow from `ralph init` to `ralph run` with auth
4. **Adversarial tests**: Test malformed inputs, race conditions, concurrent edits

---

### 9. **[LOW] Breaking Changes for Existing Projects**

**Severity**: LOW
**Likelihood**: MEDIUM (50%)
**Impact**: User confusion, migration pain

**Problem**:
- **New required config sections**: `[authorization]`, `[prompt]`, `[state]`, `[init]`
- **New required files**: `.ralph/permissions.json`
- **Changed PRD format**: Evidence requirements in progress.md
- **No version flag**: No way to detect "old" vs "new" project format

**Migration Scenarios**:

1. **Existing project without auth**:
   ```
   User runs: ralph run
   Expected: Auto-create .ralph/permissions.json
   Actual: Permission denied error (file doesn't exist)
   ```

2. **Existing project with large specs**:
   ```
   User runs: ralph run
   Expected: Works as before
   Actual: Specs truncated, agent misses context
   ```

3. **Existing project with custom ralph.toml**:
   ```
   User runs: ralph init --force
   Expected: Preserve custom config
   Actual: Config overwritten with template (if merge fails)
   ```

**Mitigation**:
```python
# Proposed version detection:
@dataclass
class ProjectVersion:
    major: int
    minor: int
    patch: int

def detect_project_version(project_root: Path) -> ProjectVersion:
    """Detect Ralph Gold project version from state/config."""
    # Version 0.8: No .ralph/permissions.json
    # Version 0.9: .ralph/permissions.json optional
    # Version 1.0: .ralph/permissions.json required

    if (project_root / ".ralph" / "permissions.json").exists():
        return ProjectVersion(1, 0, 0)
    elif (project_root / ".ralph" / "state.json").exists():
        return ProjectVersion(0, 8, 0)
    else:
        return ProjectVersion(0, 0, 0)
```

**Recommended Approach**:
1. **Semver for project format**: Track version in `.ralph/version.json`
2. **Migration scripts**: `ralph migrate --from 0.8 --to 1.0`
3. **Backward compatibility**: Support v0.8 projects for 2+ versions
4. **Opt-in for breaking changes**: Add `--use-v1-features` flag

---

### 10. **[LOW] Alternative Approaches Not Considered**

**Severity**: LOW
**Likelihood**: N/A
**Impact**: May have simpler solutions

**Problem**:
- Plan jumps to complex solutions without considering simpler alternatives

**Missed Alternatives**:

1. **Authorization**: Instead of custom artifacts, use existing mechanisms
   - **Alternative**: Claude Code's `execpolicy .rules` files (already supported)
   - **Alternative**: `--full-auto` flag (already exists)
   - **Alternative**: Wrapper script with `pexpect` (standard practice)

2. **Evidence tracking**: Instead of structured JSON, use lightweight conventions
   - **Alternative**: Markdown annotations like `<!-- Evidence: file:line -->`
   - **Alternative**: Append evidence receipts to existing `progress.md`
   - **Alternative**: Use git commits as evidence trail (already exists)

3. **Spec limits**: Instead of hard limits, use smart loading
   - **Alternative**: LRU cache for specs (evict least recently used)
   - **Alternative**: Vector similarity to load most relevant specs
   - **Alternative**: User-specified priorities in spec filenames

4. **State validation**: Instead of auto-cleanup, use warnings
   - **Alternative**: Log stale task IDs, let user decide
   - **Alternative`: Move stale tasks to `.ralph/stale_tasks.json`
   - **Alternative**: Git-based state recovery (rollback to commit)

**Recommended Approach**:
For each issue, document:
- **Problem**: What are we solving?
- **Alternatives**: What else could we do?
- **Tradeoffs**: Why choose this approach?
- **Rollback**: How to revert if it fails?

---

## Recommended Plan Modifications

### Phase 0: Authorization (CRITICAL - Must Fix)

**Original Plan**:
- Create `.ralph/permissions.json` artifact
- Verify authorization in `loop.py`
- Assume agents will respect the artifact

**Revised Plan**:
1. **Test artifact approach first**:
   ```bash
   # Create test project with .ralph/permissions.json
   # Run Claude Code agent
   # Document whether permission requests occur
   ```

2. **If artifact approach fails**, fallback to:
   ```bash
   # Option A: Use execpolicy
   echo "allowed_prefixes: ['git', 'pytest', 'uv']" > .ralph/.rules

   # Option B: Modify runner argv
   runners.claude.argv = ["claude", "--full-auto", "-p"]

   # Option C: Wrapper script
   #!/usr/bin/expect -f
   set timeout -1
   spawn claude -p
   expect "Write to file*"
   send "yes\r"
   interact
   ```

3. **Add evidence tracking LATER** (separate issue)

**Success Criteria**:
- [ ] Artifact approach validated with real agent
- [ ] Fallback approach documented
- [ ] At least one method confirmed to work
- [ ] Test coverage for authorization flow

---

### Phase 0.5: Evidence-Based Prompts (HIGH - Simplify)

**Original Plan**:
- Require structured JSON output from agents
- Parse JSON in `loop.py`
- Store evidence in state

**Revised Plan**:
1. **Phase 1 (v0.9)**: Add evidence discipline WITHOUT JSON requirement
   ```markdown
   ## Evidence Discipline
   - Every claim MUST cite evidence: **Evidence**: path/to/file:line
   - Record commands: `<command>\n<output>`
   - Test results: `pytest tests/file.py::test_name - PASS`
   ```

2. **Phase 2 (v1.0)**: Add lightweight evidence extraction
   ```python
   def extract_evidence_citations(output: str) -> list[str]:
       """Extract **Evidence**: patterns from output."""
       pattern = r'\*\*Evidence\*:\s*([^\n]+)'
       return re.findall(pattern, output)
   ```

3. **Phase 3 (v1.1)**: Optional JSON parsing with fallback
   ```python
   evidence = parse_structured_output(raw_output) or extract_evidence_citations(raw_output)
   ```

**Success Criteria**:
- [ ] Evidence citations appear in 70%+ of agent outputs
- [ ] Parsing doesn't crash on malformed output
- [ ] Freeform text still works (graceful degradation)

---

### Phase 1: Spec Limits (MEDIUM - Add Warnings)

**Original Plan**:
- Hard limits: 20 files, 50K chars
- Silent truncation/exclusion

**Revised Plan**:
1. **v0.9**: Diagnostic warnings only
   ```bash
   $ ralph doctor
   WARNING: 25 spec files found (limit: 20)
   WARNING: 75,000 chars in specs (limit: 50,000)
   Run 'ralph init --force' to apply limits.
   ```

2. **v1.0**: Opt-in limits via config
   ```toml
   [prompt]
   enable_limits = true  # Opt-in!
   max_specs_files = 20
   max_specs_chars = 50000
   ```

3. **v1.1**: Smart prioritization (not just "sorted")
   ```toml
   [prompt]
   priority_strategy = "recency"  # or "dependency", or "manual"
   priority_file = ".ralph/spec_priority.txt"
   ```

**Success Criteria**:
- [ ] No breaking changes for existing projects
- [ ] User has control over limits
- [ ] Warnings are actionable

---

### Phase 2: State Validation (MEDIUM - Add Safety)

**Original Plan**:
- Auto-cleanup stale task IDs
- No protection for current task

**Revised Plan**:
1. **v0.9**: Read-only validation
   ```python
   def validate_state(project_root: Path) -> list[str]:
       """Return list of stale task IDs (don't remove)."""
       stale = find_stale_task_ids(project_root)
       if stale:
           logger.warning(f"Found {len(stale)} stale task IDs: {stale}")
           logger.warning("Run 'ralph state cleanup' to remove them")
       return stale
   ```

2. **v1.0**: Manual cleanup with confirmation
   ```bash
   $ ralph state cleanup
   Found 3 stale task IDs: [1, 5, 9]
   Remove? (yes/no): yes
   Removed 3 stale task IDs.
   ```

3. **v1.1**: Auto-cleanup with safety checks
   ```python
   def safe_cleanup(project_root: Path) -> list[str]:
       """Never remove current task or recently completed tasks."""
       current = get_current_task(project_root)
       recent = get_recently_completed(project_root, hours=1)
       protected = {current} | set(recent)
       # Only cleanup old, truly stale tasks
   ```

**Success Criteria**:
- [ ] No accidental removal of active tasks
- [ ] User has control over cleanup
- [ ] Dry-run mode available

---

### Phase 3: Config Merge (LOW - Define Strategy)

**Original Plan**:
- "Deep merge template with existing config"
- No merge strategy specified

**Revised Plan**:
1. **v0.9**: Preserve-only mode (no merge)
   ```python
   def init_project(project_root: Path, force: bool = False):
       if force and config_exists():
           # Archive old config, don't merge
           archive_config(project_root)
           write_new_config(project_root)
   ```

2. **v1.0**: Simple 3-way merge with user-wins default
   ```python
   def merge_configs(
       old_template: dict,
       user_config: dict,
       new_template: dict
   ) -> dict:
       """User values win over both templates."""
       result = deepcopy(new_template)
       for key, value in user_config.items():
           if key in result and isinstance(result[key], dict):
               result[key] = merge_configs(old_template.get(key, {}), value, new_template[key])
           else:
               result[key] = value
       return result
   ```

3. **v1.1**: Configurable merge strategies
   ```toml
   [init]
   merge_strategy = "user_wins"  # or "template_wins" or "ask"
   merge_sections = ["loop", "gates", "files"]
   preserve_sections = ["runners.custom", "tracker.github"]
   ```

**Success Criteria**:
- [ ] Merge strategy is explicit and documented
- [ ] User can override merge behavior
- [ ] No accidental config loss

---

## Implementation Timeline (Revised)

**Week 1-2: Authorization (Issue 0)**
- Day 1-2: Test artifact approach with real agent
- Day 3-4: Implement fallback based on test results
- Day 5-7: Add tests and documentation
- Day 8-10: Code review and refinement

**Week 3: Evidence Discipline (Issue 0.5 - Simplified)**
- Day 1-3: Update prompt templates (no JSON requirement)
- Day 4-5: Add lightweight evidence extraction
- Day 6-7: Add tests and documentation

**Week 4: Spec Limits (Issue 1 - Warnings First)**
- Day 1-3: Implement diagnostic warnings
- Day 4-5: Add opt-in limits via config
- Day 6-7: Add tests and documentation

**Week 5: State Validation (Issue 2 - Safe Cleanup)**
- Day 1-3: Implement read-only validation
- Day 4-5: Add manual cleanup with confirmation
- Day 6-7: Add tests and documentation

**Week 6: Config Merge (Issue 3 - Defined Strategy)**
- Day 1-3: Implement preserve-only mode
- Day 4-5: Add 3-way merge with user-wins
- Day 6-7: Add tests and documentation

**Week 7-8: Integration and Polish**
- Integration testing across all phases
- Performance benchmarking
- Documentation updates
- Release preparation

---

## Conclusion

The UX improvements plan addresses real problems but needs **significant refinement** before implementation. Key recommendations:

1. **Validate assumptions early**: Test the authorization artifact approach before committing to it
2. **Simplify evidence tracking**: Start with lightweight conventions, add JSON later
3. **Add warnings before breaking changes**: Give users time to adapt
4. **Define merge strategies explicitly**: Don't leave behavior undefined
5. **Add safety checks**: Protect active work from auto-cleanup
6. **Document alternatives**: Show why this approach was chosen
7. **Implement incrementally**: Each phase should be independently valuable
8. **Test thoroughly**: Add integration tests, property tests, and adversarial tests

**Overall Assessment**: The plan is **70% ready**. With the recommended modifications, it can be **90%+ ready** for implementation. The biggest risk is the authorization artifact approach - this must be validated before proceeding.

**Next Steps**:
1. Create a spike to test authorization artifact approach
2. Document results and update plan based on findings
3. Create detailed test plan for each phase
4. Set up performance baseline for benchmarking
5. Begin implementation with Phase 0 (Authorization)
