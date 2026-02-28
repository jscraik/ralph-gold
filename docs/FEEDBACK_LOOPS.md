---
last_validated: 2026-02-28
---

# Feedback Loops

**Version:** 1.0
**Last Updated:** 2026-01-23
**Review Cadence:** Quarterly
**Audience:** Operators and contributors

---

## Overview

Ralph-gold relies on explicit feedback loops to keep agent runs aligned with
product intent and quality gates. The goal is to make review outcomes durable
and repeatable across iterations.

---

## Operator Feedback Flow (recommended)

1) **Run an iteration**
   - `ralph step` for a single task or `ralph run` for a batch.
2) **Review outputs**
   - Check gate results, logs, and any artifacts created.
3) **Record feedback**
   - Update `.ralph/FEEDBACK.md` with concise notes.
   - Capture decisions (SHIP/BLOCK) if a review gate is enabled.
4) **Update scope**
   - Adjust PRD tasks or specs if requirements changed.
5) **Repeat**
   - Run the next iteration with the updated context.

---

## Where to record feedback

- `.ralph/FEEDBACK.md` for operator notes
- `.ralph/logs/` for iteration output
- `.ralph/receipts/` for evidence citations

---

## Suggested review checklist (lightweight)

- Did gates pass?
- Does the change meet acceptance criteria?
- Are risks or regressions introduced?
- Is the outcome worth shipping, or should it be blocked?

---

## Notes

- Keep feedback short and explicit to preserve operator focus.
- Avoid storing secrets or sensitive data in feedback files.
