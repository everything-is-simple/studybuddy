# T-M5-009 `interaction-catalog`

**状态**：首版基线，`done`
**盘点日期**：2026-08-14
**任务**：T-M5-009
**证据来源**：`H:\pi-studybuddy-tmp\runs\T-M5-001\control-inventory.md`、`gap-register.md`、`ui-function-dependency-matrix.md`、当前 `src/`、`tests/`、docs/07、docs/08、docs/09。
**用途**：为 T-M5-005~008 提供稳定的 `CTRL-* → ACT-*` 输入；本表不把控件数当动作数。

## 1. 统计口径

- `CTRL-*` 是可见控件/交互入口；当前 T-M5-001 输入基线为 60 项。
- `ACT-*` 是一个用户意图在一个确认边界内完成的原子动作；一个控件可以拆成多个 `ACT-*`。
- RPC、领域命令、`TEST-*`、`E2E-*`、`UAT-*` 都不是动作，不能替代动作登记。
- 本首版只发布已能从当前证据确认的动作；不能从证据确认的控件保留为 `待分解`，不猜测动作总数或覆盖率。

## 2. 已确认动作（首版）

| ACT-ID | 用户目标 | CTRL 来源 | 前置/确认边界 | 运行/逻辑 | DATA | ERR | TEST/UAT | 当前状态 |
|---|---|---|---|---|---|---|---|---|
| ACT-SHELL-001 | 切换可见 Tab | CTRL-SHELL-01 | 点击 Tab，视图切换完成 | AppShell `onSelectTab` | 无直接写入 | ERR-UI-001 | TEST-SHELL-001 | 部分证据 |
| ACT-S1-001 | 创建学期 | CTRL-SHELL-02/CTRL-HOME-02 | 填写并确认创建 | S1 typed RPC/handler | DATA-BIZ-001 | ERR-VALIDATION-001 | UAT-S1-001 | 已证实 |
| ACT-S1-002 | 创建课程 | CTRL-SHELL-02 | 填写并确认创建 | S1 typed RPC/handler | DATA-BIZ-002 | ERR-VALIDATION-001 | UAT-S1-002 | 已证实 |
| ACT-S1-003 | 创建任务并完成 | CTRL-HOME-01 | 创建、点击完成、确认状态 | S1 RPC/状态迁移 | DATA-BIZ-003 | ERR-STATE-001 | UAT-S1-003 | 已证实 |
| ACT-S1-004 | 确认考试并查看 | CTRL-HOME-01 | 确认考试后从首页查看 | S1 RPC/状态迁移 | DATA-BIZ-004 | ERR-STATE-001 | UAT-S1-004 | 已证实 |
| ACT-S2-001 | 通过文件选择导入资料 | CTRL-MATERIAL-01 | 选择文件并确认上传 | dialog capability → materials.upload | DATA-FILE-001/DATA-BIZ-005 | ERR-FILE-001 | UAT-S2-001 | 已证实 |
| ACT-S2-002 | 启动转换或重试 | CTRL-MATERIAL-02 | 点击转换/失败后点击重试 | materials.convert/retryConversion | DATA-BIZ-005/DATA-TMP-001 | ERR-DEPENDENCY-001 | TEST-S2-002/UAT-S2-002 | 部分证据 |
| ACT-S2-003 | 选择资料读取笔记 | CTRL-NOTE-01 | 局部显式选择资料 | notes.get | DATA-BIZ-005/DATA-BIZ-006 | ERR-NOT_FOUND-001 | UAT-S2-003 | 已证实 |
| ACT-S2-004 | 编辑并保存笔记 | CTRL-NOTE-02 | 保存按钮确认写入 | notes.update | DATA-BIZ-006 | ERR-READONLY-001 | TEST-S2-004/UAT-S2-004 | 已证实 |
| ACT-S3-001 | 选择模块并开始练习 | CTRL-PRACTICE-01 | 选择模块、题数、开始 | practice.start | DATA-BIZ-007 | ERR-VALIDATION-001 | UAT-S3-001 | 已证实 |
| ACT-S3-002 | 作答并提交练习 | CTRL-PRACTICE-02/03 | 作答、提交、结果可见 | practice.answer/submit | DATA-BIZ-007/DATA-BIZ-008 | ERR-STATE-001 | UAT-S3-002 | 已证实 |
| ACT-S4-001 | 筛选并查看错题 | CTRL-MISTAKE-01/02 | 选择筛选并打开详情 | mistakes.list/get | DATA-BIZ-009 | ERR-NOT_FOUND-001 | TEST-S4-001 | 部分证据 |
| ACT-S4-002 | 重做错题并确认结果 | CTRL-MISTAKE-03 | 选择重做结果并提交 | mistakes.redo | DATA-BIZ-009/DATA-BIZ-010 | ERR-STATE-001 | UAT-S4-002 | 部分证据 |
| ACT-S5-001 | 选择已确认考试 | CTRL-CRAM-01 | 选择考试；未确认时不得继续 | exams.list / cram gate | DATA-BIZ-004 | ERR-STATE-001 | UAT-S5-001 | 已证实 |
| ACT-S5-002 | 生成并开始模拟考 | CTRL-CRAM-02 | 题数/时间确认后生成 | mock-exams handlers | DATA-BIZ-011 | ERR-DEPENDENCY-001 | UAT-S5-002 | 已证实 |
| ACT-S5-003 | 提交模拟考并读取结果 | CTRL-CRAM-03 | 提交后结果页可见，重启后再读 | mock-exams submit/result | DATA-BIZ-011/DATA-BIZ-012 | ERR-STATE-001 | UAT-S5-003 | 已证实 |
| ACT-S6-001 | 查看报告并朗读脱敏详情 | CTRL-REPORT-01..05 | 报告详情可见后点击朗读 | ReportTab + existing TTS callback | DATA-BIZ-* 待细化 | ERR-STATE-001 | renderer contract test；原生详情未覆盖 | 部分证据 |
| ACT-S7-001 | 合规确认并选择 WAV | CTRL-CAPTURE-01..04 | 勾选授权后选择受支持文件 | CaptureTab + native file dialog | DATA-FILE-* 待细化 | ERR-FILE-001/ERR-DEPENDENCY-001 | 原生 UAT 37/38/39；成功转写与结果重启回读属于 T-M5-006 依赖范围 | 部分证据/依赖阻塞 |
| ACT-TTS-001 | 从速背卡/报告/转写结果朗读 | CTRL-TTS-01..03 + Tab text zones | 可见文本且目标内容非空 | AppShell `onSpeakText` + useTtsPlayback | review event only after explicit mark | ERR-DEPENDENCY-001 | renderer contract + E2E regression；native content entry not reached | 部分证据 |
| ACT-BACKUP-001 | 选择覆盖恢复并确认风险 | CTRL-BACKUP-01..04 | `overwrite` first shows confirm/cancel; confirm invokes restore | BackupPanel + backup.restore | DATA-FILE-003 | ERR-BACKUP-001 | renderer contract + RPC regression；native restore not covered | 部分证据 |
| ACT-SETTINGS-001 | 打开设置并保存通用偏好 | CTRL-SETTINGS-01..06 | Save action and fixed feedback visible | SettingsPage + settings RPC | DATA-CFG-003 | ERR-SQLITE-001 | native UAT 21/22/60；隔离 settings.json 回读 61 | 已证实 |

