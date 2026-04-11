#!/usr/bin/env bash
# Local environment preflight (repo-canonical).
# Validates tooling contract, required binaries, and Codex action wiring.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTRACT_PATH="${TOOLING_CONTRACT_PATH:-$REPO_ROOT/docs/agents/tooling.contract.toml}"
TOOLING_DOC_PATH="${TOOLING_DOC_PATH:-$REPO_ROOT/docs/agents/tooling.md}"
MISE_PATH="$REPO_ROOT/.mise.toml"
CODEX_ENVIRONMENT_PATH="$REPO_ROOT/.codex/environments/environment.toml"
CONTRACT_TOOL="$REPO_ROOT/scripts/tooling_contract.py"

if [[ ! -f "$CONTRACT_PATH" ]]; then
  echo "Error: missing tooling contract at $CONTRACT_PATH"
  exit 1
fi

if [[ ! -f "$MISE_PATH" ]]; then
  echo "Error: missing mise config at $MISE_PATH"
  exit 1
fi

if [[ ! -f "$CODEX_ENVIRONMENT_PATH" ]]; then
  echo "Error: missing Codex environment file at $CODEX_ENVIRONMENT_PATH"
  exit 1
fi

if [[ ! -f "$CONTRACT_TOOL" ]]; then
  echo "Error: missing tooling contract helper at $CONTRACT_TOOL"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: required binary 'python3' is not installed or not on PATH"
  exit 1
fi

python3 "$CONTRACT_TOOL" \
  --contract "$CONTRACT_PATH" \
  --mise "$MISE_PATH" \
  --codex-env "$CODEX_ENVIRONMENT_PATH" \
  --doc "$TOOLING_DOC_PATH" \
  --validate \
  --check-doc

mapfile -t required_bins < <(python3 "$CONTRACT_TOOL" --contract "$CONTRACT_PATH" --print-required-bins)
for bin in "${required_bins[@]}"; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "Error: required binary '$bin' is not installed or not on PATH"
    exit 1
  fi
done

echo "Checking environment with ralph-gold..."
ralph harness doctor

echo "Environment check passed!"
