# AI / 学习功能架构设计

状态：architecture plus Phase 4–7 implementation、Phase 8 completed（deterministic fake-provider scope）和 Phase 9A completed（deterministic fake-provider / local single-process / SQLite / Chromium / backup-restore scope，见 `PHASE9A_ACCEPTANCE_EVIDENCE.md`）；Phase 9B 的 9B-2 至 9B-6 达到 `implemented/backend-pass`（v10 persistence schema、共用 note/rhythm repository/domain transaction、S2 deterministic fake-provider note draft workflow、S1 synchronous study-rhythm workflow、S1/S2 最小安全 API），9B-7 S1/S2 最小 Chromium workspace 达到 `browser-pass`，9B-8 至 9B-9 仍未实现。material revision、deterministic chunks、lexical/vector/hybrid retrieval、retrieval persistence、context assembly with citation contract、deterministic fake provider、同步 Q&A API/persistence、Q&A history、多材料范围、citation navigation 和浏览器验收已实现。Phase 8 的 schema、Cards/Exercises lifecycle、citation-safe draft generation、workspace 和 backup/restore closeout 已完成；证据见 [`PHASE8_ACCEPTANCE_EVIDENCE.md`](PHASE8_ACCEPTANCE_EVIDENCE.md)。Phase 9A 当前已完成 `planned/audit-draft` 的 9A-0 代码审计和 `planned/contract-frozen` 的 9A-1 正式领域契约/状态机冻结（[`phase9a/PHASE9A_DOMAIN_CONTRACT.md`](phase9a/PHASE9A_DOMAIN_CONTRACT.md)）。9A-2 已新增并测试 v9 schema migration，9A-3 已实现并测试学习目标、知识模块、学习计划、计划项、依赖、append-only progress 和 source identity refresh 的 repository/domain contract，9A-4 已实现并测试最小 API、project scope、稳定错误和输入边界，9A-5 已通过本地 Chromium 计划 workspace gate，9A-6 source lifecycle scoped backend/browser gates 已通过；9A-7 artifact backup/restore 已通过 `restore-gates-pass`，9A-8 已在限定范围内完成 closeout；完整用户路径之外的扩展能力仍按后续 Phase 推进。Phase 9B 当前：v10 `phase9b_material_learning_schema`（9B-2）、共用 note/rhythm repository/domain transaction 与 citation-safe source link/refresh（9B-3）、单材料 deterministic fake-provider `generate_note`（9B-4）以及 S1 daily/weekly IANA-timezone settings、manual allocation 和 deterministic summary（9B-5）已实现并有 focused tests。S1 不会写 progress、自动重排或启动 scheduler。人工简答复核、真实 Provider generation、9B-8 至 9B-9 和后续学习工作流仍按主路线图推进。

## 1. 范围与原则

StudyBuddy 当前的 source of truth 仍是 `materials`、`extractions`、`text_spans`。AI 数据全部是可追溯的派生数据或用户状态，不替代原始材料和解析正文。Phase 4 面向单用户、单进程、SQLite、本地文件存储；provider 未配置时应用必须照常启动，AI endpoint 返回稳定的 `provider_not_configured`。

Phase 4 不接入真实 provider、不自动为历史材料生成 chunk/embedding、不引入外部向量数据库、不在 startup repair AI 数据、不引入后台队列，不自动修改用户确认过的卡片、练习或计划。

## 2. 分层

```text
materials / extractions / text_spans
        ↓ immutable source read
material_revisions
        ↓ deterministic chunker
chunks / chunk_spans
        ↓ lexical index first; optional embeddings later
retrieval_runs / retrieval_hits
        ↓ token-budgeted context assembly
context + verified citation candidates
        ↓ provider abstraction
ai_operations / generated artifacts
        ↓ explicit user confirmation or edit
Q&A / cards / exercises / study plans / review state
```

