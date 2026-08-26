[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$DataRoot,
    [int]$Port = 8787,
    [string]$Python = $env:STUDYBUDDY_PYTHON,
    [switch]$DemoMode,
    [switch]$OpenBrowser
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Port -lt 1024 -or $Port -gt 65535) { throw 'invalid_port' }
if (-not $DataRoot) { throw 'data_root_required' }

# This helper is intentionally a thin, safe first-run wrapper. It never accepts
# provider keys or endpoints; real Provider configuration remains runtime-only.
$env:STUDYBUDDY_DATA_ROOT = [System.IO.Path]::GetFullPath($DataRoot)
$env:STUDYBUDDY_DEMO_MODE = if ($DemoMode) { 'true' } else { 'false' }
if (-not $DemoMode) {
    Remove-Item Env:STUDYBUDDY_AI_PROVIDER -ErrorAction SilentlyContinue
    Remove-Item Env:STUDYBUDDY_AI_MODEL -ErrorAction SilentlyContinue
    Remove-Item Env:STUDYBUDDY_AI_BASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:STUDYBUDDY_AI_API_KEY -ErrorAction SilentlyContinue
}

$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$start = Join-Path $root 'backend/scripts/start-studybuddy.ps1'
$health = Join-Path $root 'backend/scripts/health-studybuddy.ps1'
& powershell -ExecutionPolicy Bypass -NoProfile -File $start -DataRoot $env:STUDYBUDDY_DATA_ROOT -Port $Port -Python $Python -OpenBrowser:$OpenBrowser
if ($LASTEXITCODE -ne 0) { throw 'studybuddy_start_failed' }
Start-Sleep -Milliseconds 500
& powershell -ExecutionPolicy Bypass -NoProfile -File $health -Port $Port
if ($LASTEXITCODE -ne 0) { throw 'studybuddy_health_check_failed' }
Write-Output 'studybuddy_first_run_ready'
