# StudyBuddy 能力补齐、架构拆分与桌面化路线图

> 状态：`A3-FC closed / A3-PAGES first slice closed / A3-VISUAL closed / Practice workflow phase two scoped closeout / B1 ASR C0-C6 scoped closeout / B2 OCR C0-C6 scoped closeout`。本路线图在现有 local v1（Phase 10 Gate J）之后执行；它不修改既有完成结论，也不将真实 OCR、通用真实 ASR、真实外发或桌面安装包视为已实现。当前 B0 已完成候选治理脚手架，ASR 官方候选已使用 GitHub release 的公开 `SampleClips/jfk.wav` 完成并通过 C1-ASR-01 至 C1-ASR-14；本机 Whisper.dll PE 版本与 GitHub Const-me/Whisper 1.12.0 release 对齐，其余候选仍在 researching；ASR C2 Integration、Formal contract、显式 opt-in API/browser/backup-restore evidence 已通过，且完整 Chromium 基线已恢复为 `130 passed, 4 skipped`。B2 OCR C0-C6 已在冻结的 PaddleOCR 本地 synthetic scope 内完成 scoped closeout；B3-B4/D0-D1 门禁仍待执行。
>
> 批准日期：2026-08-29。第一步目标为：在保持本地数据与现有行为契约的前提下，拆分后端和前端边界，按 Composer -> Integration -> Formal 流水线补齐已批准能力，并以时间盒验证 Tauri 桌面封装。第二步仅为前端框架迁移草案。

## 1. 决策与不变量

### 1.1 已批准决策

- 先完成架构重构和原生前端拆分；正式系统重构期间可以并行进行组件库的独立 smoke，但未通过全部规定门禁的组件不得进入正式系统。
- 前端第一步保持 FastAPI + 正式静态资源 + 原生 HTML/CSS/JavaScript，不建立独立前端仓库、不引入 React/Vue/Vite。
- `main.py` 拆为应用工厂、生命周期和按业务域划分的 routers；`repository.py` 拆为按业务域划分的 repository/domain 模块。稳定的导入入口仅可保留薄兼容层，不得继续成为实现汇聚点。
- 已批准的能力顺序：真实 ASR -> 真实 OCR -> 报告组件 -> 真实外发。每项均遵守 Composer -> Integration -> Formal 门禁。
- Tauri 桌面化为第一步末尾的时间盒工作，不提前承诺 macOS/Windows 安装包或跨平台支持。
- 第二步仅在触发条件成立后评估 React/Vue 前端迁移；后端 HTTP API、数据生命周期和安全契约必须保持独立于前端框架。

### 1.2 不可破坏边界

- 正式实现唯一来源为 `H:\studybuddy`；组件实验位于 `H:\studybuddy-composer`，组合验证位于 `H:\studybuddy-integration`。不得复制参考项目实现进入正式系统。
- 每次 schema 改动仍只能走 `backend/app/migrations/runner.py`；架构拆分本身不得借机修改 schema、迁移历史、`PRAGMA user_version` 或业务数据语义。
- 继续支持 local-disk、单实例、单服务进程的 v1 运行边界，直至桌面包装阶段显式重新评估。不得承诺多用户、云同步、多实例共享 `data_root`、真实断电恢复或生产规模容量。
- API、日志、页面、桌面壳、诊断和 artifact 不得泄露 key、绝对路径、SQL、traceback、原始 Provider/tool response、原件或未经批准的正文。
- 对任何 AI 产物、OCR/ASR 转写、报告或外发：用户确认、来源生命周期、幂等、审计、失败重试和 backup/restore non-repair 契约优先于 UI 或工具接入速度。

## 2. 总门禁：组件不得跳级进入正式系统

每个候选组件必须按以下状态推进；任何失败、未验证、来源不清或安全边界不足都停留在当前层，不能进入下一层。

```text
C0 catalogued
-> C1 composer_smoke_passed
-> C2 integration_passed
-> C3 formal_contract_frozen
-> C4 formal_implemented
-> C5 formal_gates_passed
-> C6 scoped_closeout
```

| 阶段 | 地点 | 必须产物 | 进入下一阶段的门槛 |
|---|---|---|---|
| C0 | Composer | component card、来源/许可证/版本/哈希记录、已忽略的二进制原件、候选能力与 non-goals | 不执行不明二进制；确认可重复的安装/启动方式 |
| C1 | Composer | fixture、独立 smoke、成功/失败/超时/取消或明确不支持的证据 | 全部规定 smoke 断言通过；不访问真实用户数据；证据不含敏感输入 |
| C2 | Integration | 与 storage、SQLite、operation/task、source lifecycle 的组合契约 | 组合成功、失败、rollback、并发/超时边界及隔离 data root 测试全部通过 |
| C3 | Formal | 正式领域/API/数据/隐私/任务契约和风险审计 | 评审确认不扩大支持边界；如需 schema，先有连续 migration 和 rollback 计划 |
| C4 | Formal | 独立重实现、focused tests、必要 migration | 不复制 Composer 或参考实现；所有输入/输出和错误均为安全契约 |
| C5 | Formal | backend、browser、source lifecycle、backup/restore、operator/runtime tests | 所有为该能力规定的测试通过，再运行完整 backend suite；真实 smoke 与 fixture/loopback 分级记录 |
| C6 | Formal | 脱敏 acceptance evidence、STATUS/TODO/ROADMAP 同步 | 明确 `implemented`、`smoke_passed`、`real-pass` 和 `not_verified` 的范围；不把一次真实 smoke 外推为通用可用性 |

