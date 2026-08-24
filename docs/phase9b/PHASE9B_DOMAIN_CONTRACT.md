# Phase 9B 资料学习工作流（S1/S2）正式领域契约与状态机

> 状态：`planned/contract-frozen`。
>
> 本文由 9B-0 现状审计初稿升级为 9B-1 正式契约。它冻结 Phase 9B 的 S1 学习节奏和 S2 资料笔记/知识模块关联边界，可直接驱动后续 migration、repository/domain、API、Chromium、source lifecycle 和 backup/restore 测试。
>
> 本文不是实现证据。当前 Phase 9B 尚未有正式 note、note block、rhythm 或 S2 generation 用户路径；9B-2 之前不得据此修改生产 schema。

## 1. 契约范围与基线

### 1.1 当前正式基线

- 当前 schema version 为 **9**，由 `backend/app/migrations/runner.py:CURRENT_SCHEMA_VERSION` 和连续 `_MIGRATIONS` 定义；Phase 9B 的 schema 变更必须追加为连续 v10 或更高 migration，不得修改 v1–v9 history。
- `materials`、`extractions`、`text_spans` 是原始资料 source of truth；`material_revisions`、`chunks`、`retrieval_runs/hits`、context、citations、AI operations、Cards/Exercises、9A plans 和本 Phase 的 notes/rhythm 都是派生数据或用户状态。
- 当前边界是单进程、单实例、SQLite、本地存储和 `project_id` scope。当前没有 `user_id`、认证、授权或多用户模型；9B 不新增这些能力。
- Phase 9A 已正式实现并验收：learning goal、knowledge module、study plan/item、same-plan dependency DAG、append-only progress、progress summary、module/item source links 和 source lifecycle。9B 必须复用这些已验证对象，不创建平行的计划或进度事实源。
- 当前 `knowledge_modules` 是 9A 的 project-scoped 可复用元数据对象，不自动升级为资料笔记正文、AI artifact 或历史版本 `KnowledgeModule`。

源码依据：`backend/app/migrations/runner.py`、`backend/app/repository.py:connect()`、9A study functions、`backend/app/main.py` `/api/study/*` routes、`docs/PHASE9A_ACCEPTANCE_EVIDENCE.md`。

### 1.2 Phase 9B 目标

Phase 9B 只冻结并实现以下两条用户路径：

```text
S1 学习节奏
已有 study plan/item/progress
  → 显式 rhythm/cadence 设置
  → 按本地日期为 item 安排工作量
  → 查看 timeline/load/coverage summary
  → 用户手动调整
  → 完成 item 后保留安排和 progress 历史

S2 资料笔记
active material/revision/chunk/retrieval/citation
  → 用户创建 note/note block
  → 关联 knowledge module
  → 关联经服务端验证的 source/citation identity
  → 可选生成 citation-safe fake-provider note draft
  → 用户编辑、确认、拒绝或归档
  → source lifecycle 显式刷新
```

### 1.3 明确不做

Phase 9B 不实现或不把以下内容作为完成前置：

- S3 限时练习、S4 错题改错、S5 期末冲刺；
- S6 家长报告；S7 课堂采集、OCR、ASR；
- 真实 Provider 下的 note、module、plan generation real-pass；
- 人工简答复核、教师/家长审核；
- reminder、push、calendar sync、recurrence engine、background scheduler；
- worker、queue、cancel、流式长任务、跨进程协调；
- 多用户、认证授权、云同步、协作、外部 vector DB；
- 自动索引历史材料、自动 repair/rebuild、自动 re-plan；
- 导图、知识图谱、复杂推荐、评分或语义图数据库；
- 通过客户端 project/user 参数绕过当前 project scope。

## 2. 正式术语与实体关系

### 2.1 Glossary

| 术语 | 正式含义 | 是否为 source of truth |
|---|---|---:|
| Rhythm | 一个已有 study plan 的显式学习节奏配置，定义 cadence、timezone 和周期边界；不是 scheduler | 否，用户安排状态 |
| Rhythm Allocation | 一个 plan item 在某个用户本地日上的 planned minutes 安排事实；可由用户调整 | 否，用户安排事实 |
| Rhythm Summary | 从 rhythm config、allocations、当前 item projection 和 progress events 计算出的只读摘要 | 否，派生响应 |
| Note | S2 的资料笔记容器，保存标题、生命周期、来源类型和用户编辑保护；可由用户创建或由 fake provider 生成 draft | 否，用户/AI artifact |
| Note Block | Note 内有序的最小可编辑内容单元。Phase 9B 只保存文本内容和有限 block kind，不保存富文本 HTML | 否，用户/AI artifact |
| Knowledge Module | 9A 已存在的可复用学习主题元数据对象；S2 通过显式多对多关联组织 note，不改变其 9A 生命周期语义 | 否，用户状态 |
| Note–Module Link | note 与同一 project 的 knowledge module 的组织关系，不等同于 source provenance | 否 |
| Note Block Source Link | note block 到 material/revision/chunk/span/citation identity 的可验证来源关系 | 否，provenance |
| Citation | context/retrieval 产生并由服务端验证的 citation key 及其 source identity；不是模型可自由创建的字符串 | 否，provenance |
| AI Note Draft | `provenance=ai_generated` 且 `status=draft` 的 note 及其 blocks；必须有可验证 citation，不能直接成为 confirmed | 否，待确认 artifact |
| User Note | `provenance=user_created` 的 note；可以没有 source，但无 source 的内容不能宣称为资料事实 | 否，用户 artifact |
| Local Date | 按 note/rhythm 的 IANA timezone 解释的 `YYYY-MM-DD` 日期；不是宿主机隐式本地日期 | 否，安排坐标 |

