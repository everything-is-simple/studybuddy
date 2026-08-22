Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'agnes-common.ps1')

$python = if ($env:STUDYBUDDY_PYTHON) { $env:STUDYBUDDY_PYTHON } else { 'python' }
$arguments = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8795')
$info = New-AgnesProcessInfo $python $arguments $AgnesConfig
$info.EnvironmentVariables.Remove('STUDYBUDDY_RUN_REAL_PROVIDER_SMOKE')
$info.EnvironmentVariables.Remove('STUDYBUDDY_REAL_PROVIDER_TARGET')
$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $info
if (-not $process.Start()) { throw 'agnes_server_start_failed' }
Write-Output 'agnes_server_started'
$process.WaitForExit()
exit $process.ExitCode
