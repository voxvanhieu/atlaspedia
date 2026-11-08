# Install the atlaspedia plugin globally for Claude Code (available in every project
# on this machine).
#
# Usage:
#   .\install.ps1              # uses this clone if it holds the marketplace, else GitHub
#   .\install.ps1 owner/repo   # register the marketplace from a GitHub repo instead
#
# This needs NO account, token or registration - it only registers the plugin
# with the local Claude Code CLI. Requires the `claude` CLI on PATH.
#
# If script execution is blocked, run:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1

$ErrorActionPreference = "Stop"

$RepoDefault = "voxvanhieu/atlaspedia"
$Marketplace = "voxvanhieu"
$Plugin      = "atlaspedia"

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Error "the Claude Code CLI ('claude') was not found on PATH. Install it first: npm install -g @anthropic-ai/claude-code"
}

$source = $null
if ($args.Count -gt 0 -and $args[0]) {
    $source = $args[0]
} elseif (Test-Path (Join-Path $PSScriptRoot ".claude-plugin\marketplace.json")) {
    $source = $PSScriptRoot   # running from a clone of this repo
} else {
    $source = $RepoDefault    # standalone script: fall back to GitHub
}

Write-Host "==> registering marketplace from: $source"
claude plugin marketplace add "$source"
if ($LASTEXITCODE -ne 0) { Write-Host "    (already registered - continuing)" }

Write-Host "==> installing plugin: $Plugin@$Marketplace"
claude plugin install "$Plugin@$Marketplace"
if ($LASTEXITCODE -ne 0) {
    claude plugin update "$Plugin@$Marketplace"
    if ($LASTEXITCODE -ne 0) { Write-Error "plugin install failed" }
}

Write-Host ""
Write-Host "done - atlaspedia is now available in every Claude Code session on this machine."
Write-Host "try it:  claude   then   /atlaspedia:go <topic>"
Write-Host "update:  claude plugin marketplace update $Marketplace   (in a clone, git pull works too)"
Write-Host "         claude plugin update $Plugin@$Marketplace"
