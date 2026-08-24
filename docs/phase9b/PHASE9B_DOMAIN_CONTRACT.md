# Phase 9B 资料学习工作流：审计、正式领域契约与状态机

> 状态：9B-0 `planned/audit-draft`；9B-1 `planned/contract-frozen`；9B-2、9B-3、9B-4、9B-5、9B-6 `implemented/backend-pass`。
>
> 审计基线：2026-08-30；9B-2 前的稳定实现基线为 schema **v9**、Phase 9A closeout。当前 schema 为 **v10**：9B-2 加入 persistence schema，9B-3 完成共用 repository/domain transaction，9B-4 完成 S2 deterministic fake-provider note draft workflow，9B-5 完成 S1 同步节奏 settings/allocation/summary workflow，9B-6 完成 S1/S2 最小安全 API。9B 的 UI、browser-pass、restore artifact acceptance 与正式用户路径仍未实现。
>
> 本文冻结 S1 学习节奏和 S2 资料笔记的语义，供 9B-2 至 9B-9 实现和验收使用。它不是完整功能证据；不得因本文出现表名、路径或错误码而宣称任何未通过后续 gate 的 Phase 9B 功能已经存在。

## 1. 审计基线与已验证复用能力

### 1.1 当前基线

- 当前源码的 `backend/app/migrations/runner.py:CURRENT_SCHEMA_VERSION` 是 **10**；v1–v10 连续注册在 `_MIGRATIONS`，`migrate()` 在 `BEGIN IMMEDIATE` 内处理 DDL、history 和 `PRAGMA user_version`，失败 rollback。
- v9 是已完成 Phase 9A 的 schema 基线；v10 `phase9b_material_learning_schema` 加入 note/block/module-link/source-tombstone 与 rhythm persistence schema。9B-3 在 repository/domain 层实现这些 records 的事务操作与显式 source refresh；9B-4 增加单材料 deterministic fake-provider note draft workflow，并在最终写入前重验 retrieval/context/citation/source identity；9B-5 对 S1 实现 explicit daily/weekly IANA-timezone settings、allocation 保护和确定性 summary。它不包含 HTTP routes、UI、export 或 restore artifact acceptance。
- `materials`、`extractions`、`text_spans` 是资料正文的 source of truth；`material_revisions`、`chunks`、retrieval/context/citation、AI artifact、9A plan 与本 Phase 的 note/rhythm 都是派生数据或用户状态。
- 当前部署范围是单进程、单实例、SQLite、本地 data root 与 `project_id` scope；没有 `user_id`、认证、授权、协作或多进程共享 data root。
- 审计期间曾存在未提交 v10 `notes`/`rhythm_*` 候选 migration，但其索引引用不存在列而失败；该候选已回退。现行 v10 由本冻结契约重新实现，不复用候选 DDL。

**验证记录：** 回退后的 v9/9A baseline 为 migration `9 passed`、9A focused `18 passed`、full backend `272 passed, 2 skipped`、Phase 9A Chromium `3 passed`。9B-2 的 migration/backup/governance 与 full-backend 结果以本任务实际命令为准；这些结果只证明 schema gate，不证明后续 9B 用户能力。

### 1.2 已有能力与 9B 的复用规则

| 已验证能力 | 9B 必须复用 | 不能误作的推断 | 证据 |
|---|---|---|---|
| revision → chunk → retrieval → context → citation | S2 generation 只能从显式 active material scope 的 current ready chunks 检索、组装 context 并服务端复验 citation | 客户端、模型或用户文本不能自造 valid citation | `repository.py:index_material_revision()`, `run_*_retrieval()`, `assemble_context()`, `validate_citation_key()`；`test_context_assembler.py` |
| active/deleted/restored/purged lifecycle | source status 由 material/revision/chunk identity 重算；purge 后不得恢复名称、正文或可点击定位 | read/startup/restore 不会自动恢复有效来源 | `repository.py:soft_delete_material()`, `restore_material()`, `purge_material()`；`test_phase9a_source_lifecycle.py` |
| 9A plan/item/progress | S1 parent 是已有 plan/item；状态改变仍只由已有 append-only progress events 完成 | allocation 不是 task、不是 session、不是实际耗时、不能写 progress event | `repository.py:create_study_plan_item()`, `append_study_progress_event()`, `study_progress_summary()`；`test_phase9a_domain.py` |
| 9A knowledge module/source link | module 是 project-scoped active/archived 主题元数据；可作为 S2 note 的组织对象 | module 不是笔记正文、不是 note revision、不是 AI confirmed fact；不可把 module source link 改成多态 owner | `repository.py:create_knowledge_module()`, `create_module_source_link()`；`test_phase9a_domain.py:test_module_archive_keeps_existing_plan_reference_but_blocks_new_reference` |
| Phase 8 draft generation | AI 内容先 draft；失败操作与 artifact 分离；citation 在最终持久化前重验；不覆盖用户编辑或 confirmed artifact | 不可复用 card/exercise 表或直接调用其 artifact persistence 写 note | `repository.py:create_generation_operation()`, `persist_generated_draft()`；`test_phase8_generation.py` |
| backup/restore | 新 SQLite 业务表会进入 SQLite Online Backup snapshot；verify/restore/startup/read 不调用 provider/rebuild | “天然进入 DB snapshot”不等于已通过 9B restore gate | `backup.py:backup_data()`, `restore_backup()`；`restore_acceptance.py:_study_checks()`；`test_phase9a_backup_restore.py` |