- Source layer：解析器和材料生命周期产生，不能由 AI 覆盖。
- Revision/chunk layer：可重建，带 source revision 和 algorithm version。
- Retrieval layer：可重建，记录检索策略和命中证据。
- Generation layer：可失败、可重试、可标记 stale；保存 provider/model/prompt metadata。
- User state：用户编辑、确认、复习、作答和计划进度不能被重新生成静默覆盖。

## 3. Provider abstraction

provider 只接收已经准备好的 messages 或 texts，不读取文件、不操作 SQLite、不知道 FastAPI request。adapter 将厂商异常映射为稳定错误码。

```python
class ProviderResponse(TypedDict):
    text: str
    structured: dict[str, object] | None
    provider_id: str
    model_id: str
    model_revision: str | None
    request_id: str | None
    prompt_tokens: int | None
    completion_tokens: int | None

class LLMProvider(Protocol):
    provider_id: str
    model_id: str
    def generate(self, *, messages: list[dict[str, str]], temperature: float,
                 max_tokens: int, response_schema: dict[str, object] | None = None) -> ProviderResponse: ...

class EmbeddingProvider(Protocol):
    provider_id: str
    model_id: str
    model_revision: str
    dimensions: int
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

正式代码已实现并使用 `LLMProvider`，并已实现 `EmbeddingProvider` registry、deterministic fake embedding 和 OpenAI-compatible embedding adapter；Mistral `mistral-embed` 的外部 acceptance 仅适用于已记录的精确 gateway/model。注册表根据 `provider_id` 创建 adapter；配置只保存 provider/model/timeout/limits，不保存 key 到数据库、manifest 或日志。支持 capability、context window、structured output、streaming capability、rate-limit 和 deterministic fake provider。真实 provider 通过环境变量配置，例如 `STUDYBUDDY_LLM_PROVIDER`、`STUDYBUDDY_LLM_MODEL`、`STUDYBUDDY_EMBEDDING_PROVIDER`、`STUDYBUDDY_EMBEDDING_MODEL`、`STUDYBUDDY_AI_TIMEOUT_SECONDS`、`STUDYBUDDY_AI_MAX_OUTPUT_TOKENS`。

稳定错误：`provider_not_configured`、`provider_unavailable`、`provider_timeout`、`provider_rate_limited`、`provider_auth_failed`、`provider_quota_exceeded`、`provider_invalid_response`、`provider_refusal`。

## 4. Source revision

第一阶段单独建立 `material_revisions`。rename 不创建 revision；soft delete/restore 只改变可见性；新的 extraction/parser 结果创建新 revision，旧 revision 标记 `superseded_at`。revision fingerprint 由 source hash、extraction 内容 hash、parser id/version 组成。

```text
material_revisions(
 id TEXT PRIMARY KEY, material_id TEXT NOT NULL, extraction_id TEXT NOT NULL,
 source_sha256 TEXT NOT NULL, extraction_sha256 TEXT NOT NULL,
 parser_id TEXT NOT NULL, parser_version TEXT NOT NULL,
 revision_fingerprint TEXT NOT NULL UNIQUE, is_current INTEGER NOT NULL,
 created_at TEXT NOT NULL, superseded_at TEXT
)
```

当前导入不会自动创建 AI revision；只有显式 AI indexing 或未来迁移任务创建。当前 indexing 对同一 extraction 幂等复用 revision，新 extraction 会 supersede 旧 current revision。现有 text_spans 没有绝对 offset，因此 chunker 按 span ordinal/id 和 extraction.text 中的顺序文本匹配建立映射；无法安全匹配的 span 不建立关联。新问题只检索 current revision 且 active material。purge 删除 material 后，未来历史回答/卡片可保留，但 citation 状态为 `source_unavailable`，不伪造可点击来源。

## 5. Chunk

第一阶段 chunk 是 extraction.text 的派生切片，offset 以 Python Unicode code-point index 定义，服务端不把它当 byte offset；span 关联保存 page/slide/document 证据。chunker 必须 deterministic，同一 extraction、strategy、version 产生相同结果。

```text
chunks(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL, material_id TEXT NOT NULL,
 revision_id TEXT NOT NULL, extraction_id TEXT NOT NULL, chunk_index INTEGER NOT NULL,
 text TEXT NOT NULL, normalized_text TEXT NOT NULL, start_offset INTEGER NOT NULL,
 end_offset INTEGER NOT NULL, token_count_estimate INTEGER, overlap_before INTEGER NOT NULL,
 overlap_after INTEGER NOT NULL, strategy TEXT NOT NULL, chunking_version TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','ready','failed','stale','deleted')),
 error_code TEXT, created_at TEXT NOT NULL, superseded_at TEXT,
 UNIQUE(revision_id, chunk_index)
)
chunk_spans(chunk_id TEXT, span_id TEXT, overlap_start INTEGER, overlap_end INTEGER,
 PRIMARY KEY(chunk_id, span_id), FOREIGN KEY(chunk_id) REFERENCES chunks(id) ON DELETE CASCADE)
