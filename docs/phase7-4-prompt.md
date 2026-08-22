# StudyBuddy Phase 7.4 执行 Prompt：Embedding Indexing、Rebuild、Verify 与生命周期

> 用途：将本文完整复制给 coding agent，继续在 `H:\studybuddy` 内实现并验收 Phase 7.4。
>
> 范围：只完成 embedding 的显式 indexing、增量 rebuild、verify、retry/lifecycle 和相关 backup/restore/test/documentation 收口。不要提前实现或宣称 Phase 7.5 hybrid RRF、Phase 7.6 Q&A/citation/UI 接入或 Phase 7 completed。

---

## 0. 角色与执行方式

你是 StudyBuddy 仓库中的资深 SQLite、数据生命周期、embedding indexing、可验证性和测试工程师。请直接修改 production code、正式测试和文档，不要只给设计方案。

必须：

1. 先阅读根目录 `AGENTS.md`，并遵守其中所有 repository、migration、testing、deployment 和安全边界。
2. 完整阅读：
   - `README.md`
   - `docs/PHASE7_1_AUDIT_AND_CONTRACT.md`
   - `docs/phase7-prompt.md`
   - `docs/phase7-2-prompt.md`
   - `docs/phase7-3-prompt.md`
   - `docs/PHASE_ROADMAP.md`
   - `docs/STATUS.md`
   - `docs/TODO.md`
   - `docs/PROJECT_PROGRESS_REPORT.md`
   - `docs/ARCHITECTURE.md`
   - `docs/ai-learning-architecture.md`
   - `backend/app/embedding.py`
   - `backend/app/providers.py`
   - `backend/app/config.py`
   - `backend/app/repository.py`
   - `backend/app/main.py`
   - `backend/app/backup.py`
   - `backend/app/migrations/runner.py`
   - 相关 chunk、embedding、indexing、retrieval、migration、backup/restore、provider 测试
3. 先执行并记录：
   ```text
   git status --short
   git diff --stat
   git log -5 --oneline
   D:\miniconda\py310\python.exe -m pytest backend/tests/
   ```
4. 当前 HEAD 预期为：
   ```text
   2e77728 feat: complete phase 7.3 embedding semantics
   ```
5. 不覆盖工作区已有用户改动；不要提交 `.backup/`、`.pi/`、数据库、上传原件、provider key、secret、私有路径、测试 artifact、临时输出或生成文件。
6. 先审计现有实现和测试契约，再写 focused tests；实现后运行 focused suite 和完整 backend suite。
7. 诚实区分 `implemented`、`backend-tested`、`browser-tested`、`real-pass`、`not_verified`。Phase 7.4 完成不等于 Phase 7 完成。

---

## 1. 当前基线与已有能力

Phase 7.1–7.3 已完成并推送，当前已有：

### Schema

当前 schema version 为 v5，migration history：

```text
1 canonical_material_schema
2 ai_phase0_schema
3 phase5_provider_metadata
4 qa_operation_idempotency
5 phase7_embedding_schema
```

`embeddings` 已具备：

- `id`、`chunk_id`、`provider_id`、`model_id`、`model_revision`；
- `dimensions`、`vector_encoding`、`vector_payload`；
- `content_hash`、`source_revision`；
- `status`：`running`、`ready`、`stale`、`failed`；
- `error_code`、`created_at`、`updated_at`；
- canonical unique identity：
  ```text
  (chunk_id, source_revision, content_hash, provider_id, model_id,
   model_revision, dimensions, vector_encoding)
  ```
- ready lookup index；
- foreign key cascade 到 chunk。

先审计 v5 是否确实满足 Phase 7.4 需求。只有发现真实 schema gap 才新增连续 v6 migration；不要为 rebuild/verify 无意义地新增 migration。

### Embedding foundation

`backend/app/embedding.py` 已有并冻结：

- `EmbeddingError` 和稳定 error code；
- `EmbeddingProvider` protocol；
- 独立 provider registry 使用的 fake embedding；
- `EmbeddingIdentity` canonical helper；
- `normalize_embedding_text()`；
- `embedding_content_hash()`；
- `encode_vector()` / `decode_vector()`；
- `cosine_similarity()`；
- `embedding_staleness()`；
- encoding：`f32le_v1`；
- fake algorithm：`sha256_bucket_v1`；
- deterministic、离线、无随机数、无 Python 内置 `hash()`。

