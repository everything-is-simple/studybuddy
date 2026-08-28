# A2.1：收缩 `repositories/_legacy.py`——repository 实现按域迁移

> 这是 A2.X 的第一个独立任务。A2.X 总任务见 [`A2_X_BOUNDDED_CORE_SPLIT_PROMPT.md`](A2_X_BOUNDDED_CORE_SPLIT_PROMPT.md)，任务编号和路线位置见 [`ROADMAP_CAPABILITIES.md`](../../ROADMAP_CAPABILITIES.md)。

## 1. 执行位置、阶段与目标

请在 `H:\studybuddy` 执行任务 **A2.1**。

当前路线位置：

```text
A0 已完成
→ A1 已完成：repository.py 兼容 façade 与域出口
→ A2 已完成：main.py 后端应用结构拆分
→ A2.1 当前任务：收缩 repositories/_legacy.py
→ A2.2：收缩 main.py
→ A2.3：收缩 migrations/runner.py
→ A2.4：收缩 providers.py
→ A3：正式静态前端与多页原生应用壳
```

当前分支和基线：

- 正式仓库：`H:\studybuddy`
- 当前分支：`master`
- 当前 HEAD：`396e30a docs: add A2.X core oversized file split roadmap tasks`
- 远端：`origin/master` 已同步
- 当前部署边界：local-disk、SQLite、单进程、单实例、单一 `data_root`、loopback 服务；不得扩展为多用户、多进程、云同步或生产规模部署。
- 当前正式 schema：v13。

本任务只处理一个生产文件：

```text
backend/app/repositories/_legacy.py
```

当前大小约：

```text
379,741 bytes
```

最终目标：

- `_legacy.py` 删除，或缩小为不超过 **32 KiB** 的极薄兼容 glue。
- 所有新增或实质重写源码文件不超过 **32 KiB**，目标 20–30 KiB。
- repository 业务实现必须分布到已有或新增的清晰 domain modules，而不是复制到另一个巨型文件。
- `backend/app/repository.py` 继续作为稳定兼容 façade，不得成为新的实现汇聚点。

## 2. 已完成结构与当前事实

A1 已建立以下结构：

```text
backend/app/repository.py                 # 稳定兼容 façade
backend/app/repositories/
  __init__.py
  connection.py
  materials.py
  ai.py
  plans.py
  learning.py
  practice.py
  capture.py
  reports.py
  tasks.py
  _legacy.py                              # 当前仍承载大量真实函数体
```

A2 已建立后端应用边界，但 A2.1 不得重新改动 API 路由、生命周期或前端。

A2 已验证的兼容基线：

- 完整 backend：`413 passed, 2 skipped`
- 完整 browser：`52 passed, 1 skipped`
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

A1 repository façade 基线：

- `backend/app/repository.py` 有 305 个既有公开符号。
- 测试和生产代码可能直接 import `backend.app.repository` 的函数。
- 测试可能 monkeypatch `backend.app.repository`、`backend.app.repositories.*` 或跨域私有 helper。
- 当前 `_legacy.py` 中的函数实现仍有跨域依赖；不能假设 A1 已完成内部函数体解耦。

## 3. 必须保护的不变量

### 3.1 Public API 与导入兼容

必须保持：

- `backend.app.repository` 的全部既有公开符号、名称、函数签名和调用方式。
- A1 已验证的 305 个 public symbols：不得减少、错误重绑定或产生不可预期的 duplicate implementation。
- 生产模块现有 import paths 可继续工作。
- 测试直接 import 的函数和常量继续工作。
- 若旧代码对函数 identity 有依赖，必须保留 identity 或记录经过验证的兼容替代方案。
- 不得以 `__getattr__`、动态 import、运行时源码执行或隐式全局污染掩盖缺失导出。

### 3.2 SQL、事务和返回值

必须逐项保持：

- SQL 语句语义、查询条件、排序、分页、limit、过滤和 join。
- `connect()`、事务边界、`BEGIN`/commit/rollback、WAL、busy timeout 和锁行为。
- repository 函数的输入验证、异常类型、稳定错误码、返回 dict/list/row 的结构。
- material/extraction/text span/source lifecycle。
- revision/chunk/retrieval/context/citation 和 AI operation。
- cards/exercises/reviews/attempts。
- plans/goals/modules/progress、notes/rhythm。
- practice/mistake/weak-point/cram。
- capture/transcript/source ingestion。
- reports/delivery audit。
- tasks/operation/embedding operation。

不得在 A2.1 中修复业务 bug、改变排序、统一命名、改错误码或调整 schema。

### 3.3 数据和安全

不得：

- 修改 migration、schema、`PRAGMA user_version` 或数据库文件。
- 新增 runtime `CREATE TABLE`。
- 改变 backup/restore 数据内容或 schema history。
- 把 secret、raw prompt/response、原文、绝对路径、SQL 或 traceback 写入日志、错误响应或普通 evidence。
- 提交数据库、uploaded originals、测试 artifact、Playwright report、临时输出或私有路径。

