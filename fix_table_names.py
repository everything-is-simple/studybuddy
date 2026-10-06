#!/usr/bin/env python3
"""批量替换 knowledge_modules 为 s2_knowledge_modules"""
import sys

files = [
    "backend/tests/test_v16_knowledge_modules_migration.py",
    "backend/tests/test_knowledge_modules_repository.py",
]

for filepath in files:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # 替换所有 knowledge_modules 为 s2_knowledge_modules
        new_content = content.replace("knowledge_modules", "s2_knowledge_modules")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"✅ {filepath}")
    except Exception as e:
        print(f"❌ {filepath}: {e}")
        sys.exit(1)

print("\n🎉 所有测试文件更新完成！")
