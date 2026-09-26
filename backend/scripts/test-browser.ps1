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
$env:STUDYBUDDY_FIXTURE_ROOT = $testRootBase
$env:STUDYBUDDY_BACKEND_ROOT = $backend
$pythonCandidates = @(
    $Python,
    'D:/miniconda/py310/python.exe',
    'C:/miniconda/py310/python.exe'
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
if ($pythonCandidates) { $env:STUDYBUDDY_PYTHON = @($pythonCandidates)[0] }
$python = if ($env:STUDYBUDDY_PYTHON) { $env:STUDYBUDDY_PYTHON } else { (Get-Command python -ErrorAction Stop).Source }
$npx = if ($env:STUDYBUDDY_NPX) { $env:STUDYBUDDY_NPX } else { (Get-Command 'npx.cmd' -ErrorAction Stop).Source }
if ($Install) {
    & $npx playwright install chromium
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$paths = foreach ($item in $Spec) {
    if ($item -match '[\\/]') { $item } else { "backend/tests/$item" }
}
Push-Location $root
$sharedService = $null
try {
    $sharedPort = 0
    foreach ($candidate in 8800..8899) {
        if (-not (Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $candidate -State Listen -ErrorAction SilentlyContinue)) {
            $sharedPort = $candidate
            break
        }
    }
    if ($sharedPort -eq 0) { throw 'browser_shared_service_port_unavailable' }

    $sharedDataRoot = Join-Path $testRoot 'shared-service'
    New-Item -ItemType Directory -Force -Path $sharedDataRoot | Out-Null
    $env:STUDYBUDDY_BASE_URL = "http://127.0.0.1:$sharedPort"
    $sharedService = Start-Job -Name "StudyBuddyBrowser-$PID" -ScriptBlock {
        param($BackendRoot, $DataRoot, $Port, $PythonPath)
        $env:PYTHONPATH = $BackendRoot
        $env:STUDYBUDDY_DATA_ROOT = $DataRoot
        $env:STUDYBUDDY_AI_PROVIDER = 'fake'
        Remove-Item Env:STUDYBUDDY_AI_API_KEY,Env:STUDYBUDDY_AI_BASE_URL,Env:STUDYBUDDY_AI_MODEL -ErrorAction SilentlyContinue
        $env:STUDYBUDDY_ASR_PROVIDER = 'fake'
        $env:STUDYBUDDY_ASR_MODEL = 'fake-capture-v1'
        Remove-Item Env:STUDYBUDDY_ASR_RUNTIME,Env:STUDYBUDDY_ASR_MODEL_PATH -ErrorAction SilentlyContinue
        Set-Location $BackendRoot
        & $PythonPath -m uvicorn app.main:app --host 127.0.0.1 --port $Port 2>&1
    } -ArgumentList $backend, $sharedDataRoot, $sharedPort, $python

    $sharedReady = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "$($env:STUDYBUDDY_BASE_URL)/api/health" -TimeoutSec 2
            if ($health.status -eq 'ok') { $sharedReady = $true; break }
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }
    if (-not $sharedReady) {
        Receive-Job -Job $sharedService -Keep | Select-Object -Last 20
        throw 'browser_shared_service_health_failed'
    }

    # Browser evidence is serial by policy; each spec owns its isolated runtime data.
    # Pass the resolved array as a native-command argument value.  `@paths`
    # is not PowerShell array splatting and silently caused Playwright to
    # ignore the requested spec after the environment rebuild.
    & $npx playwright test $paths '--workers=1' '--reporter=line'
    exit $LASTEXITCODE
} finally {
    if ($sharedService) { Remove-Job -Job $sharedService -Force -ErrorAction SilentlyContinue }
    Pop-Location
}