“全部测试通过”指当前能力在 C1、C2、C5 写明的全部必跑测试均通过，且 C5 包含当时完整 backend regression；不以跳过、删除失败用例、人工口头确认或未验证归档替代门禁。

## 3. 第一步路线图：架构、原生前端、能力流水线与桌面验证

第一步预计按可验收闭环顺序推进，不承诺固定日历工期。每个编号应单独提交、单独测试、单独更新 TODO 状态；未通过不得开始依赖项。

### A0：基线审计与拆分契约冻结

**目的：** 先定义“只搬家、不改行为”的边界，防止以重构名义混入业务修改。

**任务：**

1. 为现有 API 路径、response schema、稳定错误码、生命周期、静态页面行为和关键 import 建立机器可检验的基线清单。
2. 为 `main.py` 和 `repository.py` 建立职责地图、依赖图、循环导入风险清单和目标模块归属表。
3. 确认正式静态资源目录、FastAPI mount、缓存策略及现有浏览器测试服务入口；完成 `frontend-plan.md` 的 F0 端点到页面映射。
4. 固定兼容策略：旧 `backend.app.main:create_app` 在迁移期可作为薄导出入口，不能继续承载路由、HTML、CSS 或业务实现。
5. 记录每个拆分批次的回退方式：仅代码回退，不执行数据库回滚、不删除 data root、不重写用户数据。

**禁止：** 新 API、新 schema、新功能、新前端框架、格式化全仓库或借重构改变错误语义。

**通过门槛：** focused contract tests 与当前完整 backend/browser 基线均通过；拆分目标、兼容入口、静态目录和每批次回退步骤已写入审计记录。

### A1：拆分 repository.py 为按域模块

**目的：** 停止将所有 SQL、事务和领域规则继续写入单一 6299 行文件。

**目标结构（名称可在 A0 审计后微调）：**

```text
backend/app/repositories/
  connection.py       # connect、transaction、时间/共用安全 helpers
  materials.py        # material/extraction/span/search/lifecycle/export metadata
  ai.py               # revision/chunk/retrieval/context/citation/Q&A/embedding
  study.py            # decks/cards/exercises/review/attempt
  plans.py            # goals/modules/plans/progress
  learning.py         # notes/knowledge modules/rhythm
  practice.py         # practice/error-fixer/exam-crammer
  capture.py          # capture/transcript/source ingestion
  reports.py          # report projection/export/delivery audit persistence
  tasks.py            # operation/task persistence and task state
  __init__.py         # 明确的公共导出；不得成为第二个巨型文件
```

**任务：**

1. 先抽取无业务语义的 connection/transaction helpers，并为嵌套事务、rollback、SQLite lock 和 project scope 建回归测试。
2. 一次只迁移一个域，顺序为 materials -> ai -> study -> plans/learning -> practice -> capture/reports -> tasks。
3. 每次迁移保留原函数签名或在同一提交内更新全部调用方；不得同时改 SQL 语义、表结构或 response 字段。
4. 域间调用只能经过明确 repository/domain service API；禁止跨模块直接访问另一模块的私有 SQL helper。
5. 迁移完成后将原 `repository.py` 收缩为受测试的兼容导出层，或在所有调用点切换后删除；目标是它不再包含业务 SQL。

**通过门槛：** 每域 focused tests、transaction/rollback/source lifecycle/backup-restore regressions 和完整 backend suite 通过；行数检查证明原文件不再含业务 SQL，且不存在循环导入。

### A2：拆分 main.py 为应用工厂、生命周期与 routers

**目的：** 把路由、输入验证、响应映射与前端资源从 3183 行单文件中剥离，避免新能力继续混杂。

**目标结构：**

```text
backend/app/
  app_factory.py      # create_app、middleware、exception mapping、router registration
  lifespan.py         # preflight/connect/migrate/audit/recovery/ready/shutdown
  api/
    materials.py
    ai.py
    study.py
    plans.py
    learning.py
    practice.py
    capture.py
    reports.py
    delivery.py
    tasks.py
    system.py         # health/readiness/capabilities/diagnostics
  main.py             # 仅兼容导出 create_app，或在完成迁移后删除并更新正式入口
```

**任务：**

1. 将 Pydantic request/response models 放到所属 API 域或共享 schema 模块；禁止把内部 repository row 或 exception 直接暴露给 HTTP。
2. 一次只迁移一个 router，保持 URL、HTTP method、状态码、错误码、幂等和 response JSON 兼容。
3. 生命周期、instance lock、observability、ready state 和 exception mapping 集中在 app factory/lifespan，不允许 router 自行启动 subprocess、建表或写运行时目录。
4. 把内嵌 HTML/CSS/JS 从路由代码中完全移出；A3 后不得使用 `HTMLResponse` 承载产品 UI。
5. 更新服务入口、脚本和 browser test 启动方式；保持受支持的单实例、loopback、`workers=1`、`reload=false` 边界。

**通过门槛：** API compatibility suite、完整 backend suite、现有 Chromium suite、启动/health/readiness、backup/restore 和 Gate J 回归均通过；`main.py` 只剩薄兼容层或已删除。

### A2.X：A2 完成后、A3 前的核心大文件收缩

**目的：** A2 已完成后，不能把 `_legacy.py`、`runner.py` 和 `main.py` 的剩余体积问题推迟到前端建设之后。三个核心文件，尤其两个超过 100 KiB 的文件，分别立项、分别审计、分别迁移、分别验收；每个文件对应一个明确任务号，避免以“整体重构”掩盖不可控工作量。

