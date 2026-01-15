\
param(
  [string]$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

function Require-Command($name) {
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  if (-not $cmd) {
    Write-Error "$name is not installed. Install uv first: https://docs.astral.sh/uv/"
    exit 1
  }
}

Require-Command uv

Write-Host "Installing ralph-gold as a uv tool (editable) from: $RootDir"
uv tool install -e $RootDir

Write-Host ""
Write-Host "If 'ralph' is not on PATH yet, run:"
Write-Host "  uv tool update-shell"
Write-Host "then open a new shell."
