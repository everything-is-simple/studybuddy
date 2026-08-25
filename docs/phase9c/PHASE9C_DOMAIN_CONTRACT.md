# Phase 9C 正式领域契约与状态机

> 状态：`planned/contract-frozen`
>
> 本文是 Phase 9C-1 的 Gate B 契约产物。它冻结 S3 限时练习、S4 错题改错/反馈、S5 期末冲刺的最小正式语义，供 9C-2 migration、9C-3 repository/domain、后续 API/UI/restore tests 使用。
>
> 本文不是实现证据。当前正式 schema 仍为 v10；本文不新增表、不修改 migration、不实现业务代码。Phase 9C 完成声明仍必须等待 Gate A-J 全部通过，并限定在 deterministic fake-provider、单进程 SQLite、本地 Chromium 与 backup/restore 范围。

## 1. 契约基线与已验证复用能力

### 1.1 当前实现基线

本契约基于当前源码和测试，而不是历史版本的表面能力：

| 能力 | 当前事实证据 | 9C 复用规则 |
|---|---|---|
| schema/migration | `backend/app/migrations/runner.py:CURRENT_SCHEMA_VERSION`、`_MIGRATIONS`、`migrate()`；当前 v10 | 新增字段/表只能追加连续 v11 migration；不得改写 v10 或运行时建表 |
| exercises | `repository.py:_exercise_payload()`、`create_exercise()`、`confirm_exercise()`、`transition_exercise()`、`_exercise_public()` | 只消费当前已 `ready` 且同 project 的 exercise；题型仍仅 MC/TF/short_answer |
| attempts/grading | `repository.py:submit_exercise_attempt()`、`list_exercise_attempts()`；`backend/tests/test_phase8_exercises.py` | 原始 attempt 保持 append-only；MC/TF 保持 deterministic；short answer 初始为 `pending_review` |
| cards | `review_card()` 写入 `card_reviews`，结果为 again/hard/good/easy | 9C 最小范围**不把 cards 作为可作答题目**；card review 仅可作为 S5/S4 的可选复习信号，不能伪装成 scored attempt |
| AI generation | `create_generation_operation()`、`persist_generated_draft()`、`test_phase8_generation.py` | 9C 不要求新的 AI generation；若未来纳入，必须是独立 draft/suggestion、citation revalidation 和安全 operation |
| 9A plan/progress | `append_study_progress_event()`、`study_progress_summary()`、`test_phase9a_domain.py` | 9C 只能显式关联 plan/item/module；不写旧 progress，不自动改 plan/rhythm |
| 9B note/rhythm | `create_user_note()`、`generate_note_draft()`、`rhythm_summary()`、`test_phase9b_notes.py`、`test_phase9b_rhythm.py` | 9C 只读使用 note/module/rhythm 上下文；不改 note、module、allocation 或自动排程 |
| source lifecycle | `soft_delete_material()`、`restore_material()`、`purge_material()`、`_refresh_study_source_links_for_material()`；Phase 9A/9B lifecycle tests | 保留历史事实；只允许 source status 降级或显式 refresh 后重验，不伪造正文/名称/路径/citation |
| backup/restore | `backup.py:backup_data()/verify_backup()/restore_backup()`、`restore_acceptance.py:_study_checks()`、Phase 9B backup test | 9C-9 必须扩展专项检查；restore/read/verify 不重评分、不重建、不调用 provider |

### 1.2 领域事实与投影的原则

1. `materials → revisions → chunks → retrieval/context → citation` 仍是资料证据链，S3/S4/S5 不能成为正文 source of truth。
2. `exercise_attempts`、人工复核、错题 occurrence、用户 feedback 和 session completion 是历史事实；不能用 projection 覆盖它们。
3. `practice session` 的题目快照是 session 可复现性数据；它不能成为新的 exercise source of truth，也不能改变原 exercise。
4. `mistake case` 和 `weak point` 是从事实重算或带规则版本的派生结果；不能将 AI 建议直接写成 verified mistake fact。
5. S5 只组合 S3/S4 的事实和派生结果，不创建第二套评分/attempt 体系。
6. 公开响应、浏览器 DOM、导出和日志必须服从隐私 DTO；数据库内部保存的 answer key/submitted answer 不等于可以公开返回。

## 2. Phase 9C 范围与明确不做

### 2.1 纳入范围

#### S3 PracticeRunner

- 用户显式选择 ready exercises，创建一个有题目顺序快照的 practice session；
- 显式 start，服务端生成 UTC start/deadline；
- 在 deadline 前逐题提交，复用 Phase 8 deterministic grading；
- short answer 提交后进入 `pending_review`，不被伪造为自动正确/错误；
- 显式 finish 或服务端在读取/写入时发现 deadline 已过而进入 `expired`；
- 生成只读、可重算的结果 summary，保留所有 attempts；
- 支持刷新/重启后按持久化 session 状态恢复；不依赖后台 timer。

#### S4 ErrorFixer

