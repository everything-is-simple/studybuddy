# Phase 7.1 现状审计与契约冻结

> 审计日期：2026-08-27
>
> 范围：`embeddings`、`retrieval_runs`、`retrieval_hits`、material revision/chunking、repository、migration、backup/restore。
>
> 结论：Phase 7.1 已完成契约冻结。本文的 schema version v4 是 2026-08-27 的历史审计基线；当前正式 schema 为 v9，Phase 7 已在后续独立 evidence 中完成精确范围 gate。

## 1. 审计结论

审计时数据库 schema version 为 **4**，migration history 为当时的 v1 `canonical_material_schema`、v2 `ai_phase0_schema`、v3 `phase5_provider_metadata`、v4 `qa_operation_idempotency`；这不是当前 schema 版本。当前正式 schema 为 v9，新增 v5–v9 history 已在后续 Phase 7/8/9A 任务中实现。`embeddings`、retrieval 的 embedding metadata 和 score 字段是 Phase 4 预留结构，不代表已有 embedding 生成或 vector retrieval。

当前真实 retrieval 路径是 `repository.run_chunk_retrieval()` 的 `lexical_fts_v1`：

- 只查询 `chunks_search` FTS5；ASCII 查询使用 token AND + BM25，Unicode/special-token 查询使用参数化 substring AND fallback；
- 只允许 active material、current revision、`ready` chunk；
- 结果按 score、`start_offset`、chunk id 稳定排序，`top_k` 范围为 1–50；
- 成功 run 写入 lexical score，vector/provider/rerank 字段为 NULL；
- 未建立 ready chunk 返回 `retrieval_not_ready`，没有命中返回 `retrieval_empty`；
- 不调用 embedding provider，不生成 query embedding，不读取 `embeddings` 表。

因此当前状态应记录为：**7.1 implemented / documentation-frozen；Phase 7 embedding/hybrid partial（仅有 lexical 前置能力）**。

## 2. 现有字段审计

### 2.1 `embeddings`

| 字段 | 当前定义/约束 | 当前使用 | 审计结论 |
|---|---|---|---|
| `id` | TEXT PK | 无业务写入/读取 | 保留，作为 embedding record id |
| `chunk_id` | TEXT NOT NULL，FK `chunks(id)`，cascade | 无 | 保留；检索必须再次验证 chunk 生命周期 |
| `provider_id` | TEXT NOT NULL | 无 | 保留，identity 的一部分 |
| `model_id` | TEXT NOT NULL | 无 | 保留，identity 的一部分 |
| `model_revision` | TEXT nullable | 无 | identity 需要；nullable + UNIQUE 在 SQLite 中不能可靠去重 |
| `dimensions` | INTEGER NOT NULL | 无 | 预留；必须与 payload 长度一致 |
| `vector_encoding` | TEXT NOT NULL | 无 | 预留；当前没有版本/codec 注册表 |
| `vector_payload` | BLOB nullable | 无 | 预留；当前没有 decode、长度、有限值校验 |
| `external_vector_id` | TEXT nullable | 无 | 当前不使用；Phase 7 SQLite-first 契约中保持 NULL，外部索引不属于本任务 |
| `content_hash` | TEXT NOT NULL | 无 | 预留；没有规定 hash 输入和 stale 判定 |
| `source_revision` | TEXT NOT NULL | 无 | 预留；冻结为 `material_revisions.id`，不是用户可见名称或 source hash |
| `status` | TEXT NOT NULL，无 CHECK | 无 | 需要状态约束和明确流转 |
| `error_code` | TEXT nullable | 无 | 预留；只保存稳定脱敏错误码，不保存 provider 原文 |
| `created_at` | TEXT NOT NULL | 无 | 保留，记录首次创建 |
| `UNIQUE(chunk_id, provider_id, model_id, model_revision, content_hash)` | 存在 | 未被业务使用 | 不足以表达 dimensions/encoding；`model_revision IS NULL` 时可出现重复 identity |

### 2.2 `retrieval_runs`

