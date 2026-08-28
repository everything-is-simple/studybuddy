# A2.2：收缩 `backend/app/main.py`——兼容导出与内嵌 HTML 机械分片

> 这是 A2.X 的第二个独立任务。A2.X 总任务见 [`A2_X_BOUNDDED_CORE_SPLIT_PROMPT.md`](A2_X_BOUNDDED_CORE_SPLIT_PROMPT.md)，任务编号和路线位置见 [`ROADMAP_CAPABILITIES.md`](../../ROADMAP_CAPABILITIES.md)。

## 1. 执行位置、阶段与目标

请在 `H:\studybuddy` 执行任务 **A2.2**。

当前路线位置：

```text
A0 已完成
→ A1 已完成：repository.py 兼容 façade 与域出口
→ A2 已完成：main.py 后端应用结构拆分
→ A2.1 已完成：收缩 repositories/_legacy.py
→ A2.2 当前任务：收缩 main.py
→ A2.3：收缩 migrations/runner.py
→ A2.4：收缩 providers.py
→ A3：正式静态前端与多页原生应用壳
```

当前分支和基线：

- 正式仓库：`H:\studybuddy`
- 当前分支：`master`
- 当前 HEAD：`f52d542` (refactor: split repository _legacy.py into bounded parts (A2.1))
- 远端：`origin/master` 已同步
- 当前部署边界：local-disk、SQLite、单进程、单实例、单一 `data_root`、loopback 服务；不得扩展为多用户、多进程、云同步或生产规模部署。
- 当前正式 schema：v13。

本任务只处理一个生产文件：

```text
backend/app/main.py
```

当前大小：

```text
156,889 bytes (233 lines)
- INDEX_HTML: 146,610 bytes (lines 11-213)
- 其他代码: ~10,279 bytes (lines 1-10, 214-233)
```

最终目标：

- `main.py` <= 32 KiB，最终仅保留薄兼容导出层。
- INDEX_HTML 内嵌的单页应用必须逐字节一致地机械分片到独立文件，不做 A3 前端重构。
- 保持 `backend/app/main` 模块的既有兼容导出：`create_app`、`app`、`INDEX_HTML`（如必要）。
- 所有新增或实质重写源码文件不超过 32 KiB，目标 20–30 KiB。
- A2 已建立的应用工厂、生命周期和 API routers 不受 A2.2 影响；A2.2 只处理 `main.py` 的机械分片。

## 2. 已完成结构与当前事实

A2 已建立以下结构（这些文件在 A2.2 中不变）：

```text
backend/app/
  app_factory.py          # FastAPI 应用创建、中间件、异常映射
  lifespan.py             # startup/shutdown 生命周期
  api/
    registration.py       # 路由注册
    [其他 API 模块...]    # materials, ai, study, plans, etc.
  main.py                 # 当前承载 INDEX_HTML + 兼容导出
```

A2.2 已验证的兼容基线：

- 完整 backend：`413 passed, 2 skipped`
- 完整 browser：适用时重新验证
- FastAPI 业务路由：151 条
- FastAPI 总路由：155 条
- `app.main.create_app` 可用
- `app.main.app` 可用
- `uvicorn app.main:app` 兼容
- `python -m app --help` 可用
- `INDEX_HTML` 当前 payload SHA-256：

```text
1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c
```

## 3. 必须保护的不变量

### 3.1 Public API 与导入兼容

必须保持：

- `backend.app.main` 模块可继续 import。
- 既有兼容符号：`create_app`、`app`（如生产或测试需要）、`INDEX_HTML`（如路由需要）。
- 生产代码、测试、CLI、启动脚本中的 import paths 继续工作。
- `uvicorn app.main:app` 或等效启动方式继续可用。
- 既有的 browser 测试启动逻辑不受破坏。

### 3.2 HTML 内容与行为

必须逐字节保持：