### 2.2 总体关系

```text
project
├── learning_goals                         [Phase 9A]
├── knowledge_modules                      [Phase 9A, reusable metadata]
│     └── note_module_links                [Phase 9B, many-to-many organization]
├── study_plans                            [Phase 9A]
│     ├── study_plan_items                 [Phase 9A]
│     │     └── rhythm_allocations         [Phase 9B, optional user schedule facts]
│     ├── study_progress_events             [Phase 9A, append-only facts]
│     └── rhythm_settings                  [Phase 9B, at most one per plan]
└── notes                                  [Phase 9B]
      └── note_blocks                      [Phase 9B, ordered text units]
            └── note_block_source_links    [Phase 9B, verified provenance]
```

关系决策：

1. 一个 rhythm 只属于一个已有 study plan；一个 plan 最多一个 rhythm settings 记录。S1 不创建新的 plan、task 或 progress event 事实源。
2. 一个 note 属于一个 project，可以关联零个或多个同 project 的 knowledge module；一个 module 可以关联零个或多个 note。该关联只表示组织关系，不自动把 module source links 复制到 note。
3. 一个 note 至少有一个 note block；note block 在 note 内有唯一 position。Phase 9B 不支持跨 note 共享 block。
4. 一个 note block 可以有零个或多个 source links；一个 source link 只属于一个 block。citation provenance 绑定 block，不绑定整个 note 的模糊文本范围。
5. 一个 note 可以关联多个 material/revision，但必须通过不同 block source links 表达；不得用 note 级 `material_id` 覆盖多来源关系。
6. note/module 的关系不能跨 project；source identity 的 material 也必须属于当前 project。所有跨行、跨项目、current revision 和 citation 规则由 repository/domain transaction 强制。

## 3. S1 学习节奏正式契约

### 3.1 与 Phase 9A 的关系

S1 只扩展已有 `study_plans`、`study_plan_items` 和 `study_progress_events` 的用户安排视图：

- rhythm settings 的 parent 必须是同 project 的既有 plan；plan 不存在或跨 project 时拒绝；
- allocation 的 item 必须属于该 plan，不能指向其它 plan/project；
- allocation 不改变 item status，不新增 progress event；只有用户调用已有 progress API 才能改变 progress projection；
- item 完成、跳过、重开不会删除 allocation 或 progress history；summary 在读取时重新计算；
- archived item 的 allocation 保留为历史数据，但不进入 active rhythm coverage/load 分母；
- archived plan 不允许新增或修改 rhythm/allocation；active、paused 和 confirmed plan 允许按后续 API contract 修改安排；draft plan 允许设置安排；completed plan 的 rhythm 只读。

### 3.2 Rhythm settings 字段契约

9B-2 应实现等价于以下语义的表/字段；具体列名可在不改变语义的情况下由 migration 任务确定：

| 字段 | 约束与语义 |
|---|---|
| `id` | 稳定 `rhythm_...` ID；一个 plan 只能有一个 active settings 记录 |
| `project_id` | 由服务端注入并与 plan 一致，客户端不可指定任意 project |
| `plan_id` | 必填，FK 到同 project `study_plans`，唯一 |
| `cadence` | 只允许 `daily` 或 `weekly`；Phase 9B 不实现 custom recurrence |
| `timezone` | 必填 IANA timezone 名称，例如 `Asia/Shanghai`、`UTC`；服务端用 `zoneinfo` 校验，禁止任意缩写和静默 fallback |
| `period_start` | 必填 `YYYY-MM-DD` local date；作为 summary 的固定起点，必须能按 timezone 解释 |
| `target_minutes` | 非负整数，范围 `0..10080`；为该 rhythm 周期目标，不是已完成时长 |
| `created_at/updated_at` | UTC ISO-8601；服务端生成 |

`cadence` 语义：

- `daily`：一个 rhythm period 是一个 `period_start + n days` 的本地日；每个 period 的目标为 `target_minutes`，允许 `0` 表示只使用 item allocation、不设目标。
- `weekly`：一个 rhythm period 是从 `period_start` 起连续 7 个本地日；每个 period 的目标为 `target_minutes`。`period_start` 不强制为周一，以支持用户明确选择的起始日。
- 不支持 custom cadence、recurrence rule、例外日、法定节假日、提醒时间、日历事件或宿主机 timezone 推断。
- `period_start` 是 date-only 业务坐标；不在数据库中伪造午夜 UTC instant。API 返回原始 local date 和 timezone。

timezone 只用于把 allocation 的 local date 分到 period；S1 不保存一天内的具体时刻，因此 DST 不会产生额外小时或自动重排。若未来要支持具体时段，必须新增独立契约，不得把 minutes 假定为时钟区间。

### 3.3 Rhythm allocation 字段契约

