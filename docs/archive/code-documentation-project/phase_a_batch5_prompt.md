# Phase A Batch 5 继续工作 Prompt

## 背景

StudyBuddy 代码文档改进项目 Phase A（API层文档）已完成 7/15 文件（22.2%）。
需要继续完成批次 5 的 8 个大文件，共 2,140 行代码。

## 已完成工作

### 批次 1-4 已推送（7 文件，611 行）

| 文件 | 行数 | 提交 |
|------|------|------|
| web.py | 23 | d091fc4 |
| registration.py | 29 | d091fc4 |
| tasks.py | 65 | d091fc4 |
| materials_collection.py | 95 | 2d04a0e |
| ai_indexing.py | 130 | 8f06049 |
| materials_detail.py | 124 | fb39d2f |
| study_generation.py | 145 | fb39d2f |

## 待完成工作（批次 5）

在 `H:\studybuddy\backend\app\api\` 目录下，需要为以下 8 个文件添加完整的文档注释：

1. **study_rhythm.py** (164 lines) - 学习节奏与时间分配 API
2. **system.py** (238 lines) - 系统配置与能力检测 API
3. **study_learning.py** (258 lines) - 学习记录与进度跟踪 API
4. **study_practice.py** (307 lines) - 练习与答题 API
5. **study_capture_reports.py** (308 lines) - 学习报告与数据导出 API
6. **study_notes.py** (310 lines) - 学习笔记管理 API
7. **study_plans.py** (355 lines) - 学习计划管理 API
8. **ai_retrieval_qa.py** (340 lines) - AI 检索与问答 API

## 文档注释标准

### 1. 模块级注释（文件开头）

```python
"""学习节奏与时间分配 API 端点。

本模块提供学习节奏管理功能，支持：
- 节奏设置的保存与查询（每周/每月目标时间）
- 时间分配的创建、修改、删除（计划任务到具体日期）
- 周趋势统计与周期汇总
- 节奏数据的 JSON 导出

所有端点要求 plan_id 必须存在且属于当前 project。
"""
```

### 2. 函数级注释（每个路由函数）

```python
@app.get("/api/study/plans/{plan_id}/rhythm")
def get_study_rhythm_route(plan_id: str) -> dict[str, object]:
    """查询指定学习计划的节奏设置。
    
    返回已配置的节奏设置（周期类型、时区、起始日期、目标分钟数），
    或未配置状态。不返回时间分配明细。
    
    Args:
        plan_id: 学习计划 ID（最长 255 字符）
    
    Returns:
        dict: 包含 status, plan_id, settings 的响应对象
            - status: "configured" | "not_configured"
            - settings: 节奏设置对象（已配置时）或 None
    
    Raises:
        HTTPException(404): study_rhythm_plan_not_found - 学习计划不存在
        HTTPException(500): study_rhythm_summary_failed - 数据库查询失败
    """
```

### 3. 辅助函数注释

```python
def _bounded_id(value: str, code: str) -> str:
    """验证并返回有界的 ID 字符串。
    
    Args:
        value: 待验证的 ID 字符串
        code: 验证失败时的错误代码
    
    Returns:
        str: 验证通过的 ID
    
    Raises:
        HTTPException(404): 当 ID 为空、超长（>255）或包含控制字符时
    """