- 由 MC/TF deterministic incorrect attempt 形成错题 occurrence；
- short answer 只有在显式人工 review 为 `incorrect` 后形成错误事实；`correct` 和 `uncertain` 不形成确定性错题；
- 用户可以显式创建/补充反馈和改错记录；
- redo 必须创建新的 attempt，并保留与原 mistake case 的关联；
- 人工 review 至少覆盖本地单用户 short-answer path，review decision/feedback 可审计；
- mistake case 与 weak-point summary 可读、可重算，支持 source/module warning。

#### S5 ExamCrammer

- 用户显式创建 cram goal，指定考试/截止 local date、timezone 和目标题量；
- 用户从同 project 的 ready exercises 中显式选择范围，创建题目快照的 cram session；
- cram session 复用 S3 practice session/attempt/grading 事实；
- 结果只读汇总 S3 facts 与 S4 mistake/weak-point projection；
- 可显式关联已有 9A plan/item，但不修改其 progress/rhythm；
- 提供确定性 summary/建议，AI feedback 不属于本阶段完成条件。

### 2.2 明确不做

- Cards 作为 timed scored question；card review 不转换成 exercise attempt；
- 新题型：cloze、ordering、matching、essay/open-ended deterministic grading；
- 真实 Provider generation、真实题库/试卷导入、考试平台同步；
- AI 自动判定 mistake、自动决定 short-answer review、自动确认 correction 或自动生成 confirmed plan；
- scheduler、worker、queue、cancel、后台 timer、定时过期扫描、提醒、push、calendar sync、自动重排；
- 多用户、认证授权、teacher/parent role、跨 project、云同步、协作；
- OCR、ASR、S6/S7、Phase 9D；
- 自动写 9A `study_progress_events`、创建/移动/删除 9B rhythm allocation；
- 删除、覆盖或静默修改 exercise、attempt、review、mistake occurrence、feedback、note、module、plan 或 confirmed artifact；
- rich text、附件、图片、音频、外部 vector database；
- 系统级 screen reader、极端长内容、长期运行稳定性、真实资源耗尽和全局 production `real-pass`。

## 3. 正式术语与实体关系

### 3.1 Glossary

| 术语 | 正式定义 | 类型 |
|---|---|---|
| Practice Session | 一组冻结题目顺序和时限的练习执行容器；`session_kind` 为 `practice` 或 `cram` | 用户状态/事实容器 |
| Session Item | session 内一个题目的不可变执行快照和 position | session snapshot |
| Attempt | 一次题目提交事实；每次重做/重试按规则产生新 attempt | append-only fact |
| Deterministic Grading | MC/TF 由服务器内部 answer key 计算的评分；不是客户端输入 | grading fact |
| Review | 对 pending short answer 的显式人工决定和反馈；不改写原 attempt | append-only fact |
| Mistake Case | 一个可追踪的错题聚合对象，关联 occurrences 和 feedback events | projection + user state |
| Mistake Occurrence | 某一次 attempt/review/user action 导致的错题事实记录 | append-only fact |
| Feedback Event | 用户、人工或未来 AI 对错题的追加反馈/改错记录 | append-only fact |
| Weak Point | 按冻结规则从 mistake facts 聚合出的只读弱点摘要 | derived projection |
| Cram Goal | 用户为某一考试/截止日建立的冲刺目标 | user state |
| Cram Session | `PracticeSession.session_kind='cram'` 的模拟练习；不另建评分事实 | session specialization |
| Source Status | `valid`、`source_deleted`、`source_unavailable`、`stale` | server-derived status |
| AI Suggestion | 非事实、非 confirmed 的 draft 建议；本 9C 不作为必要能力 | proposed artifact |

### 3.2 实体关系

```text
project
├── exercise_sets → exercises (Phase 8, existing)
│                     └── exercise_attempts (existing append-only facts)
│
├── practice_sessions (9C, session_kind=practice|cram)
│     └── practice_session_items (9C immutable selection/question snapshots)
│            └── exercise_attempts.session_id/session_item_id (9C linkage)
│
├── exercise_attempt_reviews (9C append-only human review facts)
├── mistake_cases (9C aggregate)
│     ├── mistake_occurrences (9C append-only)
│     └── mistake_feedback_events (9C append-only)
│
├── cram_goals (9C)
│     └── practice_sessions.session_kind=cram + cram_goal_id
│
└── weak-point summary (derived read; no independent fact source)

existing exercise/card/note/module/plan source links
        ↓
server-side source refresh and safe status/warning
```

冻结：

1. S3 和 S5 共用 `practice_sessions`/`practice_session_items`；S5 不复制 attempt/grading 表。
2. `exercise_attempts` 仍是题目作答事实源；9C 只增加 nullable session linkage 和提交幂等/sequence metadata，不能创建第二个 submitted-answer fact table。
3. `mistake_cases` 可以保存稳定聚合身份和当前 lifecycle，但 occurrence、review、feedback 历史必须独立保留。
4. weak-point 默认是只读 projection，不保存独立的 AI/人工“弱点事实”；如 9C-2 需要缓存，必须带 `projection_version`，并可完全删除重算。
5. `cram_goal` 可关联一个同 project 的 9A `plan_id`/`plan_item_id`，但该关系是引用，不是 progress ownership。
6. 所有新增实体带 `project_id`，服务端注入并验证；当前没有 `user_id`、认证或多用户 actor boundary。

