[CmdletBinding()]
param(
    [string]$DataRoot = $env:STUDYBUDDY_DATA_ROOT,
    [int]$Port = 8787,
    [string]$Python = $env:STUDYBUDDY_PYTHON,
    [string]$OcrModelRoot = $env:STUDYBUDDY_OCR_MODEL_ROOT,
    [switch]$OpenBrowser
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not $DataRoot) { throw 'data_root_required' }
if ($Port -lt 1024 -or $Port -gt 65535) { throw 'invalid_port' }
if (-not $Python) {
    $candidate = 'D:/miniconda/py310/python.exe'
    $legacyCandidate = 'C:/miniconda/py310/python.exe'
    $venvCandidate = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path '.venv/Scripts/python.exe'
    $Python = if (Test-Path $candidate) { $candidate } elseif (Test-Path $venvCandidate) { $venvCandidate } elseif (Test-Path $legacyCandidate) { $legacyCandidate } else { 'python' }
}
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$resolvedRoot = [System.IO.Path]::GetFullPath($DataRoot)
New-Item -ItemType Directory -Force -Path $resolvedRoot | Out-Null
$pidPath = Join-Path $resolvedRoot '.studybuddy.pid'
$existingListener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existingListener) {
    $existingProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($existingListener.OwningProcess)" -ErrorAction SilentlyContinue
    if ($existingProcess -and $existingProcess.CommandLine -match 'backend\.app\s+serve' -and $existingProcess.CommandLine -match [regex]::Escape($resolvedRoot)) {
        Set-Content -LiteralPath $pidPath -Value ([string]$existingListener.OwningProcess) -NoNewline
        Write-Output 'studybuddy_already_running'
        exit 0
    }
    throw 'port_in_use'
}
if (Test-Path $pidPath) {
    $oldPid = 0
    [int]::TryParse((Get-Content -Raw -LiteralPath $pidPath), [ref]$oldPid) | Out-Null
    if ($oldPid -gt 0 -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) { throw 'data_root_in_use' }
    Remove-Item -Force -LiteralPath $pidPath -ErrorAction SilentlyContinue
}
$env:STUDYBUDDY_DATA_ROOT = $resolvedRoot
$env:STUDYBUDDY_HOST = '127.0.0.1'
$env:STUDYBUDDY_PORT = [string]$Port
$env:STUDYBUDDY_REPORT_DELIVERY_MODE = 'off'
$env:STUDYBUDDY_REPORT_DELIVERY_ENABLED = 'false'
$env:STUDYBUDDY_REPORT_DELIVERY_AUTHORIZED = 'false'
if (-not $OcrModelRoot) {
    $candidateOcrModelRoot = Join-Path (Split-Path $root -Parent) 'studybuddy-composer/references/vendor/PaddleOCR/models'
    if (Test-Path -LiteralPath $candidateOcrModelRoot -PathType Container) { $OcrModelRoot = $candidateOcrModelRoot }
}
if ($OcrModelRoot) {
    $env:STUDYBUDDY_OCR_PROVIDER = 'paddleocr'
    $env:STUDYBUDDY_OCR_MODEL = 'PP-OCRv5_server_det+PP-OCRv5_server_rec'
    $env:STUDYBUDDY_OCR_MODEL_ROOT = [System.IO.Path]::GetFullPath($OcrModelRoot)
    $env:STUDYBUDDY_OCR_ENABLED = 'true'
}

try { $null = & $Python --version 2>&1 } catch { throw 'studybuddy_python_unavailable' }

Push-Location $root
try {
    $argumentList = "-m backend.app serve --data-root `"$resolvedRoot`""
    $process = Start-Process -FilePath $Python -ArgumentList $argumentList -WorkingDirectory $root -PassThru -WindowStyle Hidden
    Set-Content -LiteralPath $pidPath -Value ([string]$process.Id) -NoNewline
    Start-Sleep -Milliseconds 300
    $process.Refresh()
    if ($process.HasExited) {
        Remove-Item -Force -LiteralPath $pidPath -ErrorAction SilentlyContinue
        throw 'studybuddy_start_failed'
    }
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $probe = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/liveness" -UseBasicParsing -TimeoutSec 1
            if ([int]$probe.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 250
        $process.Refresh()
        if ($process.HasExited) { break }
    }
    if (-not $ready) {
        if (-not $process.HasExited) { try { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue } catch {} }
        Remove-Item -Force -LiteralPath $pidPath -ErrorAction SilentlyContinue
        throw 'studybuddy_start_not_ready'
    }
    if ($OpenBrowser) {
        Start-Process "http://127.0.0.1:$Port"
    }
    Write-Output "studybuddy_started"
} finally {
    Pop-Location
}
