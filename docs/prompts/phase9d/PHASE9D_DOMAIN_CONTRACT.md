# Phase 9D 正式领域契约与状态机

> 状态：`planned/contract-frozen`。本文件是 9D-1 的 Gate B 契约产物，不是 schema、代码、API 或用户路径实现证据。
>
> 审计与立项基线：[`PHASE9D_AUDIT_AND_SCOPE.md`](PHASE9D_AUDIT_AND_SCOPE.md)。9D-0 结论为**部分立项**：当前只冻结并允许实现 deterministic fake/loopback OCR/ASR、本地报告生成/预览/导出和 delivery dry-run；真实 OCR/ASR provider 与真实 SMTP/飞书生产外发暂不立项。

## 1. 审计基线与已验证复用能力

### 1.1 当前正式基线

- 当前 schema 为 v11，下一连续 migration 为 v12；schema 唯一入口是 `backend/app/migrations/runner.py`。
- 部署边界是本地、单进程、单实例、SQLite、单一 `data_root`、服务端注入 `project_id`；当前没有 `user_id`、认证、家长账号、授权系统或多租户。
- `materials`、`extractions`、`text_spans` 是资料正文 source of truth；`material_revisions`、`chunks`、retrieval/context/citation 是可追溯的资料派生链。
- 原件由 `backend/app/storage.py:store_original()` 按 hash-derived 路径保存；material 已有 active/deleted/restored/purged lifecycle。
- Phase 9A/9B/9C 的计划、节奏、笔记、练习、attempt、review、mistake、weak-point 等事实已经存在，可供 S6 只读聚合；S6 不创建第二套学习事实。
- `ai_operations` 已有 `queued/running/succeeded/failed/cancelled/stale` 生命周期；provider registry 有 deterministic fake provider，也有真实 OpenAI-compatible HTTP provider。

### 1.2 9D 必须复用的能力

| 已有能力 | 9D 复用规则 | 不得作出的推断 |
|---|---|---|
| `materials → extractions → text_spans → revisions → chunks` | S7 确认后的转写成为该 material 的新 extraction/revision，复用既有 chunk/index/retrieval/citation | 不得新建平行正文库；未确认 transcript 不能直接作为 ready source |
| hash-derived originals | S7 音频/图片直接使用已有 material/original storage 和 lifecycle | 不得把原件路径放入 API、日志、报告或 delivery audit |
| citation identity/status | 转写接入后的 citation 必须由服务端从现有 revision/chunk/span 验证 | 客户端、provider 或历史 citation 不能自造 `valid` |
| `ai_operations` / fake provider | 默认使用 deterministic fake/loopback，记录安全 operation metadata | raw request/response、provider secret 不持久化 |
| 9A/9B/9C facts | S6 只读聚合 counts/ratios/time buckets 和受限提醒事实 | 不得把 report 当 progress、attempt、review 或 note 写入口 |
| backup/restore | v12 数据天然进入 SQLite backup，但仍必须通过专项 restore gate | restore/startup/read/verify 不得重新 OCR/ASR、生成报告或发送 delivery |

## 2. Phase 9D 范围与明确不做

### 2.1 当前纳入范围

#### S7 ClassCapture

1. 显式创建 project-scoped capture session。
2. 每个 session 接收一个音频或图片原件，复用 material/original storage；多个文件必须创建多个 session。
3. 通过 deterministic fake/loopback OCR/ASR 生成可供用户核对的 transcript draft。
4. 保存转写文本、分段质量标记、置信度和 operation metadata，不保存 raw provider request/response。
5. 用户显式确认后将 transcript 作为该 capture material 的新 extraction/revision，进入既有 chunk/retrieval/citation 管线。
6. source lifecycle、失败、低置信、编辑保护和 retry 具有稳定语义。

#### S6 ParentReport

1. 基于已存在的 9A/9B/9C 事实生成 project-scoped、只读、脱敏报告快照。
2. 支持 `daily`、`weekly`、`monthly`、`exam_alert` 四种报告类型。
3. 提供本地预览、JSON/Markdown 导出和 report snapshot 读取。
4. delivery 只实现 `off` / `dry_run`：默认关闭；dry-run 只构造并记录安全摘要，不连接第三方端点。
5. delivery audit append-only、可幂等重放；真实 live delivery 在本阶段拒绝。

### 2.2 明确不做

