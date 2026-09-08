# Phase E Batch E2 完成总结

## 概述

**完成时间**: 2025-01-18  
**批次**: Phase E - Batch E2 (迁移系统)  
**状态**: ✅ 100% 完成  
**文件数**: 19/19  
**代码行数**: ~1,350 行  
**提交数**: 4 次

---

## 已完成文件清单

### 核心引擎

#### 1. runner.py (222 行)
- **功能**: 迁移执行引擎和注册中心
- **关键特性**:
  - 14 版本迁移注册表
  - 严格连续版本执行（不允许跳跃）
  - 事务性执行（失败回滚）
  - 旧数据库基线采用（adopt）
  - schema_migrations + PRAGMA user_version 一致性

#### 2. _helpers.py (~215 行)
- **功能**: 共享辅助工具
- **关键特性**:
  - 时间戳/对象枚举/列查询
  - 基线完整性验证（按版本递增检查表和列）

#### 3. _canonical.py (~95 行)
- **功能**: 规范化材料 Schema
- **关键特性**:
  - 基础四表 + FTS5 搜索索引
  - 旧数据库列兼容性处理

#### 4. _ai_schema.py (~210 行)
- **功能**: AI 能力链 Schema
- **关键特性**:
  - 修订链/分块/嵌入/检索/QA 全套表
  - 嵌入身份标识唯一约束
  - 状态机 CHECK 约束

### 版本迁移脚本

| 版本 | 文件 | 内容 | 关键点 |
|------|------|------|--------|
| v01 | _v01_canonical_material.py | 基础材料表 | 委托 _canonical |
| v02 | _v02_ai_phase0.py | AI 基础表 | 委托 _ai_schema |
| v03 | _v03_phase5_provider.py | Provider 追踪列 | request_id/tokens/finish_reason |
| v04 | _v04_qa_idempotency.py | QA 幂等性 | 部分唯一索引 |
| v05 | _v05_phase7_embedding.py | embeddings 重建 | CHECK 约束 + 保守降级 |
| v06 | _v06_search_index.py | FTS5 虚拟表 | Schema 契约 |
| v07 | _v07_phase8_cards.py | 卡片/练习 8 表 | 引用状态机 + 10 索引 |
| v08 | _v08_exercise_provenance.py | 练习溯源 | exercise_kind 列 |
| v09 | _v09_phase9a_learning_plan.py | 学习计划 8 表 | 依赖 DAG + 11 索引 |
| v10 | _v10_phase9b_material_learning.py | 笔记/节奏 6 表 | 溯源完整性约束 |
| v11 | _v11_phase9c_feedback.py | 练习反馈 7 表 | 错题指纹去重 |
| v12 | _v12_phase9d_extended.py | 采集/报告 5 表 | 交付幂等指纹 |
| v13 | _v13_phase10_tasks.py | 任务信封 2 表 | 租约字段 + 运行中唯一 |
| v14 | _v14_fix_revision_fingerprint.py | 指纹修复 | P14-P0-05 + rollback() |
| - | __init__.py | 包公共 API | 导出 5 个符号 |

---

## 关键技术发现

### 1. executescript() 事务陷阱（v9-v12）

```python
# 错误做法：executescript() 会隐式提交待处理事务
connection.executescript(script)  # 迁移无法整体回滚！

# 正确做法（v9-v12 采用）：逐条执行
for statement in script.split(";\n"):
    connection.execute(statement)  # 保持在 BEGIN IMMEDIATE 内
```

### 2. SQLite ALTER TABLE 限制（v5）

SQLite 无法通过 ALTER TABLE：
- 添加 CHECK 约束
- 将可空列改为 NOT NULL

v5 因此重建 embeddings 表，旧数据保守降级（running/ready → stale），
绝不静默提升为可用状态。

### 3. 指纹公式的字面量陷阱（v14）

```python
# 分隔符是四字符字面量，不是 0x1F 控制字符！
hashlib.sha256("\\x1f".join(values).encode())
#             ^^^^ 反斜杠+x+1+f
```

必须与运行时实现（_legacy_part_14.py）完全一致。

### 4. 引用状态机贯穿设计

v7/v9/v10/v12 的源链接共享同一状态机：
```
valid → source_deleted | source_unavailable | stale | invalid
```

配合 ON DELETE SET NULL，源材料删除后记录保留、状态标记失效。

### 5. 修订链与幂等设计

- material_revisions: is_current 标记当前版，superseded_at 记录被替代时间
- ai_operations: idempotency_key 部分唯一索引（v4）
- report_delivery_attempts: idempotency_key_fingerprint 防重复发送（v12）

---

## 注释覆盖统计

- **模块级 docstring**: 19/19 (100%)
- **函数级 docstring**: 100% 公共函数 + 关键私有函数
- **迁移函数**: 15/15 migrate() 全部注释
- **唯一 rollback()**: v14 已注释

---

## 提交历史

```
12b0be5 - v11-v14 + __init__ (Batch E2 收官)
6186207 - v07-v10 (卡片/练习/计划/笔记)
0ab0a44 - v01-v06 (基础迁移)
bf7209f - _helpers + _canonical + _ai_schema
4f8768c - runner.py (迁移引擎)
```

---

## Phase E 总进度

| 批次 | 文件数 | 状态 | 实际工时 |
|------|--------|------|----------|
| E1: 核心基础设施 | 11/11 | ✅ | ~3 小时 |
| **E2: 迁移系统** | **19/19** | **✅** | **~1.5 小时** |
| E3: 辅助工具 | 0/10 | ⏳ | - |
| E4: 入口文件 | 0/4 | ⏳ | - |
| **Phase E 合计** | **30/44** | **🟡 68%** | **~4.5 小时** |

**项目整体进度**: 73/97 文件 (75.3%)

---

## 下一步

### Batch E3: 辅助工具 (10 文件)
- diagnostics.py, db_audit.py, recovery.py
- startup_preflight.py, instance_lock.py
- import_locks.py, http_errors.py, http_helpers.py
- delivery.py, local_settings.py
- **预计工时**: 1-2 天（按当前效率可能 <1 小时）

### Batch E4: 入口文件 (4 文件)
- __init__.py, __main__.py, lifespan.py, connection_test.py
- **预计工时**: 0.5-1 天
