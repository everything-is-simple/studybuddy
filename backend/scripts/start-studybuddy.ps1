[CmdletBinding()]
param(
    [string]$DataRoot = $env:STUDYBUDDY_DATA_ROOT,
    [int]$Port = 8787,
    [string]$Python = $env:STUDYBUDDY_PYTHON
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not $DataRoot) { throw 'data_root_required' }
if ($Port -lt 1024 -or $Port -gt 65535) { throw 'invalid_port' }
if (-not $Python) {
    $candidate = 'C:/miniconda/py310/python.exe'
    $Python = if (Test-Path $candidate) { $candidate } else { 'python' }
}
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$resolvedRoot = [System.IO.Path]::GetFullPath($DataRoot)
New-Item -ItemType Directory -Force -Path $resolvedRoot | Out-Null
$pidPath = Join-Path $resolvedRoot '.studybuddy.pid'
if (Test-Path $pidPath) {
    $oldPid = 0
    [int]::TryParse((Get-Content -Raw -LiteralPath $pidPath), [ref]$oldPid) | Out-Null
    if ($oldPid -gt 0 -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) { throw 'data_root_in_use' }
    Remove-Item -Force -LiteralPath $pidPath -ErrorAction SilentlyContinue
}
$env:STUDYBUDDY_DATA_ROOT = $resolvedRoot
$env:STUDYBUDDY_HOST = '127.0.0.1'
$env:STUDYBUDDY_PORT = [string]$Port
$env:STUDYBUDDY_REPORT_DELIVERY_MODE = 'off'
$env:STUDYBUDDY_REPORT_DELIVERY_ENABLED = 'false'
$env:STUDYBUDDY_REPORT_DELIVERY_AUTHORIZED = 'false'

Push-Location $root
try {
    $argumentList = "-m backend.app serve --data-root `"$resolvedRoot`""
    $process = Start-Process -FilePath $Python -ArgumentList $argumentList -WorkingDirectory $root -PassThru -WindowStyle Hidden
    Set-Content -LiteralPath $pidPath -Value ([string]$process.Id) -NoNewline
    Start-Sleep -Milliseconds 300
    $process.Refresh()
    if ($process.HasExited) {
        Remove-Item -Force -LiteralPath $pidPath -ErrorAction SilentlyContinue
        throw 'studybuddy_start_failed'
    }
    Write-Output "studybuddy_started"
} finally {
    Pop-Location
}
