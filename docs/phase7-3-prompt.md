# StudyBuddy Phase 7.3 执行 Prompt：Embedding Schema、Payload Codec 与 Stale Semantics

> 用途：将本文完整复制给 coding agent，继续在 `H:\studybuddy` 内实现并验收 Phase 7.3。
>
> 范围：只完成 embedding schema、payload codec、identity 和 stale semantics。不要提前宣称 Phase 7 completed；vector/hybrid、真实 provider、完整 rebuild/verify、Q&A/UI 接入仍属于后续任务。

---

## 0. 角色与执行方式

你是 StudyBuddy 仓库中的资深 SQLite migration、数据完整性、embedding storage 和测试工程师。请直接修改代码、正式测试和文档，不要只给设计方案。

必须：

1. 先阅读根目录 `AGENTS.md`。
2. 完整阅读并遵守：
   - `README.md`
   - `docs/PHASE7_1_AUDIT_AND_CONTRACT.md`
   - `docs/phase7-prompt.md`
   - `docs/phase7-2-prompt.md`
   - `docs/PHASE_ROADMAP.md`
   - `docs/STATUS.md`
   - `docs/TODO.md`
   - `docs/PROJECT_PROGRESS_REPORT.md`
   - `docs/ai-learning-architecture.md`
   - `backend/app/migrations/runner.py`
   - `backend/app/embedding.py`
   - `backend/app/repository.py`
   - `backend/app/backup.py`
   - 相关 migration、embedding、indexing、retrieval、backup/restore 测试
3. 先执行：
   ```text
   git status --short
   git diff --stat
   git log -5 --oneline
   D:\miniconda\py310\python.exe -m pytest backend/tests/
   ```
4. 不覆盖工作区已有用户改动；不重写已有 migration history；不提交数据库、原文件、secret、provider key、私有路径、测试 artifact 或输出文件。
5. 先写 focused tests，再实现，再运行 focused suite 和完整 backend suite。
6. 诚实区分 `implemented`、`backend-tested`、`browser-tested`、`real-pass` 和 `not_verified`。

---

## 1. 当前基线

当前仓库已经完成并推送：

```text
849c304 feat: complete phase 7.2 embedding provider foundation
```

当前已存在：

### Schema

- schema version 为 v5；
- migration history：
  ```text
  1 canonical_material_schema
  2 ai_phase0_schema
  3 phase5_provider_metadata
  4 qa_operation_idempotency
  5 phase7_embedding_schema
  ```
- v5 已重建 `embeddings` 表；
- `model_revision` 为非 NULL；
- `status` 有 `running/ready/stale/failed` CHECK；
- `updated_at` 已存在；
- canonical unique identity 已包含：
  ```text
  chunk_id, source_revision, content_hash, provider_id, model_id,
  model_revision, dimensions, vector_encoding
  ```
- v5 对旧 rows 的处理不会静默把旧 `running/ready` 变为 ready，而是转为 stale；未知 status 转为 failed。

### Embedding module

`backend/app/embedding.py` 已有：

- `EmbeddingError`；
- `EmbeddingProvider` protocol；
- `FakeEmbeddingProvider`；
- `normalize_embedding_text()`；
- `embedding_content_hash()`；
- `encode_vector()` / `decode_vector()`；
- `cosine_similarity()`；
- `f32le_v1`；
- `sha256_bucket_v1`；
- deterministic fake provider；
- finite、非零、dimensions、payload length 校验。

### Provider/config

`backend/app/providers.py` 和 `backend/app/config.py` 已有：

- 独立 `EmbeddingProviderRegistry`；
- fake embedding capabilities；
- embedding 环境变量：
  ```text
  STUDYBUDDY_EMBEDDING_PROVIDER
  STUDYBUDDY_EMBEDDING_MODEL
  STUDYBUDDY_EMBEDDING_MODEL_REVISION
  STUDYBUDDY_EMBEDDING_TIMEOUT_SECONDS
  STUDYBUDDY_EMBEDDING_MAX_BATCH_SIZE
  STUDYBUDDY_EMBEDDING_MAX_TEXT_CHARS
  STUDYBUDDY_EMBEDDING_MAX_DIMENSIONS
  STUDYBUDDY_EMBEDDING_MAX_RESPONSE_BYTES
  STUDYBUDDY_EMBEDDING_MAX_RETRIES
  ```
- `/api/ai/capabilities` 在显式 embedding 配置时返回安全 embedding descriptor；未配置时保留 LLM legacy response shape。

### Indexing/vector 当前能力

