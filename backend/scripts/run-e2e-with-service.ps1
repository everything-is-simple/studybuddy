# Run the browser coverage suite against an isolated local test service.

[CmdletBinding()]
param(
    [int]$ServiceStartWait = 15,
    [int]$HealthCheckRetries = 10,
    [int]$Port = 0,
    [string]$DataRoot = $env:STUDYBUDDY_E2E_DATA_ROOT,
    [string]$Spec = 'browser_e2e_full_coverage.spec.js'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$workspaceParent = Split-Path $root -Parent
$testRootBase = [System.IO.Path]::GetFullPath((Join-Path $workspaceParent 'studybuddy-test')).TrimEnd('\')
$productionRoot = [System.IO.Path]::GetFullPath((Join-Path $workspaceParent 'studybuddy-data')).TrimEnd('\')
$pythonCandidates = @($env:STUDYBUDDY_PYTHON, 'D:/miniconda/py310/python.exe', 'C:/miniconda/py310/python.exe') |
    Where-Object { $_ -and (Test-Path -LiteralPath $_) }
$python = if ($pythonCandidates) { @($pythonCandidates)[0] } else { (Get-Command python -ErrorAction Stop).Source }

if (-not $DataRoot) {
    $DataRoot = Join-Path $testRootBase ('runs/e2e-service-{0}-{1}' -f [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmssfff'), $PID)
}
$resolvedDataRoot = [System.IO.Path]::GetFullPath($DataRoot).TrimEnd('\')
if ($resolvedDataRoot.Equals($productionRoot, [StringComparison]::OrdinalIgnoreCase) -or
    $resolvedDataRoot.StartsWith($productionRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'e2e_data_root_must_not_be_production_data_root'
}
if (-not ($resolvedDataRoot.Equals($testRootBase, [StringComparison]::OrdinalIgnoreCase) -or
    $resolvedDataRoot.StartsWith($testRootBase + '\', [StringComparison]::OrdinalIgnoreCase))) {
    throw 'e2e_data_root_must_be_under_studybuddy_test'
}
New-Item -ItemType Directory -Force -Path $resolvedDataRoot | Out-Null

function Test-Port {
    param([int]$CandidatePort)
    return $null -ne (Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $CandidatePort -State Listen -ErrorAction SilentlyContinue)
}

if ($Port -eq 0) {
    foreach ($candidate in 8800..8899) {
        if (-not (Test-Port $candidate)) { $Port = $candidate; break }
    }
}
if ($Port -le 0 -or (Test-Port $Port)) { throw 'e2e_loopback_port_unavailable' }

$env:STUDYBUDDY_DATA_ROOT = $resolvedDataRoot
$env:STUDYBUDDY_PORT = [string]$Port
$env:STUDYBUDDY_BASE_URL = "http://127.0.0.1:$Port"
$env:STUDYBUDDY_TEST_ROOT = $testRootBase
$env:STUDYBUDDY_BACKEND_ROOT = Join-Path $root 'backend'
$env:STUDYBUDDY_PYTHON = $python

Write-Host "Starting isolated StudyBuddy E2E service on $($env:STUDYBUDDY_BASE_URL)"
Write-Host "Data root: $resolvedDataRoot"

$serviceJob = Start-Job -Name "StudyBuddyE2E-$PID" -ScriptBlock {
    param($ProjectRoot, $ServiceDataRoot, $ServicePort, $PythonPath)
    $env:STUDYBUDDY_DATA_ROOT = $ServiceDataRoot
    $env:STUDYBUDDY_PORT = [string]$ServicePort
    $env:STUDYBUDDY_AI_PROVIDER = 'fake'
    Remove-Item Env:STUDYBUDDY_AI_API_KEY,Env:STUDYBUDDY_AI_BASE_URL,Env:STUDYBUDDY_AI_MODEL -ErrorAction SilentlyContinue
    Set-Location $ProjectRoot
    & $PythonPath -m backend.app serve 2>&1
} -ArgumentList $root, $resolvedDataRoot, $Port, $python

$testExitCode = 1
try {
    Start-Sleep -Seconds $ServiceStartWait
    $healthy = $false
    for ($i = 1; $i -le $HealthCheckRetries; $i++) {
        try {
            $response = Invoke-RestMethod -Uri "$($env:STUDYBUDDY_BASE_URL)/api/health" -Method Get -TimeoutSec 3
            if ($response.status -eq 'ok') { $healthy = $true; break }
        } catch {
            if ($i -lt $HealthCheckRetries) { Start-Sleep -Seconds 2 }
        }
    }
    if (-not $healthy) {
        Receive-Job -Job $serviceJob | Select-Object -Last 30
        throw 'e2e_service_health_failed'
    }
    $paths = if ($Spec -match '[\\/]') { $Spec } else { "backend/tests/$Spec" }
    & (Get-Command npx.cmd -ErrorAction Stop).Source playwright test $paths '--workers=1' '--reporter=line' '--timeout=60000'
    $testExitCode = $LASTEXITCODE
} finally {
    if ($serviceJob) { Remove-Job -Job $serviceJob -Force -ErrorAction SilentlyContinue }
}
exit $testExitCode
