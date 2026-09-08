# Phase E: 基础设施层执行计划

## 📋 概述

**Phase**: E - Infrastructure（基础设施层）  
**优先级**: 🟡 中  
**预计工时**: 5-7 天  
**状态**: ⏳ 待启动

---

## 🎯 目标

为 StudyBuddy 的基础设施代码添加完整的中文注释，包括：
- 核心基础设施（配置、存储、备份恢复）
- 数据库迁移系统
- 任务系统
- HTTP 辅助工具
- 应用生命周期管理

---

## 📊 文件清单

### 总览

| 批次 | 文件数 | 总代码量 | 预计工时 | 优先级 |
|------|--------|----------|----------|--------|
| E1: 核心基础设施 | 10 | 2,758 行 | 2-3 天 | 🔴 高 |
| E2: 迁移系统 | 14 | 1,256 行 | 2 天 | 🟡 中 |
| E3: 任务与服务 | 3 | 514 行 | 1 天 | 🟡 中 |
| E4: 辅助工具 | 5 | 310 行 | 1 天 | 🟢 低 |
| **总计** | **32** | **4,838 行** | **6-7 天** | - |

---

## 📂 批次 E1: 核心基础设施 (10 文件, 2,758 行)

### 文件列表

| 文件 | 代码量 | 优先级 | 说明 |
|------|--------|--------|------|
| `repository.py` | 678 行 | 🔴 高 | **Repository Legacy 层核心入口** |
| `backup.py` | 484 行 | 🔴 高 | 备份系统 |
| `restore_acceptance.py` | 465 行 | 🔴 高 | 恢复验收系统 |
| `config.py` | 345 行 | 🔴 高 | 配置管理 |
| `capabilities.py` | 343 行 | 🔴 高 | 能力检测与管理 |
| `capability_detect.py` | 250 行 | 🟡 中 | 能力探测 |
| `embedding.py` | 229 行 | 🟡 中 | 嵌入向量管理 |
| `chunking.py` | 97 行 | 🟡 中 | 文本切分 |
| `storage.py` | 89 行 | 🟡 中 | 存储抽象 |
| **小计** | **2,980 行** | - | - |

### 执行顺序

1. **第一优先**: `config.py`, `storage.py`, `capabilities.py`（核心配置）
2. **第二优先**: `backup.py`, `restore_acceptance.py`（数据安全）
3. **第三优先**: `repository.py`（Legacy 入口，等待重构）
4. **第四优先**: `embedding.py`, `chunking.py`, `capability_detect.py`（AI 辅助）

---

## 📂 批次 E2: 迁移系统 (14 文件, 1,256 行)

### 文件列表

| 文件 | 代码量 | 优先级 | 说明 |
|------|--------|--------|------|
| `migrations/runner.py` | 182 行 | 🔴 高 | 迁移运行器 |
| `migrations/_helpers.py` | 227 行 | 🔴 高 | 迁移辅助函数 |
| `migrations/_ai_schema.py` | 172 行 | 🟡 中 | AI 模式定义 |
| `migrations/_canonical.py` | 52 行 | 🟡 中 | 规范模式 |
| `migrations/_v01_canonical_material.py` | 12 行 | 🟢 低 | V1: 材料表 |
| `migrations/_v02_ai_phase0.py` | 12 行 | 🟢 低 | V2: AI 阶段 0 |
| `migrations/_v03_phase5_provider.py` | 18 行 | 🟢 低 | V3: Provider |
| `migrations/_v04_qa_idempotency.py` | 20 行 | 🟢 低 | V4: QA 幂等性 |
| `migrations/_v05_phase7_embedding.py` | 45 行 | 🟢 低 | V5: 嵌入向量 |
| `migrations/_v06_search_index.py` | 20 行 | 🟢 低 | V6: 搜索索引 |
| `migrations/_v07_phase8_cards.py` | 88 行 | 🟢 低 | V7: 卡片系统 |
| `migrations/_v08_exercise_provenance.py` | 17 行 | 🟢 低 | V8: 练习溯源 |
| `migrations/_v09_phase9a_learning_plan.py` | 144 行 | 🟡 中 | V9a: 学习计划 |
| `migrations/_v10_phase9b_material_learning.py` | 102 行 | 🟡 中 | V10: 材料学习 |
| `migrations/_v11_phase9c_feedback.py` | 157 行 | 🟡 中 | V11: 反馈系统 |
| `migrations/_v12_phase9d_extended.py` | 118 行 | 🟡 中 | V12: 扩展功能 |
| `migrations/_v13_phase10_tasks.py` | 68 行 | 🟡 中 | V13: 任务系统 |
| `migrations/_v14_fix_revision_fingerprint.py` | 93 行 | 🟡 中 | V14: 修复指纹 |
| `migrations/__init__.py` | 4 行 | 🟢 低 | 包初始化 |
| **小计** | **1,551 行** | - | - |