## 2. Phase 9B 范围与不变量

### 2.1 两条正式用户路径

```text
S1 学习节奏
9A plan/item/progress
  → 用户显式配置 rhythm
  → 用户为 item 指定 local-date / planned minutes
  → 读取确定性 timeline / load / coverage summary
  → 用户手动移动、修改或删除仍可编辑的 allocation
  → progress 仍由 9A event 写入，summary 读取时重算

S2 资料笔记
active material → current revision → ready chunk → retrieval/context/citation
  → 用户创建 user note，或显式 fake-provider generate_note
  → draft note / ordered blocks / block-level source links
  → 用户编辑、关联已有 module、确认、拒绝或归档
  → source lifecycle 显式刷新；历史内容保留，status/warning 变化
```

### 2.2 全局不变量

1. 所有 scope 由服务端 `AppConfig.project_id` 注入；客户端不得传入任意 `project_id` 或未来 `user_id`。
2. 原始资料与 extraction 正文不被 note、module、rhythm、AI output 或导出反向覆盖。
3. 用户 note、用户编辑、confirmed note、9A progress event 和 completed item 不得被 AI generation、source refresh、backup/restore 或普通 read 静默改写。
4. source deleted/stale/unavailable 时不得伪造 source text、material name、stored path、quote 或可定位 citation。
5. 所有审计时间由服务端生成 timezone-aware UTC ISO-8601；S1 的 business date 是明确 timezone 下的 date-only 值，不能使用宿主机隐式 timezone。
6. 所有新增表、字段、索引与约束只能在 9B-2 的连续 migration 中加入；不得在 repository/API/startup 中 ad-hoc 建表。
7. Phase 9B 只有 deterministic fake-provider/local single-process/SQLite/Chromium/backup-restore 的目标范围；真实 Provider acceptance、worker 和 production-scale 不是本契约的完成条件。

### 2.3 明确不做

- S3/S4/S5 限时练习、错题、冲刺；S6/S7 家长报告、课堂采集、OCR、ASR；
- reminder、push、calendar sync、recurrence engine、scheduler、自动执行、自动重排、overdue automation、session timer、实际学习时长；
- real-provider generation acceptance、streaming、queue、worker、cancel、后台 stale scan、跨进程协调；
- 多用户、认证授权、云同步、协作、跨 project artifact、外部 vector DB；
- note revision/diff/merge、富文本 HTML、脚本、图片/附件/音频、导图或知识图谱；
- AI 自动创建/修改/archive `knowledge_modules`、自动重规划或将 AI output 直接当 confirmed knowledge。

## 3. 正式术语与关系

### 3.1 Glossary

| 术语 | 冻结定义 | 类型 |
|---|---|---|
| Rhythm | 一个既有 study plan 的显式节奏配置，定义 cadence、timezone、period anchor 与每 period target；不是 scheduler | S1 user schedule state |
| Rhythm Allocation | 既有 plan item 在一个 local date 的 planned minutes 安排事实 | S1 user schedule state |
| Rhythm Summary | 从 settings、allocations、当前 item projection、progress events 与 9A source warnings 重算的只读响应 | derived response |
| Local Date | 由 rhythm IANA timezone 解释的严格 `YYYY-MM-DD`；不含时间/offset | business coordinate |
| Note | project 内的资料笔记容器，具 title、provenance、lifecycle 和 user-edit protection | S2 user/AI artifact |
| Note Block | note 内有序、最小的文本内容单元；citation provenance 绑定到 block | S2 content artifact |
| User Note | `provenance=user_created` 的 note；可没有资料来源，但不得展示为已验证资料结论 | user artifact |
| AI Note Draft | `provenance=ai_generated` 且 `status=draft` 的 note；每一个 block 必须有创建时验证为 valid 的 citation link | proposed AI artifact |
| Knowledge Module | 9A 已有的 active/archived 主题元数据；S2 只使用它组织 note | reusable 9A metadata |
| Note–Module Link | note 与同 project module 的组织关系；不是 source provenance | organization relation |
| Note Block Source Link | block 到 material/revision/extraction/chunk/span/citation identity 的服务端验证 provenance record | provenance relation |
| Source Tombstone | material purge 后保留在 note link 的 opaque identity 和 `source_unavailable` status；不含可恢复名称/正文/路径 | lifecycle history |