- INDEX_HTML 字符串内容的逐字节一致性（SHA-256 不变）。
- 所有内嵌 `<style>`、`<script>` 和 HTML 结构。
- 既有页面功能、状态管理、事件处理、导航、搜索、问答、学习、计划、笔记、练习、报告和课堂采集。
- 既有的 ARIA 标记、可访问性语义、焦点管理和键盘导航。
- 既有的响应式布局、narrow 模式、对话框、toast 和页面级状态通知。

不得在 A2.2 中：

- 修改 HTML 结构、CSS 样式或 JavaScript 逻辑。
- 引入 React、Vue、Vite 或其他前端框架。
- 改变 API 路径、请求格式、响应格式或错误码。
- 修改页面元素 ID、CSS 类名或 ARIA 属性。
- 改变 localStorage、sessionStorage 或 URL 参数契约。

A2.2 只做机械分片：把 INDEX_HTML 的内容原样搬到独立文件，并保持相同的字节序列和运行时行为。

### 3.3 数据和安全

不得：

- 修改 migration、schema、`PRAGMA user_version` 或数据库文件。
- 新增 runtime `CREATE TABLE`。
- 改变 backup/restore 数据内容或 schema history。
- 把 secret、raw prompt/response、原文、绝对路径、SQL 或 traceback 写入日志、错误响应或普通 evidence。
- 提交数据库、uploaded originals、测试 artifact、Playwright report、临时输出或私有路径。

## 4. A2.2 工作方式：机械分片内嵌 HTML，保留兼容导出

### 4.1 当前 `main.py` 结构

```python
# Lines 1-10: imports and module setup
"""Backward-compatible FastAPI application entrypoint."""
from __future__ import annotations
import sys
import types
from . import app_factory
from .api.registration import ROUTE_MODULES

# Lines 11-213: INDEX_HTML constant (146,610 bytes)
INDEX_HTML = """<!doctype html>
<html lang="zh-CN">...</html>
<script>...</script>
"""

# Lines 214-233: compatibility exports (~544 bytes)
class _MainModule(types.ModuleType):
    ...

sys.modules[__name__].__class__ = _MainModule
app = app_factory.create_app()
create_app = app_factory.create_app
```

### 4.2 目标结构

**方案一：INDEX_HTML 移至独立 `.html` 文件**

```text
backend/app/
  main.py                          # <= 1 KiB 薄兼容导出
  templates/
    index.html                     # 146,610 bytes 内嵌单页应用
  app_factory.py                   # 已有
  ...
```

`main.py` 新内容（示例）：

```python
"""Backward-compatible FastAPI application entrypoint."""
from __future__ import annotations
import sys
import types
from pathlib import Path
from . import app_factory
from .api.registration import ROUTE_MODULES

# Load INDEX_HTML from template file for backward compatibility
_template_path = Path(__file__).parent / 'templates' / 'index.html'
INDEX_HTML = _template_path.read_text(encoding='utf-8')

class _MainModule(types.ModuleType):
    ...

sys.modules[__name__].__class__ = _MainModule
app = app_factory.create_app()
create_app = app_factory.create_app
```

`app_factory.py` 或相关路由模块需要更新以从文件读取 HTML，而不是从 `main.INDEX_HTML`。

**方案二：INDEX_HTML 分片为多个常量模块**

如果路由必须使用 Python 常量而不是模板文件：

```text
backend/app/
  main.py                          # <= 1 KiB 薄兼容导出
  _html_payload.py                 # 或分为 _html_part_00.py, _html_part_01.py 等
  app_factory.py
  ...
```

每个 `_html_part_*.py` <= 32 KiB，包含原始 HTML 字符串片段。`main.py` 从这些模块组装完整 INDEX_HTML。

**推荐：方案一**（独立 `.html` 文件）

- 更清晰的关注点分离。
- 浏览器测试和静态分析可直接访问 HTML 文件。
- 为 A3 静态前端迁移铺平道路。
- Python 源码大小检查不包括 `.html` 文件。

### 4.3 实施步骤

