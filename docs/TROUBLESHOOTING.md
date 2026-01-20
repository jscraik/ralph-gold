# Troubleshooting Guide

**Version:** 1.0
**Last Updated:** 2026-01-20
**Review Cadence:** Quarterly
**Audience:** Users encountering issues with ralph-gold

---

## Quick Diagnostics

Run the built-in diagnostic command to check your setup:

```bash
ralph diagnose
```

This validates:
- Configuration file existence and syntax
- PRD file format and structure
- Runner configuration

With optional gate testing:
```bash
ralph diagnose --test-gates
```

---

## Exit Codes Reference

### `ralph run` Exit Codes

| Code | Meaning | Description | Action |
|------|---------|-------------|--------|
| **0** | Success | Loop completed successfully (EXIT_SIGNAL true, all gates/judge/review passed) | None needed |
| **1** | Incomplete | Loop ended without successful exit (max iterations reached, no-progress limit hit) | Increase `max_iterations` or investigate why agent isn't completing tasks |
| **2** | Failed | One or more iterations failed (non-zero return code, gate failure, judge failure, or review BLOCK) | Check logs under `.ralph/logs/` for failure details |

### `ralph step` Exit Codes

| Code | Meaning | Description | Action |
|------|---------|-------------|--------|
| **0** | Success | Iteration completed (may or may not have made progress) | Check `ralph status` for current state |
| **1** | Failed | Iteration failed (agent error, gate failure, etc.) | Check logs under `.ralph/logs/` |
| **2** | Blocked | Task is blocked by dependencies | Mark dependencies complete or skip blocked tasks |

### Other Commands

| Command | Exit Codes | Success | Notes |
|---------|-----------|--------|-------|
| `ralph init` | 0=success, 1=failure | 0 | Fails if not in git repo |
| `ralph diagnose` | 0=passed, 2=issues found | 0 | Use `--test-gates` to validate gates |
| `ralph status` | 0=success, 1=no data | 0 | Returns 1 if no iterations run yet |
| `ralph stats` | 0=success, 1=no data | 0 | Returns 1 if no history available |

---

## Common Issues

### "Unknown agent" Error

**Symptom:**
```
Error: Unknown agent 'xyz'
```

**Cause:** Agent not configured in `.ralph/ralph.toml` or CLI not installed

**Solutions:**
1. Check runner configuration:
   ```toml
   [runners.codex]
   argv = ["codex", "exec", "--full-auto", "-"]
   ```
2. Verify the agent CLI is installed and in PATH:
   ```bash
   which codex  # or claude, copilot, etc.
   ```
3. Test the agent manually:
   ```bash
   codex exec --full-auto -
   ```

---

### "No prompt provided" from Codex

**Symptom:** Codex complains about missing prompt

**Cause:** Runner argv doesn't include `-` for stdin input

**Solution:** Ensure your runner config includes `-`:
```toml
[runners.codex]
argv = ["codex", "exec", "--full-auto", "-"]  # The - is required
```

---

### Gate Failures

**Symptom:** Iteration fails during gate execution

**Diagnosis:**
```bash
# Test gates individually
ralph diagnose --test-gates

# Check gate output in logs
cat .ralph/logs/iteration-*.log
```

**Common Causes:**
1. **Test failures:** Run tests manually to see what's failing
2. **Lint errors:** Check linter output for specific issues
3. **Missing dependencies:** Install required packages
4. **Wrong working directory:** Gates run from project root

**Solutions:**
- Fix the underlying issues (tests, lint, etc.)
- Or temporarily disable problematic gates:
  ```toml
  [gates]
  commands = []  # Disable all gates
  ```

---

### No Progress Streak

**Symptom:** Loop exits with "no progress limit reached"

**Cause:** Agent completed iterations but didn't mark tasks complete

**Solutions:**
1. **Increase no-progress limit:**
   ```toml
   [loop]
   no_progress_limit = 10  # Default is 3
   ```

2. **Check agent feedback:** Review agent outputs to understand why tasks aren't being marked complete

3. **Manual intervention:** Mark tasks complete manually in PRD, then resume:
   ```bash
   ralph resume
   ```

---

### Agent Execution Issues

#### "No Files Written" Warning

**Symptom:** Iteration completes but agent wrote no user files

```
WARNING: Agent wrote no files
Possible causes:
- Agent timed out (exit code 124)
- Pre-existing gate failures
- Agent chose not to write
```

**Layered Troubleshooting:**

