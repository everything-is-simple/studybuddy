# StudyBuddy 开发环境与功能组件基线
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


更新时间：2026-09-22

本文是 StudyBuddy 本地开发入口的当前基线。它记录本机已经安装并验证的运行工具，以及正式系统实际使用的功能组件。历史阶段报告、fake provider 和候选组件不能单独把能力标记为 `available`。

## 正式入口

- 源码仓库：`H:\studybuddy`
- 正式运行 data root：`H:\studybuddy-data`
- 正式日志目录：`H:\studybuddy-log`
- 服务：`127.0.0.1:8787`，单进程、单实例、delivery 默认关闭
- Python：`D:\miniconda\py310\python.exe`
- 当前 schema：v15

启动、健康检查和停止：

```powershell
powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\dev-studybuddy.ps1 `
  -DataRoot H:\studybuddy-data -Port 8787
powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\health-studybuddy.ps1 -Port 8787
powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\check-development-environment.ps1
```

目录职责和新机器重建顺序见 [`NEW_MACHINE_SETUP.md`]([维护者看]NEW_MACHINE_SETUP.md)；可直接交给新机器 AI 的完整配置提示词见 [`STUDYBUDDY_NEW_MACHINE_PROMPT.md`]([维护者看]STUDYBUDDY_NEW_MACHINE_PROMPT.md)。

## 已验证的开发工具

| 组件 | 当前标准位置/版本 | 用途 | 状态 |
|---|---|---|---|
| Miniconda Python | `D:\miniconda\py310` / Python 3.10 | StudyBuddy 运行、CLI、后端测试 | `available`，依赖已安装，`pip check` 通过 |
| Node.js / npm | `D:\nodejs` / 24.14.0 / 11.9.0 | 浏览器测试工具链 | `available` |
| Playwright | `@playwright/test` 1.62.1 | Chromium 浏览器门禁 | `available`，Chromium、Headless Shell、FFmpeg、Winldd 已安装 |
| PowerShell | `C:\Program Files\PowerShell\7` / 7.6.3 | 启动、健康、测试脚本 | `available` |
| Git | `C:\Program Files\Git` / 2.55.0 | 版本管理和推送 | `available` |
| Pi | `C:\Users\Administrator\.pi` / 0.87.0 | 项目开发会话 | `available`，已信任本仓库 |
| pi-desktop | `C:\Users\Administrator\.percho` | Pi 桌面后代运行目录 | `available` |
| OMP | `C:\Users\Administrator\.omp` / 18.2.8 | shell/开发环境辅助 | `available` |
| Codex CLI | `C:\Users\Administrator\.codex` / 0.155.1 | 代码任务辅助 | `available` |
| Claude Code | `C:\Users\Administrator\.claude` / 2.1.278 | 代码任务辅助 | `available` |

StudyBuddy 的 Python 运行依赖为：FastAPI、Uvicorn、Pydantic、python-multipart、python-docx、pypdf、PyMuPDF、python-pptx、pytest、httpx。它们是当前代码和正式测试使用的依赖；只安装但未被正式代码调用的包不列入功能能力。

## StudyBuddy 实际功能组件

| 功能组件 | 正式实现/依赖 | 当前状态与边界 |
|---|---|---|
| HTTP 服务与本地存储 | FastAPI、Uvicorn、SQLite | `available`；仅支持本地单进程、单实例 |
| 材料导入与解析 | TXT、Markdown、PDF、DOCX、PPTX parser；python-docx、pypdf、PyMuPDF、python-pptx | `available`；RTF、旧 DOC、旧 PPT 明确拒绝 |
| 材料生命周期 | 列表、详情、搜索、回收站、恢复、导出 | `available`；原件和正文有独立安全边界 |
| 索引与检索 | SQLite FTS5 词法检索、embedding 存储、vector/hybrid retrieval | `available`；向量能力依赖 embedding provider 配置，真实 provider 仍按精确配置验证 |
| 问答与引用 | QA thread、retrieval run、citation、原文定位 | `implemented`；fake/局部 provider 范围有证据，真实 provider 全覆盖为 `not_verified` |
| Cards / Exercises | 草稿、引用、确认/拒绝、复习和练习记录 | `implemented`；生成能力依赖 LLM provider |
| Goals / Plans / Notes / Rhythm | 目标、模块、计划、进度、笔记和节奏 | `implemented`；不包含自动 scheduler/worker |
| Capture / transcription | capture、loopback/deterministic transcription、草稿确认后进入材料管线 | `implemented`；真实音频格式、语言、并发和长时稳定性为 `not_verified` |
| OCR | PaddleOCR 主引擎 + RapidOCR ONNX fallback，使用 Composer 已验证模型 | `available` 仅限当前 Python 3.10、模型和离线 C1/C2 scope；通用准确率、多语言、容量仍为 `not_verified` |
| Reports | daily/weekly/monthly/exam_alert 脱敏只读投影与导出 | `implemented`；来源不足时显式降级 |
| SMTP / 飞书 delivery | 配置元数据和 allowlisted dry-run 审计 | 默认 `off`；`enabled=false`、`authorized=false`；不执行真实发送 |
| Backup / verify / restore | SQLite Online Backup、manifest、完整性和 schema 检查 | `available`；restore 只写入空目标，不自动 repair |

Composer、Integration 和 Test 的关系不是“把实验代码 import 进正式环境”：Composer/Integration 只保留组件证据和组合契约，正式系统使用自己的 Provider 适配器。当前机器的 OCR 包、Composer 模型和离线 C1/C2 证据已具备；Whisper ASR 由正式服务的已配置本地 runtime 提供，缺失时仍必须由能力接口标记为 `not_installed` 或 `not_configured`。

## AI、邮件和飞书配置规则

配置状态只能通过脱敏的系统设置/能力接口或 UI 判断，区分 `configured`、`verified`、`available`、`not_configured` 和 `not_verified`。本基线不保存、不复制、不回显 API key、SMTP 授权码、Webhook、材料 token 或原始 provider 错误。

`report_delivery_mode=off`、`report_delivery_enabled=false`、`report_delivery_authorized=false` 是默认安全基线。SMTP 测试邮件、飞书发送和真实 Provider 网络连接测试必须由用户单独授权后再执行。

## 自动复核

从 `H:\studybuddy` 运行 `backend/scripts/check-development-environment.ps1`。脚本只输出脱敏的 JSON 状态；它检查工具可执行性、Python 导入、`pip check`、应用 version、当前服务三项健康端点和项目 Playwright CLI，不读取配置文件中的 secret，也不触发外部网络副作用。
