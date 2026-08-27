# A1：repository.py 按域拆分 —— 任务 Prompt

> 生成日期：A0 完成并推送之后（HEAD `cc7f11f`）。
> 本文件是给下一步编码代理的完整任务输入，自包含、decision-complete。

## 一、角色与必读

你是 StudyBuddy 正式系统（`H:\studybuddy`）的编码代理。开始前必须完整阅读以下文件，并以其为约束：

- `AGENTS.md` —— 仓库规则、AI 开发顺序、测试与安全边界
- `docs/prompts/architecture/A0_BASELINE_AUDIT.md` —— A0 基线审计与冻结结论
- `docs/prompts/architecture/A0_ROUTE_REPOSITORY_MAP.md` —— 路由与 repository 职责地图、外部调用点
- `docs/prompts/architecture/A0_STATIC_FRONTEND_CONTRACT.md` —— 前端现状（A1 不触碰）
- `docs/prompts/architecture/A0_REFACTOR_ROLLBACK_PLAN.md` —— 回退方案
- `docs/ARCHITECTURE.md` —— 架构边界
- `docs/CODE_TEST_GOVERNANCE.md`、`docs/MIGRATIONS.md` —— 测试与迁移治理

## 二、当前状态（已冻结）

- 仓库：`H:\studybuddy`；远端 `https://github.com/everything-is-simple/studybuddy.git`
- 当前 HEAD：`cc7f11f`（master 与 origin/master 已同步）
- A0 已完成：基线冻结，未修改业务代码、schema、前端
- 后端基线：`C:\miniconda\py310\python.exe -m pytest backend/tests/` → **413 passed, 2 skipped**
- 浏览器基线：**52 passed, 1 skipped**（18 个 spec / 53 tests）；剩余 skip 为 opt-in real provider 路径，与 A1 无关
- `backend/app/repository.py` 约 6,243 行；`backend/app/main.py` 约 3,184 行（151 条路由）

## 三、A1 目标

在**不改任何行为**的前提下，把 `backend/app/repository.py` 按业务域拆分为独立模块；旧 `repository.py` 保留为兼容转发层（façade），使所有现有导入、测试、CLI、task runner、delivery、recovery 继续工作。

## 四、兼容性硬约束（不可违反）

1. 不改 SQLite schema、migration 顺序/history、`PRAGMA user_version`；不新增表；不新增 runtime ad-hoc DDL。
2. 不改 API 路径、HTTP method、成功/错误状态码、response JSON 形状、error code、下载 media type。
3. 不改前端（`INDEX_HTML` 内嵌页面）与 `main.py` 路由逻辑；A1 只动 repository 层。
4. 保留 `backend.app.repository` 的全部公开符号与函数签名（含常量 `VALID_STATUSES`、`MAX_CONTEXT_TOKENS`、`RETRIEVAL_POLICY_VERSION`、`QA_PROMPT_VERSION` 等），通过转发/再导出。
5. 不改事务边界：`with connect(...) as connection:` 的调用方所有权不变；拆分不得改变 commit/rollback 时机。
6. 不改原文件 hash/layout、启动/恢复顺序、backup/restore。
7. 不泄露路径、SQL、traceback、provider 原始错误、secret、正文。
8. 拆分不能夹带任何前端重构、Provider 接入、组件复制、数据库变更或 bug 修复；若发现只有拆分层才能修的阻塞问题，先暂停并向用户报告。
9. 不得从 Composer/Integration 项目复制实现；A1 是纯机械拆分。

## 五、已知外部调用点（必须继续可用）

- `backend/app/main.py`：大量直接 import + 懒加载（`run_vector_retrieval`、`run_hybrid_retrieval`、`index_embeddings_for_material`）
- `backend/app/cli.py`：`connect`、`recover_active_operation_tasks`
- `backend/app/recovery.py`：`connect`、`recover_active_operation_tasks`
- `backend/app/task_handlers.py`：`connect`、`index_embeddings_for_material`
- `backend/app/task_runner.py`：task 状态机函数、`connect as connect_database`
- `backend/app/delivery.py`：`find_report_delivery_replay`、`record_report_delivery_attempt`
- 测试代码直接 import repository 函数：全部保留

## 六、目标结构（backend/app/repositories/）