### 3.2 实体关系

```text
project
├── learning_goals / knowledge_modules                    [9A]
│     └── note_module_links                               [9B, organization only]
├── study_plans → study_plan_items → study_progress_events [9A]
│     ├── rhythm_settings                                 [9B, max one per plan]
│     └── rhythm_allocations                              [9B, item/local-date schedule facts]
└── notes                                                 [9B]
      └── note_blocks                                     [9B, ordered]
            └── note_block_source_links                  [9B, verified provenance]

materials → extractions → text_spans                      [source of truth]
          → material_revisions → chunks → retrieval/context/citation
                                                              [evidence path]
```

冻结关系：

1. 一个 rhythm 只属于一个同 project 的既有 plan；一个 plan 最多一条 rhythm settings。S1 不创建 plan、item 或 progress 的平行事实源。
2. allocation 同时属于一个 plan 与该 plan 的一个 item；它不能指向其它 plan/project item。
3. note 属于一个 project；note 可关联零至多个同 project module，module 可关联零至多个 note。note 与 module 都可以独立存在。
4. note 至少有一个 block；block 只属于一个 note，且在该 note 内 position 唯一。
5. 一个 block 可有零至多个 source links；同一 block/citation identity 不重复。不同 block 可以引用相同 chunk。
6. note 可以通过不同 block links 关联多个 materials/revisions；不得用 note 级单一 `material_id` 伪造多来源 provenance。
7. 9A `module_source_links`、`plan_item_source_links` 不迁移为多态 owner，不自动复制到 note，也不自动成为 note evidence。

## 4. S1 学习节奏契约

### 4.1 Parent 与既有 9A 状态的关系

- rhythm parent 必须为同 project 的 9A plan；allocation item 必须属于该 parent plan。
- settings/allocation **不改变** plan status、item status、dependency 或 progress event；用户仍通过现有 `started`、`completed`、`skipped`、`reopened` progress event 改变 item projection。
- S1 允许 plan item 没有 rhythm allocation；无 allocation 不是错误，也不创建默认值。
- draft、confirmed、active、paused plan 可创建/更新 rhythm settings 与对符合条件 item 的 allocation。该授权只扩展新的 rhythm rows，不放宽 9A 对 plan/item title、description、position、module/dependency 的编辑保护。
- completed 或 archived plan 的 rhythm settings 与 allocation 都只读；不允许新建、更新或删除。
- pending、in_progress、skipped item 的 allocation 可编辑；completed 或 archived item 的 allocation 只读并保留为历史。9A `reopened` event 将 item projection 改回 `in_progress` 后，该 item allocation 再次可编辑。
- item 被 9A archive 前，若已有 progress event，9A 既有 archive protection仍有效；S1 不改变它。已 archive item 的既有 allocation 历史保留但不计入 current load/coverage。

### 4.2 Rhythm settings 字段/枚举草案

9B-2 必须实现语义等价的结构；列名可调整但不得改变以下规则。

| 字段 | 冻结语义 |
|---|---|
| `id` | 稳定 `rhythm_...` ID |
| `project_id`, `plan_id` | 服务端 scope；plan 必须同 project；`plan_id` 唯一 |
| `cadence` | 仅 `daily` 或 `weekly` |
| `timezone` | 必填、可被 Python `zoneinfo.ZoneInfo` 加载的 IANA name；`UTC` 合法，`CST`/`GMT+8` 等缩写非法 |
| `period_start` | 必填严格 `YYYY-MM-DD` local date；是固定 anchor，不是 UTC midnight timestamp |
| `target_minutes` | 每一个 cadence period 的用户目标整数，`0..10080`；`0` 表示没有 target、仍允许 allocation |
| timestamps | `created_at` / `updated_at`，服务端 UTC ISO-8601 |

Cadence：

- `daily` 的 period 为一个 local date；每个 local day target 为 `target_minutes`。
- `weekly` 的 period 从 `period_start` 起每连续七个 local dates 构成；不强制周一，避免宿主 locale/ISO week 隐式规则。
- 不支持 custom recurrence、例外日、节假日、具体时段、calendar event 或 hour-level DST 排程。
- timezone 只用于 local date 分桶；S1 不保存一天内时刻，DST 不会隐式增减 planned minutes 或触发重排。

### 4.3 Allocation 字段/输入草案

| 字段 | 冻结语义 |
|---|---|
| `id` | 稳定 `rhythm_allocation_...` ID |
| `project_id`, `plan_id`, `item_id` | 服务端验证同 project、同 plan 的 parent/item 关系 |
| `local_date` | 严格 `YYYY-MM-DD`，按 settings timezone 解释；不接受 datetime、offset、timestamp 或自然语言 |
| `planned_minutes` | 正整数 `1..1440`；是计划投入，不是实际完成分钟数 |
| timestamps | 服务端 UTC ISO-8601 |

