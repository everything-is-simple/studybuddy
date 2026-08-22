[CmdletBinding()]
param([string]$Profile)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'agnes-common.ps1')
try { $AgnesConfig = Get-AgnesConfig $Profile } catch { Write-Error $_.Exception.Message; exit 2 }

$node = if ($env:STUDYBUDDY_NODE) { $env:STUDYBUDDY_NODE } else { (Get-Command 'npx.cmd' -ErrorAction Stop).Source }
$arguments = @('playwright', 'test', 'H:/studybuddy/backend/tests/browser_qa.spec.js', '--workers=1', '--reporter=line')
$info = New-AgnesProcessInfo -FilePath $node -Arguments $arguments -Config $AgnesConfig
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