### Current indexing/vector boundary

`backend/app/repository.py` 已有：

- `index_embeddings_for_material()`：同步、显式、SQLite-first；
- 同一 identity 的 ready skip/upsert；
- provider batch embedding；
- malformed vector / provider error 的 failed path；
- `run_vector_retrieval()` 最小 vector-only 路径；
- ready-only、source binding、identity 和 payload safety checks。

这些不代表 7.4 已完成。必须审计当前 indexing 的 transaction、状态转换、失败恢复、增量范围、verify 能力和生命周期一致性。

### Deployment boundary

本 Phase 不引入：

- startup 自动 indexing；
- 后台任务队列；
- 多 worker、多进程协调；
- 外部 vector DB、ANN、隐藏 index 文件；
- cloud sync 或共享 data root。

推荐实现为同步显式 repository/service/API/CLI 边界，调用者明确触发并等待结果。

---

## 2. Phase 7.4 目标

实现可重复、可观察、可安全失败的 embedding indexing lifecycle：

```text
explicit request
  → select active material/current revision/ready chunks
  → verify existing identity/status/payload/source binding
  → embed only missing or explicitly stale/failed targets
  → persist ready or failed atomically
  → explicit verify reports inconsistencies
  → explicit rebuild/retry repairs selected targets
```

必须交付：

1. 清晰的 indexing scope 和显式调用入口；
2. 同 identity ready skip；
3. changed content/revision/provider/model/dimensions/encoding 的 stale/incompatible 处理；
4. 显式 rebuild/retry，不自动修复、不在 startup 偷跑；
5. verify 报告 schema、identity、payload、source binding、孤儿和状态问题；
6. 失败状态、批次策略和事务边界；
7. material revision、delete/restore/purge 生命周期一致性；
8. backup/restore 保持 embedding 状态且不自动 rebuild；
9. focused tests、完整 backend suite 和文档收口。

本任务不做：

- hybrid RRF、vector/lexical merge；
- 新的真实网络 provider；
- Q&A/citation/API/UI 全链路接入；
- 后台异步 worker；
- startup 自动 embedding；
- 外部 vector DB 或不受 backup 管理的索引文件。

---

## 3. Indexing contract

### 3.1 Scope

至少支持以下显式 scope，具体 API 可以沿用当前项目风格：

- 单 material 当前 revision；
- 单 revision；
- 项目范围或明确的 material ID 列表（如果现有边界适合）。

每次调用必须明确：

- provider identity；
- 是否只处理 missing；
- 是否允许处理 stale；
- 是否允许 retry failed；
- batch size；
- dry-run/verify（如实现）；
- 结果统计。

默认安全行为：

- 只索引 active material；
- 只索引 current revision；
- 只索引 `chunk.status='ready'`；
- 不碰 deleted material、superseded revision、非 ready chunk；
- 不自动删除历史 stale/failed 记录；
- 不覆盖用户 Q&A、citation 或其他用户状态。

### 3.2 同 identity 幂等

对于 canonical identity：

- `ready` 且 payload/source binding 有效：skip，不调用 provider；
- `running`：不得静默当作 ready；按明确 lease/repair policy 处理，不能产生重复 ready；
- `stale`：默认 skip；只有显式 rebuild/retry 才重新生成；
- `failed`：默认 skip；只有显式 retry/rebuild 才重新生成；
- identity 任一字段改变：不能复用旧 payload，必须生成新 identity 或明确将旧 row stale；
- provider 返回 malformed/dimension mismatch/invalid vector：不能写 ready；
- identical identity 的重试不得违反 unique constraint 或产生重复行。

若实现 `running` lease，必须：

- 使用现有时间格式和稳定 lease policy；
- 过期 running 才可由显式 retry/rebuild 接管；
- 未过期 running 返回稳定 conflict/skip 结果；
- 不声称支持跨进程可靠协调。

### 3.3 Batch failure policy

请选择并冻结一种策略：

1. **batch atomic**：一个 provider batch 失败，该 batch 不产生 ready，全部目标进入 failed；或
2. **per-item result**：provider/adapter 明确返回每个 item 结果，成功 item 可 ready，失败 item failed。

