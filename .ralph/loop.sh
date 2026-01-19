#!/usr/bin/env bash
set -euo pipefail

# Golden Ralph Loop outer runner.
#
# Usage:
#   ./.ralph/loop.sh [mode] [max_iterations]
#
# mode:
#   build (default)  -> uses .ralph/PROMPT_build.md
#   plan             -> uses .ralph/PROMPT_plan.md
#
# max_iterations:
#   0 or unset -> run forever (Ctrl+C to stop)
#
# Optional env vars:
#   RALPH_AGENT=claude|codex|copilot  (default: claude)
#   RALPH_PRD=.ralph/PRD.md           (default: .ralph/PRD.md)
#   RALPH_PUSH=1                      (if set, push current branch after each iteration)

MODE="${1:-build}"
MAX_ITERATIONS="${2:-0}"

AGENT="${RALPH_AGENT:-claude}"
PRD_FILE="${RALPH_PRD:-.ralph/PRD.md}"

PROMPT_FILE=".ralph/PROMPT_build.md"
if [[ "$MODE" == "plan" ]]; then
  PROMPT_FILE=".ralph/PROMPT_plan.md"
fi

ITER=0
echo "Starting Ralph loop: mode=$MODE agent=$AGENT prd=$PRD_FILE prompt=$PROMPT_FILE max=$MAX_ITERATIONS"

while true; do
  if [[ "$MAX_ITERATIONS" -gt 0 && "$ITER" -ge "$MAX_ITERATIONS" ]]; then
    echo "Reached max iterations: $MAX_ITERATIONS"
    break
  fi

  echo "\n======================== LOOP $((ITER + 1)) ========================"
  ralph step --agent "$AGENT" --prompt-file "$PROMPT_FILE" --prd-file "$PRD_FILE" || {
    rc=$?
    echo "ralph step exited with code $rc (stopping loop)"
    exit $rc
  }

  if [[ "${RALPH_PUSH:-}" != "" ]]; then
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    git push origin "$CURRENT_BRANCH" || git push -u origin "$CURRENT_BRANCH"
  fi

  ITER=$((ITER + 1))
done
