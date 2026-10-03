# StudyBuddy Handoff

更新时间：2026-10-03（America/Los_Angeles）

## 当前交接结论

StudyBuddy 是本机单进程 FastAPI + SQLite 学习系统，正式源码在 `H:\studybuddy`，正式数据根在 `H:\studybuddy-data`，服务地址为 `http://127.0.0.1:8787`。

当前正式页面入口：

- `http://127.0.0.1:8787/app/buddy.html`：Buddy 统一入口
- `http://127.0.0.1:8787/app/student.html`：学生视图
- `http://127.0.0.1:8787/app/parent.html`：家长视图

## 已完成事项

- Buddy 已成为默认首页，并支持学生/家长视图入口。
- 已将两个上游仓库的原始 PRD、Design、Task 文档归档到 `docs/legacy-product-references/`。
- 已新增原始文档映射：[PRD-DESIGN-TASK-MAP.md](docs/legacy-product-references/PRD-DESIGN-TASK-MAP.md)。
- 已把本地 OCR 模型配置到 `H:\PaddleOCR\models`。
- 已把 Whisper CLI 和模型配置到：
  - `H:\Whisper\cli\main.exe`
  - `H:\Whisper\Models\ggml-large-v3-turbo.bin`
- 已修正 `H:\studybuddy-data` 中遗留的旧 Composer 路径。
- 已删除 `H:\studybuddy-references` 中不进入正式运行路径的大型历史整包；参考组件卡和 smoke 脚本仍保留。

## 当前能力状态

最近一次正式服务能力检查结果：

| 能力 | 状态 |
|---|---|
| 文件解析 | `available` |
| OCR | `configured`，PaddleOCR |
| ASR | `configured`，Whisper CLI |
| 语义索引 | `configured`，使用现有 Embedding 配置 |
| QA | `configured` |
| 内容生成 | `configured` |
| 本地报告 | `available` |
| SMTP / 飞书外发 | `off` |

真实外部 Provider、真实 SMTP/飞书发送和真实教材质量仍需单独验证，不能仅凭 `configured` 标记为 `real-pass`。

## 启动与检查

正式启动命令：

```powershell
powershell -ExecutionPolicy Bypass -NoProfile -File H:\studybuddy\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-data -Port 8787
```

健康检查：

```powershell
Invoke-WebRequest http://127.0.0.1:8787/api/liveness
Invoke-WebRequest http://127.0.0.1:8787/api/health
Invoke-WebRequest http://127.0.0.1:8787/api/readiness
```

能力自检接口：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/system/capabilities/self-check
```

## 验证证据

本轮组件和运行环境证据在：

- `H:\studybuddy-test\verification\components-review-20261002\activation-result.json`
- `H:\studybuddy-test\verification\components-review-20261002\settings-path-update.json`
- `H:\studybuddy-test\verification\components-review-20261002\service-health.json`
- `H:\studybuddy-test\verification\components-review-20261002\report.md`

定向测试曾通过：

```text
37 passed
```

覆盖能力解析、保存配置、启动脚本 PID 归属和路径校验。

## 文档来源

原始产品资料来自：

- `H:\studybuddy-composer\references\ai-studybuddy`
- `H:\studybuddy-composer\references\pi-studybuddy`

正式归档位于：

- `H:\studybuddy\docs\legacy-product-references\ai-studybuddy`
- `H:\studybuddy\docs\legacy-product-references\pi-studybuddy`

原始 PRD 定义的业务主线是 S1 学习节奏、S2 资料笔记、S3 限时练习、S4 错题改错、S5 期末冲刺、S6 家长观察和 S7 课堂采集。原始文档中的完成状态只代表上游仓库版本，当前实现必须以正式 `STATUS.md`、`ARCHITECTURE.md`、`TODO.md` 和测试证据为准。

## 当前工作区注意事项

- 工作区已有未提交修改，来自前序能力配置、启动脚本、测试和文档工作；接手时先运行 `git status` 和 `git diff --stat`，不要直接覆盖。
- 不要把 `H:\studybuddy-composer` 或 `docs/legacy-product-references` 的源码直接导入正式系统。
- 不要读取、提交或展示 API key、密码、Webhook、Cookie、真实教材正文或 Provider 原始响应。
- 不要启用真实 SMTP、飞书外发或未授权的真实 Provider 测试。
- 组件测试目录是 `H:\studybuddy-composer`，组合测试目录是 `H:\studybuddy-integration`，脱敏证据目录是 `H:\studybuddy-test`。

## 推荐下一步

1. 用可视浏览器测试 Buddy、学生和家长三条入口的实际交互。
2. 按当前 PRD 映射检查计划、今日安排、进度和家长读取/创建计划流程是否覆盖用户主路径。
3. 将本轮需要保留的修改拆成独立提交后再推送，避免把既存未提交变更混在一起。
4. 对真实教材做单独、明确授权的 OCR/ASR 用户路径验证，并把结果写入 `H:\studybuddy-test\verification`。