## 4. S3 Practice Session 契约

### 4.1 Session 输入与字段

9C-2 应实现语义等价的结构；列名可以调整，但不能改变规则。

#### `practice_sessions`

| 字段 | 规则 |
|---|---|
| `id` | 稳定 `practice_session_...` ID |
| `project_id` | 服务端 scope；不得由客户端覆盖 |
| `session_kind` | 仅 `practice`、`cram` |
| `cram_goal_id` | `practice` 必须 NULL；`cram` 必须引用同 project active goal |
| `status` | `draft`、`active`、`finished`、`expired`、`archived` |
| `title` | trim 后 1–200 Unicode chars |
| `duration_seconds` | 整数 `60..7200`；服务端校验，不接受 client duration 后续覆盖 |
| `timezone` | 合法 IANA timezone name；仅用于 display/business date，不改变 UTC duration |
| `local_date` | 由用户/服务端在 timezone 下确定的严格 `YYYY-MM-DD`；不接受 datetime/offset |
| `started_at` | 服务端 UTC ISO-8601；draft 时 NULL |
| `deadline_at` | 服务端 UTC ISO-8601；active 时非 NULL |
| `finished_at` | 服务端 UTC ISO-8601；finished/expired 时非 NULL |
| `created_at/updated_at` | 服务端 UTC ISO-8601 |

规则：

1. session 创建时必须一次性冻结至少 1 个、最多 50 个 distinct ready exercises；空选择、跨 project、非 ready、archived 或重复 exercise 拒绝。
2. 创建产生 `draft`；显式 `start` 后才成为 `active`。draft 可以在未开始前 archive，但不能修改题目 selection、duration 或 timezone；需要修改时创建新 session。
3. `start` 是一次性转换：服务器在写事务内生成 `started_at=utc_now()`、`deadline_at=started_at+duration_seconds`。客户端不能传 `started_at`、`deadline_at`、elapsed、score 或 finished_at。
4. 本阶段不支持 pause/resume。active session 一旦 start，只有 `finish` 或 deadline 到达；不得通过 PATCH 延长/缩短。
5. deadline 是 UTC instant。没有后台 timer；每一个 session read、item read、submit、finish 都先执行保守的 `if now >= deadline_at → expired` transition。进程停止期间不会实时更新数据库状态，下一次显式读/写才回收。
6. 服务端以写事务中的 UTC wall-clock 判断 deadline；客户端显示倒计时只是 UX，不是事实。单进程范围内不宣称跨进程精确计时或真实断电恢复。
7. deadline 前到达应用但写事务在 deadline 后取得锁时，以事务内服务器当前时间为准，拒绝提交并保留 `expired`/unanswered 状态；不接受客户端“我提前提交”的证明。
8. `finish` 在 active 时将 session 置为 `finished`；若已到 deadline，置为 `expired`。finished/expired/archived 只读。

### 4.2 Session item snapshot

`practice_session_items` 至少保存：

- `id`、`session_id`、`project_id`、`exercise_id`、`position`；
- `exercise_type`、`prompt`、`options_json`、`explanation_snapshot`；
- `exercise_kind`、`source_revision`；
- safe citation identity/status metadata，不保存 source full text/path/display name；
- internal `answer_key_json` snapshot，仅供服务器 grading，永不进入 public DTO/DOM/export/log；
- `created_at`/`updated_at`。

快照规则：

1. start 前在一个 domain transaction 中重新验证 exercise 仍是 same project、`ready`、题型受支持，并复制题面/选项/内部 answer key/当前 source identity。
2. session item 是可复现的执行快照；之后 exercise 被 archive、source 变 stale/deleted/unavailable 不改写快照，不会 promotion citation，也不向用户伪造可用来源。
3. session item 的 prompt/options 可公开给 session owner；`answer_key_json`、source full text、stored_path 不可公开。
4. `position` 从 0 开始且同 session 唯一；提交按 session item，不允许直接把任意 exercise ID 注入另一 session。
5. 不提供 session item 内容编辑；用户要使用新题面必须创建新 session。

### 4.3 Session state machine

```text
absent → draft → active → finished
                  └──────→ expired
 draft/finished/expired → archived
```

| 当前状态 | 允许操作 | 禁止/不会发生 |
|---|---|---|
| draft | read、start、archive | edit selection/duration、submit、finish as completed |
| active before deadline | read、submit item、finish | pause、edit、client score/deadline、archive while active |
| active at/after deadline | read triggers expired、finish yields expired | submit accepted、renew/extend |
| finished | read、result、archive | submit、reopen、regrade、edit |
| expired | read、result、archive | submit、reopen、renew |
| archived | read limited/export if frozen | all mutation |

状态转换必须稳定：重复 start/finish/submit 在非法状态下返回 conflict，不创建额外 session/history。普通 read 可以进行 deadline transition；这属于冻结的时间状态维护，不是后台任务或业务 repair。

### 4.4 Submit 与 grading

