<#
.SYNOPSIS
StudyBuddy 后台监控进程：记录操作、检测错误并自动纠正。

.DESCRIPTION
以守护循环运行：
1. 若后端未运行则启动（stdout/stderr 重定向到 data_root\logs 下带时间戳的文件）。
2. 持续 tail 服务端日志，把每个 HTTP 请求（用户操作）写入 operations.jsonl。
3. 检测错误（Traceback / ERROR / 5xx / 进程退出 / 健康检查失败），写入 monitor-journal.jsonl。
4. 可安全自动纠正的异常立即纠正（重启后端、清理陈旧 pid、启动失败退避重试），纠正动作全部记录。
5. 其余错误仅记录（kind=error），留待人工修复——不做超出安全范围的自动改动。

.NOTES
日志与账本均写在 data_root 下（logs/），不落入主仓库。
停止监控：Stop-Process -Id (Get-Content <data_root>\logs\monitor.pid)
#>
[CmdletBinding()]
param(
    [string]$DataRoot = $env:STUDYBUDDY_DATA_ROOT,
    [int]$Port = 8787,
    [string]$Python,
    [int]$PollSeconds = 3
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
$DataRoot = [System.IO.Path]::GetFullPath($DataRoot)
$logDir = Join-Path $DataRoot 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$journalPath = Join-Path $logDir 'monitor-journal.jsonl'
$operationsPath = Join-Path $logDir 'operations.jsonl'
$monitorPidPath = Join-Path $logDir 'monitor.pid'
$pidPath = Join-Path $DataRoot '.studybuddy.pid'

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
function Write-Journal([string]$kind, [hashtable]$fields) {
    $entry = @{ timestamp = (Get-Date).ToString('o'); kind = $kind }
    foreach ($k in $fields.Keys) { $entry[$k] = $fields[$k] }
    $line = $entry | ConvertTo-Json -Compress -Depth 4
    [System.IO.File]::AppendAllText($journalPath, $line + "`n", $utf8NoBom)
}
Set-Content -LiteralPath $monitorPidPath -Value ([string]$PID) -NoNewline

# ---- 服务器进程管理 -------------------------------------------------------
$script:serverLogOut = $null
$script:serverLogErr = $null

function Get-ServerProcess {
    if (-not (Test-Path $pidPath)) { return $null }
    $old = 0
    [int]::TryParse((Get-Content -Raw -LiteralPath $pidPath), [ref]$old) | Out-Null
    if ($old -le 0) { return $null }
    return Get-Process -Id $old -ErrorAction SilentlyContinue
}

function Start-Server {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $script:serverLogOut = Join-Path $logDir "server-out-$stamp.log"
    $script:serverLogErr = Join-Path $logDir "server-err-$stamp.log"
    $env:STUDYBUDDY_DATA_ROOT = $DataRoot
    $env:STUDYBUDDY_HOST = '127.0.0.1'
    $env:STUDYBUDDY_PORT = [string]$Port
    $env:STUDYBUDDY_REPORT_DELIVERY_MODE = 'off'
    $env:STUDYBUDDY_REPORT_DELIVERY_ENABLED = 'false'
    $env:STUDYBUDDY_REPORT_DELIVERY_AUTHORIZED = 'false'
    $proc = Start-Process -FilePath $Python `
        -ArgumentList "-m backend.app serve --data-root `"$DataRoot`"" `
        -WorkingDirectory $root -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $script:serverLogOut `
        -RedirectStandardError $script:serverLogErr
    Set-Content -LiteralPath $pidPath -Value ([string]$proc.Id) -NoNewline
    Start-Sleep -Milliseconds 800
    $proc.Refresh()
    if ($proc.HasExited) {
        Remove-Item -Force -LiteralPath $pidPath -ErrorAction SilentlyContinue
        return $null
    }
    $script:gracePolls = 4  # 冷启动宽限：跳过随后几轮 liveness 检查，避免误判重启
    return $proc
}

function Restart-Server([string]$reason) {
    Write-Journal 'correction' @{ action = 'restart_server'; reason = $reason }
    $old = Get-ServerProcess
    if ($old) { try { Stop-Process -Id $old.Id -Force -ErrorAction SilentlyContinue } catch {} }
    Remove-Item -Force -LiteralPath $pidPath -ErrorAction SilentlyContinue
    $proc = Start-Server
    if ($proc) {
        Write-Journal 'correction' @{ action = 'restart_server_done'; pid = $proc.Id }
        return $true
    }
    Write-Journal 'correction' @{ action = 'restart_server_failed'; reason = 'start_failed' }
    return $false
}

# ---- 日志 tail（按字节偏移，处理截断与半行） -------------------------------
$script:offsets = @{}
$script:pending = @{}

function Read-NewLines([string]$path) {
    if (-not $path -or -not (Test-Path $path)) { return @() }
    $fi = Get-Item $path
    $off = 0
    if ($script:offsets.ContainsKey($path)) { $off = [int]$script:offsets[$path] }
    if ($fi.Length -lt $off) { $off = 0; $script:pending[$path] = '' }  # 文件被重建/轮转
    if ($fi.Length -eq $off) { return @() }
    $fs = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
        [void]$fs.Seek($off, [System.IO.SeekOrigin]::Begin)
        $bytes = New-Object byte[] ([int]($fi.Length - $off))
        $read = 0
        while ($read -lt $bytes.Length) {
            $n = $fs.Read($bytes, $read, $bytes.Length - $read)
            if ($n -le 0) { break }
            $read += $n
        }
    } finally { $fs.Close() }
    $script:offsets[$path] = $off + $read
    $text = $script:pending[$path] + [System.Text.Encoding]::UTF8.GetString($bytes, 0, $read)
    if (-not $text) { return @() }
    if ($text -notmatch "`n$") {
        $idx = $text.LastIndexOf("`n")
        if ($idx -lt 0) { $script:pending[$path] = $text; return @() }
        $script:pending[$path] = $text.Substring($idx + 1)
        $text = $text.Substring(0, $idx + 1)
    } else {
        $script:pending[$path] = ''
    }
    return ($text -split "`r?`n") | Where-Object { $_ }
}

