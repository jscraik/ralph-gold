---
last_validated: 2026-02-28
---

# Golden Ralph Loop (reference)

This repository packages a pragmatic “gold” Ralph loop:

- Fresh context every iteration (outer loop restarts the CLI agent)
- File-based state as memory
- One story per iteration
- Backpressure via test/lint/build gates
- Optional review gate (SHIP/BLOCK) after deterministic gates
- Dual-gate exit (PRD done + explicit EXIT_SIGNAL)
- Circuit breaker for no-progress loops
- Optional rate limiting
- Receipts + context snapshots for auditability
- Auto-block backstop after repeated failed attempts

Exit codes (ralph run):
- 0: successful completion
- 1: incomplete exit (e.g., max iterations / no-progress)
- 2: iteration failed (non-zero return, gate failure, judge failure, or review BLOCK)

See README for usage.
