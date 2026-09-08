# Phase D 执行计划：Schema 和 Adapter 层

## 📋 概览

| 项目 | 内容 |
|------|------|
| **阶段名称** | Phase D - Schema 和 Adapter 层 |
| **优先级** | 🟡 中 |
| **预计工时** | 1-2 天 |
| **文件总数** | 9 个文件 |
| **代码总量** | 565 行 |
| **注释语言** | 中文（功能描述）+ 英文（参数名） |

---

## 📁 文件清单

### Schema 层（5 个文件，379 行）

| 文件 | 行数 | 说明 | 优先级 |
|------|------|------|--------|
| `schemas/study.py` | 127 | 学习相关的 Pydantic 模型 | 🔴 高 |
| `schemas/materials_ai.py` | 127 | 材料和 AI 相关的模型 | 🔴 高 |
| `schemas/local_settings.py` | 60 | 本地配置模型 | 🟡 中 |
| `schemas/connection_test.py` | 63 | 连接测试模型 | 🟡 中 |
| `schemas/__init__.py` | 2 | 模块导出 | 🟢 低 |
| **小计** | **379** | - | - |

### Adapter 层（4 个文件，186 行）

| 文件 | 行数 | 说明 | 优先级 |
|------|------|------|--------|
| `adapters/file_parsers/adapter.py` | 144 | 文件解析适配器（PDF/DOCX/TXT） | 🔴 高 |
| `adapters/file_parsers/models.py` | 38 | 解析结果模型 | 🟡 中 |
| `adapters/file_parsers/__init__.py` | 4 | 子模块导出 | 🟢 低 |
| `adapters/__init__.py` | 0 | 空模块导出 | 🟢 低 |
| **小计** | **186** | - | - |

---

## 🎯 分批策略

### 批次 D1：Schema 层核心模型（254 行，45%）

**工作量**: 2-3 小时

| 文件 | 行数 | 内容 |
|------|------|------|
| `schemas/study.py` | 127 | 学习、练习、计划相关模型 |
| `schemas/materials_ai.py` | 127 | 材料、索引、检索模型 |

**重点关注**：
- Pydantic 模型的字段说明
- 验证规则的业务含义
- 模型之间的关联关系

---

### 批次 D2：Adapter 层（182 行，32%）

**工作量**: 1-2 小时

| 文件 | 行数 | 内容 |
|------|------|------|
| `adapters/file_parsers/adapter.py` | 144 | 文件解析主适配器 |
| `adapters/file_parsers/models.py` | 38 | 解析结果数据模型 |

**重点关注**：
- 文件格式支持（PDF/DOCX/TXT）
- 解析流程和错误处理
- 适配器模式的实现

---

### 批次 D3：配置和辅助模块（129 行，23%）

**工作量**: 1 小时

| 文件 | 行数 | 内容 |
|------|------|------|
| `schemas/local_settings.py` | 60 | 本地配置模型 |
| `schemas/connection_test.py` | 63 | 数据库连接测试 |
| `schemas/__init__.py` | 2 | Schema 模块导出 |
| `adapters/file_parsers/__init__.py` | 4 | 解析器导出 |
| `adapters/__init__.py` | 0 | 空模块 |

**重点关注**：
- 配置项的含义和默认值
- 连接测试的检查逻辑
- 模块导出的完整性

---

## ✍️ 注释标准

### Schema 层注释重点

**1. Pydantic 模型类**

```python
class MaterialBase(BaseModel):
    """材料基础模型。
    
    定义学习材料的核心字段，用于 API 请求和响应。
    所有材料相关的 Pydantic 模型都应继承此基类。
    
    Attributes:
        original_name: 用户上传的原始文件名（保留扩展名）
        media_type: MIME 类型（如 'application/pdf'）
        stored_path: 文件系统存储路径（相对 data_root）
        project_id: 所属项目的唯一标识符
    
    校验规则:
        - original_name 不能为空字符串
        - media_type 必须是标准 MIME 格式
        - stored_path 必须是相对路径（不包含 '..' 或绝对路径）
    """
    original_name: str = Field(..., min_length=1)
    media_type: str
    stored_path: str
    project_id: str
```

**2. 字段级注释**