- 真实 OCR/ASR provider 的通用接入、准确率承诺、成本/容量承诺；
- 真实 SMTP、飞书 webhook、短信、推送或任何生产第三方外发；
- 自动定时报告、scheduler、worker、queue、后台重试、跨进程任务和 push reminder；
- 多用户、认证、家长账号、监护人关系、权限模型、云同步、协作或跨 project 访问；
- 视频流、实时课堂监听、音频播放、TTS、说话人识别、声纹、课堂成员识别；
- 报告原文、材料名、材料正文、文件路径、答案 key、提交答案、Q&A 内容、聊天内容、逐题明细；
- 报告写回 progress、rhythm、note、module、attempt、review、mistake 或 weak-point；
- OCR/ASR 自动确认、自动修正低置信内容、自动覆盖用户编辑；
- 报告内容的富文本脚本、远程图片、外部链接或未经审计的 HTML；
- 通过 backup/restore、startup、read 或 verify 隐式触发任何 AI、OCR/ASR、report generation 或 delivery。

## 3. 正式术语与关系

### 3.1 Glossary

| 术语 | 冻结定义 | 类型 |
|---|---|---|
| Capture Session | 一次显式课堂原件采集及其转写生命周期；project-scoped | S7 aggregate |
| Capture Material | session 关联的唯一 `materials` 记录；保存音频/图片原件和 source lifecycle | existing source |
| Transcript Draft | 从 capture material 产生、等待用户核对的文本及质量信息；未确认前不是 ready source | proposed artifact |
| Transcript Segment | transcript draft 的有序文本片段，含 `confidence` 与 `quality` | quality-bearing artifact |
| Transcription Operation | 一次 fake/loopback 或未来 provider 转写尝试；append-only operation fact | operation fact |
| Confirmed Transcript Revision | 用户确认后由 transcript 创建的该 material 的新 extraction/revision | source revision |
| Report Snapshot | 某 project、某报告类型和时间窗口的脱敏聚合快照；只读、可重算 | S6 projection |
| Report Delivery Attempt | 对 report 的一次显式 delivery 请求及其结果；append-only | delivery fact |
| Dry-run | 不连接第三方、不发送数据，仅生成安全发送摘要和审计记录 | local action |
| Live Delivery | 真实向 SMTP/飞书等第三方发送；本阶段保留为未来 gate，当前拒绝 | future capability |
| Source Status | 服务端基于 material/revision identity 计算的 `valid/source_deleted/source_unavailable/stale` | derived status |
| Project Scope | 服务端 `AppConfig.project_id`；客户端不能选择任意 project | security boundary |

### 3.2 实体关系

```text
project
├── capture_sessions                                  [S7]
│     └── one materials row (capture material)        [existing source]
│           └── confirmed transcription → extraction
│                                      → material_revision
│                                      → chunks/citations
│
├── report_snapshots                                  [S6, read-only projection]
│     └── report_delivery_attempts                    [append-only audit]
│
├── learning_goals / study_plans / progress           [9A facts]
├── notes / rhythm                                     [9B facts]
└── practice / attempt / review / mistake / weak-point [9C facts]
```

冻结关系：

1. 一个 `capture_session` 只关联一个 capture material；一个 capture material 只能由一个 session 拥有。若要采集多个音频/图片，创建多个 session；本阶段不做多 asset session。
2. capture material 仍是普通 material source of truth，使用已有 `material_id`、`source_sha256`、`stored_path`、`media_type` 和 delete/restore/purge 语义。
3. transcript draft 不直接写入 ready `material_revisions`；只有显式 confirm 才能创建该 material 的新 extraction/revision。
4. report snapshot 只能读取 9A/9B/9C 已有 project-scope 事实，不拥有或复制这些事实；delivery attempt 只能引用 report snapshot。
5. report recipient 不是正式用户/账号对象。当前只允许配置中的 opaque delivery target；不在数据库创建 parent/user/recipient 身份体系。

## 4. 全局不变量

