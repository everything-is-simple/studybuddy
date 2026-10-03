[CmdletBinding()]
param(
    [string]$Python = 'D:\miniconda\py310\python.exe',
    [string]$NodeRoot = 'D:\nodejs',
    [string]$PowerShellRoot = 'D:\PowerShell\7',
    [string]$GitRoot = 'D:\Git',
    [string]$CygwinRoot = 'D:\cygwin64',
    [string]$PiRoot = 'C:\Users\Administrator\.pi',
    [string]$BaseUrl = 'http://127.0.0.1:8787',
    [switch]$SkipService,
    [switch]$IncludeOptionalTools
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
        if ($LASTEXITCODE -ne 0) { return $null }
        $match = [regex]::Match($output, 'v?\d+\.\d+(?:\.\d+)?')
        if ($match.Success) { return $match.Value }
        if ($output) { return 'installed' }
    } catch {}
    return $null
}

function Get-HttpStatus([string]$Uri) {
    $response = $null
    try {
        $request = [System.Net.HttpWebRequest]::Create($Uri)
        $request.Method = 'GET'
        $request.Timeout = 5000
        $request.ReadWriteTimeout = 5000
        $request.KeepAlive = $false
        $response = $request.GetResponse()
        return [int]$response.StatusCode
    } catch { return $null } finally {
        if ($response) { $response.Dispose() }
    }
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
        $versionOutput = (& $Python -m backend.app version 2>$null) -join ''
        if ($LASTEXITCODE -eq 0) {
            try {
                $versionPayload = $versionOutput | ConvertFrom-Json
                Add-Check 'studybuddy_version' 'available' ("$($versionPayload.application_version)/schema-$($versionPayload.schema_version)")
            } catch { Add-Check 'studybuddy_version' 'available' }
        } else { Add-Check 'studybuddy_version' 'failed' }
    } catch { Add-Check 'python_checks' 'failed' } finally { Pop-Location }
}

$node = Join-Path $NodeRoot 'node.exe'
if (Test-Path -LiteralPath $node) { $env:PATH = $NodeRoot + ';' + $env:PATH }
$tools = @(
    @{ name = 'powershell7'; command = (Join-Path $PowerShellRoot 'pwsh.exe'); args = @('-NoProfile', '-Command', '$PSVersionTable.PSVersion.ToString()') },
    @{ name = 'git'; command = (Join-Path $GitRoot 'cmd/git.exe'); args = @('--version') },
    @{ name = 'cygwin_bash'; command = (Join-Path $CygwinRoot 'bin/bash.exe'); args = @('--version') },
    @{ name = 'node'; command = $node; args = @('--version') },
    @{ name = 'npm'; command = (Join-Path $NodeRoot 'npm.cmd'); args = @('--version') },
    @{ name = 'pi'; command = (Join-Path $PiRoot 'agent/bin/pi.cmd'); args = @('--version') }
)
if ($IncludeOptionalTools) {
    foreach ($name in @('omp', 'codex', 'claude')) {
        $commandInfo = Get-Command $name -ErrorAction SilentlyContinue
        if ($commandInfo) { $tools += @{ name = $name; command = $commandInfo.Source; args = @('--version') } }
    }
}
foreach ($tool in $tools) {
    if (-not (Test-Path -LiteralPath $tool.command)) { Add-Check $tool.name 'not_installed'; continue }
    $version = Get-VersionText $tool.command $tool.args
    Add-Check $tool.name ($(if ($version) { 'available' } else { 'failed' })) $version
}

$playwright = Join-Path $root 'node_modules/.bin/playwright.cmd'
if (Test-Path -LiteralPath $playwright) {
    $version = Get-VersionText $playwright @('--version')
    Add-Check 'playwright' ($(if ($version) { 'available' } else { 'failed' })) $version
} else { Add-Check 'playwright' 'not_installed' }

if (-not $SkipService) {
    foreach ($endpoint in @('liveness', 'health', 'readiness')) {
        $httpStatus = Get-HttpStatus "$($BaseUrl.TrimEnd('/'))/api/$endpoint"
        Add-Check "service_$endpoint" ($(if ($httpStatus -eq 200) { 'available' } else { 'unavailable' })) ([string]$httpStatus)
    }
    foreach ($endpoint in @('system/settings', 'system/capabilities', 'ai/capabilities')) {
        $httpStatus = Get-HttpStatus "$($BaseUrl.TrimEnd('/'))/api/$endpoint"
        Add-Check ("api_" + ($endpoint -replace '/', '_')) ($(if ($httpStatus -eq 200) { 'available' } else { 'unavailable' })) ([string]$httpStatus)
    }
}

$failed = @($results | Where-Object { $_.status -in @('failed', 'unavailable', 'not_installed') }).Count
[pscustomobject]@{
    status = $(if ($failed -eq 0) { 'ok' } else { 'failed' })
    checks = $results
} | ConvertTo-Json -Depth 4 -Compress
if ($failed -gt 0) { exit 1 }
