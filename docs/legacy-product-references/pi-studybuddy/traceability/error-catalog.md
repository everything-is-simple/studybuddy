# T-M5-009 `error-catalog`

**状态**：首版基线，`done`
**盘点日期**：2026-08-14
**任务**：T-M5-009
**规则来源**：docs/06 §2.2/§2.3、docs/08 §1/§6/§7、docs/13 §4/§6/§9、当前 handlers 与 renderer 错误分支。

## 1. 错误责任模型

`ERR-*` 描述用户可观察的失败边界，不等同于异常栈，也不等同于 RPC 方法。每条必须回答：触发条件、责任层、用户消息、恢复动作、日志允许字段和证据状态。未知责任不得写成“系统错误后重试”并结束。

责任层：`renderer`（呈现/状态机）、`preload/main`（能力与 IPC）、`host/handler`（校验/事务）、`data/file`（SQLite/文件副作用）、`dependency`（WPS/OCR/whisper/模型）、`governance`（证据或范围不成立）。

## 2. 错误目录

| ERR-ID | 触发边界 | 责任层 | 对用户的可操作消息 | 恢复/停止动作 | 关联 ACT | 证据状态 |
|---|---|---|---|---|---|---|
| ERR-VALIDATION-001 | 必填字段、题数、状态转换或重复名称不合法 | renderer + handler | 请检查输入或选择唯一模块后重试 | 修正输入；不得写入半成品 | ACT-S1-001/002、ACT-S3-001 | 已证实 |
| ERR-NOT_FOUND-001 | 资料、课程、错题或会话已不存在 | handler/data | 未找到该内容，请刷新后重试 | 刷新列表；不可伪造成功 | ACT-S2-003/ACT-S4-001 | 部分证据 |
| ERR-READONLY-001 | 归档学期或只读资料发生写入 | handler | 当前内容已归档，不能修改 | 返回或选择活动学期 | ACT-S2-004 | 已登记 |
| ERR-STATE-001 | 未确认考试、已提交重复提交、重启后状态不一致 | renderer + handler | 当前状态不允许此操作，请刷新后重试 | 读取真实状态；禁止按钮重复提交 | ACT-S1-003/ACT-S4-002/ACT-S5-001..003 | 部分证据 |
| ERR-MODEL-001 | 无可用模型/凭证，契约错误码 `MODEL_NOT_CONFIGURED` | dependency + host | 尚未配置可用 AI 模型，请先在设置中完成配置 | 设置页配置/重试；不得回退 fixture | ACT-S2-002 | 已证实 |
| ERR-FILE-001 | 文件选择取消、MIME/大小/路径白名单失败 | preload/main + handler | 文件不可用，请选择受支持的文件后重试 | 重新选择；清理 capability 暂存 | ACT-S2-001 | 部分证据 |
| ERR-DEPENDENCY-001 | WPS/OCR/whisper/外部 AI 不可用或未随包 | dependency | 当前能力不可用，原因与可恢复入口待补齐 | 显示不可用边界；不伪称转换/转写成功 | ACT-S2-002/ACT-S5-002 | 阻塞/未覆盖 |
| ERR-SQLITE-001 | SQLite 初始化、锁、FK/CHECK/事务失败 | data | 数据保存失败，请稍后重试；如持续请重启应用 | 回滚事务、关闭连接、保留诊断摘要 | 相关写入 ACT | 部分证据 |
| ERR-FILE-DATA-001 | 文件写入成功但数据库写入失败，或反向失败 | data/file | 数据未完整保存，请重试；不要继续使用半成品 | 补偿/清理孤儿文件，记录资产状态 | ACT-S2-001/002 | 未覆盖 |
| ERR-BACKUP-001 | 备份目录/zip 冲突、校验或恢复失败 | backup/data | 备份或恢复未完成，请选择其他位置或恢复点 | 保留原数据；停止覆盖；人工诊断 | 待分解 | 未覆盖 |
| ERR-SECURITY-001 | DOM/日志出现 UUID、路径、密钥、错误栈或越权路径 | governance/security | 操作未完成，请联系维护者；不显示内部细节 | 立即停止并保留脱敏证据 | 全局安全不变量 | 已登记 |
| ERR-EVIDENCE-001 | 只有 renderer/CDP/handler/seed 证据却声称 UAT/发布通过 | governance | 证据不足，不能将该路径标记为通过 | 降级为自动化/部分证据并补真机 UAT | 全部 UAT | 已登记 |

## 3. 统一错误码与日志边界

当前正式错误码来自 docs/06：`NOT_FOUND`、`INVALID_JSON`、`INTERNAL_ERROR`、`MODEL_NOT_CONFIGURED` 及特殊隐私错误；本目录的 `ERR-*` 是治理层分类 ID，不新增 API 错误码。生产日志只允许脱敏 allowlist 字段；不记录请求正文、模型完整输出、base URL、密钥、完整 UUID、绝对路径或错误栈。

## 4. 证据状态

- `已证实`：有对应测试或非注入可见 UI 证据。
- `部分证据`：存在接线/自动化/局部路径，但不满足完整闭环。
- `未覆盖`：当前没有足够证据。
- `阻塞`：依赖、范围或数据责任未解决；不得由绿灯替代。

## 5. 下游消费

T-M5-005 扩充 S6/S7/TTS/备份/设置错误与恢复；T-M5-006 扩充运行依赖和离线错误；T-M5-007/008 将 `ERR-EVIDENCE-001` 作为 UAT/发布证据门禁。