`backend/app/repository.py` 已有：

- `index_embeddings_for_material()`；
- embedding identity 查询和 upsert；
- fake indexing；
- `run_vector_retrieval()` 的最小 vector-only 路径。

注意：这些代码是 Phase 7 foundation，不代表 7.3 已经完整。需要审计并补齐 payload/stale 语义，不能只增加测试绕过缺陷。

### 测试基线

Phase 7.2 后曾通过：

```text
focused: 25 passed
full backend: 208 passed, 2 skipped, 1 warning
```

实现前必须重新运行当前工作区测试。

---

## 2. Phase 7.3 目标

实现一个可审计、可验证、可安全失效的 embedding persistence contract：

```text
ready chunk
  → canonical embedding input normalization
  → content hash + source revision identity
  → provider/model/dimensions/encoding identity
  → validated binary payload
  → ready/stale/failed/running state
  → retrieval only when all binding checks pass
```

必须交付：

1. schema 与 migration 审计和必要补齐；
2. canonical embedding identity；
3. payload codec contract；
4. encode/decode 的完整 malformed boundary；
5. stale 判定函数和调用路径；
6. ready-only / source-binding 安全过滤；
7. migration rollback、idempotence、backup/restore evidence；
8. focused tests 与文档收口。

本任务不做：

- 新的外部 vector database 或 ANN；
- 真实网络 embedding provider；
- hybrid RRF；
- 完整 rebuild/verify CLI（可以为后续 7.4 提供可复用判定函数）；
- Q&A 全链路改写；
- startup 自动 embedding；
- 多 worker、多进程、后台队列。

---

## 3. 冻结的 canonical identity

一条 embedding 的唯一 identity 必须是：

```text
(
  chunk_id,
  source_revision,
  content_hash,
  provider_id,
  model_id,
  model_revision,
  dimensions,
  vector_encoding
)
```

固定语义：

- `chunk_id` 必须是当前 material revision 的 chunk；
- `source_revision` 必须是对应 `material_revisions.id`，不能使用展示名称、source hash 或时间代替；
- `content_hash` 必须是 embedding 输入文本规范化后的 UTF-8 SHA-256；
- `provider_id`、`model_id`、`model_revision` 必须是稳定、非空字符串；
- `model_revision` 不允许 nullable identity；缺失时只能在 provider/config 边界规范化为明确稳定值；
- `dimensions` 必须是正整数且不超过硬上限；
- `vector_encoding` 必须包含 codec/version，例如 `f32le_v1`；
- dimensions 或 encoding 改变即为不同 identity；不能静默复用旧 payload；
- 相同 identity 的 ready row 必须幂等复用；
- 不同任一 identity 字段不能静默复用；
- `external_vector_id` 在 SQLite-first Phase 7 中保持 NULL，除非有正式 migration 和明确外部索引设计；本任务不要启用它。

建议集中定义：

```python
@dataclass(frozen=True)
class EmbeddingIdentity:
    chunk_id: str
    source_revision: str
    content_hash: str
    provider_id: str
    model_id: str
    model_revision: str
    dimensions: int
    vector_encoding: str
```

如果当前项目风格不适合 dataclass，可以采用等价 tuple/key builder，但必须避免不同调用方各自拼 SQL identity。

identity 校验应拒绝：

- 空字符串；
- 控制字符；
- 超长 provider/model/revision/encoding；
- bool 冒充 dimensions；
- dimensions <= 0 或超过 `MAX_EMBEDDING_DIMENSIONS`；
- content hash 非固定长度 hex；
- source revision/chunk id 不符合当前项目安全 ID 语义。

错误只返回稳定错误码，不返回原始 SQL、路径或正文。

---

## 4. Embedding input normalization 与 content hash

当前已有：

```python
normalize_embedding_text(text) -> " ".join(text.split())
embedding_content_hash(text) -> sha256(normalized.encode("utf-8")).hexdigest()
```

请审计并冻结以下语义：

- 前后空白被去除；
- 连续 Unicode whitespace 被折叠为单个 ASCII space；
- 同一 normalized text 得到同一 hash；
- query normalization 和 embedding content normalization 必须概念分开；
- 不修改 `chunks.text`、extractions.text 或原始材料；
- 不把正文写入日志、error_code、embedding metadata 或 capabilities；
- 空文本、全 whitespace 必须明确为 `embedding_invalid_request` 或项目正式等价错误；
- content hash 的输入必须在测试中可见且稳定，但测试不得提交真实私有材料。

必须增加测试：

