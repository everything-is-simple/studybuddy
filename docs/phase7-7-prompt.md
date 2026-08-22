# StudyBuddy Phase 7.7 执行 Prompt：Embedding / Hybrid Retrieval 最终验收与证据收口

> 用途：将本文完整复制给 coding agent，继续在 `H:\studybuddy` 内完成 Phase 7.7 最终验收与状态收口。
>
> 范围：对 Phase 7.1–7.6 已实现的 embedding、vector、hybrid、fallback、Q&A/citation 集成执行最终 backup/restore、性能边界、provider gate、Chromium 和完整回归验收。优先补测试、验收脚本和文档证据；只有发现真实生产缺陷才修改 production code。不要提前进入 Phase 8，也不要把未配置或未执行的真实 provider、Chromium、规模压力测试标记为 real-pass。

---

## 0. 角色与强制执行规则

你是 StudyBuddy 仓库中的资深系统验收、SQLite backup/restore、RAG retrieval、provider integration、性能基线和浏览器测试工程师。请直接执行验收并修改必要的正式代码、测试、脚本和文档，不要只给计划。

必须：

1. 先阅读根目录 `AGENTS.md`。
2. 完整阅读：
   - `README.md`
   - `docs/PHASE7_1_AUDIT_AND_CONTRACT.md`
   - `docs/phase7-prompt.md`
   - `docs/phase7-2-prompt.md`
   - `docs/phase7-3-prompt.md`
   - `docs/phase7-4-prompt.md`
   - `docs/phase7-5-prompt.md`
   - `docs/phase7-6-prompt.md`
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
   - 现有 embedding、indexing、retrieval、Q&A、citation、backup/restore、migration、provider、API boundary、browser 和 acceptance tests
3. 先执行并记录：
   ```text
   git status --short
   git diff --stat
   git log -5 --oneline
   D:\miniconda\py310\python.exe -m pytest backend/tests/
   ```
4. 当前 HEAD 预期为：
   ```text
   e2810f8 feat: complete phase 7.6 qa retrieval integration
   ```
5. 不覆盖工作区已有用户改动；不要提交 `.backup/`、`.pi/`、数据库、上传原件、provider key、secret、私有路径、测试 artifact、临时输出、性能原始 dump 或生成文件。
6. 使用项目 Python：
   ```text
   D:\miniconda\py310\python.exe
   ```
7. 只有真实执行并有可复核证据时，才标记：
   - `implemented`
   - `backend-tested`
   - `browser-tested`
   - `real-pass`
   - `not_verified`
8. 不得因为 fake provider 或 mock HTTP 通过，就宣称真实 embedding provider 通过。
9. 不得因为 backend tests 通过，就宣称 Chromium/browser-tested。
10. 不得将 Phase 7.7 之外的 cards、exercises、study plans 或后台 worker 纳入本任务。

---

## 1. 当前基线与完成目标

### 1.1 已有实现

Phase 7.1–7.6 已完成或部分完成：

- v5 embedding schema migration；
- 独立 `EmbeddingProvider` protocol 和 registry；
- deterministic fake embedding provider；
- `sha256_bucket_v1`；
- canonical `EmbeddingIdentity`；
- `f32le_v1` codec；
- stale/source-binding/ready-only checks；
- explicit indexing、rebuild、retry_failed、verify；
- vector cosine retrieval；
- `vector_cosine_v1`；
- deterministic `hybrid_rrf_v1`；
- `RRF_K = 60`；
- fixed vector candidate pool；
- stable tie-breaker；
- explicit `fallback_lexical_v1`；
- `/api/retrieval` lexical/vector/hybrid mode；
- Q&A 默认 lexical，显式 vector/hybrid mode；
- Q&A fallback、retrieval run/hit、operation、answer、citation linkage；
- server-side context assembly 和 citation verification；
- backup/restore 基础能力；
- 单进程、单实例、SQLite-first 边界。

### 1.2 尚未证明的最终事项

Phase 7.7 必须验证或明确标记：

- embedding/retrieval/Q&A metadata backup/restore 完整性；
- corrupted/stale/orphan embedding recovery evidence；
- deterministic fake benchmark 和容量边界；
- provider configuration/error mapping gate；
- 如存在可用真实 embedding provider，执行 opt-in real smoke；
- Chromium Q&A lexical/vector/hybrid/fallback acceptance；
- full backend regression；
- migration history/schema version consistency；
- 文档和状态收口。

