Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'agnes-common.ps1')

$node = if ($env:STUDYBUDDY_NODE) { $env:STUDYBUDDY_NODE } else { 'npx.cmd' }
$info = New-AgnesProcessInfo $node @('playwright', 'test', 'H:/studybuddy/backend/tests/browser_qa.spec.js', '--workers=1', '--reporter=line') $AgnesConfig
$info.EnvironmentVariables['STUDYBUDDY_RUN_REAL_PROVIDER_SMOKE'] = '0'
$info.EnvironmentVariables.Remove('STUDYBUDDY_REAL_PROVIDER_TARGET')
$info.EnvironmentVariables['STUDYBUDDY_RUN_REAL_PROVIDER_UI_SMOKE'] = '1'
$info.EnvironmentVariables['STUDYBUDDY_REAL_PROVIDER_UI_TARGET'] = 'agnes-ai-hub'
$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $info
if (-not $process.Start()) { throw 'agnes_ui_process_start_failed' }
$process.WaitForExit()
$code = $process.ExitCode
$process.Dispose()
exit $code
