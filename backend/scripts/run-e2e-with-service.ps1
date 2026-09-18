# E2E Test with Service Management
# Starts service, waits for ready, runs tests, stops service

param(
    [int]$ServiceStartWait = 15,
    [int]$HealthCheckRetries = 10
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================="
Write-Host "StudyBuddy E2E Tests with Service"
Write-Host "=========================================="
Write-Host ""

Set-Location "H:\studybuddy"

# Function to check if port is in use
function Test-Port {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $connection
}

# Function to stop service on port
function Stop-ServiceOnPort {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($connection) {
        $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "  Stopping process $($process.Id) ($($process.Name))..."
            Stop-Process -Id $process.Id -Force
            Start-Sleep -Seconds 2
        }
    }
}

# 1. Cleanup
Write-Host "[1/6] Cleanup..."
Stop-ServiceOnPort -Port 8787
Get-Job | Remove-Job -Force -ErrorAction SilentlyContinue
Write-Host "  Done"
Write-Host ""

# 2. Start service in background job
Write-Host "[2/6] Starting service (background job)..."

# Secrets are never hardcoded here. API key must be provided via the
# STUDYBUDDY_AI_API_KEY environment variable of the invoking shell.
if (-not $env:STUDYBUDDY_AI_API_KEY) {
    Write-Host "  Warning: STUDYBUDDY_AI_API_KEY not set; AI provider will start unconfigured."
}

$apiKey = $env:STUDYBUDDY_AI_API_KEY
$serviceJob = Start-Job -Name "StudyBuddyService" -ScriptBlock {
    param($AiApiKey)

    $env:STUDYBUDDY_DATA_ROOT = "H:\studybuddy-data"
    $env:STUDYBUDDY_PORT = "8787"
    # Correct variable names (see docs/LOCAL_V1_USER_GUIDE.md):
    $env:STUDYBUDDY_AI_PROVIDER = "openai"
    $env:STUDYBUDDY_AI_MODEL = "glm-5.3-flash"
    $env:STUDYBUDDY_AI_BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3"
    if ($AiApiKey) { $env:STUDYBUDDY_AI_API_KEY = $AiApiKey }

    Set-Location "H:\studybuddy"
    & "C:\miniconda\py310\python.exe" -m backend.app serve 2>&1
} -ArgumentList $apiKey

Write-Host "  Job started (ID: $($serviceJob.Id))"
Write-Host "  Waiting $ServiceStartWait seconds for startup..."
Start-Sleep -Seconds $ServiceStartWait

# 3. Health check
Write-Host "[3/6] Health check..."

$healthy = $false
for ($i = 1; $i -le $HealthCheckRetries; $i++) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8787/api/health" -Method Get -TimeoutSec 3
        if ($response.status -eq "ok") {
            Write-Host "  Service is healthy!"
            $healthy = $true
            break
        }
    }
    catch {
        Write-Host "  Attempt $i/$HealthCheckRetries - not ready yet..."
        if ($i -lt $HealthCheckRetries) {
            Start-Sleep -Seconds 2
        }
    }
}

if (-not $healthy) {
    Write-Host "  ERROR: Service did not become healthy"
    Write-Host ""
    Write-Host "Last 30 lines of service output:"
    Receive-Job -Job $serviceJob | Select-Object -Last 30
    Remove-Job -Job $serviceJob -Force
    exit 1
}

Write-Host ""

# 4. Verify job is still running
$jobState = (Get-Job -Id $serviceJob.Id).State
if ($jobState -ne "Running") {
    Write-Host "  ERROR: Service job is not running (state: $jobState)"
    Receive-Job -Job $serviceJob
    Remove-Job -Job $serviceJob -Force
    exit 1
}

Write-Host "[4/6] Service confirmed running"
Write-Host ""

# 5. Run tests
Write-Host "[5/6] Running Playwright tests..."
Write-Host "  This may take 5-10 minutes"
Write-Host "  Service will remain running during tests"
Write-Host ""

npx playwright test backend/tests/browser_e2e_full_coverage.spec.js --workers=1 --reporter=list,html --timeout=60000

$testExitCode = $LASTEXITCODE

Write-Host ""
Write-Host "Tests finished with exit code: $testExitCode"
Write-Host ""

# 6. Report and cleanup
Write-Host "[6/6] Cleanup and report..."

if (Test-Path "playwright-report\index.html") {
    Write-Host "  Report: playwright-report\index.html"
}

$screenshots = Get-ChildItem "H:\studybuddy-test\e2e-screenshots\*.png" -ErrorAction SilentlyContinue
if ($screenshots) {
    Write-Host "  Screenshots: $($screenshots.Count) files in H:\studybuddy-test\e2e-screenshots\"
}

Write-Host ""
Write-Host "Stopping service..."
Remove-Job -Job $serviceJob -Force
Start-Sleep -Seconds 1

Write-Host ""
Write-Host "=========================================="
if ($testExitCode -eq 0) {
    Write-Host "SUCCESS: All tests passed"
} else {
    Write-Host "FAILED: Some tests failed (exit code: $testExitCode)"
}
Write-Host "=========================================="

exit $testExitCode