```python
class StudyPlanCreate(BaseModel):
    """学习计划创建请求。
    
    用户通过此模型创建新的学习计划，包括目标、周期和关联材料。
    """
    
    title: str = Field(..., min_length=1, max_length=200)
    """计划标题（1-200 字符）"""
    
    target_date: date | None = None
    """目标完成日期（可选，用于截止日期提醒）"""
    
    material_ids: list[str] = Field(default_factory=list)
    """关联的材料 ID 列表（可以为空，稍后添加）"""
```

### Adapter 层注释重点

**1. 适配器类**

```python
class FileParserAdapter:
    """文件解析适配器。
    
    提供统一接口解析多种格式的文件（PDF、DOCX、TXT），
    将原始文件内容转换为结构化的文本数据。
    
    支持的格式:
        - PDF: 使用 PyPDF2 提取文本
        - DOCX: 使用 python-docx 提取段落和表格
        - TXT: 直接读取文本内容
    
    使用示例:
        adapter = FileParserAdapter()
        result = adapter.parse_file("/path/to/file.pdf")
        print(result.text_content)
    
    注意:
        - PDF 解析不支持扫描件（需要先 OCR）
        - DOCX 解析会保留基本格式（标题、列表）
        - 大文件（>10MB）可能导致内存不足
    """
```

**2. 方法级注释**

```python
def parse_file(self, file_path: str) -> ParseResult:
    """解析文件并提取文本内容。
    
    根据文件扩展名自动选择合适的解析器，返回统一的
    ParseResult 对象。
    
    Args:
        file_path: 文件的绝对路径
    
    Returns:
        ParseResult 对象，包含:
            - text_content: 提取的纯文本
            - metadata: 文件元数据（页数、作者等）
            - format: 原始文件格式
    
    Raises:
        ValueError: 文件格式不支持时
        FileNotFoundError: 文件路径不存在时
        ParseError: 解析失败时（如 PDF 损坏）
    
    注意:
        此方法会尝试自动检测文件编码（对于 TXT 文件）。
    """
```

---

## ✅ 验收标准

### 代码质量

- [ ] 所有 Pydantic 模型类都有类级 docstring
- [ ] 关键字段有行内注释说明业务含义
- [ ] 所有适配器类和公共方法有完整 docstring
- [ ] 注释符合 Google Style 规范

### 工具检查

```bash
# 静态检查
pydocstyle --convention=google backend/app/schemas/
pydocstyle --convention=google backend/app/adapters/

# 类型检查
mypy backend/app/schemas/
mypy backend/app/adapters/
```

### 文档完整性

- [ ] 每个批次完成后更新 `docs/phase_d_progress.md`
- [ ] Phase D 完成后创建 `docs/phase_d_completion_summary.md`
- [ ] 提交信息清晰标注批次和文件范围

---

## 📅 执行时间表

| 批次 | 文件数 | 行数 | 预计时间 | 累计进度 |
|------|--------|------|----------|----------|
| D1 | 2 | 254 | 2-3 小时 | 45% |
| D2 | 2 | 182 | 1-2 小时 | 77% |
| D3 | 5 | 129 | 1 小时 | 100% |
| **总计** | **9** | **565** | **4-6 小时** | **100%** |

---

## 🚀 开始命令

```text
继续 StudyBuddy Phase D 批次 D1，
从 schemas/study.py 开始（127 行），
然后是 schemas/materials_ai.py（127 行），
使用中文注释
```

---

## 📊 Phase D 在整体项目中的位置

| Phase | 状态 | 文件数 | 代码量 | 完成度 |
|-------|------|--------|--------|--------|
| Phase A | ✅ | 15 | 2,891 行 | 100% |
| Phase B | ✅ | 9 | 362 行 | 100% |
| Phase C | ✅ | 10 | 1,197 行 | 100% |
| **Phase D** | **⏳** | **9** | **565 行** | **0%** |
| Phase E | 🔮 | 待定 | 待定 | 0% |
| Phase F | 🔮 | _legacy | ~7,000 行 | 0% |
| **总计** | - | **43/~60** | **5,015/~12,000** | **42%** |

---

**文档创建时间**: 2025-01-17  
**计划状态**: 📋 待执行  
**下一步**: 启动批次 D1