1. 所有新增实体必须带 `project_id`，且服务端从配置注入；请求体、URL 和客户端 JSON 中的 project id 被忽略或拒绝。
2. 所有服务端时间使用 timezone-aware UTC ISO-8601；报告 period 使用显式 IANA timezone 和 date-only 边界，不使用宿主机隐式 timezone。
3. ID 使用已有 opaque TEXT 前缀 + UUID hex 约定，例如 `capture_session_<uuid>`、`transcription_<uuid>`、`report_<uuid>`、`delivery_attempt_<uuid>`；客户端不能指定业务 ID。
4. 所有事实写入在 domain transaction 内完成；失败整体 rollback；普通 read 不产生事实或隐式修复。
5. provider/operation、transcript revision、report snapshot、delivery attempt 的历史不能被 retry 覆盖。重试产生新 operation/artifact/attempt，并通过 `retry_of` 或等价 opaque identity 关联。
6. `source_deleted`、`source_unavailable`、`stale` 只降级 source status，不删除历史文本状态，不恢复 source name/path/text，不伪造 citation。
7. raw provider request/response、API key、SMTP password、webhook secret、完整第三方响应不落库、不进日志、不进 backup、不进 API response。
8. 用户显式编辑过的 transcript draft 不得被 provider retry、重新生成或 source refresh 静默覆盖；新 provider 结果必须是新的 draft/operation。
9. S6 report 是只读 projection，不写入 progress、attempt、review、mistake、note、module 或 rhythm；报告生成不能改变学习事实。
10. 9D 默认只允许 fake/loopback 与 dry-run。真实 OCR/ASR 或 live delivery 即使环境中存在配置，也不能绕过 gate 进入默认路径。

## 5. S7 ClassCapture 契约

### 5.1 Capture Session 字段与输入边界

逻辑字段如下；9D-2 可按 SQLite 归一化拆成 capture、transcription 和 segment 表，但不能改变语义：

| 字段 | 契约 |
|---|---|
| `id` | 服务端生成的 `capture_session_<uuid>` |
| `project_id` | 服务端注入；只读 |
| `status` | `draft/uploaded/transcribing/review_required/confirmed/rejected/failed/archived` |
| `asset_kind` | `audio` 或 `image` |
| `material_id` | 上传成功后绑定唯一 capture material；未上传前为空；绑定后不可换绑 |
| `original_name` | 仅用于用户本地展示；不得进入报告/delivery/log；长度 1–255，basename only |
| `media_type` | 服务端从 allowlist 判定，不信任客户端声明 |
| `source_status` | 服务端计算；`valid/source_deleted/source_unavailable/stale`；不是 session workflow status |
| `created_at/updated_at` | 服务端 UTC |
| `confirmed_at/rejected_at/archived_at` | 状态到达对应状态时由服务端写入 |

当前默认输入边界：

- 使用已有 `AppConfig.max_upload_bytes`，默认 50 MiB；服务端对读入字节数强制限制，客户端声明大小不可信。超过限制稳定返回 `capture_asset_too_large`。
- v1 只接受经过服务端 MIME/扩展一致性检查的常见图片与音频；建议 allowlist 为 `image/png`、`image/jpeg`、`image/webp`、`audio/wav`、`audio/mpeg`、`audio/mp4`。不接受视频、可执行文件、压缩包或浏览器任意 `application/octet-stream`；最终 parser/provider 能力不足时返回 `capture_asset_type_not_supported`。
- 不接受客户端提供的 duration、sample rate、transcript、confidence、source status、stored path 或 provider metadata 作为可信字段。
- 一个 session 只上传一次原件。上传失败不产生可见 material；重试只允许对仍为 `draft` 的 session 执行，并使用新临时文件，不能覆盖已有原件。

### 5.2 Transcription Operation 与结果

#### Operation

- `operation_type` 使用明确的 9D 类型（建议 `class_capture_transcription`），复用 `ai_operations` 的 queued/running/succeeded/failed/cancelled/stale 语义。
- operation 输入指向 `capture_session_id` / `material_id` / 当前 source identity；不保存 raw prompt、raw audio/image bytes、raw provider response。
- 默认 runtime 为 deterministic fake/loopback。fake 结果必须可重复；真实 OCR/ASR 只有未来独立 gate 通过且显式 opt-in 才允许。
- 同一 session 的相同输入 fingerprint + Idempotency-Key 可 replay 安全结果；不同输入或不同 source revision 不得复用旧结果。provider retry 创建新 operation，不更新旧 operation。

#### Transcript Draft / Segment

