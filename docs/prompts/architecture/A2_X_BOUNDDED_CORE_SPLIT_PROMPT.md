# A2.X：核心超大文件收缩——repository legacy、migration runner、main façade 与 providers

> 任务编号已落入 `docs/ROADMAP_CAPABILITIES.md`：A2.1 对应 `_legacy.py`，A2.2 对应 `main.py`，A2.3 对应 `migrations/runner.py`，A2.4 对应 `providers.py`。

> 本 Prompt 用于在 A2 完成、A3 开始之前执行 A2.X。它是一个独立的、行为保持型架构任务，不是新能力开发，也不是 A3 前端重做。

## 0. 执行位置与任务身份

请在 `H:\studybuddy` 执行任务 **A2.X**。

当前路线图：

- 权威路线图：`docs/ROADMAP_CAPABILITIES.md`（《StudyBuddy 能力补齐、架构拆分与桌面化路线图》）。
- 当前阶段：A2 已完成，A3 尚未开始。
- A2.X 的目的：继续收缩三个仍然过大的核心文件，使它们成为可维护的薄入口或按职责拆分后的普通模块，同时保持所有既有行为、API、数据库和前端契约。
- A2.X 不得提前实现真实 ASR、真实 OCR、报告新能力、真实外发、桌面化或 React/Vue/Vite 迁移。
- A2.X 不得借重构之名修改业务语义、schema 语义、migration 历史、用户数据、API 契约或现有浏览器行为。

目标文件及当前约略大小：

```text
backend/app/repositories/_legacy.py   379,741 bytes
backend/app/migrations/runner.py        68,846 bytes
backend/app/main.py                    156,889 bytes
```

当前 HEAD 为 A2 已推送版本：

```text
8629881 docs: record bounded A2 application split
```

A2 已完成的事实：

- `main.py` 已拆出 `app_factory.py`、`lifespan.py`、HTTP helpers/errors、schemas/services 和 `backend/app/api/` 路由模块。
- `backend/app/api/registration.py` 按既有顺序注册 151 条业务路由；FastAPI 总路由数为 155。
- `app.main.create_app`、`app.main.app`、`uvicorn app.main:app`、CLI 和现有 monkeypatch 兼容路径必须继续有效。
- `backend/app/repository.py` 已是兼容 façade；`backend/app/repositories/` 有按域出口，但多个域的实际函数实现仍集中在 `_legacy.py`。
- `main.py` 仍保留完整的历史 inline `INDEX_HTML`，其当前 HTML payload SHA-256 为：

```text
1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c
```

- A2 验证基线：完整 backend `413 passed, 2 skipped`；完整 browser `52 passed, 1 skipped`。

## 1. 总目标

在不改变外部行为的前提下，将三个文件缩小到合适尺寸：

- 每个新增或实质重写的源码文件不超过 **32 KiB**，目标为 **20–30 KiB**。
- `backend/app/repositories/_legacy.py` 不再承载所有 repository/domain 函数体。
- `backend/app/migrations/runner.py` 只负责 migration registry、事务执行、版本一致性、错误边界和公共 migration contract，不再承载全部 DDL 文本与所有 migration 实现。
- `backend/app/main.py` 只负责稳定兼容导出、ASGI 对象、应用入口和必要的薄转发；不得继续承载业务路由、生命周期实现或超大 inline UI。
- 不得用一个新的 `web_ui.py`、`legacy.py`、`static.py`、`all_migrations.py`、`all_repositories.py` 或任何其它大文件替代旧大文件。
- 不得通过压缩、删除、截断、动态下载、运行时生成、编码混淆或字符串拼接隐藏大文件问题。

“合适尺寸”不是机械追求行数；必须以职责边界、依赖关系、可测试性和稳定兼容性为准。一个文件接近 32 KiB 时，应继续按域/职责拆分，而不是把上限当作目标。

## 2. 不可破坏的不变量

### 2.1 API 与应用入口

必须保持：

- 所有 URL、HTTP method、路由注册顺序、状态码、错误码、错误 JSON/detail、response model、media type 和幂等语义。
- 151 条业务路由及 155 条 FastAPI 总路由。
- `/` 的产品页面行为、DOM accessible name、CSS/JS 行为、键盘路径、窄屏布局、失败与 retry 行为。
- `app.main.create_app(config=None)`、`app.main.app`、`uvicorn app.main:app` 和 `python -m app`。
- 测试对 `app.main`、`app_factory`、repository、provider、lifespan 和其它模块的 monkeypatch 行为。
- readiness 只在 preflight → migration/connect → audit → recovery 完成后变为 ready；shutdown、instance lock、middleware 和 observability 顺序不变。

### 2.2 Repository 与事务

必须保持：

