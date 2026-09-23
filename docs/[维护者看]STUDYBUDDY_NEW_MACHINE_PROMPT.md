# 可直接交给 AI 的新机器配置 Prompt

将下面整段交给负责配置新机器的 AI。AI 必须先阅读 `H:\studybuddy\AGENTS.md`、`README.md` 和 `docs/[维护者看]NEW_MACHINE_SETUP.md`，再执行动作。

```text
你负责在 Windows 新机器上配置并启动 StudyBuddy。目标是本地单进程、单实例 FastAPI + SQLite 系统，不是云服务。

固定目录：
- 源码：H:\studybuddy
- 正式 data root：H:\studybuddy-data
- 日志：H:\studybuddy-log
- 组件独立测试：H:\studybuddy-composer
- 组件组合测试：H:\studybuddy-integration
- 正式测试 fixture/evidence：H:\studybuddy-test
- 真实教材源：H:\studybuddy-ChinaTextbook

必须遵守：
1. 先读取 H:\studybuddy\AGENTS.md、README.md、docs/[维护者看]NEW_MACHINE_SETUP.md。
2. 不读取、打印、复制或提交任何 API key、SMTP 授权码、飞书 Webhook、教材 token、数据库凭据或原始材料。
3. 不把 Composer/Integration 代码复制或 import 到正式仓库；它们只能提供独立 smoke/组合契约证据。
4. 不使用 H:\studybuddy-data\live；不让测试实例使用正式 data root。
5. 不执行真实 SMTP 邮件、真实飞书发送或真实 Provider 网络测试，除非用户在本轮明确授权。
6. report delivery 必须保持 mode=off、enabled=false、authorized=false。
7. 不把 fake、loopback 或历史 evidence 自动标记成真实能力；缺少当前 runtime/model 时标记 not_installed 或 not_verified。

执行顺序：
1. 确认 Git、PowerShell、Node/npm 和 Python 3.10 可执行；优先使用 D:\miniconda\py310\python.exe，或使用用户明确提供的 Python 路径。
2. 将正式源码、Composer、Integration、Test、ChinaTextbook 仓库分别放到固定目录；创建 data/log 目录。
3. 在 H:\studybuddy 执行（这会安装正式 OCR runtime 包；不会自动下载 OCR/ASR 模型）：
   D:\miniconda\py310\python.exe -m pip install -r backend\requirements.txt
   D:\miniconda\py310\python.exe -m pip check
4. 如果用户提供了经批准的 OCR/ASR 模型和 runtime artifact，按对应 `model-inventory.json`/组件卡校验 hash 后放置；没有 artifact 就保持能力为 `not_installed`，不要自行寻找或下载替代模型。然后在 H:\studybuddy 执行 npm ci；使用项目 Playwright 脚本安装 Chromium。
5. 执行：
   powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\check-studybuddy-workspace.ps1
   powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\check-development-environment.ps1 -SkipService
6. 启动正式服务：
   powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\dev-studybuddy.ps1 -DataRoot H:\studybuddy-data -Port 8787
7. 启动后检查 liveness、health、readiness、system/settings、system/capabilities、ai/capabilities，只记录 HTTP 状态和脱敏状态字段。
8. 运行 python -m backend.app version，必须确认 application=local-v1、schema=15。
9. 输出一份脱敏报告：工具版本、依赖/pip check、目录检查、服务健康、schema、delivery 开关状态、AI/Embedding/SMTP/飞书是否 configured/verified；不得输出 secret、路径之外的私密内容、SQL、traceback 或原始 provider 响应。
10. 未完成的 OCR/ASR/真实外发/真实 Provider 项目列为 not_installed、not_configured 或 not_verified，并写明下一步需要什么用户授权或本地 artifact。

禁止事项：不要为了让检查变绿而安装未经批准的候选模型，不要运行 live_smoke_*.py，不要把真实教材导入测试 data root，不要删除旧目录或用户已有文件。
```
