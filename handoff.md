# StudyBuddy 交接入口

工作目录：`H:\studybuddy`。开始前读取 [文档导航](docs/00-INDEX.md) 与 [产品需求](docs/01-PRD.md)。

产品需求以第一版子系统 PRD 为准；当前实现、验收结果、证据及缺口只读取 [capabilities.json](docs/capabilities.json)。本文件不维护第二份状态或测试数量。

## 本次交接相关入口

- 家长报告：[S6](docs/subsystems/S6-家长报告-ParentReport.md)，状态项 `s6-parent-report`。
- 课堂采集：[S7](docs/subsystems/S7-课堂采集-ClassCapture.md)，状态项 `s7-classroom-capture`、`x-ocr-paddleocr`、`x-asr-whisper`。
- SAPI 与恢复：[横切能力](docs/subsystems/X-横切能力.md)，状态项 `x-tts`、`x-backup-restore`。
- 启停、配置、备份恢复：[运维命令](docs/06-OPERATIONS.md)。
- 发布验收范围：[验收计划](docs/07-TEST-PLAN.md) 与状态源的 `release_acceptance`。

本轮证据位于 `H:\studybuddy-testerification\` 下的 `s6-s7-20261006cceptance.md`、`real-components-20261006cceptance.md`、`windows-release-20261006cceptance.md`。测试日志、数据库、音频、图片、组件二进制与安装包留在仓库之外。

## 运行时选择

ASR 使用 `whisper-cpp` Provider，并显式配置实际支持所选模型的 CLI。版本目录、已验证组合和旧运行时限制读取状态项 `x-asr-whisper`；不得仅因二进制存在就宣布识别可用。

组件验证使用 synthetic 输入与隔离数据根。正式设置仍由使用者通过设置页管理；不得将测试环境开关写回正式配置。真实云 Provider 与邮件/飞书外发须另行授权，外发默认关闭。

## 后续工作的边界

下一项以状态源中的产品缺口和 [P0 验收流程](docs/07-TEST-PLAN.md) 为依据。真实自用观察需由使用者持续操作并记录卡壳点；自动化验收不能代替它。

维护变更依照 [治理规则](docs/05-GOVERNANCE.md)，不因一个组件 smoke 通过而扩大全局结论。正式数据根为 `H:\studybuddy-data`，真实教材只读；不得访问教材 token、提交凭据、清理正式数据或自动外发报告。
