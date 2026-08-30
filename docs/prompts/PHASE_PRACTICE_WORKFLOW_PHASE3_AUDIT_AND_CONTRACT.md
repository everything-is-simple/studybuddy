# Practice 第三阶段：现状审计与正式契约

> 状态：`contract-frozen / 2026-08-30`
> 范围：需求审计与契约冻结完成；本阶段不实现代码、不修改 schema/API/migration。

## 1. 结论摘要

Practice 第二阶段已经完成既有 S3/S4/S5 API 的静态前端工作区。第三阶段审计确认，后续能力必须建立在现有 append-only attempt、review、mistake、feedback 和 source lifecycle 事实之上，不得另建第二套评分或学习历史。

本契约冻结三个候选方向：

1. **自适应出题**：推荐列表优先，用户显式确认后创建既有 Practice Session；不自动开始、不自动写计划。
2. **间隔重复**：显式复习计划优先，使用确定性的 due date/interval 规则；不引入后台 scheduler/worker，不自动修改 9A plan、9B rhythm 或 progress。
3. **人工简答复核**：继续使用既有 `pending_review` → `correct|incorrect|uncertain` 语义；复核是追加事实，不能把用户答案或 grading payload 暴露给普通页面。

本文件冻结的是下一阶段的需求和接口边界，不代表上述三个方向已经实现。

## 2. 现状实体与字段审计

### 2.1 已有实体

| 实体 | 当前正式来源 | 事实/投影 | 第三阶段使用规则 |
|---|---|---|---|
| `exercise_sets` / `exercises` | Phase 8 repository/API | exercise 定义 | 只选择同 project、`ready`、支持题型的 exercise |
| `practice_sessions` | `repositories/practice.py` → legacy implementation；`study_practice.py` | session 容器 | 复用既有 practice/cram session；不复制评分表 |
| `practice_session_items` | 同上 | 不可变题目快照 | 推荐结果确认后仍通过正式 session 创建流程生成 |
| `exercise_attempts` | Phase 8/9C repository | append-only 作答事实 | 自适应和间隔重复只读消费；不 UPDATE/删除旧 attempt |
| `exercise_attempt_reviews` | Phase 9C repository/API | append-only 人工复核事实 | short-answer 仅允许显式 review；decision 使用既有枚举 |
| `mistake_cases` / `mistake_occurrences` | Phase 9C repository/API | 错题聚合与 occurrence 事实 | 作为错误信号，不把 AI/推荐直接写成 confirmed fact |
| `mistake_feedback_events` | Phase 9C repository/API | append-only 反馈 | 反馈追加，不覆盖历史；归档后拒绝继续写入 |
| weak-point summary | `list_weak_points()` | 只读派生投影 | 第三阶段可读取，不作为独立事实源 |
| source revision/citation status | 既有 AI/study lifecycle | 服务端派生状态 | 只接受 `valid`；`stale/source_deleted/source_unavailable` 必须降级 |
| 9A plan/progress 与 9B rhythm | 既有正式 API | 独立领域事实 | 第三阶段只读或显式引用，不自动写入 |

### 2.2 已确认的隐私字段

以下字段可能存在于数据库内部或服务端内部，但不得进入普通 API 响应、DOM、URL、storage、日志或 artifact：

- `answer_key_json`；
- submitted answer / `answer_json`；
- 内部 grading payload；
- raw provider response/prompt；
- stored path、绝对路径、SQL、traceback、secret；
- 未批准的完整 source text。

### 2.3 当前 API inventory

Practice 现有正式 API：

```text
GET  /api/study/practice-sessions
POST /api/study/practice-sessions
GET  /api/study/practice-sessions/{session_id}
POST /api/study/practice-sessions/{session_id}/start
POST /api/study/practice-sessions/{session_id}/items/{item_id}/submit
POST /api/study/practice-sessions/{session_id}/finish
POST /api/study/practice-sessions/{session_id}/archive
GET  /api/study/practice-sessions/{session_id}/result
GET  /api/study/mistakes
GET  /api/study/mistakes/{mistake_id}
POST /api/study/attempts/{attempt_id}/review
POST /api/study/attempts/{attempt_id}/mark-mistake
GET  /api/study/weak-points
POST /api/study/mistakes/{mistake_id}/feedback
POST /api/study/mistakes/{mistake_id}/redo
POST /api/study/mistakes/{mistake_id}/archive
```

第三阶段默认不改变以上 URL、method、状态码、错误码或响应隐私边界。若推荐或复习计划需要新公共 API，必须在本契约之后另立 API contract，并通过 migration/rollback 评审后实现。

## 3. 状态与事实规则

### 3.1 Practice session

```text
draft → active → finished
                  └→ expired
 draft/finished/expired → archived
```

- `start`、`submit`、`finish` 均由服务端状态和 deadline 判定；浏览器时间不是事实；
- session item 是题面/选项/来源身份快照；不允许前端注入题面或 answer key；
- submit 对同一 session item 只接受第一次有效提交；重做创建新 session/attempt；
- deterministic MC/TF 才能产生 score/is_correct；short-answer 保持 `pending_review`；
- source 失效只改变公开状态，不伪造可用引用或恢复正文。

### 3.2 Attempt review

```text
pending_review → correct
               → incorrect → mistake occurrence
               → uncertain
```

- 只允许对 `pending_review` attempt review；
- `correct`/`uncertain` 不形成确定性 mistake；`incorrect` 形成 occurrence；
- 已 review attempt 再次 review 返回稳定 conflict；不更新旧 review；
- review feedback 是审计可见的安全文本，不返回用户原始答案。

### 3.3 Mistake lifecycle