**Quick Check (30 seconds):**
```bash
# Check for timeout
cat .ralph/logs/iteration-*.log | grep "returncode.*124"

# Check if files were created anyway
ls -lt src/ | head -10

# Check receipt details
cat .ralph/receipts/iteration-*.json | jq .
```

**Deep Diagnosis (2 minutes):**
```bash
# View full iteration log
cat .ralph/logs/$(ls -t .ralph/logs/ | head -1)

# Check for gate failures BEFORE agent ran
ralph diagnose --test-gates

# Check agent output for errors
grep -A20 "Agent output:" .ralph/logs/iteration-*.log
```

**Advanced Investigation:**
```bash
# Check for permission issues
touch .ralph/permission-test.tmp && rm .ralph/permission-test.tmp

# Check disk space
df -h

# Test agent manually
echo "test prompt" | claude
```

**Solutions by Cause:**

**1. Timeout (exit code 124):**
- Increase timeout in `.ralph/ralph.toml`:
  ```toml
  [loop]
  runner_timeout_seconds = 1800  # 30 minutes
  ```
- Verify files were created despite timeout
- Consider task complexity vs timeout

**2. Pre-existing gate failures:**
- Fix failing gates OR document why they can't be fixed
- Temporarily disable gates to test:
  ```toml
  [gates]
  commands = []
  ```

**3. Agent write hesitation:**
- Agent may need explicit permission
- Check prompt has AUTHORIZATION & MODE section
- Review agent output for reasoning

---

#### Low Completion Rate

**Symptom:** Few tasks completing relative to iterations run

**Diagnosis:**
```bash
# View metrics
ralph status

# Check write success rate
cat .ralph/metrics.json | jq '.snapshot.write_success_rate'

# Check truncation rate
cat .ralph/metrics.json | jq '.snapshot.truncation_rate'
```

**SLO Targets:**
- Write success rate: 95% (0.95)
- Truncation rate: 10% (0.10)

**If below targets:**
- Check for timeout issues (see above)
- Review agent outputs for common blockers
- Consider: increasing timeout, checking agent CLI, simplifying tasks

---

#### False Blocking

**Symptom:** Files exist on disk but task marked "blocked"

**Diagnosis:**
```bash
# Check expected files from PRD
grep -A10 "acceptance:" .ralph/PRD.md

# Verify files exist
find . -name "*.swift" -newer .ralph/state.json

# Check task status
ralph status | grep -A5 "blocked"
```

**Solution:**
1. Verify expected files exist
2. Manually mark task complete if files exist:
   ```bash
   ralph done <task-id>
   ```
3. Review agent output in `.ralph/logs/`

---

#### Spec Truncation Warnings

**Symptom:** Warning about spec files being truncated

```
WARNING: Spec truncated: 15000 chars -> 10000 chars
```

**Default Limits:**
- Total spec chars: 100,000
- Per-spec limit: 50,000

**Diagnosis:**
```bash
# Check current limits
cat .ralph/ralph.toml | grep "max.*chars"

# View truncation metrics
cat .ralph/metrics.json | jq '.snapshot.truncation_rate'
```

**Solutions:**
1. **Increase limits** (if appropriate):
   ```toml
   [prompt]
   max_specs_chars = 150000      # Total across all specs
   max_single_spec_chars = 75000  # Per individual spec
   ```

2. **Reduce spec size:**
   - Split large specs into smaller focused files
   - Move reference material to separate docs
   - Use summaries instead of full text

3. **Prioritize specs:**
   - Keep most relevant specs in `.ralph/specs/`
   - Move less critical specs to archive

**Impact:**
- Truncation may cause agent to miss requirements
- Monitor truncation rate: should stay under 10%

---

### Git Errors

**"Not a git repository"**

**Solution:**
```bash
git init
```

**"No commits yet"**

Ralph requires at least one commit for git operations to work:

```bash
git commit --allow-empty -m "Initial commit"
```

---

### Authorization Blocked

**Symptom:** `AuthorizationError: Write not permitted`

**Solutions:**
1. Check `.ralph/permissions.json` for blocking rules
2. Add allow patterns for files you need to write
3. Switch to WARN mode temporarily to understand what's being blocked
4. See `docs/AUTHORIZATION.md` for complete troubleshooting

---

### Config Validation Errors

**"max_iterations suspiciously large"**

**Cause:** Config value exceeds validation limit

**Solution:** Use a reasonable value:
```toml
[loop]
max_iterations = 100  # Max is 1000
```

**"Invalid loop mode"**

**Solution:** Use a valid mode:
```toml
[loop]
mode = "speed"  # Must be: speed, quality, or exploration
```

---

### Watch Mode Not Working

**Symptom:** Watch mode doesn't detect file changes