1. `POST session/items/{item_id}/submit` 必须使用 session/project/item ownership 验证，并由服务器读取 session item 的 snapshot answer key。
2. MC：只接受合法 integer index；TF：只接受 JSON boolean；short answer：只接受非空 string，最大长度沿用 Phase 8 `MAX_EXERCISE_ANSWER_LENGTH`（当前 1000）。
3. MC/TF 写入新的 `exercise_attempts`，`grading_status='deterministic'`、`score` 为 1.0/0.0、`is_correct` 为 true/false。服务器计算值，不接受 request 中的 score/is_correct。
4. short answer 写入新的 `exercise_attempts`，`grading_status='pending_review'`，score/is_correct/reviewed_at 为 NULL；不得自动比较字符串并判定正确。
5. submit response 只返回安全的 attempt result：attempt ID、item/position、grading status、score/is_correct（MC/TF）、安全 feedback/status；不回显提交原文、answer key 或 internal snapshot。
6. 每次重做都是新的 attempt；不能 UPDATE 旧 attempt，也不能删除旧 attempt。S4 redo 必须继续使用同一规则。
7. `submission_key` 可选但推荐 API 要求由客户端生成；若存在，同一 `(session_id, session_item_id, submission_key)` 且 fingerprint 相同则 replay 同一安全结果，不重复插入；fingerprint 不同返回 idempotency conflict。无 key 的请求不是自动去重。
8. session 每个 item 默认最多一个 accepted submission；若契约需要重做，必须显式 `redo` action 或新 session，不允许同一 session item 无控制地重复提交。9C-1 冻结为：同一 session item 只接受第一次提交，后续只能读取原 attempt；redo 创建新 practice session。
9. 因此 session result 中每个 item 有 0/1 个 session attempt；历史 attempt 仍可有多个，但 session 不会把它们隐式混入。

### 4.5 S3 result summary

result 是只读重算响应，不保存成绩 snapshot：

- session safe metadata/status/deadline；
- total item count、submitted count、unanswered count；
- deterministic correct/incorrect count；
- `pending_review_count`；
- `scored_count`、`score_total`、`score_ratio`，只按 deterministic attempts 计算；
- `source_warning_count`；
- `last_attempt_at`。

`pending_review` 不计入 deterministic 分母，也不自动成为 incorrect。summary 不写 attempt、review、mistake 或 progress。

## 5. S4 Attempt Review、Mistake 与 Feedback 契约

### 5.1 Review 事实

新增 `exercise_attempt_reviews`（语义）为 append-only review table，至少包括：

- `id`、`project_id`、`attempt_id`、`exercise_id`；
- `decision`：仅 `correct`、`incorrect`、`uncertain`；
- `feedback`：纯文本，trim 后可为空但最大 4000 chars；
- `reviewer_kind='local_user'`；当前没有 user_id/role；
- `created_at`、`reviewed_at`；
- 可选 `source_revision`/safe citation identity，必须服务端验证。

规则：

1. 只有 `grading_status='pending_review'` 的 attempt 可人工 review；MC/TF deterministic attempt 不接受 review override，保留其原始 deterministic fact。
2. review 是追加事实；同一 attempt 可有多次 review，但只有最新合法 review 用于当前 projection；历史 review 全部保留。若产品只需要一次，重复 review 也必须返回稳定 conflict，不能 UPDATE 旧 row；本最小契约采用“一次 review 后 terminal，重新判断需新 attempt”。
3. `correct`：该 attempt 不形成 mistake occurrence；`incorrect`：形成 mistake occurrence；`uncertain`：保留 review 状态但不形成确定性 mistake。
4. review API response 只返回 attempt ID、decision、feedback safe metadata、reviewed_at；不返回 answer key 或 submitted answer 原文。
5. review 不改变原 `exercise_attempts.grading_status` 的 deterministic/pending fact。若需要 public current status，使用派生的 `review_status`，不可伪造 `deterministic`。
6. review 失败、越权、重复、超长 feedback、invalid decision 必须整个事务 rollback。

### 5.2 Mistake Case

`mistake_cases` 是稳定聚合对象，字段语义：

| 字段 | 规则 |
|---|---|
| `id` | 稳定 `mistake_...` ID |
| `project_id` | 服务端 scope |
| `exercise_id` | 同 project exercise；不因 exercise archive 删除历史 |
| `exercise_revision_fingerprint` | 创建时从 exercise/source identity 生成；不是 current revision 自动替换 |
| `status` | `open`、`in_review`、`fixed`、`reopened`、`archived` |
| `origin` | `deterministic`、`human_review`、`user_reported` |
| `created_at/updated_at` | 服务端 UTC |
| `fixed_at/archived_at` | 状态对应时间 |

归并键冻结为：

```text
(project_id, exercise_id, exercise_revision_fingerprint)
```

不按 session、attempt 或 AI concept 另建 case。一个 case 可以有多次 occurrence；不同题目即使 prompt 相同也不自动合并。

### 5.3 Mistake Occurrence

`mistake_occurrences` 是 append-only，至少包括：

- `id`、`project_id`、`mistake_case_id`、`attempt_id`；
- `origin`：`deterministic`、`human_review`、`user_reported`；
- `reason_code`：`deterministic_incorrect`、`review_incorrect`、`user_marked`；
- source revision/citation safe identity snapshot；
- `created_at`。