| 字段 | 约束与语义 |
|---|---|
| `id` | 稳定 `rhythm_allocation_...` ID |
| `project_id` | 必须与 plan/item 一致 |
| `plan_id` | 必须与 item 的 plan 一致 |
| `item_id` | 必须是该 plan 的非跨项目 item |
| `local_date` | `YYYY-MM-DD`，按 rhythm timezone 解释；不得包含时间或 offset |
| `planned_minutes` | 正整数 `1..1440`；单个 item 单日最多 1440 分钟 |
| `created_at/updated_at` | UTC ISO-8601 |

约束与操作：

1. 同一个 `(item_id, local_date)` 最多一个 allocation；重复 create 使用显式 allocation ID 或幂等语义 replay，不产生第二行。
2. 一个 item 可以拆到多个 local date；一个 local date 可以安排多个 item。
3. 一个 item 的所有 allocation 总和上限为 `10080` 分钟；单个 rhythm period 的 allocation 总和也上限为 `10080` 分钟。超过上限拒绝，不能自动截断或自动移动。
4. allocation 的 `local_date` 不受宿主机当前日期影响；API 必须显式传入，服务端按冻结格式解析。
5. “移动”是同一 allocation 的受限日期/分钟更新，不创建第二套 progress 事件；实现必须在事务中保持唯一约束。
6. `pending/in_progress/skipped` item 的 allocation 可在允许编辑的 plan 状态下调整；`completed` item 的 allocation 只读，保留历史安排。`archived` item 不能新建 allocation。
7. allocation 不自动产生 `started/completed/skipped/reopened`，不自动改变 item status，也不因日期经过而产生 overdue event。
8. 9B 不保存可编辑的 completed minutes；progress summary 的完成状态来自 9A item projection。`planned_minutes` 不是实际耗时，不得在 UI/API 中称为 completed time。

### 3.4 S1 状态和合法操作

S1 没有独立的执行状态机；其状态由 parent plan、item projection 和 source warning 组成：

```text
rhythm settings: absent → present → updated
allocation:       absent → present → updated → deleted
plan:              draft/confirmed/active/paused → schedule editable
                  completed → read-only
                  archived → read-only/no new rows
item:              pending/in_progress/skipped → allocation editable
                  completed/archived → allocation read-only
```

- 删除 allocation 只删除尚未成为历史完成记录的用户安排事实；不删除 progress event。删除已完成 item 的 allocation 被拒绝。
- rhythm settings 可更新 cadence、timezone、period_start、target_minutes；更新不重写或删除既有 allocation。读取 summary 时按新的 timezone/period_start 重新分组；如果已有 allocation 超出新视图范围，返回 `unassigned`，不自动移动。
- plan/item 的既有 9A 状态转移保持不变；S1 不新增 `scheduled`、`overdue` 或 `session_completed` 状态。
- active plan 可以存在 source warning 或没有 source 的 item；S1 不因 source unavailable 阻止 plan 激活，详情只显示 warning。

### 3.5 S1 Summary 规则

`rhythm_summary` 是只读派生响应，不单独持久化 snapshot。至少包含：

- rhythm settings：cadence、timezone、period_start、target_minutes；
- period buckets：period key、local date range、planned_minutes、target_minutes、remaining_target_minutes；
- `allocated_item_count`、`unassigned_item_count`、`archived_item_count`；
- `completed_item_count`、`in_progress_item_count`、`pending_item_count`、`skipped_item_count`；
- `source_warning_count`；
- `last_progress_event_at`。

计算规则：

1. allocation 只按自己的 `local_date` 和当前 rhythm settings 分桶；不根据 UTC 转换日期，不读取服务器当前时区。
2. `unassigned_item_count` 是未归档、没有至少一条 allocation 的 plan item 数量；completed item 仍可计入历史 `allocated_item_count`，但 summary 必须明确其完成状态。
3. `remaining_target_minutes = max(target_minutes - planned_minutes, 0)`；不把实际完成状态冒充为完成分钟数。
4. archived item allocation 不计入当前 load/coverage；其历史行可在 detail/history 中受限展示。
5. progress event 与 allocation 读取可以分别查询，summary 必须在同一读取快照中保持 project/plan scope 一致；不写 summary 表。
6. 空计划、无 rhythm settings 或无 allocation 不报错：返回明确的 `rhythm_not_configured`/空 summary 语义，由 API contract 冻结 HTTP 表达；不自动创建默认 rhythm。

## 4. S2 资料笔记与知识模块正式契约

### 4.1 Note 字段与来源

| 字段 | 约束与语义 |
|---|---|
| `id` | 稳定 `note_...` ID |
| `project_id` | 服务端注入；note/module/source 必须同 project |
| `title` | 必填，去除首尾空白后 `1..400` 字符 |
| `status` | `draft`、`confirmed`、`archived` |
| `provenance` | `user_created` 或 `ai_generated`；创建后不可修改 |
| `user_edited` | 0/1；用户修改 title/block/module association 后设为 1 |
| `generation_operation_id` | AI note 可选，指向成功或失败审计 operation；用户 note 为 NULL |
| `created_at/updated_at` | UTC ISO-8601 |
| `confirmed_at/archived_at` | 状态转移时由服务端写入 |

Note 创建规则：

