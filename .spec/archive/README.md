# Archived Specification Documents

This directory contains superseded specification documents from the review and revision process. They are kept for historical reference but should **NOT** be used for implementation.

## Archive Contents

### Initial Review (First Order)

| Document | Description | Superseded By | Reason |
|----------|-------------|----------------|--------|
| `PROJECT_REVIEW_REPORT.md` | Initial project review | `PROJECT_REVIEW_REPORT_REVISED.md` | Contained overstatements corrected by adversarial review |

### After Adversarial Review (Second Order)

| Document | Description | Superseded By | Reason |
|----------|-------------|----------------|--------|
| `PROJECT_REVIEW_REPORT_REVISED.md` | Review after adversarial critique | N/A (still relevant) | Good overall summary, but see THIRD_ORDER_REVIEW.md for latest |
| `spec-2026-01-19-critical-bug-fixes.md` | PRD v1 | `spec-2026-01-19-critical-bug-fixes-v3.md` | **CRITICAL:** Contains architectural errors (wrong exit mechanism) |
| `adr-0001-exit-signal-logic.md` | ADR v1 | `adr-0001-exit-signal-logic-v3.md` | **CRITICAL:** Contains architectural errors (wrong exit mechanism) |

## Why These Were Archived

### Critical Issues in v1/v2

#### Issue 1: Wrong Exit Mechanism (ARCHITECTURAL ERROR)

**v1/v2 proposed:**
```python
return 1  # or raise SystemExit(1)
```

**Why this is wrong:**
- `run_loop()` returns `List[IterationResult]`, not `int`
- Using `return 1` would break the function signature
- Exit codes are calculated in `cli.py`, not in the loop

**v3 correct approach:**
```python
break  # Exit loop; cli.py will determine exit code
```

#### Issue 2: Missing Method Specification

**v1/v2 assumed:** `tracker.all_blocked()` exists

**Reality:** Method does NOT exist and must be added to all trackers.

**v3 specification:** Includes complete `all_blocked()` method specification.

#### Issue 3: Unverified Bug Presented as Fact

**v1/v2:** Bug 3 (status reporting) presented as confirmed

**Reality:** Bug was never verified through code inspection.

**v3 approach:** Marked as "NEEDS VERIFICATION" with conditional implementation.

## What to Use Instead

### For Implementation

Use the v3 documents in the parent `.spec/` directory:

| Document | Purpose |
|----------|---------|
| `spec-2026-01-19-critical-bug-fixes-v3.md` | **USE THIS** - Implementation-ready PRD |
| `adr-0001-exit-signal-logic-v3.md` | **USE THIS** - Corrected architecture decision |
| `THIRD_ORDER_REVIEW.md` | **READ THIS** - Verification evidence for v3 correctness |

### For Understanding the Process

To understand how the specifications evolved through three orders of review:

1. **First Order (Adversarial):** Challenged overstatements and assumptions
   - See: `PROJECT_REVIEW_REPORT_REVISED.md`

2. **Second Order (Code Verification):** Found architectural errors
   - See: `SECOND_ORDER_REVIEW.md` (in parent `.spec/`)

3. **Third Order (Final Verification):** Confirmed all issues resolved
   - See: `THIRD_ORDER_REVIEW.md` (in parent `.spec/`)

## Reference Timeline

```
2026-01-19  Initial review created
            ↓
2026-01-19  Adversarial review (PM, Engineering, Security, SRE perspectives)
            ↓
2026-01-19  v1 specs created (PRD, ADR-0001, Review Report)
            ↓
2026-01-19  Second-order review discovered architectural errors
            ↓
2026-01-19  v3 specs created with all corrections
            ↓
2026-01-19  Third-order review verified v3 correctness
            ↓
2026-01-19  v1/v2 archived to prevent accidental use
```

## Lessons Learned

### Why Multiple Review Orders Matter

1. **First-order (adversarial)** catches overstatements and challenges assumptions
2. **Second-order (code verification)** catches architectural misunderstandings
3. **Third-order (final check)** ensures corrections were applied correctly

Without the second-order review, implementation would have failed due to:
- Type errors (returning `int` from function that returns `List`)
- Missing methods (`all_blocked()` doesn't exist)
- Potentially unnecessary work (fixing Bug 3 without verification)

### Process Improvement

For future specification efforts:

1. **Always verify against actual code** before finalizing
2. **Cross-reference all documents** for consistency
3. **Conduct iterative reviews** with clear issue tracking
4. **Archive superseded versions** to prevent confusion

## Quick Reference

**If you're here looking for implementation specs:**
→ Go back to parent `.spec/` directory
→ Use files with `-v3` suffix
→ Read `THIRD_ORDER_REVIEW.md` for verification evidence

**If you're researching the review process:**
→ Start with `PROJECT_REVIEW_REPORT_REVISED.md`
→ Then read `SECOND_ORDER_REVIEW.md` to understand what was wrong
→ Finally read `THIRD_ORDER_REVIEW.md` to see how it was corrected

---

**Archived:** 2026-01-19
**Reason:** Superseded by v3 due to critical architectural errors
**Status:** DO NOT USE FOR IMPLEMENTATION
