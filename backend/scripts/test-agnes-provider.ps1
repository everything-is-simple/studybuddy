[CmdletBinding()]
param([string]$Profile)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'agnes-common.ps1')
try { $AgnesConfig = Get-AgnesConfig $Profile } catch { Write-Error $_.Exception.Message; exit 2 }

$python = if ($env:STUDYBUDDY_PYTHON) { $env:STUDYBUDDY_PYTHON } else { 'python' }
$arguments = @('-m', 'pytest', 'backend/tests/test_real_provider_smoke.py', '-q')
Invoke-AgnesProcess $python $arguments $AgnesConfig