约束：

1. `(item_id, local_date)` 唯一；同 item 同日重复 create 必须以稳定 duplicate/conflict 拒绝，不能隐式累加。显式同 allocation ID 的 retry/idempotent replay 由 API/domain 任务冻结具体 HTTP 表达。
2. 一个 item 可分配到多个 local dates；一个 local date 可安排多个 items。
3. 单 item 的 all-time allocation 总和最多 `10080` minutes；任一 current rhythm period 的 allocation 总和最多 `10080` minutes。超过上限拒绝，不截断、拆分或自动移动。
4. 移动是对一个既有 allocation 的日期和/或分钟受限更新，必须在一个 domain transaction 内维护 uniqueness 和总量上限；不写 progress event。
5. 删除只允许可编辑 allocation；删除 completed/archived item 的 allocation 或 completed/archived plan 内任一 allocation 均拒绝。
6. allocation 不会因日期经过而产生 overdue、started、completed、skipped 或实际耗时。跳过/完成/重开仅是既有 9A progress API 的显式用户操作。

### 4.4 S1 state/operation 表

| 对象/当前状态 | 允许操作 | 禁止或不发生 |
|---|---|---|
| no settings | 用户显式 create/update settings | 自动默认 rhythm、scheduler |
| settings on draft/confirmed/active/paused plan | update cadence/timezone/period_start/target；读取 summary | 修改 parent plan status/item/progress |
| settings on completed/archived plan | read/export | write/delete settings 或 allocations |
| allocation on pending/in_progress/skipped item | create/update/move/delete | 自动 progress、跨 plan/item 关联 |
| allocation on completed/archived item | history read/export | create/update/delete |
| 9A item completed/skipped | 保留 allocation；summary 反映当前 projection | 删除 progress history、将 planned minutes说成完成时间 |
| 9A item reopened | 既有 allocation 保留且可再编辑 | 重写旧 progress event |

更新 settings 不改写旧 allocations。读取 summary 时以**新** timezone/anchor/cadence 分桶；不自动迁移 date。若 allocation 不落入请求的 period window，它只是该 window 外的历史/未来 allocation，不是要被系统修复的数据。

### 4.5 Rhythm summary

`rhythm_summary` 是实时只读派生响应，不保存 snapshot。它至少返回：

- settings（cadence/timezone/period_start/target_minutes）或明确 `rhythm_not_configured` 空语义；
- requested/current period buckets 的 local-date range、planned_minutes、target_minutes、`remaining_target_minutes=max(target-planned,0)`；
- `allocated_item_count`、`unassigned_item_count`、`archived_item_count`；
- 当前 item projection 的 pending/in_progress/completed/skipped counts；
- 9A source links 派生的 `source_warning_count`；
- `last_progress_event_at`。

计算规则：

1. 仅以 allocation 的 `local_date` 和 settings timezone/anchor 分桶，不以 server local timezone 或 UTC date 重解释。
2. `unassigned_item_count` 为同 plan、非 archived、没有任一 allocation 的 item 数；completed item可计入历史 allocated count，但不能被称为未完成 minutes。
3. archived item allocation 从 current load/coverage 排除，detail/history 可受限显示。
4. progress 状态来自 9A current item projection；planned minutes 从不替代 actual/completed minutes。
5. summary read 必须在一致的 project/plan scope 中计算；不得写 summary table、不得创建 settings、allocation 或 progress。
6. active plan 有 deleted/stale/unavailable source 仍可读/编辑 rhythm，summary 仅给 warning；source warning 不会阻止计划使用。

## 5. S2 资料笔记与知识模块契约

### 5.1 Note 字段/枚举草案

| 字段 | 冻结语义 |
|---|---|
| `id` | 稳定 `note_...` ID |
| `project_id` | 服务端注入，note/module/source 均必须同 project |
| `title` | trim 后 `1..400` Unicode characters |
| `status` | `draft`、`confirmed`、`rejected`、`archived` |
| `provenance` | `user_created` 或 `ai_generated`，创建后不可变 |
| `user_edited` | 0/1；用户修改 note title、block content/order、block source relation 或 module relation 后置 1 |
| `generation_operation_id` | ai_generated note 可选的 operation reference；user_created 必须为空 |
| timestamps | `created_at`、`updated_at`、`confirmed_at`、`archived_at`；服务端 UTC ISO-8601 |

规则：

