# StudyBuddy 系统工作目录与清扫规范（2026-09-19 修订二版）

> 本文是六个系统工作目录的**唯一权威说明**：各目录定位、必须保留的内容、可清理的内容。
> 变更目录用途时先改本文，再同步 `AGENTS.md`、`README.md`、`docs/INDEX.md`。

新机器按 [`docs/[维护者看]NEW_MACHINE_SETUP.md`](../[维护者看]NEW_MACHINE_SETUP.md) 的目录重建顺序执行；可直接交给 AI 的配置提示词在 [`docs/[维护者看]STUDYBUDDY_NEW_MACHINE_PROMPT.md`](../[维护者看]STUDYBUDDY_NEW_MACHINE_PROMPT.md)。

## 一、目录地图

| 目录 | 定位 | 关键约束 |
|------|------|----------|
| `H:\studybuddy` | 正式源码仓库（生产代码 `backend/app/`、正式测试 `backend/tests/`、文档 `docs/`） | 根目录只留入口文档与元数据；不存运行数据；远端 `github.com/everything-is-simple/studybuddy.git` |
| `H:\studybuddy-data` | 正式运行数据根（data_root）：SQLite、hash-derived 原文件、配置、日志 | **唯一活跃 data_root 是其根目录**；不进 Git、不进网盘；多实例禁止共用；**清扫默认不动** |
| `H:\studybuddy-composer` | 组件独立测试目录 + 参考项目存放处（`components/`、`references/vendor/`） | 组件先在此独立测试才能进 Integration；不得把参考源码复制进正式仓库 |
| `H:\studybuddy-integration` | 组件组合测试目录（按组件分目录：asr/ocr/delivery/report 等） | 通过 Composer 的组件在此做组合契约验证；体量极小（<200KB） |
| `H:\studybuddy-test` | 测试 artifacts/fixtures：合成 fixture、测试运行结果、脱敏 artifact、清理前备份 | 正式测试数据来源；不写入正式仓库运行数据 |
| `H:\studybuddy-ChinaTextbook` | 真实教材与学习资料目录：`小学教材\<年级>\<科目>\`、`基础性作业\`、下载脚本（`下载教材.py` 等）、`教材清单.md`、`智慧教育token.txt`。**已有独立远端仓库**：`github.com/everything-is-simple/studybuddy-ChinaTextbook`（只入库脚本+清单+README，PDF/音频/token 经 .gitignore 排除） | 真实素材源，导入系统后原件由 data_root 保存；**token 文件是密钥，永不清扫、永不外传、永不入库** |

> **非正式目录**：`H:\studybuddy-e2e-test`、`H:\studybuddy-e2e-test-<时间戳>` 是 e2e / 演练产生的一次性临时 data_root（目录内只有 SQLite + lock/pid）。确认 `.pid` 指向的进程已不存在、无文档引用后即可整目录删除，无需备份。

## 二、各目录保留 / 可清边界

### H:\studybuddy（主仓库）
- **保留**：`backend/`、`docs/`、`.archive/`（历史文档归档，README 中的链接指向此处）、`node_modules/`（Playwright 测试依赖）、`.workbuddy/`（项目记忆与本地凭据脚本 `credbin/`，**必留**）、`.codebuddy/`（本机 IDE 记忆，已被 .gitignore 忽略）、`.git/`、根目录入口文档。
- **可清**：`.workbuddy/tmp-*`、`probe-*.js` 等临时脚本；任何 `__pycache__`、`.pytest_cache`、`test-results/`、`node_modules/.cache`。
- **2026-09-19 状态**：已清 `node_modules/.cache` 与扫描脚本；无 `__pycache__` / `.pytest_cache` / `test-results`。

### H:\studybuddy-data（data_root）
- **活跃 data_root 就是它的根目录**：`studybuddy.sqlite3`（生产库，当前 6 份真实教材 / 499 分块 / 499 条真实向量）、`originals/`、`config/settings.json`（外置配置，**含明文 Provider / SMTP 凭据**）、`logs/`。
- 生产运行数据，**大扫除默认整目录跳过**。唯一例外：`logs/` 可只保留最新一组 `server-{out,err}-*.log` 手动轮换（已执行一次，保留 `server-*-20260919-004329.log`）；`.studybuddy.pid` / `.studybuddy-instance.lock` 仅在确认 PID 对应进程已不存在后可删（2026-09-19 已确认无进程并清理，服务下次启动会自动重建）。
- **`live/` 子目录已于 2026-09-19 整体删除**（原为已废弃历史 data_root：v15 库、业务表与 FTS 虚表归零，仅剩 27 个孤立 original 与 FTS 影子表碎片，约 4.2 MB）。历史处置记录与失效的备份路径见 `ARCHIVE_NOTES.md`。
- `backups/` 目录当前为空；项目级备份由 CLI 生成，落点以实际命令为准。

### H:\studybuddy-composer
- **保留**：`components/` 下的组件工程目录（WhisperCli、CapsWriterCli_Full、backend-file-parsers 等）、`references/systems.json`、治理文档、`manifests/b0-catalog.json`、`audits/`（`NEXT-PHASE-PLAN.md`、`KAOBUDDY-*-AUDIT.md` / `RECHECK.md`）。
- **可清**：组件**解压完成后**的原始压缩包；`.venv`（可再生）。
- **2026-09-19 已清**：`components/backend-file-parsers/.venv`（37.1 MB，`pip install -r requirements.txt` 可重建）；`references/vendor/` 下**已验证存在同名解压目录**的原始压缩包共 339.0 MB —— PaddleOCR 的 `PaddleOCR-3.7.0.zip` 与 `models/_downloads/*.tar` 两份、Whisper 的 `Whisper-1.12.0.zip`/`.tar.gz` 双份与 `{WhisperDesktop,WhisperPS,cli,Library}.zip`、kaobuddy 的 3 份嵌套重复 zip（4 份 md5 完全一致，**保留顶层 1 份**）。
- **`references/vendor/` 本身仍按"参考项目完整性"保留**，其余内容（各解压目录、`Models/`、`kaobuddy-remote-audit`）不属清扫范围；如需继续精简须逐项确认。

### H:\studybuddy-integration
- 组合测试契约与结果文档，**无可清项**。2026-09-19 已清 `components/`、`src/` 两个空目录。
- `results/` 已被 `.gitignore` 整体忽略（含 `.env.local`），符合"凭据只放本地 results/ 且不入库"的约定。

### H:\studybuddy-test
- **必须保留**：`artifacts/` 全部证据目录（`formal-*`、`backend-file-parsers`、`file-storage-foundation`、`infrastructure-i4`（TODO.md 引用）、`vector-quality-baseline-*.json`）、`fixtures/`、`scripts/`、`e2e-reports/`、`audits/` 下的 `*.md` / `*.py` / `*.js` 与报告 JSON（如 `probe-report.json`、`performance-cli-report.json`、`cleanup-baseline-20260915.md`）、`README.md`。
- **可清（可再生中间产物）**：`runs/` 全部（pytest basetemp、userpath-*、时间戳目录）、`e2e-screenshots/` 成对截图、`artifacts/` 下非证据的临时截图目录。
- **可清（一次性运行产物）**：`audits/` 下的 scratch data root —— 以 `studybuddy.sqlite3` + `.studybuddy-instance.lock` + `originals/` 为特征的目录。2026-09-19 已清 4 个整目录与 2 个目录中的 scratch 部分。
- **刻意保留（勿删）**：`audits/data-archived-20260915/`（2026-09-15 清扫时刻意归档的库快照）、`audits/rescued-a-review-20260915/`（rescue 出来的材料 `stacks-queues.md` + 原件）。
- **备份目录**：`backups/` 下归档**至少保留最新一份**。2026-09-19 已清 `repo-data-archived-20260919`（386 MB，旧 scratch 数据根归档，21 材料 / 2601 spans / 17 原件，无文档引用），`backups/` 现为空。⚠️ `backups/pre-legacy-cleanup-20260918/` 已在同日上一轮清扫中被删除，引用它的历史记录已在 `ARCHIVE_NOTES.md` 与 `STATUS.md` 加更正说明。

## 三、清扫操作规范

1. **先扫描出清单（只读），用户逐类确认后才动手**；本环境删除按小批分次执行，每批核对。
2. 清理前把"拿不准"的少量内容归档到 `H:\studybuddy-test\backups\<pre-大扫除-日期>\`；**可再生的 runs/缓存不做备份**。
3. 清理用一次性 Python 脚本（本目录 `cleanup-20260919.py` 为现成模板）：**显式白名单路径**，不用 shell 通配符递归删除；脚本内硬护栏拒绝 `ChinaTextbook`、`.git`、`.workbuddy/memory` 与四个允许根之外的一切路径。
4. 清理后验证：跑 `cleanup` 同目录的 `verify-cleanup-20260919.py` 落地核对（该删的全删、该留的全留），再加 `backend/scripts/check-source-size.py` 与 focused 后端测试；结果记录到本文"清扫日志"。
5. 教材下载可复用脚本已在 `H:\studybuddy-ChinaTextbook\`（`下载教材.py`、`下载教材音频.py`、`下载基础性作业.py`）正式化。

## 四、清扫日志

| 日期 | 范围 | 释放空间 | 执行方式 | 备注 |
|------|------|----------|----------|------|
| 2026-09-18 | p0 清扫（见 `p0-cleanup-20260918.py`） | — | 一次性脚本，备份至 `backups/pre-p0-cleanup-20260918` | — |
| 2026-09-19 | runs 清空保留 pytest-basetemp（见 `runs-cleanup-20260919.py`） | — | 一次性脚本 | 之后 runs 又重新累积 |
| 2026-09-19 | 六目录大扫除（第一轮，本文第二、三节边界） | 约 7.4G：test 4.1G、backups 旧归档 252M、composer 安装包 2.6G、主仓库 tmp-chinatextbook 53M、omp-windows-x64.exe 202M | 一次性 Python 脚本分两批，用户逐类确认后执行 | 保留 formal-* 等证据、fixtures、composer/references/vendor。**副作用**：`backups/pre-legacy-cleanup-20260918` 一并被清，导致 `ARCHIVE_NOTES.md` 与 `STATUS.md` 的恢复路径失效（已加更正说明） |
| 2026-09-19 | 六目录说明文档核对与修订（`AGENTS.md` / `README.md` / `docs/INDEX.md` / 本文） | — | 文档修订 | 修正 data_root 双根歧义（根目录=活跃库）、补充 `.codebuddy/`、补记失效备份路径、修 `test_governance_consistency.py` 的 docs 根 md 白名单（既有红灯：`WORKSPACE_DIRECTORIES.md` 未入白名单） |
| 2026-09-19 | 六目录大扫除（第二轮，见 `cleanup-20260919.py`） | 约 777 MB（实测）：test 394.1M（backups 归档 386.1M + audits scratch 8.0M）、composer 376.1M（.venv 37.1M + vendor 冗余原包 339.0M）、data 4.5M（logs/pid 0.3M + `live/` 残留 4.2M）、主仓库 2.5M（`node_modules/.cache`） | 一次性 Python 脚本分 7 批（misc/audits/archive/liveroot/vendor/venv/cache），用户四类全确认 | 保留 50 项"该留"清单全部完好、38 项"该删"清单全部删除（见 `verify-cleanup-20260919.py`）；清理后体量：studybuddy 34.7M / data 124.3M / composer 4.8G / test 3.2M / integration 190K / ChinaTextbook 4.8G。**注**：`vendor` 批次脚本对 10 项误报 `SKIP(不存在)`（脚本记录 472.2M，比实测少 305.1M），但文件系统实测这 10 项确已删除且父目录 mtime 与该批次一致（10:44）；脚本逐项报告与文件系统不一致的成因未定位，以落地核对结果为准。门禁复跑：`check-source-size` 通过、focused 后端 91 passed |
