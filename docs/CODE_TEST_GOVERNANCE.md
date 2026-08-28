# StudyBuddy 代码、测试与治理契约

> 本文是仓库级工程治理规范。它规定代码放置、测试分层、状态命名、证据和变更门禁；能力事实仍记录在 `STATUS.md`，执行任务仍只记录在 `TODO.md`，长期顺序仍记录在 `PHASE_ROADMAP.md`。

## 1. 系统边界

StudyBuddy 当前支持的部署模型是单进程、单实例、SQLite、本地磁盘和本地浏览器。多个 worker、多个服务实例或多个进程不得共享同一个 `data_root`。云同步、多用户、认证授权、外部存储、生产级容量和真实断电恢复都必须有独立设计与证据，不能从现有测试结果推断支持。

正式代码只能位于 `backend/app/`；正式 Python 测试只能位于 `backend/tests/`；长期文档只能位于 `docs/`。Composer、Integration 和外部项目只能提供已核验的契约或测试依据，不能直接成为正式实现源码。

## 2. 代码治理

### 2.1 分层与所有权

- API、生命周期、HTTP 安全错误和启动顺序归 `backend/app/main.py` 及其边界模块负责；Web 入口为 `create_app`，ASGI 默认对象为 `app`。
- operator CLI 的唯一模块入口为 `backend/app/__main__.py`，委托 `backend/app/cli.py:main`；备份、校验、恢复和 schema 查询均保持显式调用。
- SQLite 连接、查询、事务、业务持久化和一致性归 `backend/app/repository.py` 负责。
- schema 变化只能通过 `backend/app/migrations/runner.py` 的连续 migration 完成。
- 原文件路径、hash 校验、临时文件和 containment 归 `backend/app/storage.py` 负责。
- backup、verify、restore 和 restore acceptance 必须保持 operator 显式调用，不得在启动时自动 repair、backup 或 restore。
- Provider、embedding、retrieval 和 citation 必须保留稳定错误码、来源绑定和可审计 metadata；AI 生成内容默认是 draft，不得静默覆盖用户确认内容。

### 2.2 不变量

每次涉及持久化、文件或 API 契约的变更，都必须说明并测试相关不变量：

- material、extraction、text span、search index 的事务一致性；
- active/deleted/purged 生命周期和 shared hash 原文件保留；
- 数据库 schema version 与 `schema_migrations` 历史一致；
- source revision、chunk、retrieval hit、citation 的可追溯关系；
- 错误响应、日志和 UI 不泄露路径、SQL、正文、secret、原始异常或 traceback；
- readiness 只在 preflight、数据库初始化、audit 和 recovery 完成后变为 ready。

### 2.3 变更要求

代码变更必须保持最小范围，并同步：实现、聚焦测试、必要的完整回归、权威状态和 TODO。新增业务表、字段约束或索引时，必须新增或修改 migration，并覆盖新库、升级、幂等、失败 rollback、backup/restore 版本保持测试。不得在业务运行路径中以 ad-hoc `CREATE TABLE IF NOT EXISTS` 代替 migration。新增或实质重写的源码文件必须不超过 32 KiB，目标是 20-30 KiB；超过上限必须先获得明确审批。不得通过新建/搬迁大 compatibility、legacy、static 或 inline-content 文件规避该限制。`backend/app/main.py` 当前内嵌 UI 是 A3 前唯一非增长的历史例外，结构重构必须验证它的 HTML payload 未改变。

## 3. 测试分层与命令

### 3.1 默认门禁

默认后端门禁不调用真实网络、不使用真实 Provider、不写入仓库内数据库或原文件。统一入口是：

```powershell
powershell -NoProfile -File .\backend\scripts\test-backend.ps1
```