| 字段 | 当前使用 | 审计结论 |
|---|---|---|
| `id` | 每次 lexical retrieval 生成 `retrieval_<uuid>` | 保留，作为不可变审计记录 |
| `query` | 保存原始 query | 保留；受现有 query 长度限制，不保存 provider prompt |
| `normalized_query` | 当前为 `strip()` 后文本 | 保留；Phase 7 不能把它误称为 embedding normalization |
| `project_id` | lexical scope 过滤和持久化 | 保留，必须继续保证 project isolation |
| `thread_id` | 当前始终 NULL | 保留；后续接入时只能写入已验证的 thread，不改变现有 NULL 兼容性 |
| `policy_version` | 当前固定 `lexical_fts_v1` | 保留；Phase 7 使用新版本标识，不重解释历史 run |
| `embedding_provider_id` | 当前始终 NULL | 预留；只在该 run 实际生成/使用 query embedding 时写入 |
| `embedding_model_id` | 当前始终 NULL | 预留；必须与 query embedding identity 一致 |
| `status` | `succeeded` / `empty` / `failed` | 保留现有值；fallback 是成功的 retrieval result，原因写入 error/fallback metadata 设计，不把 lexical fallback 伪装成 vector success |
| `error_code` | `retrieval_not_ready` / `retrieval_empty` | 保留稳定错误语义；必要时扩展稳定 embedding/index 错误码 |
| `created_at` | 写入 UTC ISO timestamp | 保留 |

### 2.3 `retrieval_hits`

| 字段 | 当前使用 | 审计结论 |
|---|---|---|
| `run_id` / `chunk_id` | 每个成功 lexical hit 写入 | 保留 FK/PK；hit 不能绕过 chunk 生命周期验证 |
| `rank` | 1-based lexical result rank | 保留；表示最终 rank，不是候选 rank |
| `score` | 当前等于 `lexical_score` | 冻结为 final score；Phase 7 不改变历史含义 |
| `lexical_score` | 当前写入 lexical score | 保留，lexical-only 时与 final score 相同 |
| `vector_score` | 当前 NULL | 仅 vector candidate 实际参与时写入 cosine score |
| `rerank_score` | 当前 NULL | Phase 7.1 不启用 reranker；不因字段存在而宣称已支持 |
| `selected` | 当前成功 hit 写入 1 | 冻结为是否进入最终结果；未选候选若未来需要审计，必须另有明确写入策略 |
| `citation_label` | 当前为 `chunk-<rank>` | 保留历史语义；citation key 仍由 context assembler/server validation 产生，不能由模型创建 |

### 2.4 chunking、repository 与生命周期

- `chunking.py` 当前策略为 `boundary_window`、版本 `1.0.0`；chunk 文本是 extraction text 的 Unicode code-point 切片，`normalized_text` 为 whitespace collapse + casefold。
- `chunks` 状态已有 `pending`、`ready`、`failed`、`stale`、`deleted`，但当前 indexing 主要创建 `ready`，重复 indexing 复用已有 ready chunks。
- current revision 由 `material_revisions.is_current = 1` 表达；material soft delete 由 `materials.deleted_at` 表达；purge 通过 FK cascade 删除派生 chunks，并保留历史 QA/citation 的 unavailable 状态。
- `chunks_search` 连接时会补齐/删除有效 ready rows，但这是 lexical index repair，不是 embedding rebuild，也不应在 startup 触发 embedding provider。
- `run_chunk_retrieval()` 是当前唯一真实 retrieval implementation；API `POST /api/retrieval` 只暴露 query/material scope/top_k，没有 retrieval mode 或 policy 参数。

## 3. 未使用字段与兼容性风险

### 未使用或仅预留

- `embeddings` 整张表目前没有 production write/read path。
- `embeddings.external_vector_id` 当前明确未使用；Phase 7 不引入外部 vector index。
- `retrieval_runs.thread_id` 当前由 retrieval helper 固定为 NULL。
- `retrieval_runs.embedding_provider_id`、`embedding_model_id` 当前固定为 NULL。
- `retrieval_hits.vector_score`、`rerank_score` 当前固定为 NULL；`score` 目前只是 lexical score。

