#!/usr/bin/env bash

if [[ -z "${BASH_VERSION:-}" ]]; then
  printf '❌ verify-work.sh requires bash. Run: bash scripts/verify-work.sh [options]\n' >&2
  return 2 2>/dev/null || exit 2
fi

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  printf '❌ verify-work.sh is CLI-only; do not source it. Run: bash scripts/verify-work.sh [options]\n' >&2
  return 2
fi

set -euo pipefail

SCRIPT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -P -- "$SCRIPT_DIR/.." && pwd -P)"
CANONICAL_VERIFY_WORK="${CODEX_VERIFY_WORK_PATH:-$HOME/.codex/scripts/verify-work.sh}"
SCOPE_MODE="project-local"
FAST_MODE=0

usage() {
  cat <<'USAGE'
Usage: scripts/verify-work.sh [options]

Project-local verification entrypoint for ralph-gold.

Scope defaults:
  - project-local is the default
  - workspace governance is opt-in only

Options:
  --fast                 Run the minimal local verification lane
  --project-governance   Keep project-local scope (default)
  --workspace-governance Delegate to canonical cross-repo governance checks
  -h, --help             Show this help text
USAGE
}

while (($# > 0)); do
  case "$1" in
    --fast)
      FAST_MODE=1
      shift
      ;;
    --project-governance)
      SCOPE_MODE="project-local"
      shift
      ;;
    --workspace-governance)
      SCOPE_MODE="workspace"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf '❌ unknown argument: %s\n' "$1" >&2
      usage
      exit 2
      ;;
  esac
done

cd "$PROJECT_ROOT"
echo "[verify-work] repo root: $PROJECT_ROOT"
echo "[verify-work] scope: $SCOPE_MODE"

if [[ "$SCOPE_MODE" == "workspace" ]]; then
  if [[ ! -f "$CANONICAL_VERIFY_WORK" ]]; then
    printf '❌ canonical verify-work script not found: %s\n' "$CANONICAL_VERIFY_WORK" >&2
    exit 1
  fi
  if [[ "$FAST_MODE" -eq 1 ]]; then
    exec bash "$CANONICAL_VERIFY_WORK" --fast --workspace-governance
  fi
  exec bash "$CANONICAL_VERIFY_WORK" --workspace-governance
fi

echo
echo "==> codex-preflight"
bash scripts/codex-preflight.sh --mode optional

echo
echo "==> plan-graph-validation"
if [[ -f ".agent/PLANS.md" ]]; then
  python3 /Users/jamiecraik/.codex/scripts/plan-graph-lint.py .agent/PLANS.md
else
  echo "[verify-work] skip plan-graph-validation: .agent/PLANS.md not found"
fi

if [[ "$FAST_MODE" -eq 1 ]]; then
  echo
  echo "[verify-work] project-local fast lane passed"
  exit 0
fi

echo
echo "==> check"
make check

echo
echo "[verify-work] project-local full lane passed"
