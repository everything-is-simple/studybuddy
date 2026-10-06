# S1 学习节奏 / Today

> 状态以 [capabilities.json](../capabilities.json) 中 id=S1 为准；本文不写测试通过数。

产品初衷见 [01-PRD](../01-PRD.md)，原始意图参考 [S1 StudyRhythm PRD](../archive/legacy-product-references/ai-studybuddy/subsystems/03-S1学习节奏子系统PRD-StudyRhythm.md)。

## 1. 目标

学生打开 Today 就知道今天该做什么：目标 → 计划 → 节奏分配，最终投影成最多 5 件可点击、有来源的待闭合事项。Today 是主闭环的回流点，下游（资料、练习、错题、冲刺）产生的事实都要在这里变成"下一步"；读不到，"看得见下一步"就断了。S1 只读事实、不自己产生学习事实，也不做复杂 GTD。

## 2. 用户流程

1. 在 `plans.html` 创建学习目标（goal）和计划（plan），添加计划项，确认并激活计划。
2. 在 `plan-detail.html` 设置节奏（cadence daily/weekly、时区、起始日、每日目标分钟），给计划项分配日期和分钟数（allocation）。
3. 打开 `today.html`，看到"今日待闭合项"：到期安排、明日准备、待核对、错题复习、下一步。
4. 对到期项点"开始学习 / 记录完成"，页面写入进度事件后自动刷新列表；其他项点击跳到对应页面（`plan-detail.html`、`material-detail.html`、`review.html`、`exercises.html`、`practice-session.html`、`practice.html#cram-goals`）。
5. 同页查看计划节奏摘要和周趋势。

## 3. 数据对象

| 表 | 关键字段 | 状态 |
|---|---|---|
| `learning_goals` | title, description | `active / archived` |
| `study_plans` | goal_id, title, user_edited | `draft → confirmed → active ⇄ paused → completed / archived` |
| `study_plan_items` | plan_id, module_id, deck_id, exercise_set_id, position | `pending / in_progress / completed / skipped / archived` |
| `study_plan_dependencies` | predecessor_item_id, successor_item_id | 前置未完成时后继项显示"需先完成前置学习项" |
| `study_progress_events` | item_id, event_type, metadata_json | `started / completed / skipped / reopened` |
| `rhythm_settings` | plan_id, cadence, timezone, period_start, target_minutes | `daily / weekly` |
| `rhythm_allocations` | plan_id, item_id, local_date, planned_minutes | 无状态，按日期投影 |

Today 投影（`backend/app/repositories/today.py`）不落库，按优先级排序后截取前 5 项：

| category | 优先级 | 来源 |
|---|---|---|
| `due_task` | 0 | 活跃计划中 `local_date ≤ 今天` 且未完成的 allocation（逾期单独标注） |
| `tomorrow_prep` | 0 | 明天的 allocation；`cram_goals` 中 active 且 `target_date` 恰为明天 |
| `quality_check` | 1 | 材料最新抽取为 `failed / rejected / empty`；S2 有 `lifecycle=draft` 的 AI 知识模块 |
| `mistake_review` | 1 | `mistake_cases` 中 `open / in_review / reopened` 的计数（合并为 1 项） |
| `next_step` | 2 | 仅当候选 < 3 时补充：首个已确认、来源有效、掌握度 < 0.5 的知识模块；否则最近未完成的练习会话 |

响应还包含 `remaining_count`、`remaining_p0_count` 和固定的 `unavailable_sources: [course_timetable, confirmed_exam_dates]`。

## 4. 页面与 API

页面：`today.html`、`plans.html`、`plan-detail.html`。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/today/pending-items` | Today 投影；可选 `date`、`timezone` |
| GET/POST | `/api/study/goals` | 目标列表 / 创建 |
| GET/PATCH | `/api/study/goals/{goal_id}` | 目标详情 / 修改 |
| POST | `/api/study/goals/{goal_id}/archive` | 归档目标 |
| GET/POST | `/api/study/plans` | 计划列表 / 创建 |
| GET/PATCH | `/api/study/plans/{plan_id}` | 计划详情 / 修改 |
| POST | `/api/study/plans/{plan_id}/confirm` `activate` `pause` `complete` `archive` | 计划状态迁移 |
| POST | `/api/study/plans/{plan_id}/items` | 添加计划项 |
| PATCH | `/api/study/plans/{plan_id}/items/{item_id}` | 修改计划项 |
| POST | `/api/study/plans/{plan_id}/items/{item_id}/archive` | 归档计划项 |
| POST/DELETE | `/api/study/plans/{plan_id}/dependencies[/{dependency_id}]` | 前置依赖 |
| GET | `/api/study/plans/{plan_id}/progress` | 进度事件 |
| POST | `/api/study/plans/{plan_id}/items/{item_id}/progress` | 记录 started/completed 等 |
| GET/PUT | `/api/study/plans/{plan_id}/rhythm` | 节奏设置 |
| GET/POST | `/api/study/plans/{plan_id}/rhythm/allocations` | 日程分配 |
| PATCH/DELETE | `/api/study/plans/{plan_id}/rhythm/allocations/{allocation_id}` | 修改 / 删除分配 |
| GET | `/api/study/plans/{plan_id}/rhythm/summary` `weekly-trend` `export` | 摘要、周趋势、导出 |

## 5. 规则与 AI 边界

- Today 完全规则驱动：日期、优先级、排序、截断（≤5）、逾期判定都不用 LLM。
- Today 只读：不创建任务、不改状态；状态只在学生点击动作后通过进度 API 改变。
- 日期按 `rhythm_settings.timezone` 计算本地日；无活跃计划时默认 `Asia/Shanghai`。
- 冲刺目标在明天时显示"这是已设置的目标，不代表考试日期"，不把备考目标当考试日期。
- 计划状态迁移、节奏与分配都由学生显式操作；AI 不排程、不确认。
- 家长只能通过 S6 看到计划和节奏的计数，不看计划项标题。

## 6. 验收标准

- 有活跃计划且今天有分配时，Today 显示"今天安排：<标题>"；昨天未完成的显示"逾期未闭合"。
- 点"开始学习"后该项变为"记录完成"；再点后该项从 Today 消失。
- 有前置未完成的计划项显示"需先完成前置学习项"，按钮为"查看计划详情"。
- 明天有分配或冲刺目标日为明天时，出现"明日准备"项。
- 材料解析失败、AI 知识草稿待确认、存在未闭合错题时，分别出现对应项且链接到正确页面。
- 任何时刻最多 5 项；超出时页面提示剩余数量。
- 待办少于 3 项时补一个"建议学习 / 继续练习"下一步。

## 7. 已知缺口

- 没有课程表和考试日期实体，Today 返回 `unavailable_sources`。
- 只读 `rhythm_allocations`；有计划但未排日程时 Today 为空。
- 薄弱点（S4）不直接进入 Today，只以错题计数出现。
- 冲刺目标只在目标日为明天时提示（见 S5）。
