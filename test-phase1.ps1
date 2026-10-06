# S2 Knowledge Modules Phase 1 测试验证脚本（PowerShell）
# 运行方式：powershell -File test-phase1.ps1

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "S2 Knowledge Modules Phase 1 测试验证" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 设置 Python 路径
$Python = "D:\miniconda\py310\python.exe"

Write-Host "步骤 1: 运行 Migration v16 测试..." -ForegroundColor Yellow
Write-Host "----------------------------------------"
& $Python -m pytest backend/tests/test_v16_knowledge_modules_migration.py -v --tb=short
$MigrationResult = $LASTEXITCODE
Write-Host ""

Write-Host "步骤 2: 运行 Repository 测试..." -ForegroundColor Yellow
Write-Host "----------------------------------------"
& $Python -m pytest backend/tests/test_knowledge_modules_repository.py -v --tb=short
$RepositoryResult = $LASTEXITCODE
Write-Host ""

Write-Host "步骤 3: 运行后端回归测试..." -ForegroundColor Yellow
Write-Host "----------------------------------------"
& $Python -m pytest backend/tests/ -v --tb=line -x
$RegressionResult = $LASTEXITCODE
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "测试结果总结" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

if ($MigrationResult -eq 0) {
    Write-Host "✅ Migration v16 测试: PASSED" -ForegroundColor Green
} else {
    Write-Host "❌ Migration v16 测试: FAILED" -ForegroundColor Red
}

if ($RepositoryResult -eq 0) {
    Write-Host "✅ Repository 测试: PASSED" -ForegroundColor Green
} else {
    Write-Host "❌ Repository 测试: FAILED" -ForegroundColor Red
}

if ($RegressionResult -eq 0) {
    Write-Host "✅ 后端回归测试: PASSED" -ForegroundColor Green
} else {
    Write-Host "❌ 后端回归测试: FAILED" -ForegroundColor Red
}

Write-Host ""

# 计算总体结果
if ($MigrationResult -eq 0 -and $RepositoryResult -eq 0 -and $RegressionResult -eq 0) {
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "🎉 Phase 1 测试验证: 全部通过" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
    exit 0
} else {
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host "⚠️  Phase 1 测试验证: 存在失败" -ForegroundColor Red
    Write-Host "==========================================" -ForegroundColor Red
    exit 1
}
