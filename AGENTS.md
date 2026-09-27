# StudyBuddy Agent Instructions
<!-- STUDYBUDDY-UNIFIED-EXECUTION-PROTOCOL -->
## 统一执行协议（2026-09-27）

本文件与 `H:\studybuddy\docs\[所有角色看]AI_AGENT_TASK_DIALOGUE_TEMPLATES.md` v2.1 使用同一套执行口径。本文档中早于 2026-09-27 的报告、表格和历史标签保留其原始事实；历史标签只能在原日期、原范围和原证据路径下解释，不能升级为当前全局结论。

### 可执行 Prompt 的必填字段
- **角色**：本次执行者的职责。
- **唯一目标**：一个可判定的结果，不把多个目标合并成“全部处理”。
- **当前阶段**：只能填写 `P0`（边界确认）、`P1`（真实状态读取）、`P2`（真实操作执行）、`P3`（证据核对）、`P4`（交付与结论）之一，并按顺序推进。
- **允许读取/写入**：逐项列出绝对路径、URL、端点、数据根和输入；未列出的对象禁止访问或修改。
- **指定工具/命令/端口/输入**：必须原样执行；对象不可用时返回 `BLOCKED`，不得替换。
- **禁止操作、停止条件和证据路径**：逐项写明；每个结论必须有实际命令/动作、结果和绝对证据路径。

### 统一状态与范围
`PASS`、`FAIL`、`BLOCKED`、`LIMITED`、`NOT_APPLICABLE`、`NOT_VERIFIED` 是本项目当前统一结果状态。`implemented`、`configured`、`available`、测试通过、隔离环境通过只能描述实现或可见性，不能单独写成 `real-pass`。`real-pass` 只能表示本次指定真实目标、真实路径、真实输入和真实动作均有证据；未覆盖范围必须写 `NOT_VERIFIED`。

### 统一路径和运行基线
源码 `H:\studybuddy`；正式数据 `H:\studybuddy-data`；验证证据 `H:\studybuddy-test\verification`；隔离数据 `H:\studybuddy-test\data_root`；真实教材 `H:\studybuddy-ChinaTextbook`（只读）；组件测试 `H:\studybuddy-composer`；组合测试 `H:\studybuddy-integration`；日志 `H:\studybuddy-log`；临时目录 `H:\studybuddy-tmp`；正式地址 `http://127.0.0.1:8787`；首页 `http://127.0.0.1:8787/app/today.html`。

正式启动命令为：`powershell -ExecutionPolicy Bypass -NoProfile -File H:\studybuddy\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-data -Port 8787`。隔离验证命令为：`powershell -ExecutionPolicy Bypass -NoProfile -File H:\studybuddy\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-test\data_root -Port 8787`。不得把 `python -m backend.app serve`、其他端口、其他数据根或其他浏览器替换到已指定任务中。

### 强制禁止
不得凭推测输出；不得用 HTML 解析、按钮清单、curl/API 请求、静态检查或 headless 结果冒充可视浏览器点击；不得读取、复制、提交或展示密钥、Token、Cookie、真实教材正文、Provider 原始响应、SQL 或完整 traceback；不得在未授权时调用真实 Provider/OCR/ASR、发送 Email/飞书或扩大文件范围。工具、路径、页面、服务状态或证据不满足前置条件时，立即停止并报告 `BLOCKED`。

<!-- /STUDYBUDDY-UNIFIED-EXECUTION-PROTOCOL -->


StudyBuddy is a local, single-process FastAPI + SQLite capability-integration system for user-owned study material; it does not train models.

## Delivery
- An active slice must change what a user can do in the browser or CLI; audit/contract/status-only work requires explicit request.
- `implemented` is not `real-pass`; keep unverified scope labeled `not_verified`. Capabilities must be discoverable; missing components surface as `not_installed` or `not_configured`.
- `report_delivery` is default-off and per-use authorized.

## Boundaries
- Source: `H:\studybuddy`; production: `backend/app/`; formal tests: `backend/tests/`; durable docs: `docs/`.
- Active data root: `H:\studybuddy-data`; never use retired `H:\studybuddy-data\live`. Tests/artifacts: `H:\studybuddy-test`.
- Test components in `H:\studybuddy-composer`, then `H:\studybuddy-integration`; reimplement against verified contracts—never copy their source into the formal system.
- Real material is in `H:\studybuddy-ChinaTextbook`; its token is a secret: never expose, copy, commit, or clean it.
- Never commit databases, originals, artifacts, secrets, provider keys, private paths, or test output; never expose paths, SQL, source text, tracebacks, raw provider errors, or secrets.
- Workspace retain/clean rules: [`docs/[架构师+运维看]WORKSPACE_DIRECTORIES.md`](docs/[架构师+运维看]WORKSPACE_DIRECTORIES.md).

