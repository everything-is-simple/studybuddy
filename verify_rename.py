#!/usr/bin/env python3
"""验证 s2_knowledge_modules 重命名是否完成"""
import sys
import re

files_to_check = [
    ("backend/app/migrations/_v16_knowledge_modules.py", "migration"),
    ("backend/app/repositories/knowledge_modules.py", "repository"),
    ("backend/tests/test_v16_knowledge_modules_migration.py", "migration tests"),
    ("backend/tests/test_knowledge_modules_repository.py", "repository tests"),
]

all_ok = True

for filepath, desc in files_to_check:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # 检查是否还有旧的表名（排除 import 语句、模块调用和注释）
        lines = content.split('\n')
        old_table_refs = []

        for i, line in enumerate(lines, 1):
            # 跳过 import 行
            if 'import knowledge_modules' in line:
                continue
            # 跳过 Python 模块函数调用（knowledge_modules.xxx()）
            if 'knowledge_modules.' in line:
                continue
            # 跳过纯注释行
            if line.strip().startswith('#'):
                continue
            # 检查是否有旧表名（在 SQL 语句中）
            if re.search(r'\bknowledge_modules\b', line) and 's2_knowledge_modules' not in line:
                # 排除文档字符串中的说明
                if '→' not in line and 'v9' not in line and '变更说明' not in line and 'Tests for' not in line:
                    # 确保是 SQL 上下文（包含 SELECT/INSERT/UPDATE/FROM/JOIN 等关键字）
                    if any(kw in line.upper() for kw in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'FROM', 'JOIN', 'TABLE', 'INDEX', 'TRIGGER']):
                        old_table_refs.append((i, line.strip()))

        if old_table_refs:
            print(f"❌ {desc} ({filepath}):")
            for line_num, line in old_table_refs[:3]:  # 只显示前3个
                print(f"   Line {line_num}: {line[:80]}")
            if len(old_table_refs) > 3:
                print(f"   ... 还有 {len(old_table_refs) - 3} 处")
            all_ok = False
        else:
            print(f"✅ {desc} ({filepath})")

    except Exception as e:
        print(f"❌ {desc} ({filepath}): {e}")
        all_ok = False

if all_ok:
    print("\n🎉 所有文件已成功更新为 s2_knowledge_modules！")
    sys.exit(0)
else:
    print("\n⚠️ 仍有部分 SQL 语句包含旧表名，请检查")
    sys.exit(1)