## 3. 控件输入基线（未等同于动作）

下表保留 T-M5-001 的 60 项控件盘点；`待分解` 表示尚未形成可发布的原子 `ACT-*`，不是 PASS/FAIL 结论。

| CTRL-ID | 页面/区域 | 当前事实摘要 | 后续动作登记 | 当前证据 |
|---|---|---|---|---|
| CTRL-SHELL-01 | TabBar | 10 个 Tab 可见；接线与逐控件可用性需分开 | 已映射 ACT-SHELL-001；其余待分解 | 部分证据 |
| CTRL-SHELL-02 | 左侧学期树 | 选择与展开存在；创建语义由 S1 任务覆盖 | 已映射 ACT-S1-001/002 | 已证实 |
| CTRL-SHELL-03 | 左侧会话 | 搜索/新建/选择/重命名/导出/删除 | 待分解，消费 T-M5-003 事实 | 部分证据 |
| CTRL-SHELL-04 | 顶部设置 | 打开设置/返回工作台 | 待分解，消费 T-M5-005 | 部分证据 |
| CTRL-SHELL-05 | 状态栏 | 验证按钮和状态展示 | 待分解，消费 T-M5-005 | 未覆盖 |
| CTRL-SHELL-06 | 右侧上下文 | 当前课程/目标/薄弱点展示 | 待分解，消费 T-M5-005 | 未覆盖 |
| CTRL-CHAT-01..07 | 对话 | 模型、学科、目标、错题、工具、引用、发送 | 待分解，保留 T-M5-003 证据 | 部分证据 |
| CTRL-HOME-01..02 | 首页 | 简报/任务/考试与空态 | 已映射 S1 动作；其余待分解 | 部分证据 |
| CTRL-MATERIAL-01..04 | 资料 | 上传/转换/生成笔记/预览 | 已映射 ACT-S2-001/002；其余待分解 | 部分证据 |
| CTRL-NOTE-01..05 | 笔记 | 选择/编辑/保存/朗读/学习状态/渲染 | 已映射 ACT-S2-003/004；其余待分解 | 部分证据 |
| CTRL-PRACTICE-01..05 | 练习 | 选模块/作答/导航/提交/重试 | 已映射 ACT-S3-001/002；其余待分解 | 部分证据 |
| CTRL-MISTAKE-01..04 | 错题 | 筛选/详情/分类/重做/复盘 | 已映射 ACT-S4-001/002；其余待分解 | 部分证据 |
| CTRL-CRAM-01..05 | 冲刺 | 考试/生成/作答/速背/计划 | 已映射 ACT-S5-001..003；朗读速背卡入口已实现但本轮未到达 | 部分证据 |
| CTRL-REPORT-01..05 | 报告 | 生成/详情/冻结/投递/导出/朗读 | 已映射 ACT-S6-001；详情朗读入口已实现，原生详情未覆盖 | 部分证据 |
| CTRL-CAPTURE-01..04 | 采集 | 授权/WAV/转写/保存/朗读 | 已映射 ACT-S7-001；合规空态原生可见，whisper/成功转写不在本任务 | 部分证据/阻塞 |
| CTRL-TTS-01..03 | TTS | 引擎/播放/暂停/停止/复习标记 | 已映射 ACT-TTS-001；常驻控制和自动化通过，完整 UI 内容入口未覆盖 | 部分证据 |
| CTRL-BACKUP-01..04 | 备份 | 选择/备份/调度/恢复/历史 | 已映射 ACT-BACKUP-001；overwrite 确认已实现，真实恢复未覆盖 | 部分证据 |
| CTRL-SETTINGS-01..06 | 设置 | 凭证/设置/模型/工具链/实验/技能包 | 已映射 ACT-SETTINGS-001；打开/保存反馈可见，重启值未覆盖 | 部分证据 |

## 4. 覆盖状态与停止条件

- 首版正式 `ACT-*` 行数为本文件第 2 节可见行数；60 个 `CTRL-*` 是输入基线，不是动作总数。
- 自动化覆盖、负向覆盖、持久化覆盖、真机 UAT 覆盖率在完整动作拆分前标记为 `未覆盖/待核验`，不发布百分比。
- 所有来源路径仅作证据定位；DOM 不得出现完整 UUID、绝对路径、密钥或错误栈。
- 若继续拆分需要新增 API/schema/handler/入口，按 docs/13 §9.3 停止并请求裁决。

## 5. 下游消费

- T-M5-005：补齐报告、采集、TTS、备份、设置和整体 UX 的动作拆分。
- T-M5-006：为依赖健康、离线/不可用降级和安装边界补充动作与错误映射。
- T-M5-007：按完整 `ACT-*` 清单进行干净 Windows 真机 UAT。
- T-M5-008：将发布候选的动作覆盖、恢复和 Git 证据写入 `release-evidence.md`。
