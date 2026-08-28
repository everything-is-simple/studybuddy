# A0：基线审计与拆分契约冻结

> 审计状态：`frozen-for-refactor`（仅文档；本 A0 未修改 `main.py`、`repository.py`、schema 或前端运行时）
>
> 审计对象：`H:\studybuddy`，提交 `5f6698d docs: add capabilities and desktop roadmap`
>
> 审计日期：2026-08-27（以当前工作区实际测试输出为准）

## 1. 范围与不可变原则

A0 只固定现状、边界、证据和回退办法。A1 之前不得拆分 `main.py`/`repository.py`，不得新增 migration，不得把 Composer/Integration 组件接入正式系统，不得将内嵌页面改造成静态目录。

本次拆分的兼容目标是：

- HTTP 路径、method、成功状态码、错误状态码和错误码不变；
- response JSON 的数组/对象形状、字段名、隐私边界和下载 media type 不变；
- `backend.app.main:create_app`、`backend.app.main:app`（如被外部使用）及 `backend.app.repository` 的既有导入仍可用；
- SQLite schema、migration history、事务边界、原文件 hash/layout、启动和恢复顺序不变；
- 浏览器入口仍为 `/`，当前内嵌 HTML/CSS/JavaScript 行为不变；
- 失败时不泄露路径、SQL、traceback、provider 原始错误、secret 或正文。

任何不满足以上条件的变化都必须单独立项，而不是作为拆分副作用进入 A1/A2。

## 2. 当前运行基线

### 后端

