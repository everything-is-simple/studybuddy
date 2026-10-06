# T-M5-009 `system-traceability`

**状态**：首版基线，`done`
**盘点日期**：2026-08-14
**任务**：T-M5-009
**矩阵方向**：UI → 运行 → 逻辑 → 数据 → 测试 → 运维；任何一列缺证据都不能把整行标为通过。

## 1. 状态语义

| 状态 | 含义 |
|---|---|
| `已证实` | 当前有对应实现、测试或非注入可见 UI 证据，且证据范围与结论同等宽度 |
| `部分证据` | 有接线、局部路径、renderer 自动化或历史证据，但仍缺完整闭环/重启/UAT |
| `未覆盖` | 没有足够证据，不能由静态实现推断 |
| `阻塞` | 依赖、范围、数据所有者或安全边界未解决 |
| `不适用` | 明确不属于当前任务/当前阶段，并记录理由 |

## 2. 首版跨层矩阵

| TRACE-ID | UI/ACT | 运行能力 | 逻辑/handler | DATA | TEST/E2E/UAT | OPS/release | 状态/缺口 |
|---|---|---|---|---|---|---|---|
| TRACE-S1-001 | ACT-S1-001 创建学期 | AppShell→typed RPC | semesters.create + 校验 | DATA-BIZ-001 | UAT-S1-001；重启回读 | OPS-START-001；release §UAT | 已证实 |
| TRACE-S1-002 | ACT-S1-002 创建课程 | AppShell→typed RPC | courses.create + FK | DATA-BIZ-002 | UAT-S1-002 | OPS-START-001 | 已证实 |
| TRACE-S2-001 | ACT-S2-001 导入资料 | dialog capability | materials.upload + storage guard | DATA-FILE-001/002 + DATA-BIZ-005 | UAT-S2-001 | OPS-DATA-001 | 部分证据 |
| TRACE-S2-002 | ACT-S2-002 转换/重试 | host dependency adapter | materials.convert/retry | DATA-BIZ-005 + DATA-TMP-001 | TEST-S2-002 | OPS-DEP-001 | 阻塞 |
| TRACE-S2-003 | ACT-S2-004 保存笔记 | preload→host RPC | notes.update/read-only | DATA-BIZ-006 | UAT-S2-004 + restart | OPS-DATA-001 | 已证实 |
| TRACE-S3-001 | ACT-S3-001 开始练习 | renderer state + RPC | practice.start | DATA-BIZ-007 | UAT-S3-001 | OPS-DATA-001 | 已证实 |
| TRACE-S3-002 | ACT-S3-002 提交并读结果 | renderer state + RPC | practice.submit/getResult | DATA-BIZ-007/008 | UAT-S3-002 + second restart | OPS-DATA-001 | 已证实 |
| TRACE-S4-001 | ACT-S4-001 查看错题 | renderer state + RPC | mistakes.list/get | DATA-BIZ-009 | TEST-S4-001 | OPS-DATA-001 | 部分证据 |
| TRACE-S5-001 | ACT-S5-001 选择已确认考试 | renderer gate + RPC | exams.list / confirmed gate | DATA-BIZ-004 | UAT-S5-001 | OPS-START-001 | 已证实 |
| TRACE-S5-002 | ACT-S5-003 提交模拟考并回读 | renderer state + RPC | mock-exams submit/result | DATA-BIZ-011/012 | UAT-S5-003 + restart | OPS-DATA-001 | 已证实 |
| TRACE-CHAT-001 | T-M5-003 对话动作待分解 | agent host + model runtime | sessions/agent.send | DATA-MEM-003 + DATA-CFG-001/002 | T-M5-003 UAT evidence | OPS-DEP-001 | 部分证据 |
| TRACE-S6-001 | ACT-S6-001 报告详情朗读 | reports/deliveries RPC + existing TTS callback | ReportTab/报告 handlers 已接线 | DATA-BIZ-* 待细化 | renderer contract/E2E；原生详情未覆盖 | OPS-REPORT-001 | 部分证据 |
| TRACE-S7-001 | ACT-S7-001 合规确认/WAV 选择 | capture + whisper boundary | classCapture handlers | DATA-FILE-* / DATA-BIZ-* | 原生 UAT 37/38/39 只到合规空态；依赖自包含未证实 | OPS-DEP-001 | 阻塞 |
| TRACE-TTS-001 | ACT-TTS-001 速背卡/报告/转写朗读 | AppShell useTtsPlayback | existing tts handlers | review event only after explicit mark | renderer contract/E2E；原生内容入口未到达 | OPS-DEP-001 | 部分证据 |
| TRACE-BACKUP-001 | ACT-BACKUP-001 overwrite 确认 | backup RPC/scheduler | BackupPanel + backup handlers | DATA-FILE-003 + all DATA-BIZ | renderer contract/RPC；真实恢复回读待补 | OPS-BACKUP-001 | 部分证据 |
| TRACE-SETTINGS-001 | ACT-SETTINGS-001 设置保存反馈 | settings + credential-vault | config/vault handlers | DATA-CFG-003 | 原生打开/保存反馈 21/22；重启值未覆盖 | OPS-SEC-001 | 部分证据 |

## 3. 证据分层约束

- `TEST-*` 证明单件/集成/系统逻辑；`E2E-*` 证明真实 Electron 进程和受控隔离根；`UAT-*` 只有通过可见 UI、非注入、全新隔离根形成的真机证据才成立。
- renderer 自动化、`webContents.executeJavaScript`、CDP、handler 直调、数据库预置和测试 `test.*` seed 不能升级为真机 UAT。
- `release-evidence.md` 的发布通过必须同时满足质量门、真机 UAT、数据隔离、安装/升级/恢复和 Git/治理证据；单项绿灯不能替代全链。

## 4. 维护规则

功能任务新增或改变 `CTRL-*`、`ACT-*`、`ERR-*`、`DATA-*`、RPC、schema、文件落点或运维责任时，必须先更新本矩阵和对应目录，再开始实现。若需要新增 API/schema/handler/入口，停止并请求任务范围裁决。