### 1.3 最终状态规则

即使所有 fake/backend 测试通过，若真实 embedding provider 未配置、Chromium 未执行或性能边界未形成证据，也只能写：

```text
implemented / backend-tested / partial
```

不能写：

```text
Phase 7 completed
real-pass
production-ready
```

除非每个对应 gate 都有实际证据。

---

## 2. Backup / restore 专项验收

使用 pytest `tmp_path` 创建全新的 source/backup/restore 目录。不得使用仓库目录中的数据库、`.backup/` 或既有测试 artifact。

至少构造以下状态：

1. active material + current revision + ready chunks；
2. fake embedding ready rows；
3. stale embedding；
4. failed embedding；
5. lexical retrieval run/hits；
6. vector retrieval run/hits；
7. hybrid retrieval run/hits；
8. fallback hybrid run/hits；
9. Q&A answer + `ai_operation` + retrieval run linkage；
10. valid citation；
11. deleted/purged source 的历史 citation unavailable 状态；
12. 如现有 schema 支持，保留 malformed/failed audit metadata。

执行：

```text
backup → verify_backup → restore 到新的空 target → 再次 verify
```

比较并断言：

- `schema_migrations` 完整历史；
- `PRAGMA user_version`；
- schema version；
- materials/extractions/revisions/chunks 数量；
- embeddings 数量、status、provider/model/model_revision/dimensions/encoding；
- embedding payload bytes 或稳定 digest；
- retrieval run/hit 数量；
- retrieval `policy_version`；
- `embedding_provider_id` / `embedding_model_id`；
- `error_code` 和 fallback reason；
- lexical/vector/final score、rank、citation label；
- Q&A answer、operation、`retrieval_run_id`、citation linkage；
- citation status，尤其是 `source_deleted` / `source_unavailable`；
- restore 不调用 embedding provider；
- restore 不调用 LLM provider；
- restore 不自动 indexing/rebuild/retrieval；
- restore 不把 stale/failed embedding 静默提升为 ready；
- restore 不改变 citation lifecycle。

如果发现 schema gap：

- 先确认是否真的无法由现有列表达；
- 只有必要时新增连续 migration；
- 不修改 v1–v5 migration history；
- migration 必须连续、幂等、事务化；
- 添加 upgrade、rollback、backup/restore history tests；
- 保持 `schema_migrations` 和 `PRAGMA user_version` 一致；
- 禁止 runtime ad-hoc `CREATE TABLE` / `ALTER TABLE`。

如果 v5 和现有 Q&A/citation schema 足够，明确记录：

```text
Phase 7.7 required no new migration.
Existing v5 embedding schema and Q&A/citation schema express all audited metadata.
```

---

## 3. Corruption / lifecycle / rebuild 验收

补齐或审计 focused tests：

- ready embedding payload malformed；
- wrong payload length；
- NaN/Inf/non-finite vector；
- wrong dimensions；
- wrong encoding；
- wrong content hash；
- wrong source revision；
- wrong provider/model/model revision；
- chunk deleted/stale/non-current；
- material deleted/restored/purged；
- orphan embedding；
- failed embedding default skip；
- explicit retry_failed；
- explicit rebuild；
- verify remains read-only；
- retrieval never returns invalid embedding candidate；
- Q&A context never includes invalid/non-current/deleted chunk；
- backup preserves the bad/stale status for diagnosis；
- restore does not silently repair or upgrade it。

所有 provider failure 必须：

- 使用稳定脱敏 error code；
- 不返回 traceback、SQL、路径、raw provider response 或 secret；
- 不让 vector-only 自动切 lexical；
- 只允许 hybrid 在明确开启 fallback 时 fallback；
- fallback run 记录 `fallback_lexical_v1`；
- Q&A 不在 retrieval failure/empty/not-ready 时无 context 自由生成。

---

## 4. Synthetic benchmark 与性能边界

不引入 ANN、外部 vector DB、后台任务或多进程 worker。使用 deterministic fake embedding 和 SQLite-first 现有实现，建立可重复的 synthetic benchmark。

### 4.1 数据规模

至少覆盖：