**当前源码大文件盘点（2026-08-29）：**

| 任务 | 文件 | 当前大小 | 目标 | 责任边界 |
|---|---|---:|---:|---|
| A2.1 | `backend/app/repositories/_legacy.py` | ~~379,741 B~~ → 29,750 B bridge | ✅ completed | 18部分实现+runtime+bridge；保持305符号、monkeypatch兼容；413 passed |
| A2.2 | `backend/app/main.py` | ~~156,889 B~~ → 969 B | ✅ completed | INDEX_HTML 提取到 templates/index.html；保持兼容导出；413 passed |
| A2.3 | `backend/app/migrations/runner.py` | ~~68,846 B~~ → 7,412 B | ✅ completed | 拆分为 13 个版本模块 + helpers；413 passed |
| A2.4 | `backend/app/providers.py` | ~~33,593 B~~ → 目录 (9 模块) | ✅ completed | 拆分为职责模块；413 passed |

测试文件、历史/契约文档和已知既有超限文档另行治理，不把测试或文档搬入生产模块来规避源码门禁；本组任务优先处理 `backend/app/` 生产源码。不得再产生新的 `web_ui.py`、`all_migrations.py`、`all_repositories.py` 或其它超大替代文件。

#### A2.1：收缩 `repositories/_legacy.py`

- 先建立 AST 函数、依赖、调用方、域归属和 monkeypatch inventory。
- 按 connection/common → materials → ai → study → plans/learning → practice → capture → reports → tasks 迁移到已有或新建 bounded domain modules。
- 每次只搬一个域；不改 SQL、签名、事务、返回值、错误和数据语义；`repository.py` 继续作为完整兼容 façade。
- 最终 `_legacy.py` 删除，或仅保留 <=32 KiB 的明确兼容 glue；不得复制实现。
- 通过：public symbol inventory 305/305、无循环导入、repository/transaction/source lifecycle/backup-restore focused tests 与完整 backend regression。

#### A2.2：收缩 `main.py`

- 先固定 151 条业务路由、155 条总路由、公开符号、`create_app`/`app`、CLI/ASGI import 和 `INDEX_HTML` hash。
- 应用工厂、lifespan、HTTP 映射、schemas、services 和 API routers 已在 A2 拆出；本任务只清理剩余兼容入口与 inline UI 载荷。
- 允许将现有 `INDEX_HTML` 机械分片为多个 <=32 KiB 的受控源码片段，并在 import 时按固定顺序组装；HTML/CSS/JS 必须逐字节不变。不得引入 static root、页面拆分或新前端框架；这些仍属于 A3。
- 通过：`main.py` <=32 KiB、HTML hash 不变、route inventory/monkeypatch/startup/health/readiness/browser regression 全部通过。

#### A2.3：收缩 `migrations/runner.py`

- 先固定 `_MIGRATIONS` 的版本、名称、顺序、函数行为和 v13 schema baseline。
- 将 migration body 按版本组或领域拆入多个 <=32 KiB 模块；runner 只负责注册组装、`BEGIN IMMEDIATE`/rollback、history、`PRAGMA user_version`、inspect/assert 和安全错误。
- 严禁新增/删除/重编号 migration，严禁改变 DDL、字段、索引、约束、默认值或业务数据语义，严禁 runtime ad-hoc table creation。
- 通过：new DB、v1–v13 upgrade、重复 migrate、失败 rollback、history/user_version、backup/restore 和完整 backend regression 全部通过。

#### A2.4：收缩 `providers.py`

- 先固定 Provider/Embedding registry、adapter class、错误码、超时、SSE/JSON、Bearer/secret 脱敏和默认 fake-provider 行为 inventory。
- 按协议/adapter/registry 拆分为 bounded modules；不改变网络默认值、真实 Provider opt-in、原始响应过滤或错误边界。
- 通过：provider focused tests、API/QA/retrieval/generation browser regression、完整 backend regression 和源码尺寸门禁。

**A2.X 总门禁：** A2.1 → A2.2 → A2.3 → A2.4 依次执行；每个子任务单独提交、单独回退、单独更新 TODO 和 evidence。任一失败立即停止当前子任务，不修改 migration history、不删除数据库/原件、不进入 A3。所有新增/实质重写生产源码 <=32 KiB，目标 20–30 KiB；完整 backend/browser 基线不得下降。A2.X 不等于 A3，不实现正式 static root 或多页前端。

### A3：执行 frontend-plan F0/F1，建立原生多页应用壳

**目的：** 将 `main.py` 中的测试 workspace 转为可维护、可测试的正式静态资源，而不改变技术栈。

**任务：**

1. 按 A0 结论创建唯一正式 static root，并由 app factory 显式挂载；不创建未挂载的孤立 `frontend/` 目录。
2. 建立 `css/tokens.css`、`css/app.css`、`js/api.js`、`js/shell.js`；统一请求取消、错误码映射、toast/dialog、导航、焦点和安全 DOM 写入。
3. 将 `index.html` 限制为总览入口；迁移 `materials.html`、`material-detail.html`、`qa.html` 为独立任务页，采用 URL 中的非敏感资源标识保留上下文。
4. 每页仅使用已存在、受测试的 API；发现缺口先回到后端契约任务，不在浏览器猜字段、写环境变量或直接调用外部 Provider。
5. 保持并扩展现有 desktop、390px 窄屏、键盘、失败、重复点击、stale response、citation unavailable 与隐私 DOM 测试。

**禁止：** 引入 React/Vue/Vite、浏览器存储 key/原文、浏览器执行本机工具、伪造 Provider/ASR 状态、将所有工作区再次塞回首页。