```text
open → in_review → fixed → reopened
  └──────────────────────→ archived
```

实际可用状态以当前 repository/API 为准；页面统一通过 `sbState.label()`，不得把内部状态码作为唯一文案。

## 4. 第三阶段功能契约

### 4.1 自适应出题

**默认产品选择：recommendation-first。**

输入信号仅允许：

- deterministic incorrect attempt；
- 已完成的人工 review decision；
- mistake occurrence/feedback 的安全元数据；
- weak-point 派生摘要；
- exercise readiness、source status、最近练习时间等服务端事实。

冻结规则：

1. 推荐必须可解释，至少返回安全的 reason label 和来源/题目状态；
2. 候选池只来自同 project 的 `ready` exercise 和可验证 current source；
3. 固定候选池、过滤顺序和 tie-breaker 后再实现；默认 tie-breaker 为：优先未归档且 source valid，其次错误 occurrence 数降序，再按最近错误时间降序，最后按稳定 exercise ID 升序；
4. 推荐结果是暂态建议，不是 confirmed learning fact；
5. 用户确认后调用既有 session 创建语义；不自动 start、不自动 finish、不直接写 progress；
6. Provider 不得绕过服务端候选过滤或自行决定不可审计的题目；
7. 无候选、来源失效、数据不足时返回安全 empty/blocked 状态，不伪造推荐成功。

本阶段不实现推荐 endpoint 或算法。推荐 API 的独立契约已冻结于 `docs/prompts/PHASE_PRACTICE_RECOMMENDATION_API_CONTRACT.md`。

### 4.2 间隔重复

**默认产品选择：显式复习计划，不自动调度。**

冻结的核心概念：

- review event：一次 deterministic attempt 或人工 review 的服务端事实；
- due local date/time：按用户指定 IANA timezone 计算的复习到期时间；
- interval：整数天数，服务端计算；
- schedule version：规则变更时用于解释历史结果；
- source validity：题目 source 失效时进入需要人工确认/不可复习状态，不自动替换题目。

初始规则只冻结接口语义，不冻结具体算法参数：

- correct/good 信号延长 interval；
- incorrect 或 unresolved/pending_review 不得标记为掌握，并进入人工/再次复习队列；
- 同一事件只能产生一次 schedule projection；
- 时区和 local date 由服务端确定；客户端不提交 due_at 作为事实；
- 归档 exercise、失效 source 和 archived mistake 不自动重新激活。

禁止：后台 timer、scheduler、worker、提醒、推送、日历同步、自动修改 plan/rhythm/progress。

### 4.3 人工简答复核

继续复用既有 API：

```text
POST /api/study/attempts/{attempt_id}/review
```

请求仍为：

```json
{"decision":"correct|incorrect|uncertain","feedback":"safe text"}
```

冻结规则：

- short-answer attempt 只能从 `pending_review` 进入一次 review；
- `feedback` 有服务端长度和字符边界；
- `incorrect` 才进入 mistake projection；
- 未复核答案不参与“已掌握”统计；
- reviewer 仍为 local user，不扩展多用户角色；
- 复核失败必须 rollback，不留下半条 review 或 mistake 事实。

## 5. Source lifecycle、幂等与失败契约

- recommendation/schedule 只消费 current/active/ready source；
- delete/restore/purge/re-index 保留历史 attempt/review/mistake/feedback，不删除事实；
- source unavailable/stale/source_deleted 只显示安全降级，不恢复名称、正文或路径；
- 所有未来写操作必须显式 Idempotency-Key，重复请求只能 replay 同一安全结果；
- 失败后必须可重试，不能产生重复 attempt、review、schedule event 或 feedback；
- 页面切换、reload、redo 和列表刷新必须丢弃 stale response；
- backup/restore 只恢复事实和版本，不触发推荐、排程、重评分、Provider、OCR/ASR 或自动 repair。

## 6. API/schema 变更结论

本次审计和契约冻结：

- 不新增 endpoint；
- 不新增错误码；
- 不新增 migration/schema；
- 不改变现有 Practice API response shape；
- 不改变单进程、单实例、local SQLite/local-disk 边界；
- 不实现算法、scheduler、worker 或自动调度。

如果后续正式实现 recommendation 或 schedule 需要持久化 projection/event，必须另行提出连续 migration、rollback、backup/restore 和 API contract；不得在运行时建表或复用不匹配的现有字段。

## 7. 下一阶段实现顺序

1. 先实现人工简答复核页面的完整 UX/evidence（若仍有缺口）；
2. 单独冻结 recommendation API 与 deterministic candidate/ranking contract；
3. 实现 recommendation read-only backend，再接 UI；
4. 单独冻结 schedule event/projection schema 和时区规则；
5. 通过 migration/rollback/backup contract 后实现显式复习计划；
6. 最后再评估是否需要任何自动化调度；默认不做。

每一步都必须有 focused backend/browser、privacy、source lifecycle、backup/restore（适用时）和完整回归证据。

## 8. 审计验收

- [x] 现状实体、字段、API、状态和隐私边界已追溯到正式源码/测试；
- [x] 自适应出题的输入、候选池、排序、输出、失败和确认边界已冻结；
- [x] 间隔重复的事件、时区、due 语义和自动化 non-goals 已冻结；
- [x] 人工简答复核的状态、决策、反馈、错题投影和隐私边界已冻结；
- [x] 明确 recommendation-first、显式复习计划和 local-user review 默认选择；
- [x] 明确本次不新增 schema、migration、endpoint、错误码或算法实现；
- [x] 明确 source lifecycle、幂等、失败/retry、stale 和 backup/restore non-repair 规则；
- [x] 明确下一步实现顺序和 stop conditions。
