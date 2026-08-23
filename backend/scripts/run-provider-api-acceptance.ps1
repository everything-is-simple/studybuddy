[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ProviderId,
    [Parameter(Mandatory = $true)][string]$ModelId,
    [Parameter(Mandatory = $true)][string]$BaseUrl
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$StableErrors = @(
    'provider_auth_failed', 'provider_forbidden', 'provider_rate_limited',
    'provider_quota_exceeded', 'provider_timeout', 'provider_unavailable',
    'provider_connection_failed', 'provider_protocol_error',
    'provider_schema_mismatch', 'provider_malformed_response',
    'provider_refusal', 'provider_output_too_large'
)

function Write-AcceptanceSummary([int]$AttemptsRun, [int]$Passed, [int]$Failed, [int]$Skipped, [string]$Result) {
    Write-Output "provider_acceptance_provider=$ProviderId"
    Write-Output "provider_acceptance_model=$ModelId"
    Write-Output 'provider_acceptance_gateway=explicit_argument'
    Write-Output "provider_acceptance_attempts_run=$AttemptsRun"
    Write-Output "provider_acceptance_passed=$Passed"
    Write-Output "provider_acceptance_failed=$Failed"
    Write-Output "provider_acceptance_skipped=$Skipped"
    Write-Output "provider_acceptance_result=$Result"
}

function Stop-NotRun([string]$Code) {
    Write-Output $Code
    Write-AcceptanceSummary 0 0 0 0 'not_run'
    exit 2
}

function Test-AcceptanceUrl([string]$Value) {
    $uri = $null
    return [Uri]::TryCreate($Value, [UriKind]::Absolute, [ref]$uri) -and
        $uri.Scheme -eq 'https' -and -not $uri.UserInfo -and -not $uri.Query -and -not $uri.Fragment
}

function Get-StableError([string]$Output) {
    foreach ($code in $StableErrors) {
        if ($Output -match "(?<![a-z_])$code(?![a-z_])") { return $code }
    }
    return 'provider_protocol_error'
}

if ($env:STUDYBUDDY_RUN_THREE_ATTEMPT_PROVIDER_ACCEPTANCE -ne '1') { Stop-NotRun 'provider_acceptance_not_enabled' }
if ($ProviderId -notmatch '^[a-z0-9][a-z0-9-]{0,63}$' -or
    [string]::IsNullOrWhiteSpace($ModelId) -or $ModelId.Length -gt 128 -or
    $ModelId -notmatch '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$') {
    Stop-NotRun 'invalid_provider_acceptance_config'
}
if (-not (Test-AcceptanceUrl $BaseUrl)) { Stop-NotRun 'invalid_ai_base_url' }
if ([string]::IsNullOrWhiteSpace($env:STUDYBUDDY_AI_API_KEY)) { Stop-NotRun 'provider_acceptance_configuration_incomplete' }
if ($env:STUDYBUDDY_AI_PROVIDER -and $env:STUDYBUDDY_AI_PROVIDER -ne $ProviderId) { Stop-NotRun 'provider_acceptance_target_mismatch' }
if ($env:STUDYBUDDY_AI_MODEL -and $env:STUDYBUDDY_AI_MODEL -ne $ModelId) { Stop-NotRun 'provider_acceptance_target_mismatch' }
if ($env:STUDYBUDDY_AI_BASE_URL -and $env:STUDYBUDDY_AI_BASE_URL.TrimEnd('/') -ne $BaseUrl.TrimEnd('/')) { Stop-NotRun 'provider_acceptance_target_mismatch' }

$projectPython = 'C:/miniconda/py310/python.exe'
$python = if ($env:STUDYBUDDY_PYTHON) { $env:STUDYBUDDY_PYTHON } elseif (Test-Path $projectPython) { $projectPython } else { 'python' }
$passed = 0
$failed = 0
$skipped = 0
$attemptsRun = 0

for ($attempt = 1; $attempt -le 3; $attempt++) {
    if ($passed -ge 2) {
        Write-Output "provider_acceptance_attempt=$attempt status=skipped reason=threshold_reached"
        $skipped++
        continue
    }
    if ($failed -ge 2) {
        Write-Output "provider_acceptance_attempt=$attempt status=skipped reason=threshold_unreachable"
        $skipped++
        continue
    }

    $dataRoot = Join-Path ([IO.Path]::GetTempPath()) ('studybuddy-provider-acceptance-' + [Guid]::NewGuid().ToString('N'))
    $pytestBase = Join-Path ([IO.Path]::GetTempPath()) ('studybuddy-provider-pytest-' + [Guid]::NewGuid().ToString('N'))
    $process = $null
    $attemptError = $null
    try {
        $info = [System.Diagnostics.ProcessStartInfo]::new()
        $info.FileName = $python
        $info.UseShellExecute = $false
        $info.CreateNoWindow = $true
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true
        $info.WorkingDirectory = (Join-Path $PSScriptRoot '../..')
        $info.Arguments = '"-m" "pytest" "backend/tests/test_real_provider_smoke.py" "-q" "--basetemp" "' + $pytestBase + '"'
        $info.EnvironmentVariables['PYTHONPATH'] = (Join-Path $PSScriptRoot '..')
        $info.EnvironmentVariables['STUDYBUDDY_DATA_ROOT'] = $dataRoot
        $info.EnvironmentVariables['STUDYBUDDY_RUN_REAL_PROVIDER_SMOKE'] = '1'
        $info.EnvironmentVariables['STUDYBUDDY_REAL_PROVIDER_TARGET'] = $ProviderId
        $info.EnvironmentVariables['STUDYBUDDY_AI_PROVIDER'] = $ProviderId
        $info.EnvironmentVariables['STUDYBUDDY_AI_MODEL'] = $ModelId
        $info.EnvironmentVariables['STUDYBUDDY_AI_BASE_URL'] = $BaseUrl.TrimEnd('/')
        $info.EnvironmentVariables['STUDYBUDDY_AI_API_KEY'] = $env:STUDYBUDDY_AI_API_KEY
        $process = [System.Diagnostics.Process]::new()
        $process.StartInfo = $info
        if (-not $process.Start()) { throw 'provider_connection_failed' }
        $output = $process.StandardOutput.ReadToEnd() + $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        $exitCode = $process.ExitCode
        $attemptsRun++
        if ($exitCode -eq 0) {
            $passed++
            Write-Output "provider_acceptance_attempt=$attempt status=passed"
        } else {
            $failed++
            Write-Output "provider_acceptance_attempt=$attempt status=failed error=$(Get-StableError $output)"
        }
    } catch {
        $attemptsRun++
        $failed++
        $attemptError = 'provider_connection_failed'
        Write-Output "provider_acceptance_attempt=$attempt status=failed error=$attemptError"
    } finally {
        if ($null -ne $process) { $process.Dispose() }
        if (Test-Path $dataRoot) { Remove-Item -LiteralPath $dataRoot -Recurse -Force -ErrorAction SilentlyContinue }
        if (Test-Path $pytestBase) { Remove-Item -LiteralPath $pytestBase -Recurse -Force -ErrorAction SilentlyContinue }
    }
}

$result = if ($passed -ge 2) { '2_of_3_passed' } else { '2_of_3_not_met' }
Write-AcceptanceSummary $attemptsRun $passed $failed $skipped $result
if ($result -eq '2_of_3_passed') { exit 0 }
exit 1
