[CmdletBinding()]
param([string]$Profile)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'agnes-common.ps1')
try { $AgnesConfig = Get-AgnesConfig $Profile } catch { Write-Error $_.Exception.Message; exit 2 }

$projectPython = 'D:/miniconda/py310/python.exe'
$python = if ($env:STUDYBUDDY_PYTHON) { $env:STUDYBUDDY_PYTHON } elseif (Test-Path $projectPython) { $projectPython } else { 'python' }
$arguments = @('-m', 'pytest', 'backend/tests/test_real_provider_smoke.py', '-q')
Invoke-AgnesProcess -FilePath $python -Arguments $arguments -Config $AgnesConfig
