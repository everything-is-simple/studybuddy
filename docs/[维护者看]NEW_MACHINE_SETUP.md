# StudyBuddy 新机器配置与迁移基线
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


这份文档和同目录的 `STUDYBUDDY_NEW_MACHINE_PROMPT.md` 是新机器的配置入口。目标是让一个新的 AI 按固定顺序完成目录、正式依赖、浏览器测试工具和服务启动，而不是凭历史聊天猜环境。

## 目录职责

| 目录 | 新机器动作 | 禁止事项 |
|---|---|---|
| `H:\studybuddy` | 克隆正式源码，运行安装/检查脚本 | 不放数据库、原件、凭据 |
| `H:\studybuddy-data` | 创建正式 data root；已有机器迁移时整体备份后再恢复 | 不使用 `live` 子目录，不与测试实例共用 |
| `H:\studybuddy-log` | 创建服务日志目录 | 不把日志提交到 Git |
| `H:\studybuddy-composer` | 克隆组件独立测试与组件卡仓库 | 不把 Composer 源码 import 到正式系统 |
| `H:\studybuddy-integration` | 克隆组合测试仓库和脱敏结果结构 | 不执行 live delivery smoke |
| `H:\studybuddy-test` | 克隆合成 fixtures、脱敏证据和测试脚本 | 不放真实学生资料或生产库 |
| `H:\studybuddy-ChinaTextbook` | 克隆脚本和清单；仅在用户明确授权下载并提供来源时下载教材 | token 只由用户在本地提供，绝不输出或提交 |

四个组件相关目录的关系固定为：`Composer 独立 smoke → Integration 组合契约 → StudyBuddy 正式重实现/装配 → Test 正式用户路径证据`。通过 Composer 或 Integration 不等于正式系统已可用。

## 当前组件状态

Composer 的 `manifests/b0-catalog.json` 是候选组件证据源，不是安装清单。当前记录的精确范围如下：

- `asr-whisper-cpp`：Composer/Integration 有精确 evidence，但正式系统禁止直接 import；当前正式服务已检测到本地 ASR 为 `available`。新机器必须单独提供并校验 runtime、模型和 fixture，缺失时标记 `not_installed`/`not_configured`。
- `ocr-paddleocr`：Composer/Integration 证明特定 Python 3.10 + 模型范围；正式依赖已包含 `paddleocr==3.7.0`/`paddlepaddle==3.3.1`，不代表通用 OCR 质量已验证。
- `ocr-rapidocr`：正式依赖已包含 `rapidocr_onnxruntime==1.4.4` 和 `onnxruntime==1.20.1`；它是 fallback，仍不能扩大为通用 OCR real-pass。
- `report-core`：只读、脱敏、合成数据投影有 Composer/Integration evidence；Formal 使用的是 StudyBuddy 自己的实现，不能复制实验室代码。
- SMTP/飞书：Composer 只验证 loopback 协议边界；Integration live smoke 需要明确授权和本地 secret，默认禁止执行。StudyBuddy delivery 保持 `off`。
- 文件解析、SQLite、检索、QA、Cards/Exercises、Plans/Notes、backup/restore 是正式仓库自己的组件，依赖以 `backend/requirements.txt` 和 `README.md` 为准。

## 新机器安装顺序

1. 安装并确认 Python 3.10、Node/npm、Git、PowerShell；Python 路径通过 `STUDYBUDDY_PYTHON` 或脚本参数传入。
2. 克隆四个 Git 仓库到上表路径；创建 data、log、test 目录，不从旧机器复制凭据。
3. 在正式仓库用 `D:\miniconda\py310\python.exe -m pip install -r backend/requirements.txt` 安装正式依赖，再执行 `pip check`。OCR/ASR 模型和本地 runtime 不由 pip 自动产生；必须从批准的离线 artifact 恢复并按 Composer evidence 校验。
4. 在正式仓库执行 `npm ci`，再用项目 Playwright 脚本安装 Chromium。
5. 执行 `check-studybuddy-workspace.ps1` 和 `check-development-environment.ps1`；先修复结构/依赖失败，再启动服务。
6. 用 `dev-studybuddy.ps1` 启动正式 data root，确认 liveness/health/readiness 均为 200。
7. 只通过脱敏 API/UI 保存和检查 AI、Embedding、SMTP、飞书元数据。不要把 key、授权码、Webhook 写进 prompt、Git、日志或测试 artifact。
8. 先完成新手手册场景 0，再单独验证导入、搜索、索引、问答和引用回溯；真实 Provider、SMTP 邮件、飞书发送必须单独授权。

## 可交付判定

新机器只有在环境检查为 `ok`、正式服务三项健康端点为 200、`python -m backend.app version` 为 `local-v1/schema-15`、delivery 仍为 off，并且组件状态没有被候选 evidence 偷换后，才算完成基础配置。真实 OCR/ASR、真实外发和真实 Provider 连接不能由安装包存在自动升级为 `available`。