1. **创建 `backend/app/templates/` 目录。**
2. **提取 INDEX_HTML 内容**：从 `main.py` lines 11-213 提取 HTML 字符串常量的内容（不含 `INDEX_HTML = """` 和结尾 `"""`），写入 `backend/app/templates/index.html`。
3. **验证字节一致性**：计算新文件的 SHA-256，确认与原 INDEX_HTML payload 一致。
4. **更新 `main.py`**：
   - 删除 INDEX_HTML 字符串常量。
   - 添加从 `templates/index.html` 读取的逻辑。
   - 保留 `create_app`、`app` 和 `INDEX_HTML` 兼容导出。
5. **更新路由或 app_factory（如需要）**：如果 `app_factory.py` 或其他模块直接引用 `main.INDEX_HTML`，改为从文件读取或从 `main` 模块导入。
6. **运行 compile check**：`python -m compileall -q backend/app`。
7. **运行 import smoke**：`PYTHONPATH=backend python -c "import app.main; print(app.main.app, len(app.main.INDEX_HTML))"`。
8. **运行完整 backend 测试**：`python -m pytest backend/tests/ -q`。
9. **验证 INDEX_HTML SHA-256 不变**：

```python
import hashlib
from pathlib import Path
content = Path('backend/app/templates/index.html').read_text(encoding='utf-8')
print(hashlib.sha256(content.encode('utf-8')).hexdigest())
# 必须输出：1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c
```

10. **运行 browser 测试或 smoke**（如适用）。
11. **运行源码大小检查**：`python backend/scripts/check-source-size.py --main-html-sha256 1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c`。

### 4.4 兼容性注意事项

- 如果 `app_factory.py` 或任何路由模块中有 `from .main import INDEX_HTML` 或 `import app.main; ... app.main.INDEX_HTML`，在分片后仍需能访问。
- 如果有 browser 测试或 CLI 需要 `INDEX_HTML` 在 Python 中可用，保留 `main.INDEX_HTML` 导出。
- 如果 FastAPI 路由使用 `HTMLResponse(INDEX_HTML)`，确保 INDEX_HTML 可访问。
- 模板文件路径使用相对于 `__file__` 的方式，避免硬编码绝对路径。

### 4.5 如果使用方案二（分片常量）

如果必须保留 Python 常量而不是文件：

1. 将 INDEX_HTML 按 ~24 KiB 分片为多个常量字符串。
2. 创建 `_html_part_00.py`, `_html_part_01.py`, ... 每个 <= 32 KiB。
3. `main.py` 组装：

```python
from ._html_part_00 import HTML_PART_00
from ._html_part_01 import HTML_PART_01
# ...
INDEX_HTML = HTML_PART_00 + HTML_PART_01 + ...
```

但这增加了复杂性，且不如独立 `.html` 文件清晰。仅在有技术约束时使用。

## 5. 禁止事项

- 不改 `backend/app/app_factory.py`、`backend/app/lifespan.py`、`backend/app/api/`、frontend、browser workspace，除非为修复 A2.2 导致的明确 import 或路由兼容回归，且必须记录。
- 不修改任何 migration、schema、DDL、数据库数据或 backup format。
- 不新增 API、字段、状态、错误码、Provider 能力或前端行为。
- 不修改 INDEX_HTML 的内容、结构、样式或脚本逻辑。
- 不引入 React、Vue、Vite 或其他前端框架。
- 不修改 HTML 元素 ID、CSS 类名、ARIA 属性或 JavaScript 变量名。
- 不修改 API 路径、请求格式、响应格式或错误码。
- 不删除失败数据库、备份、原件或测试证据。
- 不在完整回归前提交"看起来已经拆完"的中间状态。

## 6. 测试和验收

### 6.1 每个变更后

使用项目 Python 环境：

```powershell
python -m compileall -q backend/app
PYTHONPATH=backend python -c "import app.main; print(app.main.app, len(app.main.INDEX_HTML))"
python backend/scripts/check-source-size.py --main-html-sha256 1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c
git diff --check
```

### 6.2 INDEX_HTML 内容验证