1. user-created note 创建时为 `draft + user_created`，可无 source；界面/API 必须明确它是用户笔记，不能将无来源文本呈现为已验证资料结论。
2. AI note 只能由成功 `generate_note` operation 原子创建为 `draft + ai_generated`；每个生成 block 必须至少一条创建时 `valid` 的 source link。
3. note 没有物理 delete；所有 note 最终可 archive。`rejected` 是 AI draft 的只读历史状态，不是 deletion。
4. 每个 note 始终至少一个非空 block；空 note、空 block、只空白 content 的创建、保存、确认均拒绝。
5. source status 不占用 note status：confirmed note 后来源变 stale/deleted/unavailable 时 note 仍 confirmed，detail 返回 links/warning。

### 5.2 Note block 字段/编辑规则

| 字段 | 冻结语义 |
|---|---|
| `id`, `note_id`, `project_id` | 稳定 ID 与同 project/note ownership |
| `position` | 非负整数、同 note 唯一；稳定排序 |
| `block_kind` | 仅 `text`、`heading`、`bullet` |
| `content` | 必填 UTF-8 text，trim 后非空，最大 `12000` characters；整个 note 所有 blocks 合计最多 `48000` characters |
| `provenance` | `user_created` 或 `ai_generated`；AI block 不可伪装为 user block |
| timestamps | 服务端 UTC ISO-8601 |

- Phase 9B 不保存 HTML、script、image、attachment 或 rich-text AST；UI 以纯文本安全渲染。
- draft note 内可增加、编辑、删除和重排 blocks，但必须保留至少一个 block，所有更新在一个 transaction 内保持 position/size invariant。
- confirmed、rejected、archived note 的 blocks 均只读。用户要改 confirmed content，必须创建一条新的 user note；9B 不提供隐式 revision/reopen。
- 用户编辑 AI draft 后，note `user_edited=1`；不会改写 block/note provenance、operation history 或原有 valid provenance link。

### 5.3 Note–module 组织关系

- `knowledge_modules` 保持 9A 的 `active|archived` lifecycle，不新增 module draft/confirmed/stale 状态。
- note-module link 只能连接同 project 的 note 与 module；同 pair 唯一；link 仅表达组织关系，不复制 module source links。
- draft note 可新增/移除 active module link。新建 archived module link 拒绝。
- confirmed/rejected/archived note 的 module links 只读；module 后续 archive 时既有 link 保留，并在 note detail 返回 archived-module warning。
- `generate_note` 不得自动 create/update/archive module，不得生成“confirmed module”。用户必须显式创建/选择 module 再组织 note。

### 5.4 Note block source link

9B-2 应新增独立 note block source link 结构；禁止改造 9A link 成为多态表。最小语义：

```text
id, project_id, note_id, note_block_id,
material_id, revision_id, extraction_id, chunk_id, span_id,
citation_key, status, created_at, updated_at
```

字段规则：

1. `note_id` / `note_block_id` 的 ownership、同 project relation 由 FK/domain transaction 强制。
2. `material_id` 等 source identity 应保留为 opaque TEXT identity，**不对 material/revision/extraction/chunk 建会在 purge 时清空 identity 的 FK**。这是保留 `source_unavailable` tombstone 的刻意选择；其 valid relation 必须由 domain 逐次验证。
3. 不保存 `stored_path`、原始二进制、source full text、未验证 quote 或 material display name。note block content 是 user/AI artifact，不是 source copy。
4. 创建 link 的 citation key 必须来自本次 `assemble_context()` / retrieval result，且经 `validate_citation_key()` 与 source identity 二次验证；客户端的 status 一律忽略/拒绝。
5. 同一 `(note_block_id, citation_key)` 不重复；citation key 不存在、跨 project、跨 current revision、chunk/span不一致均拒绝且不落库。
6. user note block 可有零 links；ai-generated note 每个 block 必须至少一 valid link，且确认时必须再次满足该条件。
7. link status 只能由服务端计算为 `valid`、`source_deleted`、`source_unavailable` 或 `stale`；不是客户端可写 note state。

### 5.5 S2 状态机

```text
user-created:
  absent → draft → confirmed → archived
                 └────────────→ archived

ai-generated:
  operation running → draft → confirmed → archived
                          ├──→ rejected → archived
                          └──→ archived
provider/retrieval/validation failure before persistence:
  operation failed; no note/block/source-link artifact
```

| Current note | Allowed action | Result / protection |
|---|---|---|
| user draft | edit blocks/title, link active module, add/remove source link, confirm, archive | any user edit sets `user_edited=1` |
| AI draft | same draft edits, confirm, reject, archive | original provenance/operation retained; edits never change it to user-created |
| confirmed | archive, read/export | no ordinary patch, reject, reopen or regeneration overwrite |
| rejected AI draft | read/export, archive | no edit/confirm/retry-in-place; retry creates new draft |
| archived | read/export | terminal; no restore/reopen in 9B |

Confirm rules:

