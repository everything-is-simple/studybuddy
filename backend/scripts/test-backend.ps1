[CmdletBinding()]
param(
    [switch]$FullOutput
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$projectPython = 'C:/miniconda/py310/python.exe'
$python = if ($env:STUDYBUDDY_PYTHON) { $env:STUDYBUDDY_PYTHON } elseif (Test-Path $projectPython) { $projectPython } else { 'python' }
$defaultBaseTemp = Join-Path (Split-Path $root -Parent) 'studybuddy-test/runs/pytest-basetemp'
$baseTemp = if ($env:STUDYBUDDY_PYTEST_BASETEMP) { $env:STUDYBUDDY_PYTEST_BASETEMP } else { $defaultBaseTemp }
New-Item -ItemType Directory -Force -Path $baseTemp | Out-Null
$args = @('-m', 'pytest', 'backend/tests/', '-q', "--basetemp=$baseTemp", '-p', 'no:cacheprovider')
if (-not $FullOutput) { $args += '--tb=short' }

Push-Location $root
try {
    & $python @args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
