# Pi / pi-desktop 开发环境

StudyBuddy 的正式开发根目录是 `H:\studybuddy`。

当前工具、依赖和功能组件的唯一基线见 [`DEVELOPMENT_ENVIRONMENT_BASELINE.md`]([维护者看]DEVELOPMENT_ENVIRONMENT_BASELINE.md)；每次环境变更后从仓库根目录运行 `backend/scripts/check-development-environment.ps1`。

## 已确认的工具环境

- Python 3.10：`D:\miniconda\py310`
- Node.js：`D:\nodejs`
- Cygwin：`D:\cygwin64`
- PowerShell 7：`C:\Program Files\PowerShell\7`
- Git：`C:\Program Files\Git`
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