规则：

1. 同一 attempt 不能重复生成 occurrence；唯一约束或 domain check 必须拒绝 duplicate。
2. MC/TF `is_correct=false` 在首次进入 S4 projection/read 或显式 materialize 时生成 deterministic occurrence；生成必须幂等，不能因普通刷新增加计数。
3. short answer pending 不自动进入 mistake；只有 review decision `incorrect` 或用户显式 `user_marked` 才能形成对应 origin 的 occurrence，并显示事实来源。
4. occurrence 保留 attempt 与 source identity；source deleted/purged/stale 后只更新 safe status，不删除 occurrence。
5. occurrence 不保存 source full text、stored_path、未验证 quote 或 answer key。

### 5.4 Mistake 状态机与改错

```text
absent → open → in_review → fixed
             ↑       ↓         ↓
             └──── reopened ←──┘
open/in_review/fixed/reopened → archived
```

具体规则：

- 新 occurrence 创建/发现时 case 为 `open`；
- 用户开始查看/编辑改错时可进入 `in_review`；不要求计时；
- 显式提交一条非空 correction/feedback event 后可进入 `fixed`；这表示用户完成一次改错记录，不表示题目永远不会错；
- 新 occurrence 在 fixed case 上产生时自动/事务性进入 `reopened`，但不得删除旧 fixed history；
- `archived` 是用户显式 terminal 状态；不提供 restore/reopen archived case，本阶段新错误可创建新 case only if revision fingerprint differs；
- 不能通过普通 patch 直接改变 status 或覆盖旧 correction；每个动作必须是有审计意义的 event。

`mistake_feedback_events` 至少包括：

- `id`、`project_id`、`mistake_case_id`；
- `event_kind`：`user_correction`、`user_note`、`status_transition`；
- `content` 纯文本最大 12000 chars；
- `provenance='user_created'`；
- `created_at`。

本 9C 最小范围不实现 AI confirmed correction。AI feedback 若未来增加，只能是 `ai_suggestion` draft，不能写入该 user event 表。

### 5.5 Weak Point projection

Weak point 不建立独立 source-of-truth 表，默认由查询实时重算：

- 按 `project_id + exercise_id + exercise_revision_fingerprint` 关联 mistake case；
- 可选按 exercise 的已验证 module/plan context 分组，但 module 缺失时保留 exercise-level bucket；
- 输出 occurrence_count、open_count、fixed_count、reopened_count、last_occurrence_at、source_warning_count；
- 只统计 deterministic incorrect、review_incorrect、user_marked，并保留 origin breakdown；
- pending/uncertain 不计入 incorrect count；
- archived case 默认不计入 active weak-point，但可在历史查询中读取；
- 不输出 answer key、submitted answer、source full text；
- 不将 AI suggestion 计入统计。

如后续为性能增加缓存，缓存必须带 `projection_version`，可由全部事实删除并重建；不能将缓存当不可变事实。

## 6. S5 Cram Goal 与 Cram Session 契约

### 6.1 Cram Goal

`cram_goals` 字段语义：

| 字段 | 规则 |
|---|---|
| `id` | `cram_goal_...` |
| `project_id` | 服务端 scope |
| `title` | trim 后 1–200 Unicode chars |
| `target_date` | 严格 `YYYY-MM-DD` local date |
| `timezone` | 合法 IANA timezone；仅用于 target date/display |
| `target_exercise_count` | 整数 `1..200` |
| `plan_id` / `plan_item_id` | 可 NULL；若存在必须同 project，item 必须属于 plan |
| `status` | `draft`、`active`、`completed`、`archived` |
| timestamps | 服务端 UTC |

规则：

1. 创建 goal 为 draft；显式 activate 后可创建 cram session；draft 可 archive，不能直接产生 session。
2. completed 只由用户显式完成，且至少有一个 finished/expired cram session；不能因 target date 到达自动 completed。
3. archived goal terminal；不自动删除关联 session、attempt、mistake 或 feedback。
4. goal 与 9A plan/item 是引用关系；创建/激活/完成 goal 不写 `study_progress_events`，不修改 plan/item status，不创建 rhythm allocation。
5. target date 是 display/business coordinate，不是自动 scheduler deadline。session 的实际 deadline 仍由 `duration_seconds` + server UTC start 计算。

### 6.2 Cram session

S5 使用 `practice_sessions.session_kind='cram'`，并必须带 `cram_goal_id`。它与 S3 共享：

- session create/start/deadline/finish/expire；
- item snapshot；
- exercise_attempts；
- deterministic grading；
- pending_review 语义；
- privacy/source lifecycle；
- result summary。

Cram session 的额外规则：

