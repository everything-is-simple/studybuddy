# S3 限时练习（PracticeRunner）

> 状态以 [capabilities.json](../capabilities.json) 中 id=S3 为准；本文不写测试通过数。

原始意图参考 [S3 PracticeRunner PRD](../archive/legacy-product-references/ai-studybuddy/subsystems/03-S3-限时练习子系统PRD-PracticeRunner.md)。

## 1. 目标

整理完知识模块后，最自然的下一步是"做题验证掌握了没有"。S3 从已确认的知识模块生成或录入题目，学生在限时会话中作答，客观题由规则即时批改。会话中的错误自动成为 S4 错题，作答结果更新模块掌握度，并让 Today 能给出"继续练习 / 建议学习"的下一步。

## 2. 用户流程

1. 从 Today 的"按模块练习"或直接进入 `exercises.html`，选择练习集和已确认的知识模块（或材料 ID）。
2. AI 生成题目草稿，或手工录入题目；逐题确认（ready）或拒绝。
3. 在 `practice.html` 查看推荐题目，勾选后创建练习会话（设定时长）。
4. 进入 `practice-session.html`，开始会话并逐题提交；超时后会话自动过期，不能再提交。
5. 结束后在 `practice-result.html` 查看得分摘要；简答题等待人工复核（正确 / 错误 / 不确定）。
6. 错题进入 `review.html`（S4）。

## 3. 数据对象

| 表 | 关键字段 | 状态 |
|---|---|---|
| `exercise_sets` | title | `active / archived` |
| `exercises` | exercise_type `multiple_choice / true_false / short_answer`, prompt, explanation, exercise_kind `ai_generated / user_created`, edited_by_user | `draft → ready / rejected`，另有 `stale / archived` |
| `exercise_citations` | exercise_id, citation_key, quote | `valid / source_deleted / source_unavailable / stale / invalid` |
| `s2_module_exercises` | module_id, exercise_id | 题目归属知识模块 |
| `practice_sessions` | session_kind `practice / cram`, cram_goal_id, duration_seconds, deadline_at, timezone, local_date | `draft → active → finished / expired`，`archived` |
| `practice_session_items` | 题目快照（prompt、options、answer_key、来源与 citation_status） | 会话内只读 |
| `exercise_attempts` | answer_json, score, is_correct, grading_status, session_id, session_item_id, submission_key | grading `deterministic / pending_review / needs_review / reviewed` |
| `exercise_attempt_reviews` | attempt_id, decision `correct / incorrect / uncertain` | 每次作答最多一条 |

单个会话最多 50 题。

## 4. 页面与 API

页面：`exercises.html`、`practice.html`、`practice-session.html`、`practice-result.html`。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET/POST | `/api/study/exercise-sets`，GET `.../{set_id}` | 练习集 |
| POST | `/api/study/exercise-sets/{set_id}/exercises` | 手工录题 |
| POST | `/api/study/exercise-sets/{set_id}/generate` | AI 生成题目草稿（按模块或材料） |
| GET | `/api/study/exercises`、`/api/study/exercises/{exercise_id}` | 题目列表 / 详情 |
| PATCH | `/api/study/exercises/{exercise_id}` | 修改题目 |
| POST | `/api/study/exercises/{exercise_id}/confirm` `reject` `archive` | 题目状态 |
| GET/POST | `/api/study/exercises/{exercise_id}/attempts` | 直接作答（非会话） |
| GET | `/api/study/practice-recommendations` | 推荐题目（limit、weak_point） |
| GET/POST | `/api/study/practice-sessions` | 会话列表 / 创建 |
| GET | `/api/study/practice-sessions/{session_id}` | 会话详情 |
| POST | `/api/study/practice-sessions/{session_id}/start` `finish` `archive` | 会话状态 |
| POST | `/api/study/practice-sessions/{session_id}/items/{item_id}/submit` | 会话内提交（支持 submission_key 幂等） |
| GET | `/api/study/practice-sessions/{session_id}/result` | 结果摘要 |
| POST | `/api/study/attempts/{attempt_id}/review` | 简答题人工复核 |

## 5. 规则与 AI 边界

- 规则批改：单选、判断按答案键即时判分（`deterministic`）；简答题不自动判分，进入 `pending_review`。
- 限时由服务器时间判定：到 `deadline_at` 后会话转为 `expired`，提交被拒绝。
- AI 只生成题目草稿，必须带有效引用；学生确认后才为 `ready` 可进入会话。来源失效的题目不进入推荐和会话。
- 会话内答错自动生成错题（`deterministic_incorrect`）；人工复核为 incorrect 也生成错题（`review_incorrect`）。AI 不判定"掌握"，掌握度由作答记录按规则计算。
- 家长只看到会话数、作答数、正误计数，不看题干、答案或学生作答。

## 6. 验收标准

- 从已确认模块生成的题目先显示为草稿；确认后才能被选入会话。
- 会话开始后显示倒计时；超时后不能再提交，结果页仍可查看。
- 客观题提交后立即显示对错；简答题显示"待复核"，复核后更新结果。
- 会话内答错的题出现在 `review.html` 错题清单，Today 出现"错题复习"计数。
- 有未完成会话时，Today 的下一步可显示"继续练习：<会话名>"；模块掌握度低于 50% 时显示"建议学习 / 继续练习：<模块名>"。

## 7. 状态来源

本页不维护当前缺口或验证结论；以 [`capabilities.json`](../capabilities.json) 的 `id=S3` 为准。第一版产品目标和边界见文首链接的 S3 PRD。