**Diagnosis:**
```bash
# Check if watch is enabled
ralph diagnose

# Verify watch configuration
cat .ralph/ralph.toml | grep -A5 "\[watch\]"
```

**Common Issues:**
1. **Not enabled:** Set `watch.enabled = true` in config
2. **Wrong patterns:** Ensure patterns match your files
3. **Platform limitations:** Some systems have file watching limits

**Solution:**
```toml
[watch]
enabled = true
patterns = ["**/*.py", "**/*.md"]  # Adjust to your needs
```

---

## Advanced Debugging

### Enable Debug Logging

```bash
RALPH_DEBUG=1 ralph run --agent codex
```

This enables verbose logging including:
- Configuration loading
- Task selection
- Gate execution
- Agent invocation

### Check Iteration Logs

Each iteration creates a log file:

```bash
# List all iteration logs
ls -la .ralph/logs/

# View the most recent log
cat .ralph/logs/$(ls -t .ralph/logs/ | head -1)

# Search for errors
grep -i error .ralph/logs/*.log
```

### Inspect State

View current Ralph state:

```bash
# View state JSON
cat .ralph/state.json | jq .

# Check progress file
cat .ralph/progress.md

# View PRD
cat .ralph/PRD.md
```

### Reset State

If you need to start over:

```bash
# Archive current state
ralph snapshot before-reset

# Clean state (keeps PRD, resets progress)
rm .ralph/state.json

# Or reinitialize entirely
ralph init --force
```

**Warning:** `--force` archives existing `.ralph/` directory. See `docs/INIT_ARCHIVING.md`.

---

## Getting Help

### Diagnostic Information

When reporting issues, include:

1. **Ralph version:**
   ```bash
   ralph --version
   ```

2. **Diagnostic output:**
   ```bash
   ralph diagnose > ralph-diagnose.txt
   ```

3. **Configuration:**
   ```bash
   cat .ralph/ralph.toml
   ```

4. **Relevant logs:**
   ```bash
   cat .ralph/logs/$(ls -t .ralph/logs/ | head -1)
   ```

5. **System info:**
   ```bash
   uname -a
   python --version
   git --version
   ```

### Report Issues

- **Security issues:** jscraik@brainwav.io
- **Bugs:** GitHub Issues
- **Feature requests:** GitHub Issues

---

## Recovery Procedures

### Recover from Failed Iteration

```bash
# Check what failed
ralph status

# View the failed log
cat .ralph/logs/iteration-X.log

# Fix the issue manually (tests, code, etc.)

# Resume the loop
ralph resume
```

### Rollback to Snapshot

```bash
# List available snapshots
ralph snapshot --list

# Rollback to a snapshot
ralph rollback my-snapshot-name
```

### Clean Up Artifacts

```bash
# Remove old logs
ralph clean --logs

# Remove old archives
ralph clean --archives

# Remove all artifacts
ralph clean --all
```

---

## Performance Issues

### Slow Iterations

**Diagnosis:**
```bash
# View iteration statistics
ralph stats --by-task

# Check for slow tasks
ralph stats --export stats.csv
```

**Common Causes:**
1. **Slow gates:** Optimize test suite or linting
2. **Large context:** Reduce PRD size or spec files
3. **Agent timeout:** Increase `runner_timeout_seconds`

**Solution:**
```toml
[loop]
runner_timeout_seconds = 1800  # 30 minutes
```

### High Memory Usage

**Causes:**
- Large context snapshots
- Many iteration logs
- Large state file

**Solutions:**
```bash
# Clean old logs
ralph clean --logs

# Clean old archives
ralph clean --archives

# Reduce snapshot retention
```

---

## Platform-Specific Issues

### Windows

**Path separators:** Use forward slashes in config (`/` not `\`)

**Line endings:** Git should handle this, but check:
```bash
git config core.autocrlf
```

**File watching:** May need polling fallback on some systems

### macOS

**File descriptor limits:** May need to increase for large projects:
```bash
ulimit -n 4096
```

**Python installation:** Use `uv` for consistent environment

### Linux

**Permissions:** Ensure Ralph has permission to write to `.ralph/`
**Inotify limits:** May need to increase for watch mode with many files

---

## Related Documentation

- **Diagnostics:** `ralph diagnose --help`
- **Authorization:** `docs/AUTHORIZATION.md`
- **Configuration:** `docs/CONFIGURATION.md`
- **Security:** `SECURITY.md`

---

**Document Owner:** maintainers
**Next Review:** 2026-04-20
**Change Log:**
- 2026-01-20: Initial version (v1.0)
