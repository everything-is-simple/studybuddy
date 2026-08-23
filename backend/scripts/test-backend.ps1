[CmdletBinding()]
param(
    [switch]$FullOutput
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$projectPython = 'C:/miniconda/py310/python.exe'
$python = if ($env:STUDYBUDDY_PYTHON) { $env:STUDYBUDDY_PYTHON } elseif (Test-Path $projectPython) { $projectPython } else { 'python' }
$args = @('-m', 'pytest', 'backend/tests/', '-q')
if (-not $FullOutput) { $args += '--tb=short' }

Push-Location $root
try {
    & $python @args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