- `backend/app/repository.py` 的全部既有公开符号、函数签名、导入路径和测试直接 import 兼容性。
- 当前 repository façade 的公开 inventory（A1 已验证为 305 个公开符号）不减少。
- SQL、查询条件、排序、分页、事务边界、`BEGIN`/rollback 行为、SQLite lock/WAL、错误映射和返回值不变。
- material/extraction/text span/source lifecycle、revision/chunk/retrieval/citation、AI artifact、plans/learning/practice/capture/reports/tasks 的数据不变量不变。
- 不能因为拆文件而复制一份函数实现，造成两个版本、函数 identity 改变或 monkeypatch 只作用于一份实现。
- 跨域调用必须通过明确的稳定模块出口；私有 helper 的迁移要有依赖图和兼容策略。

### 2.3 Migration 与数据库

必须保持：

- 当前正式 schema version（v13）不变。
- `_MIGRATIONS` 的版本号、名称、顺序和 migration history 不变。
- `schema_migrations` 与 `PRAGMA user_version` 一致。
- new DB、v1–v13 upgrade、重复运行幂等、事务 rollback、失败后无半迁移状态。
- 不修改 DDL、字段、索引、CHECK、FK、UNIQUE、默认值、触发器或业务数据语义。
- 不新增 migration，不删除 migration，不重编号，不重写既有 migration 内容。
- 不把 migration 变成运行时 ad-hoc `CREATE TABLE IF NOT EXISTS`；所有 schema 变化仍只能通过 runner 管理的连续 migration。
- backup/restore 必须保持 schema version、migration history 和 existing data compatibility。

### 2.4 安全边界

不得暴露或记录：

- secret/provider key、绝对路径、SQL、traceback、原始 Provider/tool response、原件、未经批准的正文或测试隐私数据。
- 不得提交数据库、uploaded originals、生成 artifact、Playwright report、临时输出或个人路径。

## 3. 允许的目标结构

可以微调命名，但必须先做 inventory 并记录最终映射。推荐结构如下：

```text
backend/app/
  main.py                         # 薄兼容入口；目标 <= 32 KiB
  app_factory.py                  # 已有 A2 factory，继续保持小型
  lifespan.py                     # 已有生命周期模块
  api/                            # 已有按域路由模块
  ui_fragments/                   # 仅在必要时使用，逐片段 <= 32 KiB
    __init__.py
    index_shell.py 或 .html       # 仅保存原有 UI 的机械分片
    ...
  repositories/
    connection.py
    materials.py
    ai.py
    study.py 或现有对应域模块
    plans.py
    learning.py
    practice.py
    capture.py
    reports.py
    tasks.py
    _compat.py                    # 如确有必要，必须是薄转发/兼容辅助
    _legacy.py                    # 最终应删除或仅保留很薄的暂存兼容内容
  migrations/
    runner.py                     # registry/transaction/version runner，目标 <= 32 KiB
    migrations_v1_v4.py 或按域/版本分组的模块
    migrations_v5_v8.py
    migrations_v9_v13.py
    __init__.py
```

注意：不要照搬此结构而不审计实际依赖。若某个模块仍会超过 32 KiB，应继续拆分。不得创建一个新的集中式巨型兼容层。

## 4. A2.X-1：审计与冻结，不先改代码

先完成以下审计并将结果写入 `docs/prompts/architecture/` 的 A2.X evidence 或对应 A2.X 文档：

1. 读取完整的：
   - `AGENTS.md`
   - `docs/ROADMAP_CAPABILITIES.md`
   - `docs/STATUS.md`
   - `docs/TODO.md`
   - `docs/CODE_TEST_GOVERNANCE.md`
   - `docs/ARCHITECTURE.md`
   - `docs/MIGRATIONS.md`
   - `docs/BACKUP_RESTORE.md`
   - A0/A1/A2 architecture prompts and route map。
2. 对 `_legacy.py` 建立 AST inventory：函数名、行号、依赖的本地 helper、引用的 repository symbol、所属域、被哪些模块 import/call/monkeypatch。
3. 对 `runner.py` 建立 migration inventory：版本、函数、DDL 对象、执行顺序、测试覆盖和跨 migration helper 依赖。
4. 对 `main.py` 建立剩余 inventory：公开符号、HTML literal、导入兼容转发、ASGI app 和任何仍被外部 import 的对象。
5. 运行并保存当前基线：

```powershell
C:\miniconda\py310\python.exe -m pytest backend/tests/ -q
python backend/scripts/check-source-size.py --main-html-sha256 1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c
python -m compileall -q backend/app
```

6. 冻结拆分批次、回退点和兼容方案。此阶段不修改 schema、测试断言或产品行为。

## 5. A2.X-2：拆分 `_legacy.py`