- user draft: nonempty title and at least one nonempty block; source is optional, but source-free display/export retains user-created/provenance warning.
- AI draft: every block has at least one **currently valid** source link; stale/deleted/unavailable/missing required link rejects confirm.
- Confirm is explicit and idempotent only if already confirmed state is not being silently re-applied; API must return stable invalid-state semantics rather than create another transition/history.
- A later source lifecycle degradation does not revert confirmed/rejected/archived note status or erase user/AI content; it only adds warning/status to links.

## 6. S2 fake-provider generation contract

### 6.1 Scope and operation

- New `ai_operations.operation_type` is `generate_note`; it requires note-specific persistence, not Phase 8 card/exercise persistence reuse.
- Only deterministic fake provider belongs to Phase 9B acceptance. A configured real network provider is not sufficient evidence and must not be claimed as 9B real-pass.
- One generation request has exactly **one active, same-project, explicitly indexed material**. This deliberately matches the already tested Phase 8 generation scope. Multi-material generation is deferred; manually authored notes can cite multiple materials through blocks.
- Request includes topic, material ID, optional explicit current source revision, retrieval mode, fallback policy and an optional `Idempotency-Key`; it never accepts project ID, source status, stored path, provider metadata or raw prompt.
- The operation records safe project/material/source-revision/retrieval-policy/prompt-version/provider-model/request/usage/latency/status/error/output-note metadata. It must not persist raw prompt, raw provider response, API key or source full text beyond note block artifact content.

### 6.2 Structured output and transaction boundary

The provider output is only an in-memory structured payload:

```text
{ title, blocks: [{ block_kind, content, citation_keys: [...] }] }
```

- Reject unknown fields, missing/empty blocks, invalid block kind, oversized title/content, forged/duplicate citation, citation absent from current context, or citation whose validated revision differs from request source revision.
- Do not hold a SQLite long write transaction during provider I/O: create running operation and retrieval metadata then commit; call provider; then revalidate source/citations and atomically write note + blocks + links + succeeded operation in a second transaction.
- Provider not configured, retrieval not ready/empty, timeout/unavailable, malformed output, stale source, citation mismatch or persistence failure must leave **no** partial note/block/link. A failed operation with stable safe error is retained.

### 6.3 Idempotency and retry

| Existing same project Idempotency-Key | Required behavior |
|---|---|
| same fingerprint, succeeded `generate_note` | replay the same persisted note response; no provider I/O or duplicate artifact |
| same fingerprint, running | conflict/in-progress; no second operation |
| same fingerprint, failed/stale | explicit retry clears/releases old key and creates a new operation/new draft; no overwrite |
| different fingerprint | idempotency mismatch conflict |
| no key | request is not automatically deduplicated |

A retry always creates a new AI draft and new operation. It never replaces a user-edited, confirmed, rejected or archived note.

## 7. Source lifecycle mapping

### 7.1 Canonical link status

| Actual source condition | note block link status | New AI confirm / safe location |
|---|---|---|
| active material; stored identity matches current revision, ready chunk, extraction/span and validated citation | `valid` | permitted |
| material soft-deleted | `source_deleted` | prohibited |
| material purged or source identity no longer exists | `source_unavailable` | prohibited |
| active material but non-current revision, missing/not-ready/stale chunk, identity/span/citation mismatch | `stale` | prohibited |
| client sends nonexistent/forged/cross-project relation at create | reject; no row | prohibited |

### 7.2 Lifecycle operations

| Event | Required outcome |
|---|---|
| material delete | relevant note links become `source_deleted`; note/module/rhythm/progress/user content remains |
| material restore | restores material only; note link must **not** auto-promote. Explicit note-source refresh may become `valid` only after full identity/current/ready validation |
| material purge | preserve note, blocks, module links, operation and opaque source identities; links become `source_unavailable`; never return material name, quote, full text/path or click target |
| new extraction/current revision | old link becomes `stale`; no automatic rewrite to new revision |
| chunk re-index | old missing/non-ready/mismatched identity becomes `stale`; explicit user relink or new generated draft is required |
| module archive | existing note-module link remains with warning; no new association to archived module |
| read/startup/backup/verify/restore | no refresh, repair, relink, re-index, generation, status promotion, default rhythm creation or progress write |

Implementation rule: delete/purge paths may eagerly downgrade links inside their material lifecycle transaction; restore never eagerly promotes. The explicit refresh operation is the only positive revalidation path. It must not change note block content, module relation, note status, allocation or progress event.

### 7.3 Active objects with unavailable source

- active/paused 9A plan and S1 rhythm remain readable and manually editable with source warnings; source unavailable does not block existing plan/progress history.
- confirmed user or AI note remains readable/exportable after later source degradation; source warning is visible and status is not silently changed.
- a new AI note draft cannot be confirmed with non-valid required source. A user note may be source-free but must retain its provenance warning.
- source unavailable never blocks app startup, ordinary note read, plan read, backup/restore or verify; it only restricts new citation-dependent create/confirm/relink operations.