当前 provider protocol 如果只返回整体 vector list，优先采用 batch atomic，并在文档和测试中明确：

- 已提交的前序 batch 是否保留；
- 失败 batch 是否留下 failed rows；
- 外层 transaction 是否 rollback 全部调用；
- 返回的 `embedded_count`、`failed_count`、`skipped_count` 是否准确。

不能出现“返回整体 ready，但实际混有 failed/stale”的含糊状态。

---

## 4. Rebuild / retry contract

实现显式 rebuild/repair helper 或 service。名称可按项目风格，但语义必须固定。

### 4.1 Missing-only indexing

默认增量 indexing：

- 只选择没有有效 ready embedding 的 chunk；
- 相同有效 identity 直接 skip；
- 不调用 provider 处理已 ready row；
- 结果可重复，第二次调用不会增加 provider call 或 embedding row。

### 4.2 Explicit rebuild

显式 rebuild 可针对：

- 一个 material；
- 一个 revision；
- 一个 provider/model identity；
- stale rows；
- failed rows；
- 全部当前 ready chunks。

必须：

- 明确 scope，不允许空 scope 意外全库重建；
- 记录 selected/embedded/skipped/failed/stale counts；
- 旧 identity 不被静默覆盖；
- 新 payload 通过完整 codec 和 source binding 检查后才 ready；
- 失败保留可诊断 row/error code；
- 不删除 retrieval runs、hits、Q&A messages、answers 或 citations。

### 4.3 Retry

retry 只能由显式调用触发：

- failed → running → ready 或 failed；
- stale → running → ready 或 failed；
- malformed old row 不得直接 ready；
- provider 未配置、配置不合法、batch/text/dimensions 超限时返回稳定错误；
- retry 不泄露 raw provider error、文本、路径或 SQL。

如果当前项目不适合增加 API/CLI，至少提供可测试的 repository/service helper，并在文档明确它不是后台 worker。

---

## 5. Verify contract

实现显式 verify helper/service，返回脱敏、可机器读取的报告。报告不得包含正文、payload、路径、secret 或 raw traceback。

至少检查：

### Schema

- 当前 schema version/history；
- embeddings 表必须存在；
- 必要 columns、status constraint、unique identity；
- `PRAGMA foreign_keys` 相关完整性（沿用现有 audit 风格）。

### Row identity

- identity 字段非空且格式合法；
- dimensions 合法；
- encoding 支持；
- content hash 格式合法；
- chunk/source revision/material 的关系正确；
- source revision 是否 current；
- chunk 是否 ready；
- material 是否 active；
- 孤儿 embedding；
- duplicate identity（即便数据库 constraint 理论上阻止，也要测试报告路径）。

### Payload

- `ready` 必须有 payload；
- payload bytes 类型正确；
- payload 长度严格匹配 dimensions；
- codec 可解码；
- 每个 float finite；
- 不能是全零；
- payload size 不超过硬上限；
- `failed`/`stale` 可以没有 payload，但不能被报告为 ready-valid；
- `running` 不得被报告为 retrieval-ready。

### Status/source binding

建议报告字段：

```json
{
  "status": "valid|invalid|empty",
  "scope": {"project_id": "...", "material_id": "...", "revision_id": "..."},
  "counts": {
    "checked": 0,
    "ready_valid": 0,
    "ready_invalid": 0,
    "stale": 0,
    "failed": 0,
    "running": 0,
    "orphan": 0
  },
  "issues": [
    {"code": "embedding_payload_length_mismatch", "count": 1}
  ],
  "policy_version": "..."
}
```

具体字段可以适配现有 observability/repository 风格，但必须确定性、脱敏、可测试。单条 issue 不要携带正文或完整 chunk ID 以外的私密标识；如现有 API 返回 ID，保持项目既有安全边界。

Verify 默认只读，不应在普通 verify 中隐式修改 status 或重建 payload。若提供 `repair`，必须是单独显式操作并有事务测试。

---

## 6. Lifecycle integration

审计并补齐 material/chunk 生命周期：

### Import / revision