- ASCII whitespace；
- tab/newline；
- Unicode whitespace；
- 同内容不同 whitespace；
- Unicode emoji/非 ASCII；
- empty/whitespace；
- hash 长度和 lowercase hex；
- 原文未被修改。

---

## 5. Payload codec contract

当前 codec 名称冻结为：

```text
f32le_v1
```

必须在代码 docstring/正式文档中明确：

- 每个元素为 IEEE-754 32-bit float；
- little-endian；
- payload 长度必须严格等于 `dimensions * 4`；
- decode 结果必须恰好为 dimensions 个 finite float；
- vector 不得为空、不得为全零；
- 不接受 NaN 或 Infinity；
- encode/decode 失败使用稳定 `EmbeddingError.code`；
- codec version 改变即 incompatible，不得按旧 codec 猜测解析。

推荐稳定错误码：

```text
embedding_invalid_dimensions
embedding_invalid_vector
embedding_payload_length_mismatch
embedding_payload_invalid
embedding_encoding_unsupported
embedding_payload_too_large
```

### encode 要求

`encode_vector(values, dimensions/encoding 可选)` 应：

- 拒绝非 list/tuple；
- 拒绝空 vector；
- 拒绝 bool、非数字、NaN、Infinity；
- 拒绝 dimensions 超限；
- 拒绝全零；
- 防止 float32 pack overflow 或转换异常；
- 若允许 int，必须明确转换为 float；
- 不允许静默截断维度；
- 对 unsupported encoding 返回稳定错误。

### decode 要求

`decode_vector(payload, dimensions, encoding="f32le_v1")` 应：

- 拒绝非 bytes/bytearray；
- 严格校验 dimensions；
- 严格校验 payload length；
- 拒绝截断、额外 bytes、空 bytes；
- 捕获 `struct.error`；
- 解码后再次校验 finite、非零、dimensions；
- 不让损坏 payload 冒泡为 500 traceback 或进程崩溃。

### payload size

必须执行 payload size 上限：

```text
expected_bytes = dimensions * 4
expected_bytes <= configured max response/payload boundary
```

不要无限读取或无限分配内存。若当前 AppConfig 没有专门 payload max，可复用并明确文档化 `embedding_max_response_bytes`，但必须保证上限不小于合法 configured dimensions payload，或返回稳定配置错误。

### round-trip

测试：

- normal vector round trip；
- negative/positive float；
- float32 precision 使用 `pytest.approx`；
- dimensions 1、32、最大合法值和超限；
- wrong dimensions；
- truncated payload；
- payload extra bytes；
- unsupported encoding；
- NaN/Infinity；
- all-zero；
- malformed object；
- oversized payload。

---

## 6. Schema / migration 要求

### 6.1 先审计现有 v5

不要盲目新增 v6。先确认 v5 已真实满足：

- `model_revision NOT NULL`；
- status CHECK；
- updated_at；
- canonical unique identity；
- ready lookup index；
- old rows safe downgrade to stale/failed。

如果 v5 已满足 Phase 7.3 schema 基线，不应创建无意义 migration；应在 repository/codec/test 层补齐。只有发现真实 schema gap，才增加连续 v6 migration，并说明理由。

### 6.2 若需要 v6

必须：

- 版本连续；
- migration name 稳定；
- idempotent；
- transaction boundary 由现有 runner 管理；
- failure rollback；
- user_version/history 一致；
- old v5 database upgrade；
- repeated startup 不新增 history row；
- backup/restore history/version preserved。

不得：

- 在 `repository.py`、startup、测试 fixture ad-hoc `CREATE TABLE` 或 `ALTER TABLE`；
- 手动修改 `schema_migrations` 或 operator workflow version；
- 删除无法证明安全的旧 embedding rows；
- 将旧 unknown/invalid rows 静默标记 ready。

### 6.3 v5 legacy rows

已有 v5 migration 对旧数据有安全转换。请补测试覆盖：

- v4 → v5；
- v5 空 embeddings；
- v5 ready row；
- v5 stale row；
- v5 failed row；
- unknown status；
- nullable/empty model revision legacy row；
- duplicate identity legacy input；
- migration failure rollback；
- second run idempotence。

如果旧 ready row 缺少 payload、identity 或 source binding 证据，必须保持 stale/failed，不得变 ready。

---

## 7. Stale semantics

实现集中、可复用的判定逻辑，例如：

```python
def embedding_staleness(
    embedding_row,
    *,
    expected_identity: EmbeddingIdentity,
    payload_valid: bool,
) -> str | None:
    """Return stable stale/error reason, or None when ready is valid."""
```