1. 选择可以按显式 exercise IDs，或由同 project 的 exercise set/module/plan item 得到候选；最终必须落为 distinct exercise snapshot，客户端不能只发送未验证的 set label。
2. 选择范围必须在 create 时冻结；之后 set/module/plan/item 改变不改 cram session。
3. `target_exercise_count` 是 goal 目标，不保证系统自动补题；选择不足时由用户显式调整或创建新 session，不自动生成题目。
4. S5 不创建自己的 attempt、grade 或 mistake occurrence；所有结果来自共享 session attempts 和 S4 projection。
5. cram summary 可返回 deterministic score、pending review count、mistake count、weak-point safe summary；不能把 suggestion 说成 confirmed knowledge。
6. source warning 不删除 session；purged/stale citation 只显示 unavailable/stale，不能继续提供 source location。

### 6.3 S5 state machine

```text
cram_goal: absent → draft → active → completed
                         └──────────→ archived
cram_session: draft → active → finished|expired → archived
```

同一 session 状态规则复用 S3；goal 和 session 的重复动作、跨 project 关系、空选择、超限、expired submit 均返回稳定 conflict/validation code。

## 7. Source/citation lifecycle

### 7.1 Canonical source status

9C 复用四态：

| 条件 | status | 允许操作 |
|---|---|---|
| material active、current revision、ready chunk、identity/citation 全部验证 | `valid` | 新 session item/summary location 可用 |
| material soft-deleted | `source_deleted` | 历史 session/attempt/mistake 可读；新 citation-dependent create/confirm/relink 禁止 |
| material purged/identity 不存在 | `source_unavailable` | 只保留 opaque identity/status；不返回名称/正文/path/location |
| 非 current revision、chunk 非 ready/stale、identity mismatch | `stale` | 历史可读；不得自动改到新 revision |

### 7.2 事件映射

- **delete**：已有 session item、attempt、mistake occurrence 和 feedback 保留；相关 source status 变 `source_deleted`。
- **restore**：不自动把 `source_deleted` promotion 为 `valid`；本阶段若提供显式 source refresh，必须完整验证 current/ready/citation 后才可更新 status；不改 session/attempt 内容。
- **purge**：source status 变 `source_unavailable`；不删除 session、attempt、review、mistake、feedback、cram goal/result；不恢复 material name、正文、stored path。
- **new revision/re-index**：旧 identity 变 `stale`；不重写 session snapshot，不自动重新生成题目/解析/feedback。
- **read/startup/backup/verify/restore**：不得 refresh、relink、regrade、rebuild、regenerate 或 promotion。

Session item 的题面 snapshot 可继续展示给本地用户；只要 citation 非 valid，就必须显示 source warning，禁用 source location/export action。题面 snapshot 不等于可以恢复原始 source。

## 8. AI、operation、draft 与 provider 边界

### 8.1 本阶段决定

Phase 9C 的必需闭环不包含 AI generation。Phase 8 已有 exercise explanation 和 fake-provider draft generation 足以支持 deterministic S3/S4/S5 验收。9C 不新增 `generate_feedback`、`generate_variant` 或 `generate_explanation` operation 作为 completed gate。

如果未来需要在 9C 内部试验 AI feedback，必须先进行契约变更，至少满足：

- 独立 `ai_operations.operation_type`；
- provider I/O 前先写 safe running operation，失败只保留安全 failed operation；
- output 只在内存结构化校验；
- AI 结果状态为 `draft/suggestion`，不能直接改 mistake status、review decision、weak point 或 cram goal；
- source revision/current ready citation 在最终持久化前再次验证；
- raw prompt、raw provider response、API key、source full text 不持久化；
- explicit Idempotency-Key replay/running conflict/failed retry；
- fake-provider acceptance 与真实 Provider evidence 分开。

### 8.2 现有 artifact 保护

- Phase 8 ready/archived exercise/card 不被 9C 重生成覆盖；
- 9A completed progress/item、9B confirmed note、user feedback、review history 不被 9C 静默修改；
- S5 不能把建议写成 plan/progress；
- restore/startup/read 不会重新调用 provider 或改变 artifact 状态。

## 9. 隐私、输入、错误与 API 资源草案

### 9.1 输入边界

所有 API 由服务端注入 project scope，并限制：

- ID：非空、无控制字符、最大 255 chars；
- title：1–200 Unicode chars；
- duration：60–7200 seconds；
- session item count：1–50；cram goal target count：1–200；
- answer：按题型校验，short answer 非空且最大 1000 chars；
- feedback/correction：纯文本、无 HTML/脚本，最大 4000/12000 chars；
- timezone：只能是可由 Python `zoneinfo.ZoneInfo` 加载的 IANA name，`CST`、`GMT+8` 等缩写拒绝；
- date：严格 `YYYY-MM-DD`，不能接受 datetime/offset/natural language；
- arrays：拒绝重复、跨 project、越权或超上限 IDs；
- 客户端传入的 `score`、`is_correct`、`grading_status`、`source status`、`answer key`、`deadline`、`finished_at`、`project_id` 均忽略或拒绝，不可作为事实。

### 9.2 隐私 DTO

普通 exercise/session/mistake/cram list/detail：

- 可返回题面、options、position、状态、safe score/result、citation identity/status、summary；
- 不返回 `answer_key_json`、answer key、内部 snapshot answer key、`answer_json`、用户 submitted answer 原文、stored_path、raw source text、raw provider response、secret、SQL、traceback。

submit response：

