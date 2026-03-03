#!/bin/bash
# Local environment check using ralph-gold
# Requires: uv tool install ralph-gold

set -e

echo "Checking environment with ralph-gold..."
export PATH="$HOME/.local/bin:$PATH"

# Check if ralph is available
if ! command -v ralph &> /dev/null; then
    echo "Installing ralph-gold..."
    uv tool install ralph-gold
    export PATH="$HOME/.local/bin:$PATH"
fi

# Run harness doctor check for this repo
ralph harness doctor

echo "Environment check passed!"