1. 用户创建的 note 为 `draft + user_created`，可以没有 source；无 source 的 user note 不得被展示为已验证资料结论。
2. AI 创建的 note 为 `draft + ai_generated`，必须绑定一个成功的 `generate_note` operation，并且每个生成 block 至少有一个创建时验证为 `valid` 的 source link。
3. note 不能物理删除。draft 可以 archive；confirmed note 只能 archive，不能回到 draft，也不能被普通 patch 静默替换为新内容。
4. note 至少保留一个 block；空内容 note 的创建、保存或确认由 API/domain 以稳定错误拒绝。
5. note 的 `status` 不直接变成 `stale` 或 `source_unavailable`。来源状态属于 note block source link；note detail 返回 `source_warning_count` 和每条 link status。

### 4.2 Note block 字段与状态

| 字段 | 约束与语义 |
|---|---|
| `id` | 稳定 `note_block_...` ID |
| `note_id/project_id` | 必填，scope 必须一致 |
| `position` | 非负整数；同一 note 唯一、稳定排序 |
| `block_kind` | 只允许 `text`、`heading`、`bullet`；不保存 HTML、脚本、图片、图谱或富文本 AST |
| `content` | 必填 UTF-8 文本；服务端限制总长度和单 block 长度，具体上限由 API contract 采用本契约语义后冻结 |
| `provenance` | `user_created` 或 `ai_generated`；AI draft block 不得伪装为 user-created |
| `created_at/updated_at` | UTC ISO-8601 |

- block 不设独立 confirmed 状态；其可编辑性由 parent note status 和 provenance 保护。
- draft note 内 block 可编辑、排序和有限增删，但 note 必须始终保留至少一个 block。
- confirmed/archived note 的 block 不允许普通编辑、删除或排序；用户要修改必须创建新的 user note 或由未来独立契约提供 revision workflow，9B 不实现隐式 revision。
- 用户对 AI draft 的任何 block 修改把 note 标记 `user_edited=1`，但不会把 provenance 改成 user-created，也不会删除 generation operation 或原始 citation。
- source link 不保存正文全文；block content 是用户/AI artifact，不是 source replacement。

### 4.3 Note–module 关系

- `knowledge_modules` 继续使用 9A 的 `active/archived` 生命周期，不新增 `draft`、`confirmed` 或 `stale` module 状态，不改变已有 9A 表的既有语义。
- S2 新增 note–module link（建议独立表），一条 link 只能连接同 project 的一个 note 和一个 module；同一 pair 不重复。
- draft note 可以关联 active module；confirmed note 关联的 module 可以后来 archive，历史 link 保留并返回 module archived warning。
- 新增 link 不能指向 archived module；删除 link 只删除组织关系，不删除 note、module、block、source link 或 progress。
- AI `generate_note` 不直接创建、修改或 archive knowledge module，不生成“已确认知识点”。用户必须显式创建/选择 module 并关联 note。若未来需要 AI module suggestion，必须另立 operation/output contract，不属于 9B-1 的生成落库范围。

### 4.4 Note source link 和 citation

建议新增独立 `note_block_source_links` 表，不能把 9A 的 `module_source_links` 直接改成多态 owner 表。最小语义字段：

```text
id, project_id, note_id, note_block_id,
material_id, revision_id, extraction_id, chunk_id, span_id,
citation_key, status, created_at, updated_at
```

约束：

1. `note_id`、`note_block_id` 必须同属当前 project 和同一 note；source material 也必须属于当前 project。
2. `material_id`、`revision_id`、`extraction_id`、`chunk_id`、`span_id`、`citation_key` 是 source identity/定位 metadata；不得保存 `stored_path`、原文件内容或未受限正文副本。
3. `citation_key` 如果存在，必须来自当前 `assemble_context()` 或 retrieval 结果并通过 `validate_citation_key()`；客户端不能仅凭字符串建立 valid link。
4. 一个 block 可以关联多个不同 citation；同一 block/citation pair 不重复。不同 block 可以引用同一 chunk/citation，但各自 link 独立保存。
5. user-created note 的 block 可以零 source link；AI-generated note 的每个 block 至少一个 valid link 才可创建成功/确认。
6. source link status 由服务端计算，客户端提交的 status 一律忽略或拒绝；初始落库只能是 `valid`。
7. source link 不保存 quote。UI/API 需要显示引用内容时，使用当前 citation/source contract 受限读取；source unavailable 时只显示安全状态和稳定 identity，不伪造材料名称、正文或可点击定位。

### 4.5 S2 Note 状态机

```text
user-created:
  absent → draft → confirmed → archived
                 └────────────→ archived

ai-generated:
  generation_running → draft → confirmed → archived
                         ├────→ rejected (rejected draft is retained as history)
                         └────→ archived
```

正式状态集合为 `draft`、`confirmed`、`rejected`、`archived`。`rejected` 只适用于曾经持久化的 AI-generated draft；它是不可编辑的历史 artifact，不是可确认或可用的 note。Provider 在 note 持久化前失败时不创建 note artifact，只保留 `ai_operations.status='failed'`；只有已经写入的 draft 被用户显式 reject 后才进入 `rejected`。user-created note 不进入 `rejected` 状态。retry 永远创建新的 note draft，不复用或覆盖 rejected artifact。

合法操作：