**通过门槛：** `frontend-plan.md` F0/F1 对应页面、挂载和 API 映射已完成；相关 Chromium tests 全通过；不再由内嵌 HTML 提供产品 UI。

### A4：Provider 设置、课堂采集与任务状态页面

**目的：** 在真实 ASR 尚未接入前，先让页面如实表达能力状态，避免 UI 先行宣称可用。

**任务：**

1. 实施 `settings-provider.html`：仅显示后端 capability、安全配置状态、保存/验证的分离操作和安全错误；密钥输入后清空，永不回读或持久化到浏览器。
2. 实施 `capture.html`：上传、operation/task 状态、draft 编辑、confirm/reject/archive 和 source lifecycle 显示；未通过 ASR 门禁时必须禁用真实转写动作并说明原因。
3. 实施 `tasks.html`：显示 embedding_index enqueue/read/retry/cancel；其它操作显示“尚未接入任务运行器”。
4. 为每个页面补齐 loading/empty/error/success、键盘、窄屏、reload、privacy DOM 和失败重试测试。
5. 真实 ASR adapter 只有在 B1-B3 通过后才能从“候选”变为可选能力；前端由 capabilities 驱动，不硬编码工具路径或模型名。

**通过门槛：** 已批准 UI 范围可在 fake/loopback 或真实已验证能力下演示；未验证能力不会显示为已连接或可执行。

**备注：** 本阶段对应 frontend-plan.md 中的 A4，是静态前端 A3 的直接继续。

### A3-FC：前端契约与架构收口（已完成，声明范围内）

**目的：** 在继续扩展页面或引入真实能力之前，消除静态前端的字段漂移、状态漂移、错误映射不一致和视觉 token 分裂问题。该任务不引入新业务能力、不修改 schema、不引入 React/Vue/Vite。

**工作包：**

1. 维护 `docs/frontend-contract-audit-report.md`，逐页记录页面路由、API、method、Content-Type、请求字段、响应字段、状态机、错误码、重试、窄屏、键盘和隐私断言。
2. 对照后端路由自动检查页面调用的 endpoint 是否存在；对关键 response 字段和状态值建立 contract fixtures，禁止继续使用旧字段名。
3. 收口 `js/api.js`：字符串 JSON body 自动补 `Content-Type`、统一解析安全错误、保存 request ID、扩展稳定错误码映射，并为可取消请求预留 AbortSignal 入口。
4. 收口 `css/app.css`：补齐所有页面使用的 token，消除未定义 CSS 变量；统一 badge、notice、button、focus、grid 和移动端导航样式。
5. 收口 `js/shell.js`：只保留产品任务导航，补充报告/任务/设置入口，统一当前页面标记；移动端采用可访问的更多导航，不压缩成不可用的横向长导航。
6. A3-FC-3 分两轮执行：首轮完成全部现有静态页面的 API/字段/状态/错误/安全审计和基础 browser regression；第二轮已完成每页状态到 `sbState` 的迁移，以及 stale/failure/source-lifecycle、360–1920 响应式、键盘和隐私 DOM 矩阵。失败/retry 证据索引见 `docs/frontend-static-failure-retry-matrix.md`。
7. A3-FC-3-2 通过后执行的首批页面拆分已完成：`plan-detail.html`、`note-detail.html`、`practice-session.html`、`practice-result.html`、`review.html`、`reports.html`、`settings.html`。页面保持现有 `plans.html`、`notes.html`、`practice.html`、`classroom.html`、`settings-provider.html`、`tasks.html` 可回退，不改变 API 语义。
8. 页面拆分和行为门禁已通过；A3-VISUAL 亦已完成：Neutral Modern card/button/badge/notice/dialog/focus/grid 已收敛到共享 CSS，全部 21 个 `/app/*.html` 无局部 `<style>`，visual matrix 覆盖 shared tokens、card、360/1920、触控目标和 focus ring。当前完整基线为 backend `426 passed, 2 skipped`、browser `130 passed, 3 skipped`；视觉任务未改变 API 或业务行为。

**通过门槛：** A3-FC 已在声明范围内通过：前端契约审计表完整；无未定义 token；页面 endpoint/字段/状态检查通过；核心浏览器套件、360–1920、键盘、错误恢复、source lifecycle 和隐私 DOM 通过；源码尺寸检查通过；TODO/STATUS/frontend-plan/evidence 已同步。该关闭不代表 `legacy_only`/`not_exposed`/`a3_pages` 能力已迁移；A3-PAGES/A3-VISUAL 仍按后续任务执行。

### 后续前端能力切片（A3-VISUAL 之后，按顺序）

