Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'agnes-common.ps1')

$python = if ($env:STUDYBUDDY_PYTHON) { $env:STUDYBUDDY_PYTHON } else { 'python' }
$arguments = @('-m', 'pytest', 'backend/tests/test_real_provider_smoke.py', '-q')
Invoke-AgnesProcess $python $arguments $AgnesConfig
