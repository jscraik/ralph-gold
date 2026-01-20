# Migration Guide: v0.7.x to v0.8.0

**Version:** 0.8.0
**Release Date:** 2026-01-20
**Migrating From:** v0.7.x

---

## Executive Summary

This release addresses three critical agent execution issues:

1. **Spec Truncation** — Increased limits from 50KB/10KB to 100KB/50KB
2. **Agent Write Hesitation** — Added explicit tool authorization to prompt
3. **Silent Gate Bypass** — Implemented no-files detection with diagnostics

Plus new features:
- **Metrics Module** — Track write success rate and truncation rate
- **SLO Module** — Service level objectives with error budget tracking
- **Atomic Receipt Writes** — POSIX rename guarantee for data safety

---

## Breaking Changes

### None

All changes are backward compatible. Existing projects will continue to work with upgraded CLI.

---

## New Features

### 1. Increased Spec Limits

**Before:**
- Total spec chars: 50,000
- Per-spec limit: 10,000

**After:**
- Total spec chars: 100,000 (2x increase)
- Per-spec limit: 50,000 (5x increase)

**Impact:** Larger spec files no longer truncated, reducing missed requirements.

---

### 2. No-Files Detection

**What's New:**
- Agent iterations that write no files now emit `NoFilesWrittenReceipt`
- Diagnostic information identifies causes (timeout, gate failures, permissions)
- Layered troubleshooting guidance (Quick → Deep → Advanced)

**Impact:** Previously silent failures now detected and reported.

---

### 3. Metrics & SLO Tracking

**New Artifacts:**
- `.ralph/metrics.json` — Iteration metrics with write success rate
- SLO monitoring with error budget calculation

**SLO Targets:**
- Write success rate: 95%
- Truncation rate: 10%

**Impact:** Proactive detection of systemic issues (timeout, agent problems).

---

### 4. Atomic Receipt Writes

**What's New:**
- All receipt writes use POSIX atomic rename
- No corrupted/partial receipts from crashes/interrupts

**Impact:** Improved data reliability for crash recovery.

---

## Migration Steps

### Step 1: Backup Existing State

**Required:** Always backup before upgrading.

```bash
# Create timestamped backup
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ralph snapshot "pre-v0.6-upgrade-$TIMESTAMP"

# Verify snapshot exists
ralph snapshot --list | grep "pre-v0.6-upgrade"
```

**Expected Output:**
```
pre-v0.6-upgrade-20260120-143000
```

---

### Step 2: Upgrade CLI

```bash
# Using pip
pip install --upgrade ralph-gold

# Using uv
uv pip install --upgrade ralph-gold

# Verify version
ralph --version
```

**Expected Output:**
```
ralph-gold 0.6.0
```

---

### Step 3: Validate Configuration

```bash
# Run diagnostics
ralph diagnose

# Check for warnings
ralph diagnose --test-gates
```

**Expected Output:**
```
✓ Configuration file found
✓ PRD file format valid
✓ Runner configuration valid
```

---

### Step 4: Run Test Iteration

**Recommended:** Run a single iteration to verify changes.

```bash
# Run one iteration
ralph step --agent <your-agent>

# Check for no-files warnings
cat .ralph/logs/iteration-*.log | grep -i "no files"

# Check metrics (if any)
cat .ralph/metrics.json | jq .
```

---

### Step 5: Monitor SLOs

**New Feature:** Check SLO compliance after running iterations.

```bash
# View metrics snapshot
cat .ralph/metrics.json | jq '.snapshot'

# Check write success rate (should be ≥ 0.95)
cat .ralph/metrics.json | jq '.snapshot.write_success_rate'

# Check truncation rate (should be ≤ 0.10)
cat .ralph/metrics.json | jq '.snapshot.truncation_rate'
```

**If Below Targets:**
- See TROUBLESHOOTING.md "Agent Execution Issues" → "Low Completion Rate"

---

## Configuration Changes

### Optional: Adjust Spec Limits

If you have very large spec files, you may want to increase limits further:

```toml
# .ralph/ralph.toml
[prompt]
max_specs_chars = 150000      # Total across all specs
max_single_spec_chars = 75000  # Per individual spec
```

**Note:** Defaults (100k/50k) are sufficient for most projects.

---

### Optional: Adjust Timeout

