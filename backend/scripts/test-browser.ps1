[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)][string[]]$Spec,
    [switch]$Install,
    [string]$Python = $env:STUDYBUDDY_PYTHON,
    [string]$TestRoot = $env:STUDYBUDDY_TEST_ROOT
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$backend = Join-Path $root 'backend'
$workspaceParent = Split-Path $root -Parent
$testRootBase = [System.IO.Path]::GetFullPath((Join-Path $workspaceParent 'studybuddy-test')).TrimEnd('\')
$productionRoot = [System.IO.Path]::GetFullPath((Join-Path $workspaceParent 'studybuddy-data')).TrimEnd('\')
$testRoot = if ($TestRoot) {
    [System.IO.Path]::GetFullPath($TestRoot)
} else {
    Join-Path $workspaceParent ("studybuddy-test/runs/browser-{0}-{1}" -f [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmssfff'), $PID)
}
$normalizedTestRoot = $testRoot.TrimEnd('\')
if ($normalizedTestRoot.Equals($productionRoot, [StringComparison]::OrdinalIgnoreCase) -or
    $normalizedTestRoot.StartsWith($productionRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'browser_test_root_must_not_be_production_data_root'
}
if (-not ($normalizedTestRoot.Equals($testRootBase, [StringComparison]::OrdinalIgnoreCase) -or
    $normalizedTestRoot.StartsWith($testRootBase + '\', [StringComparison]::OrdinalIgnoreCase))) {
    throw 'browser_test_root_must_be_under_studybuddy_test'
}
New-Item -ItemType Directory -Force -Path $testRoot | Out-Null
$env:STUDYBUDDY_TEST_ROOT = $testRoot
$env:STUDYBUDDY_BACKEND_ROOT = $backend
$pythonCandidates = @(
    $Python,
    'D:/miniconda/py310/python.exe',
    'C:/miniconda/py310/python.exe'
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
if ($pythonCandidates) { $env:STUDYBUDDY_PYTHON = @($pythonCandidates)[0] }
$npx = if ($env:STUDYBUDDY_NPX) { $env:STUDYBUDDY_NPX } else { (Get-Command 'npx.cmd' -ErrorAction Stop).Source }
if ($Install) {
    & $npx playwright install chromium
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$paths = foreach ($item in $Spec) {
    if ($item -match '[\\/]') { $item } else { "backend/tests/$item" }
}
Push-Location $root
try {
    # Browser evidence is serial by policy; each spec owns its isolated runtime data.
    # Pass the resolved array as a native-command argument value.  `@paths`
    # is not PowerShell array splatting and silently caused Playwright to
    # ignore the requested spec after the environment rebuild.
    & $npx playwright test $paths '--workers=1' '--reporter=line'
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
