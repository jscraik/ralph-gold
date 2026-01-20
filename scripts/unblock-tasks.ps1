# Quick workaround script to unblock stuck RALPH tasks and increase timeout
# Usage: .\scripts\unblock-tasks.ps1

$ErrorActionPreference = "Stop"

$RalphDir = ".ralph"
$PrdFile = "$RalphDir\PRD.md"
$BackupDir = "$RalphDir\archive\unblock-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "RALPH Task Unblocker (PowerShell)" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# Check if in a project with .ralph
if (-not (Test-Path $RalphDir)) {
    Write-Host "❌ Error: .ralph directory not found. Are you in a RALPH project?" -ForegroundColor Red
    exit 1
}

# Create backup
Write-Host "📦 Creating backup..."
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
Copy-Item $PrdFile "$BackupDir\PRD.md"
Write-Host "   ✅ Backed up to: $BackupDir" -ForegroundColor Green
Write-Host ""

# Count blocked tasks
$PrdContent = Get-Content $PrdFile -Raw
$BlockedCount = ([regex]::Matches($PrdContent, '^\[- \]')).Count

Write-Host "📊 Current Status:"
Write-Host "   Blocked tasks: $BlockedCount"
Write-Host ""

if ($BlockedCount -eq 0) {
    Write-Host "✅ No blocked tasks found. Nothing to do!" -ForegroundColor Green
    exit 0
}

# Show blocked tasks
Write-Host "📋 Blocked Tasks:"
Get-Content $PrdFile | Select-String -Pattern '^\[- \]' | Select-Object -First 20
Write-Host ""

# Ask for confirmation
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "This script will:"
Write-Host "  1. Unblock all blocked tasks (change [-] to [ ])"
Write-Host "  2. Increase runner_timeout_seconds to 1800 (30 minutes)"
Write-Host "  3. Reset attempt counts for blocked tasks"
Write-Host ""
Write-Host "⚠️  This will modify .ralph/PRD.md and .ralph/state.json" -ForegroundColor Yellow
Write-Host ""

$Response = Read-Host "Continue? (y/N)"
if ($Response -ne "y" -and $Response -ne "Y") {
    Write-Host "❌ Cancelled." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🔧 Applying fixes..."
Write-Host ""

# 1. Unblock tasks in PRD
Write-Host "1️⃣  Unblocking tasks in PRD..."
$NewContent = $PrdContent -replace '^\[- \]', '[ ] '
Set-Content -Path $PrdFile -Value $NewContent -NoNewline
Write-Host "   ✅ Tasks unblocked" -ForegroundColor Green

# 2. Increase timeout in ralph.toml
$RalphToml = "$RalphDir\ralph.toml"
if (Test-Path $RalphToml) {
    Write-Host "2️⃣  Increasing timeout to 30 minutes..."
    $TomlContent = Get-Content $RalphToml -Raw

    if ($TomlContent -match 'runner_timeout_seconds') {
        $NewToml = $TomlContent -replace 'runner_timeout_seconds\s*=\s*\d+', 'runner_timeout_seconds = 1800  # 30 minutes (increased from 120s)'
    } else {
        # Add after [loop] section
        $NewToml = $TomlContent -replace '(\[loop\])', '$1`nrunner_timeout_seconds = 1800  # 30 minutes'
    }

    Set-Content -Path $RalphToml -Value $NewToml -NoNewline
    Write-Host "   ✅ Timeout increased to 1800s (30 minutes)" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  ralph.toml not found, skipping timeout update" -ForegroundColor Yellow
}

# 3. Reset attempt counts in state.json
$StateFile = "$RalphDir\state.json"
if (Test-Path $StateFile) {
    Write-Host "3️⃣  Resetting attempt counts..."

    try {
        $State = Get-Content $StateFile -Raw | ConvertFrom-Json

        if ($State.PSObject.Properties.Name -contains 'task_attempts') {
            $State.task_attempts = @{}
            Write-Host "   ✅ Reset task_attempts" -ForegroundColor Green
        }

        if ($State.PSObject.Properties.Name -contains 'blocked_tasks') {
            $BlockedCount = $State.blocked_tasks.PSObject.Properties.Name.Count
            $State.blocked_tasks = @{}
            Write-Host "   ✅ Unblocked $BlockedCount tasks" -ForegroundColor Green
        }

        if ($State.PSObject.Properties.Name -contains 'noProgressStreak') {
            $State.noProgressStreak = 0
            Write-Host "   ✅ Reset noProgressStreak" -ForegroundColor Green
        }

        $State | ConvertTo-Json -Depth 10 | Set-Content $StateFile
    } catch {
        Write-Host "   ⚠️  Error modifying state: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "   ⚠️  state.json not found, skipping reset" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host "✅ Done! Summary:" -ForegroundColor Green
Write-Host ""
Write-Host "  • Tasks unblocked: $BlockedCount"
Write-Host "  • Timeout: 1800s (30 minutes)"
Write-Host "  • Attempt counts: reset"
Write-Host "  • Backup: $BackupDir"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Review the unblocked tasks: ralph status"
Write-Host "  2. Resume the loop: ralph run --agent <your-agent>"
Write-Host "  3. Monitor progress: ralph status --watch"
Write-Host ""
Write-Host "To restore backup if needed:"
Write-Host "  cp $BackupDir\PRD.md $PrdFile"
Write-Host ""