```powershell
python - <<'PY'
import hashlib
from pathlib import Path
# 如果使用 templates/index.html
content = Path('backend/app/templates/index.html').read_text(encoding='utf-8')
actual = hashlib.sha256(content.encode('utf-8')).hexdigest()
expected = '1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c'
print(f'SHA-256: {actual}')
assert actual == expected, 'INDEX_HTML content changed'
print('✓ INDEX_HTML content verified')
PY
```

### 6.3 最终 A2.2 门禁

必须验证：

1. `main.py` <= 32 KiB。
2. 如使用 `templates/index.html`：文件存在，SHA-256 为 `1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c`。
3. 如使用分片常量：每个 `_html_part_*.py` <= 32 KiB，组装后 SHA-256 一致。
4. `main.INDEX_HTML` 可访问且内容不变。
5. `main.create_app` 可用。
6. `main.app` 可用。
7. `python -m compileall -q backend/app` 通过。
8. Schema version 仍为 v13。
9. Migration registry 未改变。
10. Route inventory 仍为业务 151、总计 155。
11. 完整 backend regression 不低于当前基线：

```powershell
python -m pytest backend/tests/ -q
```

目标：`413 passed, 2 skipped`；若测试数量变化，必须解释变化。

12. 如有受影响的 browser 测试，重新运行相关 suite。
13. 启动和 CLI smoke：

```powershell
cd backend
python -m app --help
```

以及 `app.main:app` import、liveness/health/readiness smoke。

## 7. 文档、提交和回退

### 7.1 文档

完成后更新：

- `docs/prompts/architecture/A2_2_MAIN_SPLIT_EVIDENCE.md`
- `docs/STATUS.md`
- `docs/ROADMAP_CAPABILITIES.md` 中 A2.2 状态

`docs/TODO.md` 是已冻结大小的既有超限文件，不能增长；不要为了记录 A2.2 修改它。A2.X 任务以 `ROADMAP_CAPABILITIES.md` 和本 Prompt/evidence 为权威记录。

文档必须明确：

- 最终 `main.py` 大小和结构。
- INDEX_HTML 的新位置（文件路径或分片模块）。
- INDEX_HTML SHA-256 验证结果。
- `main.INDEX_HTML`、`main.app`、`main.create_app` 兼容验证。
- Compile、import、backend、browser 测试命令和结果。
- 未验证边界。
- A2.1 已完成，A2.3、A2.4 和 A3 尚未开始或仍未完成。

### 7.2 提交

推荐提交信息：

```text
refactor: extract INDEX_HTML from main.py to template file (A2.2)
```

或

```text
refactor: split main.py INDEX_HTML into bounded constant modules (A2.2)
```

提交必须可回退、可解释、通过所有必须门禁。

### 7.3 回退

失败时：

- 只回退当前代码提交；
- 不执行数据库 rollback；
- 不删除 data root、数据库、原件或 verified backup；
- 不手工修改 `schema_migrations` 或 `PRAGMA user_version`；
- 保留脱敏测试结果和 failure evidence；
- 先恢复上一个可运行提交，再分析问题。

## 8. 完成报告格式

最终报告必须包含：

1. A2.2 的实际实施方式（方案一或方案二）。
2. `main.py` 的初始/最终大小与最终结构。
3. INDEX_HTML 的新位置（文件路径或分片模块列表及大小）。
4. INDEX_HTML SHA-256 验证结果（必须为 `1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c`）。
5. `main.INDEX_HTML`、`main.app`、`main.create_app` 兼容性验证。
6. Compile、import smoke、源码大小检查结果。
7. Schema/migration/route/HTML identity 验证结果。
8. Backend/browser 测试的实际命令与结果。
9. Skip 项、未验证边界和残余风险。
10. Commit hash、推送分支和最终 `git status`。

只有在所有门禁真实通过后，才可以将 A2.2 标记为完成，并开始 A2.3。A2.2 完成不代表 A2.X 全部完成，也不代表 A3 前端迁移开始或完成。