## Engineering
- Schema changes use `backend/app/migrations/runner.py`; migrations are consecutive, idempotent, transactional, and rollback-tested.
- Follow `revision → chunks → retrieval → citations → Q&A → cards/exercises`; generated content starts as a cited draft and never overwrites confirmed edits.
- New/substantially rewritten `.py`, `.js`, `.css`, `.html`, `.ps1`, `.json` files are ≤100 KB unless explicitly approved.
- Test with `D:\miniconda\py310\python.exe -m pytest backend/tests/`; run focused tests first, full backend tests after infrastructure/migration/storage/API changes, and `python backend/scripts/check-source-size.py` before structural completion.
- For completed slices update [`STATUS.md`](docs/[需求+所有角色看]STATUS.md) and [`TODO.md`](docs/[需求看]TODO.md); do not add evidence/contracts unless the slice also ships user-exercisable capability.

## Support And Authority
- Support only local single-process, single-instance, local storage; do not claim shared `data_root`, multi-worker, cloud, multi-user, real power-loss recovery, or production-scale support without evidence.
- Start with [`README.md`](README.md), [`docs/INDEX.md`](docs/INDEX.md), [`ARCHITECTURE.md`](docs/[架构师看]ARCHITECTURE.md), [`CODE_TEST_GOVERNANCE.md`](docs/[架构师+测试看]CODE_TEST_GOVERNANCE.md), and [`MIGRATIONS.md`](docs/[架构师+运维看]MIGRATIONS.md).

## AI 任务执行门禁（与 `docs/[所有角色看]AI_AGENT_TASK_DIALOGUE_TEMPLATES.md` v2.1 一致）

所有由 AI 执行的 StudyBuddy 任务必须显式填写并在 P0 阶段确认：执行角色、本次唯一目标、当前阶段、必须先读取的真实对象、允许读取路径、允许写入路径或浏览器副作用、指定工具与原始命令、输入、输出、停止条件和证据路径。未填写的字段不是默认授权。

统一阶段为 `P0 任务边界确认 → P1 真实状态读取 → P2 真实操作执行 → P3 证据核对 → P4 交付与结论`。统一状态为 `PASS`、`FAIL`、`BLOCKED`、`LIMITED`、`NOT_APPLICABLE`、`NOT_VERIFIED`。`implemented`、`configured`、`available`、测试通过和隔离环境通过不得写成 `real-pass`；只有本次精确真实路径、输入和动作均有证据时，才可报告 scoped `real-pass`。

AI 必须原样使用任务指定的工具、命令、URL、端口、数据根和输入。工具或路径不可用、真实页面与参考文档不一致、需要未授权副作用或证据无法落盘时，立即返回 `BLOCKED`，列出实际错误并等待确认；不得用 curl、API 请求、HTML 解析、headless 运行、其他路径或推测结果替代指定的浏览器真实操作。浏览器任务的专项参考为 `H:\studybuddy\docs\[测试看]BROWSER_VERIFICATION_TASK_TEMPLATE.md`。

统一路径基线如下：源码根 `H:\studybuddy`；正式数据根 `H:\studybuddy-data`；验证证据 `H:\studybuddy-test\verification`；隔离测试数据 `H:\studybuddy-test\data_root`；真实教材 `H:\studybuddy-ChinaTextbook`（只读，Token 不得暴露）；组件测试 `H:\studybuddy-composer`；组件组合测试 `H:\studybuddy-integration`；日志 `H:\studybuddy-log`；临时目录 `H:\studybuddy-tmp`；正式地址 `http://127.0.0.1:8787`；首页 `http://127.0.0.1:8787/app/today.html`；健康端点 `/api/liveness`、`/api/health`、`/api/readiness`。

用户运行和验证任务的启动脚本分别使用已授权的数据根：正式运行命令为 `powershell -ExecutionPolicy Bypass -NoProfile -File H:\studybuddy\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-data -Port 8787`；隔离验证命令为 `powershell -ExecutionPolicy Bypass -NoProfile -File H:\studybuddy\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-test\data_root -Port 8787`。未在任务中明确授权时，不得启动服务、调用真实 Provider/OCR/ASR、发送 Email/飞书、修改配置、删除数据或扩大文件范围。

文档修改任务只能修改 Prompt 列出的文档；交付前必须执行 `git diff --check`，检查 diff 只包含授权文件，并报告实际修改路径。验证日志、截图和报告写入 `H:\studybuddy-test\verification`，不得写入源码根、正式数据根或真实教材目录。
