# S6 家长观察报告（ParentReport）

> 状态以 [capabilities.json](../capabilities.json) 中 `id=s6-parent-report` 为准。

原始意图参考 [S6 ParentReport PRD](../archive/legacy-product-references/ai-studybuddy/subsystems/06-S6-家长观察子系统PRD-ParentReport.md)。

## 1. 目标

学习数据属于学生本人，留在本机。家长需要知道孩子是否保持正常节奏、考试是否临近，但不应通过远程登录或查看原文来"查岗"。S6 由学生在本机生成脱敏聚合报告，导出或（受控地）外发给家长。报告只读 S1/S3/S4/S5/S7 的计数事实，不产生学习事实，也不改变 Today。

## 2. 用户流程

1. 学生在 `reports.html` 选择报告类型（daily / weekly / monthly / exam_alert）和时间段，可用"今天 / 本周 / 本月"快捷填写。
2. 生成报告快照；同一时段、同一数据指纹重复生成会返回已有快照。
3. 预览报告，导出 JSON 或 Markdown，自行转交家长。
4. 在 `classroom.html` 查看报告及其外发尝试记录。
5. 维护者在设置中配置并显式授权外发后，才可能通过 API 发起外发（默认关闭）。
6. `parent.html` 为家长入口页：引导安排学习、跳转 `reports.html` 查看报告。

## 3. 数据对象

| 表 | 关键字段 | 状态 |
|---|---|---|
| `report_snapshots` | report_kind `daily / weekly / monthly / exam_alert`, timezone, period_start, period_end, content_version, aggregation_fingerprint, safe_payload_json, markdown_content, error_code | `draft / ready / failed / archived` |
| `report_delivery_attempts` | report_id, channel `smtp / feishu`, mode `off / dry_run / live`, target_label, content_fingerprint, idempotency_key_fingerprint, error_code, retry_of | `blocked / dry_run / succeeded / failed` |

`safe_payload` 只有固定分区和固定字段，全部为计数、布尔或分档：

- `period`：类型、起止日期、时区、生成时间
- `plan`：活跃目标/计划数，计划项完成/开始/跳过数，计划分钟数
- `rhythm`：已分配天数与分钟、未分配项数、超载天数
- `practice`：练习/冲刺会话数、作答数、客观题正误数、待复核数、完成会话数
- `feedback`：错题 open / in_review / fixed / reopened / archived 数，薄弱点数
- `source_quality`：来源有效/失效计数、不确定转写片段数
- `exam_alert`：最近冲刺目标剩余天数分档 `0-3 / 4-7 / 8-14 / 15+`、是否 7 天内
- `quality_flags`：是否有待复核、来源警告、不确定采集

外发记录只存内容指纹，不存报告正文。

## 4. 页面与 API

页面：`reports.html`、`classroom.html`（报告与外发记录）、`parent.html`。

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/study/reports` | 生成快照（report_kind、timezone、period_start、period_end；支持 Idempotency-Key） |
| GET | `/api/study/reports` | 列表（分页、include_archived） |
| GET | `/api/study/reports/{report_id}` | 详情 |
| GET | `/api/study/reports/{report_id}/preview` | 预览（同详情） |
| GET | `/api/study/reports/{report_id}/export` | 导出 `format=json / markdown` |
| POST | `/api/study/reports/{report_id}/delivery` | 外发（channel、target_label、mode、authorization_granted） |
| GET | `/api/study/reports/{report_id}/delivery-attempts` | 外发审计记录 |

## 5. 规则与 AI 边界

- 报告完全由规则聚合，不用 LLM 写摘要。
- 隐私硬规则：家长永远看不到资料原文、笔记、题目答案、学生作答、错题正文、错因和问答聊天内容；也不看计划项、模块或冲刺目标的标题。
- 写入和读取都校验 `safe_payload` 的分区与字段白名单，多一个字段或类型不符即报 `report_redaction_violation`。
- 外发默认关闭（`report_delivery_mode=off`），决策链每一步都记一条审计：off → `delivery_disabled`；目标不在白名单 → `delivery_target_not_allowed`；live 未启用/未授权 → `delivery_authorization_required`；live 当前一律 → `delivery_live_not_approved`；只有 dry_run 会执行适配器。
- 外发不隐式重试、不后台执行；SMTP 仅白名单主机，飞书仅白名单 Webhook；错误只返回稳定错误码。
- 家长不登录系统操作学生数据；报告是学生主动生成并转交的。

## 6. 验收标准

- 选择"本周"生成报告后，预览只显示计数和分档，不出现任何资料名、题干、答案或聊天文字。
- 同一时段、数据未变时重复生成，返回同一份快照。
- 导出的 JSON 与 Markdown 与预览一致。
- 默认配置下发起外发，记录一条 `blocked / delivery_disabled`，没有任何网络请求。
- 起止日期非法或起始不早于结束时，提示时段无效。
- Today 不显示报告项；报告内容随 Today 背后的计划、练习、错题数据变化。

## 7. 状态来源

本页不维护当前缺口或验证结论；以 [`capabilities.json`](../capabilities.json) 的 `id=s6-parent-report` 为准。第一版产品目标和边界见文首链接的 S6 PRD。
