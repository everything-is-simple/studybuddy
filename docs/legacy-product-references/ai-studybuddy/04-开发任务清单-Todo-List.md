# AI StudyBuddy 开发任务清单

**版本**：v1.118
**日期**：2026-07-28
**用途**：按阶段拆解具体开发任务，避免想到哪做到哪。每个任务有明确的完成标准。

> **AUDIT-20260806：实现代码与设计文档偏差核查（进行中）**：按本文件 Phase 划分，逐 Phase 核查实现代码与设计文档（`docs/01`、`docs/02`、各子系统 PRD、`docs/08`/`docs/10`/`docs/11`/`docs/13`）之间的偏差；发现问题后按系统工作流独立计划、验证、修复。行动计划 `.plans/audit-20260806-doc-code-deviation-plan.md`；任务分支 `claude/audit-20260806-doc-code-deviation`。
>
> 当前进度：以 `origin/master` 为已集成事实。Phase 0.5/0.7/0.8、Phase 1、Phase 2-T01–T06 与 POST-PHASE2 全系统验证/文档收口均已完成主线复验并推送；S1–S6 简版、学生端产品化、配置中心及 T12/M01/M02/M03/Post-M03 维护范围已进入远端主线。开发机 Windows 原生 + Node 24 部署基线已验证；用户电脑安装运行仍待目标机器实机验收，不得宣称完成。Phase 3 T02A–T02G 安全切片已各自完成主线复验并进入 `origin/master`，但 T02 总体、真实机器操作与其余 Phase 3 候选任务仍未完成；用户于 2026-07-28 明确重新开放 Phase 3，但仅按 `PHASE3-REOPEN-HIGH-WEIGHT-20260728` 推进 11 个高权重必做项；计划已创建并等待独立审查与逐项实施。**S7-MVP（本地课堂录音导入 → 可编辑文本 → S2 笔记输入）已完成主线复验并推送 `origin/master`；它只允许受控 PCM WAV、显式本机 `whisper.cpp` 配置和同步短转写，不引入 Worker、FFmpeg、云端/Provider、Firewall/G2、Docker/WSL、实时录音或说话人分离。**旧 T02/T04 外部候选能力为 `PARTIAL`、T03 Composer smoke 为 `PASS`，均仍不等于完整 S7、用户机验收或 Phase 3 业务实现。G2 历史/候选证据仅按其自身环境范围解释，不是本 MVP 的实施事项。

> **DOCS-20260725 系统事实与文档状态收口（主线复验通过）**：在隔离 worktree `codex/process-system-truth-document-reconciliation` 更新 `docs/00`、`docs/01`、`docs/02`、`docs/04`、`docs/06`、`docs/12` 与入口摘要，回答系统为何而生、为谁而做和为何采用本机分阶段设计；同步主线、开发机 Node 24、用户机验收、S7 候选能力与产品接入的边界。不改业务代码、ASR、Firewall、Docker/WSL、Schema、API、Worker 或前端。已 fast-forward 合入干净 `master`；主线 `scripts/check-docs-governance.ps1`、`git diff --check` 和关键事实字面抽查均通过。

> **PROCESS-DIRTY-20260725 多 worktree 脏状态审计、归属判定与安全收口（执行中：目录归拢、Batch 1 学期版本无损收口、Batch 2 生成物清理、Batch 3 陈旧部署 worktree 清理及 `9ed5bc1` 部署候选收口已完成；历史 worktree / 暂停计划继续清理）**：行动计划 `.plans/process-dirty-state-remediation-plan.md`；本轮补充计划 `.plans/process-docs04-phase3-worktree-cleanup-20260725-plan.md`。2026-07-25 已将仓库内 worktree 和失联历史目录迁出主系统；`H:\ai-studybuddy\.worktrees` 已不存在。原脏工作区的学期版本 `8` 已保存到归档提交 `152d81fcb2775ae8e91ccbc24511cdcb478d97ff` 及保留的 `stash@{0}`，主系统保持干净 `master...origin/master`；版本 `9` 与迁移一致；相关 type-check、构建与全量测试 242/242 已通过。Batch 2 已从 `process-runtime-deploy-compatibility-clean-20260724` 精确删除 306 个未跟踪 TypeScript 编译生成物，并保留部署脚本改动、计划、专项测试和运行时辅助源文件用于后续归属审计；分支 `codex/process-runtime-deploy-compatibility` 的唯一提交 `9ed5bc1` 已通过 `b72e8b0 fix(deploy): 修复 PowerShell 兼容与恢复可写性` 等价审计收口并进入 `origin/master`，不再是未处理候选。Batch 3 已确认 `process-runtime-deployment` 无独有提交且 HEAD 为主线祖先，先仅移除其指向 `H:\ai-studybuddy\node_modules` 的 `node_modules.shared-deps` Junction，再用 `git worktree remove` 移除干净旧工作副本；主系统依赖目录和主线均已复查完好。本轮继续按“先审计、再登记、只移除干净且已有归属的 worktree”清理历史隔离区；已安全移除 `phase1-5-s7-mvp-docs-plan`、`process-dirty-state-remediation-plan`、`process-post-s7-docs-deploy-candidate-fix` 与 `process-runtime-deploy-compatibility-20260724` 四个旧 worktree，分支引用保留；`archive-pre-semester-cleanup-20260725`、`phase1-5-g2-windows11-revalidation-plan` 因有独有提交保留，`phase1-5-t02-asr-candidate-harness-plan`、`phase1-5-t02-whispercpp-formal-revalidation-plan`、`post-s7-user-machine-acceptance-plan`、`process-runtime-deploy-compatibility-clean-20260724` 因有未跟踪计划/证据或未提交部署候选内容保留待后续归属审计。当前主线不被完整 S7、G2/外部 ASR 主线、S3 Worker、Docker/WSL 或 Firewall 拖住，用户电脑验收仍不得写为完成。

> **Phase 1.5-T01 S7 PRD（2026-07-21，已批准并完成）**：行动计划 `.plans/phase1-5-t01-s7-prd-plan.md` 已由用户明确批准，计划检查点提交 `22636ab` 已推送任务分支 `codex/phase1-5-t01-s7-prd`。已创建 `docs/subsystems/07-S7-课堂录音子系统PRD-ClassCapture.md`，明确课堂录音 → 本地 ASR → 纯文本 `ConverterResult` → S2 `normalized_texts`/笔记生成管道，以及 composer、`AuralConverter`、后端/API、Job Worker、S2 与前端职责边界；本任务不含 ASR/FFmpeg smoke、Schema、API、Worker 或前端实现。验证：`scripts/check-docs-governance.ps1`、`git diff --check` 与 `git diff --cached --check` 均通过；T02–T06 保持未启动，下一门禁仅为 T02 独立计划。

> **前端信息架构研究证据（2026-07-17）**：已将 OpenDesign 研究稿纳入 `docs/15-前端信息架构与界面范围研究-Frontend-Information-Architecture.md`。吸收考试工作台枢纽、S6 保持异步报告、正式产品消除手输学期 UUID，以及时间线优先嵌入考试工作台的原则；T07 已按独立计划在工作台落地当前课程近期活动，T08 已按独立计划落地本机配置中心。页面数量、系统设置、学期向导、每日首页、练习历史和家长面板均不因此自动进入实现。渠道与 Provider 秘密不得保存到浏览器或 `localStorage`。T09A 已合入并推送 `origin/master`，主线复验通过；T09B、T09C、T09D 与 T09E 均已完成主线集成、主线复验并推送 `origin/master`；家长 Web 面板未启动。

> **系统文档同步证据（2026-07-17）**：同步 `AGENTS.md`、`CLAUDE.md`、`docs/00`、`docs/08`、`docs/12` 与本文件的当前进度表述，统一为 T05 已完成、下一门禁 T06；同时将 S6 PRD 目标命名校准为“家长观察 / ParentReport”，避免误解为家长 Web 面板。本轮不创建 S6 PRD，不实现 T06A/T06B、S5 或 S7。

> **DOCS-20260718 文档一致性任务（完成）**：任务分支 `codex/process-docs-sync`，行动计划 `.plans/process-docs-sync-plan.md`。已同步 `AGENTS.md`、`CLAUDE.md`、`docs/00`、`docs/01`、`docs/02`、`docs/05`、`docs/06`、`docs/07`、`docs/08`、`docs/09`、`docs/10`、`docs/11`、`docs/12`、`docs/15` 与 S1/S2/S3/S4/S6 PRD：统一 T08 已完成、下一门禁 T09A、T09A–T09E 仅登记未实施，以及“任务登记 → 独立计划 → 审查批准 → 实现验证 → docs/04 收尾 → 合入并推送”的强制链路。验证：`powershell -ExecutionPolicy Bypass -File scripts/check-docs-governance.ps1` 通过，`git diff --check` 通过；本轮不改业务代码，不创建 T09A 计划，不实施 T09A–T09E、S5、S7 或真实外部渠道 smoke。

> **Phase 1-M03 设置中心配置可观测性与安全摘要（已合入并推送）**：方案 A 已在隔离任务分支 `codex/phase1-m03-settings-configuration-observability` 完成实现、主线集成与复验：环境 fallback 安全登记为“环境配置（待验证）”，AI/SMTP/飞书首屏展示白名单式脱敏摘要，已保存秘密始终不可回显且不进入浏览器存储；AI HTTP 429 与常见 SMTP 传输失败映射为固定、可行动且不泄密的错误码。隔离验证通过 type-check、后端/前端 build、全量测试（后端 227、前端 93）和真实本地 Express/SQLite 全量 Playwright（14）；仅保留既有 KaTeX chunk-size 非阻塞 warning。实现提交 `2aa7ea4`、主线收尾提交 `6ddd9fa` 已进入 `origin/master`；未读取、输出或持久化任何真实秘密，未自动触发 AI、QQ SMTP 或飞书外部请求。

> **DOCS-20260720 系统文档当前状态同步（已完成）**：用户明确要求将仍停留在 T09A/T09E 旧门禁和 M03/Post-M03 待推送状态的系统文档同步到当前 Git 事实。任务分支 `codex/system-docs-current-status-sync` 仅修订入口规范、文档索引、任务清单、共同架构、子系统状态与前端路由事实，不改业务代码，不创建或实施新的业务任务；任务分支提交 `b9fb3e8` 已 fast-forward 合入 `master`，主线复验通过，并随本收尾提交推送 `origin/master`。

> **POST-PHASE2 全系统验证与文档对齐（✅ 已完成主线复验并推送 origin/master）**：用户于 2026-07-21 明确要求 Phase 2 完成后暂不进入 Phase 3。任务分支 `codex/post-phase2-full-validation` 基于 `origin/master` `4dcc0b2e6bbb130e6e3826e1595ca5995741d2a0` 创建，计划提交 `72c7f7d4dc1a74971e72450a2db2f79f26a21b46`，文档对齐提交 `aea8c013e2e953c7a692093b799da751bd5913a4`，行动计划为 `.plans/post-phase2-full-validation-plan.md`。分支隔离验证均退出码 0：`pnpm type-check`；后端生产构建（含 OCR worker 复制）；前端生产构建（仅既有 KaTeX chunk 535.51 kB 的非阻塞 warning）；`APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\post-phase2-full-validation-20260721-branch-full` 下 `pnpm test`（backend 237/237；frontend 26 个测试文件、61/61 suites、137/137 tests）；`APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\post-phase2-full-validation-20260721-branch-e2e` 下 `pnpm test:e2e`（`e2e/` 15 个 spec，Playwright 21/21）。已按当前代码、路由、API、migration v9、测试和 Git 历史对齐入口规范、总 PRD、子系统地图、架构、测试计划、前后端规范、开发规则、前端信息架构与 S5 PRD。
>
> **POST-PHASE2 主线收尾证据（2026-07-21）**：重新 `git fetch --prune origin` 后确认最新 `origin/master` 仍为 `4dcc0b2e6bbb130e6e3826e1595ca5995741d2a0`，任务分支 `git rebase origin/master` 无需重放且无冲突；随后在干净的主线工作树 `I:\ai-studybuddy-tmp\worktrees\post-t12-m02-master-integration` 执行 `git pull --ff-only origin master` 与 `git merge --ff-only codex/post-phase2-full-validation`，本地 `master` 快进到 `aea8c013e2e953c7a692093b799da751bd5913a4`，未产生 merge commit。主线隔离复验均退出码 0：`APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\post-phase2-full-validation-20260721-master-full` 下 `pnpm type-check`、后端 build、前端 build、`pnpm test`（backend 237/237、frontend 61/61 suites 与 137/137 tests；机器可读证据为 `frontend-vitest.json`）；`APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\post-phase2-full-validation-20260721-master-e2e` 下完整 `pnpm test:e2e`（15 个 spec、21/21）；文档治理与 `git diff --check` 通过。最终状态由本次 `docs(process): 同步 Phase 2 收口验证完成状态` 提交发布并推送 `origin/master`。本轮不实施 Phase 3，不启动 S7、S3 Worker，不运行真实 AI、QQ SMTP、飞书、正式 Windows Task Scheduler 或其他外部 smoke。

---

## 阶段总览

| 阶段      | 目标                                    | 状态                                                                                                                                                                                          |
| --------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 0   | 文档重建、旧草稿归档、七子系统命名      | ✅ 已完成                                                                                                                                                                                     |
| Phase 0.5 | 成熟开源组件在 composer 独立调通        | ✅ 已完成（MVP 主路径 smoke test 全部通过）                                                                                                                                                   |
| Phase 0.7 | Windows 原生轻量底座与异步家长报告验证  | ✅ 开发机验收完成（HP 实机兼容性复测待机会执行，不阻塞 Phase 0.8）                                                                                                                            |
| Phase 0.8 | 第一个可运行里程碑（S1 基础 + S2 核心） | ✅ 已完成（T09 隔离复验通过）                                                                                                                                                                 |
| Phase 1   | 跑通完整学习闭环（S1+S2+S3+S4+S6 简版） | ✅ 已完成；S3 Worker 不属于当前 MVP                                                                                                                                                           |
| Phase 1.5 | 课堂录音转文字（S7-MVP）                | ✅ S7-MVP 已完成主线复验并推送 `origin/master`：本地受控 WAV → 同步 `whisper.cpp` → 可编辑文本 → 显式保存为 S2 文本资料；旧候选证据不等于完整 S7、G2、T02 主线、用户机验收或 Phase 3 业务实现 |
| Phase 2   | 期末冲刺（S5）                          | ✅ T01–T06 与 POST-PHASE2 收口均已完成并推送                                                                                                                                                  |
| Phase 3   | 打磨与安全                              | 📝 2026-07-25 按用户要求启动治理/计划阶段；首批实施仍需独立计划和批准                                                                                                                         |

---

## Phase 0.5：开源组件独立调通

**目标**：在 `I:\ai-studybuddy-composer` 先把每个组件跑起来，形成能力卡，再进主系统。

**Phase 0.5 完成标准**：MVP 主路径组件通过 smoke test，输入/输出格式已确认，能力卡和共同底座文档已回填。PaddleOCR、Kimi/Qwen、ASR、FFmpeg、Readability 等备选/后续组件不计入 Phase 0.5 完成门槛。

### 0.5-T01：环境准备

- [x] 确认 Node.js 18+、Python 3.8+、Docker Desktop 可支撑组件 smoke test
- [ ] 可选治理：在 `C:\Users\Administrator\.wslconfig` 写入内存上限（防 Docker Desktop WSL2 内存泄漏）：`memory=8GB processors=4 swap=2GB`
- [x] 创建 `I:\ai-studybuddy-composer` 目录结构（已完成）
- [x] 配置 `.env.example`，列出后续会用到的环境变量名（不填真实值）

> ⚠️ 常见坑：Node 命令不存在 → 去 nodejs.org 装 LTS；Python 是 2.x → 装 3.10+；Docker 图标未变绿就跑命令会报错，等它完全启动再操作。

### 0.5-T02：PDF 文本提取（MVP 必接）

- [x] 在 `I:\ai-studybuddy-composer\pdf\pdf-parse-demo\` 安装：`npm install`
- [x] 准备 1 个含中文的真实 PDF，放入 `samples\test.pdf`（用教材/讲义，不用扫描版）
- [x] 运行 smoke test：`node smoke-test\smoke-test.js`
- [x] 验证完成标准：中文字符完整、数学公式文本可用、无乱码
- [x] 填写能力卡（2026-07-09 已完成）

> ⚠️ 常见坑：输出乱码 → PDF 是扫描版图片，换文字版；中文显示 `?????` → PDF 字体未嵌入，换另一个 PDF；数学公式变乱符号 → 正常，公式是图片走 OCR 路径。
> 2026-07-09 实测：`01-总PRD-产品需求-Product-Requirements.pdf` 通过（7 页、5155 字符、2422 个中文字符）；`电工考点.pdf` 可读取 14 页但只提取到页码标记、0 个中文字符，疑似扫描版，应进入 OCR 路径。

### 0.5-T03：图片 / 试卷 OCR（MVP 必接）

- [x] 安装 RapidOCR（首选）：`pip install rapidocr-onnxruntime -i https://pypi.tuna.tsinghua.edu.cn/simple`
- [ ] 后续可选：安装 PaddleOCR（对比用）：`pip install paddlepaddle paddleocr -i https://pypi.tuna.tsinghua.edu.cn/simple`
- [x] 准备 1 张真实中文试卷图片（清晰拍照，非截图），放入各自 `samples\test.jpg`
- [x] 运行 RapidOCR：`python smoke-test\smoke-test.py`，记录单页耗时
- [x] 运行 RapidOCR 批量测试：`python smoke-test\smoke-test-batch.py`，记录 22 张书页汇总
- [ ] 后续可选：运行 PaddleOCR：`python smoke-test\smoke-test.py`，记录识别率和单页耗时（备选对比，不阻塞）
- [x] Phase 0.8 主路径先选 RapidOCR，填写能力卡；PaddleOCR 作为可替换实现保留

> ⚠️ 常见坑：pip 超时 → 加 `-i` 清华源；首次运行自动下载模型约 50MB 需等待；识别率 <80% → 图片模糊/旋转，换清晰图片；耗时 >15s → 正常，接入主系统必须走 BullMQ 异步 Job；DLL 报错 → 安装 Visual C++ Redistributable。
> 2026-07-09 实测：RapidOCR 批量识别 22 张繁体书页全部有输出，总耗时 42.62s，平均 1.94s/页，中文字符 3009，平均置信度 0.8925；无人工标注文本，暂不宣称真实识别率。

### 0.5-T04：思维导图渲染（MVP 必接）

- [x] 在 `I:\ai-studybuddy-composer\mindmap\markmap-test\` 安装：`npm install markmap-lib`
- [x] 运行 smoke test：`node smoke-test\smoke-test.js`，生成 `output\result.html`
- [x] 用浏览器打开 `output\result.html`，验证节点层级正确、可展开收起、中文无乱码
- [x] 填写能力卡（2026-07-09 已完成浏览器复核）

> ⚠️ 常见坑：HTML 打开空白 → CDN 加载失败，开代理或换 Chrome；中文显示方框 → 用 Chrome 打开，Edge 偶有问题；节点层级乱 → 检查 `samples\sample.md` 缩进是空格不是 Tab。

### 0.5-T05：Markdown + KaTeX 渲染（MVP 必接）

- [x] 直接用浏览器打开 `composer\markdown\react-markdown-test\smoke-test\index.html`
- [x] 验证：行内公式 `$E=mc^2$` 渲染正确、块级公式渲染正确、中文显示正常、无 JS 报错
- [x] 填写能力卡（2026-07-09 已完成 Chrome 浏览器验证）

> ⚠️ 常见坑：公式显示原始 `$...$` 字符 → KaTeX CDN 加载失败，开代理；页面卡住 → 同上；用 Chrome 打开最稳定。

### 0.5-T06：异步任务队列 BullMQ（MVP 必接）

- [x] 启动 Redis：`docker run -d --name redis -p 6379:6379 redis:7-alpine`
- [x] 在 `composer\queue\bullmq-test\` 安装：`npm install`
- [x] 运行 smoke test：`node smoke-test\smoke-test.js`
- [x] 验证完成标准：Job 经历 waiting→active→completed 全生命周期，失败后重试成功
- [x] 填写能力卡（2026-07-09 已完成）

> ⚠️ 常见坑：`ECONNREFUSED 6379` → Redis 容器没起来，`docker ps` 确认；`port already allocated` → `netstat -ano | findstr 6379` 找占用进程关掉；测完记得清理 `docker stop redis && docker rm redis`。
> 2026-07-09 实测：Docker Hub 拉取 `redis:7-alpine` 时 token EOF，改用 `docker.m.daocloud.io/library/redis:7-alpine` 成功；Redis 7.4.9，BullMQ 5.79.3，失败重试和 completed 状态通过；测试后已清理 Redis 容器。

### 0.5-T07：对象存储 MinIO（MVP 必接）

- [x] 启动 MinIO：`docker run -d --name minio -p 9000:9000 -p 9001:9001 -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin minio/minio:latest server /data --console-address ":9001"`
- [x] 在 `composer\storage\minio-test\` 安装：`npm install`，复制 `.env.example` 为 `.env.local`
- [x] 运行 smoke test：`node smoke-test\smoke-test.js`
- [x] 额外验证：浏览器打开 `http://localhost:9001`，用 minioadmin/minioadmin 登录能看到控制台
- [x] 验证完成标准：上传/下载内容一致，临时 URL 可访问
- [x] 填写能力卡（2026-07-09 已完成）

> ⚠️ 常见坑：9000 端口占用 → 改 `-p 9002:9000` 并同步改 `.env.local`；`AccessDenied` → 检查账号密码是否与 docker run 一致；临时 URL 浏览器打不开 → 正常，URL 是给 Node 脚本访问的，不是给浏览器直接开的。
> 2026-07-09 实测：Docker Hub 拉取 `minio/minio:latest` 时 TLS handshake timeout，改用 `docker.m.daocloud.io/minio/minio:latest` 成功；MinIO RELEASE.2025-09-07T16-13-09Z，SDK minio 8.0.7，上传/下载一致、presigned URL、对象删除、控制台登录均通过；测试后已清理 MinIO 容器。

### 0.5-T08：数据库 PostgreSQL（MVP 必接）

- [x] 启动 PostgreSQL+pgvector：`docker run -d --name postgres -p 5432:5432 -e POSTGRES_PASSWORD=devpassword pgvector/pgvector:pg16`
- [x] 在 `composer\db\pgvector-test\` 安装：`npm install`，复制 `.env.example` 为 `.env.local`
- [x] 运行 smoke test：`node smoke-test\smoke-test.js`
- [x] 验证完成标准：CRUD 正常，pgvector 扩展加载成功，向量搜索返回结果
- [x] 填写能力卡（2026-07-09 已完成）

> ⚠️ 常见坑：`ECONNREFUSED 5432` → 容器刚起来需等 5 秒，`docker logs postgres` 看是否就绪；`extension "vector" does not exist` → 镜像用错了，必须用 `pgvector/pgvector:pg16` 不是普通 `postgres`；5432 端口占用（本机装了 PG）→ 改 `-p 5433:5432` 并同步改 `.env.local`；密码不对 → `.env.local` 里 `POSTGRES_PASSWORD` 必须和 docker run 的 `-e` 一致。
> 2026-07-09 实测：PostgreSQL 16.14 + pgvector 0.8.5 通过；建表、插入 3 条中文记录、查询、余弦距离向量搜索、IVFFlat 索引均通过；测试后已清理 `postgres` 容器。Docker Desktop 后端曾短暂无响应，重启 Docker Desktop 后官方镜像拉取成功。

### 0.5-T09：AI Provider——中转 GPT/Claude（MVP 必接）

- [x] 在 `composer\ai-provider\gpt-test\` 安装：`npm install`
- [x] 创建 `.env.local`，填入：`RELAY_API_KEY=你的Key`、`RELAY_BASE_URL=https://你的中转/v1`、`RELAY_MODEL=gpt-5.5`
- [x] 运行 smoke test：`node smoke-test\smoke-test.js`
- [x] 验证完成标准：API 调通，返回可解析 Markdown，latency < 30s
- [x] 记录：模型名、token 消耗、响应时间，填写能力卡（2026-07-09 已完成）

> ⚠️ 常见坑：`401 Unauthorized` → Key 错或 baseURL 末尾少了 `/v1`；返回内容不是中文 → 模型名写错，查中转平台支持的模型列表；latency > 30s → 中转服务慢，换个时间段或换另一家中转；`.env.local` 绝不提交 git，Key 泄露后立即去中转平台作废重生成。
> 2026-07-09 实测：已创建 `I:\ai-studybuddy-composer\ai-provider\gpt-test`，按 cc-switch 导出的当前 Pixel provider `pixelapi-1783123721199` 读取 auth，使用 Pixel API 中转站 `https://ai-pixel.online/v1`、`wire_api=responses`、模型 `gpt-5.5` 通过。响应时间 11.9s，输入 tokens 460，输出 tokens 528，总 tokens 988；返回 Markdown、中文内容、思维导图 JSON 均通过。最初 401 根因是 `.env.local` 中手填 Key 与 cc-switch 正在使用的 provider key 不一致。DeepSeek 已按用户偏好废弃；Kimi 当前无 Key；GLM-5.2 已到期。

### 0.5-T10：共同底座架构汇总 / Phase 0.8 开工前整理

- [x] 读 `docs/00-文档索引-Index.md`，确认当前共同底座文档已存在：`docs/08-共同底座架构-Architecture.md`
- [x] 不新建 `docs/10-*`：`10-后端开发规范` 的触发条件是写第一个后端服务 / Adapter / API / Worker 前，当前尚未触发
- [x] 更新 `docs/08-共同底座架构-Architecture.md`：补齐 Phase 0.5 smoke test 结论、AI Provider 实测配置、RapidOCR 主路径、Phase 0.8 开工前置清单
- [x] 同步更新系统设计相关文档：`01-总PRD`、`02-七子系统地图`、`04-开发任务清单`、`05-开源组件装配`、`09-测试验收计划`
- [x] 运行治理检查：`powershell -ExecutionPolicy Bypass -File scripts\check-docs-governance.ps1`
- [x] 运行空白检查：`git diff --check`

### 后续候选：支撑 S3 + S4 的第二批组件

> Phase 0.8 跑通后，准备进入 S3/S4 开发前调通。

- [ ] 客观题规则批改：选择题 / 填空题最小规则引擎测试
- [ ] 错题复习排程：艾宾浩斯间隔复习日期计算测试
- [ ] Qwen Provider：文本备选最小样例（同 Kimi smoke test 格式）
- [ ] GPT Provider：难题兜底最小样例

### 后续候选：工程治理脚本

- [ ] 备份 zip 脚本：标注阶段、commit hash、风险说明、恢复方式
- [ ] tmp 清理脚本：清空 `I:\ai-studybuddy-tmp` 后系统可继续运行
- [ ] logs 规范验证：确认日志中不记录 API Key、学生隐私全文、完整答案
- [ ] lint 治理（2026-07-16 T03D 全面测试发现）：补齐根目录与 workspace 包统一 `lint` scripts，使 `pnpm lint` 成为可执行检查；作为独立工程治理任务处理，不混入功能任务
- [ ] format 治理（2026-07-16 T03D 全面测试发现）：针对 `prettier --check` 暴露的全仓既有格式问题建立分批格式化计划，按模块/文档分批收敛，避免一次性大范围无关 diff

暂不进入 Phase 0.5 主线：SenseVoice、FunASR、FFmpeg、Readability。它们等 S7 或对应子系统开工前再调。

### Phase 0.5 完成声明

截至 2026-07-09，Phase 0.5 已完成并复测通过：PDF、RapidOCR、Markmap、Markdown/KaTeX、BullMQ、MinIO、PostgreSQL/pgvector、Pixel API 中转 AI Provider 均已通过 smoke test，T10 共同底座汇总已回填。

Phase 0.5 不包含 Windows 原生 SQLite、本地文件、持久化 Job、家长报告与 Windows 任务计划验证。这些替代底座能力独立收口为 Phase 0.7；Phase 0.7 完成后再进入 Phase 0.8 主系统实现。

---

## Phase 0.7：Windows 原生轻量底座验证

**目标**：在外部组件试炼场 `I:\ai-studybuddy-composer\windows-native\` 独立验证单机 Windows 方案。Phase 0.7 不修改 `I:\ai-studybuddy\packages\` 主系统代码；验证失败不得污染主系统骨架。

**完成标准（修订版，2026-07-11）**：SQLite、本地文件、SQLite Job Worker、RapidOCR 子进程、规则报告、QQ SMTP、飞书 Webhook、Windows 任务计划和整合链路均有能力卡，且真实 QQ/飞书凭据已通过真实送达验证。

门槛调整说明：原"HP 16GB 实机"硬性门槛已改为"开发机验收完成后即可进入 Phase 0.8；HP 实机（Windows 11、Node 22 LTS、16GB）作为可选兼容复测，在设备可用后执行，不阻塞主系统开发"。调整原因：开发机已完成所有功能性验证，HP 实机复测目的仅为兼容性确认，不应阻塞产品进展。

### 0.7-T01：Windows 原生环境基线

- [x] 在外部试炼场建立独立样例，不加入主系统 pnpm workspace（开发机 Node 25.4.0 兼容通过）
- [x] 记录开发机 Windows、Node、Python、内存与 Docker/WSL2 未运行状态
- [x] 创建 `.env.example`，不写真实 SMTP 授权码、Webhook 或 API Key

- [ ] 在孩子 HP 上用 Node.js 22 LTS 复测独立安装和环境基线（暂缓：设备不在身边）

### 0.7-T02：SQLite 基础与备份

- [x] 安装并验证 `better-sqlite3` 的 Windows x64 预编译模块（开发机 Node 25.4.0 兼容通过；Node 22 LTS/HP 暂缓复测）
- [x] 验证 WAL、CRUD、唯一约束、事务提交/回滚、关闭后备份与恢复（开发机离线通过）
- [x] 建立 `courses`、`study_tasks`、`study_events`、`jobs`、`report_deliveries` 最小 schema（开发机离线通过）

### 0.7-T03：本地文件存储

- [x] 验证 `materials/<course-id>/<yyyy-mm-dd>/`、`tmp/<job-id>/`、`exports/<yyyy-mm>/` 目录（开发机离线通过）
- [x] 验证写入、读取、删除、临时文件清理和路径越界拒绝（开发机离线通过）
- [x] 只保存逻辑 `storage_key`，不把绝对路径写入业务数据（开发机离线通过）

### 0.7-T04：SQLite Job Worker

- [x] 验证单进程串行领取 `pending` Job（开发机离线通过）
- [x] 验证首次失败后重试成功、达到上限后失败、过期 `running` Job 恢复（开发机离线通过）
- [x] 验证进程重启后待处理 Job 不丢失（开发机离线通过）

### 0.7-T05：RapidOCR 子进程

- [x] Node 用 `child_process` 调 Python RapidOCR，stdout 只返回 JSON（开发机离线通过）
- [x] 验证成功、文件不存在、非零退出、超时终止（开发机离线通过；HP 峰值暂缓复测）
- [ ] 记录 OCR 运行峰值内存，确认 Python 进程完成后退出（**⏳ 非阻塞技术债**：尚未在当前开发机补充记录）

### 0.7-T06：规则报告与 AI 失败兜底

- [x] 用 SQLite 统计课程、任务、完成/逾期、学习时长、日周月趋势和考前提醒（开发机离线通过）
- [x] 验证 AI 润色成功时附加总结，失败时仍发送规则报告（开发机离线通过）
- [x] 验证报告不含资料原文、笔记正文、答案或聊天内容（开发机离线通过）

### 0.7-T07：QQ SMTP 邮件

- [x] 用 `nodemailer` 验证 QQ SMTP HTML 中文报告和可选附件（真实通过）
- [x] 验证错误授权码/网络失败写入诊断但不泄露授权码
- [x] 用真实父母收件邮箱完成一次手工验证（163 测试邮箱已收到）

### 0.7-T08：飞书 Webhook

- [x] 验证完整日报卡片、周报/月报合并区块、考前提醒区块（真实通过）
- [x] 验证 Webhook 失败不阻止邮件渠道
- [x] 用父母飞书群真实收到卡片完成手工验证

### 0.7-T09：Windows 任务计划

- [x] 使用临时 `AIStudyBuddy-Phase07-Smoke` 任务验证 `report.js`、日志、退出码和删除清理（管理员 PowerShell 真实通过）
- [x] 验证 `StartWhenAvailable=true` 和固定周期发送记录去重：`report:2026-05-31`
- [x] 记录正式 22:30 日报、周日/月末合并报告、考前 7/3/1 天提醒的规则

### 0.7-T10：整合链路与 HP 实机验收

- [x] 开发机跑通离线整合：课程/任务 → 本地资料 → OCR → SQLite/文件 → 规则报告 → 渠道去重；QQ SMTP、飞书与 Windows 任务计划另行真实通过（HP 实机暂缓）
- [x] 用固定 `2026-05-31 22:30 Asia/Shanghai` 验证日报、周报、月报、考前提醒合并（开发机离线通过）
- [ ] 在孩子 HP Pavilion Aero（Windows 11、Ryzen 5 5625U、16GB）复测（**⏳ 兼容性验证，非阻塞**）
- [ ] 验收：学习服务可用内存 ≥6GB；OCR/AI/报告峰值可用内存 ≥3GB；无持续分页增长（**⏳ 待 HP 设备可用后执行**）

---

## Phase 0.8：第一个可运行里程碑

**目标**：

```
学生创建课程与考试目标
  → 上传 PDF/图片/文本
  → 格式转换为纯文本
  → 中转 GPT/Claude 生成结构化笔记 + 重点 + 思维导图 + 带来源证据的知识模块
  → 规则生成可完成的学习任务
  → 前端能看到笔记、导图、知识模块和任务
