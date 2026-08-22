[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$Profile)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'agnes-common.ps1')
try { $AgnesConfig = Get-AgnesConfig $Profile } catch { Write-Error $_.Exception.Message; exit 2 }

$runner = Join-Path $PSScriptRoot 'run-provider-api-acceptance.ps1'
$info = [System.Diagnostics.ProcessStartInfo]::new()
$info.FileName = 'powershell.exe'
$info.UseShellExecute = $false
$info.CreateNoWindow = $true
$info.WorkingDirectory = (Join-Path $PSScriptRoot '../..')
$info.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $runner + '" -ProviderId "' + $AgnesConfig.Provider + '" -ModelId "' + $AgnesConfig.Model + '" -BaseUrl "' + $AgnesConfig.BaseUrl + '"'
$info.EnvironmentVariables['STUDYBUDDY_AI_PROVIDER'] = $AgnesConfig.Provider
$info.EnvironmentVariables['STUDYBUDDY_AI_MODEL'] = $AgnesConfig.Model
$info.EnvironmentVariables['STUDYBUDDY_AI_BASE_URL'] = $AgnesConfig.BaseUrl
$info.EnvironmentVariables['STUDYBUDDY_AI_API_KEY'] = $AgnesConfig.Key
$info.EnvironmentVariables['STUDYBUDDY_RUN_THREE_ATTEMPT_PROVIDER_ACCEPTANCE'] = $env:STUDYBUDDY_RUN_THREE_ATTEMPT_PROVIDER_ACCEPTANCE
$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $info
if (-not $process.Start()) { throw 'agnes_child_process_start_failed' }
$process.WaitForExit()
$code = $process.ExitCode
$process.Dispose()
exit $code
