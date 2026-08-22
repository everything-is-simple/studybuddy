# StudyBuddy Phase 7.5 执行 Prompt：Vector Similarity、Hybrid RRF 与安全 Fallback

> 用途：将本文完整复制给 coding agent，继续在 `H:\studybuddy` 内实现并验收 Phase 7.5。
>
> 范围：在已有 lexical retrieval、embedding identity/codec/stale semantics 和显式 indexing/rebuild/verify 基础上，实现确定性的 vector candidate、hybrid RRF、fallback policy、retrieval audit metadata 和 regression tests。不要提前实现 Phase 7.6 的 Q&A/citation/UI 全链路，也不要提前宣称 Phase 7 completed。

---

## 0. 角色与执行方式

你是 StudyBuddy 仓库中的资深检索系统、SQLite、排序算法、provider failure handling 和测试工程师。请直接修改 production code、正式测试和文档，不要只给设计方案。

必须：

1. 先阅读根目录 `AGENTS.md`。
2. 完整阅读：
   - `README.md`
   - `docs/PHASE7_1_AUDIT_AND_CONTRACT.md`
   - `docs/phase7-prompt.md`
   - `docs/phase7-2-prompt.md`
   - `docs/phase7-3-prompt.md`
   - `docs/phase7-4-prompt.md`
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
   - 相关 retrieval、embedding、indexing、verify、Q&A/citation、migration、backup/restore 和 API boundary tests
3. 先执行并记录：
   ```text
   git status --short
   git diff --stat
   git log -5 --oneline
   D:\miniconda\py310\python.exe -m pytest backend/tests/
   ```
4. 当前 HEAD 预期为：
   ```text
   88f8a0a feat: complete phase 7.4 embedding indexing
   ```
5. 不覆盖工作区已有用户改动；不要提交 `.backup/`、`.pi/`、数据库、上传原件、provider key、secret、私有路径、测试 artifact、临时输出或生成文件。
6. 先审计现有 retrieval contract 和 schema，再写 focused tests；实现后运行 focused suite 和完整 backend suite。
7. 诚实区分 `implemented`、`backend-tested`、`browser-tested`、`real-pass`、`not_verified`。Phase 7.5 完成不等于 Phase 7 完成。

---

## 1. 当前基线

Phase 7.1–7.4 已完成并推送，当前已有：

### Lexical retrieval

`run_chunk_retrieval()` 是既有正式路径：

- policy：`lexical_fts_v1`；
- FTS5 ASCII token AND 与 Unicode/special-token substring fallback；
- active material、current revision、ready chunk、project scope 硬过滤；
- `top_k` 1–50；
- score/rank/tie-breaker 稳定；
- `retrieval_runs` / `retrieval_hits` 持久化；
- 没有 ready chunk 时为 `retrieval_not_ready`；没有命中时为 `retrieval_empty`；
- 历史 lexical score、rank 和 policy 语义不可改变。

### Embedding foundation

已有：

- v5 `embeddings` schema；
- canonical `EmbeddingIdentity`；
- `f32le_v1` codec；
- `sha256_bucket_v1` deterministic fake provider；
- explicit indexing/rebuild/retry；
- read-only `verify_embeddings()`；
- `run_vector_retrieval()` 最小 vector-only 路径；
- stale/source binding/ready-only safety filters。

### Frozen constants and semantics

必须沿用或明确冻结：

```text
VECTOR_POLICY_VERSION = vector_cosine_v1
HYBRID_POLICY_VERSION = hybrid_rrf_v1
RRF_K = 60
VECTOR_CANDIDATE_POOL = 50
```

如审计发现当前常量或字段不足，先说明真实 gap。不得修改历史 `lexical_fts_v1` 语义，不得用新 migration 逃避 repository contract；只有真实 schema gap 才增加连续 migration。

---

## 2. Phase 7.5 目标

实现以下最小闭环：