- transcript draft 至少有：`id`、`capture_session_id`、`operation_id`、`text`、`language`（可为空或服务端识别）、`quality_status`、`edited_by_user`、`created_at`、`updated_at`。
- segment 至少有：`ordinal`、`text`、`confidence`、`quality`。`confidence` 为服务端归一化 `[0,1]` 数值；fake provider 也必须使用同一语义，不得把 fake 分数宣称为真实准确率。
- `quality` 只能为 `clear` 或 `uncertain`。当 confidence 低于冻结阈值、provider 明确标记模糊、文本为空/乱码或图片/音频无法可靠识别时使用 `uncertain`。阈值由 9D-2/测试固定为一个确定常量，不由客户端提交。
- 任意 `uncertain` segment 都要求用户核对；系统可以允许用户继续编辑/确认，但不能把它表现为 AI 已最终裁决。报告只允许统计 `uncertain_segment_count`，不包含片段文本。
- 转写失败、超时、未配置 provider、格式不支持、输出结构非法均进入 `failed`/安全错误；不得保存半截 raw response。失败 operation 仍保留安全 metadata，retry 产生新 operation。
- 空文本不能 confirm。乱码或仅空白文本必须返回 `transcript_empty_or_invalid`。

### 5.3 Capture Session 状态机

```text
draft
  └─ upload success ─────────────→ uploaded
uploaded
  ├─ explicit transcribe ───────→ transcribing
  └─ archive ───────────────────→ archived
transcribing
  ├─ operation succeeded ────────→ review_required
  ├─ operation failed/cancelled → failed
  └─ source deleted/purged ──────→ transcribing + source_status degraded
failed
  ├─ explicit retry ─────────────→ transcribing
  └─ archive ───────────────────→ archived
review_required
  ├─ user edits draft ───────────→ review_required (edited_by_user=1)
  ├─ explicit confirm ───────────→ confirmed
  ├─ explicit reject ────────────→ rejected
  └─ archive ───────────────────→ archived
confirmed
  └─ archive ───────────────────→ archived
rejected
  ├─ explicit new transcription → transcribing (new draft; old artifact retained)
  └─ archive ───────────────────→ archived
archived
  └─ terminal
```

- `confirmed` 表示 transcript 已通过用户显式确认并产生 confirmed material revision；不表示 OCR/ASR 绝对正确。
- `source_status` 与 workflow status 分离。原件被删除或 purge 后，confirmed session 保留历史事实，但 source status 降为 `source_deleted` 或 `source_unavailable`；不得伪造可下载原件或 citation。
- 普通 GET 不会自动从 `failed` 重试、不从 `source_unavailable` 提升状态、不自动重建 revision。
- 同一 session 重新转写不得覆盖已确认 revision；必须生成新的 draft。已确认内容如需替换，用户必须显式发起新 session 或明确的 future revision workflow；本阶段不做 silent replacement。

### 5.4 S2 资料管线接入

- 9D 冻结为：**同一个 capture material 创建新的 extraction/revision**，不新建第二个 transcript material，也不把 transcript 存成平行正文。revision 的 `parser_id/parser_version` 区分 `ocr`/`asr` 与普通文件 parser。
- confirm 前：transcript text 只属于 draft artifact，不进入 `ready` chunks、FTS 或 vector retrieval。
- confirm 时，在一个 domain transaction 内：
  1. 重新确认 capture material 仍属于 project、未 deleted/purged；
  2. 重新校验 draft/segment/text，计算 source fingerprint；
  3. 创建 extraction/revision，并按既有 chunking/index contract 生成 chunks；
  4. 只有全部成功才把 session 置为 `confirmed`；任何失败整体 rollback，session 保留 `review_required`。
- confirmed revision 的 citation 必须使用现有 `material_id/revision_id/extraction_id/chunk_id/span_id/citation_key` identity，并由服务端 `validate_citation_key()` 或等价逻辑验证。
- 用户编辑 transcript draft 后，`edited_by_user=1`；provider retry 不能覆盖该 draft。新的 draft 只有用户显式选择后才可 confirm。
- 已确认 revision、note、module、exercise、attempt、review 不被后续转写或 source refresh 静默改写。

## 6. S6 ParentReport 契约

### 6.1 Report Snapshot 字段与类型