- user draft：编辑 title/block、排序、添加/删除 source link、关联/取消 module、confirm、archive；
- AI draft：在 source/citation 验证通过后允许用户编辑、关联 module、confirm、reject、archive；
- confirmed：只读，可显式 archive；不能 patch、reopen 或被新 generation 覆盖；
- archived：只读终态；不可恢复到 draft/confirmed；
- rejected：只读历史 draft，不可 confirm；可 archive；retry 创建新 note draft，不复用或覆盖旧 note。

确认规则：

1. user-created note 可以无 source，内容非空即可 confirm；界面必须明确“用户笔记/无已验证来源”，不得把它显示为 AI 事实。
2. ai-generated note 每个 block 至少需要一个当前 `valid` source link；任一 required link 为 stale/source_deleted/source_unavailable 或不存在时，confirm 拒绝。
3. 已确认 AI note 后 source 被删除、purged 或变 stale，不回滚 note status，不删除内容，不提升 link 状态；detail 显示 warning。以后若用户要编辑，9B 不提供把 confirmed note 改回 draft 的 API。
4. 重新生成永远创建新 note draft；不得静默覆盖 user-edited、confirmed、archived 或 rejected artifact。

### 4.6 AI note generation contract

Phase 9B 只允许 deterministic fake provider 的可选 S2 note generation；真实网络 Provider generation 不属于本 Phase completed evidence。

- 新 operation type：`generate_note`。不复用当前仅支持 card/exercise 的 artifact persistence；9B-3/9B-4 必须实现 note-specific atomic persistence。
- operation 必须记录 project、material scope、source revision identity、retrieval policy、prompt version、provider/model、request ID/usage/latency、status、error code 和 output note ID；不保存 raw prompt、raw provider response 或 secret。
- 输入必须是显式的 active material scope，至少一个 material，且已建立 current ready indexing；允许 lexical/vector/hybrid 但必须复用现有 retrieval/context/citation contract。多 material generation 的每个 block 必须保留对应 citation identity。
- Provider 输出必须在内存中通过固定结构化 schema 验证：title、ordered blocks、block_kind、content、citation keys；未知字段、越界长度、空 blocks、伪造 citation、跨 revision citation 都拒绝。
- operation 状态沿用 `queued/running/succeeded/failed/cancelled/stale` 语义，但 9B 不实现 queued worker、cancel 或后台 stale scanner；同步请求只使用 running→succeeded/failed，失败后保留安全审计。
- `Idempotency-Key` 是显式请求 contract：同 key+同 fingerprint 的 succeeded 请求 replay 同一 note response；running 返回 conflict；failed key 可重试并创建新 operation；同 key+不同 fingerprint 拒绝。无 key 的相同请求不视为重复。
- Provider 未配置、retrieval empty/not ready、timeout、rate-limit、malformed/schema/citation failure 不能留下半成品 note；operation 保留稳定 failed code，重试由用户显式触发。
- Provider I/O 不得持有 SQLite 长写事务：先创建 operation/必要 retrieval metadata 并 commit，再调用 provider，最后在单独事务中验证 source/citation 并原子写 note、blocks、links、operation success。

## 5. Source lifecycle 正式映射

### 5.1 Note block source link 状态

source link status 只能由实际 source identity 计算：

| 实际条件 | status | 可定位/可作为新确认来源 |
|---|---|---|
| material active；revision current；chunk ready；chunk/material/extraction/span/citation identity 一致 | `valid` | 可定位；可用于 AI draft confirm |
| material soft-deleted | `source_deleted` | 不可定位；不可用于新 AI confirm |
| material purged 或 identity 已不存在 | `source_unavailable` | 不可定位；不可用于新 AI confirm |
| material active 但 revision 非 current、chunk stale/missing/not ready、span/citation 不一致 | `stale` | 不可定位；不可用于新 AI confirm |
| 客户端提交不存在/伪造 relation | reject，不落库 | 否 |

### 5.2 生命周期操作

- **delete**：note/module/plan artifact 不删除；相关 note block links 更新为 `source_deleted`，已确认 note 保留内容并显示 warning。
- **restore**：只恢复 material lifecycle；note link 不因 startup/read/restore 自动变 `valid`。必须调用显式 source refresh/read validation；若 source identity 已恢复且 current/ready 一致，显式刷新可变回 `valid`。
- **purge**：note、blocks、module link、source link、operation history 和用户内容保留；source link 固定为 `source_unavailable`。不得恢复材料名称、正文、stored_path 或 clickable citation。数据库外键清理不能让 link 被误解为 valid；实现必须保留 status 或等价 unavailable tombstone 语义。
- **new extraction/new revision**：旧 link 变 `stale`，除非 link 指向的新 current identity 是用户显式重新绑定的结果；不自动把旧 note source link 改写到新 revision。
- **chunk re-index**：原 chunk stale/deleted 或 identity 不一致时 link 变 `stale`；新 chunk 必须通过用户显式 source relink/refresh contract 重新绑定。
- **module archive**：note/module link 保留并显示 archived module；不能删除 note 或 source link。新 note 不能关联 archived module。
- **plan/item lifecycle**：S1 allocations 服从 plan/item 读写保护；S2 note 不因 plan archive、item complete 或 progress event 被删除、重生成或改写。

### 5.3 Active 对象与 unavailable source