判定顺序必须稳定并测试。至少覆盖：

1. content hash 不一致；
2. source revision 不一致；
3. provider id 不一致；
4. model id 不一致；
5. model revision 不一致；
6. dimensions 不一致；
7. encoding 不一致；
8. payload missing；
9. payload length mismatch；
10. payload malformed/nonfinite/zero；
11. chunk 不存在；
12. chunk revision 不匹配；
13. material deleted；
14. revision 非 current；
15. chunk 非 ready；
16. embedding status 非 ready。

建议稳定 reason：

```text
embedding_content_hash_stale
embedding_source_revision_stale
embedding_provider_stale
embedding_model_stale
embedding_model_revision_stale
embedding_dimensions_stale
embedding_encoding_stale
embedding_payload_missing
embedding_payload_invalid
embedding_chunk_missing
embedding_revision_mismatch
embedding_source_deleted
embedding_source_not_current
embedding_chunk_not_ready
embedding_status_unavailable
```

注意：

- stale reason 与 `EmbeddingError.code` 可以共用或分开，但必须稳定、脱敏；
- stale row 可以保留用于诊断；
- stale row 默认不得参与 retrieval；
- 不要在普通 retrieval 请求中把所有 stale rows 反复写回数据库导致隐式 mutation，除非已有明确事务和测试；可以先计算不可用 reason，7.4 再提供显式 verify/repair；
- `ready` 只有在 identity + payload + source binding 全部通过时才允许。

### stale transition

固定状态行为：

```text
running → ready | failed
ready → stale
stale → running（仅显式 retry/rebuild）
failed → running（仅显式 retry/rebuild）
```

本任务至少实现或提供：

- `is_embedding_ready_for_retrieval()`；
- `mark_embedding_stale()` 或等价 repository helper；
- 不能把 failed/stale 自动升级 ready；
- ready identity 幂等复用；
- identity 改变创建新 row 或显式更新同 identity，不能覆盖另一 identity；
- purge 依赖 FK cascade 清除 embedding；soft delete 不允许 embedding 继续参与检索。

---

## 8. Repository / indexing 接入要求

审计 `index_embeddings_for_material()` 并补齐：

- 输入文本 hash 和 provider identity 必须统一使用 canonical helper；
- encode 前验证 vector dimensions；
- encode 后验证 payload dimensions/size；
- 同 identity ready row：skip，不调用 provider；
- 同 chunk 旧 identity：标记 stale 或保留不可用旧 row，不能复用；
- provider 失败：只写稳定 error code，不写 raw exception；
- vector malformed：failed，不进入 ready；
- transaction rollback 不留下半成品 ready；
- 失败 row 不影响其他材料和 lexical retrieval；
- current/deleted/ready chunk 过滤必须与 lexical contract 一致。

如果当前 `index_embeddings_for_material()` 仍在一个 provider batch 失败时把整个 batch 全部写 failed，需明确这是当前批次 atomic policy，或改为部分成功；无论选择哪一个，都必须在文档和测试中固定，不能出现“返回 ready 但其中部分 failed”的含糊状态。

不要在本任务引入 startup 自动 indexing。

---

## 9. Retrieval safety contract

本任务不实现 hybrid，但必须确保现有 vector-only 最小路径不绕过 stale 语义：

- SQL 层过滤 `e.status='ready'`；
- provider/model/model revision/dimensions/encoding 必须匹配当前 provider；
- `content_hash` 必须等于当前 normalized chunk text hash；
- `source_revision` 必须等于 current revision；
- material `deleted_at IS NULL`；
- chunk `status='ready'`；
- chunk 属于当前 material revision；
- decode 失败的 ready row 必须被视为不可用，不能让 retrieval 崩溃；
- 无可用 candidate 返回既有稳定 empty/not-ready 语义；
- 不改变既有 lexical retrieval 的历史 score/rank 含义。

如果发现 vector retrieval 在 decode/identity mismatch 时会直接抛异常，请修复为安全不可用路径并增加测试。

---

## 10. Backup / restore

SQLite Online Backup 理论上会复制 embeddings，但必须增加实际证据：

1. 创建包含：
   - ready embedding；
   - stale embedding；
   - failed embedding；
   - 至少一个合法 payload；
2. 执行 backup；
3. `verify_backup`；
4. restore 到新空目录；
5. 检查：
   - schema version/history；
   - embedding row count；
   - status 保留；
   - payload bytes 保留；
   - identity 保留；
   - stale 不被升级为 ready；
   - restore 不自动调用 provider/rebuild；