```text
query
  → lexical candidates
  → query embedding
  → ready/source-bound vector candidates
  → deterministic RRF merge
  → final top-k
  → persisted retrieval run/hits with explainable scores
```

并实现安全 fallback：

```text
hybrid/vector request + embedding unavailable
  → explicit fallback policy
  → lexical-only retrieval
  → persisted fallback reason/policy
```

必须交付：

1. vector candidate retrieval contract；
2. hybrid RRF deterministic merge；
3. explicit mode/policy selection；
4. fallback lexical behavior；
5. retrieval run/hit audit metadata；
6. stale/deleted/current/ready/project filtering regression；
7. vector/hybrid empty/not-ready/error semantics；
8. backup/restore metadata regression（若 schema 有变化）；
9. focused/full backend tests 和文档收口。

本任务不做：

- 真实网络 embedding adapter；
- 外部 vector database、ANN 或隐藏索引文件；
- 后台队列、多 worker、多进程协调；
- Q&A prompt/context 全链路重写；
- citation 规则重写；
- cards、exercises、study plans；
- startup 自动 indexing 或 provider probe。

---

## 3. Retrieval API / repository contract

可以沿用现有 API 风格，也可以新增明确 mode 字段，但必须保持 legacy client compatibility：

- 未指定 mode 时仍走 lexical-only，不改变旧请求响应和历史 policy；
- `lexical`：只调用 lexical retrieval，不调用 embedding provider；
- `vector`：只调用 vector retrieval；provider/index 不可用时返回稳定错误，不自动 fallback；
- `hybrid`：运行 lexical + vector，再按 RRF merge；
- `hybrid` 请求可以显式允许 fallback，默认策略应记录清楚；
- 不允许任意客户端传入 policy version、RRF 常数、权重或 SQL 片段覆盖服务器冻结 policy；
- material IDs 必须去重、属于 project，deleted material 必须安全拒绝或返回项目既有稳定错误；
- query/top_k 输入边界沿用当前 retrieval contract；
- 不返回 source text 全文、vector payload、provider raw response、路径、SQL 或 traceback。

推荐内部接口：

```python
def run_hybrid_retrieval(
    connection,
    *,
    project_id: str,
    query: str,
    provider: EmbeddingProvider,
    material_ids: list[str] | None = None,
    top_k: int = 5,
    allow_fallback: bool = True,
) -> dict[str, object]: ...
```

可以采用等价命名，但必须有单一实现，不能让 API、Q&A 和测试分别拼 hybrid SQL/ranking。

---

## 4. Candidate selection

### 4.1 Lexical candidate

复用现有 `run_chunk_retrieval()` 的 candidate 语义或提取可复用 helper，但不能复制后产生两个不一致的 lexical contract。

必须保留：

- active/current/ready/project filters；
- material scope validation；
- existing lexical score/rank/tie-breaker；
- lexical no-ready 与 empty 的区分。

Hybrid 需要 lexical candidate pool。推荐：

```text
lexical candidate pool = min(max(top_k, VECTOR_CANDIDATE_POOL), MAX_RETRIEVAL_TOP_K)
```

如果现有 top-k 上限或 policy 不适合，选择明确的固定规则并测试。最终输出仍受 `top_k` 限制。

### 4.2 Vector candidate

query embedding：

- 使用当前 provider identity；
- provider 调用失败、返回 malformed、dimension mismatch、invalid vector 必须映射为稳定 embedding error；
- query text 使用 retrieval query normalization，不要把 query hash 当 chunk content hash；
- 不持久化 query vector payload。

candidate SQL 必须至少过滤：

```sql
c.project_id = ?
AND m.deleted_at IS NULL
AND r.is_current = 1
AND r.material_id = c.material_id
AND c.status = 'ready'
AND e.status = 'ready'
AND e.provider_id = ?
AND e.model_id = ?
AND e.model_revision = ?
AND e.dimensions = ?
AND e.vector_encoding = ?
```