## 8. Database and domain-transaction responsibilities

### 8.1 9B-2 schema must express

- note/block/status/provenance/block-kind/cadence/link-status CHECK constraints;
- note/block/module/plan/item/project ownership FKs where deletion must delete the owned user artifact safely;
- `rhythm_settings.plan_id` unique; `note_module_links(note_id,module_id)` unique; `note_blocks(note_id,position)` unique; `rhythm_allocations(item_id,local_date)` unique; `note_block_source_links(note_block_id,citation_key)` unique;
- nonnegative position, positive planned minutes, basic required fields and appropriate read indexes;
- note source tombstone identity fields as non-FK opaque text, as specified in §5.4;
- any `generation_operation_id` FK that does not erase note provenance when operation history is retained.

SQLite CHECK/FK cannot prove current revision, same-project external identities, all allocation totals, note nonempty aggregate, item ownership, source lifecycle, or DAG semantics; migrations must not pretend otherwise.

### 8.2 9B-3 domain transactions must enforce

1. plan/item/rhythm settings/allocation same-project/same-plan relation and state protection;
2. strict timezone/date parsing, cadence enum, workload bounds and aggregate item/period limits;
3. deterministic summary grouping, unassigned/archived exclusion and progress linkage without writing events;
4. note/block/module same-project ownership, position/content aggregate and at-least-one-block invariant;
5. note transition/provenance/user-edit protection and terminal state behavior;
6. active module association validation and archived-module historical warning;
7. active/current/ready revision/chunk/span/citation identity validation and opaque unavailable tombstone preservation;
8. explicit refresh without stale/unavailable promotion except after verified restored identity;
9. fake-provider output validation, operation idempotency, retry, no long write transaction and atomic draft persistence;
10. export privacy/size/failure contract; and
11. rollback of every multi-row write so no half note, block, link, allocation, summary snapshot or erroneous progress projection remains.

## 9. API resource and export draft

This section freezes resource boundaries, not final HTTP method/status/Pydantic naming. 9B-6 must follow existing 400/404/409/500 safe error conventions and must not expose raw SQLite/provider exception details.

### 9.1 S1 resources

- `GET/PUT /api/study/plans/{plan_id}/rhythm`: explicit read/save settings; GET when absent returns frozen not-configured semantics and never creates default.
- `GET /api/study/plans/{plan_id}/rhythm/summary`: read-only settings/buckets/coverage/progress/source warning summary.
- `POST /api/study/plans/{plan_id}/rhythm/allocations`
- `PATCH|DELETE /api/study/plans/{plan_id}/rhythm/allocations/{allocation_id}`
- `GET /api/study/plans/{plan_id}/rhythm/export?format=json`

### 9.2 S2 resources

- `GET|POST /api/study/notes`: list/create user draft, server-injected project scope.
- `GET|PATCH /api/study/notes/{note_id}`: draft-only edit.
- `POST /api/study/notes/{note_id}/confirm|reject|archive`
- `POST|PATCH|DELETE /api/study/notes/{note_id}/blocks[/{block_id}]`
- `POST|DELETE /api/study/notes/{note_id}/modules/{module_id}`
- `POST|DELETE /api/study/notes/{note_id}/blocks/{block_id}/sources[/{source_link_id}]`
- `POST /api/study/notes/generate`: deterministic fake-provider `generate_note`, explicit `Idempotency-Key`, no overwrite.
- `POST /api/study/notes/sources/refresh` or equivalent explicit refresh resource.
- `GET /api/study/notes/{note_id}/export?format=markdown|json`

### 9.3 Controlled exports

- **Note Markdown:** title/status/provenance, ordered block kind/content, safe module metadata, opaque citation identity and source status. Valid citation can include only source detail already safely returned by current source contract. Non-valid source outputs status/opaque identity only.
- **Note JSON:** versioned `format_version`, note/block/module/link safe representation, safe generation operation metadata and export time. No raw provider data/secret/path/SQL/traceback/source full-text copy.
- **Rhythm JSON:** versioned settings, plan safe identity/title, local-date allocations, derived summary/source warning. No source body/path/provider response. No CSV/ICS/calendar import in 9B.
- All exports use the existing safe download/content-disposition and bounded-size pattern. A failure returns one stable error and no partial file.

## 10. Stable error semantic set

9B-6 assigns HTTP statuses but must retain these semantic distinctions and never return raw exception strings.

