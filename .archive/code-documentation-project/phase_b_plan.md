# Phase B: Repository 层注释计划

## 概述

**目标**: 为 Repository 层的 9 个核心文件补齐注释  
**范围**: `backend/app/repositories/` 目录（不包括 `_legacy*.py`）  
**工作量**: 预计 1-2 天（实际文件很小，约 362 行）  
**优先级**: 🔴 高

## 文件清单

| 批次 | 文件 | 行数 | 大小 | 优先级 | 状态 |
|------|------|------|------|--------|------|
| B1 | connection.py | 52 | 3.2K | 高 | ⏳ 待处理 |
| B1 | materials.py | 19 | 1.2K | 高 | ⏳ 待处理 |
| B1 | tasks.py | 19 | 1.4K | 高 | ⏳ 待处理 |
| B2 | ai.py | 46 | 3.9K | 高 | ⏳ 待处理 |
| B2 | capture.py | 37 | 3.4K | 高 | ⏳ 待处理 |
| B3 | learning.py | 64 | 4.8K | 中 | ⏳ 待处理 |
| B3 | plans.py | 72 | 6.0K | 中 | ⏳ 待处理 |
| B4 | practice.py | 38 | 3.0K | 中 | ⏳ 待处理 |
| B4 | reports.py | 14 | 886B | 低 | ⏳ 待处理 |

**总计**: 9 个文件，361 行，约 27KB

## 注释标准

### 模块级 Docstring

每个模块顶部添加：

```python
"""材料管理数据访问层。

本模块提供材料的创建、查询、更新和删除等数据库操作。
所有操作都在事务边界内执行，调用者负责管理连接和提交。

主要函数：
- create_material: 创建新材料记录
- get_material: 查询单个材料
- list_materials: 分页查询材料列表
- delete_material: 软删除材料

关联模块：
- api.materials_collection: HTTP API 层
- adapters.file_parsers: 文件解析
"""
```

### 函数级 Docstring

每个公共函数添加：

```python
def create_material(
    connection,
    project_id: str,
    original_name: str,
    media_type: str,
    stored_path: str
) -> dict[str, object]:
    """创建新的学习材料记录。
    
    在指定项目中创建一个新材料，记录文件元数据和存储位置。
    材料创建后初始状态为 'pending'，需要后续解析和索引。
    
    Args:
        connection: SQLite 数据库连接（需要写权限）
        project_id: 项目唯一标识符（必须存在）
        original_name: 用户上传的原始文件名（1-255 字符）
        media_type: MIME 类型（如 'application/pdf'）
        stored_path: 文件系统存储路径（相对 data_root）
        
    Returns:
        新创建的材料字典，包含以下字段：
        {
            "id": str (UUID),
            "project_id": str,
            "original_name": str,
            "media_type": str,
            "stored_path": str,
            "status": "pending",
            "created_at": str (ISO 8601),
            "updated_at": str (ISO 8601)
        }
        
    Raises:
        ValueError: project_not_found - 项目不存在
        ValueError: material_name_empty - 文件名为空
        ValueError: material_name_too_long - 文件名超过 255 字符
        sqlite3.IntegrityError: 数据库约束冲突
        
    Side Effects:
        - INSERT into materials 表
        - 更新 project.material_count
        
    Note:
        此函数不验证 stored_path 的实际存在性，调用者需确保
        文件已成功写入存储系统。
    """
```

## 执行计划

### 批次 B1: 基础设施层（connection + materials + tasks）

**文件**: 3 个，90 行  
**工时**: 0.5 天  
**内容**:
- `connection.py`: 数据库连接管理
- `materials.py`: 材料基础操作
- `tasks.py`: 异步任务管理

### 批次 B2: AI 层（ai + capture）

**文件**: 2 个，83 行  
**工时**: 0.5 天  
**内容**:
- `ai.py`: AI 索引和检索
- `capture.py`: 捕获会话管理

### 批次 B3: 学习层（learning + plans）

**文件**: 2 个，136 行  
**工时**: 0.5 天  
**内容**:
- `learning.py`: 学习域（卡片、练习、笔记）
- `plans.py`: 计划管理

### 批次 B4: 辅助层（practice + reports）

**文件**: 2 个，52 行  
**工时**: 0.5 天  
**内容**:
- `practice.py`: 练习域
- `reports.py`: 报告域

## 验收标准

每个批次完成后：

1. ✅ **文档字符串完整性**
   - 每个模块有模块级 docstring
   - 每个公共函数有函数级 docstring
   - 包含 Args, Returns, Raises, Side Effects

2. ✅ **格式规范**
   - 使用 Google Style
   - 中文功能描述 + 英文参数名
   - 缩进和空行符合 PEP 257

3. ✅ **工具检查**
   ```bash
   pydocstyle backend/app/repositories/<file>.py --convention=google
   ```

4. ✅ **代码审查**
   - 至少 1 人审查注释质量
   - 确认注释与代码逻辑一致

5. ✅ **提交规范**
   - 每个批次独立提交
   - 提交信息: `docs(phase-b): add docstrings to <batch> (<files>)`

## Legacy 文件处理

**跳过文件**: `_legacy.py` 及 `_legacy_part_*.py`（18 个文件）

**原因**:
- 这些文件是从单一大文件拆分而来
- 职责不清晰，需要先重构再注释
- 大小巨大（~400KB），注释性价比低

**后续计划**:
1. 在独立的重构项目中按领域拆分
2. 重构完成后再补齐注释
3. 不阻塞 Phase B 的完成

## 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 文件职责不清晰 | 中 | 低 | 先阅读代码，理解后再注释 |
| 注释与代码不一致 | 高 | 中 | Code Review 强制检查 |
| 工作量超出预期 | 低 | 低 | 文件很小，风险可控 |

## 时间表

| 日期 | 批次 | 文件 | 状态 |
|------|------|------|------|
| Day 1 上午 | B1 | connection + materials + tasks | ⏳ |
| Day 1 下午 | B2 | ai + capture | ⏳ |
| Day 2 上午 | B3 | learning + plans | ⏳ |
| Day 2 下午 | B4 | practice + reports | ⏳ |

**预计完成时间**: 2 天

---

**创建时间**: 2025年  
**维护者**: Claude (Pi Agent Desktop)