- 可返回新 attempt ID、item/position、deterministic/pending status、score/is_correct（MC/TF）；
- 不回显 answer 或 key；
- 失败只返回 stable error code。

review/feedback detail：

- 可返回 decision、feedback（当前 local user 自己写入的 safe text）、timestamps、provenance；
- 不返回 answer key；submitted answer 仍不在普通 API/DOM/export 中返回。

导出：

- 只提供 bounded JSON/Markdown safe summary；包含题面、状态、score、mistake status、feedback provenance 和 citation status；
- 不导出 answer key、submitted answer、raw source text/path、provider raw data；
- 不支持 CSV/ICS/PDF/考试平台格式。

### 9.3 稳定错误码

9C-7 必须把以下 semantic code 映射到当前 FastAPI 的安全 HTTP status；不得暴露底层异常：

**Session：**

- `study_practice_invalid_payload`
- `study_practice_not_found`
- `study_practice_project_mismatch`
- `study_practice_empty_selection`
- `study_practice_selection_invalid`
- `study_practice_selection_duplicate`
- `study_practice_not_ready`
- `study_practice_invalid_duration`
- `study_practice_invalid_timezone`
- `study_practice_invalid_date`
- `study_practice_invalid_state`
- `study_practice_start_conflict`
- `study_practice_expired`
- `study_practice_item_not_found`
- `study_practice_item_already_submitted`
- `study_practice_submission_invalid`
- `study_practice_submission_idempotency_mismatch`
- `study_practice_result_failed`
- `study_practice_persist_failed`

**Review/mistake：**

- `study_attempt_not_found`
- `study_attempt_review_not_allowed`
- `study_attempt_review_duplicate`
- `study_attempt_review_invalid`
- `study_mistake_not_found`
- `study_mistake_invalid_state`
- `study_mistake_feedback_invalid`
- `study_mistake_feedback_not_allowed`
- `study_mistake_occurrence_duplicate`
- `study_mistake_source_stale`
- `study_mistake_source_unavailable`
- `study_weak_point_failed`

**Cram：**

- `study_cram_goal_not_found`
- `study_cram_goal_invalid_payload`
- `study_cram_goal_invalid_state`
- `study_cram_goal_target_invalid`
- `study_cram_goal_date_invalid`
- `study_cram_goal_timezone_invalid`
- `study_cram_goal_plan_invalid`
- `study_cram_session_invalid_scope`
- `study_cram_session_empty_selection`
- `study_cram_session_failed`

**Source/privacy/operation：**

- `study_source_deleted`
- `study_source_unavailable`
- `study_source_stale`
- `study_operation_not_found`
- `study_operation_in_progress`
- `study_export_failed`
- `study_privacy_boundary`

建议 HTTP 映射：invalid payload 400、not found 404、state/duplicate/expired/source conflict 409、provider/内部持久化失败 500/503；最终 API 命名由 9C-7 复用当前 `_study_error()` 和既有 route 约定，不在 9C-1 重新发明错误 envelope。

### 9.4 API resource 草案

9C-7 可在不改变领域语义的前提下采用等价路径：

```text
POST   /api/study/practice-sessions
GET    /api/study/practice-sessions
GET    /api/study/practice-sessions/{session_id}
POST   /api/study/practice-sessions/{session_id}/start
POST   /api/study/practice-sessions/{session_id}/items/{item_id}/submit
POST   /api/study/practice-sessions/{session_id}/finish
POST   /api/study/practice-sessions/{session_id}/archive
GET    /api/study/practice-sessions/{session_id}/result

GET    /api/study/attempts/{attempt_id}
POST   /api/study/attempts/{attempt_id}/review
GET    /api/study/mistakes
GET    /api/study/mistakes/{mistake_id}
POST   /api/study/mistakes/{mistake_id}/start-review
POST   /api/study/mistakes/{mistake_id}/feedback
POST   /api/study/mistakes/{mistake_id}/redo
POST   /api/study/mistakes/{mistake_id}/archive
GET    /api/study/weak-points

GET    /api/study/cram-goals
POST   /api/study/cram-goals
GET    /api/study/cram-goals/{goal_id}
POST   /api/study/cram-goals/{goal_id}/activate
POST   /api/study/cram-goals/{goal_id}/complete
POST   /api/study/cram-goals/{goal_id}/archive
POST   /api/study/cram-goals/{goal_id}/sessions
GET    /api/study/cram-goals/{goal_id}/summary
```

不提供客户端设置 deadline、score、reviewed/correctness、source status 或 project scope 的接口。

## 10. SQLite constraint 与 domain transaction 分工

### 10.1 SQLite 应表达

9C-2 v11 migration 应表达可由 SQLite 稳定保证的约束：

- status/provenance/session_kind/decision/origin/reason/event_kind 的 CHECK；
- project/entity ownership 的 FK；
- session item `(session_id, position)` 唯一；
- session item `(session_id, exercise_id)` 唯一；
- exercise attempt session/item/submission key 的适当唯一索引；
- review/occurrence/feedback 主键和基础 FK；
- `duration_seconds`、position、target count、文本长度的基础约束；
- cram goal 的合法 status 和可选 plan references；
- `mistake_occurrences(attempt_id, reason_code)` 防重复；
- 所有 query 所需的 project/status/time/source indexes。