随后必须执行 source binding 和 payload decode 校验：

- content hash 与当前 normalized chunk text hash 相等；
- source revision 与当前 revision 相等；
- payload bytes 严格符合 codec；
- stale/corrupt/zero/nonfinite 记录跳过；
- 不因单个 corrupt candidate 使整个 retrieval 崩溃。

使用 cosine similarity。若 fake provider 输出 normalized vector，仍不能省略 denominator/finite validation。

Vector candidate 排序固定：

```text
(-round(vector_score, 12), stable_chunk_id)
```

candidate pool 大小固定为 `VECTOR_CANDIDATE_POOL`，不得由客户端覆盖。

### 4.3 No candidate semantics

固定并测试：

- scope 没有 active/current/ready chunk：`retrieval_not_ready`；
- 有 ready chunks 但无 ready matching embeddings：vector-only 为 `retrieval_empty` 或项目已冻结的 `embedding_index_unavailable`，必须稳定且文档明确；
- hybrid 一路为空但另一路有结果：仍可返回另一侧结果，不能凭空补分；
- 两路都为空：`retrieval_empty`；
- vector/provider 不可用：vector-only 返回 embedding/index error；hybrid 只有在 `allow_fallback=True` 时 fallback lexical。

---

## 5. Hybrid RRF contract

### 5.1 Frozen formula

使用 Reciprocal Rank Fusion：

```text
rrf_score = Σ 1 / (RRF_K + rank)
```

其中：

- `RRF_K = 60`；
- rank 从 1 开始；
- lexical 和 vector 各自独立 rank；
- 只为实际出现在某一路 candidate list 的 chunk 加该路分数；
- 不按 raw lexical BM25 与 cosine 直接比较；
- 不使用随机数、当前时间或 Python 内置 `hash()` 参与排序。

建议内部结构：

```python
{
    chunk_id: {
        "row": row,
        "lexical_rank": 1 | None,
        "vector_rank": 2 | None,
        "lexical_score": float | None,
        "vector_score": float | None,
        "rrf_score": float,
    }
}
```

最终排序固定：

```text
(-round(rrf_score, 12), stable_chunk_id)
```

如使用 material/chunk index 作为第一 tie-breaker，必须固定、记录并测试；不能不同调用路径不同排序。

### 5.2 Scores and hits

`retrieval_hits` 现有字段语义必须保持：

- `score`：final score；hybrid 时为 RRF score；
- `lexical_score`：实际 lexical score，否则 NULL；
- `vector_score`：实际 cosine score，否则 NULL；
- `rerank_score`：本 Phase 不启用，保持 NULL；
- `rank`：最终 rank，不是 lexical/vector candidate rank；
- `selected=1`：只写最终 top-k，除非现有 schema/审计策略明确记录未选 candidates。

API 返回的 hit 可以额外包含：

```text
lexical_rank
vector_rank
lexical_score
vector_score
score / rrf_score
```

但不返回 payload 或正文全文。`text_preview` 沿用既有安全限制。

### 5.3 Policy version

固定：

```text
lexical_fts_v1
vector_cosine_v1
hybrid_rrf_v1
fallback_lexical_v1
```

历史 lexical runs 不得被更新或重解释。新 hybrid run 必须写 `hybrid_rrf_v1`，vector-only 写 `vector_cosine_v1`，fallback lexical run 必须清晰记录 fallback policy/reason，不能伪装为 vector success。

---

## 6. Fallback policy

Fallback 不是隐式异常吞掉，而是显式 policy：

```text
hybrid + allow_fallback=True
  provider not configured/unavailable/timeout/rate_limited/auth_failed/
  invalid_response/dimension_mismatch/index_unavailable
  → run lexical-only
  → policy = fallback_lexical_v1
  → record sanitized fallback reason
```

要求：