### 执行顺序

1. **核心**: `runner.py`, `_helpers.py`, `_ai_schema.py`, `_canonical.py`
2. **历史迁移**: V1-V14（按版本号顺序）

---

## 📂 批次 E3: 任务与服务 (3 文件, 514 行)

### 文件列表

| 文件 | 代码量 | 优先级 | 说明 |
|------|--------|--------|------|
| `task_runner.py` | 306 行 | 🔴 高 | 任务运行器 |
| `task_handlers.py` | 103 行 | 🔴 高 | 任务处理器 |
| `services/imports.py` | 105 行 | 🟡 中 | 导入服务 |
| `services/__init__.py` | 1 行 | 🟢 低 | 包初始化 |
| **小计** | **515 行** | - | - |

---

## 📂 批次 E4: 辅助工具 (5 文件, 310 行)

### 文件列表

| 文件 | 代码量 | 优先级 | 说明 |
|------|--------|--------|------|
| `app_factory.py` | 205 行 | 🔴 高 | 应用工厂 |
| `observability.py` | 171 行 | 🟡 中 | 可观测性 |
| `recovery.py` | 140 行 | 🟡 中 | 恢复机制 |
| `cli.py` | 127 行 | 🟡 中 | CLI 入口 |
| `db_audit.py` | 97 行 | 🟡 中 | 数据库审计 |
| `startup_preflight.py` | 79 行 | 🟡 中 | 启动预检 |
| `diagnostics.py` | 75 行 | 🟡 中 | 诊断工具 |
| `lifespan.py` | 66 行 | 🟡 中 | 生命周期管理 |
| `instance_lock.py` | 90 行 | 🟡 中 | 实例锁 |
| `http_helpers.py` | 54 行 | 🟢 低 | HTTP 辅助 |
| `import_locks.py` | 42 行 | 🟢 低 | 导入锁 |
| `main.py` | 35 行 | 🟢 低 | 主入口 |
| `http_errors.py` | 31 行 | 🟢 低 | HTTP 错误 |
| `__main__.py` | 7 行 | 🟢 低 | Python 入口 |
| `__init__.py` | 0 行 | 🟢 低 | 包初始化 |
| **小计** | **1,219 行** | - | - |

---

## 📝 注释标准

### 模块级 Docstring

```python
"""配置管理模块。

本模块提供 StudyBuddy 的配置加载、验证和访问功能。支持从环境变量、
配置文件和默认值三个来源加载配置，并提供统一的配置对象。

主要组件：
- Config: 配置数据类，包含所有配置项
- load_config(): 加载配置的主函数
- validate_config(): 配置验证函数

配置来源优先级: 环境变量 > 配置文件 > 默认值

关联模块：
- local_settings - 本地设置持久化
- capabilities - 能力配置
"""
```

### 函数级 Docstring

