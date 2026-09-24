[CmdletBinding()]
param(
    [switch]$FullOutput
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$pythonCandidates = @(
    $env:STUDYBUDDY_PYTHON,
    'D:/miniconda/py310/python.exe',
    'C:/miniconda/py310/python.exe'
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
$python = if ($pythonCandidates) { @($pythonCandidates)[0] } else { (Get-Command 'python' -ErrorAction Stop).Source }
$runStamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmssfff')
$defaultBaseTemp = Join-Path (Split-Path $root -Parent) "studybuddy-test/runs/pytest-$runStamp-$PID"
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