- vector-only 默认不 fallback；
- hybrid `allow_fallback=False` 时返回稳定 embedding error；
- hybrid fallback 不调用 provider 第二次；
- lexical retrieval 仍使用原有 ready/current/deleted/project filters；
- lexical 命中时整体状态 `succeeded`，并带 fallback metadata；
- lexical 无命中返回 `retrieval_empty`；
- 无 ready chunk 返回 `retrieval_not_ready`；
- fallback reason 只允许稳定 error code，例如 `embedding_provider_unavailable`，不能存 raw exception/message/provider response；
- fallback 不修改 embedding row，也不将失败/stale 变 ready；
- fallback 行为必须在 retrieval run/hits/API response 中可解释但不泄露敏感信息。

推荐结果字段：

```json
{
  "status": "succeeded|empty|failed",
  "policy_version": "fallback_lexical_v1",
  "fallback": true,
  "fallback_reason": "embedding_provider_unavailable",
  "hits": []
}
```

如果当前 `retrieval_runs` 没有 fallback 字段，schema 变化必须通过 migration。不要运行时 ad-hoc ALTER。可以在不改 schema 的情况下复用 `policy_version` + `error_code`，但必须确保机器可读且不破坏已有字段语义；先审计再决定。

---

## 7. API and Q&A compatibility

Phase 7.5 允许增加 retrieval mode API，但必须保持旧行为：

- 既有 `POST /api/retrieval` 默认 mode lexical；
- 旧客户端 response shape 和 error semantics 不变；
- 新 mode 输入明确校验：`lexical|vector|hybrid`；未知 mode 稳定 400；
- provider 未配置时，lexical 请求正常；vector 请求稳定失败；hybrid 按 allow_fallback policy；
- 不在本 Phase 改写 Q&A prompt/context/citation 全链路；如果现有 Q&A 仍固定调用 lexical，必须在文档明确 7.6 才接入 hybrid；
- 不增加未经需要的 UI。

如果新增 API 字段，必须补：

- malformed JSON；
- unknown mode；
- invalid top_k；
- duplicate/unknown/deleted material IDs；
- project isolation；
- no secret/path/raw error/source text leak；
- provider failure and fallback response；
- retrieval run/hit persistence。

---

## 8. Schema / migration / backup decision

先审计 v5 是否足够保存 Phase 7.5 所需数据：

- `retrieval_runs.policy_version`；
- `embedding_provider_id`、`embedding_model_id`；
- `error_code`；
- `retrieval_hits.score`、`lexical_score`、`vector_score`、`rerank_score`；
- existing foreign keys and indexes。

如果 v5 足够：

- 不新增 migration；
- hybrid/fallback metadata 使用现有字段的冻结语义；
- 在测试中证明 backup/restore 不丢失新 run/hit metadata。

如果存在真实 gap：

- 新增连续、事务化、幂等 migration；
- 更新 migration history tests、backup/restore tests；
- 不修改 v1–v5 history；
- 不在 runtime ad-hoc schema mutation。

至少补 backup/restore test：

1. 创建 lexical/vector/hybrid/fallback retrieval runs；
2. 写入 hits 的 lexical/vector/final scores 和 policy；
3. backup/verify/restore 到新空目录；
4. 比较 run/hit count、policy、provider/model、scores、status/error code；
5. 确认 restore 不调用 provider、不重建 embedding、不改变历史 lexical run；
6. 不提交任何数据库或 backup artifact。

---

## 9. 测试交付清单

至少新增或补充：

### Vector

- query embedding deterministic；
- active/current/ready/project filter；
- matching provider/model/revision/dimensions/encoding；
- stale/content hash/source revision exclusion；
- corrupt/truncated/extra/zero/nonfinite payload exclusion；
- cosine ranking；
- vector tie-breaker；
- candidate pool fixed；
- vector-only empty/not-ready/error；
- retrieval run/hit persistence。

### Hybrid