1. **Practice workflow**：第二阶段已完成 scoped closeout，第三阶段已完成现状审计与正式契约冻结；推荐 API/数据契约已独立冻结并完成实现。契约 `contracts/frontend-practice-workflow-contract.md` 已更新；已迁移公开题目、start/submit/finish、嵌套结果、expired/source warning、practice/review 导航，以及 review 详情、feedback、review、mark-mistake、redo、archive 操作。`browser_practice_workflow.spec.js` 当前为 `7 passed`；完整 backend `426 passed, 2 skipped`，完整 browser `130 passed, 3 skipped`；推荐 API/browser evidence 和服务生命周期均已串行收口。第三阶段正式契约见 `docs/contracts/PHASE_PRACTICE_WORKFLOW_PHASE3_AUDIT_AND_CONTRACT.md`，推荐 API/数据契约见 `docs/contracts/PHASE_PRACTICE_RECOMMENDATION_API_CONTRACT.md`。仍不扩大为真实 Provider 或全局 production `real-pass`。不得机械复制 `/legacy`，也不改变 API 语义。
2. **Practice workflow 第三阶段需求审计/契约冻结**：已完成 practice/exercise/attempt/review 数据与 API 审计，并冻结自适应出题、间隔重复、人工简答复核的边界、状态机、隐私、幂等和 source lifecycle；推荐 API 已按独立契约实现，后续 schedule/算法扩展仍需单独立项。
3. **B3 reports/export/audit**：在 B3 gate 后扩展 `reports.html` 的脱敏导出和审计工作区；维持 report projection、`delivery=off`、allowlisted dry-run 和 append-only audit。dry-run 永不显示为已发送，live delivery 仍属于 B4。
4. **Provider 配置写入**：不属于 A3-VISUAL，也不因设置页已存在而获批。仅在后端形成安全写入/验证契约后单独立项；浏览器不得保存、回显或持久化密钥，且必须具备脱敏 connection-test failure 和独立 browser evidence。
5. **`legacy_only` / `not_exposed`**：以 `docs/frontend-static-capability-matrix.md` 为来源逐项立项。`legacy_only` 需独立页面/路径和 browser evidence；`not_exposed` 在存在安全公共契约前保持不暴露，不得用 mock 伪造成功。

### B0：组件库统一准备与证据治理

**目的：** 为 ASR、OCR、报告、外发建立一致的入库和测试标准。

**任务：**

1. 在 `H:\studybuddy-composer` 为每个候选创建 component card、固定版本清单、许可证/来源记录、风险/隐私说明、独立 fixture 和 smoke command。
2. 二进制安装包、模型、大型参考 archive 仅作为本地受忽略输入；Git 只提交 manifest、校验值、脚本、最小 fixture 和脱敏证据。
3. 在 `components.json` 只登记已完成规定 smoke 的组件；候选在 `initial-catalog.json` 或等价目录中标为 `researching`，不得伪造 pass。
4. 为每个组件定义网络默认关闭、受控临时目录、超时、子进程清理、输出上限、错误脱敏和 test artifact 位置。

**当前实现：** B0 governance scaffold 已建立于 `H:\studybuddy-composer\B0-COMPONENT-GOVERNANCE.md`，机器可读 catalog 为 `manifests/b0-catalog.json`；ASR 官方 `H:\Whisper\cli` 使用 `H:\Whisper\Models\ggml-large-v3-turbo.bin` 与 GitHub release 的公开 `SampleClips/jfk.wav` 通过 `C1-ASR-01` 至 `C1-ASR-14`；本机 `Whisper.dll` PE product version 为 `1.12.0.0`，对应 GitHub `Const-me/Whisper` release `1.12.0`、commit `c5515ace19066e938854b4b99e0c2e9bbc2eeb65`。SAPI 合成 WAV 不作为该 runtime 的正向识别 oracle；官方 release asset 尚未完成哈希复核（下载受网络限制）；ASR C2 Integration 已通过；Formal 已独立重实现并通过限定范围 contract evidence。OCR、报告和外发独立 C1 smoke 尚未通过。C0 选型已冻结于 `H:\studybuddy-composer\DECISIONS\STUDYBUDDY_MEDIA_CAPABILITIES.md`：官方 `H:\Whisper\cli\main.exe` + `H:\Whisper\Models\ggml-large-v3-turbo.bin` 是唯一 ASR runtime；PaddleOCR 是中文/版面主 OCR，RapidOCR ONNX 是轻量回退，Tesseract 仅兼容后备；PPTX 采用 formal-pptx 原生文字 → MarkItDown/python-pptx 辅助 → 图片页 PaddleOCR 三层路径；edge-tts 是免费在线、显式用户操作的 TTS 候选，未进入当前 9D 业务范围。ASR C1 evidence 见 `H:\studybuddy-composer\results\asr-whisper-cpp\c1-smoke.json`；已知本机 CLI/运行时/PPTX 预检不提升 C2/Formal 状态。

**通过门槛：** 四类能力均有可审计候选记录；没有不明二进制被提交或被正式系统调用。

### B1：真实 ASR 组件流水线

**候选与选择：** C0 已选择官方 `H:\Whisper\cli\main.exe` + `H:\Whisper\Models\ggml-large-v3-turbo.bin` 作为唯一 canonical runtime；Composer 中的组件记录只作证据/审计，禁止形成第二个运行路径。FunASR、SenseVoice 保持未选备选，除非主候选在 C1/C2 失败。选择仍以离线运行、Windows 可重复安装、可控 CLI 协议、无隐式网络外发、明确文本/段落/时间戳输出为准。

**Composer smoke：**

1. 审计可执行入口、参数、音频格式、模型安装、退出码、stdout/stderr、网络行为、资源和许可证。
2. 对合成或明确授权的非敏感音频执行成功、不可读输入、格式不支持、超时、取消/终止、空输出、超大输出和重复调用测试。
3. 验证临时文件和子进程清理、输出大小限制、错误脱敏、无路径/音频内容泄露和 deterministic fixture 结果。

**Integration：** 将通过的候选与 local storage、operation/task、capture draft、source lifecycle 和 backup/restore 组合验证；只使用隔离 data root。

**Formal：** 冻结 `CaptureTranscriptionProvider` 契约后独立实现 adapter；任务接入必须单独评审，不能因已有 `embedding_index` runner 而自动获批。必须实现 draft-first、用户确认、幂等、超时、取消、retry、安全审计和浏览器全链路。