- 10 materials / 100 chunks；
- 50 materials / 1,000 chunks；
- 如果本机时间允许，100 materials / 5,000 chunks；
- 每个 chunk 使用固定 ASCII/Unicode synthetic text；
- embedding 使用 fake provider；
- 不提交生成数据库或 benchmark output。

### 4.2 测量项目

分别测量并记录：

- explicit material/chunk indexing；
- embedding indexing；
- incremental idempotent re-index；
- vector retrieval；
- hybrid retrieval；
- Q&A retrieval + context assembly（provider 可使用 fake LLM）；
- verify_embeddings；
- backup/verify/restore（至少小规模）。

每项至少执行多次，报告：

- sample count；
- min/median/p95（若样本足够）；
- total duration；
- rows/chunks/embeddings/hits；
- peak memory 如能可靠测量；
- SQLite/database size；
- machine/environment class；
- 是否为 synthetic、是否为 real-pass。

### 4.3 边界要求

不要凭空设定 production SLA。只记录实测结果和适用边界，例如：

```text
synthetic / local Windows / single process / SQLite / fake provider
```

如果结果显示 5,000 chunks 已明显退化：

- 记录为当前容量边界；
- 不通过引入外部系统规避；
- 不宣称规模可扩展；
- 将后续容量优化写入 TODO。

benchmark 脚本必须：

- 位于正式测试或 scripts 目录；
- 不保存私有路径、数据库、provider key；
- 不依赖网络；
- 不修改生产 data root；
- 不在 startup 运行；
- 输出可脱敏、可复核的 JSON/Markdown summary；
- 生成输出默认放临时目录，不提交 artifact。

如果本轮没有执行 benchmark，必须明确 `not_verified`，不能用普通 pytest 结果代替。

---

## 5. Real embedding provider gate

真实 embedding provider 是 opt-in gate，不得因未配置而阻塞 fake/backend 验收。

### 5.1 配置边界

明确区分两类 provider：

```text
LLM / Q&A provider
Embedding / vector query provider
```

已有 LLM provider 配置不等于 embedding provider 已配置。分别检查：

```text
STUDYBUDDY_LLM_PROVIDER
STUDYBUDDY_LLM_MODEL
STUDYBUDDY_EMBEDDING_PROVIDER
STUDYBUDDY_EMBEDDING_MODEL
```

不得把 LLM provider 数量或 LLM smoke 结果写成 embedding real-pass 证据。

### 5.2 如果真实 embedding provider 可用

只在用户明确配置 provider、model、base URL、key 且测试目标匹配时执行：

1. capability/config validation；
2. 单文本 embedding smoke；
3. batch embedding smoke；
4. dimensions/encoding validation；
5. explicit indexing synthetic material；
6. vector retrieval；
7. hybrid retrieval；
8. Q&A retrieval/citation linkage；
9. stable provider/model metadata persistence；
10. error mapping 和 secret redaction；
11. 不把 key 写入数据库、日志、artifact 或 response。

### 5.3 如果未配置或无法安全执行

记录：

```text
real embedding provider: not_verified
reason: not configured / unavailable / credentials not supplied / target mismatch
```

不要临时寻找或读取 provider secret，不要默认调用网络，不要把 fake provider 结果标为 real-pass。

---

## 6. Chromium / browser final acceptance

Phase 7.7 需要实际浏览器证据。先找到仓库真实的 browser test runner 和现有 specs，不要假设 Python pytest 能执行 JS spec。

至少覆盖：

- import material；
- explicit chunk indexing；
- embedding indexing 状态展示或既有 index status；
- lexical Q&A 默认路径；
- explicit hybrid Q&A；
- explicit vector Q&A；
- hybrid fallback notice/status；
- vector/index/provider failure；
- retrieval empty/not-ready；
- answer citation display；
- citation detail/navigation；
- deleted/purged source unavailable；
- thread/history/replay；
- refresh and scope preservation；
- no raw provider/path/SQL/traceback/secret leak；
- desktop and narrow viewport；
- keyboard/focus/ARIA/status contract if UI changes。

每个 browser test 必须记录：

- runner command；
- browser/version if available；
- viewport；
- pass/fail/skip；
- whether fake or real provider；
- exact provider/model/gateway if real；
- evidence path only if artifact is permitted and contains no private paths/secrets。

没有实际 Chromium 结果时，必须写 `browser-tested: not_verified`。

---

## 7. Full regression and acceptance matrix

