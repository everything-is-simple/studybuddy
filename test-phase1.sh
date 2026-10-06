#!/bin/bash
# S2 Knowledge Modules Phase 1 测试验证脚本
# 运行方式：bash test-phase1.sh

echo "=========================================="
echo "S2 Knowledge Modules Phase 1 测试验证"
echo "=========================================="
echo ""

# 设置 Python 路径
PYTHON="/d/miniconda/py310/python.exe"

echo "步骤 1: 运行 Migration v16 测试..."
echo "----------------------------------------"
$PYTHON -m pytest backend/tests/test_v16_knowledge_modules_migration.py -v --tb=short
MIGRATION_RESULT=$?
echo ""

echo "步骤 2: 运行 Repository 测试..."
echo "----------------------------------------"
$PYTHON -m pytest backend/tests/test_knowledge_modules_repository.py -v --tb=short
REPOSITORY_RESULT=$?
echo ""

echo "步骤 3: 运行后端回归测试..."
echo "----------------------------------------"
$PYTHON -m pytest backend/tests/ -v --tb=line -x
REGRESSION_RESULT=$?
echo ""

echo "=========================================="
echo "测试结果总结"
echo "=========================================="
echo ""

if [ $MIGRATION_RESULT -eq 0 ]; then
    echo "✅ Migration v16 测试: PASSED"
else
    echo "❌ Migration v16 测试: FAILED"
fi

if [ $REPOSITORY_RESULT -eq 0 ]; then
    echo "✅ Repository 测试: PASSED"
else
    echo "❌ Repository 测试: FAILED"
fi

if [ $REGRESSION_RESULT -eq 0 ]; then
    echo "✅ 后端回归测试: PASSED"
else
    echo "❌ 后端回归测试: FAILED"
fi

echo ""

# 计算总体结果
if [ $MIGRATION_RESULT -eq 0 ] && [ $REPOSITORY_RESULT -eq 0 ] && [ $REGRESSION_RESULT -eq 0 ]; then
    echo "=========================================="
    echo "🎉 Phase 1 测试验证: 全部通过"
    echo "=========================================="
    exit 0
else
    echo "=========================================="
    echo "⚠️  Phase 1 测试验证: 存在失败"
    echo "=========================================="
    exit 1
fi