## 4. A2.1 工作方式：先审计，后按域迁移

### 4.1 第一步：建立 machine-checkable inventory

在修改代码前，使用 AST 和静态搜索建立审计结果。至少记录：

1. `_legacy.py` 中全部顶层函数、常量和 import。
2. 每个函数的：
   - 名称、起止行号、字节数；
   - 所属领域；
   - 本地 helper 依赖；
   - `_legacy.py` 内部调用的其它函数；
   - 外部生产调用方；
   - 测试 import/monkeypatch 点；
   - 是否跨域调用；
   - 是否涉及 transaction、source lifecycle、citation、operation/task。
3. 对比已有 `repositories/*.py` 的导出与实现，识别已经迁移的函数，避免重复实现。
4. 建立旧路径 → 新路径 → façade 出口 → monkeypatch 目标表。
5. 建立循环依赖风险图。
6. 记录基线结果和当前文件 hash/size。

推荐使用 Python AST，不要依靠正则复制函数体。审计结果应写入：

```text
docs/prompts/architecture/A2_1_REPOSITORY_LEGACY_EVIDENCE.md
```

该 evidence 文件必须是脱敏的，不含绝对私有路径、原文、secret、数据库内容或原始 provider response。

### 4.2 第二步：冻结迁移分组

推荐按以下顺序处理，必要时可在 evidence 中说明调整：

```text
A2.1-a  connection/common primitives
A2.1-b  materials
A2.1-c  ai/retrieval/citation/Q&A/indexing
A2.1-d  study/cards/exercises/reviews
A2.1-e  plans/learning/notes/rhythm
A2.1-f  practice/cram/mistakes
A2.1-g  capture/transcript
A2.1-h  reports/delivery
A2.1-i  tasks/operation/embedding task state
A2.1-j  final façade cleanup and legacy removal
```

每一组应单独完成：

1. 移动真实函数定义，而不是复制函数体。
2. 只补齐该域需要的 imports 和明确 dependency imports。
3. 更新显式 exports/`__all__`。
4. 更新 `repository.py` façade 的转发绑定。
5. 检查所有生产调用方和测试 import。
6. 检查 monkeypatch 是否仍作用于真实执行路径。
7. 运行该域 focused tests、compile、import smoke 和 size check。
8. 记录迁移前后 symbol/function identity、文件大小和测试结果。

### 4.3 跨域 helper 规则

跨域 helper 不得全部留在 `_legacy.py`。按以下优先级处理：

1. 无业务语义的 connection/time/row conversion primitive 放入小型 shared module。
2. 只有一个领域使用的 helper 放入该领域模块，并通过显式导入使用。
3. 多域使用但有清晰基础语义的 helper 放入明确命名的 bounded common module。
4. 暂时不能迁移的 helper 可留在 `_legacy.py`，但必须在 evidence 中列出原因、调用方和后续收口点；不能把整个域因方便而留回去。
5. 禁止 domain A import domain B 的私有 helper；跨域调用必须使用稳定、显式的 domain API。
6. 禁止新模块 import `_legacy.py` 以继续调用大文件实现；这只会制造伪拆分。
7. 禁止把所有原函数重新 re-export 到一个新大文件。

### 4.4 Monkeypatch 兼容规则

必须审计以下情况：

- `monkeypatch.setattr(repository, "function", replacement)`。
- `monkeypatch.setattr("app.repository.function", replacement)`。
- 对 `app.repositories.materials` 等域模块的 patch。
- 测试 patch `connect`、时间函数、provider/retrieval helper、storage helper 或 transaction helper。

如果新模块通过 `from ... import helper` 固化了不可更新绑定，必须改为可 patch 的显式依赖方式，或在 façade/dispatcher 层同步更新。不能只让 import 语法看起来正确而使 patch 静默失效。

## 5. 禁止事项

- 不改 `backend/app/main.py`、`backend/app/api/`、`backend/app/app_factory.py`、frontend 或 browser workspace，除非为修复 A2.1 导致的明确 import compatibility 回归，且必须记录。
- 不修改任何 migration、schema、DDL、数据库数据或 backup format。
- 不新增 API、字段、状态、错误码、Provider 能力或前端行为。
- 不复制 `_legacy.py` 为另一个超过 32 KiB 的文件。
- 不创建 `all_repositories.py`、`repository_legacy_v2.py` 或其它巨型兼容层。
- 不用压缩、base64、动态下载、运行时生成或 `exec` 隐藏源码体积。
- 不删除失败数据库、备份、原件或测试证据。
- 不在完整回归前提交“看起来已经拆完”的中间状态。

## 6. 测试和验收

### 6.1 每个迁移组

使用项目 Python 环境：

```powershell
C:\miniconda\py310\python.exe -m pytest <focused-tests> -q
python -m compileall -q backend/app
python backend/scripts/check-source-size.py --main-html-sha256 1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c
 git diff --check
```

