Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$AgnesDefaultModels = @{
    budget = 'agnes-1.5-flash'
    balanced = 'agnes-2.0-flash'
    advanced = 'agnes-2.5-flash'
}

function Get-AgnesConfig([string]$Profile) {
    $provider = if ($env:STUDYBUDDY_AGNES_PROVIDER_ID) { $env:STUDYBUDDY_AGNES_PROVIDER_ID } else { 'agnes-ai-hub' }
    $model = $env:STUDYBUDDY_AGNES_MODEL
    if ($Profile) {
        if ($Profile -notmatch '^[a-z0-9][a-z0-9-]{0,31}$') { throw 'agnes_invalid_profile' }
        $modelVariable = 'STUDYBUDDY_AGNES_MODEL_' + ($Profile.ToUpperInvariant() -replace '-', '_')
        $model = [Environment]::GetEnvironmentVariable($modelVariable)
        if ([string]::IsNullOrWhiteSpace($model) -and $AgnesDefaultModels.ContainsKey($Profile)) { $model = $AgnesDefaultModels[$Profile] }
    }
    $baseUrl = if ($env:STUDYBUDDY_AGNES_BASE_URL) { $env:STUDYBUDDY_AGNES_BASE_URL } else { 'https://apihub.agnes-ai.com/v1' }
    $key = $env:STUDYBUDDY_AGNES_KEY
    if ($provider -ne 'agnes-ai-hub') { throw 'agnes_invalid_provider_id' }
    if ([string]::IsNullOrWhiteSpace($model) -or [string]::IsNullOrWhiteSpace($baseUrl) -or [string]::IsNullOrWhiteSpace($key)) {
        throw 'agnes_configuration_incomplete'
    }
    $uri = $null
    if (-not [Uri]::TryCreate($baseUrl, [UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -ne 'https' -or $uri.UserInfo -or $uri.Query -or $uri.Fragment) {
        throw 'invalid_ai_base_url'
    }
    [pscustomobject]@{
        Provider = $provider
        Model = $model
        BaseUrl = $baseUrl.TrimEnd('/')
        Key = $key
        Profile = $Profile
    }
}

function New-AgnesProcessInfo([string]$FilePath, [string[]]$Arguments, [object]$Config) {
    $info = [System.Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $FilePath
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.WorkingDirectory = (Join-Path $PSScriptRoot '../..')
    $info.EnvironmentVariables['PYTHONPATH'] = (Join-Path $PSScriptRoot '..')
    $info.Arguments = ($Arguments | ForEach-Object { '"' + $_.Replace('"', '\"') + '"' }) -join ' '
    $info.EnvironmentVariables['STUDYBUDDY_AI_PROVIDER'] = $Config.Provider
    $info.EnvironmentVariables['STUDYBUDDY_AI_MODEL'] = $Config.Model
    $info.EnvironmentVariables['STUDYBUDDY_AI_BASE_URL'] = $Config.BaseUrl
    $info.EnvironmentVariables['STUDYBUDDY_AI_API_KEY'] = $Config.Key
    $info.EnvironmentVariables['STUDYBUDDY_RUN_REAL_PROVIDER_SMOKE'] = '1'
    $info.EnvironmentVariables['STUDYBUDDY_REAL_PROVIDER_TARGET'] = 'agnes-ai-hub'
    if ($env:STUDYBUDDY_DATA_ROOT) { $info.EnvironmentVariables['STUDYBUDDY_DATA_ROOT'] = $env:STUDYBUDDY_DATA_ROOT }
    if ($env:STUDYBUDDY_PROJECT_ID) { $info.EnvironmentVariables['STUDYBUDDY_PROJECT_ID'] = $env:STUDYBUDDY_PROJECT_ID }
    if ($env:STUDYBUDDY_AI_TIMEOUT_SECONDS) { $info.EnvironmentVariables['STUDYBUDDY_AI_TIMEOUT_SECONDS'] = $env:STUDYBUDDY_AI_TIMEOUT_SECONDS }
    if ($env:STUDYBUDDY_AI_MAX_RETRIES) { $info.EnvironmentVariables['STUDYBUDDY_AI_MAX_RETRIES'] = $env:STUDYBUDDY_AI_MAX_RETRIES }
    $info
}

function Invoke-AgnesProcess([string]$FilePath, [string[]]$Arguments, [object]$Config) {
    $info = New-AgnesProcessInfo $FilePath $Arguments $Config
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $info
    if (-not $process.Start()) { throw 'agnes_child_process_start_failed' }
    $process.WaitForExit()
    $code = $process.ExitCode
    $process.Dispose()
    exit $code
}