# ---- 解析与记录 ------------------------------------------------------------
$accessRe = [regex]::new('"(?<method>[A-Z]+) (?<path>[^ "]+)(?: HTTP/[^"]*)?" (?<status>\d{3})')
$seenErrors = @{}

function Process-LogLine([string]$line) {
    if (-not $line) { return }
    $m = $accessRe.Match($line)
    if ($m.Success) {
        $status = [int]$m.Groups['status'].Value
        $op = @{
            timestamp = (Get-Date).ToString('o')
            method    = $m.Groups['method'].Value
            path      = $m.Groups['path'].Value
            status    = $status
        }
        [System.IO.File]::AppendAllText($operationsPath, ($op | ConvertTo-Json -Compress) + "`n", $utf8NoBom)
        if ($status -ge 500) {
            Write-Journal 'error' @{ source = 'http_status'; status = $status; path = $op.path; line = $line.Substring(0, [Math]::Min(300, $line.Length)) }
        }
        return
    }
    if ($line -match 'Traceback|(^|\s)(ERROR|CRITICAL)(\s|:)' ) {
        $key = $line.Substring(0, [Math]::Min(120, $line.Length))
        if (-not $seenErrors.ContainsKey($key)) {
            $seenErrors[$key] = $true
            Write-Journal 'error' @{ source = 'log_level'; line = $line.Substring(0, [Math]::Min(500, $line.Length)) }
        }
    }
}

function Test-Liveness {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/liveness" -Method Get -TimeoutSec 4 -UseBasicParsing
        return ($resp.StatusCode -eq 200)
    } catch { return $false }
}

# ---- 主循环 ----------------------------------------------------------------
Write-Journal 'monitor_started' @{ pid = $PID; port = $Port; data_root = $DataRoot }
$livenessFailCount = 0
$startFailStreak = 0
$script:gracePolls = 0

while ($true) {
    try {
        $proc = Get-ServerProcess
        if (-not $proc) {
            if ($startFailStreak -ge 3) {
                Start-Sleep -Seconds 60
            }
            $started = Start-Server
            if ($started) {
                Write-Journal 'correction' @{ action = 'start_server'; pid = $started.Id }
                $startFailStreak = 0
            } else {
                $startFailStreak++
                Write-Journal 'error' @{ source = 'startup'; detail = "start_failed_streak=$startFailStreak" }
            }
        } else {
            $startFailStreak = 0
        }

        foreach ($logFile in @($script:serverLogOut, $script:serverLogErr)) {
            foreach ($line in (Read-NewLines $logFile)) { Process-LogLine $line }
        }

        if (Get-ServerProcess) {
            if ($script:gracePolls -gt 0) {
                $script:gracePolls--
            } elseif (Test-Liveness) {
                $livenessFailCount = 0
            } else {
                $livenessFailCount++
                Write-Journal 'error' @{ source = 'liveness'; detail = "liveness_failed_count=$livenessFailCount" }
                if ($livenessFailCount -ge 2) {
                    $livenessFailCount = 0
                    [void](Restart-Server 'liveness_failed')
                }
            }
        }
    } catch {
        Write-Journal 'error' @{ source = 'monitor_loop'; detail = $_.Exception.Message }
    }
    Start-Sleep -Seconds $PollSeconds
}
