#!/usr/bin/env python3
"""Update test_knowledge_modules_repository.py with s2_ prefix"""
import re

filepath = "backend/tests/test_knowledge_modules_repository.py"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 替换所有 knowledge_modules 为 s2_knowledge_modules（除了 import 行）
lines = content.split('\n')
new_lines = []

for line in lines:
    # 跳过 import 行（保持 from backend.app.repositories import knowledge_modules）
    if 'from backend.app.repositories import knowledge_modules' in line:
        new_lines.append(line)
    else:
        # 替换 SQL 中的表名
        new_line = line.replace('knowledge_modules', 's2_knowledge_modules')
        new_lines.append(new_line)

new_content = '\n'.join(new_lines)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"✅ {filepath} 更新完成")