```

空 extraction 允许零 chunk；超大 span 按安全字符/token 上限切分，尽量不跨 page/slide 边界。rename 不影响 chunk，delete 默认排除 retrieval，restore 可重新使用 ready chunk，purge 级联删除派生 chunk。用户编辑不修改 chunk，而应保存为 annotation 或新的用户 artifact。

## 6. Embedding 与 retrieval

正式实现已支持 SQLite FTS5 lexical retrieval、显式 embedding indexing、vector cosine retrieval、deterministic hybrid RRF 和明确 fallback policy。embedding identity、f32 payload codec、ready/stale lifecycle、indexing lease 与 retry 的正式契约见 [`PHASE7_1_AUDIT_AND_CONTRACT.md`](PHASE7_1_AUDIT_AND_CONTRACT.md)；外部 real-pass 仅限 [`PHASE7_EMBEDDING_ACCEPTANCE_EVIDENCE.md`](PHASE7_EMBEDDING_ACCEPTANCE_EVIDENCE.md) 所记录的 Mistral 精确配置。

明确决策：第一阶段不引入外部 vector DB。先使用 SQLite FTS5 的 chunk lexical index，原因是当前单进程/SQLite/backup 模型简单且可完全恢复。未来 embedding 可以先落 SQLite（压缩 binary payload 或独立 embedding blob 文件但必须纳入 manifest）；规模确实需要时再引入外部 ANN，并要求独立 index manifest/rebuild 命令，不能形成隐式状态。

```text
embeddings(
 id TEXT PRIMARY KEY, chunk_id TEXT NOT NULL, provider_id TEXT NOT NULL,
 model_id TEXT NOT NULL, model_revision TEXT, dimensions INTEGER NOT NULL,
 vector_encoding TEXT NOT NULL, vector_payload BLOB, external_vector_id TEXT,
 content_hash TEXT NOT NULL, source_revision TEXT NOT NULL,
 status TEXT NOT NULL, error_code TEXT, created_at TEXT NOT NULL,
 UNIQUE(chunk_id, provider_id, model_id, model_revision, content_hash)
)
retrieval_runs(
 id TEXT PRIMARY KEY, query TEXT NOT NULL, normalized_query TEXT NOT NULL,
 project_id TEXT NOT NULL, thread_id TEXT, policy_version TEXT NOT NULL,
 embedding_provider_id TEXT, embedding_model_id TEXT, status TEXT NOT NULL,
 error_code TEXT, created_at TEXT NOT NULL
)
retrieval_hits(
 run_id TEXT NOT NULL, chunk_id TEXT NOT NULL, rank INTEGER NOT NULL,
 score REAL NOT NULL, lexical_score REAL, vector_score REAL, rerank_score REAL,
 selected INTEGER NOT NULL, citation_label TEXT NOT NULL,
 PRIMARY KEY(run_id, chunk_id)
)
```

第一阶段策略：现有 FTS5/substring 语义 → chunk FTS5 AND lexical ranking → top-k → context assembly。vector score、hybrid、reranker 只保留字段/接口，不在第一阶段启用。deleted material、非 current revision、非 ready chunk 都排除。空结果是 `retrieval_empty`，不是让模型自由回答。

## 7. RAG context 与 citation

`context_assembler` 独立于 Q&A endpoint。输入 query、历史消息、retrieval hits、system policy、token budget，输出有序 context blocks、citations、截断元数据、prompt/policy version。每个 block 使用明确边界标记，将材料内容视为不可信数据，不允许材料中的指令升级为 system/developer 指令。

```text
qa_citations(
 id TEXT PRIMARY KEY, answer_id TEXT NOT NULL, citation_key TEXT NOT NULL,
 material_id TEXT NOT NULL, revision_id TEXT, extraction_id TEXT,
 chunk_id TEXT, span_id TEXT, quote TEXT NOT NULL, position INTEGER NOT NULL,
 source_revision TEXT, status TEXT NOT NULL,
 UNIQUE(answer_id, citation_key)
)
```

模型只能返回引用 key；系统只接受 assembly 产生且仍能映射到 chunk/span 的 key。伪造 key、越界 quote 或不在 context 的 citation 标为 `citation_invalid`，不能直接展示为可信引用。答案要求基于 context，不足时明确不知道；历史 source 被 purge 后保留答案文本和引用记录，但 citation 显示 unavailable。

## 8. AI operation

不立即引入 worker，但所有生成操作预留统一操作记录：

```text
ai_operations(
 id TEXT PRIMARY KEY, operation_type TEXT NOT NULL, status TEXT NOT NULL
 CHECK(status IN ('queued','running','succeeded','failed','cancelled','stale')),
 project_id TEXT NOT NULL, material_id TEXT, thread_id TEXT,
 input_fingerprint TEXT NOT NULL, source_revision TEXT,
 retrieval_policy_version TEXT, prompt_version TEXT,
 provider_id TEXT, model_id TEXT, request_id TEXT,
 retry_count INTEGER NOT NULL DEFAULT 0, error_code TEXT,
 output_artifact_id TEXT, prompt_tokens INTEGER, completion_tokens INTEGER,
 latency_ms INTEGER, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT
)
```

同步执行可以先写 `running` 再结束；未来 worker 复用状态。input fingerprint 保证幂等，retry 只对 timeout/unavailable/rate-limit 等 retryable code 开放。source revision 改变使旧 operation stale；不可重试错误终止。backup/restore 直接覆盖 operation 记录，不自动重跑。

## 9. Q&A

第一阶段最小模型：

```text
qa_threads(id, project_id, title, created_at, updated_at, archived_at)
qa_messages(id, thread_id, role CHECK(system/user/assistant/tool), content,
 created_at, ai_operation_id)