命令：

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/
```

结果：**413 passed, 2 skipped**，共收集 415 项；跳过项为 opt-in real provider smoke。该结果是本次 A0 的后端基线，不是对未来重构后的自动承诺；每个拆分阶段都必须复跑同一命令。

`main.py` 当前 AST 路由数量：**151**（包含 `/` HTML 入口）。完整 method/path/status 机器清单已由本次审计扫描得到；按域摘要及冻结边界见 `A0_ROUTE_REPOSITORY_MAP.md`。

### 浏览器专项

权威 runner：`backend/scripts/test-browser.ps1`；它将 Playwright 固定为 `--workers=1 --reporter=line`，每个 spec 自己启动 Uvicorn，并使用隔离 data root。专项 spec 共 18 个：

`browser_file_import.spec.js`、`browser_folder_import.spec.js`、`browser_frontend_failure_contract.spec.js`、`browser_material_export.spec.js`、`browser_material_management.spec.js`、`browser_material_pagination.spec.js`、`browser_material_recycle_bin.spec.js`、`browser_material_search.spec.js`、`browser_multi_file_import.spec.js`、`browser_p6d.spec.js`、`browser_p6e.spec.js`、`browser_phase7.spec.js`、`browser_phase8.spec.js`、`browser_phase9a.spec.js`、`browser_phase9b.spec.js`、`browser_phase9c.spec.js`、`browser_phase9d.spec.js`、`browser_qa.spec.js`。

首次 runner 执行时因缺少 Playwright Chromium executable 被环境阻塞。用户随后已执行 `npx playwright install chromium`，A0 发现的 Phase 8 exercise browser failure 已由后续最小产品修复处理：`studyTransition()` 现在等待容器刷新完成后再渲染 ready artifact，避免测试或用户在被随后替换的瞬时 radio input 上作答。

当前实际结果：

- 聚焦 Phase 8 browser：**3 passed**；
- 聚焦 Phase 8 backend：**18 passed**；
- 完整 backend：**413 passed, 2 skipped**；
- 完整 18 个 browser specs / 53 tests：**52 passed, 1 skipped**。

浏览器基线现状态为 **`browser-pass-with-one-opt-in-skip`**。剩余 skip 为既有 opt-in targeted Provider browser path，不属于 A0 架构拆分或 Phase 8 修复范围。本次修复未修改 schema、migration、`repository.py`、API 路径、HTTP 状态码、JSON/error code、backup/restore 或正式 static root。

### 入口与运行边界

- 发布 API 工厂：`backend/app/main.py:create_app`。
- Uvicorn 导入入口：`app.main:app`（`backend` 为 cwd，见 browser specs）。
- 显式 CLI：`backend/app/__main__.py` → `backend/app/cli.py:main`；`serve` 固定 `workers=1,reload=False`。
- PowerShell runtime：`backend/scripts/start-studybuddy.ps1`、`health-studybuddy.ps1`、`stop-studybuddy.ps1`。
- 服务绑定 loopback；支持范围为 local single-process/single-instance/SQLite/local-disk。
- Backup/restore/verify/rotate/upgrade-preflight/diagnostics 是 CLI 操作，不是当前 FastAPI 路由；启动不自动 backup、restore、repair 或 run task。

## 3. 当前职责结论

`main.py` 同时承载 app factory、lifespan/preflight/recovery/readiness、middleware、所有 HTTP 路由、上传/下载编排、错误映射和完整内嵌页面。`repository.py` 同时承载 connection/migration 初始化、事务、material/source、revision/chunk/retrieval/citation/Q&A、embedding、cards/exercises、plans/notes/rhythm、practice/capture/transcript/report/delivery/operation-task 的持久化。

这不是“空壳路由层”：路由中仍有 provider 选择、文件校验、导出 ZIP、上传编排和错误翻译；repository 中仍有跨域 source lifecycle、citation refresh、operation/idempotency 和事务协作。因此 A1/A2 必须先保留兼容 façade，不能按文件行号机械剪切。

## 4. 冻结后的拆分顺序

```text
A0 基线审计（本文件集）
→ A1 repository.py 按域拆分，旧 repository.py 兼容转发
→ A2 main.py 路由与应用工厂拆分，旧 main.py 兼容导出
→ A3 原生前端 F0/F1（保持页面/API 契约）
→ A4 Provider 设置与采集页 F2/F3
→ B1 ASR → B2 OCR → B3 报告 → B4 外发
→ D0/D1 Tauri 桌面化
```

组件 smoke 可并行，但只能在 `H:\studybuddy-composer`；组合测试只能在 `H:\studybuddy-integration`；未验证组件不得进入本目录正式实现。

## 5. A1/A2 每阶段验收门

1. 变更前记录 git commit、pytest 结果、browser 可执行环境和 route inventory hash。
2. 只迁移一个职责域；不改 schema、不改业务规则、不改前端文案/DOM 行为。
3. 先新增目标模块，再以旧 façade 导出；确认所有内部和外部 import 后才删除重复实现。
4. 运行 focused tests，再运行完整 backend；Chromium 可用时运行完整 browser runner。
5. 对比 OpenAPI route inventory、状态码、JSON 快照/错误码、启动/health/readiness、材料导入/导出、备份恢复和 CLI。
6. 任一门失败即回退本域迁移，不继续下一个域。

详细路径、函数和调用点见 `A0_ROUTE_REPOSITORY_MAP.md`；静态入口见 `A0_STATIC_FRONTEND_CONTRACT.md`；回退步骤见 `A0_REFACTOR_ROLLBACK_PLAN.md`。

## A1 重新采集与结构收口结果

A1 实施前重新采集的实际 HEAD 为 `cc7f11f6cb569c1d572e11b23da5f20d0a162c59`，与 Prompt 中的短 SHA 一致；工作区原有用户文档 `docs/prompts/architecture/A1_REPOSITORY_SPLIT_PROMPT.md` 未被撤销。完整后端回归为 **413 passed, 2 skipped**，两个 skip 为 opt-in real-provider smoke；`browser_phase8.spec.js` 为 **3 passed**。公开 repository inventory 为 305 个符号，façade 对比无缺失。

A1 新增 `backend/app/repositories/` 结构：connection、materials、ai、plans、learning、practice、capture、reports、tasks 九个显式域出口；`backend/app/repository.py` 继续作为兼容 façade。为保留现有跨域私有 helper 的 monkeypatch、函数 identity、事务边界和行为等价，当前函数实现暂由 `repositories/_legacy.py` 单一载体承载，域模块提供显式可审计导出；这是限定范围的结构收口，不是内部函数体完全解耦。未修改 `main.py`、前端、schema/migration、storage、provider 或生产调用点。

## A2 重做结果与源码大小门禁

A2 在本地备份旧的未推送大文件尝试后，从 A1 推送基线重做。`backend/app/main.py` 保留为兼容 façade，并保留唯一、非增长的既有 `INDEX_HTML` 字符串；其 HTML payload SHA-256 为 `1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c`，与 A1 基线完全一致。A2 不创建 `web_ui.py`、static root 或任何新的大 UI/legacy 搬运文件，A3 才负责静态前端迁移。

后端应用现在由 `app_factory.py`、`lifespan.py`、`http_errors.py`、`http_helpers.py`、小型 schemas/services 模块和 `api/registration.py` 协作；后者按原顺序调用 14 个小型真实 route 模块。`main.py:create_app`、`main.py:app`、151 条业务路由、启动顺序、错误/detail、JSON/media type 与直接 monkeypatch 兼容路径均保留。新增或实质重写源码实行 32 KiB 上限，`backend/scripts/check-source-size.py` 对新增文件、既有超限文件增长和 `main.py` HTML hash 执行门禁。

A2 重做验证：完整 backend **413 passed, 2 skipped**；完整 18 个 browser specs **52 passed, 1 skipped**；业务路由数 **151**（FastAPI 总路由 155）；所有新增/实质重写模块均低于 20 KiB。
