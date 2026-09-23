[CmdletBinding()]
param(
    [string]$Python = 'D:\miniconda\py310\python.exe',
    [string]$BaseUrl = 'http://127.0.0.1:8787',
    [switch]$SkipService
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$results = [System.Collections.Generic.List[object]]::new()

function Add-Check([string]$Name, [string]$Status, [string]$Detail = '') {
    $results.Add([pscustomobject]@{ name = $Name; status = $Status; detail = $Detail })
}

function Get-VersionText([string]$Command, [string[]]$Arguments) {
    try {
        $output = (& $Command @Arguments 2>$null | Select-Object -First 3) -join ' '
        $match = [regex]::Match($output, 'v?\d+\.\d+(?:\.\d+)?')
        if ($match.Success) { return $match.Value }
        if ($output) { return 'installed' }
    } catch {}
    return $null
}

if (-not (Test-Path -LiteralPath $Python)) {
    Add-Check 'python' 'not_installed'
} else {
    $pythonVersion = Get-VersionText $Python @('--version')
    if ($pythonVersion) { Add-Check 'python' 'available' $pythonVersion } else { Add-Check 'python' 'failed' }
    try {
        Push-Location $root
        $null = & $Python -c 'import fastapi, uvicorn, pydantic, multipart, docx, pypdf, fitz, pptx, pytest, httpx' 2>$null
        Add-Check 'python_imports' ($(if ($LASTEXITCODE -eq 0) { 'available' } else { 'failed' }))
        $null = & $Python -m pip check 2>$null
        Add-Check 'pip_check' ($(if ($LASTEXITCODE -eq 0) { 'available' } else { 'failed' }))
        $null = & $Python -m backend.app version 2>$null
        Add-Check 'studybuddy_version' ($(if ($LASTEXITCODE -eq 0) { 'available' } else { 'failed' }))
    } catch { Add-Check 'python_checks' 'failed' } finally { Pop-Location }
}

foreach ($tool in @(
    @{ name = 'node'; command = 'node'; args = @('--version') },
    @{ name = 'npm'; command = 'npm'; args = @('--version') },
    @{ name = 'pi'; command = 'pi'; args = @('--version') },
    @{ name = 'omp'; command = 'omp'; args = @('--version') },
    @{ name = 'codex'; command = 'codex'; args = @('--version') },
    @{ name = 'claude'; command = 'claude'; args = @('--version') }
)) {
    $commandInfo = Get-Command $tool.command -ErrorAction SilentlyContinue
    if (-not $commandInfo) { Add-Check $tool.name 'not_installed'; continue }
    $version = Get-VersionText $commandInfo.Source $tool.args
    Add-Check $tool.name ($(if ($version) { 'available' } else { 'failed' })) $version
}

$playwright = Join-Path $root 'node_modules/.bin/playwright.cmd'
if (Test-Path -LiteralPath $playwright) {
    $version = Get-VersionText $playwright @('--version')
    Add-Check 'playwright' ($(if ($version) { 'available' } else { 'failed' })) $version
} else { Add-Check 'playwright' 'not_installed' }

if (-not $SkipService) {
    foreach ($endpoint in @('liveness', 'health', 'readiness')) {
        try {
            $response = Invoke-WebRequest -Uri "$($BaseUrl.TrimEnd('/'))/api/$endpoint" -UseBasicParsing -TimeoutSec 5
            Add-Check "service_$endpoint" ($(if ([int]$response.StatusCode -eq 200) { 'available' } else { 'failed' })) ([string]$response.StatusCode)
        } catch { Add-Check "service_$endpoint" 'unavailable' }
    }
}

$failed = @($results | Where-Object { $_.status -in @('failed', 'unavailable', 'not_installed') }).Count
[pscustomobject]@{
    status = $(if ($failed -eq 0) { 'ok' } else { 'failed' })
    checks = $results
} | ConvertTo-Json -Depth 4 -Compress
if ($failed -gt 0) { exit 1 }
