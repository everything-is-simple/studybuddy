# StudyBuddy 系统工作目录与清扫规范（2026-09-19）

> 本文是六个系统工作目录的**唯一权威说明**：各目录定位、必须保留的内容、可清理的内容。
> 变更目录用途时先改本文，再同步 `AGENTS.md`、`README.md`、`docs/INDEX.md`。

## 一、目录地图

| 目录 | 定位 | 关键约束 |
|------|------|----------|
| `H:\studybuddy` | 正式源码仓库（生产代码 `backend/app/`、正式测试 `backend/tests/`、文档 `docs/`） | 根目录只留入口文档与元数据；不存运行数据；远端 `github.com/everything-is-simple/studybuddy.git` |
| `H:\studybuddy-data` | 正式运行数据根（data_root）：SQLite、hash-derived 原文件、配置、日志 | 唯一活跃 data_root；不进 Git、不进网盘；多实例禁止共用；**清扫默认不动** |
| `H:\studybuddy-composer` | 组件独立测试目录 + 参考项目存放处（`components/`、`references/vendor/`） | 组件先在此独立测试才能进 Integration；不得把参考源码复制进正式仓库 |
| `H:\studybuddy-integration` | 组件组合测试目录（按组件分目录：asr/ocr/delivery/report 等） | 通过 Composer 的组件在此做组合契约验证；目前体量极小（<1MB） |
| `H:\studybuddy-test` | 测试 artifacts/fixtures：合成 fixture、测试运行结果、脱敏 artifact、清理前备份 | 正式测试数据来源；不写入正式仓库运行数据 |
| `H:\studybuddy-ChinaTextbook` | 真实教材与学习资料目录：`小学教材\<年级>\<科目>\`、`基础性作业\`、下载脚本（`下载教材.py` 等）、`教材清单.md`、`智慧教育token.txt`。**已有独立远端仓库**：`github.com/everything-is-simple/studybuddy-ChinaTextbook`（只入库脚本+清单+README，PDF/音频/token 经 .gitignore 排除） | 真实素材源，导入系统后原件由 data_root 保存；**token 文件是密钥，永不清扫、永不外传、永不入库** |

## 二、各目录保留 / 可清边界

### H:\studybuddy（主仓库）
- **保留**：`backend/`、`docs/`、`.archive/`（历史文档归档，README 中的链接指向此处）、`node_modules/`（Playwright 测试依赖）、`.workbuddy/memory/`（项目记忆）、`.git/`、根目录入口文档。
- **可清**：`.workbuddy/tmp-*`、`probe-*.js` 等临时脚本；任何 `__pycache__`、`.pytest_cache`、`test-results/`。

### H:\studybuddy-data（data_root）
- 生产运行数据，**大扫除默认整目录跳过**。唯一例外：`logs/` 可按大小手动轮换；`.pid`/`.lock` 仅在确认服务已停止后可删。

### H:\studybuddy-composer
- **保留**：`components/` 下的组件工程目录（WhisperCli、CapsWriterCli_Full、backend-file-parsers 等）、`references/systems.json`、治理文档。
- **可清**：组件**解压完成后**的原始压缩包（`*.7z`、`*.zip`）；`.venv`（可再生）。
- **需用户逐项确认**：`references/vendor/`（Whisper / PaddleOCR / kaobuddy 参考源码）——对应组件 scoped closeout 完成并归档证据后才有资格清。

### H:\studybuddy-integration
- 目前全部是组合测试契约与结果文档，**无可清项**。

### H:\studybuddy-test
- **必须保留**：`artifacts/formal-*`（README/STATUS 引用的 real-pass 最终证据，含 `formal-file-import-final/latest.json`）、最新的质量基线 JSON（如 `vector-quality-baseline-*.json`）、`fixtures/`、`scripts/` 中长期脚本、`README.md`。
- **可清（可再生中间产物）**：`runs/` 全部（pytest basetemp、userpath-*、*-1789* 时间戳目录）、`artifacts/` 下非 formal 的 `*userpath-*`、`e2e-plan-*`、`*-secret.png` 截图、`e2e-screenshots/` 成对截图。
- **可清（一次性脚本）**：`*-cleanup-*.py`、`anchor-check.py`、`scripts/legacy-delete-diag.js` 这类执行完即弃的脚本（执行前留档到本目录 git 历史）。
- **备份目录**：`backups/` 下的 `pre-*-cleanup-*` / `repo-data-archived-*` 归档，**至少保留最新一份**；更旧的在前一次清理验收通过后可清。

## 三、清扫操作规范

1. **先扫描出清单（只读），用户逐类确认后才动手**；本环境删除按小批分次执行，每批核对。
2. 清理前把"拿不准"的少量内容归档到 `H:\studybuddy-test\backups\<pre-大扫除-日期>\`；**可再生的 runs/缓存不做备份**。
3. 清理用一次性 Python 脚本（参照 `runs-cleanup-20260919.py` 的写法），不用 shell 通配符递归删除；`ChinaTextbook`、`data`、`.workbuddy/memory` 在脚本里显式排除。
4. 清理后验证：`backend` 测试套件仍可跑、`artifacts/formal-*` 完整、各目录 README 与本文一致；结果记录到本文"清扫日志"。
5. 教材下载可复用脚本已在 `H:\studybuddy-ChinaTextbook\`（`下载教材.py`、`下载教材音频.py`、`下载基础性作业.py`）正式化，主仓库 `.workbuddy/tmp-chinatextbook` 中的早期版本可清。

## 四、清扫日志

> **附注（2026-09-19）**：e2e / 验证演练会产生 `H:\studybuddy-e2e-test`、`H:\studybuddy-e2e-test-<时间戳>` 这类**一次性临时 data_root**（目录内只有 SQLite + lock/pid）。它们不属于上述六个正式目录：确认 `.pid` 指向的进程已不存在、无文档引用后即可整目录删除，无需备份。

| 日期 | 范围 | 释放空间 | 执行方式 | 备注 |
|------|------|----------|----------|------|
| 2026-09-18 | p0 清扫（见 `p0-cleanup-20260918.py`） | — | 一次性脚本，备份至 `backups/pre-p0-cleanup-20260918` | — |
| 2026-09-19 | runs 清空保留 pytest-basetemp（见 `runs-cleanup-20260919.py`） | — | 一次性脚本 | 之后 runs 又重新累积 |
| 2026-09-19 | 六目录大扫除（本文第二、三节边界） | 约 7.4G：test 4.1G（runs 573 项 + artifacts 非证据 259 项 + e2e-screenshots 66 项 + 一次性脚本）、backups 旧归档 252M、composer 安装包 2.6G、主仓库 tmp-chinatextbook 53M、omp-windows-x64.exe 202M | 一次性 Python 脚本分两批，用户逐类确认后执行 | 保留：formal-* 23 个证据目录、infrastructure-i4（TODO.md 引用）、vector-quality-baseline-20260919.json、fixtures、backups/repo-data-archived-20260919、composer/references/vendor（用户决定全保留）；清扫后体量：studybuddy 41M / data 129M / composer 5.3G / test 398M / integration 379K / ChinaTextbook 4.8G |