### 风险

1. **identity 不完整**：现有 UNIQUE 未包含 dimensions 和 vector encoding/version；同一 chunk/provider/model/content 在维度或 codec 改变后不能可靠区分。
2. **NULL 去重风险**：SQLite 对 UNIQUE 中的 NULL 允许多行，`model_revision` 为 NULL 时不能达到“一条 identity 一条记录”。
3. **status 无约束**：任意字符串可写入，无法依赖数据库保证 `ready/stale/failed/running` 契约。
4. **payload 不可验证**：没有 codec version、byte order、precision、payload length、finite-value 校验；损坏 BLOB 可能在未来检索时导致不稳定行为。
5. **source binding 未执行**：`content_hash` 和 `source_revision` 没有由 chunk 写入流程计算或比对，旧 embedding 目前不会自动变 stale。
6. **历史 policy 兼容性**：`lexical_fts_v1` 的 `score`/rank 语义不能被未来 hybrid 重新解释；未来必须使用新的 policy version。
7. **生命周期边界**：任何 vector candidate 查询必须重复 active/current/ready 过滤；不能仅依赖 embedding FK，因为 soft delete 和 superseded revision 不会触发 FK 删除。
8. **backup coverage 尚无 embedding 专项证据**：SQLite Online Backup 会包含该表，但当前测试没有写入 embedding 后验证 payload、status、stale 保留。恢复不得自动 rebuild 或把 stale 升级为 ready。

## 4. 冻结的 embedding 契约

### 4.1 Identity

一条 embedding 的 canonical identity 是：

```text
(chunk_id, source_revision, content_hash, provider_id, model_id,
 model_revision, dimensions, vector_encoding)
```

语义固定如下：

- `chunk_id` 必须属于 active material 的 current revision 且 chunk status 为 `ready`；
- `source_revision` 固定使用对应 `material_revisions.id`；
- `content_hash` 固定为 embedding 输入文本的 SHA-256。Phase 7.1 不改变 chunk source；实现时必须在写入前定义规范化输入并测试；
- `provider_id`、`model_id`、`model_revision` 是 provider 返回/配置的模型身份。缺失 revision 必须规范化为稳定的空字符串或明确版本标识，不能继续使用 nullable identity；
- `dimensions` 必须为正整数，且等于 decoded vector 长度；
- `vector_encoding` 必须包含 codec/version，例如后续冻结为明确的 `f32 little-endian` 版本值；encoding 改变即 incompatible/stale；
- 相同 identity 的 ready embedding 必须幂等复用，不重复调用 provider；不同任一 identity 字段不得静默复用。

### 4.2 Status 与 stale

embedding status 冻结为四态：

- `running`：本次显式 indexing 已开始但尚未完成；默认不可检索；
- `ready`：identity、payload、dimensions、finite values、source binding 全部验证通过；允许参与 vector retrieval；
- `stale`：历史 payload 可保留用于诊断，但 content hash、source revision、provider/model/revision、dimensions 或 encoding 与当前 policy 不一致；默认不可检索；
- `failed`：provider、响应、codec 或 dimension 校验失败；默认不可检索；`error_code` 只存稳定脱敏码。

状态流转固定为 `running -> ready|failed`，已有 `ready -> stale`；重试应创建/更新同一 identity 的显式 operation 记录，不把失败或 stale 静默升级为 ready。删除/purge 遵循 chunk FK/lifecycle；不得留下可参与检索的 orphan。

## 5. 冻结的 retrieval policy

Phase 7 使用新的、可版本化的 policy 名称；`lexical_fts_v1` 只表示已有 lexical 行为。建议首批固定为 `lexical_fts_v1`、`vector_cosine_v1`、`hybrid_rrf_v1` 和 `fallback_lexical_v1`，具体常量在实现任务中落代码并测试。

所有 policy 共享以下规则：active material、current revision、ready chunk 是硬过滤；top-k、候选池大小、分数精度、tie-breaker 必须由 policy 固定；最终相同分数按 `chunk_id`（必要时先按 material/revision/chunk index）稳定排序；run/hit 必须保存足以解释 provider/model/policy 和 lexical/vector/final scores 的 metadata，但不保存不必要正文。