- lexical-only regression exact pass；
- vector-only regression exact pass；
- lexical and vector overlap；
- lexical-only candidate；
- vector-only candidate；
- both candidate lists empty；
- RRF formula with ranks 1-based；
- `RRF_K=60` frozen；
- final top-k；
- final tie-breaker；
- lexical/vector/final score persistence；
- policy version persistence；
- no reranker score fabricated。

### Fallback

- provider not configured；
- provider unavailable；
- timeout/rate-limit/auth/invalid response/dimension mismatch；
- hybrid fallback enabled；
- hybrid fallback disabled；
- vector-only never silently fallback；
- lexical fallback success/empty/not-ready；
- fallback reason stable and sanitized；
- fallback does not mutate embedding rows。

### API/security

- legacy default remains lexical；
- mode validation；
- project/material scope validation；
- no secret/path/raw exception/source text leak；
- run/hit audit rows；
- existing Q&A/citation/thread/idempotency tests remain green。

### Backup/regression

```text
D:\miniconda\py310\python.exe -m pytest backend/tests/test_embedding.py backend/tests/test_migrations.py backend/tests/test_ai_indexing.py backend/tests/test_retrieval.py backend/tests/test_backup_restore.py backend/tests/test_ai_backup_restore.py
D:\miniconda\py310\python.exe -m pytest backend/tests/
```

若修改用户可见 API/UI，再运行对应 Chromium focused E2E；没有浏览器证据不得声称 `browser-tested`。

---

## 10. 文档收口

更新：

- `docs/PHASE_ROADMAP.md`；
- `docs/STATUS.md`；
- `docs/TODO.md`；
- `docs/PROJECT_PROGRESS_REPORT.md`；
- 必要时 `docs/ai-learning-architecture.md` 或正式决策文档。

文档必须明确：

- Phase 7.5 是 `implemented / backend-tested`、`partial` 还是 `blocked`；
- vector-only、hybrid、fallback 的 mode 和 policy；
- RRF 公式、RRF_K、candidate pool、top-k、tie-breaker；
- score/run/hit metadata 语义；
- v5 是否足够、是否新增 migration；
- backup/restore 实际证据；
- Q&A/citation/UI、真实 provider、Chromium 和 real-pass 仍未完成范围。

---

## 11. 完成判定

只有同时满足以下条件，Phase 7.5 才能标记 `implemented / backend-tested`：

1. vector candidate 有显式、单一实现，且 active/current/ready/source-binding/identity/payload 过滤完整；
2. vector-only 使用 cosine、固定 candidate pool、固定排序和稳定 empty/error 语义；
3. hybrid 使用真实 lexical + vector candidate list，不直接比较未经解释的 raw scores；
4. RRF 公式、`RRF_K=60`、1-based ranks、最终 top-k 和 tie-breaker 已冻结并测试；
5. retrieval hits 同时保存 lexical/vector/final score，未使用 reranker 时 rerank 为 NULL；
6. fallback 只有在显式允许时发生，vector-only 不静默 fallback；
7. fallback reason/policy 稳定、可审计且不泄露 raw provider error；
8. legacy lexical path、Q&A/citation/lifecycle/idempotency 不回归；
9. backup/restore 保留新增 retrieval audit metadata；
10. focused tests 和完整 backend suite 通过；
11. 文档与实际行为一致。

Phase 7.5 完成不等于 Phase 7 完成。仍需：

```text
7.6 Q&A / citation / API / UI 接入
→ 7.7 最终基线、backup/restore 专项和验收
```

---

## 12. 最终报告格式

完成后按以下结构报告：

1. 实现摘要；
2. 修改文件（production/migration/tests/docs）；
3. lexical/vector/hybrid/fallback 的精确行为；
4. RRF 参数、candidate pool、tie-breaker 和 score persistence；
5. schema/migration/backup 结论；
6. provider failure 和安全边界；
7. focused/full backend/Chromium 测试结果；
8. 未验证限制；
9. Phase 7.5 判断：`implemented` / `partial` / `blocked`；
10. Phase 7 剩余任务。