```
backend/app/repositories/
├── connection.py   # connect, utc_now, search-index helpers, migration 初始化
├── materials.py    # materials/extractions/spans/search/page/restore/rename/purge/delete, get_material, get_spans
├── ai.py           # revision/chunk/retrieval/citation/Q&A/embedding/generation operation
├── plans.py        # goals/modules/plans/items/dependencies/progress/source links/rhythm
├── learning.py     # cards/exercises/notes（含生成 draft）
├── practice.py     # practice sessions/mistakes/weak points/cram
├── capture.py      # capture assets/transcription ops/segments/confirm/reject
├── reports.py      # report projection/snapshot/export/delivery audit
└── tasks.py        # operation task 状态机 + recover/reclaim
```

边界说明：

- 顶层已有 `backend/app/delivery.py`（外发编排）。repository 拆分里的 delivery audit（`record_report_delivery_attempt`、`find_report_delivery_replay`、`list_report_delivery_attempts` 等）归属 `reports.py`，**不要**放回顶层 delivery.py。
- `plans.py` / `learning.py` 的归属以 `A0_ROUTE_REPOSITORY_MAP.md` 的域映射为准；repository.py 内部已有 `# Phase 9A domain repository`、`# Phase 9C shared exercise-feedback` 等段落标记，可作为归属依据。
- 跨域辅助函数（被多个域引用、拆分会产生循环导入的）先放 `connection.py` 或 `_shared.py` 并记录决策；**不允许**引入运行时循环 import 或全局状态 hack。

## 七、拆分方法

1. **先 inventory**：生成当前 `backend.app.repository` 的完整公开符号清单（含被测试 import 的）作为基线，保存到临时文件，**不要提交**。
2. **建立模块**：先创建 `repositories/` 与目标文件，按函数从原文件复制；内部私有辅助函数与被调函数一并迁移，保持依赖完整。
3. **保持旧 façade**：`repository.py` 改为从目标模块转发 + 显式再导出全部公开符号；迁移期间**不删除**任何符号。
4. **逐个域提交**：每迁移一个域独立提交一次。提交信息形如 `refactor: split repository tasks domain into repositories/tasks.py`。
5. **每域验证**：先跑该域相关 focused 测试（示例：tasks → `test_task_runner.py`、`test_phase10_operations.py`；materials → `test_file_import_path.py`、`test_material_pagination.py` 等），再跑完整后端；浏览器环境可用时跑相关 spec。
6. **循环依赖处理**：互相引用的域拆到公共底层模块或由 façade 统一中转，记录决策。
7. **最后收口**：全部域迁移完成后，`repository.py` 只保留常量、跨域辅助函数与转发；确认 `python -c "import backend.app.repository"`、`python -m backend.app` 和 `uvicorn app.main:app`（backend cwd）均正常。
8. 迁移后对比 OpenAPI route inventory 与错误码：必须逐项一致。

## 八、验收门

命令（均在 `H:\studybuddy` 根目录）：

```powershell
C:\miniconda\py310\python.exe -m pytest backend/tests/
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 <spec>
git diff --check
git status --short --branch
```

- 最终后端：**413 passed, 2 skipped**（数量只允许因新增/删除测试而可解释地变化，并在提交说明中写明）
- 最终浏览器（环境可用时）：**52 passed, 1 skipped**
- `git diff --check` 无错误；`git status` 干净
- 不提交 `test-results/`、`playwright-report/`、SQLite、originals、`.incoming-*`、临时 inventory 文件、secret
- 每阶段浏览器若因缺 Chromium 无法运行，在提交说明中如实记录 `browser-not-run`，**不得**声称 browser-pass

## 九、风险提示

- 最危险的是跨域函数（citation refresh、source lifecycle、idempotency、QA operation）被机械搬错导致行为漂移；逐函数核对事务与 WHERE 条件、错误码。
- 不要因为"看起来重复"就合并实现；保持行为等价。
- 拆分后 `repository.py` 的任何 `from .repositories.xxx import *` 都要显式列出 `__all__` 或完整符号，避免符号丢失。

## 十、明确不在 A1 范围

- A2 `main.py` 路由与应用工厂拆分
- A3 静态前端、A4 Provider 设置/采集页
- B1 ASR、B2 OCR、B3 报告、B4 外发
- D0/D1 Tauri 桌面化
- 任何 schema/migration/API/前端变更，或把 Composer/Integration 组件接入正式系统

## 十一、完成判定

A1 完成 = 所有域已拆分 + 旧 façade 保留 + 完整后端通过 + 浏览器（如环境可用）通过 + 每域独立提交 + 回退方案（`A0_REFACTOR_ROLLBACK_PLAN.md`）仍适用。完成后更新 `A0_BASELINE_AUDIT.md` 的职责结论与路由/仓库映射，并汇报限制与尚未验证项。