**通过门槛：** C0-C6 全部通过；真实 smoke 仅证明精确工具/模型/环境/音频范围，不外推为通用 ASR real-pass。

**当前 scoped closeout：** C0-C6 已在当前 Windows 主机、`whisper-cpp` / `ggml-large-v3-turbo` 与公开 `jfk.wav` fixture 的精确范围内通过。C5 包含 provider contract、真实 API draft-first → confirm → citation → backup/restore smoke、opt-in 静态 `capture.html` 上传 → 转写 → 草稿 → 用户确认 Chromium evidence，以及完整 Chromium `130 passed, 4 skipped` 回归；页面 capability 不暴露 runtime 或模型路径，ASR 不接入 task runner。脱敏证据见 `docs/evidence/FORMAL_ASR_ACCEPTANCE_EVIDENCE.md`。官方 asset hash、其他格式/语言/环境、取消与子进程树清理、并发/容量和通用 real-pass 仍为 `not_verified`。

### B2：真实 OCR 组件流水线

**候选与选择：** C0 已选择 PaddleOCR 为中文、表格、版面和图片/扫描 PPT 页的主 OCR；RapidOCR + ONNX Runtime 为资源受限的轻量回退；Tesseract 只作低依赖兼容后备；CapsWriter 的 OCR fit 不再作为主线。PaddleOCR 已完成 Composer C1、Integration C2、Formal C3 contract freeze、C4 implementation、C5 acceptance 与 C6 scoped closeout；RapidOCR 仍是独立 smoke candidate，未自动纳入 Formal。

**Composer smoke：**

1. 审计执行入口、模型下载与网络行为、支持图片格式、语言包、输出结构、置信度和错误码。
2. 对合成打印体中文/英文图片、空白图、损坏图、过大尺寸、格式不支持、超时和重复调用执行测试。
3. 验证不把原图、完整 OCR 文本、tool stderr 或绝对路径写进普通日志/证据；输出限制、临时文件和子进程清理必须通过。

**Integration：** 验证 image original、OCR draft、uncertain/confidence、operation/task、用户确认、material/revision/chunk/citation 接入、delete/restore/purge 和 backup/restore non-repair。

**Formal：** 已依据冻结的 `ImageOcrProvider` 契约独立实现；结果先作为 draft，未经确认不得覆盖材料或成为正常引用来源。C5 使用显式 opt-in 的本地模型和非敏感 synthetic PNG 完成 acceptance，C6 已完成限定范围 closeout。

**通过门槛：** B2 C0-C6 已在精确 PaddleOCR/模型/Windows/Python 3.10/CPU/local synthetic scope 内完成；一次真实图片 smoke 仅记录精确组件和模型范围，不外推为通用 OCR real-pass。脱敏证据见 `docs/evidence/B2_OCR_C6_SCOPED_CLOSEOUT_EVIDENCE.md`。

### TTS：独立重新立项（不属于 B1–B4 的已批准路径）

**候选：** `edge-tts` 是免费、无需购买 API Key 的在线 TTS 客户端；它不是离线引擎，也不等同于 B4 外发。只有出现明确的学习产品用户路径后，才冻结 `TextToSpeechProvider`、用户显式触发、网络 opt-in、音频临时保存/清理、失败/限流、无正文/路径/密钥日志、浏览器播放和删除契约。当前不得自动调用、不得持久化为 citation/source，且不能把 Pi/Python 本机准备度写为 Formal 能力。

### B3：报告组件流水线

**C0-C3 状态：** C0 `audit-frozen`、C1 Composer `smoke_passed`、C2 Integration `integration_passed`、C3 Formal `contract-frozen`。现有 Phase 9D report domain 是唯一 Formal 语义基线，不建立第二套 report domain。`report-core` 仅在声明的 synthetic/local scope 内通过 Composer 与 Integration；C3 contract 见 `docs/contracts/B3_REPORT_COMPONENT_CONTRACT.md`，evidence 见 `docs/evidence/B3_REPORT_C3_CONTRACT_EVIDENCE.md`。JSON/Markdown 进入 Formal C4/C5；PDF 因缺少 renderer/layout/font/resource/accessibility/privacy evidence 而排除。HTML/email、Feishu card、AI narrative、delivery state、网络和 task scheduling 同样排除。C0 evidence 见 `docs/evidence/B3_REPORT_C0_AUDIT_AND_SCOPE.md`。

**范围：** 先验证本地、确定性、脱敏的 report projection 和 JSON/Markdown export；不将“生成报告”与“真实外发”绑定。

**Composer smoke：** 验证输入白名单、日/周/月/考试提醒时间窗口、时区、脱敏、空数据、source unavailable、稳定排序、导出大小和损坏输出失败。

**Integration：** 与 9A-9D 学习数据、project scope、source lifecycle、append-only report audit、backup/restore 和隔离 data root 组合验证。

**C3 Formal contract freeze：** 已冻结复用现有 Phase 9D report domain 的正式边界、safe payload、snapshot/idempotency、source lifecycle、backup/restore non-repair、JSON/Markdown-only export、API/UI 与 privacy/error 风险；正式契约见 `docs/contracts/B3_REPORT_COMPONENT_CONTRACT.md`。尚未实现新的 Formal production behavior。

**C4 Formal：** 已独立验证并实现必要 Formal 缺口：JSON/Markdown report export 统一执行 1 MiB 上限，超限返回稳定 `payload_too_large`；现有 report domain、snapshot、API、UI、source lifecycle 与 backup/restore 语义保持不变。证据见 `docs/evidence/B3_REPORT_C4_IMPLEMENTATION_EVIDENCE.md`。