| 字段 | 契约 |
|---|---|
| `id` | 服务端生成的 `report_<uuid>` |
| `project_id` | 服务端注入；只读 |
| `report_kind` | `daily`、`weekly`、`monthly`、`exam_alert` |
| `timezone` | 有效 IANA timezone；服务端用其解释 period |
| `period_start` / `period_end` | 严格 `YYYY-MM-DD`；半开区间 `[start,end)`；start < end |
| `status` | `draft/ready/failed/archived` |
| `content_version` | 服务端稳定版本字符串 |
| `aggregation_fingerprint` | 输入事实及规则版本的 hash；不包含 raw content |
| `safe_payload_json` | 只含第 6.2 节白名单字段；不得含 raw source |
| `markdown_content` | 从 safe payload 确定性生成的本地展示/导出文本；不得含黑名单内容 |
| `created_at/updated_at/ready_at/archived_at` | 服务端 UTC |

报告生成不是后台 job：当前 9D 只支持用户显式请求、同步生成或同步失败。若未来耗时需要 worker，必须另立 Phase 10 contract，不能在 9D 中偷偷引入。

报告是 snapshot，不是动态查询：同一 snapshot ready 后内容不可普通更新；重新生成创建新的 snapshot，旧 snapshot 可读取/归档。`aggregation_fingerprint` 用于确定性 replay 和验证，不作为用户可见内容。

### 6.2 脱敏白名单

报告对外内容只能由以下字段构成。字段名可在 API/UI 映射为中文，但值的语义不可扩大：

1. **period metadata**：report kind、period start/end、timezone、generated-at（不包含内部 DB ID）。
2. **plan aggregates**：active goal count、active plan count、planned item count、completed item count、started item count、skipped item count、planned minutes total；只允许 count/minutes，不允许 goal/plan/item title 或 description。
3. **rhythm aggregates**：allocated day count、allocated minutes total、unallocated eligible item count、overload day count；不返回具体日期的任务明细或用户备注。
4. **practice aggregates**：practice session count、cram session count、attempt count、deterministic correct count、deterministic incorrect count、pending-review count、completed session count；可返回 coarse score bucket，不返回逐题结果。
5. **feedback aggregates**：open mistake count、in-review count、fixed count、reopened count、archived count、weak-point count；不返回错题文本、错因原文或具体练习题。
6. **source-quality aggregates**：valid source count、stale count、source-deleted count、source-unavailable count、uncertain transcript segment count；不返回 material name、quote、正文或路径。
7. **exam alert aggregate**：仅针对显式 active goal 的 days-remaining bucket（如 `0-3`、`4-7`、`8-14`、`15+`）和目标是否临近；不返回考试名称、科目名称或原始日期，除非未来另行通过隐私评审。
8. **quality flags**：`has_pending_review`、`has_source_warnings`、`has_uncertain_capture` 等布尔/计数型安全提示。

聚合规则：

- count 只统计同一 project、同一明确 period 且有合法时间戳的事实；跨 project、未来时间、无效状态不计入。
- 每种事实使用服务端固定的状态映射；客户端不能传入“完成数/分数/提醒内容”覆盖聚合结果。
- 空数据返回零值和安全空状态，不返回 SQL 错误、source 详情或 provider 原因。
- 不把 report generation 的结果写回原事实；报告生成失败不改变任何学习对象。

### 6.3 Report 状态机

```text
draft
  ├─ synchronous aggregation success → ready
  └─ aggregation/serialization failure → failed
ready
  └─ explicit archive → archived
failed
  ├─ explicit retry → new report snapshot (old failed fact retained)
  └─ explicit archive → archived
archived
  └─ terminal/read-only
```

- `ready` snapshot 的 safe payload、markdown 和 aggregation fingerprint 不可普通编辑。
- `report_kind`、period、timezone、规则版本改变时必须创建新 snapshot，不能 update 原 snapshot。
- report 不提供用户任意正文编辑；如需解释，只能由白名单字段确定性渲染。

## 7. S6 Delivery 契约

### 7.1 支持范围和默认安全策略

| mode | 当前 9D 语义 |
|---|---|
| `off` | 默认值；请求直接稳定拒绝并写入最小安全 blocked audit（不得连接网络） |
| `dry_run` | 只生成安全内容摘要和目标校验结果；不连接 SMTP/飞书、不发送任何 payload |
| `live` | 当前阶段不支持；即使配置了 provider/secret 也返回 `delivery_live_not_approved`，不得连接第三方 |

真实 live delivery 必须经过未来独立组件证据、隐私/保留/运维评审和显式 gate；它不属于本 `contract-frozen` 默认完成范围。

### 7.2 配置、授权与目标