- active study plan 允许 source warning；S1 rhythm 不因 source unavailable 禁止设置或读取。
- confirmed note 允许在后来 source unavailable 的情况下继续存在，内容和状态保留，detail 返回 warning。
- AI draft note 在 confirm 时不允许 required source unavailable/stale；user-created note 可以无 source，但必须保持 provenance 和 UI 语义。
- source unavailable 不会阻止应用启动、普通 note 读取、计划读取或 backup/restore；它只限制新 citation-dependent 操作。

## 6. 时间、时区和输入边界

### 6.1 时间格式

- 所有系统审计时间 `created_at/updated_at/confirmed_at/...` 保存 timezone-aware UTC ISO-8601，由服务端生成。
- S1 业务安排日期只接受严格 `YYYY-MM-DD` local date；不接受 datetime、Unix timestamp、任意 offset 或模糊自然语言日期。
- timezone 只接受 Python `zoneinfo.ZoneInfo` 可加载的 IANA name；不接受 `CST`、`GMT+8` 等有歧义缩写。`UTC` 是有效值。
- 解析、分桶和错误结果不能依赖宿主机本地 timezone；测试必须固定多个 timezone，至少覆盖 `UTC` 和一个非 UTC IANA zone。

### 6.2 输入边界

以下语义由 domain contract 冻结，具体 HTTP status 由 9B-6 API contract 遵循现有 400/404/409/500 风格：

- title 必须是字符串、去空白后非空、最大 400；description/content/block text 使用服务端固定上限，空内容按资源规则拒绝；
- `cadence` 只接受 `daily|weekly`；`target_minutes` 为整数 `0..10080`；`planned_minutes` 为整数 `1..1440`；
- allocation total 超过单 item 或单 period 上限拒绝；不静默截断、拆分、移动；
- local date、timezone、position、ID、enum、module/note/source ownership 均由服务端验证；
- 客户端不能提交 `project_id` 作为 scope 选择、source status、stored path、provider metadata 或 operation status；
- note source citation 必须服务端重新验证，不能信任客户端 quote、material name 或 status；
- malformed JSON、未知状态、过长 idempotency key、重复/冲突 idempotency key 使用稳定安全错误，不返回 SQLite/Provider 原文。

## 7. 事务、不变量与数据库/领域责任

### 7.1 SQLite/schema 可表达的约束

9B migration 至少应表达：

- project/plan/item/note/block/module 的 foreign key；
- note status/provenance、block kind、rhythm cadence、source link status 的 CHECK；
- timezone/date 作为 TEXT 的基础非空约束（IANA/date 语义由 domain 校验）；
- non-negative position、positive planned minutes；
- `(plan_id)` rhythm settings 唯一；`(note_id, module_id)` link 唯一；`(note_id, position)` block 唯一；`(item_id, local_date)` allocation 唯一；
- source link 的 owner/link identity 必填边界和合适索引；
- AI operation/note generation 的 FK 和 project scope 关系（无法完全由 SQLite 证明的部分由 domain 校验）。

不得用 migration DDL 假定 SQLite CHECK 可以表达跨行 current revision、同 project 或 DAG 规则。

### 7.2 Repository/domain transaction 必须表达

以下规则不能只依赖数据库，必须在 repository/domain 事务中验证并测试：

1. plan/item/rhythm allocation 的同 project、同 plan 关系；
2. cadence/timezone/local date/workload 解析和所有上限；
3. archived/completed plan/item 的写保护；
4. summary 的确定性分桶、unassigned、archived exclusion 和 progress 联动；
5. note/block/module 同 project 关系和 note 至少一个 block；
6. note state transition、AI/user provenance、用户编辑保护、confirmed/rejected/archived terminal semantics；
7. source revision/chunk/span/citation 的 current/ready/active identity 验证；
8. source lifecycle refresh 和 unavailable tombstone，不提升 stale/unavailable；
9. AI structured output、citation revalidation、operation idempotency、failed retry 和原子 note persistence；
10. 导出只读受控 artifact，不暴露路径、secret、raw provider 或未验证 source text；
11. 所有失败在事务中 rollback，不留下半个 note、block、link、allocation 或错误的 progress projection。

### 7.3 备份/恢复 non-repair 不变量

backup、verify、restore、startup 和普通 read：

- 必须保留 schema version、migration history、note/block/module links、rhythm settings/allocations、operation status、draft/confirmed/archived/rejected 和 source link status；
- 不得创建默认 rhythm、note、block、citation、progress event 或 AI operation；
- 不得调用 Provider、重新检索、重建 chunk/FTS/embedding、自动 relink source 或自动生成 note；
- 不得把 `stale`、`source_deleted`、`source_unavailable` 提升成 `valid`；
- restore 只能到不存在或空目标目录，保持已有 operator backup/restore contract；
- manifest、日志和响应不得泄露 live data root、stored_path、secret、raw exception、raw Provider output 或完整 source text。

## 8. 稳定错误码草案（9B-1 冻结语义）

以下错误码是 9B 域/API 的稳定语义集合；9B-6 可以将同一语义映射到现有 HTTP status，但不得返回原始异常文本：

### S1