**C5 Formal：** 已完成只读 report service/export API 和产品页面 `reports.html` 的 backend/browser/source-lifecycle/backup-restore/operator acceptance。页面仅读取已有 snapshot，支持 JSON/Markdown 导出，明确呈现未发送状态；证据见 `docs/evidence/B3_REPORT_C5_ACCEPTANCE_EVIDENCE.md`。

**C6 Formal：** 已完成 scoped closeout：复核 B3 C0-C5 evidence、Composer/Integration/Formal 隔离、B3 governance、C4/C5 focused、Phase 9D report/source-lifecycle/backup-restore、Chromium、完整 backend、frontend contract audit、source-size 和 diff check。脱敏 closeout evidence 见 `docs/evidence/B3_REPORT_C6_SCOPED_CLOSEOUT_EVIDENCE.md`。

**通过门槛：** C0-C6 全部通过。B3 完成仅限 local deterministic project-scoped JSON/Markdown report scope；报告完成不自动批准 delivery，也不表示报告内容适用于医学、教育评估或其它高风险决策。

### B4：真实外发组件流水线

**顺序约束：** 只有 B3 scoped closeout 后才开始。默认 `delivery=off` 和既有 live 拒绝语义在整个阶段保持有效，直到精确 adapter 获得单独批准。

**候选：** QQ SMTP、飞书 Webhook；每个渠道独立组件、独立证据、独立开关，不共享“已验证”结论。

**Composer smoke：** 使用 loopback/fake SMTP 或本地 HTTP receiver 验证 payload、recipient/URL allowlist、secret 隔离、timeout、rate limit、失败、retry、Idempotency-Key 和禁止网络默认值。不得使用真实收件人、真实群聊或生产 webhook 作为默认测试目标。

**Integration：** 验证 report export、delivery audit、dry-run、operator authorization、重复请求、失败 retry、source lifecycle、backup/restore 和恢复后不自动发送。

**Formal：** 先保持 dry-run；真实 live adapter 必须具有运行时 enable、显式授权、逐次确认、channel allowlist、幂等、审计和立即安全失败的错误边界。真实发送 smoke 必须用户显式授权、使用非敏感测试目标并形成脱敏证据。

**C3 状态：** 已完成 `contract-frozen`：`docs/contracts/B4_DELIVERY_COMPONENT_CONTRACT.md` 与 `docs/evidence/B4_DELIVERY_C3_CONTRACT_EVIDENCE.md` 冻结了 SMTP/Feishu 分渠道、默认关闭、显式授权、allowlist、幂等、审计、失败和 restore non-send 边界。一次 163→QQ synthetic 邮件实际收件及一次 Feishu synthetic live smoke 仅作为精确配置/网络可行性证据，不开放 Formal live delivery。

**C4 状态：** 已完成 `implemented/backend-pass`：Formal 独立实现 SMTP/Feishu adapters、运行时分渠道 target mapping 和 allowlist、内容大小限制、稳定 provider error mapping、idempotency/explicit retry 边界与 default-off/no-network/live no-adapter 测试。证据：`docs/evidence/B4_DELIVERY_C4_IMPLEMENTATION_EVIDENCE.md`。C4 没有打开 Formal live execution gate。

**C5 状态：** 已完成 `scoped acceptance passed`：default-off/live-blocked browser、source lifecycle、backup/restore no-send 和两条独立 operator-authorized fixed-synthetic channel smoke 均通过。SMTP scope 仅为一条 163 SMTP 到 QQ mailbox 路径；Feishu scope 仅为一个 configured custom-bot webhook。证据：`docs/evidence/B4_DELIVERY_C5_ACCEPTANCE_EVIDENCE.md`。

**C6 状态：** 已完成 `scoped closeout passed`：复核 Composer/Integration/Formal 隔离、独立实现、runtime-secret redaction、source lifecycle、restore no-send、browser/backend/full regression、source-size、diff 和脱敏 evidence。证据：`docs/evidence/B4_DELIVERY_C6_SCOPED_CLOSEOUT_EVIDENCE.md`。B4 完成仅限精确 fixed-synthetic channel scope；Formal product API live 继续拒绝，任何产品化 live delivery 必须重新冻结并验收独立 contract。

**通过门槛：** C0-C6 已在声明 scope 内通过。精确渠道的 real smoke 不表示所有 SMTP/webhook 配置均可用。

### B5：明确延后项与重新立项条件

| 项目 | 第一步结论 | 重新立项条件 |
|---|---|---|
| 外部 vector database / pgvector | 延后 | SQLite 向量检索的容量或功能证据显示明确瓶颈，并先冻结新的部署/backup/restore 契约 |
| BullMQ 或其它外部队列 | 延后 | 当前单进程 task runner 的明确需求缺口，且已决定改变单机/单实例部署边界 |
| DOC/RTF/PPT 旧格式转换 | 继续拒绝 | 有明确用户需求、可信转换器、隔离与安全合同；不得复用启发式 DOC 解码 |
| 多用户、云同步、协作 | 延后 | 单独产品和部署路线，不与本路线图混入 |

### D0：Tauri 桌面化准备审计

**目的：** 在写桌面壳之前验证其是否与当前运行边界、安全模型和发布方式兼容。

**任务：**

