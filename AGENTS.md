# StudyBuddy Agent Instructions

StudyBuddy 是一个本机、单进程的 FastAPI + SQLite 学习闭环系统，服务一名在 Windows 上学习的学生。开始任何任务前先读 [`docs/00-INDEX.md`](docs/00-INDEX.md)，然后读 [`docs/01-PRD.md`](docs/01-PRD.md) 和相关子系统文档。

## 交付

- 一个切片必须改变学生在浏览器或 CLI 里能做的事；只改审计、契约或状态的工作需要明确要求。
- 完成后更新 [`docs/capabilities.json`](docs/capabilities.json)（唯一状态源）和相关子系统文档的验收/缺口。不在其他文档里复述状态或测试数。
- `implemented` 不是 `real-pass`；未验证范围写 `not_verified`。缺失组件以 `not_installed` / `not_configured` 呈现。
- `report_delivery` 默认关闭，逐次授权。

## 边界

- 源码 `H:\studybuddy`：正式代码 `backend/app/`，正式测试 `backend/tests/`，文档 `docs/`。
- 正式 data_root `H:\studybuddy-data`（根目录本身；不要用 `live/`）。测试与证据 `H:\studybuddy-test`。
- 组件先在 `H:\studybuddy-composer` 独立测试，再到 `H:\studybuddy-integration` 组合验证，然后按契约在正式仓库重新实现，不复制源码。
- 真实教材 `H:\studybuddy-ChinaTextbook` 只读；其中 token 是密钥，永不读取、复制、提交或清理。
- 不提交数据库、原文件、产物、密钥、私有路径、测试输出；不暴露路径、SQL、原文、traceback、Provider 原始错误或密钥。
- 目录保留/清理规则见 [`docs/06-OPERATIONS.md`](docs/06-OPERATIONS.md) §5。

## 工程

- schema 变更只走 `backend/app/migrations/runner.py`：连续、幂等、事务内、带回滚测试。
- 遵循 `revision → chunks → retrieval → citations → Q&A → 模块/练习`；生成内容先是带引用的草稿，不覆盖已确认编辑。
- 新增/重写的 `.py .js .css .html .ps1 .json` 文件 ≤ 32 KiB（`python backend/scripts/check-source-size.py`）。
- 测试：`D:\miniconda\py310\python.exe -m pytest backend/tests/`，或 `backend/scripts/test-backend.ps1`。先跑聚焦测试，涉及基础设施/迁移/存储/API 再跑全量。浏览器 spec 用 `backend/scripts/test-browser.ps1 <spec>` 串行跑。
- 只支持本机单进程、单实例、本地存储；不声称共享 data_root、多 worker、云、多用户或真实断电恢复。

## AI 执行门禁

任务需写明：角色、唯一目标、允许读写的绝对路径、指定命令/端口/数据根、禁止操作、停止条件、证据路径。未写明的不是默认授权。

- 原样使用指定的工具、命令、URL、端口和数据根；不可用时返回 `BLOCKED`，不得替换。
- 不得用 curl、HTML 解析、headless 或推测结果冒充可视浏览器操作。
- 未授权不得启动正式服务、调用真实 Provider/OCR/ASR、发送邮件/飞书、修改配置或删除数据。
- 结果状态统一用 `PASS / FAIL / BLOCKED / LIMITED / NOT_APPLICABLE / NOT_VERIFIED`。
- 验证日志、截图、报告写入 `H:\studybuddy-test\verification\`。交付前运行 `git diff --check`。

运行基线：正式 `start-studybuddy.ps1 -DataRoot H:\studybuddy-data -Port 8787`；隔离 `-DataRoot H:\studybuddy-test\data_root`；首页 `http://127.0.0.1:8787/app/buddy.html`；健康端点 `/api/liveness` `/api/health` `/api/readiness`。完整命令见 [`docs/06-OPERATIONS.md`](docs/06-OPERATIONS.md) §1。