- `study_rhythm_not_found`
- `study_rhythm_not_configured`
- `study_rhythm_invalid_payload`
- `study_rhythm_invalid_cadence`
- `study_rhythm_invalid_timezone`
- `study_rhythm_invalid_date`
- `study_rhythm_target_out_of_range`
- `study_rhythm_allocation_not_found`
- `study_rhythm_allocation_invalid`
- `study_rhythm_allocation_limit_exceeded`
- `study_rhythm_allocation_duplicate`
- `study_rhythm_edit_not_allowed`
- `study_rhythm_plan_not_found`
- `study_rhythm_item_not_found`
- `study_rhythm_summary_failed`
- `study_rhythm_persist_failed`

### S2 note/module

- `study_note_not_found`
- `study_note_invalid_payload`
- `study_note_empty`
- `study_note_invalid_state`
- `study_note_edit_not_allowed`
- `study_note_confirm_required`
- `study_note_confirm_source_required`
- `study_note_confirm_source_invalid`
- `study_note_module_invalid`
- `study_note_module_archived`
- `study_note_module_link_duplicate`
- `study_note_block_not_found`
- `study_note_block_invalid`
- `study_note_block_edit_not_allowed`
- `study_note_source_not_found`
- `study_note_source_invalid`
- `study_note_source_deleted`
- `study_note_source_unavailable`
- `study_note_source_stale`
- `study_note_export_failed`

### AI generation

- `study_note_generation_invalid_request`
- `study_note_generation_not_ready`
- `study_note_generation_empty`
- `study_note_generation_in_progress`
- `study_note_generation_idempotency_mismatch`
- `study_note_generation_stale_source`
- `study_note_generation_schema_invalid`
- `study_note_generation_citation_invalid`
- `study_note_generation_failed`
- `study_note_provider_not_configured`
- `study_note_provider_timeout`
- `study_note_provider_unavailable`
- `study_note_operation_not_found`
- `study_note_operation_stale`

`source_deleted/source_unavailable/source_stale` 表示 source 当前状态；创建/确认路径可将其作为 conflict 返回。普通读取不得为了显示错误而泄露 source text/path。

## 9. API resource 草案

以下只冻结资源边界，9B-6 负责确定最终 method/path/request/response/status：

### S1 resources

- `GET/PUT /api/study/plans/{plan_id}/rhythm`：读取或显式保存一个 plan 的 rhythm settings；不自动创建默认值。
- `GET /api/study/plans/{plan_id}/rhythm/summary`：读取 settings、period buckets、allocation coverage 和 progress summary；只读计算。
- `POST /api/study/plans/{plan_id}/rhythm/allocations`：创建一个 item/date/minutes allocation。
- `PATCH /api/study/plans/{plan_id}/rhythm/allocations/{allocation_id}`：移动或修改未保护 allocation。
- `DELETE /api/study/plans/{plan_id}/rhythm/allocations/{allocation_id}`：删除未保护 allocation；不影响 progress。
- `GET /api/study/plans/{plan_id}/rhythm/export?format=json`：导出受控 rhythm settings、allocations 和 summary；不输出服务器路径或 source 正文。

### S2 resources

- `GET/POST /api/study/notes`：按 project 列表或创建 user draft note；客户端不提交 project_id。
- `GET/PATCH /api/study/notes/{note_id}`：读取或编辑 draft note；confirmed/archived 按 edit protection 拒绝 patch。
- `POST /api/study/notes/{note_id}/confirm|reject|archive`：显式状态转移。
- `POST/PATCH/DELETE /api/study/notes/{note_id}/blocks[/{block_id}]`：draft note 内的 block 操作；顺序由 position 受约束。
- `POST/DELETE /api/study/notes/{note_id}/modules/{module_id}`：note/module 组织关系；不能新关联 archived module。
- `POST/DELETE /api/study/notes/{note_id}/blocks/{block_id}/sources[/{source_link_id}]`：显式创建/移除经过服务端验证的 source link。
- `POST /api/study/notes/generate`：显式 fake-provider `generate_note` draft；使用 `Idempotency-Key`，不覆盖现有 note。
- `POST /api/study/notes/sources/refresh` 或等价显式 refresh resource：重算 source link status，不生成/修改 note content。
- `GET /api/study/notes/{note_id}/export?format=markdown|json`：受控导出 user/AI note、blocks、module IDs/status 和 citation status；unavailable source 不恢复名称、正文或 link。

API 共用规则：

- 所有 scope 由服务端 `AppConfig.project_id` 注入；不接受任意 project/user scope；
- 响应可以返回 note content（它是用户 artifact），但不得返回 stored_path、SQL、secret、raw Provider response、原始异常或未验证 quote；
- source detail 只返回安全材料标识/定位 metadata 和 status，purge 后 material display name 必须为 null 或不返回；
- export 使用安全 content disposition、大小限制和失败后可 retry；不把数据库 raw row 直接作为公开 API contract；
- 真实 Provider、scheduler、worker、cancel、multi-user endpoints 不属于 9B API。

## 10. 导出契约

### 10.1 Note Markdown

Markdown export 包含：note title、note status/provenance、按 position 排列的 block kind/content、module title（若安全可用）和每个 block 的 citation status/opaque identity。它不包含：stored_path、原文件二进制、raw prompt/response、secret、SQL、traceback、purged material name 或 source full text 的隐式复制。

