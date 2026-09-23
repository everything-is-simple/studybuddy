[CmdletBinding()]
param(
    [int]$Port = 8787,
    [string]$BaseUrl,
    [ValidateRange(1, 60)]
    [int]$TimeoutSec = 10
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Port -lt 1024 -or $Port -gt 65535) { throw 'invalid_port' }
$base = if ($BaseUrl) { $BaseUrl.TrimEnd('/') } else { "http://127.0.0.1:$Port" }

function Get-Probe([string]$Path, [string]$ExpectedStatus) {
    $httpStatus = $null
    try {
        $request = [System.Net.HttpWebRequest]::Create("$base/api/$Path")
        $request.Method = 'GET'
        $request.Timeout = $TimeoutSec * 1000
        $request.ReadWriteTimeout = $TimeoutSec * 1000
        $request.KeepAlive = $false
        $response = $request.GetResponse()
        $httpStatus = [int]$response.StatusCode
        if ($httpStatus -ne 200) {
            $response.Dispose()
            return [pscustomobject]@{ state = 'http_error'; http_status = $httpStatus }
        }
        $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
        $content = $reader.ReadToEnd()
        $reader.Dispose()
        $response.Dispose()
        $payload = $content | ConvertFrom-Json
        if ($payload.status -ne $ExpectedStatus) {
            return [pscustomobject]@{ state = 'invalid_response'; http_status = $httpStatus }
        }
        return [pscustomobject]@{ state = 'ok'; http_status = $httpStatus }
    } catch {
        $exception = $_.Exception
        while ($exception -and $exception -isnot [System.Net.WebException] -and $exception.InnerException) {
            $exception = $exception.InnerException
        }
        if ($httpStatus -eq 200) {
            return [pscustomobject]@{ state = 'invalid_response'; http_status = 200 }
        }
        try {
            if ($exception -is [System.Net.WebException] -and $exception.Response) {
                $httpStatus = [int]$exception.Response.StatusCode
                $exception.Response.Dispose()
            }
        } catch { }
        if ($null -ne $httpStatus) {
            return [pscustomobject]@{ state = 'http_error'; http_status = $httpStatus }
        }
        if ($exception -is [System.Net.WebException]) {
            if ($exception.Status -eq [System.Net.WebExceptionStatus]::Timeout) {
                return [pscustomobject]@{ state = 'timeout'; http_status = $null }
            }
            if ($exception.Status -in @([System.Net.WebExceptionStatus]::ConnectFailure,
                                        [System.Net.WebExceptionStatus]::NameResolutionFailure,
                                        [System.Net.WebExceptionStatus]::ProxyNameResolutionFailure)) {
                return [pscustomobject]@{ state = 'unavailable'; http_status = $null }
            }
        }
        if ($exception -is [System.TimeoutException]) {
            return [pscustomobject]@{ state = 'timeout'; http_status = $null }
        }
        return [pscustomobject]@{ state = 'unavailable'; http_status = $null }
    }
}

$probes = [ordered]@{
    liveness = Get-Probe 'liveness' 'ok'
    health = Get-Probe 'health' 'ok'
    readiness = Get-Probe 'readiness' 'ready'
}
$states = @($probes.Values | ForEach-Object { $_.state })
$overall = if (@($states | Where-Object { $_ -ne 'ok' }).Count -eq 0) {
    'healthy'
} elseif (@($states | Where-Object { $_ -eq 'unavailable' }).Count -eq $states.Count) {
    'unavailable'
} else {
    'degraded'
}
[pscustomobject]@{ status = $overall; probes = $probes } | ConvertTo-Json -Compress -Depth 4
if ($overall -ne 'healthy') { exit 1 }