qa_answers(id, message_id, ai_operation_id, answer_text, answer_format,
 source_coverage, status, prompt_version, provider_id, model_id, generated_at)
```

assistant answer 必须关联 operation、retrieval_run 和独立 citations。provider 原文不覆盖最终 answer；结构化输出先 schema validate。历史 thread 可保留，source 删除只影响 citation availability。第一阶段 API 设计为 `GET /api/ai/capabilities`、thread CRUD、`POST /api/qa/threads/{id}/messages`；未配置 provider 返回 `provider_not_configured`，不返回 source 全文或 key。

## 10. Cards

Phase 8.2 已实现 backend MVP：`study_decks`、`study_cards`、`card_citations`、`card_reviews`。card 状态为 `draft/ready/rejected/stale/archived`；现有 API 支持 deck/card create/list、draft edit、confirm/reject/archive 和 append-only review。8.4 可从显式已索引 single-material scope 通过 lexical/vector/hybrid retrieval 生成 cited AI card draft；operation/retrieval/provider metadata 与 draft/citation 原子保存，重复请求可 replay，失败或 source stale 不留 draft。8.5 内嵌 workspace 提供 deck 选择、生成/编辑/确认/拒绝/归档/复习、citation 定位或 unavailable 展示及刷新恢复。AI card 永远先 draft，确认时需要有效 citation；用户编辑会标记 `edited_by_user`，已 ready/archived card 不可通过该 API 编辑。backup/restore closeout 已覆盖 Cards、citations、reviews 和 generation operations 的保留与不自动 repair；真实 Provider generation evidence 和系统级辅助技术验收仍未完成。

## 11. Exercises

Phase 8.3 已实现 backend MVP：`exercise_sets`、`exercises`、`exercise_citations`、`exercise_attempts`。首批且仅支持 `multiple_choice`、`true_false`、`short_answer`；不实现 cloze/ordering。题干、options、answer key、explanation 和引用均有严格大小/类型校验；普通 exercise/attempt-history response 不返回 `answer_key_json` 或 `answer_json`。exercise 有 `user_created`/`ai_generated` provenance，状态为 `draft/ready/rejected/stale/archived`，并支持 draft-only edit、confirm/reject/archive。8.4 可生成 cited AI exercise draft，但 provider output 必须是精确 JSON schema、每题只能引用本次 context 的 current revision citation，服务端重验后才落库；raw prompt/provider response 不保存。8.5 workspace 提供 set 选择、生成/编辑/确认/拒绝/归档和作答；answer key 仍不进入普通 DOM/API 响应。AI exercise 必须绑定 active current source revision 和 valid revision/chunk/span citation，confirm 会重新验证；delete/restore/purge/re-index 会反映 citation lifecycle。MC/TF 使用 deterministic grading 并 append-only 保存 attempts；short answer 只返回 `pending_review`，人工复核 API 和真实 Provider generation evidence 仍未实现；Phase 8 fake-provider backup/restore closeout 已通过。

## 12. Study plans

第二阶段：`study_plans`、`study_plan_items`。计划先是 draft，用户确认后 active；AI 重新规划生成新 draft，不覆盖已完成或用户编辑项。状态 draft/active/paused/completed/archived，item 记录 material/deck/exercise dependency、due date、timezone、estimated minutes。rename 不破坏依赖；source purge 后 item 标记 `source_unavailable`，不自动删除完成记录。当前不实现提醒、推送或自动 scheduler。

## 13. 第一阶段 API 与错误

第一阶段只实现/设计最小接口：

- `GET /api/ai/capabilities`：只返回 provider/model capability，不返回 secrets。
- `POST /api/materials/{id}/ai-index`：显式、同步骨架或未来 operation，输入有幂等 key；未实现前不自动调用。
- `GET /api/materials/{id}/ai-index`：返回 chunk/index 状态。
- `POST /api/qa/threads`、`GET /api/qa/threads`、`GET /api/qa/threads/{id}`、`POST /api/qa/threads/{id}/messages`：生成操作返回 operation id、retrieval run id 和 citations。

稳定错误还包括 `ai_operation_not_found`、`ai_operation_already_running`、`ai_operation_stale`、`retrieval_not_ready`、`retrieval_empty`、`retrieval_failed`、`context_budget_exceeded`、`citation_invalid`、`source_deleted`、`source_unavailable`、`chunk_not_ready`、`invalid_exercise_schema`、`invalid_card_payload`、`study_plan_conflict`。所有 provider/source 内容按不可信文本处理，禁止 HTML/SQL/命令执行。

## 14. Backup / restore

第一阶段没有外部向量索引，新增 SQLite 表天然进入现有 Online Backup API 和 manifest database snapshot。可重建的 FTS/chunk/embedding 仍需要 manifest 版本与显式 rebuild 命令；backup/verify/restore 都不调用 rebuild。若未来使用外部 vector DB，必须增加 index manifest、content hash、provider/model/policy 版本和离线 rebuild/verify，否则不引入。restore 保留历史 answer/card/attempt/plan 和 stale 状态，不把 stale 重新升级为 ready。

## 15. 明确技术决策

1. lexical FTS5 first，embedding later；
2. SQLite-first，不引入外部 vector DB；
3. 同步调用可先实现，但先持久化 `ai_operations`，为 worker 保留状态；
4. citation 独立表，不只存 JSON；payload/options 可暂时 JSON；
5. source revision 单独建表；
6. AI 生成内容必须 draft，不能直接 ready；
7. AI 生成默认必须有可验证 citation；
8. purge 后保留历史 artifacts，citation 标 unavailable；
9. provider response 原文默认不持久化，保留结构化结果、usage 和 operation metadata；
10. 单用户优先，user_id 暂不必填入所有表但保留未来迁移空间；
11. 第一阶段不引入后台队列；
12. backup/restore 只快照和验证，不 repair、不自动重新索引。

## 16. 路线图与验收

以下是 AI 子路线与项目主路线图的对应关系。项目主路线图的 Phase 4 是当前 AI 最小闭环；本节不再使用独立的 Phase 0/1/2 编号，避免与项目阶段冲突。

### 当前项目 Phase 4：AI 最小闭环

Provider Protocol、revision/chunk schema、deterministic chunker、显式 indexing、chunk FTS5、deterministic lexical retrieval、retrieval run/hit persistence、context assembly、citation contract、deterministic fake provider、同步 Q&A API/persistence、Q&A history、多材料范围、citation 详情/跨材料导航和完整浏览器 E2E 已实现并验证。Q&A 调用显式 scope retrieval、server-side citation verification，并持久化 operation/thread/user message/assistant message/answer/citation；purge 后历史 citation 标记 `source_unavailable`。Phase 4 已完成；真实 provider 和后续学习能力属于后续项目 Phase。

### 项目 Phase 5：真实 Provider 接入

通用 OpenAI-compatible provider adapter、环境配置、timeout/output limit、稳定错误映射、capability endpoint、provider request/usage/latency metadata 和 secret/error leakage tests 已实现并通过 mock HTTP 验证。v3 migration 增加 provider request ID、total tokens 和 finish reason；v4 增加显式 Idempotency-Key 与 retrieval run 关联，用于同步成功 replay。同步 Q&A 会在请求事务中将超过五分钟 lease 的 running operation 标记为 `stale/qa_operation_stale`，保留审计记录并允许同 key 重试；这不是后台扫描、跨进程协调或真实 crash recovery。DeepSeek 官方 `deepseek-chat` 已通过 adapter-level、完整 API-level synthetic smoke 和 Chromium UI/E2E；ARK、硅基流动、Agnes AI-Hub、Sub2API 的独立 capability matrix 已建立，但真实 provider-specific 验证仍待逐个完成。

### 项目 Phase 6 及以后：AI MVP 产品化与扩展

embedding provider、SQLite embedding payload、hybrid retrieval、rebuild/verify 和 stale semantics；Cards/Exercises backend MVP 的 draft、citation、user edit、schema validation、deterministic grading；plans 的 draft/confirm/active、dependency、progress；以及在需求明确后引入 worker、cancel、concurrency、observability 和 provider 长任务恢复。

## 17. 测试矩阵

Fake provider 覆盖未配置、timeout、rate-limit、auth/quota、malformed JSON、schema mismatch、refusal、oversized output、无 key 泄露。chunk 覆盖空文件、中文 offset、page/slide boundary、long span、overlap、revision/stale/delete/restore/purge。retrieval/RAG 覆盖 FTS AND、empty、top-k、citation mapping、context budget、伪造 citation、prompt injection boundary。Q&A 覆盖 duplicate submit、stale operation、历史保留、source unavailable 和安全渲染。cards/exercises/plans 覆盖 draft、user edit、invalid schema、deterministic grading、completed item 不被重写。backup/restore 覆盖新增表、stale 状态、verify no-repair、restore 后 citations/operations 保留。

## 18. 当前不实现

后续设计不自动索引历史材料、不引入外部 vector DB 或 worker；Phase 8 的人工简答复核、真实 Provider generation、系统级辅助技术和 plans 完整功能仍未实现。当前 Phase 4 的 AI 表、API、Q&A UI 和 browser 验收、Phase 7 retrieval/indexing 范围，以及 Phase 8 Cards/Exercises 的 fake-provider backend、Chromium workspace 和 backup/restore closeout 已完成；后续变更仍必须遵循项目主 Phase 路线和 migration 治理。