不要假装 SQLite CHECK 能证明：当前 exercise ready、同 project 的跨表关系、deadline 当前时间、citation current/ready、session item 快照与 source 的语义一致、weak point projection、progress 不被改写。

### 10.2 Domain transaction 必须表达

9C-3 至少实现并测试：

1. project/plan/item/module/exercise ownership 与状态检查；
2. session selection snapshot、ready gate、题型校验和冻结；
3. server UTC start/deadline/finish/expiry，锁竞争下的保守判断；
4. session item submit 的 answer validation、server grading、append-only attempt、idempotency；
5. result summary 只读重算，不写隐式 facts；
6. pending short-answer review 的 decision/feedback、duplicate protection、append-only history；
7. mistake case 归并、occurrence 幂等、状态 transition、redo new attempt；
8. weak-point projection 的确定性规则和 source warning；
9. cram goal/session scope、snapshot、S3/S4 reuse、不修改 9A/9B；
10. citation/source refresh、delete/restore/purge/re-index 安全状态；
11. 所有多行写入 rollback，不能留下半个 session、item、attempt、review、mistake 或 feedback；
12. answer key/submitted answer 不越过 safe DTO/log/export boundary。

## 11. Backup/restore non-repair 契约

Phase 9C 新增记录必须在 backup SQLite snapshot 中保留：

- draft/active/finished/expired/archived practice/cram sessions；
- immutable session items；
- exercise attempts 和 submission idempotency metadata；
- pending/reviewed attempt review facts；
- mistake cases、occurrences、feedback events；
- cram goals、关联 plan/item；
- `ai_operations`（若未来存在 9C operation）；
- source statuses、opaque identity 和历史时间。

`backup`、`verify-backup`、`restore`、startup、ordinary read 必须：

- 保留 schema history/version、append-only row 和 status；
- 不调用 provider；
- 不重新评分、不重跑 pending review、不重建 mistake occurrence、不重新计算后写入 projection、不重跑 cram；
- 不把 expired/stale/source_deleted/source_unavailable promotion；
- 不恢复 answer key/submitted answer 到普通响应；
- 不覆盖 live data root；restore 只到新空目录；
- 不在 manifest/log/error 中泄露 path、secret、raw source/provider data。

Weak point 作为实时 projection 读时可以计算，但读取不得写 cache；若未来有缓存，restore 只能保留其 versioned rows，并必须证明不影响事实和 source status。

## 12. Test contract for downstream tasks

### Gate B（本任务）

9C-1 通过条件：

- S3/S4/S5 实体关系、owner、状态和状态转换无歧义；
- session time/deadline/timeout/reload/idempotency 明确；
- MC/TF/short answer/review/redo 语义明确；
- mistake occurrence/case/feedback/weak-point 事实与 projection 分离；
- S5 复用 S3/S4，不产生第二套 grading/attempt；
- privacy、source lifecycle、API/error/export、SQLite/domain 分工和 restore non-repair 可直接写 tests；
- 9D、Phase 10 和真实 Provider non-goals 未混入。

### 后续 focused tests 必须覆盖

- `test_phase9c_domain.py`：所有跨 project/state/transaction/idempotency/time/source/mistake/cram rules；
- `test_phase9c_api.py`：HTTP status/error/input/privacy DTO；
- `test_phase9c_source_lifecycle.py`：delete/restore/purge/re-index status and historical facts；
- `test_phase9c_backup_restore.py`：backup→verify→new-empty-target restore、schema/history、non-repair；
- `browser_phase9c.spec.js`：S3/S4/S5 happy/failure/expired/duplicate/reload/narrow/keyboard/privacy；
- migration tests：new DB、v10 upgrade、idempotency、rollback、`schema_migrations`/`user_version`/backup version。

测试不得把 answer key、submitted answer、provider key、raw source text 或 private path 写进 assertion output/artifact。

## 13. Gate B 结论与准确状态

本契约冻结了 9C-0 提出的时间、答案安全、重做、错题归并、人工复核、weak point、冲刺范围、source lifecycle、AI boundary、API/error、migration/domain 分工和 backup/restore non-repair 未决项。

准确状态：

> **Phase 9C-1：`planned/contract-frozen`。** S3/S4/S5 正式实体关系、状态机、不变量、时间/评分/复核/重做/冲刺语义和隐私边界已冻结；9C-2 已完成 v11 migration/schema，9C-3 已完成共享 repository/domain transaction，9C-4 已完成 S3 PracticeRunner backend workflow，9C-5 已完成 S4 ErrorFixer backend workflow，均为 `implemented/backend-pass`。API、UI、S5 独立 workflow、lifecycle/restore 和最终 acceptance 仍未完成，不代表 Phase 9C completed。

下一任务：**9C-6 S5 期末冲刺工作流**。复用既有 S3 session、S4 feedback/mistake 和 9A plan references 完成 cram goal/session backend workflow，不顺手扩大至 API/UI 或 Phase 9C closeout。