### 5.1 迁移原则

- 一次只迁移一个 repository/domain group。
- 建议顺序：connection/common → materials → ai → study/cards/exercises → plans/learning → practice → capture → reports → tasks。
- 每批只移动函数定义及必要的 import/helper；不重写 SQL，不顺手修 bug，不格式化无关代码。
- 先处理无争议、低耦合的函数；高耦合跨域 helper 放到明确的 shared primitive 或保留一个很薄的兼容出口。
- 不允许域模块互相 import `_legacy.py` 形成新的循环依赖。
- 每个域模块必须有清晰的 `__all__` 或显式导出；`repositories/__init__.py` 不得成为第二个巨型文件。

### 5.2 兼容与 monkeypatch

- 在移动函数前，建立“旧路径 → 新路径 → 兼容出口 → monkeypatch 目标”的表。
- `repository.py` 继续提供全部稳定公开导出。
- 若既有测试 patch `backend.app.repository.some_helper`，必须确认实际执行路径仍读取可 patch 的绑定；不能只改变 re-export 而导致 patch 静默失效。
- 对跨域私有 helper，优先采用一个小型、明确拥有者的 shared module；不能把所有 helper 再集中回 `_legacy.py`。
- 函数 identity 只有在现有契约确实要求时才保持；若必须改变，先证明所有直接 import、patch 和调用方仍兼容，并记录原因。
- 完成一个域后立即运行对应 focused tests、repository inventory 和 import smoke。

### 5.3 `_legacy.py` 完成标准

- `_legacy.py` 删除已迁移的函数体；不得只是把原文件复制到多个新文件后仍保留重复实现。
- 最终 `_legacy.py` 要么删除，要么只保留经过审计的极薄兼容 glue；如保留，必须低于 32 KiB，且不能继续成为业务实现汇聚点。
- `repository.py` 仍为薄 façade，所有 305 个既有公开符号继续可用。

## 6. A2.X-3：拆分 `migrations/runner.py`

### 6.1 目标

将 DDL/migration body 与 migration execution engine 分离：

- `runner.py` 只保留 `MigrationError`/`MigrationResult`（如当前公开）、公共时间/对象/列检查 helper、migration registry 组装、transactional `migrate()`、schema inspection/assertion 以及错误边界。
- 每组 migration body 放入普通尺寸模块；按版本组或领域分组均可，但每个文件 <= 32 KiB。
- registry 必须保持当前版本号、名称、顺序和 callable 行为完全不变。

### 6.2 迁移要求

- 先用 AST/运行时 inventory 固定 `_MIGRATIONS` 的完整快照。
- 不要把 DDL 字符串做无意义重排；机械搬迁时保持字符串内容和执行顺序。
- 若 migration body 依赖 runner 的私有 helper，改为显式参数传入或从小型公共模块导入；不得依赖隐式全局污染。
- `MigrationError`、`MigrationResult`、`schema_version`、`migrate`、`inspect_schema_version`、`assert_schema_version` 的 import behavior 继续兼容。
- 为新分组模块增加 migration registration tests，确认 new DB、upgrade、repeat migrate、failure rollback、history/user_version 和 backup/restore 都与基线一致。

## 7. A2.X-4：继续收缩 `main.py`

### 7.1 目标

`main.py` 必须成为真正的薄兼容入口，目标不超过 32 KiB；不再依赖“历史超大 inline UI 例外”。

### 7.2 Inline HTML 处理边界

这是 A2.X 相对于原 A2 的明确新增范围：必须缩小 `main.py`，因此允许将当前 `INDEX_HTML` **机械拆出**为多个受 32 KiB 约束的 UI fragment 文件，或一个经过审计的 bounded asset package。

严格要求：

- 这是机械搬迁，不是 A3 UI 重构。
- `INDEX_HTML` 的最终字符串必须与当前基线逐字节一致；验证 SHA-256 仍为：
  `1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c`。
- 不得改变 HTML/CSS/JS、DOM、文本、空白、脚本执行顺序、accessible name、错误显示、键盘、窄屏或隐私行为。
- 不得在 A2.X 引入 static root、mount、页面拆分、React/Vue/Vite、模板引擎、浏览器 API 重构或新的前端能力。
- 不得生成一个新的大合并文件；每个 fragment/source file 必须 <= 32 KiB。
- 可使用一个极小的 assembler，在 import 时按固定顺序读取/拼接受控 fragments；不得从网络、data root 或用户可写目录读取 UI。
- 若采用 `.html` fragment，必须确保其是正式受控源码，文件大小也受同一门禁约束，且不会绕过规则。
- A2.X 完成后 A3 仍需独立执行正式 static root 和多页原生前端迁移。

### 7.3 兼容入口

