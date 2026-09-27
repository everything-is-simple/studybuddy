# StudyBuddy Pi Workflow
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


This guide keeps Pi sessions continuous while keeping project instructions short. It does not replace `AGENTS.md`, which contains only durable repository constraints.

## Start And Continue Work

- Start a named task with `pi -n "area-task"`, for example `pi -n "backend-provider-retry"`.
- Name an already-open session with `/name area-task`.
- Continue the latest project session with `pi -c`; use `pi -r` to select a prior session.
- Use `/tree` to return to an earlier point. Use `/fork` for an alternative approach and `/clone` to preserve a current branch before an experiment.

## Preserve Useful Context

- Prefer SoL-Pi observation pack and evidence-preserving reducer for large tool outputs. Those mechanisms keep a retrievable evidence id or receipt instead of leaving the full payload in the live prompt.
- Allow SoL-Pi online context compact for long sessions once context pressure is high. Do not wait for a manual `/compact` as the only compression path.
- When you still run `/compact`, require it to preserve: current goal, accepted decisions, key files, hard constraints, remaining steps, and verification commands.
- Use `/session` to inspect session size, token use, and cost before a long continuation. Displayed numbers are a snapshot, not a fixed savings promise.
- Session output that may be copied into project files or committable evidence may contain only a safe summary, a stable error code, and redacted paths. Never include provider keys, real textbook tokens, raw provider responses, original source text, databases, artifacts, or a complete session transcript.
- Store durable project facts, user preferences, and failure lessons with Hermes memory. Keep short-lived task state in the current session or its handoff, not in `AGENTS.md`.

## Model Defaults And Switching

- Open `/model`, select the preferred available model, then press `Ctrl+S` to save it as the startup default.
- Open `/thinking`, select the preferred level, then press `Ctrl+S` to save that default.
- Use `/scoped-models` to limit the cycle to available, credentialed models used for this project. Press `Ctrl+P` to cycle them and `Ctrl+L` to select directly.
- Do not put provider credentials, API keys, or machine-specific paths into repository files.

## Verify A Change

1. Restart Pi in `H:\studybuddy` and confirm the saved model and thinking level appear in the status bar.
2. Create a named session with `pi -n`, then use `pi -c` or `pi -r` to confirm it can be identified and continued.
3. Confirm `Ctrl+P` changes only among the models selected in `/scoped-models`.
4. Run `pi --verbose --offline` when investigating startup context or loaded resources. It is a diagnostic, not a token-usage measurement. Confirm the project `.pi/sol-pi.json` enables `observationPack`, `evidencePreservingReducer`, and `onlineContextCompact`, and that the run does not make network requests.
5. After a large `read` or `bash` result, confirm the observation ledger records an observation id plus original size or summary hash. After compact, the evidence id or receipt must still locate that result; the live context must not retain the full raw payload.
6. After an online compact, recover the current goal, accepted decisions, key files, hard constraints, remaining steps, and verification commands. Do not expect the full original tool output to return.