重点测试范围按域选择，至少包括：

- `test_repository.py`、`test_repository_*`（如存在）
- `test_file_import_path.py`
- `test_material_*`
- `test_retrieval.py`
- `test_qa_api.py`
- `test_ai_citation_lifecycle.py`
- `test_phase8_generation.py`
- `test_phase9a_*`
- `test_phase9b_*`
- `test_phase9c_*`
- `test_phase9d_*`
- `test_task_runner.py`
- `test_phase10_*`
- backup/restore、startup/preflight 和 governance tests

以实际仓库中的测试文件为准，不要因文件名不存在而伪造结果。

### 6.2 最终 A2.1 门禁

必须验证：

1. `_legacy.py` <= 32 KiB，或已删除。
2. 所有新增/实质重写生产源码 <= 32 KiB，且不存在新的巨型 repository/compatibility 文件。
3. `repository.py` public symbol inventory 仍为 305/305。
4. 没有重复实现：每个迁移函数只有一个真实定义。
5. 没有循环导入。
6. `PYTHONPATH=backend python -c "import app.repository; import app.main; print(len(app.main.app.routes))"` 通过。
7. schema version 仍为 v13。
8. migration registry 未改变。
9. route inventory 仍为业务 151、总计 155。
10. `INDEX_HTML` hash 仍为：

```text
1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c
```

11. 相关 repository transaction/source lifecycle/backup/restore focused tests 通过。
12. 完整 backend regression 不低于当前基线：

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/ -q
```

目标：`413 passed, 2 skipped`；若测试数量变化，必须解释变化。

13. A2.1 不涉及 UI 时至少运行受影响的 browser smoke；如果 import/应用行为有变化，重新串行运行完整 browser suite，并以实际结果为准。
14. 启动和 CLI smoke：

```powershell
cd backend
C:\miniconda\py310\python.exe -m app --help
```

以及 `app.main:app` import、liveness/health/readiness smoke。

## 7. 文档、提交和回退

### 7.1 文档

完成后更新：

- `docs/prompts/architecture/A2_1_REPOSITORY_LEGACY_EVIDENCE.md`
- `docs/STATUS.md`
- `docs/ROADMAP_CAPABILITIES.md` 中 A2.1 状态
- 必要时 `docs/ARCHITECTURE.md` 和 `docs/prompts/architecture/A0_ROUTE_REPOSITORY_MAP.md`

`docs/TODO.md` 是已冻结大小的既有超限文件，不能增长；不要为了记录 A2.1 修改它。A2.X 任务以 `ROADMAP_CAPABILITIES.md` 和本 Prompt/evidence 为权威记录。

文档必须明确：

- 最终 `_legacy.py` 状态和大小；
- 新增/修改模块清单及大小；
- 305 public symbols 对比；
- monkeypatch/import 兼容结论；
- focused/full/backend/browser 测试命令和结果；
- 未验证边界；
- A2.2、A2.3、A2.4 和 A3 尚未开始或仍未完成。

### 7.2 提交

推荐按域拆分提交：

```text
refactor: move repository connection primitives out of legacy
refactor: move repository materials domain out of legacy
refactor: move repository ai domain out of legacy
refactor: move repository study domain out of legacy
refactor: move repository plans and learning domains out of legacy
refactor: move repository practice domain out of legacy
refactor: move repository capture and reports domains out of legacy
refactor: move repository tasks domain out of legacy
refactor: remove repository legacy implementation
```

每个提交必须可回退、可解释、通过该批次 focused tests。若当前仓库的提交策略要求单个任务一个最终提交，可以在全部批次通过后 squash，但不得丢失迁移证据。

### 7.3 回退

失败时：

- 只回退当前代码提交；
- 不执行数据库 rollback；
- 不删除 data root、数据库、原件或 verified backup；
- 不手工修改 `schema_migrations` 或 `PRAGMA user_version`；
- 保留脱敏测试结果和 failure evidence；
- 先恢复上一个可运行提交，再分析下一批。

## 8. 完成报告格式

最终报告必须包含：

1. A2.1 的实际迁移顺序和目标结构。
2. `_legacy.py` 的初始/最终大小与最终状态。
3. 新增/修改文件及大小，确认没有新巨型替代文件。
4. repository public inventory：旧/新数量与差异。
5. 函数重复定义和循环导入检查结果。
6. monkeypatch/import 兼容验证结果。
7. schema/migration/route/HTML identity 验证结果。
8. focused tests、完整 backend、browser smoke/full browser 的实际命令与结果。
9. skip 项、未验证边界和残余风险。
10. commit hashes、推送分支和最终 `git status`。

只有在所有门禁真实通过后，才可以将 A2.1 标记为完成，并开始 A2.2。A2.1 完成不代表 A2.X 全部完成，也不代表 A3 前端迁移开始或完成。