- 渠道抽象可使用 `smtp` / `feishu` 作为未来 channel identifier，但当前 adapter 不得实现真实发送。
- channel secret 只允许从环境/受控运行配置读取，不能存储到 SQLite、报告 snapshot、delivery audit、backup 或普通 repr/log。
- 目标是配置的 opaque allowlist entry；当前不实现 parent/recipient 表，也不接受请求体任意目标作为授权。
- `off` → `delivery_disabled`；`dry_run` 必须明确显示 `not_sent`；`live` → `delivery_live_not_approved`。
- 若未来启用 live，必须同时满足：显式配置、显式用户确认、目标精确匹配 allowlist、channel gate 通过；任何一个缺失都拒绝。当前 live 逻辑只保留拒绝 contract。

### 7.3 Delivery Attempt 记录

每次显式 delivery 请求最多写一条 append-only attempt：

- `id`、`project_id`、`report_id`、`channel`、`mode`、安全目标标识/脱敏摘要、content fingerprint、idempotency key fingerprint、result/status、error code、created_at、finished_at、retry_of。
- 不保存完整收件地址、webhook URL、secret、报告 raw content 或第三方 raw response；目标只允许受控 opaque label 或脱敏摘要。
- 状态为 `blocked`、`dry_run`、`succeeded`（仅未来 live gate）、`failed`。重试创建新 attempt，不覆盖历史。
- 相同 project/report/channel/mode/target/content fingerprint + 相同 idempotency key 的请求 replay 安全结果；同 key 不同 payload 返回 `delivery_idempotency_mismatch`。
- 9D 不自动重试、不自动发送、不因 report ready 而发送；所有 attempt 都必须由用户显式请求触发。

## 8. Source lifecycle 与数据保留

### 8.1 Source status

S7 source identity 与既有 source contract 一致：

- `valid`：material active、revision/extraction/chunk identity 仍匹配 current verified source；
- `source_deleted`：material 被软删除；
- `source_unavailable`：purge 或 restore 后无法安全确认原始来源；
- `stale`：source identity 仍存在但 revision/extraction/chunk 不再是对应 current source。

source status 是服务端派生值，客户端不可写。历史 transcript text、confirmed revision 的 metadata、report snapshot 与 delivery audit 不因为 source degradation 被伪造、重写或恢复为 valid。

### 8.2 保留和清理

- capture original 与 confirmed transcript revision 服从既有 material delete/restore/purge lifecycle；本阶段不引入自动清理 worker。
- 失败的临时上传字节在请求结束/失败 rollback 后删除；raw provider input/output 永不作为持久化对象保留。
- transcript draft 与 operation metadata 在其 session 生命周期内保留；用户显式 reject/archive 后仍保留最小审计事实，不能通过普通 retry 覆盖。
- report snapshot 与 delivery audit 通过显式项目/实体清理删除；本阶段不自动定时删除。若未来引入固定保留期，必须新增 retention contract、migration 和验收，不得由 scheduler 暗中实现。
- backup 包含 SQLite 中的 9D 事实，但不包含 secrets、raw provider response 或临时上传文件；restore 到新空目录。

### 8.3 Backup/restore non-repair

backup、verify、restore、startup、普通 read 必须满足：

1. 不调用 OCR/ASR/provider，不生成 transcript，不创建 report snapshot。
2. 不改变 capture/session/transcript/report/delivery status，不把 source status 从 unavailable/stale 提升。
3. 不发送 dry-run 以外的任何 delivery；restore/startup 不应创建 delivery attempt。
4. 保留 migration history、`PRAGMA user_version`、append-only operation/delivery facts 和 source tombstone identity。
5. 需要重新索引、重新转写或重新生成报告时，必须是用户显式操作且走对应 domain contract。

## 9. AI / operation / draft / provider 边界

1. S7 fake/loopback 是默认唯一可重复 provider；其 confidence 只表示测试/组件输出，不是准确率承诺。
2. 真实 OCR/ASR 适配器不得以“provider 配置存在”自动启用；必须有独立 capability gate、显式测试和 9D 范围更新。
3. operation 只记录安全 metadata：类型、状态、scope、input fingerprint、source revision、provider/model ID（可公开）、request ID、retry count、error code、时间和 latency；不记录 raw input/output 或 secret。
4. transcript draft 是建议/待核对 artifact；confirm 是用户动作。provider 输出不能直接成为 confirmed revision。
5. user-edited transcript draft 有保护标记；retry 产生新 draft，不覆盖用户版本。未来需要 merge 时另立契约。
6. S6 报告不需要 LLM；若未来引入 AI narrative，必须沿用 draft/citation/privacy contract，并不能把生成文本放入本阶段白名单。