- 新 revision、新 chunks 只生成 missing embedding；
- 旧 revision embedding 保留但不得进入 current retrieval；
- content hash 改变时旧 identity 不得复用；
- chunking strategy/version 改变时 source binding 仍能阻止错误复用。

### Soft delete / restore

- soft-deleted material 的 embedding 不得进入 indexing/retrieval；
- restore 不自动触发 provider 或 rebuild；
- restore 后需要显式 indexing/rebuild；
- 既有 embedding status/payload 保留，除非项目现有生命周期契约要求清理。

### Purge

- purge 后 embedding 按 FK/cascade 或明确清理规则删除；
- 不产生 orphan embedding；
- purge 不删除无关 material 的 embedding；
- retrieval runs/hits/citations 的已有 lifecycle 不能回归。

### Failed / stale / running

固定允许的状态转移：

```text
running → ready | failed
ready → stale
stale → running（仅显式 rebuild/retry）
failed → running（仅显式 rebuild/retry）
```

禁止：

- failed/stale 自动静默 ready；
- 普通 retrieval 触发写入或 provider 调用；
- startup 自动把所有 stale/rebuild；
- 删除失败诊断信息后伪装成功。

---

## 7. Transaction 与 failure safety

必须明确 transaction boundary：

- provider HTTP/计算可以在数据库事务外执行；
- 写入 running/ready/failed 的状态必须在明确 transaction 中完成；
- 成功 ready row 必须在同一事务中同时满足 identity、payload、source binding；
- provider 失败不能留下 running 永久不受控；
- 数据库写入失败时不能返回成功统计；
- 事务 rollback 后不能留下半成品 ready、错误 duplicate 或孤儿 row；
- 失败 batch policy 与返回统计一致；
- 并发能力只能按单进程/单实例边界声明，不要声称多 worker 安全。

至少测试：

- provider exception；
- malformed vector；
- dimension mismatch；
- database write failure；
- transaction rollback；
- repeated identical call；
- retry after failed；
- retry stale；
- running/lease behavior（如实现）；
- previous successful batches vs failed batch 行为。

---

## 8. API / CLI 边界

Phase 7.4 不强制新增用户 UI。优先提供清晰、可测试的 repository/service helper；如新增 API 或 CLI，必须：

- 是显式操作，不在 startup 调用；
- 输入 scope 有界且拒绝空/模糊全库操作；
- 参数包含 material/revision/provider/model 等必要 binding；
- 返回稳定 schema、counts、status 和 error code；
- 不返回 source text、vector payload、路径、SQL、traceback、provider key 或 raw provider response；
- 错误为稳定脱敏码；
- 明确操作是 synchronous、local、single-process；
- 不伪装成后台队列、真正 cancel 或多进程协调。

如果新增 endpoint，补 `test_api_input_boundaries.py` 或对应 focused API 测试，并验证项目边界、deleted material、非 current revision 和 unknown IDs。

---

## 9. Backup / restore evidence

使用 pytest `tmp_path`，不得提交 backup artifact。至少创建包含以下状态的测试数据库：

- 一个合法 ready embedding；
- 一个 stale embedding；
- 一个 failed embedding；
- 至少一个可比较 payload；
- 如实现 running lease，再包含 running row。

执行：

1. `backup_data()`；
2. `verify_backup()`；
3. `restore_backup()` 到新的空目录；
4. 检查 schema version/history/user_version；
5. 检查 embedding row count、identity、status、error_code；
6. 比较 ready payload bytes；
7. 确认 stale/failed 没有变 ready；
8. 恢复过程没有调用 provider、没有 rebuild、没有新增 embedding；
9. restore 后 verify 结果与 source 一致；
10. purge/restore 的既有 backup contract 不回归。

---

## 10. 测试交付清单

至少新增或补充：

### Indexing

- active/current/ready scope；
- deleted/superseded/not-ready exclusion；
- same identity ready skip；
- missing-only second call idempotence；
- changed content hash creates new identity / old becomes unavailable；
- changed revision/provider/model/revision/dimensions/encoding 不复用旧 payload；
- malformed provider output never ready；
- provider failure stable failed state；
- batch atomic policy（或正式 per-item policy）；
- accurate embedded/skipped/failed counts；
- database write rollback；
- no startup indexing。

### Rebuild/retry

