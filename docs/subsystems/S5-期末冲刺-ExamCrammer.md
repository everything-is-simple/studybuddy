# S5 期末冲刺（ExamCrammer）

> 状态以 [capabilities.json](../capabilities.json) 中 id=S5 为准；本文不写测试通过数。

原始意图参考 [S5 ExamCrammer PRD](../archive/legacy-product-references/ai-studybuddy/subsystems/08-S5-期末冲刺子系统PRD-ExamCrammer.md)。

## 1. 目标

临近考试时，学生需要围绕一个明确目标集中补弱，而不是继续零散地做单模块练习。S5 让学生设置冲刺目标（目标日期 + 目标题数），从已确认且来源有效的题目组建限时冲刺会话，复用 S3 的批改和 S4 的错题回流。冲刺目标临近时 Today 给出"明日备考目标"提醒，让考前也看得见下一步。

## 2. 用户流程

1. 在 `practice.html#cram-goals` 填写冲刺目标名称、目标日期、目标题数，创建为草稿。
2. 激活目标（目标日期已过的不能激活）。
3. 在目标详情中勾选已确认、来源有效的题目（不超过目标题数，单次最多 50 题），创建冲刺练习。
4. 跳转到 `practice-session.html` 限时作答；答错的题进入 S4 错题。
5. 在 `practice-result.html` 查看冲刺结果：得分摘要、本次错题数、涉及题目的薄弱点。
6. 至少有一次已结束的冲刺会话后，可以"完成目标"；不再需要时归档。
7. 目标日期为明天时，Today 出现"明日备考目标：<名称>"。

## 3. 数据对象

| 表 | 关键字段 | 状态 |
|---|---|---|
| `cram_goals` | title, target_date, timezone, target_exercise_count(1–200), plan_id, plan_item_id | `draft → active → completed`；`draft / active / completed → archived` |
| `practice_sessions` | session_kind=`cram`, cram_goal_id | 同 S3：`draft → active → finished / expired`，`archived` |
| 冲刺结果（派生） | goal 摘要、session 结果、mistake_count、weak_points | 不落库 |

`completed` 前置条件：该目标下至少一个会话为 `finished` 或 `expired`。`plan_id / plan_item_id` 仅做范围校验，不回写进度。

## 4. 页面与 API

页面：`practice.html#cram-goals`（`js/cram.js`）、`practice-session.html`、`practice-result.html`。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET/POST | `/api/study/cram-goals` | 目标列表 / 创建（draft） |
| GET | `/api/study/cram-goals/{goal_id}` | 目标详情 |
| POST | `/api/study/cram-goals/{goal_id}/active` | 激活 |
| POST | `/api/study/cram-goals/{goal_id}/completed` | 完成（需已有结束的冲刺会话） |
| POST | `/api/study/cram-goals/{goal_id}/archived` | 归档 |
| POST | `/api/study/cram-goals/{goal_id}/sessions` | 用所选题目创建冲刺会话 |
| GET | `/api/study/cram-goals/{goal_id}/sessions/{session_id}/result` | 冲刺结果 |

作答、结束等会话操作复用 S3 的 `/api/study/practice-sessions/...` 接口。

## 5. 规则与 AI 边界

- 全部规则驱动：状态迁移、题数上限、日期校验、批改、错题入库都不用 LLM。
- 冲刺目标日期是学生设置的目标，不等于考试日期；Today 文案明确区分。
- 选题由学生手工勾选；系统只过滤出 `ready` 且引用全部有效的题目。
- AI 不生成冲刺建议、不自动标记"已掌握"或"已完成"。
- 家长报告只读冲刺会话数和最近冲刺目标的剩余天数分档（`0-3 / 4-7 / 8-14 / 15+`），不看题目和目标名称。

## 6. 验收标准

- 创建目标后列表显示目标日期和题数；激活后才出现选题表单。
- 目标日期已过时显示"已过目标日期"，不能激活或创建新冲刺练习，只能归档。
- 选题超过目标题数或 50 题时提示并拒绝。
- 冲刺会话中答错的题出现在 `review.html`，Today 错题计数增加。
- 结果页显示本次错题数和相关薄弱点。
- 目标日期为明天且目标为 active 时，Today 显示"明日备考目标"并链接到 `practice.html#cram-goals`。

## 7. 已知缺口

- 冲刺不按薄弱点选题，需手工勾选。
- Today 只在目标日为明天时提示，更早的倒计时不出现。
- 冲刺结果不回写计划进度。
- 没有考试日期实体，冲刺目标无法关联真实考试。