### `lexical-only`

只运行现有 FTS5/Unicode lexical 路径。embedding 配置、embedding 表和 provider 可用性都不影响结果。命中为 `succeeded`，无命中为 `retrieval_empty`，没有 ready chunk 为 `retrieval_not_ready`。历史 `lexical_fts_v1` 结果保持原含义。

### `vector-only`

必须为 query 生成 embedding，并只使用匹配 identity 且 status=`ready` 的 chunk embedding 做 cosine similarity。query embedding 或 vector index 不可用时返回稳定 embedding/index error，不自动改为 lexical；没有 candidate 返回 `retrieval_empty`。vector-only 的 run 必须记录实际 provider/model。

### `hybrid`

独立生成 lexical candidates 和 vector candidates，再按版本化 hybrid policy 合并。Phase 7 首个冻结策略采用可解释、确定性的 Reciprocal Rank Fusion（RRF）；实现时固定 lexical/vector candidate pool、RRF 常数、最终 top-k 和 tie-breaker。命中同时记录 lexical/vector/final score；缺少某一路候选不等于凭空补分。

### `fallback`

fallback 不是第三种排序算法，而是 hybrid/vector 请求在 embedding provider 未配置、不可用、超时、invalid response、dimension mismatch 或 embedding index unavailable 时的降级行为。默认 fallback 目标是 lexical-only：返回 lexical 成功/empty 结果，并在 retrieval run 中记录脱敏 fallback reason/policy。若 lexical 也没有 ready scope，仍返回 `retrieval_not_ready`；无命中仍返回 `retrieval_empty`。fallback 不适用于显式 vector-only，除非调用方选择另一个明确允许 fallback 的 policy。

## 6. 需要新增的 migration

7.1 **当时不执行 migration**；本节记录的是 2026-08-27 的历史审计决策，审计时 schema 保持 v4。后续 Phase 7 已通过连续 v5/v6 等 migration 实现，并由当前 v9 schema history 保持一致；本节的 v5 proposal 不应被理解为当前未实现待办。

1. 重建/调整 `embeddings`，使 canonical identity 能表达 `dimensions` 与 `vector_encoding`，并将 model revision 从 nullable identity 规范化为非 NULL 稳定值；
2. 为 `status` 增加数据库 CHECK（仅 `running/ready/stale/failed`），并保留 `error_code`；
3. 增加 `updated_at`，用于 running/ready/stale/failed 状态变更审计；
4. 增加或明确覆盖 `(chunk_id, source_revision, content_hash, provider_id, model_id, model_revision, dimensions, vector_encoding)` 的唯一约束/索引；
5. 如实现需要在 `retrieval_runs` 持久化 fallback reason、query dimensions 或 policy parameters，必须通过同一或后续连续 migration 明确新增字段，不能运行时 ALTER/CREATE；
6. 为旧 v4 数据保留兼容升级路径：当前表为空时是主要路径；若存在 rows，迁移必须校验/规范化，无法证明 identity 的记录不得静默变成 ready，应标为 stale/failed 并可诊断；
7. backup/restore 继续只快照数据库，不自动 rebuild；补充带 embedding rows、stale rows 和损坏/失败状态的 restore 验收。

migration 必须保持 `schema_migrations` 与 `PRAGMA user_version` 一致、连续、事务化、幂等；失败必须整体 rollback。7.1 不修改 `CURRENT_SCHEMA_VERSION`，也不修改现有 v1-v4 migration history。

## 7. 后续实现验收门槛

在 7.2–7.5 完成前，不能声称支持 embedding/hybrid。至少需要 provider/fake determinism、payload round-trip 与损坏边界、v5 upgrade/rollback/idempotence、stale 判定、indexing 去重/重试/verify、cosine/RRF tie-breaker、fallback/empty、生命周期过滤和 backup/restore 证据。当前 lexical-only retrieval 与 Q&A citation contract 必须全程保持回归通过。