至少执行：

```text
D:\miniconda\py310\python.exe -m pytest backend/tests/test_embedding.py backend/tests/test_ai_provider.py backend/tests/test_ai_indexing.py backend/tests/test_retrieval.py backend/tests/test_context_assembler.py backend/tests/test_qa_api.py backend/tests/test_ai_citation_lifecycle.py backend/tests/test_ai_backup_restore.py backend/tests/test_backup_restore.py backend/tests/test_migrations.py
D:\miniconda\py310\python.exe -m pytest backend/tests/
```

建立最终矩阵：

| Gate | 证据 | 状态 |
|---|---|---|
| fake embedding deterministic | focused tests | implemented/backend-tested |
| embedding identity/codec/stale | focused tests | actual result |
| explicit indexing/rebuild/verify | focused tests | actual result |
| vector retrieval | focused tests | actual result |
| hybrid RRF | focused tests | actual result |
| explicit fallback | focused tests | actual result |
| Q&A lexical compatibility | focused/full tests | actual result |
| Q&A vector/hybrid integration | focused/full tests | actual result |
| citation validation/lifecycle | focused/full tests | actual result |
| backup/restore retrieval metadata | dedicated test | actual result |
| synthetic benchmark | benchmark output | actual result/not_verified |
| real embedding provider | opt-in smoke | actual result/not_verified |
| Chromium final acceptance | actual browser runner | actual result/not_verified |
| full backend suite | full pytest | actual result |

禁止用“代码已存在”替代测试证据。

---

## 8. Documentation closeout

更新：

- `docs/PHASE_ROADMAP.md`；
- `docs/STATUS.md`；
- `docs/TODO.md`；
- `docs/PROJECT_PROGRESS_REPORT.md`；
- 必要时 `docs/ARCHITECTURE.md` 或 `docs/ai-learning-architecture.md`。

必须明确：

- Phase 7.1–7.6 的实现和测试证据；
- Phase 7.7 每个 gate 的实际状态；
- fake embedding 与真实 embedding 的明确区别；
- LLM provider 与 embedding provider 的独立配置和证据；
- backup/restore 是否有专项 retrieval/Q&A metadata evidence；
- benchmark 的 synthetic/local/single-process/SQLite 限定；
- browser 是否实际执行；
- 未验证项和当前容量边界；
- 不支持多进程、多实例共享 data root、云同步、外部 vector DB 或生产规模容量。

只有当所有要求的 gate 都有实际证据时，才可把 Phase 7 标记为 `completed`。否则保持：

```text
Phase 7: partial
```

---

## 9. 完成判定

Phase 7.7 只能在以下条件全部满足时标记为 `completed`：

1. Phase 7.1–7.6 focused tests 通过；
2. 完整 backend suite 通过；
3. embedding/retrieval/Q&A/citation backup/restore 专项通过；
4. malformed/stale/failed/orphan lifecycle evidence 通过；
5. synthetic benchmark 已执行并报告适用边界；
6. 如声明真实 embedding 支持，则对应 provider gate 实际通过；否则明确 `not_verified`；
7. Chromium final acceptance 实际通过；
8. 文档、TODO、STATUS、roadmap 和 progress report 一致；
9. 没有泄露 secret、路径、SQL、traceback、raw provider response 或完整私有 source text；
10. 没有把 fake/backend/browser 局部结果夸大为全局 production `real-pass`；
11. 工作区只提交相关源代码、正式测试和文档，不提交数据库、artifact、`.backup/`、`.pi/`。

如果 real embedding 或 Chromium 未执行，Phase 7 不得标记 `completed`，只能标记：

```text
partial / backend-tested / real-pass not_verified
```

---

## 10. 最终报告格式

完成后按以下结构报告：

1. Phase 7.7 实现/验收摘要；
2. 修改文件和是否新增 migration；
3. backup/restore 专项结果；
4. corruption/lifecycle/rebuild 结果；
5. synthetic benchmark 数据、环境和容量边界；
6. LLM provider 与 embedding provider 配置/证据的独立说明；
7. real embedding gate 结果；
8. Chromium/browser gate 结果；
9. focused/full backend suite 结果；
10. 安全边界和未验证限制；
11. 最终 Phase 7 判断：`completed` / `partial` / `blocked`；
12. 后续 Phase 8 任务。