## 10. 输入、错误与 API resource 草案

### 10.1 输入与响应安全

- 所有文本有服务端长度上限；报告 safe payload 有固定字段/数量上限；不得接受任意 JSON 作为报告内容。
- 客户端不得提交 `project_id`、source status、stored path、answer key、provider metadata、confidence 结论、聚合数字或 delivery authorization 作为可信值。
- 普通 list/detail/preview/export/delivery response 不返回原件路径、secret、raw response、答案 key、提交原文、Q&A 原文或报告黑名单字段。
- export 只支持受限 `application/json` 与 `text/markdown`；JSON 必须是 safe payload，Markdown 必须由 safe payload 确定性渲染。

### 10.2 API resource 草案

资源命名只冻结边界，9D-8 再按当前 `main.py` 路由风格落地：

```text
POST   /api/study/capture-sessions
GET    /api/study/capture-sessions
GET    /api/study/capture-sessions/{capture_id}
POST   /api/study/capture-sessions/{capture_id}/upload
POST   /api/study/capture-sessions/{capture_id}/transcribe
GET    /api/study/capture-sessions/{capture_id}/transcript
POST   /api/study/capture-sessions/{capture_id}/transcript/edit
POST   /api/study/capture-sessions/{capture_id}/confirm
POST   /api/study/capture-sessions/{capture_id}/reject
POST   /api/study/capture-sessions/{capture_id}/archive

POST   /api/study/reports
GET    /api/study/reports
GET    /api/study/reports/{report_id}
GET    /api/study/reports/{report_id}/preview
GET    /api/study/reports/{report_id}/export
POST   /api/study/reports/{report_id}/delivery
GET    /api/study/reports/{report_id}/delivery-attempts
```

- 所有 mutating POST 支持适用时的 `Idempotency-Key`；同 key 不同请求 fingerprint 稳定返回 mismatch。
- 不提供 live delivery 专用 endpoint；统一 delivery endpoint 根据 mode 返回 `delivery_live_not_approved`。
- 不提供 parent/user scope endpoint、跨 project endpoint 或 scheduler endpoint。

### 10.3 稳定错误码

至少冻结以下错误码；HTTP 状态按现有 `main.py` 的稳定 code 风格映射，不返回内部异常：

| 错误码 | 语义 |
|---|---|
| `project_scope_violation` | 请求对象不属于服务端 project |
| `capture_not_found` | session 不存在或不可见 |
| `capture_invalid_state` | 当前状态不允许动作 |
| `capture_asset_type_not_supported` | 音频/图片类型不在 allowlist |
| `capture_asset_too_large` | 超出服务端 upload limit |
| `capture_upload_failed` | 原件写入失败且已 rollback |
| `capture_source_unavailable` | 原件无法安全使用 |
| `transcription_not_ready` | 没有可处理的已上传原件 |
| `transcription_provider_not_configured` | 需要的 fake/loopback capability 不可用 |
| `transcription_failed` | 转写失败/超时/非法输出 |
| `transcript_empty_or_invalid` | 空白、乱码或结构不合格 |
| `transcript_uncertain_requires_review` | 仍有低置信内容需要核对 |
| `transcript_citation_invalid` | source identity/citation 验证失败 |
| `transcript_user_edit_protected` | 试图静默覆盖用户编辑 |
| `report_invalid_kind` | 报告类型不支持 |
| `report_invalid_period` | timezone/period 边界非法 |
| `report_not_found` | report 不存在或不可见 |
| `report_invalid_state` | report 当前状态不允许动作 |
| `report_redaction_violation` | 生成内容越过脱敏白名单 |
| `report_generation_failed` | 聚合或序列化失败 |
| `delivery_disabled` | delivery mode 为 off |
| `delivery_target_not_allowed` | 目标不在受控 allowlist |
| `delivery_authorization_required` | 缺少显式授权（未来 live gate） |
| `delivery_live_not_approved` | 当前 9D 不允许真实外发 |
| `delivery_idempotency_mismatch` | 相同 key 对应不同请求 |
| `delivery_failed` | dry-run/未来 adapter 失败 |
| `source_deleted` / `source_unavailable` / `source_stale` | source 已降级，不伪造内容 |
| `invalid_idempotency_key` | key 缺失、过长或格式非法 |
| `payload_too_large` | JSON/text/segment 超出边界 |