1. 冻结桌面威胁模型：本地 UI shell、FastAPI sidecar、loopback port、data root、日志、崩溃、升级、卸载、secret 和文件选择器边界。
2. 决定并记录 sidecar 生命周期、端口冲突、单实例、健康检查、退出清理、异常重启和用户可见错误语义。
3. 明确 Tauri UI process + FastAPI sidecar 是新的桌面组合运行模型；不得沿用“单 OS 进程”文字宣称。若继续支持单实例 local service，必须以单一 app/data-root ownership 来验证。
4. 先只针对 Windows 做开发环境 spike；macOS 仅在相应系统构建、签名和真实验收条件具备后单独立项。

**通过门槛：** threat model、打包输入清单、sidecar 生命周期、数据目录迁移/备份策略和 release test plan 完成；没有将开发期 `tauri dev` 当作安装包证据。

### D1：Tauri Windows 最小安装包时间盒

**任务：**

1. 创建最小 Tauri shell，加载正式静态前端，受控启动并监控 FastAPI sidecar。
2. 验证首次启动、单实例、导入、Q&A fake path、受控退出/重启、日志脱敏、data root 位置、backup/restore、升级前检查和失败恢复。
3. 仅在以上稳定后评估系统托盘、开机启动、文件关联；它们各自为可选子任务，不得阻塞基础安装包，也不得绕过导入安全边界。
4. 构建安装/卸载/升级测试，用临时 data root；不删除或覆盖既有 live data root。

**通过门槛：** Windows 安装包在隔离环境完成规定路径和完整 backend/browser/desktop smoke；记录包大小、依赖、签名状态和未验证限制。未达标则保留 Web/loopback 发布方式，不宣称桌面版本完成。

### D2：macOS 可行性门（非第一步承诺）

只在拥有 macOS 构建环境、签名/notarization 方案、系统 webview/sidecar 测试和数据目录/权限验收后启动。不得以 Windows 成功推断 macOS 可用。

## 4. 第一步总验收与文档收口

第一步完成不等于所有未来能力都完成。仅当下列独立 gate 均已有证据，才可声明“第一步 scoped closeout”：

1. A0-A4 的架构/前端门禁通过，`main.py` 和 `repository.py` 不再承载巨型混合实现。
2. B1-B4 中每个被正式批准和实现的组件均已完成 C0-C6；未通过或未启动者必须明确列为 `not_started`/`not_verified`，不得掩盖。
3. D0-D1 Windows desktop 时间盒达标；若 D1 未达标，第一步可在能力与架构范围内关闭，但桌面化保持未完成，不能称为“桌面应用已交付”。
4. 每次组件/正式接入都有 focused tests、完整 backend regression、相关 Chromium/desktop tests、source lifecycle、backup/restore 与安全检查。
5. `README.md`、`STATUS.md`、`TODO.md`、`PHASE_ROADMAP.md`、`frontend-plan.md`、组件 manifests/cards 和 acceptance evidence 与真实状态同步。

## 5. 第二步路线图草案：现代前端框架迁移（6-12 个月后评估）

> 状态：`draft / not approved for implementation`。只有原生静态前端的维护成本、复杂交互需求或 Web 多用户产品决策触发时才启动；不因“技术更新”单独发起迁移。

### 触发门

满足至少一项才可开始评估：

- 页面/共享状态/重复逻辑已超过原生模块化方案可维护阈值，并有具体缺陷或开发成本证据；
- 产品已批准拖拽计划、复杂富文本、跨页面实时状态或同等复杂交互；
- 已批准多用户 Web 产品方向，并另行冻结认证、授权、project isolation、部署与数据边界。

### 草案任务

1. **E0 评估与 ADR：** 比较 React 与 Vue、路由、状态管理、测试、可访问性、Tauri 集成、许可证、构建可复现性和团队维护成本；不预先选型。
2. **E1 API 契约冻结：** 为当前 API 建立版本化 contract tests；框架迁移不得借机改变来源生命周期、错误码、幂等、隐私或鉴权边界。
3. **E2 最小垂直切片：** 在单独前端工作区试做总览 + materials + Q&A；保留原生前端作为可回退发布版本。
4. **E3 组件与测试体系：** 建立设计 token、页面组件、请求层、错误状态、Playwright、可访问性和 visual regression；不接受无测试的大规模一次性重写。
5. **E4 渐进迁移：** 按页面替换，不做“全部推倒重来”；每页在功能、窄屏、键盘、隐私 DOM 和失败路径验证通过后才切换默认入口。
6. **E5 桌面与 Web 分流：** 明确 Tauri 包内资源和可能的 Web 发布产物；多用户 Web 需要独立后端/部署路线，不能复用 local-v1 声明。
7. **E6 收口：** 性能、包体、离线、升级、回退、桌面 sidecar、browser/full regression 和文档证据全部通过后，才移除原生前端。

## 6. 任务执行纪律

- 一次只实现一个编号任务；一个任务同时涉及重构、schema、新组件和 UI 时，必须拆分，先完成契约和重构门禁。
- 组件候选下载、模型下载或真实 smoke 不得与正式系统代码变更放在同一提交中。
- 失败组件要保留可审计的失败结论、版本和安全原因；不删除失败测试来得到“通过”。
- 所有真实网络/真实音频/真实图片/真实外发均需 explicit opt-in；默认 fixture、loopback、dry-run 和脱敏 evidence。
- 完整 backend 命令保持：`C:\miniconda\py310\python.exe -m pytest backend/tests/`。浏览器和桌面门禁使用项目正式脚本；新增命令必须写入组件卡和相关 evidence。
- 每个完成声明都要说明精确工具、模型、运行环境、输入类别、时间、通过范围和 `not_verified` 限制。