```python
def load_config(config_path: str | None = None) -> Config:
    """加载应用配置。
    
    从以下来源加载配置（优先级从高到低）：
    1. 环境变量（STUDYBUDDY_* 前缀）
    2. 配置文件（YAML 或 JSON）
    3. 内置默认值
    
    Args:
        config_path: 配置文件路径，None 则使用默认路径
    
    Returns:
        Config: 配置对象，包含所有已验证的配置项
    
    Raises:
        ValueError: 当必需的配置项缺失或无效时
        FileNotFoundError: 当指定的配置文件不存在时
    
    Side Effects:
        - 读取文件系统上的配置文件
        - 读取环境变量
        - 创建默认配置文件（如果不存在）
    
    Example:
        >>> config = load_config()
        >>> print(config.data_root)
        '/path/to/data'
    """
```

---

## ✅ 验收标准

### 每个批次完成后

1. **覆盖率检查**:
   ```bash
   python backend/scripts/check_docstring_coverage.py backend/app/
   ```

2. **格式检查**:
   ```bash
   pydocstyle --convention=google backend/app/
   ```

3. **类型检查**:
   ```bash
   mypy backend/app/
   ```

4. **测试通过**:
   ```bash
   C:\miniconda\py310\python.exe -m pytest backend/tests/
   ```

### Phase E 完成标准

- [ ] 所有 32 个文件都有模块级 docstring
- [ ] 所有公共函数都有函数级 docstring
- [ ] 所有公共类都有类级 docstring
- [ ] 通过 `pydocstyle --convention=google` 检查
- [ ] 通过 `mypy` 类型检查
- [ ] 所有测试通过
- [ ] 创建 Phase E 完成总结文档
- [ ] 提交到 Git 并推送到 GitHub

---

## 🎯 优先级说明

### 🔴 高优先级（核心基础设施）
- 配置管理、存储、备份恢复
- 迁移系统核心
- 任务系统
- 应用工厂

### 🟡 中优先级（重要功能）
- 能力检测
- AI 辅助功能（嵌入、切分）
- 迁移历史
- 导入服务
- 可观测性

### 🟢 低优先级（辅助工具）
- HTTP 辅助
- 包初始化
- 小型迁移脚本

---

## 🚧 特殊处理

### repository.py (678 行)
- **状态**: Legacy 代码，等待重构
- **处理**: 仅添加模块级 docstring 和关键函数注释
- **原因**: 避免在即将重构的代码上投入过多时间

### 迁移脚本 (V1-V14)
- **处理**: 统一添加标准化的迁移脚本 docstring
- **模板**: 包含迁移版本、目的、SQL 变更摘要

---

## 📅 执行时间线

| 日期 | 批次 | 文件数 | 代码量 | 状态 |
|------|------|--------|--------|------|
| Day 1-2 | E1 核心基础设施（前 5 个） | 5 | ~1,700 行 | ⏳ |
| Day 3 | E1 核心基础设施（后 5 个） | 5 | ~1,280 行 | ⏳ |
| Day 4-5 | E2 迁移系统 | 14 | ~1,551 行 | ⏳ |
| Day 6 | E3 任务与服务 | 3 | ~515 行 | ⏳ |
| Day 7 | E4 辅助工具 | 15 | ~1,219 行 | ⏳ |

---

## 🎊 Phase E 完成后

完成 Phase E 后，整个 **代码注释补齐工程** 将达到：

| Phase | 模块 | 文件数 | 代码量 | 状态 |
|-------|------|--------|--------|------|
| Phase A | API 层 | 15 | 2,891 行 | ✅ 100% |
| Phase B | Repository 代理 | 9 | 362 行 | ✅ 100% |
| Phase C | Provider 层 | 10 | 1,197 行 | ✅ 100% |
| Phase D | Schema/Adapter | 9 | 565 行 | ✅ 100% |
| **Phase E** | **基础设施层** | **32** | **4,838 行** | **⏳ 0%** |
| **总计** | **公共代码** | **75** | **9,853 行** | **🟡 52%** |

剩余未处理：
- **Phase F**: Repository Legacy (~7,000 行，待重构后处理)

---

**创建时间**: 2025-01-17  
**文档版本**: 1.0  
**作者**: AI Assistant  
**状态**: ⏳ 待执行