- explicit rebuild only；
- stale only scope；
- failed only scope；
- material/revision/provider scope；
- empty/ambiguous scope rejected；
- retry converts failed/stale to running then ready/failed；
- failed/stale never silently ready；
- Q&A/citation/retrieval history preserved。

### Verify

- fresh empty database；
- valid ready row；
- missing payload；
- truncated/extra/malformed payload；
- wrong dimensions/encoding；
- invalid content hash/identity；
- orphan chunk/source/material；
- deleted material；
- non-current revision；
- non-ready chunk；
- running/failed/stale statuses；
- deterministic report and stable issue codes；
- verify read-only；
- optional explicit repair has transaction tests。

### Lifecycle / backup

- revision replacement；
- soft delete/restore；
- purge cascade/orphan check；
- ready/stale/failed/running backup/restore；
- payload byte equality；
- provider not called during restore；
- restore does not auto rebuild。

### Regression commands

```text
D:\miniconda\py310\python.exe -m pytest backend/tests/test_embedding.py backend/tests/test_migrations.py backend/tests/test_ai_indexing.py backend/tests/test_retrieval.py backend/tests/test_backup_restore.py backend/tests/test_ai_backup_restore.py
D:\miniconda\py310\python.exe -m pytest backend/tests/
```

如新增 API 或用户可见状态，再运行对应 API/Chromium focused E2E；没有浏览器证据不得声称 `browser-tested`。

---

## 11. 文档收口

更新：

- `docs/PHASE_ROADMAP.md`；
- `docs/STATUS.md`；
- `docs/TODO.md`；
- `docs/PROJECT_PROGRESS_REPORT.md`；
- 必要时 `docs/ai-learning-architecture.md` 或新增正式 `docs/` 决策文档。

文档必须明确：

- Phase 7.4 是 `implemented / backend-tested`、`partial` 还是 `blocked`；
- 是否新增 migration，以及真实理由；
- indexing 默认 scope 和显式 rebuild/retry 语义；
- verify 是只读还是包含显式 repair；
- batch failure 与 transaction policy；
- status transition 和 lifecycle；
- backup/restore 实际证据；
- hybrid RRF、fallback、真实 provider、Q&A/citation/UI 仍未完成。

不得把本 Phase 的 repository helper、fake provider 或 verify 测试写成 Phase 7 completed 或 real-pass。

---

## 12. 完成判定

只有同时满足以下条件，Phase 7.4 才能标记 `implemented / backend-tested`：

1. 有显式 indexing 入口，默认只处理 active/current/ready scope；
2. 同 identity ready 幂等 skip，重复调用不重复 provider/row；
3. stale/failed/running 不会被普通 indexing 或 retrieval 静默当作 ready；
4. 显式 rebuild/retry 能按有界 scope 处理 stale/failed/missing，并准确报告 counts；
5. verify 能检查 schema、identity、payload、source binding、status 和 orphan，并返回确定性脱敏报告；
6. malformed payload/provider output/dimension mismatch 不会进入 ready；
7. provider/DB failure 的 transaction boundary 明确，rollback 不留下半成品或错误成功统计；
8. import/revision/soft delete/restore/purge 生命周期与 embedding 状态一致；
9. backup/restore 保留 rows/status/identity/payload/history，且不会自动 provider/rebuild；
10. focused tests 和完整 backend suite 通过；
11. 文档状态与实际实现一致。

如果只完成 indexing 或只完成 verify，必须标记 `partial`。

Phase 7.4 完成不等于 Phase 7 完成。后续仍有：

```text
7.5 hybrid RRF / fallback
→ 7.6 Q&A / citation / API / UI 接入
→ 7.7 最终基线、专项验收与 real-pass 边界
```

---

## 13. 最终报告格式

完成后按以下结构报告：

1. 实现摘要；
2. 修改文件（production/migration/tests/docs）；
3. indexing scope、幂等、rebuild/retry 和状态转换；
4. verify 报告 schema、issue codes 和只读/repair 边界；
5. transaction、failure、lifecycle 和 purge 证据；
6. backup/restore 证据；
7. focused/full backend/Chromium 测试结果；
8. 未验证限制；
9. Phase 7.4 判断：`implemented` / `partial` / `blocked`；
10. Phase 7 剩余任务。
