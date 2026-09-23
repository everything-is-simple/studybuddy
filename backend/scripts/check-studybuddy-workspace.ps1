[CmdletBinding()]
param(
    [string]$WorkspaceRoot = 'H:\',
    [switch]$RequireDatabase
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = [System.IO.Path]::GetFullPath($WorkspaceRoot).TrimEnd('\')
$checks = [System.Collections.Generic.List[object]]::new()

function Add-Check([string]$Name, [string]$Status, [string]$Detail = '') {
    $checks.Add([pscustomobject]@{ name = $Name; status = $Status; detail = $Detail })
}

$directories = @(
    @{ name = 'source'; path = (Join-Path $root 'studybuddy'); marker = 'README.md' },
    @{ name = 'data_root'; path = (Join-Path $root 'studybuddy-data'); marker = 'config' },
    @{ name = 'log_root'; path = (Join-Path $root 'studybuddy-log'); marker = $null },
    @{ name = 'composer'; path = (Join-Path $root 'studybuddy-composer'); marker = 'B0-COMPONENT-GOVERNANCE.md' },
    @{ name = 'integration'; path = (Join-Path $root 'studybuddy-integration'); marker = 'README.md' },
    @{ name = 'test'; path = (Join-Path $root 'studybuddy-test'); marker = 'README.md' },
    @{ name = 'china_textbook'; path = (Join-Path $root 'studybuddy-ChinaTextbook'); marker = 'README.md' }
)

foreach ($item in $directories) {
    if (-not (Test-Path -LiteralPath $item.path -PathType Container)) {
        Add-Check $item.name 'not_installed'
        continue
    }
    if ($item.marker -and -not (Test-Path -LiteralPath (Join-Path $item.path $item.marker))) {
        Add-Check $item.name 'failed'
    } else {
        Add-Check $item.name 'available'
    }
}

$dataRoot = Join-Path $root 'studybuddy-data'
$database = Join-Path $dataRoot 'studybuddy.sqlite3'
if (Test-Path -LiteralPath $database -PathType Leaf) {
    Add-Check 'data_root_database' 'available'
} elseif ($RequireDatabase) {
    Add-Check 'data_root_database' 'failed'
} else {
    Add-Check 'data_root_database' 'not_initialized'
}

$liveRoot = Join-Path $dataRoot 'live'
if (Test-Path -LiteralPath $liveRoot) {
    Add-Check 'retired_live_root' 'failed'
} else {
    Add-Check 'retired_live_root' 'clear'
}

$composerManifest = Join-Path $root 'studybuddy-composer/manifests/b0-catalog.json'
$integrationResults = Join-Path $root 'studybuddy-integration/results'
$testFixtures = Join-Path $root 'studybuddy-test/fixtures'
Add-Check 'composer_catalog' ($(if (Test-Path -LiteralPath $composerManifest -PathType Leaf) { 'available' } else { 'failed' }))
Add-Check 'integration_results_root' ($(if (Test-Path -LiteralPath $integrationResults -PathType Container) { 'available' } else { 'not_initialized' }))
Add-Check 'test_fixtures_root' ($(if (Test-Path -LiteralPath $testFixtures -PathType Container) { 'available' } else { 'failed' }))

$failed = @($checks | Where-Object { $_.status -in @('failed', 'not_installed') }).Count
[pscustomobject]@{
    status = $(if ($failed -eq 0) { 'ok' } else { 'failed' })
    checks = $checks
} | ConvertTo-Json -Depth 4 -Compress
if ($failed -gt 0) { exit 1 }

