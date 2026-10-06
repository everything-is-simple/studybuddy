# StudyBuddy

本机单进程学习闭环系统：学生在 Windows 上导入资料、建计划、练习、改错、备考，家长收脱敏报告。

## 快速启动

```powershell
# 启动（默认 127.0.0.1:8787）
powershell -ExecutionPolicy Bypass -NoProfile -File H:\studybuddy\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-data -Port 8787

# 浏览器打开
http://127.0.0.1:8787/app/today.html
```

健康检查 `/api/liveness` `/api/health` `/api/readiness`；停止用 `stop-studybuddy.ps1`。完整运维见 [`docs/06-OPERATIONS.md`](docs/06-OPERATIONS.md)。

## 当前能力

- **Today**：待办 ≤ 5 项，按紧急/重要/建议排序；点"开始""完成"写进度事件。
- **资料与知识模块**：导入、索引、AI 抽取草稿、人工确认、按模块练习、掌握度投影。
- **限时练习、错题、冲刺**：规则批改、错题复盘、重做闭合、倒计时。
- **计划与节奏**：激活计划、排日程、记录进度、依赖。
- **朗读（TTS）**：知识模块入口、fake/SAPI/edge-tts Provider、缓存 WAV，不写学习事实。

外发报告、真实 OCR/ASR、真实邮件/飞书、Electron 壳、通用对话均未实现或已退出主线。状态见 [`docs/capabilities.json`](docs/capabilities.json)。

## 文档

| 文档 | 用途 |
|---|---|
| [`docs/00-INDEX.md`](docs/00-INDEX.md) | 导航入口 |
| [`docs/01-PRD.md`](docs/01-PRD.md) | 产品需求（为谁、解决什么） |
| [`docs/02-SUBSYSTEMS.md`](docs/02-SUBSYSTEMS.md) | 七个子系统地图 |
| [`docs/03-ARCHITECTURE.md`](docs/03-ARCHITECTURE.md) | 技术栈、代码布局、数据流 |
| [`docs/05-GOVERNANCE.md`](docs/05-GOVERNANCE.md) | 代码、测试、组件、文档规则 |
| [`docs/06-OPERATIONS.md`](docs/06-OPERATIONS.md) | 启动、备份恢复、迁移、新机器 |
| [`docs/07-TEST-PLAN.md`](docs/07-TEST-PLAN.md) | P0 主闭环验收、证据位置 |
| [`docs/08-DECISIONS.md`](docs/08-DECISIONS.md) | 决策记录 |
| [`docs/subsystems/`](docs/subsystems/) | S1–S7 + 横切能力详细设计 |
| [`docs/user/`](docs/user/) | 使用手册、新手指南 |

## 目录

| 目录 | 用途 |
|---|---|
| `H:\studybuddy` | 源码、测试、文档 |
| `H:\studybuddy-data` | 正式 data_root（SQLite、原文件、配置） |
| `H:\studybuddy-test` | 隔离测试、证据 |
| `H:\studybuddy-composer` / `-integration` | 组件试炼 / 组合验证 |
| `H:\studybuddy-ChinaTextbook` | 真实教材（只读；token 是密钥） |

## 测试

```powershell
# 后端（Python 3.10）
powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\test-backend.ps1

# 浏览器（串行，一次一个 spec）
powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\test-browser.ps1 <spec>
```

新代码 ≤ 32 KiB；schema 变更走 `migrations/runner.py`；生成内容先是草稿；不提交数据库/密钥/路径。详见 [`docs/05-GOVERNANCE.md`](docs/05-GOVERNANCE.md)。

## 支持范围

✅ 本机单进程、单实例、SQLite、本地文件、Windows  
❌ 多 worker、共享 data_root、云同步、多用户、真实断电恢复

## 远端

`https://github.com/everything-is-simple/studybuddy.git`

## Agent 执行门禁

开始前读 [`AGENTS.md`](AGENTS.md) 和 [`docs/00-INDEX.md`](docs/00-INDEX.md)。任务需写明：角色、唯一目标、允许读写路径、指定命令/数据根、禁止操作、证据路径。未写明的不是默认授权。
