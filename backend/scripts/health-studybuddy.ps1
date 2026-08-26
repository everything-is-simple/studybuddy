[CmdletBinding()]
param(
    [int]$Port = 8787,
    [string]$BaseUrl
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Port -lt 1024 -or $Port -gt 65535) { throw 'invalid_port' }
$base = if ($BaseUrl) { $BaseUrl.TrimEnd('/') } else { "http://127.0.0.1:$Port" }
try {
    $liveness = Invoke-RestMethod -Uri "$base/api/liveness" -Method Get -TimeoutSec 5
    $health = Invoke-WebRequest -Uri "$base/api/health" -Method Get -TimeoutSec 5 -SkipHttpErrorCheck
    $readiness = Invoke-WebRequest -Uri "$base/api/readiness" -Method Get -TimeoutSec 5 -SkipHttpErrorCheck
    [pscustomobject]@{
        liveness = $liveness.status
        health_status = [int]$health.StatusCode
        readiness_status = [int]$readiness.StatusCode
    } | ConvertTo-Json -Compress
    if ([int]$health.StatusCode -ne 200 -or [int]$readiness.StatusCode -ne 200) { exit 1 }
} catch {
    Write-Output '{"status":"unavailable","error_code":"health_check_failed"}'
    exit 1
}