等价的直接命令为：

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/ -q
```

Bash/Cygwin 等价路径为 `/cygdrive/c/miniconda/py310/python -m pytest backend/tests/ -q`。

浏览器门禁必须串行执行，并通过统一入口指定 spec：

```powershell
powershell -NoProfile -File .\backend\scripts\test-browser.ps1 browser_qa.spec.js
```

Phase 8 Cards/Exercises 改动的最小浏览器门禁为：

```powershell
powershell -NoProfile -File .\backend\scripts\test-browser.ps1 browser_phase8.spec.js
```

`test-browser.ps1` 每次只接受一个 spec；需要多个 browser spec 时必须分别串行执行。

历史 Phase 9B closeout 的脱敏回归基线为：focused Gate A-I `59 passed`，完整 backend `299 passed, 2 skipped`，相关非真实 Provider Chromium `45 passed, 1 skipped`，默认 real-provider spec `2 skipped`；权威证据见 `PHASE9B_ACCEPTANCE_EVIDENCE.md`。当前全仓默认 backend 基线由 `STATUS.md` 记录为 `412 passed, 2 skipped`；当前全 Chromium 为 `52 passed, 3 skipped`，三个 skip 均是显式 opt-in real-provider browser paths。测试数量变化必须以新运行输出为准，不得把历史文档数字当作当前事实。

真实 Provider 仍只能通过目标专用 gate 或 `run-provider-api-acceptance.ps1` 启用，不属于默认门禁。

### 3.2 测试层级

- `test_*.py`：单元、repository/API 集成、迁移、存储安全、恢复、并发控制和稳定错误契约。使用 `tmp_path` 或独立临时 data root。
- `browser_*.spec.js`：Playwright/Chromium 用户路径、响应式、键盘和前端失败契约。必须串行运行，服务和 data root 每个 spec 或场景隔离，测试后清理。
- `test_real_provider_smoke.py` 与 `browser_*real_provider*.spec.js`：真实 Provider opt-in 门禁，默认 skip；必须同时匹配显式开关、provider、model、base URL 和 key。证据只适用于精确组合，不表示全局可用性。
- `backend/scripts/`：可复现的 operator 或 acceptance runner。脚本不得接受 secret 作为命令行参数，不得打印子进程原始输出或 key。
- `backend/tests/write_*.py`、`crash_worker.py`：仅为测试辅助程序，不是产品入口，不能向源码树写数据库、原文件或未脱敏日志。

### 3.3 证据等级

状态词必须按以下含义使用：

| 状态 | 含义 | 最低证据 |
|---|---|---|
| `planned` | 只有设计或待办 | 文档/任务描述 |
| `implemented` | 代码已存在 | 聚焦 backend 测试 |
| `backend-pass` | 后端契约在当前环境通过 | 可复现 pytest 命令和结果 |
| `browser-pass` | 浏览器用户路径通过 | 可复现 Playwright 命令、浏览器和 viewport |
| `real-pass` | 精确真实环境用户路径通过 | 脱敏 artifact，含 provider/model/gateway、commit、命令和限制 |
| `not_verified` | 明确未验证 | 记录原因和不能推断的范围 |

`real-pass` 只能描述局部能力和精确配置组合，不能改写为全局生产就绪。网络 smoke、benchmark、ACL、磁盘耗尽、断电、屏幕阅读器等未执行项目必须保持 `not_verified`。

## 4. 文档事实源

- `README.md`：入口和简明当前定位，不复制完整状态表。
- `docs/STATUS.md`：能力状态、证据索引和已知运行限制；是实现状态的权威来源。
- `docs/` 根目录只保留核心入口、设计、治理、状态、路线、TODO 和正式 acceptance；规划、历史、运行手册和辅助 evidence 统一放在 `docs/prompts/`，其中辅助 evidence 放在 `docs/prompts/evidence/`。
- `docs/TODO.md`：唯一可勾选的执行清单；完成项必须关联代码、测试、文档和证据。
- `docs/PHASE_ROADMAP.md`：长期阶段、依赖和执行顺序，不作为测试结果记录。
- `docs/PROJECT_PROGRESS_REPORT.md`：面向项目汇报的当前事实摘要，不能产生与 STATUS 冲突的新状态。
- `docs/CODE_TEST_GOVERNANCE.md`：本治理契约，描述规则而不是功能完成度。
- `docs/INDEX.md`：所有重要文档的导航入口。

发生冲突时，先修正事实源，再修正引用它的摘要文档；禁止用新增第二张状态表解决冲突。

## 5. 提交前检查清单

统一执行顺序：先运行 `test-backend.ps1`，涉及 UI 时再运行 `test-browser.ps1` 的最小相关 spec；真实 Provider、容量基线和 restore drill 必须作为独立证据记录，不能混入默认门禁。

1. 确认变更属于 `backend/app/`、`backend/tests/` 或 `docs/` 的正确边界。
2. 运行变更相关的 focused backend tests。
3. 若涉及基础设施、migration、storage、recovery、backup 或 API，运行完整 backend suite。
4. 若涉及 UI，运行对应 Chromium spec；真实 Provider 只在显式 gate 下运行。
5. 检查 `git status --short`，确认没有数据库、原文件、secret、私有路径、Playwright report 或未脱敏 artifact。
6. 更新 `STATUS.md`、`TODO.md` 或 `PHASE_ROADMAP.md` 中真正受影响的唯一事实源，并保留 `not_verified` 限制。
7. 报告命令、结果、跳过项和未验证边界；`implemented` 不得写成 `real-pass`。

## 6. 例外管理

临时实验、provider key、运行数据库、上传 originals、benchmark 输出和 acceptance artifacts 必须放在仓库外的隔离目录，例如 `H:\studybuddy-test` 或系统临时目录。若确需提交脱敏证据，只提交稳定、可审计且不含私有路径、正文、secret 和原始响应的摘要，并在对应文档标明证据范围与限制。