If you see timeout issues (exit code 124):

```toml
# .ralph/ralph.toml
[loop]
runner_timeout_seconds = 1800  # 30 minutes (default: 900)
```

---

## Rollback Procedure

### If Upgrade Fails

**Option 1: Rollback CLI**
```bash
# Uninstall current version
pip uninstall ralph-gold

# Install previous version
pip install ralph-gold==0.5.0
```

**Option 2: Rollback State**
```bash
# Restore from snapshot
ralph rollback "pre-v0.6-upgrade-<timestamp>"

# Verify state restored
ralph status
```

---

### If Issues During Iterations

**Symptom:** No-files warnings, unexpected failures

**Quick Fix:**
```bash
# Check for timeout
cat .ralph/logs/iteration-*.log | grep "returncode.*124"

# Check receipt details
cat .ralph/receipts/iteration-*.json | jq .

# See TROUBLESHOOTING.md for detailed guidance
```

**Rollback if Needed:**
```bash
# Restore snapshot
ralph rollback "pre-v0.6-upgrade-<timestamp>"

# Continue with old CLI version
pip install ralph-gold==0.5.0
```

---

## Validation Checklist

After migration, verify the following:

- [ ] Backup snapshot created
- [ ] CLI version shows 0.6.0
- [ ] `ralph diagnose` passes
- [ ] Test iteration ran successfully
- [ ] No unexpected warnings in logs
- [ ] Metrics file created (if iterations run)
- [ ] Write success rate ≥ 95% (after several iterations)
- [ ] Truncation rate ≤ 10% (after several iterations)

---

## New Documentation Sections

See these updated docs for details:

- **TROUBLESHOOTING.md** — New "Agent Execution Issues" section with:
  - "No Files Written" warning troubleshooting
  - Low completion rate diagnosis
  - False blocking (files exist but task blocked)
  - Spec truncation warnings

- **docs/EVIDENCE.md** — Updated receipt schemas with `NoFilesWrittenReceipt`

- **docs/CONFIGURATION.md** — Updated spec limit defaults

---

## Common Questions

### Q: Do I need to update my PRD?

**A:** No. PRD format is unchanged.

### Q: Will my existing iterations be affected?

**A:** No. Existing iteration history and receipts are preserved.

### Q: What if I see "no files written" warnings?

**A:** This is expected behavior for iterations where agent wrote nothing. See TROUBLESHOOTING.md for diagnosis.

### Q: How do I disable no-files detection?

**A:** Detection is built-in. If agent legitimately writes no files (rare), the warning is informational only.

### Q: Can I revert to v0.5 after running iterations with v0.6?

**A:** Yes, but new receipt formats (`NoFilesWrittenReceipt`) may not be readable by old CLI. Use snapshot rollback for clean revert.

---

## What's Changed Internally

### New Modules

- `src/ralph_gold/metrics.py` — Metrics collection (Phase 4)
- `src/ralph_gold/slo.py` — SLO tracking (Phase 5)

### Modified Modules

- `src/ralph_gold/config.py` — Updated `PromptConfig` defaults
- `src/ralph_gold/receipts.py` — Added `NoFilesWrittenReceipt`, atomic writes
- `src/ralph_gold/templates/PROMPT_build.md` — Added AUTHORIZATION & MODE section
- `src/ralph_gold/loop.py` — Added no-files detection + 7 helper functions

### New Tests

- `tests/test_config_prompt_defaults.py`
- `tests/test_receipts_no_files.py`
- `tests/test_prompt_enhancements.py`
- `tests/test_loop_no_files_detection.py`
- `tests/test_metrics.py`
- `tests/test_slo.py`

---

## Support

### Issues During Migration

1. Check TROUBLESHOOTING.md first
2. Review iteration logs: `.ralph/logs/`
3. Check receipts: `.ralph/receipts/`
4. Run diagnostics: `ralph diagnose --test-gates`

### Report Issues

- **Bugs:** GitHub Issues
- **Security:** jscraik@brainwav.io

When reporting, include:
- Ralph version (`ralph --version`)
- Diagnostic output (`ralph diagnose > diagnose.txt`)
- Relevant logs (`.ralph/logs/iteration-*.log`)

---

**Migration Guide Owner:** maintainers
**Next Review:** After v0.7 release
