# Pi / pi-desktop 开发环境
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


StudyBuddy 的正式开发根目录是 `H:\studybuddy`。

当前工具、依赖和功能组件的唯一基线见 [`DEVELOPMENT_ENVIRONMENT_BASELINE.md`]([维护者看]DEVELOPMENT_ENVIRONMENT_BASELINE.md)；每次环境变更后从仓库根目录运行 `backend/scripts/check-development-environment.ps1`。

## 已确认的工具环境

- Python 3.10：`D:\miniconda\py310`
- Node.js：`D:\nodejs`
- Cygwin：`D:\cygwin64`
- PowerShell 7：`D:\PowerShell\7`
- Git：`D:\Git`
- Pi 用户目录：`C:\Users\Administrator\.pi`
- Pi-desktop 后代目录：`C:\Users\Administrator\.percho`
- OMP：`C:\Users\Administrator\.omp`
- Codex：`C:\Users\Administrator\.codex`
- Claude：`C:\Users\Administrator\.claude`

Pi 已信任 `H:\studybuddy`。不要把 StudyBuddy 的 API key、SMTP 密码或飞书 Webhook 复制到 Pi 配置；这些凭据只由 StudyBuddy 的运行配置管理。

## 启动开发服务

```powershell
powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\dev-studybuddy.ps1 `
  -DataRoot H:\studybuddy-data -Port 8787
```

脚本优先使用 `D:\miniconda\py310`，不存在时回退到 `H:\studybuddy\.venv`。delivery 始终设置为 off/false/false。

如果正式实例已经运行，脚本返回 `studybuddy_already_running` 并同步 data root 的 PID 文件，不会重复启动第二个实例。