- `main.py` 保留 `create_app`、`app` 和已承诺的公开兼容符号。
- 将 factory/lifespan/router/schema/helper 实现继续留在 A2 已建立的模块中，不把实现重新导回 `main.py`。
- 对测试中直接 patch `app.main` 符号的情况，建立显式同步机制并测试；不要依靠不可更新的闭包引用。

## 8. 测试与验收门禁

### 8.1 每批次门禁

```powershell
python -m compileall -q backend/app
C:\miniconda\py310\python.exe -m pytest <focused-tests> -q
python backend/scripts/check-source-size.py --main-html-sha256 1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c
 git diff --check
```

不要在命令中携带 secret，不要将测试数据库或 originals 写入仓库。

### 8.2 必须完成的最终检查

1. **源码尺寸**
   - `_legacy.py`、`runner.py`、`main.py` 和所有新增/实质重写文件均 <= 32 KiB。
   - 不存在新的大型 compatibility/legacy/static/UI/migration 汇聚文件。
2. **Import/入口**

```powershell
PYTHONPATH=backend python -c "import app.main; print(len(app.main.app.routes))"
cd backend; python -m app --help
```

3. **Route inventory**
   - 对比 A2 基线的 path、methods、endpoint name、status code、response class、顺序。
   - 业务路由仍为 151，总路由仍为 155。
4. **HTML identity**
   - `INDEX_HTML` 与 A2 基线逐字节一致，SHA-256 不变。
5. **Repository inventory**
   - 比较 A1 的 305 个公开 repository symbols；无缺失、无重复实现、无循环导入。
6. **Migration inventory**
   - `_MIGRATIONS` 版本/名称/顺序完全一致；schema version 仍为 v13。
7. **Focused tests**
   - `test_migrations.py`、repository transaction/source lifecycle/backup/restore、API compatibility、startup/preflight、相关 Phase 8–10 tests。
8. **完整 backend**

```powershell
C:\miniconda\py310\python.exe -m pytest backend/tests/ -q
```

   目标是至少保持当前基线：`413 passed, 2 skipped`；如测试数量变化，必须解释原因。
9. **完整 browser**
   - A2 已有的 18 个 browser specs 逐个串行运行。
   - 目标是至少保持当前基线：`52 passed, 1 skipped`。
10. **启动 smoke**
   - liveness、health、readiness、`/`、CLI help、`uvicorn app.main:app` import/启动路径。

## 9. 文档与提交要求

- A2.X 每个独立 domain/batch 单独提交，提交信息明确说明移动的职责和兼容策略。
- 最终更新唯一事实源：
  - `docs/STATUS.md`
  - `docs/TODO.md`
  - 必要时 `docs/ARCHITECTURE.md`、`docs/MIGRATIONS.md`、A0 route/repository map
  - 新增 A2.X evidence 文档必须放在 `docs/prompts/architecture/`。
- 文档必须明确：
  - `_legacy.py`、`runner.py`、`main.py` 的最终尺寸；
  - 新模块清单；
  - repository public inventory、migration registry、route inventory 的对比结果；
  - backend/browser 命令和结果；
  - 仍未验证的边界；
  - A3 尚未开始，A2.X 不等同于正式 static frontend migration。
- 不得把 `implemented` 写成 `real-pass`；不得声称支持多进程、多用户、云同步、真实断电恢复或生产级容量。
- 只有所有门禁通过后，才允许提交并推送 `master`。失败时保留可诊断状态，不删除数据库/原件，不手工回滚 migration history。

## 10. 禁止事项清单

- 禁止新增 API、schema、migration、业务功能或前端框架。
- 禁止修改既有 SQL、DDL、错误、response、状态机、生命周期顺序或 UI 字节内容。
- 禁止复制 Composer/Integration/参考项目实现进入正式系统。
- 禁止把 `_legacy.py`、`runner.py`、`main.py` 搬到另一个超大文件。
- 禁止用压缩、base64、动态下载、生成 artifact 或运行时用户目录隐藏源码体积。
- 禁止删除失败数据库、备份、测试证据或用户数据来“修复”测试。
- 禁止在完整回归未通过时声称 A2.X 完成、提交或推送。

## 11. 最终报告格式

完成时请报告：

1. A2.X 实际拆分结构和每个核心文件大小。
2. `_legacy.py`、`runner.py`、`main.py` 的最终状态。
3. 兼容入口、public symbol、route、migration registry 和 HTML hash 对比结果。
4. 每个 focused/full/browser 命令及真实结果。
5. 跳过项和未验证边界。
6. commit hashes、推送分支和 `git status`。

如果审计发现某一拆分会破坏 monkeypatch、函数 identity、migration rollback 或 HTML identity，应停止该批次，记录风险和回退点，不得用行为变更绕过问题。
