[CmdletBinding()]
param(
    [string]$DataRoot = $env:STUDYBUDDY_DATA_ROOT,
    [int]$TimeoutSeconds = 10
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not $DataRoot) { throw 'data_root_required' }
if ($TimeoutSeconds -lt 1 -or $TimeoutSeconds -gt 120) { throw 'invalid_timeout' }
$pidPath = Join-Path ([System.IO.Path]::GetFullPath($DataRoot)) '.studybuddy.pid'
if (-not (Test-Path $pidPath)) { Write-Output 'studybuddy_not_running'; exit 0 }
$processId = 0
[int]::TryParse((Get-Content -Raw -LiteralPath $pidPath), [ref]$processId) | Out-Null
if ($processId -le 0) { Remove-Item -Force -LiteralPath $pidPath; throw 'studybuddy_pid_invalid' }
$process = Get-Process -Id $processId -ErrorAction SilentlyContinue
if (-not $process) { Remove-Item -Force -LiteralPath $pidPath; Write-Output 'studybuddy_not_running'; exit 0 }
try { $process.CloseMainWindow() | Out-Null } catch { throw 'studybuddy_stop_failed' }
$process.Refresh()
if (-not $process.WaitForExit($TimeoutSeconds * 1000)) { throw 'studybuddy_stop_timeout' }
Remove-Item -Force -LiteralPath $pidPath -ErrorAction SilentlyContinue
Write-Output 'studybuddy_stopped'
