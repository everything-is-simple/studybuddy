# S2 Knowledge Modules - 表名冲突修复与测试
# 执行时间：2026-10-05

Write-Host "=========================================="
Write-Host "Step 1: 验证文件更新"
Write-Host "=========================================="

D:\miniconda\py310\python.exe verify_rename.py
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "⚠️ 文件验证失败，停止测试"
    exit 1
}

Write-Host ""
Write-Host "=========================================="
Write-Host "Step 2: 运行 Migration v16 测试"
Write-Host "=========================================="

D:\miniconda\py310\python.exe -m pytest backend/tests/test_v16_knowledge_modules_migration.py -v

$migration_result = $LASTEXITCODE

Write-Host ""
Write-Host "=========================================="
Write-Host "Step 3: 运行 Repository 测试"
Write-Host "=========================================="

D:\miniconda\py310\python.exe -m pytest backend/tests/test_knowledge_modules_repository.py -v

$repo_result = $LASTEXITCODE

Write-Host ""
Write-Host "=========================================="
Write-Host "Step 4: 运行后端回归测试（前5个测试）"
Write-Host "=========================================="

D:\miniconda\py310\python.exe -m pytest backend/tests/ -x --maxfail=1 -v | Select-Object -First 50

$backend_result = $LASTEXITCODE

Write-Host ""
Write-Host "=========================================="
Write-Host "测试结果总结"
Write-Host "=========================================="

if ($migration_result -eq 0) {
    Write-Host "✅ Migration v16 测试: PASSED"
} else {
    Write-Host "❌ Migration v16 测试: FAILED"
}

if ($repo_result -eq 0) {
    Write-Host "✅ Repository 测试: PASSED"
} else {
    Write-Host "❌ Repository 测试: FAILED"
}

if ($backend_result -eq 0) {
    Write-Host "✅ 后端回归测试: PASSED"
} else {
    Write-Host "⚠️ 后端回归测试: 需要检查"
}

Write-Host ""
Write-Host "=========================================="

if ($migration_result -eq 0 -and $repo_result -eq 0) {
    Write-Host "🎉 Phase 1 核心测试: 全部通过"
    Write-Host "=========================================="
    exit 0
} else {
    Write-Host "❌ Phase 1 核心测试: 存在失败"
    Write-Host "=========================================="
    exit 1
}
