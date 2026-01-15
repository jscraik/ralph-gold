#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install it first: https://docs.astral.sh/uv/"
  exit 1
fi

echo "Installing ralph-gold as a uv tool (editable) from: $ROOT_DIR"
uv tool install -e "$ROOT_DIR"

echo ""
echo "If 'ralph' is not on PATH yet, run:"
echo "  uv tool update-shell"
echo "then open a new shell."