对 `valid` citation，导出可以包含受限且由当前 source contract 返回的 quote/定位；对 `source_deleted`、`source_unavailable`、`stale` 只输出状态和安全 identity，不伪造 quote。导出失败返回稳定 `study_note_export_failed`，不生成部分成功文件。

### 10.2 Note JSON

JSON export 是版本化、受控的 artifact representation，至少包含 `format_version`、note metadata、blocks、module relation metadata、source link status、generation operation safe metadata 和导出时间。不得包含 raw provider data、API key、stored path 或未验证正文 source copy。

### 10.3 Rhythm JSON

Rhythm JSON 只包含 format version、plan safe identity/title、settings、local-date allocations、derived summary 和 source warning count。它不包含材料正文、stored_path、Provider response 或系统内部 SQL。9B 不实现 CSV、ICS、calendar invite 或 scheduler import。

## 11. 测试驱动的验收契约

后续任务必须覆盖以下最小事实，而不是只测试 happy path：

### Gate B：契约

- S1/S2 对象、关系、状态、输入、source/citation、export、error 和 non-goals 无歧义；
- 9A plan/item/progress/module 既有语义没有被覆盖；
- 所有跨行约束标明 domain transaction enforcement。

### S1 domain/API/UI

- daily/weekly、UTC/非 UTC timezone、period boundary、invalid date/timezone、workload limit；
- item split、move、duplicate allocation、unassigned、archived/completed protection；
- progress event 不被 allocation 重复产生；summary 可从事实重算；
- reload、500/retry、narrow/keyboard、安全错误和 JSON export。

### S2 domain/API/UI

- user note 无 source 可创建/确认并保留 provenance warning；AI note 每个 block citation required；
- note/block/module cross-project rejection、duplicate link、module archive boundary；
- draft edit/confirm/reject/archive、confirmed protection、retry 新建不覆盖旧 artifact；
- malformed output、empty retrieval、provider not configured、timeout、伪造 citation、idempotency replay/conflict/failed retry；
- delete/restore/purge/new revision/re-index 的 valid/source_deleted/source_unavailable/stale；
- note Markdown/JSON export、citation unavailable privacy、reload、narrow/keyboard/failure。

### Restore/non-repair

- backup→verify→新空目录 restore 保留 notes/blocks/module links/rhythm allocations/operations/status；
- restore/startup/read/verify 不创建、修复、重排、重新生成或提升 source；
- schema history、`PRAGMA user_version`、integrity/foreign key 和 manifest version 一致。

## 12. Deferred decisions（明确延期）

以下不属于 9B-1 冻结的 9B 最小契约，后续若需要必须单独变更契约并增加测试：

1. custom recurrence、节假日、例外日、提醒、calendar sync、具体时段和 DST 小时级排程；
2. 实际学习时长、session timer、pause/resume timer、自动完成或按时间更新 progress；
3. note revision history、diff、merge、协同编辑和冲突解决；
4. 富文本 HTML、图片/附件、音频、导图、知识图谱和 block 类型扩展；
5. AI 自动创建/修改 knowledge module、AI module suggestion 持久化和自动 re-plan；
6. 真实 Provider generation、流式输出、worker、cancel、后台 stale scan；
7. 人工审核、教师/家长角色、quality gate 和多用户权限；
8. 跨 project note/module/source、共享 artifact 和云同步；
9. CSV/ICS/PDF/Notion 等额外导出格式；
10. 外部 vector DB、自动历史材料 indexing 和规模化容量方案。

## 13. 9B-1 完成结论与准确状态

### 已冻结

- S1 使用已有 Phase 9A plan/item/progress，不创建第二套计划/任务/进度事实源；
- S1 采用 `daily|weekly` cadence、IANA timezone、local-date allocation 和确定性分钟上限；不支持 custom recurrence/scheduler；
- S2 新增 note/note block 语义；knowledge module 保持 9A active/archived 元数据语义，通过独立 many-to-many 组织 link 关联 note；
- citation/source provenance 绑定 note block；user note 可无 source，AI note 必须 citation-safe；
- note 使用 draft/confirmed/rejected/archived；Provider failed 不创建半成品 note，用户 reject 的 AI draft 保留为不可编辑历史；confirmed source 后续 unavailable 时保留内容并显示 warning；
- source lifecycle 映射为 valid/source_deleted/source_unavailable/stale，restore/read/backup/verify 不自动 repair 或提升状态；
- operation、idempotency、provider raw data、导出、project scope、隐私和 backup/restore non-repair 边界；
- S3/S4/S5、S6/S7、Phase 10 和真实 Provider acceptance 明确排除。

### 准确状态措辞

> Phase 9B-1 已完成 `planned/contract-frozen`：S1/S2 的实体关系、cadence/timezone/workload、note/block/module/citation 关系、状态转移、不变量、source lifecycle、AI fake-provider draft、错误码、API resource、导出和 backup/restore non-repair 边界已冻结。尚未实现 Phase 9B schema、repository、API、UI 或正式用户路径；不代表 Phase 9B completed 或 real-pass。

下一任务：

```text
9B-2：Migration 与 schema
```

9B-2 必须依据本文实现连续 v10（或当前源码确认的下一版本）migration，并在发现契约无法安全表达时先提出契约修订，不得隐式改写本文语义。