```

## 执行步骤

### Step 1: 切换到项目目录
```bash
cd H:\studybuddy
```

### Step 2: 确认当前状态
```bash
git status
git log --oneline -5
```

### Step 3: 按顺序处理文件

每个文件的处理流程：

1. **读取原文件**
   ```bash
   # 查看文件结构
   python -c "import os; print(f'{os.path.getsize('backend/app/api/study_rhythm.py')} bytes')"
   ```

2. **添加文档注释**
   - 在 `from __future__ import annotations` 后添加模块级 docstring
   - 为每个路由函数添加 docstring（包含 Args, Returns, Raises）
   - 为辅助函数（如 `_bounded_id`）添加简要 docstring

3. **提交推送**
   ```bash
   git add backend/app/api/study_rhythm.py
   git commit -m "docs(phase-a): add comprehensive docstrings to study_rhythm.py"
   git push origin master
   ```

4. **更新进度**
   ```bash
   echo "✅ study_rhythm.py (164 lines) - 完成 8/15"
   ```

### Step 4: 批量处理策略

**小批次提交**（推荐）：
- 每完成 1-2 个文件就提交推送
- 保持提交信息清晰：`docs(phase-a): add comprehensive docstrings to <filename>`

**大批次提交**（备选）：
- 完成全部 8 个文件后一次性提交
- 提交信息：`docs(phase-a): add comprehensive docstrings to batch 5 api files (8 files)`

## 注意事项

### 1. 文档注释风格保持一致
- 中文描述 + 英文参数名
- 错误代码使用下划线命名（如 `study_rhythm_plan_not_found`）
- HTTP 状态码写在 Raises 部分

### 2. 不修改代码逻辑
- **只添加** docstring
- **不修改** 函数签名、逻辑或格式
- **不重构** 代码结构

### 3. 文件大小限制
- 单个文件不超过 32 KiB（添加注释后）
- 如果接近限制，优先保证模块级和主要函数的注释

### 4. 特殊文件说明

**study_rhythm.py**:
- 重点：节奏设置、时间分配、周趋势
- 特殊：`_bounded_id` 辅助函数需要注释

**system.py**:
- 重点：系统配置、能力检测（OCR/ASR/Embedding）
- 特殊：包含配置项的读写操作

**study_learning.py**:
- 重点：学习记录的创建、查询、统计
- 特殊：支持幂等性 key

**study_practice.py**:
- 重点：练习集、练习项、答题记录
- 特殊：包含答案验证逻辑

**study_capture_reports.py**:
- 重点：报告生成与导出
- 特殊：包含 AI 生成的报告草稿

**study_notes.py**:
- 重点：笔记的 CRUD
- 特殊：支持附件与标签

**study_plans.py**:
- 重点：计划与卡片组/练习集的管理
- 特殊：最大文件（355 lines）

**ai_retrieval_qa.py**:
- 重点：检索与问答
- 特殊：包含 lexical/vector/hybrid 三种检索模式

## 完成标准

### 每个文件应包含：
- [x] 模块级 docstring（2-5 行）
- [x] 所有路由函数的 docstring（包含 Args, Returns, Raises）
- [x] 辅助函数的简要 docstring
- [x] Git 提交并推送

### Phase A 完成标准：
- [x] 15/15 文件全部添加文档注释
- [x] 所有提交已推送到 GitHub
- [x] 更新 `docs/CODE_DOCUMENTATION_PROJECT.md` 状态为 Phase A 完成

## 验证命令

### 完成后验证
```bash
# 检查文件大小
python backend/scripts/check-source-size.py

# 统计注释行数
python -c "
import os
total_lines = 0
comment_lines = 0
for root, dirs, files in os.walk('backend/app/api'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                total_lines += len(lines)
                comment_lines += sum(1 for line in lines if line.strip().startswith('#') or '\"\"\"' in line)
print(f'Total: {total_lines}, Comments: {comment_lines}, Ratio: {comment_lines/total_lines*100:.1f}%')
"

# 查看提交历史
git log --oneline --grep="docs(phase-a)" | wc -l
```

## 预计时间

- 每个文件：10-15 分钟
- 总计：1.5-2 小时（8 个文件）

## 下一步（Phase A 完成后）

1. 更新项目文档状态
2. 开始 Phase B：Repository 层文档（7-10 天）

---

**准备好了吗？开始执行！**

使用以下 prompt 开始新会话：

```
继续 StudyBuddy Phase A 文档工作。

工作目录：H:\studybuddy
任务：为 backend/app/api/ 下 8 个文件添加文档注释

剩余文件（批次 5）：
1. study_rhythm.py (164 lines)
2. system.py (238 lines)
3. study_learning.py (258 lines)
4. study_practice.py (307 lines)
5. study_capture_reports.py (308 lines)
6. study_notes.py (310 lines)
7. study_plans.py (355 lines)
8. ai_retrieval_qa.py (340 lines)

要求：
- 参考 docs/phase_a_batch5_prompt.md 中的标准
- 参考已完成文件的注释风格（materials_collection.py, ai_indexing.py）
- 每完成 1-2 个文件提交推送一次
- 使用中文描述 + 英文参数名
- 不修改代码逻辑，只添加 docstring

请从 study_rhythm.py 开始，逐个完成。
```