| Area | Stable codes |
|---|---|
| rhythm | `study_rhythm_not_found`, `study_rhythm_not_configured`, `study_rhythm_invalid_payload`, `study_rhythm_invalid_cadence`, `study_rhythm_invalid_timezone`, `study_rhythm_invalid_date`, `study_rhythm_target_out_of_range`, `study_rhythm_allocation_not_found`, `study_rhythm_allocation_duplicate`, `study_rhythm_allocation_limit_exceeded`, `study_rhythm_edit_not_allowed`, `study_rhythm_plan_not_found`, `study_rhythm_item_not_found`, `study_rhythm_summary_failed`, `study_rhythm_persist_failed` |
| note/block/module | `study_note_not_found`, `study_note_invalid_payload`, `study_note_empty`, `study_note_invalid_state`, `study_note_edit_not_allowed`, `study_note_confirm_source_required`, `study_note_confirm_source_invalid`, `study_note_module_invalid`, `study_note_module_archived`, `study_note_module_link_duplicate`, `study_note_block_not_found`, `study_note_block_invalid`, `study_note_block_edit_not_allowed`, `study_note_source_not_found`, `study_note_source_invalid`, `study_note_source_deleted`, `study_note_source_unavailable`, `study_note_source_stale`, `study_note_export_failed` |
| generation | `study_note_generation_invalid_request`, `study_note_generation_not_ready`, `study_note_generation_empty`, `study_note_generation_in_progress`, `study_note_generation_idempotency_mismatch`, `study_note_generation_stale_source`, `study_note_generation_schema_invalid`, `study_note_generation_citation_invalid`, `study_note_generation_failed`, `study_note_provider_not_configured`, `study_note_provider_timeout`, `study_note_provider_unavailable`, `study_note_operation_not_found`, `study_note_operation_stale` |

`source_deleted` / `source_unavailable` / `source_stale` are source facts, not permission to expose source data. Read responses can show safe status; create/confirm/relink may use their corresponding conflict semantics.

## 11. Backup/restore non-repair contract

Backup, verify, restore, startup and ordinary reads must preserve schema version/history and all 9B records/states, including draft/confirmed/rejected/archived notes, blocks, module links, source tombstones, rhythm settings/allocations and generation operation status.

They must not:

- create default rhythm/note/block/link/progress/operation;
- call provider, retrieve, re-index/rebuild FTS/embedding, reorder blocks/allocations, relink source or regenerate note;
- promote `stale`, `source_deleted` or `source_unavailable` to `valid`;
- overwrite a live data root; restore remains only to a nonexistent/empty target under existing operator contract;
- leak data root/stored path/secret/raw exception/raw provider output/full source text in manifest, logs or responses.

9B-8 must extend restore acceptance rather than assuming the general SQLite snapshot is enough.

## 12. Deferred decisions

The following are explicitly outside this frozen minimum. They require a future contract change plus tests, not an implementation shortcut:

1. custom recurrence, holiday/exception days, reminders, calendar sync, scheduled clock time and DST hour-level allocation;
2. actual time tracking, timer pause/resume, automatic completion or automatic replan;
3. note revisions, diff, merge, collaboration, conflicts or restoring archived/rejected notes;
4. rich media/rich text, file attachments, graph/knowledge-map features;
5. AI module suggestions or automatic module/plan changes;
6. multi-material generation, real-provider note acceptance, streaming, worker/cancel/background stale scanning;
7. teacher/parent approval, human review, roles/permissions, multi-user and cross-project sharing;
8. CSV/ICS/PDF/Notion or other export formats;
9. external vector database, automatic historical indexing or scale/capacity claims.

## 13. Gate B acceptance and next task

Gate B is satisfied by this document only when downstream reviewers can determine without guessing:

- S1 object ownership, cadence, timezone/date, workload, allocation protection and summary calculation;
- S2 note/block/module/provenance/source-link ownership and state transitions;
- AI draft/operation/retry/failure boundaries; source lifecycle and tombstone behavior;
- schema vs domain-transaction responsibilities; API/export/privacy/non-repair limits; and
- explicit Phase 9C/9D/10 non-goals.

**Accurate status:**

> Phase 9B-1 remains `planned/contract-frozen`: S1/S2 entity relations, cadence/timezone/workload rules, note/block/module/citation provenance, state transitions, invariants, fake-provider draft semantics, lifecycle mapping, API/export draft and backup/restore non-repair boundaries are frozen. 9B-2 through 9B-6 are `implemented/backend-pass`: v10 persistence, shared domain transactions, the S2 deterministic fake-provider note draft workflow, the S1 explicit synchronous rhythm workflow and the minimal safe S1/S2 API have focused tests. S1 uses daily/weekly IANA-timezone settings and local-date workload allocation, deterministic load/progress/source-warning summary, completed/terminal protection and rollback/SQLite-lock retry; it does not write progress, auto-replan or schedule work. The API injects server project scope, maps safe 400/404/409/500 errors, bounds exports, validates citations server-side, and preserves provider/source failure privacy. UI/browser-pass, restore artifact acceptance and a formal user path remain unimplemented; this is not Phase 9B completed or real-pass.

Next task: **9B-7 Chromium workspace**. It must use the API contract without expanding scheduler, worker or restore scope.
