# S4 错题改错（ErrorFixer）

> 状态以 [capabilities.json](../capabilities.json) 中 id=S4 为准；本文不写测试通过数。

原始意图参考 [S4 ErrorFixer PRD](../archive/legacy-product-references/ai-studybuddy/subsystems/03-S4-错题改错子系统PRD-ErrorFixer.md)。

## 1. 目标

"看到做错了"不等于完成学习。S4 把练习中的错误沉淀为可追溯的错题，让学生知道错在哪道题、来源是什么、下一步重做什么，并在学生记录改正后关闭。一次错误不等于永久薄弱点；未闭合错题持续在 Today 显示"错题复习"，直到学生处理完。

## 2. 用户流程

1. 在 Today 点"开始复盘"，或直接进入 `review.html`，看到错题清单和薄弱点汇总。
2. 打开一道错题，查看题目快照、作答记录、来源材料与来源状态。
3. 对简答题作答做人工复核；对未自动入库的作答（如直接作答）点"标记错题"。
4. 写复盘笔记（user_note）或记录改正（user_correction）；记录改正后错题变为已改正。
5. 点"再次练习"生成只含该题的新会话，进入 `practice-session.html` 重做。
6. 不再需要的错题可归档。

## 3. 数据对象

| 表 | 关键字段 | 状态 |
|---|---|---|
| `mistake_cases` | exercise_id, exercise_revision_fingerprint, origin `deterministic / human_review / user_reported`, fixed_at | `open → in_review → fixed`，`fixed → reopened`（同题再错），任意 → `archived` |
| `mistake_occurrences` | mistake_case_id, attempt_id, reason_code `deterministic_incorrect / review_incorrect / user_marked`, source_revision, source_status | 每次错误一条 |
| `mistake_feedback_events` | event_kind `user_correction / user_note / status_transition`, content, provenance `user_created` | 只追加 |
| 薄弱点（派生） | 按 exercise_id + 修订指纹聚合：occurrence_count、open/fixed/reopened 计数、source_warning_count、last_occurrence_at | 不落库，排除 archived |

错题按"题目 + 题目修订指纹"去重：同一题再错追加 occurrence；若已 fixed 则转为 `reopened`；已归档的题不能再入库。

## 4. 页面与 API

页面：`review.html`；`practice.html` 的错题库区块；`practice-result.html` 的复核入口。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/study/mistakes` | 错题列表 |
| GET | `/api/study/mistakes/{mistake_id}` | 错题详情（含来源） |
| POST | `/api/study/mistakes/{mistake_id}/feedback` | 写复盘：`user_correction` / `user_note` / `status_transition` |
| POST | `/api/study/mistakes/{mistake_id}/redo` | 用该题创建新会话（沿用原会话类型、时长、时区） |
| POST | `/api/study/mistakes/{mistake_id}/archive` | 归档 |
| POST | `/api/study/attempts/{attempt_id}/review` | 简答题复核（incorrect 生成错题） |
| POST | `/api/study/attempts/{attempt_id}/mark-mistake` | 学生手动标记错题 |
| GET | `/api/study/weak-points` | 薄弱点汇总 |

## 5. 规则与 AI 边界

- 规则入库：会话内客观题答错、复核判定 incorrect、学生手动标记，三种来源都由规则写入，不从不确定答案推断。
- 状态迁移只由学生动作触发：`user_correction` → `fixed`；`status_transition` → `in_review`（仅从 open）；归档需显式点击。
- 薄弱点只是计数聚合，不由 AI 判定，不自动改变知识模块状态。
- AI 不自动确认错因、不替学生写反思、不判定"已掌握"。
- 来源失效时错题保留，标注 `source_status`，不删除历史。
- 家长只看到错题与薄弱点计数，不看题干、正确答案、学生答案、错题正文或错因。

## 6. 验收标准

- 会话中答错的客观题立即出现在 `review.html`；Today 的"错题复习"显示未闭合数（open / in_review / reopened）。
- 记录改正后该题显示已改正，Today 计数减一；全部改正或归档后 Today 不再显示错题项。
- 已改正的题再次答错后重新出现为 reopened。
- "再次练习"跳转到只含该题的新会话。
- 薄弱点汇总按题目显示出错次数和最近出错时间。

## 7. 已知缺口

- 重做答对不会关闭错题；只有记录 `user_correction` 才设为 fixed。
- 薄弱点不进入 Today，Today 只显示错题总数。
- 直接作答（非会话）答错不自动入库，需手动标记。
- 薄弱点按题目聚合，未按知识模块聚合。