## 11. SQLite constraint 与 domain transaction 分工

### 11.1 SQLite 应表达

- 所有新增事实的 `PRIMARY KEY`、`project_id NOT NULL`、必要 FK、长度和枚举 CHECK；
- capture session 的唯一 material 绑定、report period 合法性基础约束、delivery attempt/report 引用；
- confidence 在 `[0,1]`、segment ordinal 非负、报告 count/minutes 非负；
- `UNIQUE(project_id, capture material)`、report 快照不可用普通 update 替代的版本/fingerprint 索引；
- operation/delivery attempt 的必要索引、created_at/status/source lookup；
- 不为 source identity 使用会在 purge 时破坏 tombstone 的强 FK；valid citation 由 domain 二次验证；
- secret、raw response、stored path 不出现在新增 9D 业务表。

### 11.2 Domain transaction 必须表达

- 服务端 project scope、owner、状态转移、确认/拒绝/归档权限；
- upload → material → session 绑定的原子性和失败清理；
- operation retry/idempotency、transcript user-edit protection 和旧 revision 不覆盖；
- confirm 时重新验证 source identity、创建 extraction/revision/chunks 的原子边界；
- report 聚合只读、白名单脱敏、snapshot immutability 和 fingerprint；
- delivery mode、显式授权、target allowlist、dry-run/no-network、审计和 retry；
- source status refresh、降级历史、backup/restore non-repair；
- 禁止把客户端传入的 status、confidence、聚合数、citation status 当作事实。

## 12. Test contract for downstream tasks

### Gate B（本任务）

必须能从本文件回答：

1. S7 一个 session 只能有一个 capture material；confirm 后是同 material 的新 revision，不是平行 transcript material。
2. fake/loopback 是默认路径；真实 OCR/ASR 不因配置存在自动启用。
3. transcript 的 confidence/uncertain、失败、retry、用户编辑和 source lifecycle 语义闭合。
4. S6 report 只保存白名单聚合 snapshot，不能写回学习事实。
5. delivery `off` 默认拒绝，`dry_run` 不联网，`live` 当前拒绝；secret/raw response 不落库。
6. report/session/operation/delivery 的状态机、append-only 与 idempotency 不互相矛盾。

### 后续 focused tests 必须覆盖

- **9D-2**：new DB、v11→v12、幂等、失败 rollback、history/user_version、CHECK/FK/index、backup schema version。
- **9D-3**：scope、状态转移、append-only、idempotency、source status、report projection 不改事实、delivery secret 不落库。
- **9D-4/5**：原件大小/type、fake OCR/ASR、confidence/uncertain、失败/retry、用户编辑保护、confirm revision、citation、source lifecycle。
- **9D-6/7**：四种报告类型、period/timezone、聚合白名单/黑名单、snapshot replay、off/dry-run/live reject、allowlist、审计、重试/去重。
- **9D-8/9**：稳定 HTTP error、privacy response、desktop/narrow/keyboard/reload、duplicate click、provider failure、safe DOM。
- **9D-10**：delete/restore/purge/re-index、backup→verify→新空目录 restore、无 provider/OCR/ASR/report/delivery side effect。

## 13. Gate B 结论与准确状态

- **契约状态**：`contract-frozen`。
- **当前可实现范围**：S7 fake/loopback 课堂采集、转写 draft、用户确认后接入既有 S2 revision；S6 脱敏报告 snapshot、预览/导出、off/dry-run delivery audit。
- **明确暂缓范围**：真实 OCR/ASR provider、SMTP/飞书真实发送、scheduler/worker、自动推送、多用户/家长账号。
- **下一步**：9D-2 只按本契约设计连续 v12 migration/schema；如果实现需要改变一对一 material 关系、报告白名单、delivery mode、保留策略或状态机，必须停工并先提交契约变更，不得在 migration/repository 中自行猜测。
- **完成声明限制**：本文和后续局部 backend pass 都不能单独宣称 Phase 9D completed；完成必须限定在 Gate A-L 实际通过的 deterministic fake/loopback、local single-process、SQLite、Chromium、backup/restore、dry-run 范围。
