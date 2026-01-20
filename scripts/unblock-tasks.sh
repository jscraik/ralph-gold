#!/usr/bin/env bash
# Quick workaround script to unblock stuck RALPH tasks and increase timeout
# Usage: ./scripts/unblock-tasks.sh

set -euo pipefail

RALPH_DIR=".ralph"
PRD_FILE="$RALPH_DIR/PRD.md"
BACKUP_DIR="$RALPH_DIR/archive/unblock-$(date +%Y%m%d-%H%M%S)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "RALPH Task Unblocker"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if in a project with .ralph
if [ ! -d "$RALPH_DIR" ]; then
    echo "❌ Error: .ralph directory not found. Are you in a RALPH project?"
    exit 1
fi

# Create backup
echo "📦 Creating backup..."
mkdir -p "$BACKUP_DIR"
cp "$PRD_FILE" "$BACKUP_DIR/PRD.md"
echo "   ✅ Backed up to: $BACKUP_DIR"
echo ""

# Count blocked tasks
BLOCKED_COUNT=$(grep -c '^\[- \]' "$PRD_FILE" || echo "0")
echo "📊 Current Status:"
echo "   Blocked tasks: $BLOCKED_COUNT"
echo ""

if [ "$BLOCKED_COUNT" -eq 0 ]; then
    echo "✅ No blocked tasks found. Nothing to do!"
    exit 0
fi

# Show blocked tasks
echo "📋 Blocked Tasks:"
grep -n '^\[- \]' "$PRD_FILE" | head -20 || true
echo ""

# Ask for confirmation
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "This script will:"
echo "  1. Unblock all blocked tasks (change [-] to [ ])"
echo "  2. Increase runner_timeout_seconds to 1800 (30 minutes)"
echo "  3. Reset attempt counts for blocked tasks"
echo ""
echo "⚠️  This will modify .ralph/PRD.md and .ralph/state.json"
echo ""

read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled."
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 Applying fixes..."
echo ""

# 1. Unblock tasks in PRD
echo "1️⃣  Unblocking tasks in PRD..."
sed -i.tmp 's/^\[- \]/[ ] /' "$PRD_FILE"
rm -f "${PRD_FILE}.tmp"
echo "   ✅ Tasks unblocked"

# 2. Increase timeout in ralph.toml
RALPH_TOML="$RALPH_DIR/ralph.toml"
if [ -f "$RALPH_TOML" ]; then
    echo "2️⃣  Increasing timeout to 30 minutes..."
    if grep -q "runner_timeout_seconds" "$RALPH_TOML"; then
        sed -i.tmp "s/runner_timeout_seconds = .*/runner_timeout_seconds = 1800  # 30 minutes (increased from 120s)/" "$RALPH_TOML"
        rm -f "${RALPH_TOML}.tmp"
    else
        echo "     Adding runner_timeout_seconds to [loop] section..."
        # Add after [loop] section
        sed -i.tmp '/\[loop\]/a runner_timeout_seconds = 1800  # 30 minutes' "$RALPH_TOML"
        rm -f "${RALPH_TOML}.tmp"
    fi
    echo "   ✅ Timeout increased to 1800s (30 minutes)"
else
    echo "   ⚠️  ralph.toml not found, skipping timeout update"
fi

# 3. Reset attempt counts in state.json
STATE_FILE="$RALPH_DIR/state.json"
if [ -f "$STATE_FILE" ]; then
    echo "3️⃣  Resetting attempt counts..."
    # Use python to safely modify JSON
    python3 <<'PYTHON'
import json
import sys

try:
    with open('.ralph/state.json', 'r') as f:
        state = json.load(f)

    # Reset task_attempts
    if 'task_attempts' in state:
        state['task_attempts'] = {}
        print("   ✅ Reset task_attempts")

    # Remove blocked_tasks
    if 'blocked_tasks' in state:
        blocked = state['blocked_tasks']
        state['blocked_tasks'] = {}
        print(f"   ✅ Unblocked {len(blocked)} tasks")

    # Reset noProgressStreak
    if 'noProgressStreak' in state:
        state['noProgressStreak'] = 0
        print("   ✅ Reset noProgressStreak")

    with open('.ralph/state.json', 'w') as f:
        json.dump(state, f, indent=2)

except Exception as e:
    print(f"   ⚠️  Error modifying state: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON
else
    echo "   ⚠️  state.json not found, skipping reset"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Done! Summary:"
echo ""
echo "  • Tasks unblocked: $BLOCKED_COUNT"
echo "  • Timeout: 1800s (30 minutes)"
echo "  • Attempt counts: reset"
echo "  • Backup: $BACKUP_DIR"
echo ""
echo "Next steps:"
echo "  1. Review the unblocked tasks: ralph status"
echo "  2. Resume the loop: ralph run --agent <your-agent>"
echo "  3. Monitor progress: ralph status --watch"
echo ""
echo "To restore backup if needed:"
echo "  cp $BACKUP_DIR/PRD.md $PRD_FILE"
echo ""
