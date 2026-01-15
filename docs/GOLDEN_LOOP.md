# Golden Ralph Loop (reference)

This repository packages a pragmatic “gold” Ralph loop:

- Fresh context every iteration (outer loop restarts the CLI agent)
- File-based state as memory
- One story per iteration
- Backpressure via test/lint/build gates
- Dual-gate exit (PRD done + explicit EXIT_SIGNAL)
- Circuit breaker for no-progress loops
- Optional rate limiting

Exit codes (ralph run):
- 0: successful completion
- 1: incomplete exit (e.g., max iterations / no-progress)
- 2: iteration failed (non-zero return, gate failure, or judge failure)

See README for usage.