6. 恢复后 vector retrieval 只能使用合法 ready row。

不得提交数据库或 backup artifact；使用 pytest tmp_path。

---

## 11. 测试交付清单

至少新增或补充：

### Identity / normalization

- identity helper 相同输入相等；
- 任意 identity 字段改变会被识别；
- revision/provider/model/dimensions/encoding 变化；
- whitespace normalization；
- Unicode/emoji；
- empty/whitespace；
- hash 不泄露正文。

### Codec

- round trip；
- precision；
- endian/encoding version；
- dimensions mismatch；
- truncation；
- extra bytes；
- NaN/Infinity；
- zero vector；
- invalid types；
- max dimensions；
- oversized payload；
- stable error codes。

### Migration

- fresh v5 schema；
- v4→v5；
- history/version consistency；
- idempotence；
- rollback on failed migration；
- legacy statuses；
- duplicate/invalid legacy identity；
- backup/restore history。

### Stale

- content hash stale；
- source revision stale；
- provider/model/revision stale；
- dimensions/encoding stale；
- missing/corrupt payload；
- deleted material；
- superseded revision；
- non-ready chunk；
- failed/running status；
- ready-only retrieval filter。

### Indexing

- identical ready skip；
- changed identity not reused；
- failed row stable error；
- malformed output never ready；
- transaction failure rollback；
- purge cascade；
- soft delete exclusion。

### Backup

- ready/stale/failed rows survive backup/restore；
- payload byte equality；
- provider not called on restore；
- stale not promoted。

### Regression

```text
D:\miniconda\py310\python.exe -m pytest backend/tests/test_embedding.py backend/tests/test_migrations.py backend/tests/test_ai_indexing.py backend/tests/test_retrieval.py backend/tests/test_backup_restore.py backend/tests/test_ai_backup_restore.py
D:\miniconda\py310\python.exe -m pytest backend/tests/
```

如 API 行为、capabilities 或 UI 状态变化，再运行对应 provider/Q&A Chromium focused E2E；没有浏览器证据不要宣称 browser-tested。

---

## 12. 文档收口

更新：

- `docs/PHASE_ROADMAP.md`；
- `docs/STATUS.md`；
- `docs/TODO.md`；
- `docs/PROJECT_PROGRESS_REPORT.md`；
- 必要时 `docs/ai-learning-architecture.md`。

文档必须说明：

- Phase 7.3 是 `implemented / backend-tested` 还是 `partial`；
- v5 是否已经足够，是否新增 v6；
- `f32le_v1` 的精确定义；
- stale 语义和 ready-only retrieval；
- backup/restore 的实际证据；
- 真实 provider、hybrid、rebuild/verify、Q&A/UI 等未完成范围。

---

## 13. 完成判定

只有满足以下条件，Phase 7.3 才能标记 `implemented / backend-tested`：

1. canonical identity 有单一实现并被 indexing/retrieval 使用；
2. schema/migration 真实支持 identity、status、updated_at 和诊断字段；
3. payload codec 的 encoding、endianness、precision、length 和 finite rules 已冻结并测试；
4. 损坏 payload、dimension mismatch、NaN/Infinity、zero vector 不会进入 ready 或导致请求崩溃；
5. stale 判定覆盖 content/revision/provider/model/dimensions/encoding/source lifecycle；
6. ready-only retrieval 强制检查 identity 和 source binding；
7. failed/stale 不会静默变 ready；
8. indexing 幂等、失败和 transaction boundary 有测试；
9. backup/restore 保留 embedding row、payload、status、identity 和 schema history；
10. focused tests 和完整 backend suite 通过；
11. 文档与实际实现一致。

如果只完成 codec 或只完成 schema，必须标记 `partial`。

Phase 7.3 完成不等于 Phase 7 完成。Phase 7 仍需 7.4 indexing/rebuild/verify、7.5 vector/hybrid/fallback、7.6 Q&A/citation/API/UI 和 7.7 最终基线与验收。

---

## 14. 最终报告格式

完成后按以下结构报告：

1. 实现摘要；
2. 修改文件；
3. schema/migration 结论；
4. canonical identity 和 normalization；
5. payload codec 规则和错误码；
6. stale semantics 与 retrieval safety；
7. indexing/transaction/backup evidence；
8. focused/full backend/Chromium 测试结果；
9. 未验证限制；
10. Phase 7.3 判断：`implemented` / `partial` / `blocked`；
11. Phase 7 剩余任务。