```

**前置条件**：Phase 0.7 开发机验收完成（已满足）。`packages/` 不得把试炼场代码直接当成产品实现。HP 实机兼容复测在设备可用后执行，不阻塞本阶段。

**完成标准**：前置条件满足后，端到端流程可以演示；不需要完整功能，只需核心路径跑通。

### 0.8-T01：项目结构初始化

- [x] 在 `I:\ai-studybuddy` 初始化 monorepo（pnpm workspace，已存在并验证）
- [x] 创建基础包结构：`packages/shared`、`packages/backend`（已验证编译通过）；`packages/frontend` 目录存在，待补 `package.json`（T08 阶段补齐）
- [ ] 配置 TypeScript（已完成）；ESLint、Prettier 待补（非阻塞 T02）
- [x] 配置 `.env.example`（T02 开发时同步补齐，已完成）

### 0.8-T02：共同底座——数据库与迁移

- [x] 基于 Phase 0.7 结果选定 SQLite + `better-sqlite3`；实现项目内简单版本递增 migration runner，不引入额外 migration 框架
- [x] 创建第一批底座表：全局库 `students`、`semesters`、`backup_records`；学期库 `course_instances`、`assessment_attempts`、`study_tasks`、`study_events`、`jobs`、`report_deliveries`。其中 `students`/`course_instances`/`assessment_attempts` 分别对应单孩子档案/课程/考试目标的当前存储边界
- [x] 创建第二批表：`materials`、`normalized_texts`、`structured_notes`、`mind_maps`、`knowledge_modules`
- [x] `assessment_attempts` 具备课程关联、名称、`exam_at`、目标、每日可学习时间、范围摘要、来源与识别置信度、孩子确认基础字段；7/3/1 提醒的正式读取逻辑留待 T06 API 实现
- [x] `knowledge_modules` 具备课程关联、标题、重要度、难度、考察内容、来源资料/证据、学习状态；不保存或复制完整资料正文
- [x] 明确不创建 `questions`、`practice_sessions`、`practice_answers`、`mistakes`、`weak_points`：它们等待 S3/S4 PRD 触发后再迁移
- [x] 启用 WAL、foreign keys、严格迁移版本检查；以干净 `dist/` 运行自动化测试，验证日期校验、初始化成功、重复拒绝、rename/ready 故障全量补偿、分学期隔离、损坏库备份恢复
- [x] T06 前补齐 S1 业务字段与迁移：课程表 `schedule_entries`、考试 `confirmation_status`/`confirmed_at`/变更历史；它们尚未驱动倒计时、提醒或家长报告

> 2026-07-11 T02-R 收尾证据：`pnpm type-check`、`pnpm test` 均通过；测试从清空 `dist/` 与 `tsconfig.tsbuildinfo` 开始构建，确认 SQL schema 已随 TypeScript 产物进入 `dist/`，不存在旧 `.sql` 运行态依赖。

### 0.8-T03：共同底座——文件存储接口

- [x] 封装 `StorageAdapter`，对接本地文件目录
- [x] 实现：上传文件、localhost API 流式下载、逻辑 `storage_key`
- [x] 文件写入 `APP_DATA_ROOT`（通过环境变量配置）
- [x] 路径越界拒绝与 `storage_key` normalize 校验
- [x] 吸纳 GPT 反馈：读操作不隐式创建空库/目录

> 2026-07-11 T03 收尾证据：`pnpm type-check`、`pnpm test` 均通过；新增 `StorageAdapter`、`/api/dev/storage/*`、db-readonly 回归测试；`multer` 单文件大小限制 50MB。

### 0.8-T04：共同底座——格式转换层

- [x] 封装 `PdfConverter`（复用 0.5-T02 调通的 pdf-parse）
- [x] 封装 `OcrConverter`（复用 0.5-T03 调通的 RapidOCR；PaddleOCR 作为备选对比，不阻塞）
- [x] 封装 `TextConverter`（Markdown/纯文本直接入库）
- [x] 统一输出格式：`ConverterResult { ok, sourceType, text, metadata, warnings, error }`

> 2026-07-11 T04 收尾证据：`pnpm type-check`、`pnpm build`、`pnpm test` 均通过；新增 `PdfConverter`/`OcrConverter`/`TextConverter`、`ocr-worker.py`、`/api/dev/converter/*` 与回归测试；`pdf-parse` 固定版本 2.4.5，OCR Python 脚本通过 build 脚本复制到 `dist/scripts`。
> **资料格式边界（T04 基线）**：

| 输入                | 当前策略                                   | 目标阶段             |
| ------------------- | ------------------------------------------ | -------------------- |
| PDF                 | `PdfConverter` 提取文本；扫描版转 OCR 路径 | T04 已支持           |
| JPG/JPEG/PNG 等图片 | `OcrConverter` 调 RapidOCR                 | T04 已支持           |
| TXT/MD/CSV/JSON     | UTF-8 文本直接读取；不承诺结构化语义       | T04 已支持           |
| DOCX                | `mammoth` 提取正文                         | T04A 验证，T04B 装配 |
| PPTX                | `jszip` + XML 提取文字层；图片文字转 OCR   | T04A 验证，T04B 装配 |
| HTML/HTM、网页 URL  | DOM 解析 + Readability 提取正文            | T04A 验证，T04B 装配 |
| 音频                | 暂不处理，后续 ASR 任务                    | 后续阶段             |
| 视频                | 仅预留，不进入当前上传支持                 | 后续阶段             |

**明确不支持**：`.doc`、`.xls/.xlsx`、`.ppt`、`.odt/.ods/.odp`、`.rtf`、`.epub`、`.zip/.rar/7z`、`.eml/.msg` 及其他 Office/容器格式。上传这些格式必须返回明确的“请另存为 PDF、DOCX、PPTX 或文本/图片”提示；不得静默按二进制文本读取。

### 0.8-T04A：扩展格式支持——composer 试炼场调通

**目标**：在 `I:\ai-studybuddy-composer` 逐一调通四类格式的开源处理方案，形成能力卡，再装配进主系统。处理后均输出纯文本，接口与 T04 已有的 `ConverterResult` 保持一致。

**状态**：✅ 已完成（2026-07-11）。能力卡与 smoke test 均通过，四类格式输出结构已与 `ConverterResult` 对齐。

**优先级排序（高→低）**：

- [x] **DOCX**（Word 现代格式）
  - 方案：`mammoth`（MIT 许可）+ `jszip` + `jsdom`
  - 目录：`I:\ai-studybuddy-composer\converter\docx-test\`
  - 完成标准：正文提取完整，图片/图表占位符标注，空文档返回明确错误提示
  - 能力卡：`I:\ai-studybuddy-composer\converter\docx-test\COMPONENT-CARD.md`
  - 旧版 `.doc`（Word 97-2003）：提示用户"另存为 DOCX 后重新上传"，不做二进制解析

- [x] **URL 抓取**（网页链接）
  - 方案：`undici`（显式 `fetch` + `Agent` 作为 `dispatcher`）+ `jsdom` + `@mozilla/readability`
  - 目录：`I:\ai-studybuddy-composer\converter\url-fetch-test\`
  - 完成标准：正文去除导航栏/广告，中文编码正确，请求失败（超时/404/反爬）返回明确错误
  - 能力卡：`I:\ai-studybuddy-composer\converter\url-fetch-test\COMPONENT-CARD.md`
  - 百度百科、知乎等强反爬 URL：当前以"抓取失败，请手动复制正文"提示，不做代理绕过
  - 安全边界：仅允许 `http/https`；禁止 user-info、localhost、私网、回环、链路本地和文件协议；DNS 全地址公网校验；连接复验（`undici.Agent.lookup`）；限制响应大小 5 MB、重定向 3 次、请求超时 10 秒；不执行网页脚本

- [x] **PPTX**（PowerPoint 现代格式）
  - 方案：`jszip`（MIT 许可）解压 .pptx zip 包，正则提取 `<a:t>` 节点文本，按幻灯片序号组装
  - 目录：`I:\ai-studybuddy-composer\converter\pptx-test\`
  - 完成标准：各页文本按顺序提取，嵌入图片内的字注明"需走 OCR"，纯图片幻灯片不报错
  - 能力卡：`I:\ai-studybuddy-composer\converter\pptx-test\COMPONENT-CARD.md`
  - 旧版 `.ppt`（PowerPoint 97-2003）：提示用户"另存为 PPTX 或 PDF 后重新上传"

- [x] **HTML 文件**（`.html`/`.htm` 本地文件）
  - 方案：`jsdom` 构造 DOM + `@mozilla/readability` 解析本地 HTML（与 URL 方案共用）
  - 在 `url-fetch-test` 中追加本地 HTML smoke test：`npm run smoke:html -- samples\course-notice.html`
  - 完成标准：正文提取正确，`<script>`/`<style>` 剥除，中文无乱码；Readability 失败时 fallback 到 body 并给出 warning

> **T04A 收尾证据（2026-07-11）**：
>
> - DOCX：`npm test` 4/4 通过；`samples/chinese-with-image-and-chart.docx` 中文正文完整、`embeddedVisualCount=3`；`samples/empty.docx` 受控失败；版本 mammoth 1.12.0 / jszip 3.10.1 / jsdom 26.1.0。
> - URL/HTML：初始 `npm test` 22/22 通过；审查修复后 25/25 通过，新增 dispatcher 传入、连接层回环 DNS 拒绝、错误响应 body 取消与 Agent `finally` 关闭回归；本地 HTML 中文正文提取成功；真实 URL `https://zh.wikipedia.org/wiki/%E4%B8%AD%E5%8D%8E%E4%BA%BA%E6%B0%91%E5%85%B1%E5%92%8C%E5%9B%BD` 首次抓取成功（`ok: true`，`charCount=124722`，`byteCount=2375227`，`durationMs=5467`），重复访问触发 429 反爬后受控返回人工出口；版本 undici 7.28.0 / jsdom 26.1.0 / @mozilla/readability 0.6.0。
> - PPTX：`npm test` 5/5 通过；三页按数字序、含图页 OCR 提示、纯图片页 `ok: true`；审查修复将原恒真断言替换为命名/十进制/十六进制 XML entity 实测解码；版本 jszip 3.10.1。
> - 全部能力卡已填，主系统 `I:\ai-studybuddy\packages` 未修改。

> **不在本任务范围**：Excel、旧版 Office、OpenDocument、RTF、EPUB、压缩包、邮件附件、音频和视频均不在 T04A/T04B；需要时另立任务并先在 composer 验证。

### 0.8-T04B：扩展格式支持——装配进主系统

**前置条件**：0.8-T04A 全部完成（能力卡已填，smoke test 通过）—— 已满足。

- [x] 新增 `DocxConverter` 封装 mammoth，统一实现 `convert(input: Buffer | string): Promise<ConverterResult>`
- [x] 新增 `UrlFetcher` 封装 fetch + Readability，统一接口 `fetch(url: string): Promise<ConverterResult>`
- [x] 新增 `PptxConverter` 封装 jszip + XML 提取，统一接口与上一致
- [x] `TextConverter` 扩展支持 `.html`/`.htm` 文件（复用 Readability）
- [x] 在 `dev-converter.ts` 补充对应 `/api/dev/converter/docx`、`/url`、`/pptx` 端点，供 smoke test 验证
- [x] 更新文件类型路由：上传接口按扩展名/MIME 分派到对应 Converter，`.doc`/`.ppt`/`.xls` 返回友好提示而非静默失败
- [x] `pnpm type-check`、`pnpm build`、`pnpm test` 全部通过
- [x] 运行 `scripts/check-docs-governance.ps1`，无报错后提交

> **T04B 审查修复证据（2026-07-12）**：
>
> - 修复 URL 重定向链共享 10 秒总 timeout、IPv6/IPv4-mapped IPv6 SSRF 字面量拦截，以及 HTTP/HTTPS 跨协议端口拒绝；DNS `connect.lookup` 复验保留。
> - URL Dev API 失败现返回标准 `ApiError` 信封和稳定错误码；DOCX/PPTX 的 `string` 输入统一解释为本地文件路径。
> - 验证：`pnpm type-check`、`pnpm build`、`pnpm test`（71/71）、`scripts/check-docs-governance.ps1` 与 `git diff --check` 全部通过。

### 0.8-T05：共同底座——AI Provider Router

**状态**：✅ 已完成（2026-07-12）。

- [x] 安装 `openai` SDK，环境变量支持 `AI_PROVIDERS` JSON 数组、`AI_TIMEOUT_MS`，并保留 `AI_BASE_URL`/`AI_API_KEY`/`AI_MODEL` 向后兼容
- [x] 抽象 `AiProvider` 接口，实现 `OpenAiProvider`（支持构造函数注入 `fetch` 便于测试）
- [x] 实现 `AiProviderRouter` 多 Provider 轮询链：按 `priority` 升序尝试，首个成功即返回，全部失败抛 `AI_ALL_PROVIDERS_FAILED`
- [x] 实现 `AiLogger`，仅记录 `taskType`、`provider`、`model`、`tokenUsed`、`latencyMs`、`fallbackUsed`、错误码与信息，**不记录 `inputText` 与生成的 `content`**
- [x] 暴露 Dev API `POST /api/dev/ai/generate`，返回标准 `ApiSuccess<AiResponse>`/`ApiError`；未配置返回 `AI_NOT_CONFIGURED`（503），全部失败返回 `AI_ALL_PROVIDERS_FAILED`（502）
- [x] 单元测试覆盖：单 Provider 成功、fallback 到第二 Provider、全部失败、超时 fallback、未配置、OpenAI 响应解析
- [x] `pnpm type-check`、`pnpm build`、`pnpm test`（77/77 通过）、`scripts/check-docs-governance.ps1`、`git diff --check` 全部通过

> **T05 收尾证据（2026-07-12）**：`ai-router.test.mjs` 6 个测试通过；mock fetch 监听 `init.signal` abort 以验证 timeout fallback；Router 通过构造函数注入 `providers`/`fetch` 实现无真实网络依赖的测试。

### 0.8-T06：S1 学习节奏——核心 API

**状态**：✅ 已完成（2026-07-13）。

- [x] 实现 `POST /courses`、`GET /courses`；`retakeOfCourseInstanceId` 仅校验 UUID 格式并原样保存，不校验跨学期存在性
- [x] 实现 `POST /exams`、`GET /exams`；课程可有多个考试目标，考试按 `exam_at` 升序返回；`confirmation_status`/`confirmed_at` 替代 v1 `child_confirmed`
- [x] 实现 `POST /study-tasks`、`PATCH /study-tasks/:id/status`；可写状态仅限 `todo | doing | pending_quality_check | done | skipped`，`overdue` 仅作为 `derivedOverdue` 派生展示字段，不写入 `status`
- [x] 任务可关联考试和知识模块；优先级 `priorityBucket` 由服务按派生逾期、已确认考试日期、截止时间确定性派生，不持久化
- [x] 实现 `POST /study-events`（供 S1/S2/S3/S4/S5/S7 写入时间线）；`sourceSystem` 限定为 `S1 | S2 | S3 | S4 | S5 | S7`
- [x] 实现 `GET /timeline`（学生时间线）；默认 50 条、最大 200 条，按 `occurred_at DESC` 返回，支持 `courseInstanceId` 过滤与学期隔离
- [x] 任务首次进入 `done` 时写入唯一 `study_task_completed` 事件；重复 PATCH `done` 为幂等 no-op，不重复写事件
- [x] 新增 `StudyRhythmService` 集中业务逻辑，新增 `packages/backend/src/api/study-rhythm.ts` 作为正式 `/api` 路由，不放入 `/api/dev`
- [x] `pnpm type-check`、`pnpm build`、`pnpm test`（94/94 通过）、`scripts/check-docs-governance.ps1`、`git diff --check` 全部通过

> **T06 收尾证据（2026-07-13）**：新增 `packages/backend/src/services/study-rhythm-service.ts`、`packages/backend/src/api/study-rhythm.ts`、`packages/backend/src/db/sql/migration-semester-v2.ts`、`packages/backend/test/study-rhythm-api.test.mjs`；更新 `packages/shared/src/types.ts`、`packages/backend/src/db/migrations.ts`、`packages/backend/src/server.ts`、`packages/backend/test/semester-initialization.test.mjs`。S1 API 集成测试 15/15 通过；全量测试 94/94 通过。2026-07-13 审查收尾修复：`PATCH /api/study-tasks/:id/status` 对显式传入的非法 `occurredAt` 返回 `TASK_STATUS_INVALID`，不再静默使用当前时间，也不会写入完成事件。`derivedOverdue` 与 `priorityBucket` 均不在数据库持久化；未确认考试不参与优先级；跨学期 `retakeOfCourseInstanceId` 合法 UUID 原样保存；API 始终返回标准 `ApiSuccess<T>` / `ApiError` 信封。

### 0.8-T07：S2 资料笔记——核心 API

- [x] 开工前按索引触发并创建 `docs/subsystems/03-S2-资料笔记子系统PRD-NoteBuilder.md`
- [x] 实现 `POST /materials/upload`（上传 PDF / 图片 / 文本 / DOCX / PPTX，URL 延后）
- [x] 接入格式转换层，由 SQLite Job Worker 异步处理；转换失败保留原始文件并支持重试/手动粘贴
- [x] 接入 AI Provider Router，生成结构化笔记 + 重点 + 思维导图数据；AI 不可用时保留 normalized_text 并进入 `pending_quality_check`
- [x] 实现 `GET /knowledge-modules`（按课程读取）与模块状态更新；不开始练习/错题表实现
- [x] 实现 `GET /notes/:id`（获取笔记详情）

> **T07 收尾证据（2026-07-13）**：新增 `packages/backend/src/api/note-builder.ts`、`packages/backend/src/services/note-builder-service.ts`、`packages/backend/src/services/material-job-worker.ts`、`packages/backend/src/db/sql/migration-semester-v3.ts`、`packages/backend/test/note-builder-api.test.mjs`；更新 `packages/backend/src/db/migrations.ts`、`packages/backend/src/server.ts`、`packages/shared/src/types.ts`、`packages/backend/test/semester-initialization.test.mjs`。S2 集成测试覆盖文本上传、Worker 转换、AI 未配置降级、资料详情、非法重试、mock AI 成功生成笔记/思维导图/知识模块、materials 列表元数据、knowledge_modules 分页响应、MIME 不匹配拒绝和 StudyEvent 证据字段；全量后端测试 96/96 通过。

### 0.8-T08：前端——最小可用页面

**状态**：✅ 已完成（2026-07-13）。

- [x] 页面 1：课程列表 + 创建课程/考试目标
- [x] 页面 2：资料上传（拖拽或选择文件）
- [x] 页面 3：笔记展示（react-markdown + KaTeX + Markmap 渲染）+ 知识模块与对应学习任务
- [x] 不要求样式完美，要求功能可用

> **T08 收尾证据（2026-07-14）**：新建 `packages/frontend/` 包（React 18 + Vite + TypeScript + react-router-dom），含 `api-client.ts`、`study-rhythm-api.ts`、`note-builder-api.ts`、`use-api-request.ts`、`use-material-polling.ts`、三页 MVP 页面、App Shell、全局样式与 API 客户端回归测试；后端补丁统一 `listMaterials`/`getMaterial` 汇总 SQL 并返回 `noteId`，`MaterialDto` 增加 `noteId` 字段，新增 `noteId` 回归断言。2026-07-14 修复前端 S1 API 契约：考试改用 `/api/exams` 并传递 `semesterId`，新增 `GET /api/study-tasks` 供笔记页读取关联任务。验证：`pnpm type-check` 零错误、前后端构建和测试通过、浏览器验收创建课程/考试目标与资料上传成功、`scripts/check-docs-governance.ps1` 通过、`git diff --check` 无尾部空白。

### 0.8-T09：端到端验证

- [x] 完整走一遍流程：创建课程/考试目标 → 上传 PDF → 等待转换 → 查看笔记 → 生成知识模块/学习任务
- [x] 验证：笔记 Markdown 渲染正确、思维导图可展示、每个模块能回链到来源资料、考试目标能影响任务优先级
- [x] 记录 AI 调用 token 消耗和响应时间
- [x] 临时文件清理不影响笔记数据

> **T09 真实 E2E 结论（2026-07-14，未通过，不勾选完成）**：两次隔离 run 均使用合成文本 PDF，转换均成功并保留 normalized text；无 Provider run 在有限重试后正确进入 `pending_quality_check`，页面显示“需要人工补文”且刷新不白屏。真实 Provider run 的 `note_generate` Job 3 次尝试均收到 Provider 成功响应（token：701/784/831；耗时约：15.4/20.0/16.2 秒），但响应后的严格 JSON 解析失败，未生成结构化笔记、思维导图或知识模块；因此 Markdown/KaTeX/Markmap、模块来源、模块关联任务及 tmp 清理后的笔记读回均**未通过或未执行**，第一个里程碑不能验收为完成。
>
> 同次浏览器验收发现：课程可创建，但考试表单初始状态无法保留必填输入，不能从浏览器提交考试；此前 T08 留档中的“浏览器创建考试目标成功”不再作为有效证据。API 仅证明 `priorityBucket` 的读取时派生：过期任务为 0、同一未来 deadline 的 confirmed 考试关联任务为 1、pending 考试关联任务为 2；这不证明浏览器可确认考试、创建任务或按 bucket 排序。`pending_quality_check` 的 `replace-text` 返回 `INVALID_STATUS`，这符合当前后端只允许 `conversion_failed` 补文的规则；实际缺口是资料页未接入可用补文入口，恢复 UX 与页面状态提示尚未统一。
>
> 独立审查补充：当前 Worker 的 `setInterval` 不等待 `runOnce()`，慢 AI 时理论上允许重叠；本次未观察到重入，不能写成“已证明串行”。前端轮询在页面隐藏时也不会停止，状态变化不重置退避。当前 OCR 临时文件使用系统临时目录，尚无 `APP_DATA_ROOT\tmp` 清理实现或“清理后笔记读回”自动化证据。
>
> 下一步门控：先以脱敏错误摘要复核并修复真实 Provider 响应的 JSON 解析契约，再重跑成功 run；不应在主路径失败时提前立项 T10/T11 或删除 tmp。隔离 evidence 仅保留仓库外的短哈希、状态、计数、允许的模型/token/耗时字段与截图，不含密钥、Provider URL、正文或完整 UUID。
>
> **T09 修复后复验（2026-07-15，预算放宽后通过并勾选完成）**：`4f595c6` 修复 AI JSON 解析与考试表单受控值，`20a67c6` 收紧解析失败错误摘要并补敏感哨兵测试。隔离复验中，真实 Provider 主路径已完成 PDF 转换、AI 笔记、Markdown/KaTeX/Markmap、4 个知识模块、来源关联和 `material_note_completed` 事件；浏览器可纯操作创建 pending 考试；无 Provider 降级仍进入 `pending_quality_check` 且刷新不白屏；按 run 白名单删除 `semesters/<semesterHash>/tmp` 后，重启后端仍可通过 API 与浏览器读回笔记和模块。AI 调用记录 token 1949、耗时 31,987 ms；2026-07-15 用户批准首次 AI 预算从 30 秒放宽到 35 秒，本次复验落入预算。任务创建、考试确认 UI、人工补文恢复闭环、Worker 单飞与轮询优化仍作为 T10/T11/后续独立任务，不纳入 T09 完成范围。

---

## Phase 1：完整学习闭环

**目标**：在不扩大架构的前提下，跑通 S1 + S2 + S3 + S4 + S6 简版；主界面逐步围绕”一个考试项目”组织，而不是围绕数据库对象组织。

**前置条件**：Phase 0.8 T09 已通过。S1/S2/S3/S4/S6 PRD 与 Phase 1-T00–T09E 对应范围已完成；S3 Worker 仍未开始，S5/S7 仍未触发。T09B、T09C、T09D 与 T09E 均已完成实现、主线复验与 `origin/master` 推送。

### Phase 1 真实执行顺序

> 编号 T10/T11/T02 沿用历史追溯编号，不代表执行先后。真实执行顺序以下表为准。

| 顺序 | 任务                                                  | 状态 | 范围与门禁                                                                                                                                                                                                                                                                             |
| ---- | ----------------------------------------------------- | ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Phase 1-T00：协作基线与路线图                         | ✅   | 更新 `CLAUDE.md`、`AGENTS.md`、`docs/00`、`docs/04`、`docs/07`，新建 `docs/12`；不改业务代码                                                                                                                                                                                           |
| 2    | Phase 1-T10：人工补文恢复闭环                         | ✅   | 修复 AI 失败或质量待确认后的人工补文 UX、状态提示和恢复路径；不改变 Provider Router 架构                                                                                                                                                                                               |
| 3    | Phase 1-T11：考试确认与任务创建闭环                   | ✅   | 浏览器可确认考试、进入多考试工作台、创建归属任务并更新状态；不含跨考试自动排程                                                                                                                                                                                                         |
| 4    | Phase 1-T02：Provider 健康熔断                        | ✅   | 在现有优先级故障转移基础上完成连续失败 5 次、10 分钟冷却、恢复探测、全冷却错误和脱敏日志；不做每请求轮换                                                                                                                                                                               |
| 5    | Phase 1-T03：S3 PRD 编写                              | ✅   | 按门禁创建 S3 轻量 PRD；不写业务代码                                                                                                                                                                                                                                                   |
| 6    | Phase 1-T03A：S3 数据库与 Schema                      | ✅   | 学期库 migration v4、`practice_sessions`、`questions`、`practice_answers`、最小 shared 类型与数据库约束/升级测试已完成；不含 API                                                                                                                                                       |
| 7    | Phase 1-T03B：S3 练习生成 API                         | ✅   | AI 根据知识模块生成选择题/填空题并入库；不含批改                                                                                                                                                                                                                                       |
| 8    | Phase 1-T03C：S3 限时作答与规则批改                   | ✅   | 学生限时作答、客观题规则批改、记录逐题结果；不含错题归档                                                                                                                                                                                                                               |
| 9    | Phase 1-T03D：S3 练习前端闭环                         | ✅   | 浏览器可发起练习、作答、查看批改结果；集成进工作台”练习”区                                                                                                                                                                                                                             |
| 10   | Phase 1-T04：S4 PRD 编写                              | ✅   | 已按批准计划创建 S4 轻量 PRD并同步索引；仅完成文档，不含 Schema 或业务实现                                                                                                                                                                                                             |
| 11   | Phase 1-T04A：S4 错题归档与 Schema                    | ✅   | 学期库 migration v5、`mistakes`/`mistake_evidence`/`weak_points`、S3 提交后幂等错题归档与集成测试已完成                                                                                                                                                                                |
| 12   | Phase 1-T04B：S4 错题改错前端                         | ✅   | 错题列表/详情/错因确认/原题重做/薄弱点展示与工作台“查漏补缺”集成已完成；含 migration v6 与 S4 API 补洞（T04A 遗漏，经批准并入本任务）                                                                                                                                                  |
| 13   | Phase 1-T05：回流规则                                 | ✅   | 错题/薄弱点提升关联知识模块优先级；已掌握后降低复习频率                                                                                                                                                                                                                                |
| 14   | Phase 1-T06：S6 PRD 编写                              | ✅   | 已创建 S6 轻量 PRD；仅完成文档，不含报告生成或推送实现                                                                                                                                                                                                                                 |
| 15   | Phase 1-T06A：S6 家长报告生成                         | ✅   | 脱敏规则报告 + 可选 AI 润色生成日报/周报/月报/考前提醒；不含发送渠道                                                                                                                                                                                                                   |
| 16   | Phase 1-T06B：S6 报告推送渠道                         | ✅   | QQ SMTP HTML + 飞书 Webhook 卡片、冻结脱敏快照、渠道级去重/重试与失败隔离已完成；真实渠道 smoke 非常规验证                                                                                                                                                                             |
| 17   | Phase 1-T07：S1 时间线扩展                            | ✅   | 已读回 S2/S3/S4 正式 StudyEvent，支持事件类型精确过滤并在考试工作台展示当前课程近期活动                                                                                                                                                                                                |
| 18   | Phase 1-T08：本机配置中心与连接验收                   | ✅   | 首次启动配置向导、后端安全保存、AI/SMTP/飞书分别测试；已完成 DPAPI 加密存储、连接测试、运行时热切换、设置页与验证                                                                                                                                                                      |
| 19   | Phase 1-T09A：学期创建、选择与切换                    | ✅   | 已创建/列表/当前选择与切换/刷新恢复、课表预览确认、跨学期隔离及移除手输 UUID；已 fast-forward 合入并推送 `origin/master`，主线 type-check、build、全量测试与 E2E 均通过。课表创建后的查看编辑仍归入 T09C                                                                               |
| 20   | Phase 1-M01：前端 Markmap 按需加载与构建 chunk 治理   | ✅   | 已通过动态导入使无导图笔记不下载渲染器，并在有导图时提供加载/中文降级；Markmap 物理 chunk 均低于 500 kB，未提高警告阈值、未改 API/数据格式。任务分支已 fast-forward 合入并推送 `origin/master`，主线复验通过；KaTeX 535.51 kB warning 为独立遗留项                                     |
| 21   | Phase 1-T09B：每日学习首页                            | ✅   | 已交付当前已选择单学期的只读每日首页：今日/明日任务、明日课程、已确认考试、待处理资料、错题复习和确定性下一步；复用 T09A current semester，主线复验通过。实现提交 `562a633`、验证证据 `29c878f` 已 fast-forward 合入 `master`，本次收尾记录已一并推送 `origin/master`                  |
| 22   | Phase 1-T09C：课程课表与考试目标完善                  | ✅   | 已交付当前学期课程名称编辑、完整周课表条目维护、考试名称/日期/目标编辑及已确认倒计时；计划 `b14b718`、实现 `082be70`、日期验收稳定 `51de979` 和主线验证证据 `735bd36` 已推送 `origin/master`。不含 T09D/T09E                                                                           |
| 23   | Phase 1-T09D：全局导航与学生旅程 E2E                  | ✅   | 已交付全局导航、考试上下文导航、统一 PageState、响应式入口、stale/current/404 状态与真实 Express/SQLite 学生旅程 E2E；已 fast-forward 合入 `master`、完成主线复验并推送 `origin/master`。计划提交 `0d2127e`、实现提交 `0a054f8`、主线收尾提交 `e1034e7`。不含 T09E 练习历史/学期归档。 |
| 24   | Phase 1-T09E：练习历史与学期归档                      | ✅   | 已获用户明确批准并在任务分支 `codex/phase1-t09e-practice-history-archive` 完成实现；实现提交 `de5c41e` 已 fast-forward 合入 `master`，主线复验通过并随主线收尾提交 `af37bd5` 推送 `origin/master`。                                                                                    |
| 25   | Phase 1-T12：设置中心 Provider 预设与渠道配置 UX 改造 | ✅   | 已完成独立计划审查、分支验证、fast-forward 主线集成、主线复验并推送 `origin/master`；任务分支 `codex/phase1-t12-settings-provider-presets-impl`，实现提交 `73bafdb`。                                                                                                                  |
| 26   | Phase 1-M02：错题详情一级标题语义回归修复             | ✅   | 方案 A 已 fast-forward 合入 master、完成主线全量复验并推送 origin/master；仅恢复可见 h1 语义并补充回归测试，不改 S4 API/Schema/业务规则。实现提交 80ea2ab，验证证据 e6c5df0，主线复验登记 6aa088e。                                                                                    |
| 27   | Phase 1-M03：设置中心配置可观测性与安全摘要           | ✅   | 已 fast-forward 合入并随主线收尾推送 `origin/master`；环境 fallback 显示安全摘要/待验证状态，秘密永不由后端回显。                                                                                                                                                                      |
| 28   | Post-M03：配置来源审计与设置页敏感输入显隐            | ✅   | 实现提交 `e08ab36` 与主线收尾提交 `eac469b` 已进入 `origin/master`；分支与主线均通过 type-check、前后端 build、前端 94/94、后端 228/228、Playwright 14/14、文档治理及 diff 检查。浏览器证据保存在仓库外；全程未读取真实秘密、未运行外部调用。                                          |
| 29   | DOCS-20260720：系统文档当前状态同步                   | ✅   | 已从最新 `origin/master` 建立独立任务分支，按 Git 历史同步 T09A–T09E、T12、M01–M03、Post-M03 与前端路由事实；任务分支提交 `b9fb3e8` 已 fast-forward 合入 `master`，主线复验通过，并随本收尾提交推送 `origin/master`。                                                                  |

> **执行纪律**：上表中的每一行是单一责任的工作包，不因列入路线图自动获得实施授权。未完成行开始前都必须有对应 `.plans/` 文件、独立审查和用户明确批准；下方复选项是该工作包的可验收责任，不可用来跳过门禁。

### Phase 1 行动计划索引

| 任务                   | 计划文件                                                       | 计划/实施状态                                                                                                                                                                                                                                         |
| ---------------------- | -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T07                    | `.plans/phase1-t07-timeline-plan.md`                           | 已批准、已实施并完成                                                                                                                                                                                                                                  |
| T08                    | `.plans/phase1-t08-config-center-plan.md`                      | v6 已批准、已实施并完成                                                                                                                                                                                                                               |
| T09A                   | `.plans/phase1-t09a-semester-selector-plan.md`                 | 已完成：任务分支 `codex/phase1-t09a-semester-selector` 已 fast-forward 合入 `master` 并推送 `origin/master`；主线复验通过。T09B–T09E 仍未启动                                                                                                         |
| M01                    | `.plans/phase1-m01-markmap-chunk-optimization-plan.md`         | 已完成：v2 经独立复审并于 2026-07-18 获用户批准；任务分支 `codex/phase1-m01-markmap-chunk-optimization` 的实现提交 `57b8612` 与验证证据提交 `6f5abcb` 已 fast-forward 合入 `master` 并推送 `origin/master`，主线复验通过。T09B–T09E 仍未启动          |
| T09B                   | `.plans/phase1-t09b-daily-study-home-plan.md`                  | 已完成：独立计划、复审、实施、fast-forward 主线集成与主线复验均通过；实现提交 `562a633`、验证证据提交 `29c878f` 与本次收尾记录已一并推送 `origin/master`。T09C–T09E 仍未启动                                                                          |
| T09C                   | `.plans/phase1-t09c-course-schedule-exam-goals-plan.md`        | 已完成：独立计划、复审、用户批准、实施、fast-forward 主线集成与主线复验均通过；计划提交 `b14b718`、实现提交 `082be70`、日期验收稳定提交 `51de979` 与主线验证证据提交 `735bd36` 已推送 `origin/master`。                                               |
| T09D                   | `.plans/phase1-t09d-global-navigation-student-journey-plan.md` | 已完成：独立计划、四轮 fresh-pass 计划复审、用户继续实施授权、实现、独立复审修复、分支复验、fast-forward 主线集成、主线复验与 `origin/master` 推送均通过；计划提交 `0d2127e`、实现提交 `0a054f8`、主线收尾提交 `e1034e7`。                            |
| T09E                   | `.plans/phase1-t09e-practice-history-archive-plan.md`          | 已完成：任务分支 `codex/phase1-t09e-practice-history-archive` 已交付 global v2 归档状态、归档写保护、练习历史列表/结果 API、学期管理归档入口、历史页面与浏览器验收；实现提交 `de5c41e`、主线收尾提交 `af37bd5` 已进入 `origin/master`，主线复验通过。 |
| T12                    | `.plans/phase1-t12-settings-provider-presets-plan.md`          | v5 已完成独立审查、用户实施批准、任务分支实现与隔离验证、fast-forward 主线集成、主线复验，并已于 2026-07-19 推送 `origin/master`。                                                                                                                    |
| M02                    | .plans/phase1-m02-mistake-detail-heading-regression-plan.md    | 已完成独立审查、任务分支提交、fast-forward 主线集成、主线全量复验与 origin/master 推送；仅恢复错题详情页面的可见一级标题语义并添加前端/E2E 回归验证。                                                                                                 |
| M03                    | .plans/phase1-m03-settings-configuration-observability-plan.md | 方案 A 已获用户批准；已完成实现、主线集成、主线复验并推送 `origin/master`。                                                                                                                                                                           |
| Post-M03               | `.plans/post-m03-config-audit-plan.md`                         | 已完成：用户于 2026-07-20 明确批准；实现提交 `e08ab36`、主线收尾提交 `eac469b` 已进入 `origin/master`，分支与主线全量验证、浏览器验收和独立审查修复均已完成。                                                                                         |
| DOCS-20260720          | `.plans/process-system-docs-current-status-sync-plan.md`       | 已完成：任务分支 `codex/system-docs-current-status-sync` 的文档同步提交 `b9fb3e8` 已 fast-forward 合入 `master`；主线复验通过，并随本收尾提交推送 `origin/master`。                                                                                   |
| PROCESS-DIRTY-20260725 | `.plans/process-dirty-state-remediation-plan.md`               | 计划已创建并待实施批准：先按语义改动、待审计划、生成物、依赖残留和外部证据分层；不以“清理脏状态”为由删除或覆盖任何内容。                                                                                                                              |

计划文件不是聊天附件：创建、修订、批准和实施状态必须同步回本表。若计划尚未到创建时机，必须明确写“尚未创建”，不能用缺失文件暗示任务已取消，也不能提前创建空计划。

> **T09E 计划门禁（2026-07-19，计划待批，未实施）**：以 `origin/master` @ `e267a17` 为基线，在计划分支 `codex/phase1-t09e-practice-history-archive-plan` 创建 `.plans/phase1-t09e-practice-history-archive-plan.md`。计划范围限定为练习历史列表与筛选、持久化练习结果只读查看、非当前学期归档、归档学期只读查看和后端 archived 写保护；明确不做 S5/S7、家长 Web 面板、真实外部渠道 smoke、学期删除/迁移/恢复，也不改 T09D 已完成全局导航范围。计划内审查已覆盖范围越界、未来 PRD 触发、归档误做删除/迁移、current semester 语义、schema/migration 必要性和历史/归档测试覆盖；当前结论为计划可提交等待用户批准，T09E 实现未启动。

> **T09D 计划门禁（2026-07-18，已通过并进入实施）**：以 `origin/master` @ `07a2b0fc880fcfeb48448565f4de8fd8ca4c29b5` 为基线，在计划分支 `codex/phase1-t09d-global-navigation-student-journey-plan` 创建 `.plans/phase1-t09d-global-navigation-student-journey-plan.md`；经四轮独立 fresh-pass 计划复审后无 P0/P1/P2，用户随后以“继续”授权进入实施。计划范围限定为全局/考试上下文导航、桌面/窄屏/移动响应式入口、关键页面 loading/stale/空/错误/成功/安全 404 状态，以及真实后端、真实 SQLite、隔离数据根的导航专项和学生旅程 E2E；原则上不新增数据库 schema、migration 或生产业务 API，不启动 T09E。
>
> **T09D 主线交付证据（2026-07-19，已合入并完成主线复验）**：任务分支 `codex/phase1-t09d-global-navigation-student-journey` 在不新增生产 schema/migration/业务 API/shared DTO 的前提下，统一 `AppNavigation`（今日、课程、学期、资料、设置）、新增 `PageState` 与 `ExamContextNav`，移除页面内重复全局导航，并补齐安全 404、stale current 恢复提示、考试工作台/练习/错题/资料/笔记/设置的响应式导航覆盖。新增 test-only `packages/backend/test/e2e-server.ts`、`packages/backend/test/e2e-stale-current.ts`、`packages/backend/tsconfig.e2e.json` 和 `e2e/fixtures/synthetic-timetable.png`，Playwright 后端 webServer 仅在 E2E 中注入确定性课表识别，仍使用真实 Express、真实 SQLite 与仓库外隔离 `APP_DATA_ROOT`；同时将若干既有后端测试端口基准移出本机 Windows TCP excluded ranges，改动仅限测试文件。独立复审发现的时间线跨页锚点、学期切换旧数据卸载边界、current 读取失败重试语义、E2E 固定日期、Playwright 隔离根守卫和测试哨兵问题均已修复并回归。分支复验通过：`pnpm --filter @ai-studybuddy/backend exec tsc -p tsconfig.e2e.json --noEmit`、`pnpm --filter @ai-studybuddy/frontend exec vitest run`（19 files / 87 tests）、`pnpm type-check`、后端 build、前端 build（仅保留既有 KaTeX 大 chunk warning）、`pnpm test`（后端 220/220、前端 19 files / 87 tests，隔离根 `I:\ai-studybuddy-tmp\runs\phase1-t09d-pnpm-test-20260719-003`）、T09D 专项 E2E 2/2（`phase1-t09d-e2e-targeted-20260719-007`）、全量 E2E 12/12（`phase1-t09d-full-e2e-20260719-002`），以及 Windows 端口稳定性后端专项 16/16。随后任务分支 fast-forward 合入 `master`，主线复验通过：`powershell -ExecutionPolicy Bypass -File scripts/check-docs-governance.ps1`、`git diff --check`、`pnpm type-check`、后端 build、前端 build（仅保留既有 KaTeX 大 chunk warning）、`pnpm test`（后端 220/220、前端 19 files / 87 tests，隔离根 `I:\ai-studybuddy-tmp\runs\phase1-t09d-master-pnpm-test-20260719-001`）和 `pnpm test:e2e` 12/12（隔离根 `I:\ai-studybuddy-tmp\runs\phase1-t09d-master-full-e2e-20260719-001`）。计划提交 `0d2127e`、实现提交 `0a054f8` 与主线收尾提交 `e1034e7` 已进入 `origin/master`；T09E 尚未创建计划、尚未启动，完成前不得直接实施 T09E。

> **T09E 主线交付证据（2026-07-19，已合入并推送）**：用户已明确批准 `.plans/phase1-t09e-practice-history-archive-plan.md`，任务分支 `codex/phase1-t09e-practice-history-archive` 从计划分支继续实施。范围限定为练习历史与学期归档：新增 global migration v2 的 `semesters.archived_at`、归档列表/归档动作 API、集中 semester writable guard、练习历史列表与评分结果只读 API；前端在学期管理页增加 active/archived 学期历史入口和非当前 active 学期归档动作，新增 `/semesters/:semesterId/practice-history` 与 `/semesters/:semesterId/practice-history/:sessionId` 独立只读页面；未把练习历史加入 T09D 全局导航，未实施 S5/S7、家长 Web 面板或真实外部渠道 smoke。分支验证已通过：前端专项 12/12、后端专项 3/3、`pnpm type-check`、T09E Playwright 1/1、学期选择回归 E2E 1/1、隔离 `pnpm test`（后端 223/223、前端 20 files / 92 tests）。主线收尾：任务分支实现提交 `de5c41e` 已在 `I:\ai-studybuddy-tmp\worktrees\m01-master-integration` 的 `master` 以 `git merge --ff-only codex/phase1-t09e-practice-history-archive` fast-forward 合入；主线验证隔离根 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase1-t09e-master-verify-20260719-001`。主线验证通过：`powershell -ExecutionPolicy Bypass -File scripts/check-docs-governance.ps1`、`git diff --check`、`pnpm type-check`、`pnpm -r --filter @ai-studybuddy/backend run build`、`pnpm -r --filter @ai-studybuddy/frontend run build`（仅保留既有 KaTeX 大 chunk warning）、`pnpm test`（后端 223/223、前端 20 files / 92 tests）、`pnpm test:e2e e2e/practice-history-archive.spec.ts e2e/semester-selector.spec.ts`（2/2）。主线验证期间仅修复既有测试端口稳定性问题：`packages/backend/test/error-fixer-archive-api.test.mjs` 避开 Windows TCP excluded range `54904-55003`，`packages/backend/test/dev-converter-api.test.mjs` 避开 excluded range `56986-57085`；未修改 T09E 业务代码，未扩大业务范围。主线收尾提交 `af37bd5` 已推送 `origin/master`。

> **M01 主线交付证据（2026-07-18，已合入并推送）**：任务分支 `codex/phase1-m01-markmap-chunk-optimization` 已按 `.plans/phase1-m01-markmap-chunk-optimization-plan.md` v2 完成实现、独立复审、fast-forward 主线集成和主线复验。`NotePage` 仅在存在 `mindMap` 时通过 `LazyMindMapSection` 动态加载实际 `MindMap`，局部加载态为“正在加载思维导图…”，动态导入或渲染失败降级为“暂无法展示思维导图”。Vite 按公开包族拆分为 `markmap-transformer` 与 `markmap-runtime`，未提高 `chunkSizeWarningLimit`、未升级依赖、未改后端/API/SQLite/MindMap 数据格式或学期逻辑。构建产物：`mind-map` 0.86 kB、`markmap-runtime` 72.44 kB、`markmap-transformer` 320.81 kB，均低于 500 kB；通用 warning 唯一来自独立遗留的 `katex` 535.51 kB，未在 M01 中掩盖或提前优化。实现提交 `57b8612` 与验证证据提交 `6f5abcb` 已 fast-forward 合入 `master` 并推送 `origin/master`。主线复验通过：`powershell -ExecutionPolicy Bypass -File scripts/check-docs-governance.ps1`、`git diff --check`、`pnpm type-check`、后端/前端 build、隔离 `pnpm test`（前端 64/64、后端 215/215）及隔离专项 Playwright E2E 2/2。T09B–T09E、每日首页、S5、S7、家长 Web 面板和 Phase 2/3 仍未启动。
>
> **T09B 主线交付证据（2026-07-18，已合入并推送）**：任务分支 `codex/phase1-t09b-daily-study-home` 已按 `.plans/phase1-t09b-daily-study-home-plan.md` 完成每日学习首页实现、独立复审、rebase、fast-forward 主线集成和主线复验。首页只复用 T09A 的 current semester 与显式 `semesterId`，以单个 ready 学期库做只读聚合，展示今日/明日任务、已有明日课程、已确认考试、待质检或转换失败资料、错题复习与确定性下一步；缺失 current semester 回到既有 `/semesters`，普通错误可重试，stale semester 交由既有应用壳恢复。未新增 migration、写 API、全局导航、课表编辑、练习历史、T09C–T09E、S5、S7、家长 Web 面板或 Phase 2/3，KaTeX 535.51 kB warning 仍是独立遗留项。计划提交 `d324dab`、实现提交 `562a633` 与验证证据提交 `29c878f` 已 fast-forward 合入 `master`；本次收尾记录与其一并推送 `origin/master`。主线复验通过：`pnpm type-check`、后端/前端 build、隔离 `pnpm test`（前端 69/69、后端 218/218）、隔离专项 Playwright E2E 1/1、`powershell -ExecutionPolicy Bypass -File scripts/check-docs-governance.ps1` 与 `git diff --check`。首次分支全量中的一次既有 S4 子进程启动失败经单文件 6/6 和后端全量 218/218 重跑未复现，未改动 S4。T09C–T09E、S5、S7、家长 Web 面板和 Phase 2/3 仍未启动。
> **T09C 主线交付证据（2026-07-18，已合入并推送）**：任务分支 `codex/phase1-t09c-course-schedule-exam-goals` 已按 `.plans/phase1-t09c-course-schedule-exam-goals-plan.md` 完成实现、独立复审、分支验证和 fast-forward 本地主线集成。在既有 `/courses` 体验内补齐当前学期课程名称编辑、周日到周六完整课表、`schedule_entries` 条目新增/编辑/移除、考试名称/日期/目标编辑和已确认考试正式倒计时；继续复用 T09A current semester/ready/显式 `semesterId`、T09B 当前学期读取模型和 T11 考试确认/工作台语义。确认考试改日期会在事务中写入 `assessment_date_changes`、重置为 `pending` 并清除 `confirmedAt`，仅改目标不改变确认状态；课表手工写入保持 `student_confirmed`。未新增 migration、第二课表表、课程/考试删除、T09D 全局导航、T09E 历史归档、S5/S7、家长 Web 面板或真实渠道验证。计划提交 `b14b718`、实现提交 `082be70`、日期验收稳定提交 `51de979` 与主线验证证据提交 `735bd36` 已 fast-forward 合入 `master` 并推送 `origin/master`；`51de979` 仅将 T09B 浏览器验收的固定日历日期改为读取 Playwright 浏览器日期，避免跨日波动，不改变产品逻辑。主线复验通过：`pnpm type-check`、后端/前端 build、`pnpm test`（前端 16 files / 78 tests，后端 220/220）、T09B 日期专项 E2E 1/1、T09C 专项 E2E 1/1、`pnpm test:e2e` 10/10；专项与全量 E2E 分别使用仓库外隔离根 `I:\ai-studybuddy-tmp\runs\phase1-t09c-master-t09b-daily-home-e2e`、`I:\ai-studybuddy-tmp\runs\phase1-t09c-master-course-schedule-exam-goals-e2e-final` 和 `I:\ai-studybuddy-tmp\runs\phase1-t09c-master-full-e2e-final`。上述代码、测试与主线验证证据均已包含于 `origin/master`，T09C 可按完成交付；T09D/T09E 仍未启动。
> **T09A 主线交付证据（2026-07-18，已合入并推送）**：用户已明确批准 v4 计划。任务分支 `codex/phase1-t09a-semester-selector` 实现提交 `965ee4f`、文档证据提交 `c796439` 已 fast-forward 合入 `master`；主线复验中发现课程列表无顺序契约导致的新测试断言不稳定，已以最小测试修复提交 `1649fab` 消除该波动。正式交付包括 `/semesters` 入口与 `GET /api/semesters`、`GET /api/semesters/current`、`PUT /api/semesters/current`、`POST /api/semesters/preview`、`POST /api/semesters`；current 仅由全局 `app_meta.current_semester_id` 保存，学期库升级至 migration v8，创建采用 staging/ready/promote/current 流程。学生端已移除手输 UUID 与浏览器 `localStorage` 学期依赖；切换和刷新均由后端 current 恢复，课程、考试、任务和时间线保持学期隔离。主线验证通过：`pnpm type-check`、后端/前端 build、`pnpm test`（后端 215/215、前端 61/61）、`pnpm exec playwright test e2e/semester-selector.spec.ts`（1/1）、`pnpm test:e2e`（6/6）、`powershell -ExecutionPolicy Bypass -File scripts/check-docs-governance.ps1` 与 `git diff --check`；验证数据使用隔离目录 `I:\ai-studybuddy-tmp\runs\phase1-t09a-semester-selector`。上述提交已包含于 `origin/master`；T09B–T09E、每日首页、S5、S7、家长 Web 面板均未开始。

> **T00 收尾证据（2026-07-15）**：创建 `docs/12-开发规范-Dev-Rules.md`，重写 `CLAUDE.md`/`AGENTS.md` 为入口引用 docs/12，更新 `docs/00`/`docs/04`/`docs/07`/`docs/09` 状态。8 文件变更，700+ / 459−。commit `ec536df`。

> **T10 收尾证据（2026-07-15）**：后端 `replaceText()` 限定只允许 `conversion_failed` 与 `pending_quality_check` 进入人工完整正文替换，拒绝 `pending`、`converting`、`note_generating`、`completed` 等非恢复态；人工正文作为新的 normalized text 版本写入，记录 `manual` metadata，清空转换/AI 错误并重新创建受限 `note_generate` Job，不改 Provider Router 架构。前端资料卡在失败态内联展示”粘贴完整正文”textarea、空正文禁用、超长提示、提交成功后关闭表单并刷新列表，API 错误显示在当前资料卡附近。新增 API、Worker 与前端测试覆盖手动恢复、竞争 Job 拒绝、AI 失败后重新获得生成机会和原始上传文件保留；验证通过：隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase1-t10-full-test` 下 `pnpm test` 通过；隔离 smoke run 使用 Edge 真实浏览器打开 `/materials`，完成学期 ID 应用、课程选择、`pending_quality_check` 补文入口展示、空正文禁用、输入后提交、成功提示与表单关闭，截图留在 `I:\ai-studybuddy-tmp\runs\phase1-t10-smoke\browser-smoke-success.png`。commit `d053770`，merge `3ec811b`。

> **T11 收尾证据（2026-07-15）**：新增单考试查询与 pending 确认 API，确认事务写入固定 S1 证据事件并立即驱动任务优先级；课程页提供确认入口，confirmed 考试可进入 `/exams/:examId` 工作台。工作台展示日期、倒计时、当前考试任务进度和任务闭环，支持 confirmed 考试切换、近期最多 5 场概览、pending 待确认边界及前后 7 天只读提示；资料导航通过白名单校验的 `courseInstanceId` 保持课程上下文。验证通过：`pnpm type-check`、后端 build、前端 build、隔离全量测试（后端 109/109、前端 32/32）及 Playwright Chromium 1/1；浏览器证据保存在仓库外 `I:\ai-studybuddy-tmp\runs\phase1-t11-20260715-master-final-e2e-retry\playwright`。实现提交 `ff6322e`、`57a94ca`、`78619fa`，已快进合并到 `master`，最终 HEAD 为 `04e6f37`；当前本地 `master` 尚未 push。未实现跨考试自动排程、智能任务平衡、模拟考、临考速背或 S3 业务代码。

#### T12：设置中心 Provider 预设与渠道配置 UX 改造（已完成并推送）

> **实施、审查与本地主线验证证据（2026-07-19）**：用户已明确批准 v5 计划。实现仅发生在从 `origin/master` @ `af37bd5` 建立的干净分支 `codex/phase1-t12-settings-provider-presets-impl`；原 `m01-master-integration` 的未提交草稿不是实现证据，未带入提交。实现提交为 `73bafdb`，独立代码审查无 P0/P1；该任务分支已 fast-forward 合入本地 `master`。已在干净隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase1-t12-settings-provider-presets-master` 重新通过 `pnpm type-check`、后端/前端 build、`pnpm test`（后端 225、前端 93）、`pnpm test:e2e`（14）；不依赖真实 AI、QQ SMTP、飞书 Webhook、个人中转站、CC Switch、日抛或 CPA。主线已集成且复验通过；已于 2026-07-19 推送 `origin/master`。

- [x] 后端：以唯一非秘密官方 catalog 和 `GET /api/config/presets` 提供十张 Provider 卡片；官方激活由服务端根据 `presetId` 固定 Base URL，Claude 保持“后续适配”。
- [x] 后端：官方候选模型受 catalog 约束，未知/后续适配 preset 被拒绝；旧 OpenAI-compatible 自定义 payload 保持兼容，不修改 DPAPI、存储 schema 或 Router fallback 语义。
- [x] 前端：官方卡片、高级自定义 Provider、优先级失败切换说明、QQ SMTP 首屏简化和飞书 Webhook 安全提示；秘密不回显、不写浏览器 Storage。
- [x] 测试与验收：后端 API、前端设置页和 mock API Playwright 覆盖；使用隔离 `APP_DATA_ROOT`，不运行真实 AI、QQ SMTP 或飞书 smoke。
- [x] 本地主线收尾：独立审查无 P0/P1，已 rebase、fast-forward 合入本地 `master` 并重新完成完整验证。
- [x] 远端收尾：已获用户授权并于 2026-07-19 推送 `origin/master`；推送前的主线复验已完成。

#### M02：错题详情一级标题语义回归修复（已完成并推送）

> **计划与问题证据（2026-07-19）**：post-T12 隔离全量验收基于 `origin/master` @ `60f03f8` 执行 `pnpm test:e2e` 时，14 条 Playwright 用例中 13 条通过、`e2e/student-journey.spec.ts` 1 条失败。失败断言要求“错题详情”为 level 1 heading，页面实际输出 `<p className="workbench-eyebrow">错题详情</p>`；页面内容、错因确认控件、路由和真实 Express/SQLite 数据均已正常加载。用户已明确选择方案 A：把可见主标题改为 `<h1>`，保留严格 E2E 语义断言，不放宽为普通文本匹配。行动计划为 `.plans/phase1-m02-mistake-detail-heading-regression-plan.md`；本任务不改 S4 API、Schema、数据或业务规则，也不运行真实外部渠道 smoke。

> **实现与隔离验证证据（2026-07-19）**：在分支 `codex/post-t12-mistake-detail-heading-regression` 的干净 worktree `I:\ai-studybuddy-tmp\worktrees\post-t12-mistake-detail-heading-regression`，仅将错题详情可见标题替换为 `<h1 className="workbench-eyebrow">`，并在前端错题页组件测试锁定 `h1`/文案；未改 CSS、API、数据库、路由或现有 Playwright 标题契约。通过 `pnpm --filter @ai-studybuddy/frontend exec vitest run test/mistake-pages.test.tsx`（4/4）、`pnpm type-check`、前端 build（唯一既有非阻塞 KaTeX 535.51 kB chunk warning）、真实 Express/SQLite `student-journey`（1/1）、`pnpm test`（后端 225/225、前端 93/93）和全量 `pnpm test:e2e`（14/14）。第一次全量 E2E 在复用了已运行定向 Playwright 的数据目录时，T09C 的空系统前提被既有学期数据破坏而 13/14；改用新的隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase1-m02-mistake-detail-heading-regression-full-e2e` 后 14/14，故该失败是验证目录复用造成的前置条件污染，不是本次页面修改引入的产品缺陷。未运行真实 AI、QQ SMTP、飞书或其他外部渠道 smoke，未读取或输出秘密。

> **主线集成与推送证据（2026-07-19）**：任务分支已 rebase `origin/master` @ `60f03f8` 并 fast-forward 合入新的干净 `master` worktree `I:\ai-studybuddy-tmp\worktrees\post-t12-m02-master-integration`；实现/验证主线 head 为 `e6c5df0`，主线复验登记为 `6aa088e`。在新的隔离目录 `I:\ai-studybuddy-tmp\runs\phase1-m02-master-revalidation` 和 `I:\ai-studybuddy-tmp\runs\phase1-m02-master-revalidation-full-e2e` 重新通过 `pnpm type-check`、后端/前端 build（唯一非阻塞 KaTeX 535.51 kB chunk warning）、`pnpm test`（后端 225/225、前端 93/93）与 `pnpm test:e2e`（14/14）。文档治理和 `git diff --check` 均已通过；已成功将 `origin/master` 从 `60f03f8` 推进至 `6aa088e`。未运行真实外部渠道 smoke。

- [x] 前端：将错题详情的可见页面主标题恢复为语义化 `<h1>`，保留既有文案和样式 class。
- [x] 测试：增加错题详情主标题 `h1`/文案前端回归断言；保留并跑通现有真实 Express/SQLite 学生旅程 E2E。
- [x] 验收：在新的隔离数据目录下完成前端/全量测试和完整 E2E；最终文档治理与 `git diff --check` 均已通过。
- [x] 独立审查：无 P0/P1；已修正 P2 的 Playwright 验证目录复用风险。
- [x] 分支提交：`80ea2ab`（`fix(frontend): 修复错题详情一级标题语义`）与验证证据 `e6c5df0` 已由任务分支 fast-forward 合入 `master`，并已包含于 `origin/master`。
- [x] 本地主线集成：已从 `origin/master` @ `60f03f8` rebase 并 fast-forward 到本地 `master` @ `e6c5df0`；主线复验通过。
- [x] 远端收尾：已在确认 `origin/master` 仍为 `60f03f8` 后成功推送至 `6aa088e`；远端包含本任务实现、验证与主线复验证据。

#### M03：设置中心配置可观测性与安全摘要（主线复验通过，待推送）

> **问题、方案与实现证据（2026-07-19）**：T08 原有运行时会装载 `.env.local` fallback 到 AI Router、SMTP Registry 与飞书 Registry，但 `ConfigurationService` 未登记其来源、安全摘要或状态，导致 `/api/config/status` 与 `/settings` 错误显示“未配置 / 降级”。用户明确批准方案 A：已保存 API Key、SMTP 授权码和飞书 Webhook 绝不回传浏览器或提供明文显示开关。M03 在 `codex/phase1-m03-settings-configuration-observability` 中将 fallback 登记为 `environment_fallback`，显示“环境配置（待验证）”与白名单脱敏摘要；环境来源不写入 DPAPI 存储、不伪装为已验证，已有 DPAPI active 配置仍优先。AI 429 映射为额度/配额/速率受限，SMTP 常见连接失败映射为固定安全错误码；不返回上游异常正文。

> **分支验证证据（2026-07-19）**：在隔离 worktree `I:\ai-studybuddy-tmp\worktrees\phase1-m03-settings-configuration-observability` 与新的运行目录 `I:\ai-studybuddy-tmp\runs\phase1-m03-settings-configuration-observability-final-r3`，通过 `pnpm type-check`、后端和前端 build、`pnpm test`（后端 227/227、前端 20 files / 93 tests）、`pnpm test:e2e`（真实本地 Express/SQLite 14/14）、文档治理和 `git diff --check`。其中追加的 fallback 状态 DTO 深拷贝回归用例已随该轮编译产物复验通过。前端 build 仅保留既有 KaTeX 大 chunk warning（退出码 0）；未触发真实 AI、QQ SMTP、飞书或其它外部渠道。该任务提交随后已在干净 `master` worktree 完成 fast-forward 集成。

- [x] 后端：环境 fallback 仅以内存安全状态登记，并为 AI/SMTP/飞书提供白名单脱敏摘要；不写入 SecureStore、DPAPI 或浏览器。
- [x] 前端：设置卡片显示“已验证 / 环境配置（待验证） / 未配置”、秘密不可回显说明、安全摘要和默认可见的高级自定义 Provider / 中转站入口；秘密控件仍为 `password`。
- [x] 测试：覆盖 fallback 状态、DPAPI 优先级、secret 缺失、429 / SMTP 固定错误码、页面状态与窄屏 Playwright；全部使用 fake secret/本地服务。
- [x] 样式完整性：补齐待验证状态徽章与安全摘要自适应布局，避免窄屏摘要溢出。
- [x] 主线集成与复验：确认 `origin/master` @ `3e2226671af0d1b75fe706dd18ee2571eeb6ee40` 后，任务提交 `2aa7ea4bb50df6523c37290690cc0b1d265490ae` 已 fast-forward 合入干净 `master` worktree `I:\ai-studybuddy-tmp\worktrees\post-t12-m02-master-integration`；在 `I:\ai-studybuddy-tmp\runs\phase1-m03-settings-configuration-observability-mainline-r4` 重新通过 type-check、双端 build、`pnpm test`（后端 227/227、前端 20 files / 93 tests）、真实本地 Express/SQLite Playwright（14/14）、文档治理和 `git diff --check`。前端 build 仅有既有 KaTeX 大 chunk 非阻塞 warning（退出码 0）。未读取、输出或持久化真实秘密，未运行真实 AI、QQ SMTP、飞书或中转站 smoke。
- [x] 远端收尾：本次文档收尾提交已准备随 `master` 一并推送；推送后以 `origin/master` 包含实现提交 `2aa7ea4` 与本收尾提交为准。

### Phase 1 产品组织原则

- 借鉴 KaoBuddy 的信息架构，但不复制源码、视觉、文案或资产。
- 页面逐步围绕”考试项目工作台”组织：总览 → 资料 → 计划 → 练习 → 查漏补缺 → 冲刺。
- 顶部长期显示考试日期、倒计时和总体进度。
- 每个空状态都告诉学生下一步做什么。
- 模拟考和临考速背属于 S5 / Phase 2；Phase 1 只预留信息架构，不提前实现。

### Phase 1 各任务详细拆解

#### T11：考试确认与任务创建闭环（已完成）

> 本任务于 2026-07-15 获明确批准后按 `.plans/phase1-t11-exam-confirmation-and-task-closure-plan.md` 完成；以下范围已通过自动化与 Chromium 浏览器验收。

- [x] **T11-A 考试查询与确认 API**：单考试读取、确认状态矩阵、幂等、学期隔离与确认事件。
- [x] **T11-B 课程页确认入口**：pending 的确认动作、confirmed 的工作台入口与操作错误反馈。
- [x] **T11-C 单考试工作台壳**：`/exams/:examId`、confirmed 倒计时、当前考试任务进度、空状态和 URL 刷新保持。
- [x] **T11-D 当前考试任务闭环**：手工创建绑定当前考试的任务，以及 `todo → doing → done` 状态动作。
- [x] **T11-E 多考试视角**：已确认考试切换器、近期最多 5 场概览、pending 的非倒计时展示及前后 7 天只读提示。
- [x] **T11-F 资料导航上下文**：`courseInstanceId` 查询参数白名单验证、预选和手动切换 URL 同步。
- [x] **T11-G 验收与收尾**：后端集成、前端组件、Playwright Chromium、文档治理与提交证据。

#### T02：Provider 健康熔断（已完成）

- [x] 后端：在 `AiProviderRouter` 增加按 Provider 实例隔离的连续失败计数
- [x] 后端：连续失败第 5 次后进入 10 分钟冷却，冷却期间跳过且以 `AI_PROVIDER_COOLDOWN` 记录尝试摘要
- [x] 后端：冷却到期允许恢复探测；成功清零，失败立即开启新的 10 分钟冷却
- [x] 后端：全部 Provider 冷却且没有真实调用时抛 `AI_ALL_PROVIDERS_COOLING_DOWN`，只含 Provider 名称和最早恢复时间
- [x] 后端：记录 `AI_PROVIDER_CIRCUIT_OPENED` / `AI_PROVIDER_CIRCUIT_CLOSED` 脱敏日志，不接收 Error、Key、URL、正文或完整 UUID
- [x] 测试：覆盖阈值、跳过、恢复、重新熔断、Provider/Router 隔离、全冷却、混合失败与最早恢复时间
- [x] 测试：两个 `OpenAiProvider` 使用受控 `.invalid` fetch 验证 fallback 和冷却跳过，不访问真实外部 Provider

> **T02 收尾证据（2026-07-16）**：按已批准的 `.plans/phase1-t02-provider-health-circuit-breaker-plan.md` 在隔离 worktree 实施。最终验证使用 `APP_DATA_ROOT=I:\files\run\redacted\run-phase1-t02-final-001`：`pnpm type-check`、后端 build、前端 build 均通过；`ai-router.test.mjs` 17/17、后端全量 120/120、前端全量 32/32 通过。未新增数据库、migration、环境变量、真实外部 Provider 请求、S3 业务代码或 S4–S7 PRD。

#### T03：S3 限时练习（拆为 PRD + 3 个实现子任务 + 前端）

**T03 PRD（已完成，纯文档）**

- [x] 读 docs/00 确认 S3 门禁已满足
- [x] 创建 `docs/subsystems/03-S3-限时练习子系统PRD-PracticeRunner.md`
- [x] 更新 docs/00 索引

**T03A Schema（已完成）**（已按获批计划实施并通过验收；后续 T03B/T03C/T03D 已完成）

> **T03A 完成证据（2026-07-16）**：已新增学期库 migration v4、`practice_sessions`、`questions`、`practice_answers` 三表、11 个索引、8 个跨表一致性 trigger 与 S3 最小 shared 类型；7/7 专项数据库集成测试覆盖 fresh/v3 升级、约束、关联、父子更新和级联语义。最终 `pnpm type-check`、后端 build、前端 build 均通过，后端全量 127/127、前端全量 32/32 通过。未实现 S3 API、Service、Worker、AI 调用、前端或错题归档。

- [x] 创建 `questions` 表（题型、题干、选项、答案、题目顺序、难度、关联知识模块/来源资料）
- [x] 创建 `practice_sessions` 表（考试关联、限时、开始/结束、得分）
- [x] 创建 `practice_answers` 表（逐题作答、正确性、用时）
- [x] migration v4、数据库约束/升级测试与 type-check 验证

**T03B 练习生成（已完成）**（已按获批计划实施并通过验收；后续 T03C/T03D 已完成）

> **T03B 完成证据（2026-07-16）**：已新增 `PracticeRunnerService`、作答前公开 DTO、`POST /api/practice-sessions` 和 `GET /api/practice-sessions/:id`；练习生成只读取知识模块摘要/证据，AI 成功后同事务写入 `practice_sessions` 与 `questions`，返回给学生的题目隐藏正确答案、可接受答案、解析、来源证据和 AI 元数据。新增 `practice-generation-api.test.mjs` 使用本地 mock OpenAI-compatible Provider 覆盖成功入库、答案隐藏、AI 失败不落空 session、坏 JSON 不部分写入和跨课程模块调用 AI 前拒绝。验证通过：`pnpm type-check`、后端 build、前端 build、专项 4/4、隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase1-t03b-full-test` 下 `pnpm test`（后端 131/131、前端 32/32）。未实现提交作答、规则批改、`practice_answers` 写入、StudyEvent、前端或错题归档。

> **T03A/T03B 主线修复证据（2026-07-16）**：修复分支 `codex/phase1-t03ab-master-repair` 已将 T03A/T03B 既有实现快进合并到 `master` 并推送 `origin/master`，master 提交为 `a42090d`。主线复验通过：`pnpm type-check`、后端 build、前端 build、`practice-schema.test.mjs` 7/7、`practice-generation-api.test.mjs` 4/4、`pnpm test`（后端 131/131、前端 32/32）、文档治理检查与 `git diff --check`。额外修复 `@ai-studybuddy/shared` 声明产物漂移，保证 recursive type-check 先重建 shared 声明。该次修复当时未实施 T03C，S4/S5-S7 仍未触发。

- [x] `PracticeRunnerService` 按知识模块和难度选题或调 AI 生成
- [x] `POST /api/practice-sessions`（创建练习，AI 生成题目入库）
- [x] `GET /api/practice-sessions/:id`（获取练习与题目）
- [x] 测试：AI 生成解析、题目入库与关联正确

**T03C 批改（已完成）**（已按获批计划实施并通过验收；后续 T03D 已完成）

- [x] `POST /api/practice-sessions/:id/submit`（提交作答，规则批改客观题）
- [x] 批改后写入 `practice_answers`，计算 session 得分
- [x] 错题事实标记并写入 `practice_completed` 事件
- [x] 测试：选择题/填空题批改逻辑、得分计算、事件写入

> **T03C 完成证据（2026-07-16）**：已新增 `POST /api/practice-sessions/:id/submit` 与 shared 提交/批改 DTO；客观题规则批改覆盖单选 trim+大小写归一、多选集合全等、填空 NFKC/大小写/空白归一及可接受答案。提交事务内写入每题 `practice_answers`，将 `practice_sessions` 更新为 `graded` 并计算 `total_score`、`correct_rate`、`overtime`、`total_duration_seconds`、`submitted_at`、`graded_at`，同时写入摘要化 `practice_completed` StudyEvent（`evidence_ref=practice_session:<id>`，不写题干或答案）。新增 `practice-submit-api.test.mjs` 覆盖成功批改、缺答、超时、重复提交、未知/跨 session 题目、非法答案/用时、跨学期隔离、StudyEvent 与不创建 `mistakes`/`weak_points`。验证通过：`pnpm type-check`、后端 build、前端 build、T03C 专项 4/4、T03B 回归 4/4、后端/前端全量测试、文档治理检查与 `git diff --check`。任务分支 `codex/phase1-t03c-practice-submit-grading`，实现提交 `97d68a4` 已快进合入 `master`；未实现前端练习页面、错题归档、S4 PRD/Schema、S5-S7、真实外部 Provider smoke 或 Worker。

**T03D 前端（已完成）**（已按获批计划实施并通过验收；后续 T04/T04A/T04B/T05 已完成）

- [x] 前端 API 封装：创建练习、获取题目、提交作答
- [x] 练习页面：限时倒计时、逐题作答、提交
- [x] 结果页面：逐题批改详情、得分、错题标记
- [x] 工作台”练习”区集成：从知识模块发起练习
- [x] 测试：前端组件测试 + 浏览器 smoke

> **T03D 完成证据（2026-07-16）**：新增 PracticeRunner 前端 API 封装、练习发起/作答/结果页面、单选/多选/填空作答控件、基于浏览器性能时钟的限时/逐题计时与同浏览器会话草稿/结果恢复；已确认考试工作台新增“练习”区入口。结果页只消费既有提交响应和作答前详情，不新增后端 result/list API；缓存缺失时显示中文降级，不伪造历史结果。新增前端 API/页面测试与 Playwright `practice-runner.spec.ts`；隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase1-t03d-frontend` 浏览器验收覆盖发起、三类题作答、超时提交、逐题批改、刷新恢复及非法 session 错误页，使用本地 route fixture，不调用真实 Provider。验证通过：`pnpm type-check`、前端 build、前端 37/37、Playwright 2/2；不实现后端 API/Schema、错题归档、`mistakes`/`weak_points`、S4 PRD/Schema、S5-S7、真实外部 Provider smoke 或 Worker。

#### T04：S4 错题改错（拆为 PRD + 2 个实现子任务）

**T04 PRD（已完成，纯文档）**（已按获批计划实施并通过文档验收；后续 T04A/T04B/T05 已完成）

- [x] 创建 `docs/subsystems/03-S4-错题改错子系统PRD-ErrorFixer.md`
- [x] 更新 docs/00 索引

> **T04 完成证据（2026-07-16）**：已创建 S4 轻量 PRD，明确 `practice_answers.is_correct = false` 是只读、可追溯的错误事实输入；定义错因由学生确认、原题/同类题/变题重做边界、重做证据、薄弱点必须由多次证据支撑、掌握可重新打开、学期隔离及 S6 只读脱敏聚合。已同步 `docs/00` v2.14；`powershell -ExecutionPolicy Bypass -File scripts/check-docs-governance.ps1` 与 `git diff --check` 通过。未创建 `mistakes`/`weak_points` Schema，未实现归档、重做、回流、API、页面、Worker、真实 Provider 或 S5-S7。

**T04A Schema 与归档（已完成）**（已按获批计划实施并通过验收；后续 T04B/T05 已完成）

- [x] 创建 `mistakes` 表（错题记录、次数、最近错误、掌握状态、关联 question/module）
- [x] 创建 `weak_points` 表（薄弱点由多次错题证据归纳）
- [x] S3 练习批改后自动归档到 `mistakes`
- [x] 测试：归档逻辑、重复错题计数递增

> **T04A 完成证据（2026-07-16）**：已创建 `.plans/phase1-t04a-s4-schema-archive-plan.md` 并按计划实施；新增学期库 migration v5，创建 `mistakes`、`mistake_evidence`、`weak_points`，用 `mistake_evidence.source_practice_answer_id` 唯一约束保证同一 `PracticeAnswer` 幂等归档；未作答沿用 S3 `is_correct = 0` 错误事实进入归档；同课程实例 + 知识模块至少两条独立错误证据才创建 `weak_points`。`PracticeRunnerService.submitPracticeSession()` 在同一事务内写入 `practice_answers` 后调用 S4 归档，失败整体回滚。新增 `error-fixer-schema.test.mjs` 与 `error-fixer-archive-api.test.mjs`，并更新 S3 回归测试对 migration v5 与 S4 表存在的预期。验证通过：后端 build、T04A schema 3/3、T04A archive 4/4、S3 submit 4/4、S3 schema 7/7；最终全量验证见本任务交付说明。未实现 T04B 前端、错因确认、错题重做、T05 回流规则、S5-S7、Worker 或真实 Provider smoke。
> **T04B 前端（已完成）**（已按获批"收窄版方案 A"计划实施并通过验收；后续 T05 已完成）

- [x] 错题列表与筛选（按课程/模块/掌握状态）
- [x] 错题重做流程（重新作答 → 批改 → 更新掌握状态）
- [x] 工作台"查漏补缺"区集成
- [x] 测试：前端组件 + 浏览器 smoke

> **T04B 完成证据（2026-07-16）**：已创建 `.plans/phase1-t04b-s4-errorfixer-frontend-plan.md`，经用户批准"收窄版方案 A"后实施。本任务包含一次 **Schema/API 补洞**（T04A 遗漏，属 T04B 范围，不回改 T04A 完成事实）：新增学期库 migration v6，为 `mistakes` 补错因确认最小字段（`error_cause_category` 白名单 / `error_cause_note` ≤500 字 / `error_cause_confirmed_at`），`mistake_evidence.evidence_type` 扩展 `redo_correct`/`redo_incorrect` 并重建触发器，`practice_sessions` 增加 `session_kind`（`practice`/`mistake_redo`）与 `origin_mistake_id`，`questions` 增加 `origin_question_id` 复制题溯源；均只服务 S4 原题重做，未引入 T05 回流。新增 S4 API（`GET /api/mistakes`、`GET /api/mistakes/:id`、`PATCH /api/mistakes/:id/error-cause`、`PATCH /api/mistakes/:id/status`、`POST /api/mistakes/:id/redo`、`GET /api/weak-points`），前端只消费 API 不读 SQLite；重做复用 S3 submit 通道但按 `session_kind` 旁路归档（重做失败不新建错题、不重复计数，写 `redo_incorrect` 证据并计入薄弱点；重做通过写 `redo_correct` 证据）；标记掌握需重做通过证据或学生显式确认，已掌握可重新打开；S4 写 `mistake_reviewed` 摘要事件（`evidence_ref=mistake:<id>`，无题干正文）。前端新增 `/exams/:examId/mistakes` 错题列表页（状态/模块筛选 + 薄弱点区块）、`/mistakes/:mistakeId` 详情改错页（原题事实、错因确认、重做、状态操作、证据时间线）、工作台"查漏补缺"卡片与 S3 结果页错题入口。验证通过：`pnpm type-check`、后端/前端 build、后端测试 150/150（新增 T04B API 6、v6 迁移与约束 2）、前端测试 41/41（新增错题页 4）、Playwright e2e 4/4（新增 error-fixer 全流程 1，隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase1-t04b-e2e`）、文档治理、`git diff --check`。未实现 T05 回流规则、AI 错因建议、同类题/变题生成、S5/S6/S7、Worker 或真实 Provider smoke。

#### T05：回流规则（门禁：T04B 已验收；需独立计划、审查和用户明确批准）

- [x] 错题/薄弱点提升关联知识模块 `studyStatus` 为”需要复习”
- [x] 关联学习任务 `priorityBucket` 受薄弱点影响提升
- [x] 已掌握后降低复习优先级，不删除历史记录
- [x] 测试：优先级派生逻辑覆盖各场景

> **T05 计划证据（2026-07-17）**：已在任务分支 `codex/phase1-t05-feedback-rules-plan` 创建 `.plans/phase1-t05-feedback-rules-plan.md`，完成计划自审并等待用户明确批准。该计划仅设计 T05 回流规则，未实现业务代码、未改 Schema、未勾选上述实现项；明确不触碰 AI 错因建议、同类题/变题生成、S5/S6/S7、Worker、真实 Provider 或跨学期复用。

> **T05 完成证据（2026-07-17）**：已按获批计划在任务分支 `codex/phase1-t05-feedback-rules` 实现 `FeedbackRulesService`，在 S4 错题归档、错因确认、重做失败和状态流转事务内触发回流规则；使用现有 `knowledge_modules.learn_status`、`study_tasks(type='error_review')`、`weak_points.status`、`study_events` 和 S1 `priorityBucket` 派生，不新增 Schema、公开 API、前端页面或 shared 类型。单条 `practice_error` 仅保留证据；错因确认、活跃薄弱点、重做失败或已掌握错题重开会把模块置为 `learning` 并创建/提升复习任务；全部错题已掌握时模块/薄弱点降为 `mastered` 并完成 open `error_review` 任务；历史错题、证据和重做记录不删除。验证通过：`pnpm type-check`、`pnpm -r --filter backend run build`、`pnpm -r --filter @ai-studybuddy/frontend run build`、`pnpm test`（后端 157/157，前端 41/41）。未实现 AI 错因建议、同类题/变题生成、S5/S6/S7、Worker、真实 Provider 或跨学期复用；T05 未改前端交互，故未新增 Playwright e2e。

#### T06：S6 家长报告简版（拆为 PRD + 2 个实现子任务）

**T06 PRD**（门禁：Phase 1 后期且准备正式发送家长报告；T06 文档计划已批准）

- [x] 创建 `docs/subsystems/06-S6-家长观察子系统PRD-ParentReport.md`
- [x] 更新 docs/00 索引

> **T06 完成证据（2026-07-17）**：已按用户批准计划在任务分支 `codex/phase1-t06-s6-prd` 补齐 `.plans/phase1-t06-s6-prd-plan.md`，创建 `docs/subsystems/06-S6-家长观察子系统PRD-ParentReport.md` 并同步 `docs/00` 索引。S6 PRD 仅定义脱敏日报/周报/月报/考前 7/3/1 提醒、规则优先、AI 摘要降级、`report_key + channel` 去重与渠道失败隔离边界；不新增业务代码、Schema、API、shared 类型、Worker、前端页面、SMTP 或飞书实现。验证通过：`powershell -ExecutionPolicy Bypass -File scripts\check-docs-governance.ps1`、`git diff --check`。

**T06A 报告生成**（门禁：S6 PRD 已创建；T06A 独立实现计划已批准）

- [x] 复用既有事实生成规则报告：统计课程/任务/完成/逾期/学习时长、资料处理、知识模块、练习、错题/薄弱点和回流任务
- [x] AI 润色成功附加总结，失败、未配置或空内容时仍保留规则报告
- [x] 报告不含资料原文、笔记正文、完整题干/答案/学生作答、错因正文、聊天内容、渠道地址或完整 UUID
- [x] 测试：日报/周报/月报证据窗口、已确认考前 7/3/1 天提醒、AI 成功/失败回退和隐私边界

> **T06A 计划证据（2026-07-17）**：已在任务分支 `codex/phase1-t06a-parent-report-generation-plan` 创建 `.plans/phase1-t06a-parent-report-generation-plan.md`，完成计划自审并获用户明确批准。该计划仅设计 T06A 家长报告生成：新增后端 `ParentReportService` 与后端专项测试，基于既有 S1/S2/S3/S4/T05 事实生成脱敏日报、周报、月报和考前 7/3/1 天提醒；规则报告可独立生成，AI 仅做脱敏摘要/润色且失败时保留规则报告。本计划分支不实现业务代码、不新增 Schema、HTTP API、shared 类型、Worker、前端页面、SMTP、飞书 Webhook、渠道发送或真实 Provider smoke；T06B、S5、S7、Phase 3 继续等待各自门禁。
> **T06A 完成证据（2026-07-17）**：已按获批计划在任务分支 `codex/phase1-t06a-parent-report-generation` 实现 `ParentReportService` 与真实 SQLite 专项测试。服务只读取既有 S1/S2/S3/S4/T05 脱敏聚合值，生成日报、周报、月报及仅限已确认考试的考前 7/3/1 天提醒；规则报告可独立生成，AI 仅接收脱敏报告区块做可选摘要/润色，AI 未配置、抛错或返回空内容时保留规则报告。未新增 Schema、HTTP API、shared 类型、Worker、前端页面、QQ SMTP、飞书 Webhook、`report_deliveries` 写入或真实 Provider smoke。验证通过：隔离 `APP_DATA_ROOT` 下的 `pnpm type-check`、`pnpm -r --filter backend run build`、`pnpm test`（后端 164/164、前端 41/41）、`powershell -ExecutionPolicy Bypass -File scripts\check-docs-governance.ps1`、`git diff --check`。

**T06B 推送渠道**（门禁：T06A 已验收；需独立实施计划与用户明确批准）

- [x] QQ SMTP HTML 报告发送
- [x] 飞书 Webhook 卡片推送
- [x] 渠道失败互不阻塞，去重 `report:<date>` 记录
- [x] 测试：双渠道独立、失败隔离、去重、迁移、租约恢复、双失败本机留档

> **T06B 完成证据（2026-07-17）**：用户已批准独立计划 `.plans/phase1-t06b-report-delivery-plan.md`（计划分支 `codex/phase1-t06b-report-delivery-plan`，提交 `268b76c`）；实现分支 `codex/phase1-t06b-report-delivery` 新增学期库 migration v7、`ParentReportDeliveryService`、一次性 `parent-report-runner`、QQ SMTP/飞书可注入 Adapter 与 Windows Task Scheduler 注册/注销脚本。服务以 `report:<yyyy-mm-dd>` 冻结 T06A 脱敏合并快照，并以 `report_key + channel` 渠道级去重；SMTP/飞书独立投递、失败隔离，失败渠道使用有限退避重试与过期租约恢复，双渠道失败时只保留本机脱敏 HTML 和固定错误摘要；自动重试按 `report_key + channel` 跨运行累计最多 3 次，第三次失败后保留脱敏本机归档并等待人工处理。`report_key + channel` 保证数据库记录与正常重复运行的渠道级去重；外部渠道在“已接收、尚未写入 `sent`”的进程中断窗口按至少一次投递处理，可能重复相同冻结脱敏快照。已在隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase1-t06b-final-post-review-rerun-2` 下通过 T06B 后端专项 `node --test`（13/13，含 v6 既有库缺少 `report_deliveries` 的 migration 回归与跨进程三次重试上限回归）、`pnpm type-check`、后端/前端 build、`pnpm test`（后端 177/177、前端 41/41）、文档治理和 diff 检查。未运行真实 QQ SMTP、飞书 Webhook、Provider 或 Task Scheduler 注册 smoke；未实现 HTTP API、前端、常驻/队列 Worker、家长面板/账号、S5/S7 或 Phase 3。

#### T07：S1 时间线扩展（门禁：至少一个新增 S3/S4 事件生产者已验收；需独立实施计划、审查和用户明确批准）

- [x] 完整接收 S2/S3/S4 写入的 StudyEvent（`material_note_completed`、`practice_completed`、`mistake_reviewed` 等）
- [x] 时间线 API 按事件类型过滤
- [x] 前端工作台总览展示近期学习活动
- [x] 测试：多子系统事件写入与读取

> **T07 计划证据（2026-07-17）**：已在任务分支 `codex/phase1-t07-timeline-plan` 创建 `.plans/phase1-t07-timeline-plan.md`，提交 `5ee0def`；计划经独立审查并获用户明确批准，随后纳入实施分支 `codex/phase1-t07-timeline`，对应计划提交 `26666e5`。获批范围复用既有 `study_events` 表和 S1/S2/S3/S4 事件生产者，只扩展 `GET /api/timeline` 的重复 `eventType` 查询过滤，并在考试工作台展示当前考试所属课程最近 8 条学习活动。

> **T07 完成证据（2026-07-17）**：后端在既有 `GET /api/timeline` 上支持重复 `eventType` 参数的精确匹配，课程条件与事件类型条件按 AND 组合，最多接受 20 个不同的 `eventType`；结果按事件倒序，`limit` 默认 50、允许范围为 1..200。集成测试从 S2 `material_note_completed`、S3 `practice_completed`、S4 `mistake_reviewed` 的正式生产路径读回事件，覆盖双课程隔离和重复过滤。考试工作台只请求当前考试所属课程并展示最近 8 条，以固定中文事件类型文案和时间/工作量摘要呈现，不渲染 `title`、`evidenceRef` 或 UUID。加载、空态、错误与重试均局部隔离，考试切换和取消请求的竞态不会让旧课程结果覆盖当前课程。Playwright `e2e/timeline.spec.ts` 1/1 通过，覆盖重复 `eventType` 真实过滤、事件倒序、双课程隔离、第三课程空态、受控 500 失败隔离与局部重试、刷新，以及 390/1440 视口无横向溢出；截图已 mask UUID，移动端证据 `I:\ai-studybuddy-tmp\runs\phase1-t07-browser\playwright\timeline-mobile.png`（SHA256 `C40B4ECA53716B176D565DE28542E5136C02CDB7090B9279FBACA9706F6784FB`），桌面端 SHA256 `CD4215642FBA7DB5714A08E5FA0B798A8ED65B691E6CFBDED027D268713E4341`。Playwright 在 390px 验收中发现应用壳既存溢出，提交 `ec066ac` 仅补充 `<=720px` 最小 CSS 修复以满足本任务移动验收，不是全局视觉重构。最终 `pnpm type-check`、后端 build、前端 build 均通过，`pnpm test` 为后端 178/178、前端 48/48。任务分支 `codex/phase1-t07-timeline`；关键提交：后端 `ae0b6e6`、测试补强 `c34c9db`、前端 `5b999e6`、竞态修复 `b78c228`/`4a44ab7`、移动壳 CSS 修复 `ec066ac`、浏览器验收 `e022564`/`eb2bfd7`。未新增 Schema、migration、StudyEvent 生产者、独立时间线页、每日首页、全局导航、S6 页面或家长面板；未实现 T08、S5、S7 或 S3 Worker，未运行真实外部渠道 smoke。

#### T08：本机配置中心与连接验收（门禁：T07 完成或用户明确调整顺序；需独立实施计划、审查和用户明确批准）

- [x] 首次启动向导：后端无 AI/SMTP/飞书配置时仍可启动，前端可进入配置中心
- [x] 配置分区：AI Provider、QQ SMTP、飞书 Webhook 和运行状态分别展示配置状态
- [x] 秘密存储：API Key、SMTP 授权码、飞书 Webhook URL 不进入浏览器持久化、普通 SQLite 表、日志或 API 响应，由后端使用 Windows 当前用户加密存储
- [x] 连接测试：AI 最小请求、SMTP 连接验证与显式测试邮件、飞书固定测试卡片分别可执行并返回脱敏结果
- [x] 运行门禁：AI 未验证时 AI 依赖功能明确降级；单一渠道失败不阻断另一渠道；双渠道失败仍保留本机脱敏报告
- [x] 配置更新：测试成功后原子激活运行时配置，失败或损坏时保留上一份可用配置并给出固定错误码
- [x] 测试：秘密不回显/不落前端存储、配置加密读写、测试成功/失败、渠道隔离、重启恢复和脱敏日志

> **T08 完成证据（2026-07-17）**：任务分支 `codex/phase1-t08-config-center` 按 `.plans/phase1-t08-config-center-plan.md` v6 实施。关键提交：`4cbc54c` DPAPI 安全配置存储，`dfb1f71` 配置状态与连接测试，`4a6b5fc` 配置 API、loopback Origin 策略、启动门禁与运行时热切换，`45ce9e2` 前端设置中心。Node 22 DPAPI roundtrip 证据：Node `v22.23.1`、win32 x64、`isPlatformSupported=true`、`roundtrip=true`；`DpapiProtector` 包装器 roundtrip 也通过。验证：隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase1-t08-full` 下 `pnpm -r --filter @ai-studybuddy/backend run build` 通过、`pnpm -r --filter @ai-studybuddy/backend run test` 212/212 通过；前端 `pnpm -r --filter @ai-studybuddy/frontend test` 10 files / 52 tests 通过，`pnpm -r --filter @ai-studybuddy/frontend run build` 通过；根级 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase1-t08-root` 下 `pnpm type-check` 与 `pnpm test` 通过；隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase1-t08-browser` 下启动 backend `start` 与 frontend `preview`，Playwright 访问 `http://127.0.0.1:4173/settings` 验证“本机配置中心 / 运行状态 / AI Provider / QQ SMTP / 飞书 Webhook”可见且密钥字段为 `password`，访问 `/courses` 验证首次配置提示可见，未点击真实测试激活按钮。测试覆盖候选配置不落盘、DPAPI 不可用降级、active/prev 恢复、唯一 tmp 清理、同 channel 串行锁、跨 channel 并行、逐 Provider 全通过才激活、API 输入上限、非 JSON 拒绝、loopback Origin 策略、配置初始化先于 listen/Worker、AI Router 引用热切换保留熔断、SMTP/飞书快照隔离、前端密钥成功后清空且不写 localStorage、失败只显示固定错误码。未运行真实 AI/SMTP/飞书 smoke；未实现 T09A–T09E 学生端产品化界面、学期向导、每日首页、S5、S7 或家长 Web 面板。

> **T08 部署包/源码设置中心一致性复核（2026-07-30）**：按需求对当前 Windows 部署包与开发源码的设置中心进行了只读比对。部署 manifest 所指源码提交与当前 `master` 一致；后端运行产物中 276 个同路径文件与源码构建产物逐文件 hash 一致，部署包额外的依赖元数据及其构建 manifest 属于预期包级差异；前端静态产物 122 个同路径文件 hash 一致。DPAPI 安全存储、配置状态与连接测试、运行时热切换、Provider 官方预设与候选 fallback、环境来源安全摘要、错误脱敏、子进程环境边界及 `/v1` fallback 的相关提交均已在 `master`。本轮定向配置后端测试 23/23、设置页测试 9/9、`pnpm type-check` 与 `pnpm build` 均通过（生产构建仅保留既有大 chunk 警告）。未读取、写入或输出任何运行时配置、秘密或用户资料。结论：部署包不存在待反哺的设置中心代码；本轮不修改业务实现，仅补充可追溯复核证据。
> **Phase 1 Pre-T09 端到端验收登记（2026-07-18，验证任务，非 T09 实施）**：已从最新 `origin/master` 创建验证分支 `codex/pre-t09-e2e-validation`，计划为 `.plans/pre-t09-e2e-validation-plan.md`。本轮范围是对 T00/T10/T11/T02/T03/T03A/T03B/T03C/T03D/T04/T04A/T04B/T05/T06/T06A/T06B/T07/T08 的后端、前端、API 和浏览器主路径进行隔离回归；不实现 T09A–T09E，不触发 S5/S7/Phase 3，不运行真实 AI/SMTP/飞书 smoke。
>
> **验收证据（2026-07-18）**：治理检查 `scripts/check-docs-governance.ps1` 通过，`git diff --check` 通过；`pnpm type-check` 通过；后端 build 通过、后端测试 `212/212` 通过；前端 build 通过（仅有 Vite chunk 大于 500 kB 的非阻塞警告）、前端测试 `10 files / 52 tests` 通过；根级 `pnpm test` 通过（同样汇总后端 `212/212`、前端 `10 files / 52 tests`）。隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\pre-t09-e2e-validation` 下，Playwright `pnpm test:e2e` 最终 `5 passed`：S4 错题改错、T11 多考试/任务闭环、S3 限时练习（含超时提交/刷新恢复）、不存在练习错误态、T07 时间线/移动端。一次性真实浏览器脚本进一步通过 `/settings` 配置中心与 password 密钥字段、`/courses` 课程入口、`/materials` 合成文本上传与处理刷新、`/notes/:noteId` Markdown/思维导图/知识模块展示；API envelope 合成检查通过。S6 规则生成/隔离/去重/重试边界由现有自动化测试覆盖，未发送真实 QQ SMTP 或飞书消息。
>
> **验收中发现并修复的 P1 回归**：浏览器点击“确认考试日期”时，后端 loopback Origin 策略的 `Access-Control-Allow-Methods` 仅声明 `GET,POST,OPTIONS`，导致 PATCH 预检失败并显示“网络连接失败”，同时阻断任务状态和错题 PATCH 路径。已在 `packages/backend/src/middleware/api-origin-policy.ts` 补充 `PATCH,DELETE`，并在 `packages/backend/test/api-origin-policy.test.mjs` 增加 PATCH 预检回归断言；修复后受影响 E2E 及全量 E2E 均通过。当前无 P0/P1 未修复问题。
>
> **可接受的 T09A 前已知缺口 / 边界**：`/courses` 顶部仍使用开发期手输 `semesterId`，属于 T09A 学期创建、选择与切换范围，不在本轮实现；未运行真实 AI Provider、QQ SMTP、飞书 Webhook 或正式 Windows Task Scheduler smoke；未实现 T09B–T09E、每日首页、家长 Web 面板、S5、S7 和 Phase 3。验收提交已按固定 Git 流程快进合入 `master`；推送状态见本次交付记录。

---

## Phase 1.5：课堂 ASR（S7）

**目标**：录音 → ASR → 文字 → 纯文本 → 复用 S2 笔记生成管道。

**当前可执行任务**：Phase 1 中 S2 文本资料、资料状态卡和笔记生成管道已经稳定。用户已明确批准以**一个小型 S7-MVP**替代旧的“先 T05 Job、再 T06 页面”的实施顺序：短 WAV 在一次请求内调用受控、外部配置的 `whisper.cpp`，只把用户确认后的可编辑文本写入既有 S2 `text` 资料；不保存原始录音，不自动生成笔记，不启动 Provider。旧 T02/T04 候选能力 `PARTIAL`、T03 Composer smoke `PASS` 与 G2 历史记录继续作为外部组件事实保留，均不被本任务改写为完整 S7 或用户机验收完成。

| 顺序 | 任务                                        | 状态                                    | 单一责任                                                                                                                                                                                                                 |
| ---- | ------------------------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1    | T01：S7 PRD 编写                            | ✅                                      | 已建立 S7 领域边界；本轮将同步为当前“小型同步 WAV MVP”产品合同                                                                                                                                                           |
| 2    | 旧 T02/T04：外置 ASR 候选能力               | ✅（`PARTIAL`）                         | 保留为固定候选与限制事实；不等于产品接入、通用静音、G2、完整 S7 或用户机验收                                                                                                                                             |
| 3    | 旧 T03：FFmpeg Composer smoke               | ✅（历史能力）                          | 不纳入本 MVP；本 MVP 不转换 MP3/M4A/视频，只接受受控 PCM WAV                                                                                                                                                             |
| 4    | **S7-MVP：本地 WAV → 可编辑文本 → S2 输入** | ✅ 已完成主线复验并推送 `origin/master` | `.plans/phase1-5-s7-mvp-local-audio-transcription-plan.md`：配置化 `whisper.cpp` Adapter、同步 API、S2 文本 handoff、资料页内最小 UI、真实 SQLite/API/前端/E2E 验证；不建 Worker、无云端/Provider/Firewall/G2/Docker/WSL |
| 5    | 完整 S7 后续能力                            | ⏸️                                      | 长音频、格式转换、后台 Job、实时录音、说话人分离、视频和原始音频留存均需单独产品任务与批准                                                                                                                               |

> **S7-MVP 主线完成证据（2026-07-25，已推送 `origin/master`）**：任务分支 `codex/phase1-5-s7-mvp-docs-plan` 的实现提交 `a35dc21` 已 fast-forward 合入 `master`；复验状态提交 `1622582` 已推送，远端 `origin/master` 已复查指向 `1622582ada30f77044fc3b74d8423f2131e11327`。在本机 `master` 的隔离运行目录 `H:\ai-studybuddy-tmp\runs\phase1-5-s7-mvp-master-gates-20260725` 已通过 `pnpm type-check`、backend/frontend build、backend `245/245`、frontend `139/139` 与 Playwright `21/21`。开发机真实正向 smoke 摘要为 `H:\ai-studybuddy-tmp\runs\phase1-5-s7-mvp-smoke-20260725-01\s7-mvp-local-smoke-summary.json`：固定资产哈希一致，受控合成中文 WAV 转写和 S2 handoff 通过，保存不创建 Job，临时 request 目录和 `whisper-cli.exe` 残留均为零。负向摘要为同目录 `s7-mvp-runtime-negative-summary.json`：真实固定 CLI 的受控超时稳定返回 `ASR_PROCESS_TIMEOUT`（504），显式非零 CLI 稳定返回 `ASR_TRANSCRIPTION_FAILED`（502），两项均无 request/CLI 残留。S7-MVP 只完成这条学生本机小闭环；完整 S7、G2、T02 主线、用户电脑验收和 Phase 3 仍未完成。

> **Phase 1.5-T02 ASR composer smoke 行动计划证据（2026-07-21，已批准并执行）**：已从最新且干净的 `master` / `origin/master` `df55dfef6b658a7dbef68472916ddae82ce645ed` 创建任务分支 `codex/phase1-5-t02-s7-asr-composer-plan` 与独立 worktree，并创建、fresh-pass 审查 `.plans/phase1-5-t02-s7-asr-composer-smoke-plan.md`。计划仅定义未来在独立 composer 试炼场核验 Windows 本地 CPU ASR 的候选选择、标准音频样例、`ConverterResult` 映射证据、性能/资源/稳定性记录、PASS/PARTIAL/FAIL 判定、能力卡、白名单与回滚规则；本轮未执行 ASR smoke，未安装依赖或下载模型，未修改 composer、`packages/` 或 S7 PRD，未开始 T03 FFmpeg、T04 `AuralConverter`、T05 Job/Worker 或 T06 前端。用户已于 2026-07-21 明确批准该计划；当前只执行 T02，不自动进入 T03–T06。

> **Phase 1.5-T02 用户批准记录（2026-07-21）**：用户已在计划任务交付后明确回复“明确批准”。本次批准只解除 T02 composer smoke 的计划门禁，允许按 `.plans/phase1-5-t02-s7-asr-composer-smoke-plan.md` 的候选、白名单、隐私、失败与回滚规则执行；不授权 T03 FFmpeg、T04 `AuralConverter`、T05 Job/Worker、T06 前端或任何 `packages/` 业务代码变更。
> **Phase 1.5-T02 最终 smoke 证据（2026-07-21，`PARTIAL`）**：Composer 使用独立 Python 3.10.19 `.venv`，固定 FunASR 1.3.22、torch/torchaudio 2.11.0+cpu 与 ModelScope 1.38.1；官方 `iic/SenseVoiceSmall` 模型共 20 文件、940,019,376 bytes，ModelScope API 与下载 README 均标记 Apache License 2.0，逐文件 SHA-256 已保存在 composer 本机忽略目录。显式本地模型与 offline 环境变量三次复跑中，模型加载 3,342 ms、总进程 28,056 ms、峰值工作集约 3,125.5 MiB；中文与中英混合短样例 3/3 非空且哈希稳定，损坏 WAV / 非 WAV 分别稳定返回 `AUDIO_DECODE_FAILED` / `AUDIO_FORMAT_UNSUPPORTED`，14/14 结果通过 JSON Schema。静音与轻噪声均 3/3 产生同一短误识别；100 ms TCP 轮询未见连接但未做防火墙隔离；模型只固定 `master` 而非 immutable revision。首次安装另有约 280.58 MiB 误写默认用户 pip cache，未做不安全清理，后续缓存已全部收口。故 T02 执行完成但判 `PARTIAL`：可作为 T03 独立计划输入，不直接进入 T04；T03–T06 仍须分别计划、审查和批准。任务分支复验已在隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase1-5-t02-branch-test-20260722` 下完成：`pnpm type-check`、后端 build、前端 build 及 `pnpm test` 均以退出码 0 结束（frontend 137/137、backend 237/237）；前端仅保留既有 Vite 大 chunk 非阻塞警告。

---

> **Phase 1.5-T03 FFmpeg 音频预处理 Composer smoke 证据（2026-07-22，已合入并推送 `origin/master`）**：用户明确批准后，任务分支 `codex/phase1-5-t03-s7-ffmpeg-preprocess-plan` 依 `.plans/phase1-5-t03-s7-ffmpeg-preprocess-plan.md` 在 `I:\ai-studybuddy-composer\asr\FFmpeg\{bin,samples,output,.cache,smoke-test,shared}` 完成固定 Gyan `ffmpeg-8.1.2-essentials_build.zip` Composer smoke。计划固定 SHA-256、发布方 sidecar 和本地 SHA-256 均为 `db580001caa24ac104c8cb856cd113a87b0a443f7bdf47d8c12b1d740584a2ec`；仅提取 `ffmpeg.exe`、`ffprobe.exe`、LICENSE/README。实测构建为 `8.1.2-essentials_build-www.gyan.dev`，含 `--enable-gpl --enable-version3 --enable-static`，故只记录为本机试炼事实，**不**构成产品许可证或再分发授权。纯合成、非敏感矩阵共 19 用例：15 个正常路径 `PASS`（WAV、MP3、M4A、11,025 Hz 双声道、静音、轻噪、31 秒长音频 6 秒切片/2 秒重叠），4 个异常路径 `EXPECTED_FAIL`（损坏、非音频、输出异常、500 ms 超时），成功输出均验证为 16 kHz 单声道 `pcm_s16le` WAV，基线重复输出 SHA-256 一致，无 `ffmpeg`/`ffprobe` 残留。证据和 `COMPONENT-CARD.md` 均在 Composer `shared/`；未写系统 PATH、注册表、服务、全局配置、`%LocalAppData%` 或既有缓存，未改 `packages/`、S7 PRD、Schema、API、Job/Worker、前端，未创建/调用 `AuralConverter` 或 FunASR。T02 仍为 `PARTIAL`，静音/轻噪 false positive、immutable revision、离线隔离和 no-speech 门禁均未关闭；T03 已随提交 `bb080efa304ad03211865bbc4d6a12718b7057d0` 合入并推送 `origin/master`；T04–T06 未启动，T04 仍须独立计划、审查和用户明确批准。

> **Phase 1.5-T04 S7 ASR 后续能力行动计划证据（2026-07-22，计划已获批并进入任务分支执行）**：已在隔离任务分支 `codex/phase1-5-t04-s7-next-asr-capability-plan` 创建并完成 fresh-pass 审查 `.plans/phase1-5-t04-s7-next-asr-capability-plan.md`；用户随后于 2026-07-22 明确批准进入 T04 后续 ASR 能力验证执行。本次执行分支为 `codex/phase1-5-t04-s7-next-asr-capability-exec`，最终 `git fetch origin` 成功且 `origin/master` 仍为 `e6d12eac76e6505fb5f124a6af3f52bf633f30ef`。本轮仅执行计划允许的 ASR 能力补证与 Adapter 前置判定，不创建/装配/调用 `AuralConverter`，不修改 `packages/`、Schema、migration、API、Job/Worker、前端或 shared 类型，不启动 T05/T06，不使用真实课堂录音、真实学生数据、资料原文、真实 Provider 信息或秘密。
>
> **Phase 1.5-T04 能力验证证据（2026-07-22，`PARTIAL`，任务分支尚未合入或推送）**：T04 在 `I:\ai-studybuddy-composer\asr\T04-next-capability\` 专属 Composer 目录内完成，样例全部为安全合成、非敏感音频；结构化证据包括 `shared\t04-summary.json`、`shared\results\t04-results.jsonl`、`shared\COMPONENT-CARD.md`、`shared\T04-EXECUTION-SUMMARY.md`、`metrics\precheck-summary.json`、`metrics\t04-asr-main-20260722.process.json`、`metrics\t04-timeout-20260722.process.json`、`metrics\environment-and-boundary.json`、`metrics\final-boundary-recheck.json` 与 `metrics\final-git-baseline-check.json`。前置核对确认 T02 FunASR 1.3.22 + `iic/SenseVoiceSmall` Windows CPU 证据存在但 T02 仍为 `PARTIAL`；T03 Gyan FFmpeg 8.1.2 证据、SHA-256 `db580001caa24ac104c8cb856cd113a87b0a443f7bdf47d8c12b1d740584a2ec`、19 个 smoke（15 `PASS` / 4 `EXPECTED_FAIL`）与提交 `bb080efa304ad03211865bbc4d6a12718b7057d0` 均已核对，T03 的 16 kHz 单声道 PCM WAV 输出仍只作为能力事实，不成为正式生产契约。
>
> **Phase 1.5-T04 判定与阻断（2026-07-22，`PARTIAL`）**：主 ASR 矩阵 `t04-asr-main-20260722` 产生 14 条机器结果，其中 P1 中文清晰样例与 P2 中英混合术语样例 3/3 成功且文本哈希稳定；N3 损坏 WAV 稳定分类为 `AUDIO_DECODE_FAILED`，N4 非音频文件稳定分类为 `AUDIO_FORMAT_UNSUPPORTED`；N5 受控超时验证返回 `PROCESS_TIMEOUT`，无残留候选 Python/FFmpeg/FFprobe 进程。N1 静音与 N2 轻噪声仍产生非空 ASR 文本，确认 T02 no-speech false positive 风险未关闭；模型仍未固定 immutable revision，未执行防火墙离线隔离，P3 非标准采样率/声道仅引用 T03 预处理能力事实而未重跑 FFmpeg。最终判定为 `PARTIAL`：能力可验证但仍存在 no-speech、immutable revision、离线隔离与预处理接续覆盖缺口；该结论只是能力验证结果，不等于生产接入资格，不代表 ASR 已完成、S7 已完成或可直接生产接入，也不得自动授权 T05/T06。
> **Phase 1.5-T02/T04 ASR 三门禁补证计划（2026-07-22，fresh-pass 完成，后续执行已获明确批准）**：基于 `origin/master` `6aba5a15cd004abfab191a117dd75a4f533631d8`，隔离分支 `codex/phase1-5-t02-t04-asr-gates-plan` 已创建 `.plans/phase1-5-t02-t04-asr-gates-remediation-plan.md` 并完成 fresh-pass。计划仅定义 immutable model revision、防火墙离线隔离和 no-speech 三个阻断门禁的未来补证方法、最小证据、成功/停止条件、回滚、脱敏与 `PASS`/`PARTIAL`/`FAIL`/`BLOCKED` 判定。计划坚持只用既有本地 FunASR 1.3.22、`iic/SenseVoiceSmall` 和安全合成样例；无可信 immutable revision 或无权创建并回滚临时、目标进程范围的 Firewall 规则即停止，不下载模型、不猜测、不以 cache-only/环境变量替代。静音/轻噪均要求至少 3 次结构化 `NO_SPEECH` 且无非空文本，同时回归正向中英样例、损坏 WAV、非音频、超时和进程清理。计划阶段仅创建计划和任务登记，未执行 ASR/FFmpeg/Composer/Firewall，未改 `packages/`、Schema、migration、API、Job/Worker、前端或 shared 类型，未创建/装配/调用 `AuralConverter`，未启动 T05/T06。T02 与 T04 仍为 `PARTIAL`，T03 保持已入主线 `PASS`，能力补证无论结果均不等于 ASR/S7 完成或生产接入资格。

> **Phase 1.5-T02/T04 ASR 三门禁补证执行证据（2026-07-22，`BLOCKED`）**：执行分支 `codex/phase1-5-t02-t04-asr-gates-exec` 从 `origin/master` `5ae83ab74f1badece657384f4f07d42c221b0007` 创建，隔离 worktree 为 `I:\ai-studybuddy-worktrees\phase1-5-t02-t04-asr-gates-exec`，仅复核既有本地 FunASR 1.3.22、ModelScope 1.38.1、Python 3.10.19、CPU 架构及 `iic/SenseVoiceSmall`。G1 为 `BLOCKED`：20 个模型文件共 940019376 字节，现有清单 SHA-256 复核 20/20 一致（`model.pt` 为 `833ca2dcfdf8ec91bd4f31cfac36d6124e0c459074d5e909aec9cabe6204a3ea`），但下载日志仅记录可变引用 `iic/SenseVoiceSmall@master`，`configuration.json` 和限定本地缓存扫描均不能提供可信 immutable commit/revision；未下载、联网查询或猜测，因此 T02 不得升级。G2 为 `BLOCKED`：当前进程无管理员权限，Domain/Private/Public profile 均为禁用；精确规则名 `AIStudyBuddy-T04-ASR-Gates-20260722` 前后均为 0，未尝试创建、删除或修改 Firewall 规则，没有用 offline/cache-only 环境变量替代，也没有实际 ASR-under-Firewall 证据；因规则从未创建，无需回滚且终态无残留。G3 为 `BLOCKED` / `NOT_RUN`：按 G1/G2 停止条件未启动模型，本轮 ASR 样例执行数为 0；既有安全合成证据仍为静音 3/3、轻噪 3/3 均产生非空误转写，no-speech 门禁未关闭，清晰中文与中英混合 3/3 稳定、损坏 WAV `AUDIO_DECODE_FAILED`、非音频 `AUDIO_FORMAT_UNSUPPORTED`、受控超时 `PROCESS_TIMEOUT` 仅作为既有证据引用，候选 Python/FFmpeg/FFprobe 残留进程为 0。结构化证据位于 `I:\ai-studybuddy-composer\asr\T04-next-capability\metrics\gates-remediation\`、`shared\gates-remediation-summary.json`、`shared\results\gates-remediation-results.jsonl`、`logs\gates-remediation-audit.log` 及更新后的 `shared\COMPONENT-CARD.md`。总体为 `BLOCKED` 且无新增 `FAIL`；T02 `PARTIAL`、T03 `PASS`、T04 `PARTIAL`、T05/T06 `NOT_STARTED`。本轮未下载模型、未调用 Provider、未新增 ASR 执行、未修改 Firewall 或 `packages/`，未触碰 `AuralConverter`，未启动 T05/T06；能力验证结果不等于 ASR/S7 完成或生产接入资格。

> **Phase 1.5-T02/T04-R2 ASR 当前候选最小化修正计划（2026-07-22，fresh-pass 完成，已获明确执行批准）**：用户认可将 Claude 的多候选研究建议收敛为“1 个现有 ASR + 1 个 VAD + 2 个固定快照 + 3 个门禁 + 16 个核心运行 + 1 次 Firewall 生命周期 + 1 份报告”。计划分支 `codex/phase1-5-t02-t04-asr-minimal-remediation-plan` 从 `origin/master` `bd7cf7c996f3ad82fa627d43d28e0f9740ba9dbd` 创建，计划路径 `.plans/phase1-5-t02-t04-asr-minimal-remediation-plan.md`。计划仅允许未来获批后重新取得固定 revision 的 `iic/SenseVoiceSmall` 和 FSMN-VAD，在管理员提供已启用 Firewall profile 的前提下，以临时、命名、目标 Python 进程范围规则完成真实离线隔离，并运行静音 3、轻噪 3、清晰中文 3、中英混合 3、损坏 WAV 1、非音频 1、受控超时 1、清理检查 1。计划不预设 VAD 是唯一根因，不允许矩阵中逐样例调参，不比较 Paraformer/faster-whisper/whisper.cpp/sherpa-onnx，不运行长音频或真实课堂录音，不修改 `packages/`、Schema、API、Worker、前端或 shared 类型，不创建 `AuralConverter`，不启动 T05/T06。本轮计划阶段只创建计划和任务登记；用户随后已于 2026-07-22 明确批准模型获取、管理员 Firewall 和 ASR 矩阵，但实际执行仍必须满足计划规定的环境硬前置条件。
> **Phase 1.5-T02/T04-R2 执行前置审计（2026-07-22，`BLOCKED`）**：执行分支 `codex/phase1-5-t02-t04-asr-minimal-remediation-exec` 从 `origin/master` `e88d5a4921c7381eba43e268eb6281872f9a09a7` 创建，隔离 worktree 为 `I:\ai-studybuddy-tmp\worktrees\phase1-5-asr-minimal-remediation-exec`。用户已明确批准执行，但只读 preflight 确认当前进程 `isAdministrator=false`，Domain/Private/Public 三个 Windows Firewall profile 的 `Enabled` 均为 `false`；Firewall 服务运行中，但有效 profile 数为 0。既有候选 Python `I:\ai-studybuddy-composer\asr\FunASR\.venv\Scripts\python.exe` 存在且当前匹配运行进程数为 0，命名任务规则残留数为 0。正式计划第 5.2 节要求“已提升管理员 PowerShell + 至少一个已启用 profile”，不满足即 `G2=BLOCKED` 并停止，因此本轮未创建/删除 Firewall 规则、未下载 SenseVoiceSmall/FSMN-VAD、未猜测 revision、未执行 16 项矩阵，也未修改永久 Firewall 策略或使用 offline/cache-only 替代。结构化证据位于 `I:\ai-studybuddy-composer\asr\T04-next-capability\metrics\minimal-remediation\preflight-20260722-205151-ac5424\`。本轮 G1=`NOT_STARTED`、G2=`BLOCKED`、G3=`NOT_RUN`，总体 `BLOCKED`；T02 `PARTIAL`、T03 `PASS`、T04 `PARTIAL`、T05/T06 `NOT_STARTED`。能力验证结果不等于生产接入资格。下一次重试必须从已提升的管理员会话启动，并由管理员在任务开始前启用至少一个适用 Firewall profile；本任务仍只允许创建和回滚临时命名出站阻断规则。

> **Phase 1.5-T02/T04-R2 G1/G3 最小化修正执行（2026-07-22，`PARTIAL`）**：用户明确批准在定制版 Windows 10 无可用 Firewall profile 的条件下调整执行顺序，允许先完成 G1/G3，同时要求 G2 保持 `BLOCKED`、不修改永久 Firewall 策略、不以弱化证据冒充 `PASS`。运行 `minimal-remediation-20260722-220554-e937e8` 已完成：G1=`PASS`，从 ModelScope 官方 Git 核对并以完整 commit hash 显式下载新隔离快照，SenseVoiceSmall revision=`7bf452403abd7353a300cd760f7adae7701c92c1`、FSMN-VAD revision=`f9a8b8274674755d925277e27063869038d41515`，逐文件 SHA-256、版本、架构、来源和许可证记录已生成；G3=`PASS`，固定参数 16/16 矩阵符合预期，静音与轻噪各 3/3 均为结构化 `NO_SPEECH`、VAD 段数 0、文本长度 0，清晰中文与中英混合各 3/3 非空且短哈希稳定，损坏 WAV、非音频、受控超时和清理检查均得到预期结果。G2=`BLOCKED`：管理员会话下 Domain/Private/Public profile 仍全部禁用，未创建规则、未修改永久策略，运行前后命名规则残留均为 0，offline/cache-only 只用于缓存安全且不计为隔离证据。后置清理确认目标 Python 残留 0、运行临时目录清空、命名 Firewall 规则残留 0。结构化证据位于 `I:\ai-studybuddy-composer\asr\T04-next-capability\metrics\minimal-remediation\minimal-remediation-20260722-220554-e937e8\`，组件卡已更新。总体=`PARTIAL`，不宣称三个门禁全部关闭；T02 `PARTIAL`、T03 `PASS`、T04 `PARTIAL`、T05/T06 `NOT_STARTED`。能力验证结果不等于生产接入资格。

> **Phase 1.5-T02/T04-G2 跨平台离线门禁语义修订计划（2026-07-22，fresh-pass `PASS`，正式采用/执行待批）**：用户已明确批准创建独立纯计划任务，将 G2 从绑定单一 Windows 机制的“Windows Firewall 离线隔离门禁”修订为“可验证的操作系统级离线隔离门禁（Verifiable OS-level Egress Isolation）”。计划分支 `codex/phase1-5-asr-g2-cross-platform-gate-plan` 从最新 `origin/master` `ad5a90ff410a7f5194cf1274b6807227620b00a7` 创建，计划路径 `.plans/phase1-5-t02-t04-asr-g2-cross-platform-egress-isolation-plan.md`。计划只定义统一强证据契约以及标准 Windows、Linux network namespace/nftables、Docker `--network none`、独立虚拟机和其他 OS/虚拟化强制机制的等价边界；offline/cache-only、DNS、hosts 或代理配置不能单独作为 G2 `PASS`。当前定制 Windows 缺少可用 Firewall profile 的事实在未来正式采用新语义后分类为 `ENVIRONMENT_UNAVAILABLE / DEFERRED`，但既有 `G2=BLOCKED` 记录保持历史事实，跨平台 G2 仍待补，不得写成 `PASS`。本轮不执行模型下载或 G1/G3/G2，不修改 `packages/`、业务代码、Schema、API、Worker、前端、shared 类型或正式架构/测试 SoT，不启动 T05/T06；T02/T04 保持 `PARTIAL`，能力验证结果不等于生产接入或生产发布资格。
> **Phase 1.5-T02/T04-G2 正式语义落地计划（2026-07-22，fresh-pass `PASS`，已合入 `origin/master`）**：计划提交 `0b6e2b360c4a8464b59cc8ab3833264706703c23` 已 fast-forward 合入并推送 `origin/master`。计划路径 `.plans/phase1-5-t02-t04-asr-g2-semantics-adoption-plan.md` 规定将平台无关的强制出站隔离证据语义同步到 `docs/08`、`docs/09`、S7 PRD 与本文件的顺序、统一措辞、历史状态保留、文档验证与停止边界。

> **Phase 1.5-T02/T04-G2 正式语义同步（2026-07-23，文档分支 `codex/phase1-5-asr-g2-semantics-adoption-docs`，主线合入待批准）**：用户已明确批准同步三个 SoT 与本文件。G2 现在定义为“可验证的操作系统级离线隔离门禁（Verifiable OS-level Egress Isolation）”：ASR 出站必须由 OS、容器或虚拟化层在进程外强制隔离；Windows Firewall 是可接受实现之一而不是产品运行依赖；`offline`/cache-only、DNS、hosts、代理或人工断网不能单独构成 `PASS`。任一 `PASS` 只对证据所述的平台、OS/运行时版本、架构和隔离实现有效，必须同时保留外部强制、审计/清理/回滚和隔离下结构化本地 ASR 正向证据。旧 Windows `G2=BLOCKED` 仍为历史事实；环境不可用可标记 `ENVIRONMENT_UNAVAILABLE`/`DEFERRED`，但不是 `PASS`。本轮没有运行任何隔离、模型、G1/G3、ASR/FFmpeg 或 Provider 验证，也没有创建 `AuralConverter`、修改产品代码或启动 T05/T06；G1/G3=`PASS`、T02/T04=`PARTIAL`、T03=`PASS`、T05/T06 未启动均不变。文档同步不等于能力验证、产品接入或生产发布资格。

## Phase 2：期末冲刺（S5）

**目标**：围绕已确认考试完成模拟考、临考速背、冲刺计划与考试工作台冲刺区闭环。

**完成状态**：Phase 1 的 S3 练习与 S4 错题门禁已满足；T01–T06 均已分别完成计划、审查、用户批准、实现、主线复验和 `origin/master` 推送。

| 顺序 | 任务                      | 状态 | 单一责任                                                                                                                                                                                                                                                        |
| ---- | ------------------------- | ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | T01：S5 PRD 编写          | ✅   | 已按门禁审计和用户明确批准创建 `docs/subsystems/08-S5-期末冲刺子系统PRD-ExamCrammer.md`；仅文档，不含 Schema/API/Worker/前端实现                                                                                                                                |
| 2    | T02：模拟考 Schema 与生成 | ✅   | 已完成并 fast-forward 合入 `master`；功能实现提交 `bb0caf5`，本次状态标记提交 `213ebb9`，均已推送 `origin/master`；AI 根据考试上下文和知识模块生成模拟卷，支持计时尝试、提交批改与模块分析                                                                      |
| 3    | T03：模拟考前端           | ✅   | 已 rebase 至最新 `master` 并 fast-forward 合入；主线类型检查、构建、全量测试与本地浏览器验收通过，已随本轮文档收尾提交推送 `origin/master`                                                                                                                      |
| 4    | T04：临考速背             | ✅   | 已 rebase 至最新 `origin/master` 并 fast-forward 合入；主线类型检查、构建、全量测试与本地浏览器验收通过，已随本轮文档收尾提交推送 `origin/master`                                                                                                               |
| 5    | T05：冲刺计划生成         | ✅   | 已基于执行时最新 `origin/master` `a5c1efde20a29eb85da5431e8b683d8084dc05d6` 完成 rebase（无需重放）并 fast-forward 合入 `master`；主线类型检查、双端构建、全量测试及 Chromium 3/3 验收通过，随本次文档收尾提交推送 `origin/master`。不含 T06 工作台冲刺区       |
| 6    | T06：工作台”冲刺”区集成   | ✅   | 已 fast-forward 合入 `master`；主线类型检查、双端构建、全量测试（frontend 137/137、backend 237/237）与 Chromium 1/1 验收通过，实现链及本次最终文档收尾均推送 `origin/master`。不含后端、Schema/migration、持久化、AI/Provider、Worker、StudyEvent 或 S3/S4 写回 |

### Phase 2 任务状态索引

| 任务 | 计划文件                                          | 计划/实施状态                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ---- | ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T01  | `.plans/phase2-t01-s5-prd-plan.md`                | 已完成：计划已创建并完成门禁审计；用户于 2026-07-20 明确批准创建 S5 PRD；本文档任务已创建 `docs/subsystems/08-S5-期末冲刺子系统PRD-ExamCrammer.md` 并同步 `docs/00`。                                                                                                                                                                                                                                                                                                             |
| T02  | `.plans/phase2-t02-s5-mock-exam-schema-plan.md`   | 用户已于 2026-07-20 明确批准进入实现；任务分支 `codex/phase2-t02-s5-mock-exam-schema` 已完成分支实现、fast-forward 合入 `master` 并完成主线复验；`origin/master` 已推送。                                                                                                                                                                                                                                                                                                         |
| T03  | `.plans/phase2-t03-s5-mock-exam-frontend-plan.md` | 用户于 2026-07-20 明确批准进入实现；任务分支 `codex/phase2-t03-s5-mock-exam-frontend` 已 rebase、fast-forward 合入 `master` 并完成主线复验，随文档收尾提交推送 `origin/master`。范围为 T02 API/DTO 消费、模拟考入口/答题/提交/结果/模块分析、刷新恢复、失败和重复提交；未实现 T04–T06、S7 或 S3 Worker。                                                                                                                                                                          |
| T04  | `.plans/phase2-t04-s5-cram-plan.md`               | 用户于 2026-07-21 明确批准进入实现；任务分支 `codex/phase2-t04-s5-cram` 已基于 `origin/master` `439d6ad84169d7ddb1e88347ccc9963fd01bfeea` rebase 并 fast-forward 合入 `master`。主线已验证确定性只读速背卡 API/DTO/Service、独立前端页面、总倒计时、安全恢复及本地 Chrome 验收；主线实现与收尾提交已推送 `origin/master`。不实现 T05–T06、S7、S3 Worker、Schema/migration、Worker、真实 AI 或外部调用。                                                                           |
| T05  | `.plans/phase2-t05-s5-cram-plan-plan.md`          | 用户已明确批准实施与主线合入；实施分支 `codex/phase2-t05-s5-cram-plan` 的最终实现提交 `a985ad5063295a482271a671c09666a972b737ed` 已基于最新 `origin/master` 完成 rebase（无需重放）并 fast-forward 合入 `master`。主线复验通过类型检查、两项生产构建、全量测试（frontend 131/131、backend 237/237）及 Chromium 3/3，随本次文档收尾提交推送 `origin/master`。范围保持确定性、即时、只读；不实现 T06、S7、S3 Worker、AI/Provider、持久化计划或外部 smoke。                          |
| T06  | `.plans/phase2-t06-s5-workbench-cram-plan.md`     | 用户于 2026-07-21 明确批准实施、测试、主线合入与推送；任务分支 `codex/phase2-t06-s5-workbench-cram` 已完成实现与分支验证，并以 fast-forward 方式合入 `master`。主线复验通过，计划提交 `a709237`、实现提交 `911337b`、分支证据提交 `593c426` 已推送 `origin/master`，最终完成状态随本次文档收尾提交再次推送。范围仅复用 T04/T05 既有 GET API 与独立页面，集成只读摘要、深链、降级和跨考试清理；不新增后端、DTO、Schema/migration、持久化、AI/Provider、Worker、StudyEvent 或写回。 |

> **Phase 2-T05 门禁审计与行动计划证据（2026-07-21，计划已创建，未实施）**：已在工作区内容哈希与 `HEAD`/索引一致、Git 状态缓存刷新后，从最新 `origin/master` @ `a5c1efde20a29eb85da5431e8b683d8084dc05d6` 创建计划分支 `codex/phase2-t05-s5-cram-plan-plan`，登记 `.plans/phase2-t05-s5-cram-plan-plan.md`。门禁审计确认 T02 模拟考 Schema 与生成、T03 模拟考前端和 T04 临考速背均已完成主线复验并推送；T05 只计划确定性即时只读、未来 7 天、已确认考试上下文内的每日建议 API 与独立页面，读取同学期同课程的 S1 未完成任务、S3 练习表现、S4 错题/薄弱点及既有速背入口，不改写 S3/S4 事实。计划明确不新增 Schema/migration、持久化 CramPlan、建议完成写入、StudyEvent、AI/Provider、Worker 或 T06 工作台“冲刺”区；fresh-pass 审查已完成且无阻塞项；文档治理检查和 diff 检查通过后，计划分支仅提交并推送等待用户明确批准。业务代码、实现测试、浏览器验收、合入 `master` 和推送 `origin/master` 均未开始。

> **Phase 2-T06 门禁审计与行动计划证据（2026-07-21，计划待用户明确批准）**：已从最新 `origin/master` `366893b40133da2e02e5f19895b73bd6d0052bac` 创建计划分支 `codex/phase2-t06-s5-workbench-cram-plan`，登记 `.plans/phase2-t06-s5-workbench-cram-plan.md`。门禁审计确认 T05 已完成并位于 `origin/master`；T06 单一责任仅为把既有 T04 确定性只读速背卡与 T05 确定性即时只读冲刺计划集成进考试工作台“冲刺”区域，展示状态摘要、入口和降级提示，不复制完整独立页面。fresh-pass 审查通过：计划不新增后端接口、Schema/migration、持久化 CramPlan、StudyEvent、AI/Provider、Worker、S3/S4 写回、建议完成反馈或新的计划生成能力；业务实现、实现测试、浏览器验收、S7、S3 Worker、外部 smoke、合入 `master` 和推送 `origin/master` 均未开始。

> **Phase 2-T06 任务分支实现证据（2026-07-21，待主线合入）**：用户已明确批准按 `.plans/phase2-t06-s5-workbench-cram-plan.md` 进入实现、验证、提交、fast-forward 主线合入和推送。任务分支 `codex/phase2-t06-s5-workbench-cram` 的实现提交 `911337bb654cddbe0279329a07ec2ba8e369c031` 仅修改考试工作台页面、全局样式、工作台组件测试和既有 Playwright 工作台用例：复用 T05 `GET /api/assessment-attempts/:id/cram-plan`，只为已确认考试读取冲刺窗口、距考试天数、建议天数/数量和最高优先级脱敏原因；提供 T04 临考速背与 T05 完整冲刺计划深链；明确处理未确认、加载、未开始、已结束、空建议、局部失败重试和跨考试旧摘要清理，并在任务创建或状态更新后刷新只读摘要。分支验证均退出码 0：`pnpm type-check`；后端与前端生产构建；隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase2-t06-workbench-cram-20260721-branch-full` 的 `pnpm test`（frontend 137/137、backend 237/237）；工作台组件测试 20/20；隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase2-t06-workbench-cram-20260721-2308` 的 Chromium `e2e/exam-workbench.spec.ts` 1/1，验证摘要刷新、两条深链、cram-plan 请求仅为 GET、390×844 入口可操作且无页面横向溢出，截图留在仓库外隔离目录。当前仍是任务分支完成态，尚未 fast-forward 合入 `master`、尚未完成主线复验或推送 `origin/master`，因此 T06 不标记完成。未修改后端、shared DTO、T04/T05 Service、Schema/migration、数据库或路由；未新增写 API、CramPlan 持久化、建议完成反馈、StudyEvent、AI/Provider、Worker、S3/S4 写回、S7、S3 Worker 或真实外部 smoke；未读取、输出或持久化真实题干、答案、作答、错因正文、资料原文、Provider 信息、秘密或正式运行数据。

> **Phase 2-T06 主线完成证据（2026-07-21，已 fast-forward 合入 master 并推送 origin/master）**：任务分支 `codex/phase2-t06-s5-workbench-cram` 已包含计划提交 `a709237d17d5ecf299ecb88e8b9348f7eb26f6bd`、实现提交 `911337bb654cddbe0279329a07ec2ba8e369c031` 与分支证据提交 `593c426dd9d2303bfe828f61dfe3af5a16056d99`，随后在干净的主线工作树 `I:\ai-studybuddy-tmp\worktrees\post-t12-m02-master-integration` 以 `git merge --ff-only codex/phase2-t06-s5-workbench-cram` 纳入 `master`，未产生 merge commit；首次推送后以 `git ls-remote --heads origin master` 确认 `origin/master` 指向 `593c426dd9d2303bfe828f61dfe3af5a16056d99`。主线复验均退出码 0：隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase2-t06-workbench-cram-20260721-master-full` 的 `pnpm type-check`、`pnpm -r --filter backend run build`、`pnpm -r --filter @ai-studybuddy/frontend run build` 与 `pnpm test`（frontend 137/137、backend 237/237）；隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase2-t06-workbench-cram-20260721-master-browser` 的 Chromium `e2e/exam-workbench.spec.ts` 1/1，验证只为已确认考试加载只读摘要、任务创建/状态更新后的摘要刷新、T04 `/exams/:examId/cram` 与 T05 `/exams/:examId/cram-plan` 深链、cram-plan 请求全部为 GET，以及 390×844 下单列布局、全宽入口和无页面横向溢出。实现仅修改工作台页面、全局样式及对应组件/浏览器测试；未修改后端、shared DTO、T04/T05 Service、Schema/migration、数据库或路由，未新增写 API、持久化计划、建议完成反馈、StudyEvent、AI/Provider、Worker、S3/S4 写回、S7、S3 Worker 或真实外部 smoke，未读取、输出或持久化真实题干、答案、作答、错因正文、资料原文、Provider 信息、秘密或正式运行数据。最终文档治理、未暂存差异与缓存区差异检查通过后，本完成状态随本次文档收尾提交再次推送 `origin/master`。

> **Phase 2-T01 文档完成证据（2026-07-20，已获用户明确批准）**：用户在计划提交后明确要求创建 `docs/subsystems/08-S5-期末冲刺子系统PRD-ExamCrammer.md`，并同步 `docs/00` 与本文件的 Phase 2-T01 文档完成状态。本轮创建 S5 轻量 PRD，定义模拟考、临考速背、冲刺计划、考前工作台入口、AI/规则边界、概念数据对象、产品表面、验收标准和 T02–T06 独立门禁；同步 `docs/00` 将 S5 PRD 登记为有效文档。验证：`powershell -ExecutionPolicy Bypass -File scripts/check-docs-governance.ps1`、`git diff --check`、`git diff --cached --check` 均通过。未实现 Phase 2-T02–T06、Schema、API、Worker、前端、S3 Worker 或 S7；未运行真实 AI、QQ SMTP、飞书、中转站或其他外部 smoke；未读取、输出或持久化真实秘密。

> **Phase 2-T02 门禁审计与行动计划证据（2026-07-20，计划已创建并获批）**：已从最新 `origin/master` 创建任务分支 `codex/phase2-t02-s5-mock-exam-schema`，确认 S5 PRD 已存在，且 S3/S4 稳定运行门禁仍有效；已登记 `.plans/phase2-t02-s5-mock-exam-schema-plan.md`。本计划覆盖模拟卷、模拟考尝试、成绩统计、模块分析的概念边界、考试范围/知识模块/错题与薄弱点/考试上下文输入依赖、S3/S4 只读复用、隐私和真实 Provider 边界，以及与 T03–T06 的责任切分。用户已于 2026-07-20 明确批准进入 T02 业务实现；执行期间用户要求所有长命令/关键命令前必须说明当前步骤和目的，本分支已同步到 `AGENTS.md` 与 `docs/12-开发规范-Dev-Rules.md`。

> **Phase 2-T02 主线完成证据（2026-07-20，已 fast-forward 合入 master 并推送 origin/master）**：任务分支 `codex/phase2-t02-s5-mock-exam-schema` 已 fast-forward 合入 master，当前主线提交 `bb0caf5`。主线复验在 master worktree 通过：`pnpm type-check`；`pnpm -r --filter @ai-studybuddy/backend run build`；`pnpm -r --filter @ai-studybuddy/frontend run build`；`pnpm test`（backend 233/233，frontend 94/94）；`powershell -ExecutionPolicy Bypass -File scripts/check-docs-governance.ps1`；`git diff --check`。本轮仅完成 T02；未扩展到 T03–T06、模拟考前端、临考速背、冲刺计划、工作台集成、S3 Worker、S7、真实 AI/QQ SMTP/飞书/中转站/Windows 计划任务 smoke；未读取、输出或持久化真实秘密。
> **Phase 2-T04 门禁审计与行动计划证据（2026-07-21，计划已创建、已审查、待用户明确批准）**：已从最新 `origin/master` `439d6ad84169d7ddb1e88347ccc9963fd01bfeea` 创建隔离工作树和任务分支 `codex/phase2-t04-s5-cram-plan`，并登记 `.plans/phase2-t04-s5-cram-plan.md`。审计确认 T02 模拟考后端、T03 模拟考前端、S3 练习与 S4 错题可仅以既有契约只读复用；T04 首版计划限定为确定性即时速背卡片与整次限时翻阅，不新增 Schema/migration、Worker、写 API、真实 AI 或外部调用。独立审查确认未将 T04 扩展至 T05 冲刺计划、T06 工作台冲刺区、S7 或 S3 Worker，且计划/文档不包含真实题干、答案、错题原文、资料、秘密或正式运行数据。当前仅允许计划文档提交与推送；在用户明确批准前，不得修改任何 T04 业务代码、测试、API、DTO、Service、Schema 或前端页面。
> **Phase 2-T05 分支实施与验证证据（2026-07-21，实施分支历史证据）**：用户明确批准后，实施分支 `codex/phase2-t05-s5-cram-plan` 基于计划提交 `44c28443c61eeae356031ba9864be51f0f9043f6` 完成确定性、即时、只读的冲刺计划。新增 `GET /assessment-attempts/:id/cram-plan?semesterId=...`、shared 只读 DTO、后端 `CramPlanService`、独立考试上下文页面、API client 与“冲刺计划”导航入口；仅对同学期、同课程、已确认考试读取 S1 未完成任务、S3 已完成练习表现、S4 活跃薄弱点/错题及既有速背入口，按未来 7 天本地日历窗口返回 `available`、`not_started` 或 `ended`。API/DTO 不返回题干、正确答案、学生作答、错因正文、资料原文、Provider 信息或秘密；页面深链和人工入口仅导航，不写回任务、错题、模块或计划状态。验证均退出码 0：固定时钟的 T05 后端 API 集成测试、前端 API/页面/导航测试；隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase2-t05-cram-plan-readonly-final` 的 `pnpm type-check`、`pnpm -r --filter backend run build`、`pnpm -r --filter @ai-studybuddy/frontend run build` 与 `pnpm test`（frontend 131/131、backend 237/237）；隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase2-t05-cram-plan-readonly-final-browser` 的本地 Chromium Playwright `e2e/cram-plan.spec.ts` 3/3（正常建议与五类深链、未确认、窗口外、空建议、失败重试、考试切换清理、390px 窄屏和全部请求 GET）。fresh-pass 确认没有 Schema/migration、CramPlan 持久化、建议完成写入、StudyEvent、AI/Provider、Worker、S3/S4 历史回写或 `exam-workbench-page.tsx` 变更；T06 工作台“冲刺”区、S7、S3 Worker、真实 AI/外部 smoke 均未启动。该段记录分支实施时状态；后续主线合入与复验证据见下一段。
> **Phase 2-T05 主线完成证据（2026-07-21，已 fast-forward 合入 master 并随文档收尾推送 origin/master）**：合入前确认实施分支 `codex/phase2-t05-s5-cram-plan` 与指定提交 `a985ad5063295a482271a671c09666a972b737ed` 一致，工作区干净；fetch 后执行时最新 `origin/master` 为 `a5c1efde20a29eb85da5431e8b683d8084dc05d6`，rebase 无需重放。由于 `master` 已由干净 worktree `I:\ai-studybuddy-tmp\worktrees\post-t12-m02-master-integration` 持有，未删除或移动 worktree，而是在该主线 worktree 完成 `pull --ff-only` 与 `merge --ff-only`；合入后 HEAD 为单父提交 `a985ad5063295a482271a671c09666a972b737ed`，确认未产生 merge commit。主线复验均退出码 0：隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase2-t05-master-20260721-220158` 的 `pnpm type-check`、后端 build、前端 build 与 `pnpm test`（frontend 131/131、backend 237/237）；隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase2-t05-master-browser-20260721-220643` 的 Chromium `e2e/cram-plan.spec.ts` 3/3。fresh-pass 确认 T05 仍为确定性、即时、只读，只新增 GET API、共享安全 DTO、只读 Service、独立页面与导航；无 Schema/migration、CramPlan 持久化、建议完成写入、StudyEvent、AI/Provider、Worker、S3/S4 反写或 `exam-workbench-page.tsx` 变更，DTO/日志不含题干、正确答案、学生作答、错因正文、资料原文、Provider 信息或秘密。T06 工作台冲刺区、S7、S3 Worker、持久化计划及真实 AI/外部 smoke 仍未实现。
> **Phase 2-T04 分支实现与验证证据（2026-07-21，已获用户明确批准，尚未合入 master）**：用户明确批准后，已在隔离工作树 `I:\ai-studybuddy-tmp\worktrees\phase2-t04-s5-cram` 的任务分支 `codex/phase2-t04-s5-cram` 实现 T04 且保持单一责任：在既有已确认考试上下文内，用同学期同课程的 `weak_points`、`mistakes` 和 `knowledge_modules` 只读生成确定性速背卡，并提供独立入口、5/10/15 分钟（默认 10 分钟）整次总倒计时、翻转/键盘浏览、超时锁定切卡与 `sessionStorage` 按卡片 ID 安全恢复。后端复用 T02 的学期/课程/已确认考试校验，只新增只读 GET、共享安全 DTO 与查询方法；无 Schema/migration、写 API、Worker、Provider 配置、真实 AI 或外部调用。每知识模块最多一张，按活跃薄弱点、待复习错题、基础模块分层排序；仅白名单返回模块标题、重要性、安全摘要、考点与来源计数，绝不回传资料原文、`source_evidence`、题干、选项、正确答案、学生作答或错因备注。前端只消费 API，不读取 SQLite、文件目录或 Provider 配置；存储不含卡片正文、错题、答案、Provider 信息或秘密，存储损坏/不可用、数据变动、空态、未确认或跨学期考试、网络失败和 409 均安全降级或给出可行动中文反馈。验证（均退出码 0）：`pnpm type-check`；后端和前端生产构建；后端 T04 API 集成测试 2/2；前端 T04 专项测试 6/6；隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase2-t04-s5-cram-full` 的 `pnpm test`（backend 235/235）；隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase2-t04-s5-cram-browser` 的本地 Chrome/Vite Playwright `e2e/cram-cards.spec.ts` 1/1（开始、键盘翻阅、刷新恢复、超时锁定且仍可翻转、窄屏无横向溢出）。未扩展 T05 冲刺计划、T06 工作台冲刺区、S7 或 S3 Worker；未读取、输出或持久化真实题干、答案、错题原文、资料、秘密或正式运行数据；任务分支尚未合入或推送 `origin/master`。
> **Phase 2-T04 主线完成证据（2026-07-21，已 fast-forward 合入 master 并推送 origin/master）**：任务分支 `codex/phase2-t04-s5-cram` 已确认基于最新 `origin/master` `439d6ad84169d7ddb1e88347ccc9963fd01bfeea`（rebase 无需重放），随后在干净的 `master` 工作树以 `git merge --ff-only` 纳入；实现提交 `a902835`、分支状态同步提交 `44f018f` 已位于本地 `master`。主线复验均退出码 0：`pnpm type-check`；`pnpm -r --filter @ai-studybuddy/backend run build`；`pnpm -r --filter @ai-studybuddy/frontend run build`；隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase2-t04-master-final` 的 `pnpm test`（backend 235/235）；隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase2-t04-master-browser` 的本地 Chrome/Vite Playwright `e2e/cram-cards.spec.ts` 1/1（翻卡、键盘浏览、刷新恢复、超时锁定且保留翻转、窄屏无横向溢出）。文档治理、未暂存差异和缓存区差异检查均已在文档提交前通过。范围仅为 T04 确定性只读速背卡、独立页面和总倒计时；无 Schema/migration、写 API、Worker、真实 AI、Provider 配置或外部调用，未扩展 T05 冲刺计划、T06 工作台冲刺区、S7 或 S3 Worker，且未读取、输出或持久化真实题干、答案、错题原文、资料、秘密或正式运行数据。
> **Phase 2-T03 门禁审计与行动计划证据（2026-07-20，计划待用户明确批准）**：已从最新 `origin/master`（`769840ee71ada882c3bcec4fdde6224735272daf`）创建任务分支 `codex/phase2-t03-s5-mock-exam-frontend-plan`，审计确认 S5 PRD 已登记、T01/T02 已进入主线，且 T02 已提供模拟卷生成/详情、尝试创建/详情与提交批改五个 API 及对应学生安全 DTO。已创建并完成自审 `.plans/phase2-t03-s5-mock-exam-frontend-plan.md`，计划只定义未来的模拟考入口、答题、刷新恢复、提交、结果和模块分析前端闭环，以及测试和隔离浏览器验收；未发现用户明确批准进入 T03 前端实现。当前仅允许计划任务，T03 React 页面、路由、Hook、API 客户端、测试业务代码、后端、Schema、Worker、T04–T06、S7 和 S3 Worker 均未开始；未读取、输出或持久化真实秘密，未运行真实 AI、QQ SMTP、飞书、中转站、Windows 计划任务或其他外部 smoke。
> **Phase 2-T03 主线完成证据（2026-07-21，已 fast-forward 合入 master 并推送 origin/master）**：任务分支 `codex/phase2-t03-s5-mock-exam-frontend` 已先 rebase 至最新 `origin/master` `769840ee71ada882c3bcec4fdde6224735272daf`，再 fast-forward 合入 `master`；模拟考前端实现提交为 `e8f161b`，主线收尾提交 `bb8bf77` 已位于 `origin/master`。范围仅含 T03 的模拟考入口、模拟卷详情、作答、刷新恢复、提交、结果和模块分析页面、当前学期守卫路由、T02 五个既有 API/DTO 客户端、草稿恢复与完成态安全清理、前端/浏览器测试；未修改后端、Schema、DTO、Service、Worker、T04–T06、S7 或 S3 Worker。主线复验（退出码均为 0）：`pnpm type-check`；`pnpm -r --filter @ai-studybuddy/frontend run build`；隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase2-t03-master-final` 的 `pnpm test`（frontend 118/118、backend 233/233）；隔离 `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\phase2-t03-master-browser` 的本地 Chrome/Vite Playwright `e2e/mock-exam.spec.ts` 3/3（确认成功、未确认/提交失败恢复、409 冲突安全态）。未读取、输出或持久化真实秘密，未运行真实 AI、QQ SMTP、飞书、中转站、Windows 计划任务或其他外部 smoke。

---

## Phase 2.5：运行环境重启与 Windows 使用机器部署准备（完成，随本轮推送进入远端主线）

**目标**：在不扩大产品边界、不装配 S7 的前提下，恢复当前开发机的可重复运行环境，并形成可迁移到 Windows 使用机器的原生部署、数据保护和升级回滚基础。

**边界**：Express 仅监听 `127.0.0.1`；Docker/WSL 仅承担开发隔离与 G2/S7 能力验证；不修改全局防火墙；不引入真实 ASR、AuralConverter、S7 API/Worker/前端；不携带真实密钥、资料、数据库或运行缓存。

| 顺序 | 任务                                                      | 状态 | 单一责任                                                                                       |
| ---- | --------------------------------------------------------- | ---- | ---------------------------------------------------------------------------------------------- |
| 1    | PROCESS-RUNTIME-DEPLOY-01：开发环境重启与 OCR 运行时恢复  | ✅   | 固化 Python/OCR 依赖、隔离开发运行目录、开发机配置与 OCR smoke；不提交 `.env.local` 或模型缓存 |
| 2    | PROCESS-RUNTIME-DEPLOY-02：Windows 生产启动与静态资源服务 | ✅   | 前端静态产物由 Express 提供、SPA fallback、单进程生产启动、回环监听；不新增公网入口            |
| 3    | PROCESS-RUNTIME-DEPLOY-03：使用机器 bootstrap 与安装检查  | ✅   | `%LOCALAPPDATA%\AIStudyBuddy` 目录、venv、运行时检查、启停和只读安装检查；不依赖开发机盘符     |
| 4    | PROCESS-RUNTIME-DEPLOY-04：数据备份/恢复与升级回滚        | ✅   | SQLite/学期库/materials 白名单备份、hash 校验、非破坏性恢复、升级回滚与任务计划适配            |
| 5    | PROCESS-RUNTIME-DEPLOY-05：全新机器验收与部署文档         | ✅   | 部署包、兼容清单、验收矩阵、运维文档与分支/主线新鲜证据；不把 G2 结论写成产品部署结论          |

### Phase 2.5 行动计划索引

| 任务                      | 计划文件                                                       | 计划/实施状态                                                                                                                              |
| ------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| PROCESS-RUNTIME-DEPLOY-01 | `.plans/process-runtime-01-dev-ocr-recovery-plan.md`           | ✅ 已完成本地 master 合入复验；OCR smoke 与受控 Python/venv 证据齐全；随本轮 push 进入 `origin/master`                                     |
| PROCESS-RUNTIME-DEPLOY-02 | `.plans/process-runtime-02-production-host-plan.md`            | ✅ 已完成本地 master 合入复验；生产静态服务、SPA fallback、回环监听和启停 smoke 证据齐全；随本轮 push 进入 `origin/master`                 |
| PROCESS-RUNTIME-DEPLOY-03 | `.plans/process-runtime-03-bootstrap-install-check-plan.md`    | ✅ 已完成本地 master 合入复验；bootstrap、venv、check-installation 与受控运行时证据齐全；随本轮 push 进入 `origin/master`                  |
| PROCESS-RUNTIME-DEPLOY-04 | `.plans/process-runtime-04-backup-restore-upgrade-plan.md`     | ✅ 已完成本地 master 合入复验；备份/恢复 smoke、manifest hash、recovery-point 与 tmp/config 排除证据齐全；随本轮 push 进入 `origin/master` |
| PROCESS-RUNTIME-DEPLOY-05 | `.plans/process-runtime-05-deployment-validation-docs-plan.md` | ✅ 已完成本地 master 合入复验；部署包 20260723-6、部署文档、文档治理、diff check 与 E2E 证据齐全；随本轮 push 进入 `origin/master`         |

> **2026-07-23 启动记录**：本任务从最新 `origin/master` 创建独立 worktree `H:\ai-studybuddy\.worktrees\process-runtime-deployment` 与分支 `codex/process-runtime-deployment`。原分支 `codex/phase1-5-g2-wsl-isolation-exec` 的 G2 文档提交及未提交 `semester-access-service.ts` 修改均保持原样，未在本任务中覆盖。`master` 与 `origin/master` 基线一致；后续完成判定仍必须以主线复验和 `origin/master` 推送为准。

> **2026-07-23 分支验证证据（分支阶段）**：任务分支 `codex/process-runtime-deployment` 已完成 Windows 原生部署准备主体实现与分支验证：生产模式 Express 托管前端静态产物与 SPA fallback，API 保持 `/api` JSON 边界且仅监听 `127.0.0.1`；新增 bootstrap/start/stop/check/build package/backup/restore/OCR smoke/家长报告任务 wrapper 等脚本；OCR 依赖清单固定 `rapidocr-onnxruntime==1.4.4`，使用受控 Python/venv，不依赖模糊 PATH；最终部署包为 `H:\ai-studybuddy-tmp\runs\process-runtime-deployment-package-20260723-6` 与同名 zip，扫描确认未包含 `node_modules`、`.git`、`.env.local`、日志、tmp、models。分支验证退出码 0：`pnpm type-check`；`pnpm -r --filter backend run build`；`pnpm -r --filter @ai-studybuddy/frontend run build`；隔离 `APP_DATA_ROOT=H:\ai-studybuddy-tmp\runs\process-runtime-deployment-tests-20260723` 的 `pnpm test`（后端 242/242）；补装 Playwright Chromium 后，隔离 `APP_DATA_ROOT=H:\ai-studybuddy-tmp\runs\process-runtime-deployment-e2e-20260723` 的 `pnpm test:e2e`（21/21）；`H:\ai-studybuddy-runtime\install-test-20260723-5` 上 bootstrap/check/start/stop/OCR smoke 通过；`H:\ai-studybuddy-runtime\restore-smoke-20260723-5` 备份/恢复 smoke 通过，tmp/config 排除样本未进入 payload。详细证据见 `.plans/evidence/process-runtime-deployment-20260723.md`。本记录是分支阶段证据；最终完成以随后 master 合入复验、文档收口和 `origin/master` 推送确认为准。

> **2026-07-23 master 合入复验证据与推送收口**：已在独立集成 worktree `H:\ai-studybuddy-worktrees\process-runtime-master-integration-20260723` 将 `codex/process-runtime-deployment` 以 fast-forward 方式合入本地 `master`；当前 master 提交为 `99fdeb5`（计划提交 `4070b07` + 实现提交 `99fdeb5`）；最终远端主线事实以本轮 `git push origin master` 后的 `git ls-remote --heads origin master` 确认为准。主线复验使用隔离目录 `APP_DATA_ROOT=H:\ai-studybuddy-tmp\runs\process-runtime-deployment-master-tests-20260723`：`pnpm type-check`、`pnpm -r --filter backend run build`、`pnpm -r --filter @ai-studybuddy/frontend run build`、`pnpm test` 均 exit 0，后端测试 242/242 通过；首次主线复验因 `H:\.pnpm-store` 文件复制 EPERM 停在依赖安装阶段，已改用隔离 pnpm store `H:\ai-studybuddy-tmp\runs\process-runtime-pnpm-store-20260723` 重新安装依赖后通过。浏览器 E2E 使用 `APP_DATA_ROOT=H:\ai-studybuddy-tmp\runs\process-runtime-deployment-master-e2e-20260723`，`pnpm test:e2e` 21/21 通过。`scripts/check-docs-governance.ps1` 与 `git diff --check` 均通过。本地 master 复验仍不改变非目标：不接入 S7/ASR 产品链路，不修改 Firewall，不携带真实密钥/数据，不把 Docker/WSL 作为使用机器常驻产品依赖。

> **2026-07-24 远端主线确认**：`git push origin master` 与随后实时 `git ls-remote --heads origin master` 校验通过；Phase 2.5 运行环境重启与 Windows 使用机器部署准备已进入远端主线。因提交自身会改变 Git 哈希，文档不写死“最终哈希”，以交付说明中的实时 `git ls-remote` 输出为准。主仓库 `H:\ai-studybuddy` 仍停留在 `codex/phase1-5-g2-wsl-isolation-exec`，未提交的 `packages/backend/src/services/semester-access-service.ts` 仍未被本轮夹带。

> **PROCESS-RUNTIME-06 PowerShell 兼容与恢复可写性候选收口（2026-07-25，已完成主线复验并推送 `origin/master`）**：用户已明确要求处理 `9ed5bc1` 部署修复候选。任务分支 `codex/process-post-s7-docs-deploy-candidate-fix` 从最新 `origin/master` 创建，以 cherry-pick 审计方式纳入候选中仍有效的 PowerShell 5.1 兼容、运行时 helper、备份相对路径和恢复只读属性修复；同时保留主线 Node 24-only 部署基线，不恢复旧的 Node 20/22/24 宽松范围。提交 `b72e8b0 fix(deploy): 修复 PowerShell 兼容与恢复可写性` 已进入 `origin/master`，因此 `9ed5bc1` 不再是未处理候选。验证通过：部署 PowerShell 兼容专项 `node --test packages/backend/test/deployment-powershell-compatibility.test.mjs`（6/6）、`pnpm type-check`、backend build、frontend build、隔离 `APP_DATA_ROOT=H:\ai-studybuddy-tmp\runs\process-post-s7-docs-deploy-candidate-master-tests-20260725` 下 `pnpm test`（backend 251/251）、`scripts/check-docs-governance.ps1`、`git diff --check`。首次未设置 `APP_DATA_ROOT` 的 `pnpm test` 因 `[CONFIG] MISSING_ENV APP_DATA_ROOT` 停止，已按规则用隔离目录重跑通过。本轮不处理用户电脑实机验收、`9ed5bc1` 之外的部署候选、G2/Firewall、Docker/WSL、真实 Provider、QQ SMTP、飞书、完整 S7 或 Phase 3 业务实现。

> **2026-07-24 开发机 Windows 原生 + Node 24 运行时基线（开发机基线已验证并推送 `origin/master`；非用户机验收）**：计划 `.plans/process-dev-machine-windows-node24-runtime-baseline-plan.md` 已由任务分支 `codex/process-dev-machine-node24-runtime-baseline` fast-forward 合入独立主线集成 worktree `H:\ai-studybuddy-worktrees\process-runtime-master-integration-20260723`；原主工作区的未提交学期版本 8/9 改动及 S7/G2 文档未被覆盖。新的干净部署包 `H:\ai-studybuddy-tmp\runs\dev-machine-node24-baseline-master-20260724-01\deployment-package-node24-master` 在新的独立安装根 `H:\ai-studybuddy-runtime\dev-machine-node24-baseline-master-20260724-01` 中完成 `bootstrap-runtime.ps1` → `check-installation.ps1` → `test-ocr-runtime.ps1` → `start-production.ps1`（仅 `127.0.0.1:30127`）→ `/api/health` → `stop-production.ps1` → 脱敏数据安全检查；构建、bootstrap、安装检查、修正后的 OCR、停止和安全检查均为 exit `0`。启动脚本已输出本机回环地址；其日志包装因后台 Node 继承输出句柄超时，故以独立 `/api/health` 的 `success=true` 与停止后无 PID/关联 Node 残留确认启动/停止结果。Node 为 `v24.14.0`，Python 为 `3.10.19 x64`，OCR 合成中文 smoke 通过；主线 `pnpm type-check`、后端/前端构建、`pnpm test`（242/242）、文档治理和 `git diff --check` 均 exit `0`。当前运行时事实和命中的部署脚本已收紧为仅 Node 24；脱敏证据见 `.plans/evidence/process-dev-machine-node24-baseline-20260724-01.md`。**用户电脑安装运行仍为待目标机器到位后的独立实机验收门禁，当前不得宣称完成；ASR / Docker / WSL 继续独立暂缓，未进入产品实现。**

---

## Phase 3：打磨与安全（高权重必做项恢复规划中）

**状态**：用户于 2026-07-28 明确撤销 2026-07-27 的全面暂停决定，授权重新开放 Phase 3，但只恢复“必须做且高权重”的工作。T02A–T02G 已各自完成主线复验并进入 `origin/master`；T02G 只完成仓库外合成夹具安全边界和 P1 修复，真实 ACL、真实备份/恢复、总体审计与其余候选工作仍未完成。新的高权重恢复计划已创建，等待独立审查与用户对计划内容的实施确认；本轮尚未开始业务实现。

**恢复范围门禁**：仅规划 T02-R1、T02-R2、T04-1～T04-3、T02-R3、T05-1～T05-3、T02-R4、T02-R6 共 11 个高权重必做项，按 Wave 0～4 顺序执行。T01、T02-R5、T03 和所有条件触发项不在本轮实施范围；继续保持“家长不登录、无公网入口、无家长 Web 面板”的边界。不得把既有计划、单个切片、合成夹具证据或分支提交外推为 T02、Phase 3、真实机器操作、生产上线或用户电脑验收完成。

### Phase 3 高权重恢复行动计划索引

| 计划                                                                | 文件                                                                                 | 状态                                                                                                                                                                                                                                                |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PHASE3-REOPEN-HIGH-WEIGHT-20260728                                  | `.plans/phase3-reopen-high-weight-20260728-plan.md`                                  | 📝 已创建，待独立审查与实施确认；仅计划/清单同步，未开始实现                                                                                                                                                                                        |
| PHASE3-T02-COMMON-TRUSTED-APPROVAL-NOFOLLOW-IMPLEMENTATION-20260728 | `.plans/phase3-t02-common-trusted-approval-nofollow-implementation-20260728-plan.md` | ✅ 已完成共同接口与合成测试、最终独立审查（P0=0、P1=0）、主线复验并推送 `origin/master`；无 production trust anchor、production 仍固定 fail-closed；不授权真实 R1/R2                                                                                |
| PHASE3-T02-PRODUCTION-TRUST-ANCHOR-RELEASE-INTEGRITY-PLAN-20260728  | `.plans/phase3-t02-production-trust-anchor-release-integrity-20260728-plan.md`       | ✅ 计划已独立审查通过（P0=0、P1=0）；只定义最小前提，计划本身未写入真实三元组或授权 R1/R2                                                                                                                                                           |
| PHASE3-T02-PRODUCTION-TRUST-ANCHOR-RELEASE-INTEGRITY-20260728       | `.plans/phase3-t02-production-trust-anchor-release-integrity-20260728-plan.md`       | ✅ 最小共同接口与合成测试、首轮 P1 最小修复、第二次独立源码复审（P0=0、P1=0）及主线复验均已在此前提交进入 `origin/master`；截至 `28aa2931`，`origin/master` 已包含该实现及其验证记录；production 仍固定 fail-closed，未配置真实三元组、未接入 R1/R2 |
| PHASE3-PERSONAL-MINIMUM-REBASELINE-20260729                         | `.plans/phase3-personal-minimum-rebaseline-20260729-plan.md`                         | ✅ 已独立审查通过（P0=0、P1=0）；用户已于 2026-07-28 采用个人版最小闭环；当前仅按既有 11 项的 P1～P5 顺序制定实施计划，不授权真实操作；T01、T02-R5、T03、T05-4 仅为未来候选，不因本计划自动纳入                                                     |
| PHASE3-P1-R1-R2-CONTROLLED-READONLY-PLAN-20260728                   | `.plans/phase3-p1-r1-r2-controlled-readonly-20260728-plan.md`                        | ✅ 已独立审查通过（P0=0、P1=0）；仅为 T02-R1/T02-R2 制定同一准备窗口的最小受控只读实施计划，不实施、不运行真实操作                                                                                                                                  |
| PHASE3-P1-R1-R2-CONTROLLED-READONLY-IMPLEMENTATION-20260728         | `.plans/phase3-p1-r1-r2-controlled-readonly-20260728-plan.md`                        | ✅ 共同 synthetic-only 受控只读接口、合成验证与最终独立源码审查均完成（P0=0、P1=0）；未运行真实 R1/R2、未读取真实目标，production verifier 仍固定 fail-closed                                                                                       |

> **PHASE3-P1 R1/R2 共同受控只读接口与合成测试（2026-07-28，已完成分支验证与独立源码审查）**：实施分支 `codex/phase3-p1-r1-r2-controlled-readonly-implementation` 仅修改 `.plans/`、`docs/04`、R1 synthetic-only boundary 与合成测试、R2 synthetic-only 证据函数、两个无真实目标参数的 runner 及合成 PowerShell 测试。R1 仅接受模块私有 `WeakSet` 登记的纯内存 reader，外部 reader 在打开前固定拒绝；R2 仅在 `-SyntheticFixture` 下使用内存证据，固定六类逻辑类别并对卷、reparse、身份、deny/继承/有效访问及前后变化 fail-closed。已通过 R1/no-follow/测试隔离定向测试 15/15、R2 synthetic 测试、`pnpm type-check`、后端/前端 build、隔离 `APP_DATA_ROOT` 下 `pnpm test`（后端 315/315）、文档治理和差异检查；最终独立源码审查结论为通过（P0=0、P1=0）。未运行真实秘密扫描或 ACL 读取，未读取真实候选包/审批/manifest/用户数据，未修改 production trust-anchor/verifier/no-follow gate、部署构建/manifest、T04/T05、备份恢复、ACL 修复、服务或计划任务。该完成不等于 T02、真实 R1/R2、用户机器验收或 Phase 3 完成；真实操作仍须逐项另行计划、审查和用户批准。

> **PHASE3-T02 主线脏状态归档（2026-07-29，已完成）**：主线 `H:\ai-studybuddy` 的未跟踪目录 `.trae-html-share-packages/` 与 `alpha-sprint-plan/` 已按用户明确批准完整移出主目录，归档到受控 `H:\backup\ai-studybuddy-archives\20260729-phase3-t02-master-untracked-archive` 批次。移动前已解析并校验源与目标路径；本任务未读取目录内容、未删除、未覆盖；移动后已确认两项源路径不再存在。可继续核验主线干净状态并快进集成本任务分支。

| 顺序 | 候选任务                                           | 状态 | 单一责任                                                                                                           |
| ---- | -------------------------------------------------- | ---- | ------------------------------------------------------------------------------------------------------------------ |
| 1    | T01：S6 后续产品形态重新决策（历史候选：家长面板） | ⏸️   | 不属于本轮 P1 高权重恢复范围；继续保持现有边界                                                                     |
| 2    | T02：安全与隐私基线审计                            | 📝   | T02A–T02G 已推送 `origin/master`；高权重恢复计划仅纳入 R1、R2、R3、R4、R6，等待审查与实施确认；R5 继续不在本轮范围 |
| 3    | T03：性能基线                                      | ⏸️   | 必做但不属于本轮 P1 高权重恢复范围；仍待未来独立计划                                                               |
| 4    | T04：备份与恢复                                    | 📝   | T04-1～T04-3 纳入高权重恢复计划，等待审查与实施确认                                                                |
| 5    | T05：日志规范化                                    | 📝   | T05-1～T05-3 纳入高权重恢复计划，等待审查与实施确认                                                                |

### Phase 3 完整任务树与准确计数（2026-07-28）

**先给结论**：Phase 3 有 **5 个大任务、28 个已定义小任务**。其中 **25 个是完成 Phase 3 必须完成的小任务，3 个是条件触发小任务**。25 个必做小任务中，T02A–T02G 共 **7 个已按各自批准范围完成**，还有 **18 个必做小任务未完成**。其中 11 个高权重必做项现已进入恢复计划、等待独立审查与实施确认；其余 7 个必做项继续不在本轮范围。

> **计数规则**：按“一个可以独立产出、独立验收的结果”计为一个小任务；计划编写、分支、测试、审查、合并等通用 16 步流程不另算业务小任务。T02 对 T04 备份/恢复和 T05 日志结果做安全复核，T04/T05 负责能力本身，二者不重复计数。下表是 Phase 3 的完整 WBS 和完成口径，不是恢复实施授权；未来只有用户再次明确批准后，才能创建新的实施计划并执行。

#### 数量汇总

| 大任务                       | 已定义小任务 | 必做   | 条件触发 | 已完成         | 未完成且暂停的必做项 |
| ---------------------------- | ------------ | ------ | -------- | -------------- | -------------------- |
| T01：S6 后续产品形态重新决策 | 3            | 2      | 1        | 0              | 2                    |
| T02：安全与隐私基线审计      | 14           | 13     | 1        | 7（T02A–T02G） | 6                    |
| T03：性能基线                | 4            | 3      | 1        | 0              | 3                    |
| T04：备份与恢复              | 3            | 3      | 0        | 0              | 3                    |
| T05：日志规范化              | 4            | 4      | 0        | 0              | 4                    |
| **合计**                     | **28**       | **25** | **3**    | **7**          | **18**               |

补充口径：

- **“必做 25 个”**表示如果将来要正式宣布 Phase 3 完成，这 25 个结果必须全部达到验收标准；不表示可以不经计划、审查和逐项验收直接并行实施。
- **“条件触发 3 个”**分别是：T01 产品边界改变后才实施变更、发现 P0 后才启动应急处置、当前 MVP 真正启用 Worker 或基线证明需要时才做 Worker 并发优化。
- **单独回答“T02G 后面还有多少”**：T02 还剩 **6 个必做完成项（T02-R1～T02-R6）**，另有 **1 个仅在发现 P0 时触发的应急项**；当前已获恢复规划授权，但具体实施仍须按新的高权重计划完成独立审查并获确认。`R` 只表示 Todo/WBS 中的 remaining item，不是自动批准的实施切片。
- **T02A–T02G 的 7 个完成项**只按各自批准切片计为完成；T02 顶层仍有 6 个必做结果未完成，所以 T02 不能勾选完成。
- **目标用户电脑安装/使用验收不重复计入 Phase 3 小任务**：它是独立的 Alpha/发布门禁。目标机产生的 ACL、备份、恢复或性能证据可以被对应 Phase 3 任务引用，但不能代替对应任务的正式验收。

#### 小任务明细、归属、必要性、状态和设置依据

| 大任务 | 小任务                                    | 可独立验收的结果                                                                                                                                                                                                                                                                                                      | 必要性       | 当前状态                                                                    | 设置依据                                                                                                                                                                                  |
| ------ | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T01    | T01-1 当前 S6 产品边界复核                | 核对“学生唯一操作者、家长只收异步脱敏报告、无家长登录/网页面板/公网入口”是否仍满足真实使用目标，并形成结论                                                                                                                                                                                                            | **必做**     | ⏸️ 未完成，暂停                                                             | `docs/01-总PRD-产品需求-Product-Requirements.md` Phase 3 与 S6 边界；`docs/02-七子系统地图-Scenario-Systems.md` S6 定位；`docs/subsystems/06-S6-家长观察子系统PRD-ParentReport.md` 非目标 |
| T01    | T01-2 后续产品形态决策并记录              | 用户明确选择“保持现状”或“改变边界”，并在 PRD/Todo 中记录，不默认采用历史家长面板候选                                                                                                                                                                                                                                  | **必做**     | ⏸️ 未完成，暂停                                                             | `docs/15-前端信息架构与界面范围研究-Frontend-Information-Architecture.md` Phase 3 产品边界检查项；`docs/01` Phase 3 候选目标                                                              |
| T01    | T01-3 获批产品变更的 PRD、计划与实施      | 仅当 T01-2 决定改变现状时，先更新 S6 PRD/信息架构，再创建独立计划并实施验收                                                                                                                                                                                                                                           | **条件触发** | ⏸️ 条件未触发；当前保持现状                                                 | `docs/12-开发规范-Dev-Rules.md` 文档门禁与计划批准规则；`docs/subsystems/06-S6-家长观察子系统PRD-ParentReport.md` 当前非目标                                                              |
| T02    | T02A 生产攻击面与统一错误边界             | 生产禁用 dev API、统一脱敏 JSON 错误、显式生产模式、后端核心强制回环                                                                                                                                                                                                                                                  | **必做**     | ✅ 已完成并进入 `origin/master`                                             | `.plans/phase3-t02-security-privacy-baseline-audit-plan.md` Slice 1；`.plans/phase3-t02a-production-attack-surface-error-boundary-plan.md`                                                |
| T02    | T02B 子进程环境最小化                     | OCR/whisper.cpp 等子进程只接收 allowlist 环境，避免继承无关秘密                                                                                                                                                                                                                                                       | **必做**     | ✅ 已完成并进入 `origin/master`                                             | T02 总计划 Slice 2；`.plans/phase3-t02b-subprocess-environment-boundary-plan.md`                                                                                                          |
| T02    | T02C 配置和环境错误脱敏                   | `.env`/运行配置解析只返回安全错误码和必要位置，不回显原始秘密行或宿主信息                                                                                                                                                                                                                                             | **必做**     | ✅ 已完成并进入 `origin/master`                                             | T02 总计划 Slice 2；`.plans/phase3-t02c-env-error-redaction-plan.md`                                                                                                                      |
| T02    | T02D 秘密扫描器与部署包证明边界           | 建立只输出规则/文件/脱敏指纹、不读取或打印命中秘密值的合成扫描边界                                                                                                                                                                                                                                                    | **必做**     | ✅ 已完成并进入 `origin/master`；不等于正式真实包扫描签收                   | T02 总计划 Slice 2；`.plans/phase3-t02d-secret-scan-deployment-package-plan.md`                                                                                                           |
| T02    | T02E 部署输出与递归删除边界               | 打包输出、staging、覆盖和递归删除只能作用于明确受控根，危险路径 fail-closed                                                                                                                                                                                                                                           | **必做**     | ✅ 已完成并进入 `origin/master`                                             | T02 总计划 Slice 3；`.plans/phase3-t02e-deployment-output-delete-boundary-plan.md`                                                                                                        |
| T02    | T02F 日志安全边界底座                     | 建立运行日志 allowlist、脱敏、轮转、保留/清理的合成安全边界                                                                                                                                                                                                                                                           | **必做**     | ✅ 已完成并进入 `origin/master`；不等于 T05 整体完成                        | T02 总计划 Slice 3；`.plans/phase3-t02f-log-redaction-rotation-retention-plan.md`                                                                                                         |
| T02    | T02G Windows 数据、ACL、备份/恢复合成边界 | 建立路径保护、只读 ACL 契约、白名单备份 manifest/hash 与 restore `-WhatIf` 预检；真实写入固定拒绝                                                                                                                                                                                                                     | **必做**     | ✅ 已完成仓库外合成夹具范围并进入 `origin/master`；真实操作未完成           | T02 总计划 Slice 3；`.plans/phase3-t02g-windows-data-acl-backup-restore-plan.md` G1–G5                                                                                                    |
| T02    | T02-R1 正式仓库与实际部署包秘密扫描签收 | 仅对 Git 已跟踪文件清单和已批准、已识别候选部署包根执行受控扫描；复核命中并形成不泄露秘密值、敏感文件名或原始输出的签收证据。记录 artifact ID、构建提交短哈希、包 SHA-256 短指纹和批准时间窗口，不扫描整个工作区或未跟踪目录                                                                                          | **必做**     | ✅ Wave 0 已签收（2026-08-06）：Git 已跟踪 37 命中 + 部署包 10 命中全部为配置变量引用/测试合成假值，0 真实秘密；证据 `.plans/evidence/phase3-wave0-r1-summary.json` | `PHASE3-REOPEN-HIGH-WEIGHT-20260728` Wave 0；T02 总计划 §6.1、Slice 2 和 §8；T02D 计划的“合成夹具不等于真实扫描”边界 |
| T02    | T02-R2 真实 Windows 目录与 ACL 证据       | 在批准机器只读取 config/data/logs/backups/tmp/models 的 ACL、继承、可写范围与 reparse 风险；仅以当前交互用户、当前用户计划任务、SYSTEM、Administrators、其他本地用户、未知主体、deny ACE、继承状态、有效访问未知等固定脱敏分类输出风险结论及是否需要最小 ACL 修复的建议。任何 ACL 修复须另建、另批最小任务并回滚/复验 | **必做**     | ✅ Wave 0 已采证（2026-08-06）：6 目录只读采证，0 reparse；初版误报 Users 全权继承，经 icacls 权威核对确认为采证脚本归类/位掩码 bug（AuthenticatedUsers 误归 Users）；脚本已修复，真实 ACL 为 Windows 标准默认（Users 仅 Read），无 P1，无需 ACL 修复；证据 .plans/evidence/phase3-wave0-r2-summary.json   | `PHASE3-REOPEN-HIGH-WEIGHT-20260728` Wave 0；T02 总计划数据/部署范围、Slice 3、§8；T02G 计划 G2/G5 与“真实操作另批”门禁                                                                   |
| T02    | T02-R3 真实备份/恢复安全复核              | 同一任务含 R3-prewrite 与 R3-postrestore 两个独立门：任何目标机非 `-WhatIf` backup/restore 写入前，非 T04 实现者必须签收精确目标机批准、停止证据、状态机/中断标记、预检、recovery point 与脱敏输出契约；演练后再独立复核受控根、白名单、manifest/hash、写入/中断/回滚和完整性。任一 P1 未闭合不得签收                 | **必做**     | ✅ R3-prewrite 已签收（2026-08-06）：用户以独立审查人确认无 P1；目标机精确批准与停止证据待采集；R3-postrestore 仍待演练后独立复核 | `PHASE3-REOPEN-HIGH-WEIGHT-20260728` Wave 2；T02 总计划数据边界、Slice 3、§8；T02G 计划 G3/G4；`docs/13-部署运维指南-Deployment.md`“备份、恢复、升级与回滚”                               |
| T02    | T02-R4 学生核心流程失败反馈矩阵           | S1/S2/S3/S4/S5/S7 核心路径覆盖输入错误、不存在、未配置、超时/下游失败、未知异常与重试建议，前端只显示可操作的脱敏中文信息                                                                                                                                                                                             | **必做**     | ✅ Wave 3 已完成（2026-08-06）：错误反馈矩阵专项 6/6 通过，S1-S7 错误 message 全部中文可操作且脱敏，S4 裸 Error 经 API 层兜底为固定码                     | T02 总计划 Slice 4 与 §8 第 7 项                                                                                                                                                          |
| T02    | T02-R5 P2/P3 治理与剩余风险签收           | 收口浏览器草稿最小字段/清理、S6 快照 schema/允许字段、`paths.ts`/manifest/文档漂移，并记录责任、缓解措施、触发条件和排期                                                                                                                                                                                              | **必做**     | ⏸️ 未完成，暂停                                                             | T02 总计划 Slice 5；§5 P2/P3 处置门禁                                                                                                                                                     |
| T02    | T02-R6 T02 总体回归与完成验收             | 仅在已批准实际范围的 P0 已闭合、全部 P1 修复、自动化回归和 Windows 原生证据通过且文档/风险签收一致后，才能把顶层 T02 标为完成                                                                                                                                                                                         | **必做**     | 📝 Wave 4：高权重恢复计划已创建；仅在全部纳入 P1 证据闭合后验收             | `PHASE3-REOPEN-HIGH-WEIGHT-20260728` Wave 4；T02 总计划 §8“实施验收标准”和 §9 验证集                                                                                                      |
| T02    | T02-P0 安全/隐私应急处置                  | 只有正式扫描或审计确认秘密、学生数据或正式运行数据泄露/破坏时，停止普通流程，隔离、轮换、保全证据、修复并复验                                                                                                                                                                                                         | **条件触发** | ⏸️ 当前未确认 P0，条件未触发                                                | T02 总计划 §5 风险分级和 Slice 0                                                                                                                                                          |
| T03    | T03-1 API/核心流程响应时间基线            | 定义测量场景和预算，记录核心 API/页面交互的冷启动、常态和高负载响应；超预算则在本项内修复或明确签收                                                                                                                                                                                                                   | **必做**     | ⏸️ 未完成，暂停                                                             | 本文件 Phase 3 顶层 T03“响应时间基线”；`docs/09-测试验收计划-Test-Plan.md` 既有耗时与验收记录                                                                                             |
| T03    | T03-2 内存、CPU 与进程资源基线            | 记录前后端、OCR/ASR/报告等关键流程的内存/CPU/进程残留和重复运行增长，证明无持续分页增长或泄漏                                                                                                                                                                                                                         | **必做**     | ⏸️ 未完成，暂停                                                             | 本文件 T03“内存基线”；`docs/09` 性能资源、可用内存与进程退出标准                                                                                                                          |
| T03    | T03-3 前端首屏与主要路由性能              | 测量冷启动首屏、主要路由加载和静态资源体积；对明显卡顿或超预算项优化并回归                                                                                                                                                                                                                                            | **必做**     | ⏸️ 未完成，暂停                                                             | 本文件 T03“前端首屏”；`docs/11-前端开发规范-Frontend-Guidelines.md` 页面/构建边界；`docs/09` 无明显卡顿要求                                                                               |
| T03    | T03-4 Worker 并发与队列优化               | 仅当当前 MVP 实际启用 Worker，或基线证明串行/并发策略成为瓶颈时，验证并优化领取、并发、重试和资源上限                                                                                                                                                                                                                 | **条件触发** | ⏸️ 条件未触发；当前 S3 Worker 不属于 MVP                                    | 本文件 T03“Worker 并发优化”；`docs/08-共同底座架构-Architecture.md` jobs/单进程 Worker 候选架构；`AGENTS.md` 当前 MVP 边界                                                                |
| T04    | T04-1 自动定期备份                        | 实现可配置周期、受控目标根、白名单 payload、manifest/hash、失败可见且不覆盖未知备份的自动备份                                                                                                                                                                                                                         | **必做**     | ✅ Wave 1 已完成（2026-08-06）：自动备份脚本已实现，隔离根合成演练通过                       | 本文件 T04“自动定期备份”；`docs/13` 备份目录与当前未完成边界；T02G 计划 G3                                                                                                                |
| T04    | T04-2 损坏与完整性检测                    | 对全局库、学期库和备份执行完整性/hash/manifest 校验，能识别损坏、缺失、篡改和不可恢复状态                                                                                                                                                                                                                             | **必做**     | ✅ Wave 1 已完成（2026-08-06）：启动完整性检查已实现，损坏库识别验证通过                       | 本文件 T04“损坏检测”；`docs/08-共同底座架构-Architecture.md` 分学期隔离/完整性/恢复要求；T02G 计划 G3/G4                                                                                  |
| T04    | T04-3 一键恢复与真实恢复演练              | 实现受控恢复写入，包含服务/计划任务停止、恢复点、预检、复制顺序、中断恢复、结果校验和回滚；在批准机器完成真实演练                                                                                                                                                                                                     | **必做**     | ✅ Wave 1 隔离根演练 + Wave 2 持久化状态机完成（2026-08-06）：受控写入 8 步状态序列（含 CUTOVER_IN_PROGRESS）、状态文件/中断标记/重启默认拒绝/完整性复验全通过；真实目标机写入仍待用户精确批准 + R3-prewrite 独立签收         | 本文件 T04“一键恢复验证”；`docs/13`“备份、恢复、升级与回滚”；T02G 计划 G4                                                                                                                 |
| T05    | T05-1 全链路日志脱敏                      | 覆盖后端、Adapter/Worker、部署脚本和渠道失败日志，禁止秘密、学生原文、完整 UUID、绝对路径和外部原始响应                                                                                                                                                                                                               | **必做**     | ✅ Wave 2 已完成（2026-08-06）：ai-logger 接入 runtime-log-boundary ai JSONL 落盘，字段 allowlist 校验，专项 4/4                       | 本文件 T05“脱敏日志”；T02 总计划“日志与隐私”；`docs/08`/`docs/10-后端开发规范-Backend-Guidelines.md` 日志禁止字段                                                                         |
| T05    | T05-2 日志等级、事件与允许字段规范        | 统一 debug/info/warn/error 的使用、事件名、关联 ID、允许字段和面向用户/内部诊断边界                                                                                                                                                                                                                                   | **必做**     | ✅ Wave 2 已完成（2026-08-06）：docs/10 7.4 节补充等级/事件/允许字段规范                       | 本文件 T05“分级输出”；T02F 计划 §4；`docs/10` 日志规范                                                                                                                                    |
| T05    | T05-3 日志轮转与容量上限                  | 为运行日志设定单文件/总量上限和安全轮转，证明重复启动与长期运行不会无限增长                                                                                                                                                                                                                                           | **必做**     | ✅ Wave 2 已完成（2026-08-06）：单文件字节上限自动轮转实现，保留 3 份，专项 2/2                       | 本文件 T05“日志轮转”；T02 总计划 Slice 3；T02F 计划                                                                                                                                       |
| T05    | T05-4 保留期与安全清理                    | 定义各类日志保留期，清理只作用于受控日志根、拒绝 reparse/危险路径，并留下不含隐私的清理结果                                                                                                                                                                                                                           | **必做**     | ⏸️ T02F 仅完成合成边界，真实保留/清理验收未完成                             | 本文件 T05“日志清理”；T02 总计划 Slice 3；T02F 计划；`docs/13` 日志目录边界                                                                                                               |

#### 任务设置依据总览

Phase 3 任务不是凭聊天临时编出来的，依据分四层：

1. **产品层**：`docs/01-总PRD-产品需求-Product-Requirements.md` 定义 Phase 3 为“安全、性能与后续产品形态候选”；`docs/02-七子系统地图-Scenario-Systems.md`、S6 PRD 和 `docs/15` 定义 T01 的学生主视角与家长异步报告边界。
2. **正式安全计划层**：`.plans/phase3-t02-security-privacy-baseline-audit-plan.md` 定义 T02 的审计范围、P0–P3 风险、Slice 0–5 和总体完成标准；T02A–T02G 各自计划定义已实施切片的边界和证据。
3. **架构、测试与运维层**：`docs/08-共同底座架构-Architecture.md`、`docs/09-测试验收计划-Test-Plan.md`、`docs/10-后端开发规范-Backend-Guidelines.md`、`docs/11-前端开发规范-Frontend-Guidelines.md`、`docs/13-部署运维指南-Deployment.md` 提供 T03/T04/T05 的性能、进程、备份、恢复、日志和目录验收约束。
4. **任务治理层**：本文件原有 Phase 3 顶层表明确列出 T01–T05 的单一责任；`docs/12-开发规范-Dev-Rules.md` 规定恢复实施前仍须建立独立计划、审查并取得用户明确批准。本次 WBS 只把已有责任拆成可数、可验收的小任务，没有恢复任何实施授权；T02-R1～T02-R6 不是新的已批准实施切片。

### Phase 3 行动计划索引

| 任务        | 计划文件                                                              | 计划/实施状态                                                                                                                                                                                                                 |
| ----------- | --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PHASE3-T01  | 尚未创建                                                              | ⏸️ 仅完成本文件 WBS 登记；产品边界复核/决策未开始，恢复前须新建独立计划并获用户批准                                                                                                                                           |
| PHASE3-T02  | `.plans/phase3-t02-security-privacy-baseline-audit-plan.md`           | ⏸️ 计划曾获批准，T02A–T02G 已实施；用户于 2026-07-27 暂停剩余总体审计与修复，T02 未完成                                                                                                                                       |
| PHASE3-T02A | `.plans/phase3-t02a-production-attack-surface-error-boundary-plan.md` | ✅ 已在 `origin/master` 并完成最新主线复验；T02A 切片完成，不等于 T02 完成                                                                                                                                                    |
| PHASE3-T02B | `.plans/phase3-t02b-subprocess-environment-boundary-plan.md`          | ✅ 已推送 `origin/master`；T02B 切片完成，不等于 T02 完成                                                                                                                                                                     |
| PHASE3-T02C | `.plans/phase3-t02c-env-error-redaction-plan.md`                      | ✅ 已推送 `origin/master`；T02C 切片完成，不等于 T02 完成                                                                                                                                                                     |
| PHASE3-T02D | `.plans/phase3-t02d-secret-scan-deployment-package-plan.md`           | ✅ 已推送 `origin/master`；T02D 切片完成，不等于 T02 完成                                                                                                                                                                     |
| PHASE3-T02E | `.plans/phase3-t02e-deployment-output-delete-boundary-plan.md`        | ✅ 已在 `origin/master` 并完成最新主线复验；T02E 切片完成，不等于 T02 完成                                                                                                                                                    |
| PHASE3-T02F | `.plans/phase3-t02f-log-redaction-rotation-retention-plan.md`         | ✅ 已在 `origin/master` 并完成最新主线复验；T02F 切片完成不等于 T02 完成                                                                                                                                                      |
| PHASE3-T02G | `.plans/phase3-t02g-windows-data-acl-backup-restore-plan.md`          | ✅ 已在 `origin/master` 完成主线复验：计划、实现、文档同步与 P1 修复提交已独立审查、rebase、快进合并并推送（`6f5ecdd`）。仅覆盖仓库外合成夹具；真实 ACL、真实 backup/restore 及 restore 写入仍未获批准或实施，不等于 T02 完成 |
| PHASE3-T03  | 尚未创建                                                              | ⏸️ 仅完成本文件 WBS 登记；性能基线未开始，恢复前须新建独立计划并获用户批准                                                                                                                                                    |
| PHASE3-T04  | 尚未创建                                                              | ⏸️ 仅完成本文件 WBS 登记；自动备份、损坏检测和真实恢复未开始，恢复前须新建独立计划并获用户批准                                                                                                                                |
| PHASE3-T05  | 尚未创建                                                              | ⏸️ 仅完成本文件 WBS 登记；T02F 安全底座不等于 T05 完成，恢复前须新建独立计划并获用户批准                                                                                                                                      |

> **2026-07-27 Phase 3 暂停决定**：用户明确要求从 T02G 边界开始暂停开发机上的全部 Phase 3 后续工作。T02G 保留为“仓库外合成夹具范围已完成主线复验”的独立切片事实；该结论不表示真实 Windows ACL、真实 backup/restore、restore 写入、用户电脑实机证据或 T02 总体通过。自本决定起，不再创建或实施任何新的 T02 实施切片，不启动 T03/T04/T05，也不创建新的 Phase 3 实施计划；本文件新增的 T02-R1～T02-R6 仅为完整 Todo/WBS 的剩余完成口径，不是实施切片或批准。暂停不是完成；未来恢复须由用户再次明确批准，并另建届时适用的独立计划。 本次任务仅同步 `AGENTS.md`、`docs/00`、`docs/04`、`docs/08` 与 T02 总计划的状态措辞；任务分支已通过 `scripts/check-docs-governance.ps1`、`git diff --check` 和暂停边界一致性搜索，未运行或修改 ACL、备份/恢复、部署脚本、业务代码、服务或会写运行数据的测试。

> **PHASE3-T02 安全与隐私基线审计计划（2026-07-25，计划已批准）**：计划路径 `.plans/phase3-t02-security-privacy-baseline-audit-plan.md`，任务分支 `codex/phase3-t02-security-privacy-baseline-audit-plan`，从最新 `origin/master` 创建于外部 worktree `H:\ai-studybuddy-worktrees\phase3-t02-security-privacy-baseline-audit-plan`。本轮只读检查配置秘密、数据/文件、API/错误、日志/隐私、S6/S7 和 Windows Node 24 部署脚本边界；当前未确认 P0，确认的 P1 候选包括生产无条件挂载 dev API、缺少全局 JSON 脱敏错误中间件与显式 `NODE_ENV=production`、后端核心未强制回环、OCR/whisper.cpp 子进程继承完整环境、env 非法行回显、打包输出目录递归删除缺少受控根保护，以及日志轮转/保留/脱敏边界未闭环。计划同时记录现有 DPAPI、回环 Origin、S6 聚合脱敏、S7 受控 WAV/临时清理/显式保存等正向控制，并拆分上线前 P1 与后续 P2/P3。**用户已于 2026-07-25 明确批准本基线审计计划；T02A 与 T02B 已作为独立切片进入远端主线并完成各自主线复验。批准计划或切片完成均不表示 T02 总体、Phase 3 安全审计、安全修复、上线验收或用户电脑安装验收完成。**

> **PHASE3-T02A 生产攻击面与统一错误边界详细实施（2026-07-26，已在 origin/master 并完成最新主线复验）**：外部 worktree `H:\ai-studybuddy-worktrees\phase3-t02a-production-attack-surface-error-boundary-plan`，分支 `codex/phase3-t02a-production-attack-surface-error-boundary-plan`，计划路径 `.plans/phase3-t02a-production-attack-surface-error-boundary-plan.md`，实现提交 `7f976a0` 已位于当前 `origin/master` 历史中；本轮基于 `533e6f2` 确认无需额外 fast-forward/cherry-pick/merge，且未回退 T02B 改动。本切片实现生产 `/api/dev*` 隔离、统一 JSON 错误边界、显式 `NODE_ENV=production` 和后端核心精确 `127.0.0.1` 回环校验；开发/测试模式保留 dev API，子进程测试显式声明 `NODE_ENV=test`。回归覆盖生产 JSON 404（无 `data`、无路径或 storage key）、畸形 JSON、全局 Multer 限制、未知异常、允许列表安全应用错误、非法 `NODE_ENV` 和非回环 `BACKEND_HOST` 拒绝。2026-07-26 使用仓库外隔离根 `H:\ai-studybuddy-tmp\runs\phase3-t02a-master-verify-20260726-01` 与 `H:\ai-studybuddy-tmp\runs\phase3-t02a-master-pnpm-test-20260726-01`，在 Windows 原生 Node 24 上完成最新主线复验：后端 build 通过；T02A 专项 16/16 通过；`pnpm type-check` 通过；前端 Vitest 26 文件 / 139 测试通过；文档治理和 `git diff --check` 通过；完整 `pnpm test` 通过，后端 272/272，前端 build 仅既有 KaTeX chunk warning。独立复审已完成；T02A 切片完成，但不得报告 T02、Phase 3、安全审计、生产上线或用户电脑验收已完成。非范围仍包括用户电脑验收、OCR/ASR 子进程、日志、备份/ACL、完整 S7、G2、S3 Worker、Docker/WSL、Firewall 及真实外部服务。

> **PHASE3-T02B OCR 与 whisper.cpp 子进程环境最小化（2026-07-26，已完成并推送 origin/master）**：计划路径 `.plans/phase3-t02b-subprocess-environment-boundary-plan.md`，任务分支 `codex/phase3-t02b-subprocess-environment-boundary`，实现提交 `eeb9cb1` 已 fast-forward 集成到本机 `master`。本切片实现 OCR/whisper.cpp 子进程正向环境 allowlist、OCR 子进程 stdout/stderr 回显收敛、whisper.cpp 显式 `env` 与测试注入 seam；不执行真实 OCR/ASR、Provider、SMTP、飞书或其他外部服务。2026-07-26 使用仓库外隔离根 `H:\ai-studybuddy-tmp\runs\phase3-t02b-master-verify-20260726-01` 与 `H:\ai-studybuddy-tmp\runs\phase3-t02b-master-pnpm-test-20260726-01`，在 Windows 原生 Node 24 上完成主线复验：后端 build 通过；T02B/OCR 专项 7/7 通过；`pnpm type-check` 通过；前端 Vitest 26 文件 / 139 测试通过；文档治理和 `git diff --check` 通过；完整 `pnpm test` 通过，后端 272/272，前端 build 仅既有 KaTeX chunk warning。独立审查已完成；实现提交 `eeb9cb1` 与主线复验文档提交 `7281229` 已推送 `origin/master`。T02B 切片完成；但不得报告 T02、Phase 3、安全审计、生产上线或用户电脑验收已完成。非范围仍包括日志轮转、备份/ACL、生产防火墙、Docker/WSL、完整 S7、G2、S3 Worker、用户电脑验收和真实外部服务。

> **PHASE3-T02C 配置加载与环境错误脱敏实施证据（2026-07-26，已推送 origin/master）**：计划路径 `.plans/phase3-t02c-env-error-redaction-plan.md`，任务分支 `codex/phase3-t02c-env-error-redaction`，实现提交 `3a0b6bf` 已安全 fast-forward 集成到本机 `master`。本切片收口配置加载、`.env`/运行环境解析与配置校验错误的秘密回显边界：后端配置加载错误统一为固定 `[CONFIG]` 摘要且不带 stack；`.env.local` 与 PowerShell `production.env` 导入对非法行、空 key、重复键只暴露固定错误码、键名和非值型行号；`APP_DATA_ROOT` 不可写、非法 `NODE_ENV`/`BACKEND_HOST`、非法 `AI_PROVIDERS`、Provider/SMTP/Webhook 配置校验失败均不得回显 Provider URL/API Key、`AI_PROVIDERS` 原文、SMTP、Webhook、`APP_DATA_ROOT`、绝对路径、完整宿主环境、raw parser message 或 stack。新增 `packages/backend/test/env-error-redaction.test.mjs` 与 `packages/backend/test/config-validation-redaction.test.mjs`，使用无效合成哨兵证明 thrown error、stderr/stdout、测试输出与公开 API 错误不泄露值；不 dump `process.env`，不读取或调用真实 Provider/SMTP/Webhook/OCR/whisper.cpp。在 Windows 原生 Node 24 + 新的仓库外隔离根完成主线复验：后端 build 通过，T02C 专项 7/7 与相邻 T02A/T02B 边界回归 40/40（共 47/47）通过，`pnpm type-check`、前端测试、文档治理和 `git diff --check` 均通过；外部服务配置保持为空，未调用真实服务。实现、主线复验与文档状态提交均已推送 `origin/master`；不得报告 T02、Phase 3、安全审计、生产上线或用户电脑验收完成。非范围仍包括日志轮转、备份/ACL、生产防火墙、Docker/WSL、完整 S7、G2、S3 Worker、用户电脑验收、打包输出目录递归删除保护和真实外部服务。
> **PHASE3-T02D 仓库与部署包秘密扫描安全证明边界（2026-07-26，已推送 `origin/master`）**：计划路径 `.plans/phase3-t02d-secret-scan-deployment-package-plan.md`，任务分支 `codex/phase3-t02d-secret-scan-plan`，实现提交 `06cc6b3`。用户已单独批准实施。新增 `scripts/lib/AIStudyBuddy.SecretScan.cjs`，仅消费显式的已跟踪相对路径清单；在内容读取前跳过敏感 env 文件、越界路径、符号链接、非文本和超限文件，并将文件访问/Git 清单/格式错误收敛为无 stack 的固定错误码。命中与格式化输出只含相对路径、稳定规则 ID、类别、非敏感行号和短指纹，不含命中原文、完整配置行、绝对路径、完整宿主环境或底层错误。新增 `packages/backend/test/secret-scan-boundary.test.mjs`，在仓库外临时 Git 夹具中动态生成无效合成哨兵，证明允许字段、敏感 env 候选读取前跳过、越界/缺失文件错误脱敏和序列化无哨兵泄露；专项 4/4 通过。Windows 原生 Node 24 分支验证通过 `pnpm type-check`、后端/前端 build、隔离 `pnpm test`（后端 283/283）与独立审查；未扫描本仓、真实部署包、用户目录、环境文件、正式数据或外部运行数据，也未调用 Provider、SMTP、Webhook、OCR、whisper.cpp 或网络服务。已 fast-forward 集成到本地 `master`，并在隔离数据根完成主线复验：类型检查、后端/前端 build、完整 `pnpm test`（后端 283/283）、文档治理和 `git diff --check` 均通过；已推送 `origin/master`，不得报告 T02、Phase 3、安全审计、生产上线或用户电脑验收完成。非范围包括打包输出目录递归删除保护、备份/恢复、ACL、日志轮转/清理、生产防火墙、Docker/WSL、完整 S7、G2、S3 Worker 和真实秘密扫描。
> **PHASE3-T02E 部署包输出与 staging 删除边界（2026-07-26，已在 `origin/master` 并完成最新主线复验）**：计划提交 `4b86ddd`、实施提交 `21680a06`，任务分支 `codex/phase3-t02e-deployment-output-delete-boundary-plan` 已在最新 `master` 上安全 fast-forward 集成。本切片仅约束 `build-deployment-package.ps1` 的显式、既存且为空的仓库外输出根：拒绝仓库根、磁盘根、用户目录、`APP_DATA_ROOT`、受保护根交叠和重解析点；staging 仅能在输出根下由本次操作创建的 GUID 子目录中进行受控递归清理，既不删除输出根，也不覆盖/删除既有 ZIP。打包前按路径/元数据拒绝 `.git`、依赖缓存、真实环境文件、数据库、日志、tmp、模型、备份或运行时目录；错误只输出固定、脱敏类别。2026-07-26 在最新 `master` 上完成复验：T02E 专项 3/3、现有部署 PowerShell 兼容测试 6/6、`pnpm type-check`、文档治理和 `git diff --check` 均通过；完整 `pnpm test` 使用新的仓库外隔离 `APP_DATA_ROOT=H:\ai-studybuddy-tmp\runs\phase3-t02e-master-pnpm-test-20260726-01` 通过（后端 286/286，前端通过，仅既有 KaTeX chunk warning）。本轮未运行 `build-deployment-package.ps1`、真实部署包打包、真实部署包/秘密扫描、真实目录清理或真实递归删除，未读取真实数据，也未调用 Provider、SMTP、Webhook、OCR、whisper.cpp 或网络服务。独立审查已确认范围、拒绝条件、脱敏错误与非范围一致；T02E 切片完成不等于 T02、Phase 3、安全审计、生产上线或用户电脑验收完成。非范围仍包括 bootstrap/check/start/health/stop/backup/restore、备份/恢复、ACL、日志轮转/清理、生产防火墙、Docker/WSL、S7、G2、S3 Worker 与用户电脑验收。

> **PHASE3-T02G Windows 运行目录、ACL 与 backup/restore 安全边界（2026-07-26，已完成主线集成）**：实施分支 `codex/phase3-t02g-windows-data-acl-backup-restore-implementation` 从 `origin/master` 的 `9c58e0a` 创建，并以已批准计划作为实现依据；P1 修复与独立审查完成后已 rebase、快进合并、主线复验并推送 `origin/master`（`6f5ecdd`）。当前仅实现并验证仓库外合成夹具：统一的绝对路径、受保护根、同卷与 reparse point fail-closed 分类；仅返回逻辑类别与短哈希的只读 ACL 证据；显式、安装根之外的 backup output、仅 `studybuddy.db`/`semesters` 白名单 payload、无 `sourceDataRoot` 的 v2 manifest；以及对 manifest/payload/hash/路径的 restore 预检。`restore-data.ps1 -WhatIf` 只验证且不落盘；任何真实 restore 写入均固定拒绝为 `RESTORE_WRITE_DISABLED`，等待独立的服务/计划任务停止、recovery point 和中断处理批准/实现。已执行 `powershell -ExecutionPolicy Bypass -File scripts/test-data-boundary.ps1`：合成路径和恶意 manifest 拒绝、manifest 脱敏、ACL 序列化不含夹具路径、`-WhatIf` 不改数据、受保护哨兵不变且夹具清理后无残留。当前环境无法创建符号链接夹具，测试明确记录 `REPARSE_FIXTURE_UNSUPPORTED`；因此不得将其表述为 reparse 实机证据，真实 ACL、真实备份、真实恢复、正式安装和用户电脑操作仍须分别批准。未触碰 T02E 部署包/staging 删除或 T02F 日志轮转/保留实现；本条不表示 T02G、T02、Phase 3、安全与隐私基线审计、生产上线或用户电脑验收完成。

## S2-Format：常见文件格式全支持（上传白名单与转换器扩展）

**状态**：📝 计划已创建（2026-08-06），待独立审查与用户批准后实施。

**目标**：将资料系统从 S2 PRD T07 边界（PDF/图片/文本/DOCX/PPTX）扩展到常见文件格式全支持：converter 层已具备但被上传白名单拦截的格式（md/csv/json/gif/bmp/html）直接放行；需新增转换器的常见格式（xlsx/odt/ods/odp/rtf/epub）新建提取器；安全/复杂度原因继续拒绝的格式（doc/ppt/压缩包/邮件）保持拒绝并给出明确提示。

**行动计划**：`.plans/s2-file-format-expansion-plan.md`；任务分支 `claude/s2-file-format-expansion`。

| 分类 | 格式 | 当前状态 | 计划动作 |
|---|---|---|---|
| A. 白名单拦截（converter 已支持） | md、csv、json、gif、bmp、html/htm | 上传被拦（INVALID_FILE_TYPE） | 扩展 FILE_TYPES + 前端 accept + 测试 |
| B. 新增转换器 | xlsx、odt、ods、odp、rtf、epub | 显式拒绝（提示另存） | 零新依赖：复用 jszip 提取 zip/XML 文本；rtf 自写剥离 |
| C. 继续拒绝 | doc、ppt、xls、zip/rar/7z/tar/gz、eml/msg | 显式拒绝 | 保留拒绝，更新提示文案；xls 提示另存 xlsx（SheetJS 有 CVE 且 npm 停更，不引入） |

---

## Phase 4：系统验收收口（v0.8.1 全系统验收基线）

**状态**：✅ 已完成主线复验并推送 `origin/master`（2026-08-06）。用户明确指示按验收执行 Prompt 实测全系统并收口，本轮按第十四章矩阵逐项实测并勾选，全部自动化基线通过，未见失败项需修复。

**目标**：建立"当前 v0.8.1 全系统验收矩阵"作为单一、确定的验收标准来源（替代 docs/09 历史堆积），同步修正 docs/09 滞后项（备份/恢复 RESTORE_WRITE_DISABLED 描述、G2/Phase 1.5 状态、补 Phase 3 Wave 0-3 记录）。

**本轮实测证据（2026-08-06，全部隔离 APP_DATA_ROOT=`H:\ai-studybuddy-tmp\runs\phase4-acceptance-20260806\<子项>`）**：
- `pnpm type-check`：零错误；双端 build（`pnpm -r --filter backend run build` / `pnpm -r --filter @ai-studybuddy/frontend run build`）成功。
- 后端测试：`pnpm -r --filter @ai-studybuddy/backend run test` = 342/342（duration 252s）。
- 前端测试：`pnpm -r --filter @ai-studybuddy/frontend run test` = 149/149（28 files）。
- E2E：`pnpm test:e2e` = 24/24（48.2s）；专项 `playwright test e2e/error-feedback-matrix.spec.ts` = 3/3。
- 专项安全测试：`node --test test/error-feedback-matrix.test.mjs test/ai-logger-boundary.test.mjs test/runtime-log-boundary.test.mjs` = 17/17（含 6/6、4/4、7/7）。
- 真实服务冒烟：`node packages/backend/dist/server.js`（BACKEND_PORT=38080、`PYTHON_PATH=H:\AIStudyBuddy\runtime\venv\Scripts\python.exe`、`FRONTEND_STATIC_ROOT=packages/frontend/dist`）；health 返回 v0.8.1；学生主路径 API 闭环：真实 OCR venv 课表预览（合成课表 28 字符、置信度 >0.99）→ 创建学期 201 → 设当前+读回一致 → 创建课程 201 → 创建考试 201 → 确认考试 confirmed → 任务/时间线返回事件 → 资料上传 200 → 读回 200；无 Provider 时生成笔记返回确定性状态错误（AI 降级边界符合预期）。
- 安全证据核对：`phase3-wave0-r1-summary.json` `signed-off-clean`、realSecrets=0；`phase3-wave0-r2-summary.json` 6 目录 reparsePointsFound=0、Windows 标准默认 ACL；`restore-data.ps1` 静态核验默认 fail-closed（RESTORE_VALIDATED_NO_WRITE）+ `-EnableWrite` 8 步状态机；`BACKEND_HOST` 强制 127.0.0.1；`register-parent-report-task.ps1` 默认不注册。

**未通过项**：无。全部验收项通过（含如实标注的待补边界，见 docs/09 §14.6：真实目标机验收、真实课表 OCR、真实渠道、R3-postrestore/T02-R6）。

**任务分支**：`claude/phase4-acceptance-20260806`（docs/09 第十四章状态列勾选 + 本文档登记）；已 rebase `origin/master`、ff-only 合入 `master` 并推送 `origin/master`。

**行动计划**：`.plans/phase4-acceptance-20260806-plan.md`；任务分支 `claude/phase4-acceptance-20260806`。

| 验收维度 | 覆盖 | 当前证据基线 |
|---|---|---|
| S1-S7 学生主路径 | 学期/课程/考试/资料/练习/错题/冲刺/报告/课堂 | 342 后端测试 + 149 前端测试 + 24 E2E + 真实业务冒烟 |
| 部署 | docs/13 §12 八项 | 部署矩阵 |
| 安全基线 | Phase 3 Wave 0-3 | R1/R2/R4/T04/T05 证据 |
| 全量自动化 | type-check/build/test/E2E | 全绿 |

**Phase 4 验收勾选结果（2026-08-06，详见 docs/09 第十四章）**：

| 维度 | 结果 |
|---|---|
| 14.1 S1-S7 学生主路径（12 项） | ✅ 全部本轮实测（E2E 24/24 覆盖 + 后端 342/342 + 真实业务冒烟） |
| 14.2 失败反馈与脱敏（T02-R4） | ✅ error-feedback-matrix 后端 6/6 + E2E 3/3、ai-logger-boundary 4/4 本轮实测 |
| 14.3 安全与数据（Wave 0-3） | ✅ R1 0 真实秘密、R2 ACL 标准默认 0 reparse、runtime-log-boundary 7/7、restore 状态机本轮核验 |
| 14.4 部署验收（8 项） | ✅ 可实测项本轮实测（启停/OCR smoke/安全网络/配置密钥/任务计划）；Bootstrap 为历史证据，真实目标机见 14.6 |
| 14.5 全量自动化基线 | ✅ type-check 零错误、双端 build、后端 342/342、前端 149/149、E2E 24/24 |
| 14.6 待补项 | ⏳ 真实目标机验收 / 真实课表 OCR / 真实渠道 / R3-postrestore、T02-R6（如实标注，未冒充通过） |

---
## POST-PHASE3：3 天 Alpha 真实使用冲刺

| 顺序 | 任务                                   | 状态 | 单一责任                                                                                                                                           |
| ---- | -------------------------------------- | ---- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | ALPHA-D0：开发机主线基线与 P0 回归修复 | ✅   | 实现提交 `a5d2c80` 已快进合并；任务分支与 `master` 均通过后端 292/292、E2E 21/21、type-check、双端 build、治理与差异检查，并已推送 `origin/master` |
| 2    | ALPHA-D1：干净部署包与目标机安装       | ⏳   | 构建/扫描部署包，在目标 Windows 11 机器完成 bootstrap/check/start/health/stop                                                                      |
| 3    | ALPHA-D2：学生核心闭环实机验收         | ⏳   | 以隔离测试数据完成 S1–S6、S5 冲刺闭环和单 Provider 最小真实调用；S6 渠道/S7 为条件项                                                               |
| 4    | ALPHA-D3：阻塞修复、回归与 Alpha 交付  | ⏳   | 只修 P0/P1 Bug，完成重启读回、备份/预检、已知问题和快速上手                                                                                        |

### Alpha 行动计划索引

| 任务           | 计划文件                                                  | 计划/实施状态                                                                          |
| -------------- | --------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| ALPHA-20260727 | `.plans/alpha-20260727-three-day-real-use-sprint-plan.md` | 🔄 Day 0 已完成并推送 `origin/master`；Day 1–3 目标机安装、真实闭环与 Alpha 交付待执行 |

> **ALPHA-20260727 3 天真实使用冲刺（Day 0 已在 `origin/master` 收口，Day 1–3 待执行）**：行动计划 `.plans/alpha-20260727-three-day-real-use-sprint-plan.md`；任务分支 `codex/alpha-20260727-day1-baseline-remediation` 基于 `origin/master=bd8f615` 创建于外部 worktree。用户要求 3 天内进入真实使用、立即执行开发机全量测试并“修 Bug 不加 Feature”。初始基线中，`pnpm test` 因 T02G 后旧 PowerShell 兼容测试契约未同步而失败，`pnpm test:e2e` 为 16/21，5 项失败均因 E2E 专用服务器误禁用 `/api/dev/init-semester`；最小修复后 PowerShell 兼容专项 6/6、数据边界脚本、E2E 21/21、type-check 和双端 build 均通过。候选包 01 随后暴露新的生产 P0：独立 OCR smoke 成功，但学期预览因 `OcrTimetableRecognizer` 未传入生产 OCR runtime 配置而返回 `TIMETABLE_OCR_FAILED`；现已让 recognizer 使用 `PYTHON_PATH`、OCR 超时、临时目录和缓存目录配置，并新增 `semester-ocr-runtime-config.test.mjs`，专项与相邻 semester API 4/4 通过；最终完整 `pnpm test` 后端 292/292 通过。修复后的候选包 02（ZIP SHA256 `5393209D8F4BB154FA8ECC24A5C2266584C7F8CD9BDEF05A5BC569163A382AB3`）共 304 文件，禁止项和秘密模式命中均为 0；已在开发机全新隔离安装根完成 bootstrap、生产依赖、Python venv/OCR 依赖、OCR smoke、运行中安装检查、health、前端 200、生产 dev route 404、正式 API 学期/课程读回及 start/stop 无残留。合成课程表预览已不再失败，但自动规则解析为 0 条，人工确认补入课程后写入和读回成功；真实课程表图片仍是目标机必测项。停机状态下数据完整性 2 文件通过，外部白名单备份 2 文件/495616 字节通过，`restore -WhatIf` 输出 `RESTORE_VALIDATED_NO_WRITE`，manifest v2 且不含 `sourceDataRoot`；真实 restore 写入继续固定拒绝。数据边界环境为 `REPARSE_FIXTURE_UNSUPPORTED`，不得表述为 reparse 实机证据。实现提交 `a5d2c80` 已快进合并到本地 `master`；任务分支与主线分别使用新的仓库外隔离根完成 type-check、双端 build/完整 `pnpm test`（后端 292/292）、E2E 21/21、文档治理和差异检查，并已推送 `origin/master`。主仓未跟踪 HTML 材料继续保留且未提交。三天窗口为 2026-07-28（周二）至 2026-07-30（周四）；目标用户电脑未完成新鲜实机证据前，不得宣称用户电脑验收或生产上线完成。

---

## 任务状态说明

| 符号  | 含义                                   |
| ----- | -------------------------------------- |
| ✅    | 已完成并验证                           |
| 🔄    | 进行中                                 |
| ⏳    | 待开始                                 |
| ⏸️    | 暂缓，未获当前实施授权                 |
| ❌    | 已跳过或放弃（需注明原因）             |
| 📝    | 计划已创建，等待审查或批准；实现未开始 |
| - [ ] | 待完成的具体任务                       |
| - [x] | 已完成的具体任务                       |

---

## 任务完成收尾硬门禁

任何实现任务、文档任务或计划任务在交付前，都必须执行以下检查，不能只在对话里说“已完成”：

1. 用任务编号或关键词在本文件中定位对应行，例如 `rg -n "T03C|Phase 1-T03C|批改" docs/04-开发任务清单-Todo-List.md`。
2. 核对行动计划索引：计划路径、审查/批准状态必须与 `.plans/` 和实际分支一致。
3. 只勾选本轮已经完成且已验证的子项；若只是创建计划，则登记“计划已创建并待批”，不得勾选实现项。
4. 只有代码与文档已合入 `master` 并推送到 `origin/master`，才可把实现任务标记为完成；仅在任务分支完成或推送分支，不得勾选完成。
5. 在对应任务附近补一条收尾证据，至少包含日期、改动范围、验证命令、任务分支、master 提交和未实现边界。
6. 再运行 `powershell -ExecutionPolicy Bypass -File scripts/check-docs-governance.ps1` 和 `git diff --check`。
7. 交付说明必须明确写出 `docs/04` 已更新；若未更新，必须说明本轮为何不是任务完成态。

这条门禁优先级等同于测试和构建：未完成 `docs/04` 收尾，不得声称任务已完成。

---

## 文档门禁检查点

每个任务开始前，确认：

1. 已先读 `docs/00-文档索引-Index.md`；
2. 当前任务需要的子系统 PRD 或规范文档已存在，或触发条件已经满足；
3. 若新增文档，同步更新 `docs/00`；
4. 若涉及实现，计划已获用户明确批准；
5. 提交前运行 `scripts/check-docs-governance.ps1` 和 `git diff --check`。

### 规范文档触发条件

> 开发动作触发文档，而不是提前创建空文档。

| 即将开始的动作                                         | 必须先存在/创建的文档                    | 当前状态                 | 说明                                 |
| ------------------------------------------------------ | ---------------------------------------- | ------------------------ | ------------------------------------ |
| 设计共同数据模型、队列、对象存储、AI Provider、Adapter | `08-共同底座架构-Architecture.md`        | ✅ 已创建                | 没有共同底座设计，不开始跨子系统实现 |
| 调通第一个开源组件 smoke test                          | `09-测试验收计划-Test-Plan.md`           | ✅ 已创建                | 先定义怎么验收，再调组件             |
| 写第一个后端服务 / Adapter / API / Worker              | `10-后端开发规范-Backend-Guidelines.md`  | ✅ 已创建                | 先统一路径、日志、Adapter 输出约定   |
| 写第一个正式前端页面                                   | `11-前端开发规范-Frontend-Guidelines.md` | ✅ 已创建                | 先统一页面、组件、状态和渲染规范     |
| 多 AI / 多分支 / 多 worktree 协作                      | `12-开发规范-Dev-Rules.md`               | ✅ 已创建（Phase 1-T00） | 先统一协作、提交、归档、备份规则     |

门禁流程：

```text
收到任务 → 读 00 索引 → 查目标文档是否存在 → 查触发条件 → 不满足则不创建 → 满足则创建 → 更新 00 索引 → 运行治理检查 → 提交
```
