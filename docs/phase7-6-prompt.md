# StudyBuddy Phase 7.6 执行 Prompt：Q&A、Citation、API/UI 的 Hybrid Retrieval 接入

> 用途：将本文完整复制给 coding agent，继续在 `H:\studybuddy` 内实现并验收 Phase 7.6。
>
> 范围：将已有 Phase 7.5 lexical/vector/hybrid retrieval 安全接入现有 Q&A、context assembly、citation verification、API 和必要的浏览器 UI 状态，同时保持 lexical-only 默认兼容。不要提前实现 Phase 7.7 最终验收，也不要宣称 Phase 7 completed 或 real-pass。

---

## 0. 角色与执行方式

你是 StudyBuddy 仓库中的资深 FastAPI、SQLite、RAG/Q&A、citation integrity、前端状态和测试工程师。请直接修改 production code、正式测试和文档，不要只给设计方案。

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
   - `docs/PHASE_ROADMAP.md`
   - `docs/STATUS.md`
   - `docs/TODO.md`
   - `docs/PROJECT_PROGRESS_REPORT.md`
   - `docs/ARCHITECTURE.md`
   - `docs/ai-learning-architecture.md`
   - `backend/app/main.py`
   - `backend/app/repository.py`
   - `backend/app/embedding.py`
   - `backend/app/providers.py`
   - `backend/app/config.py`
   - `backend/app/backup.py`
   - `backend/app/migrations/runner.py`
   - 现有 Q&A、citation lifecycle、context assembler、retrieval、provider、backup/restore、API boundary 和 browser tests
3. 先执行并记录：
   ```text
   git status --short
   git diff --stat
   git log -5 --oneline
   D:\miniconda\py310\python.exe -m pytest backend/tests/
   ```
4. 当前 HEAD 预期为：
   ```text
   713aee2 feat: complete phase 7.5 hybrid retrieval
   ```
5. 不覆盖工作区已有用户改动；不要提交 `.backup/`、`.pi/`、数据库、上传原件、provider key、secret、私有路径、测试 artifact、临时输出或生成文件。
6. 先审计现有 Q&A/retrieval/citation contract，再写 focused tests；实现后运行 focused suite、完整 backend suite，并在有用户可见 UI 变化时运行对应 Chromium focused E2E。
7. 诚实区分 `implemented`、`backend-tested`、`browser-tested`、`real-pass`、`not_verified`。Phase 7.6 完成不等于 Phase 7 完成。

---

## 1. 当前基线

### 1.1 Retrieval

Phase 7.5 已实现：

- `lexical_fts_v1`：既有 FTS5/Unicode retrieval；
- `vector_cosine_v1`：SQLite payload cosine retrieval；
- `hybrid_rrf_v1`：lexical + vector candidate 的确定性 RRF；
- `fallback_lexical_v1`：hybrid 显式允许时的 lexical fallback；
- `RRF_K = 60`；
- 固定 vector candidate pool；
- active material、current revision、ready chunk、project scope、identity/source binding 和 payload safety filters；
- retrieval run/hit 持久化 lexical/vector/final scores；
- `POST /api/retrieval` 已支持 `mode: lexical|vector|hybrid` 和 `allow_fallback`；
- legacy 默认 mode 仍为 lexical。

### 1.2 Current Q&A

当前 Q&A 已实现并通过 backend/browser tests：

- thread CRUD/list/history；
- `POST /api/qa/threads/{thread_id}/messages`；
- synchronous fake/LLM provider generation；
- `ai_operations` lifecycle 和 idempotency；
- retrieval run → context assembly → provider → persisted answer；
- citation key verification、citation lifecycle、source deletion/purge unavailable；
- multi-material scope、stale response guard、export/navigation；
- Q&A 现有路径默认调用 `run_chunk_retrieval()` lexical retrieval。

Phase 7.6 必须审计并修改这一调用路径，使 retrieval mode/policy 能安全选择，但不能破坏既有默认行为。

### 1.3 Architecture and safety

Source of truth 仍为：

```text
materials / extractions / text_spans
```

派生和用户状态：

```text
material_revisions / chunks / embeddings / retrieval_runs / retrieval_hits
qa_threads / qa_messages / qa_answers / qa_citations / ai_operations
```

禁止：

- 模型自行创建或修改 citation；
- 由 embedding 绕过 active/current/ready/source binding；
- Q&A 在无可验证 context 时自由回答并伪造引用；
- provider key、raw provider response、路径、SQL、traceback、完整私有正文泄露；
- startup 自动 embedding/indexing/provider probe；
- 外部 vector DB、后台 worker、多进程协调；
- 静默覆盖用户已有 Q&A、answer、citation 或确认状态。

---

## 2. Phase 7.6 目标

实现以下完整但受边界约束的离线/同步路径：

```text
material
  → explicit material/chunk indexing
  → optional embedding indexing
  → retrieval mode selection
  → lexical/vector/hybrid/fallback retrieval
  → context assembly
  → citation key verification
  → Q&A provider generation
  → persisted answer + operation + retrieval run + citations
  → history/detail/navigation/export
```

必须交付：

1. Q&A retrieval mode/policy 的明确选择边界；
2. lexical-only 默认兼容；
3. hybrid retrieval 接入 Q&A；
4. provider/index unavailable 时的安全 fallback 或稳定错误；
5. context assembler 继续只接受真实 retrieval hits；
6. citation 只能来自 verified context；
7. Q&A operation/retrieval metadata 可审计；
8. API 输入边界、project/material/thread scope 安全；
9. 必要的 UI mode/status/error/fallback 状态；
10. backup/restore 后 Q&A/retrieval/citation 状态保持；
11. focused/backend/browser tests 和文档收口。

本任务不做：

- 新的真实网络 embedding provider；
- Q&A 后台队列、真正 cancel、多 worker；
- cards、exercises、study plans；
- 新的外部 vector database；
- 重新设计已有 citation schema；
- Phase 7.7 最终 benchmark、真实 embedding acceptance 和全局 real-pass。

---

## 3. Retrieval mode contract for Q&A

### 3.1 Default compatibility

现有 Q&A client 不提供 mode 时，必须继续使用：

```text
lexical_fts_v1
```

并保持：

- 既有 request body 可用；
- 既有 response fields 可用；
- 既有 `retrieval_not_ready` / `retrieval_empty` 语义不改变；
- 既有 idempotency replay 行为不改变；
- 既有 thread/scope/citation/history 行为不改变；
- 不因 embedding 未配置而阻塞 lexical Q&A。

### 3.2 Explicit mode

可在现有 Q&A request body 中增加受限字段，例如：

```json
{
  "question": "...",
  "material_ids": [],
  "thread_id": "...",
  "top_k": 5,
  "retrieval_mode": "lexical|vector|hybrid",
  "allow_retrieval_fallback": true
}
```

字段名可适配现有项目风格，但必须：

- 默认 lexical；
- 只接受固定 enum；
- unknown mode 返回稳定 400 `retrieval_invalid_mode`；
- `top_k` 沿用 1–50 boundary；
- 不允许客户端传入 RRF_K、candidate pool、raw weights、policy SQL 或任意 policy version；
- `vector` 默认不 fallback；
- `hybrid` 的 fallback 是否默认开启必须固定、记录并测试；
- Q&A response 返回实际 `retrieval_mode`、`policy_version`、`fallback`/`fallback_reason`（如适合现有 response shape），不得暴露 raw exception。

如果为了保持旧 response shape 不扩展顶层字段，可以将安全 metadata 放入已有 retrieval/operation descriptor，但必须有可审计位置。

### 3.3 Provider/index behavior

固定行为：

- lexical：不调用 embedding provider；
- vector：query embedding/provider/index 不可用时稳定失败，不静默 fallback；
- hybrid + fallback enabled：embedding provider/index unavailable 时使用 lexical retrieval，并记录 `fallback_lexical_v1` 和 stable reason；
- hybrid + fallback disabled：稳定返回 embedding/index error；
- embedding payload corrupt/stale：跳过无效 candidate；如果没有 vector candidate，按 hybrid policy 走 lexical side 或 fallback/empty 语义；
- lexical 和 vector 都无结果：`retrieval_empty`；
- scope 没有 active/current/ready chunk：`retrieval_not_ready`；
- retrieval 不可用时不得让 Q&A provider 在没有 context/citations 的情况下自由回答。

### 3.4 Retrieval run metadata

Q&A 产生的 retrieval run 必须保留：

- `policy_version`；
- provider/model metadata（只有实际使用 query embedding 时写入 embedding provider/model）；
- status/error/fallback reason；
- project/thread scope 按现有契约；
- lexical/vector/final scores 在 hits 中保持准确；
- historical lexical run 不被重写；
- 不保存 query vector payload；
- 不保存 raw provider response 或不必要 source text。

如现有 schema 已足够，不新增 migration；发现真实 gap 才创建连续事务 migration。不得运行时 ad-hoc ALTER/CREATE。

---

## 4. Q&A pipeline integration

审计并修改现有 `create_qa_request()` / Q&A endpoint pipeline。推荐顺序：

```text
validate request and scope
→ reclaim/check idempotency operation
→ create/reuse user message + running operation
→ run selected retrieval policy
→ if retrieval failed/not-ready/empty, apply existing safe Q&A semantics
→ assemble context from persisted retrieval hits
→ call configured LLM provider
→ validate returned citation keys against assembled context
→ persist answer, citations, operation and retrieval_run_id atomically
→ return stable response
```

必须：

- retrieval mode 参与 input fingerprint/idempotency identity，避免同一 idempotency key 混用不同 mode；
- retry/replay 不重复 provider/artifact/citation；
- selected retrieval mode 和 policy 不被 provider response 覆盖；
- context assembler 输入必须来自 server-side persisted/verified retrieval hits；
- provider 只接收 assembled context 和 messages，不读取 SQLite/files；
- provider output 的 citation key 必须通过现有 `persist_qa_answer()` 或等价 server-side validator；
- invalid/unknown/out-of-context citation 不能作为可信 citation 写入；
- source deleted/purged 后 answer 保留，citation status 变为 unavailable，不能重新生成伪造 citation；
- question 无 ready scope、retrieval empty 或 provider unavailable 时采用现有安全错误/empty contract，不能无引用自由生成；
- database transaction rollback 不留下 succeeded answer、orphan citation 或错误 operation status。

不要重写既有 Q&A lifecycle；优先扩展参数和复用已有 helper。

---

## 5. Context and citation contract

### 5.1 Context

继续使用已有 `assemble_context()` 和 policy contract：

- token budget 有界；
- context blocks 有明确 citation key；
- chunk/material/revision/source binding 由服务端查询验证；
- 不把材料中的指令提升为 system/developer instruction；
- context 不足时 provider prompt 必须要求明确不知道；
- 不把 query vector 或 payload 放进 prompt；
- 不保存完整 prompt/source text 到日志或错误响应。

### 5.2 Citation

严格保持：

- citation key 只能来自 assembled context；
- model 只能返回已存在 key；
- quote/span/chunk 不能越界；
- citation status 必须经过 server-side validation；
- invalid key → `citation_invalid` 或现有正式等价状态；
- deleted/purged source → `source_deleted` / `source_unavailable` lifecycle；
- citation detail/navigation/export 不能回归；
- hybrid hit 的最终 rank/citation label 不得绕过 context assembler 的 citation key 生成规则；
- `retrieval_hits.citation_label` 不是模型可信 citation key 的唯一来源，不能允许模型任意构造。

新增或修改 citation 行为必须补测试：

- lexical Q&A citation regression；
- hybrid Q&A citation；
- fallback Q&A citation；
- invalid citation output；
- deleted/purged source；
- multi-material scope；
- stale/non-current chunk exclusion；
- answer/replay/history/export。

---

## 6. API contract

审计现有 API models/handlers，不要破坏已有客户端。

### Retrieval API

既有：

```text
POST /api/retrieval
```

保持：

- default lexical；
- mode `lexical|vector|hybrid`；
- `allow_fallback` 仅影响 hybrid；
- 稳定 input boundary 和 project/material filters。

### Q&A API

现有 endpoint 和 request schema 继续兼容。新增 retrieval mode 字段时：

- 默认值必须 lexical；
- mode 限制 enum；
- fallback bool 严格校验；
- 不能接受任意 dict 作为 policy；
- question/top_k/material_ids/thread_id 既有边界保留；
- unknown thread/material/project scope 稳定拒绝；
- response 不泄露 SQL/path/traceback/provider key/raw provider error/source full text；
- status code 与既有 provider/retrieval/error mapping 一致。

建议安全响应 metadata：

```json
{
  "retrieval": {
    "mode": "hybrid",
    "policy_version": "hybrid_rrf_v1",
    "fallback": false,
    "fallback_reason": null,
    "run_id": "retrieval_..."
  },
  "retrieval_run_id": "retrieval_...",
  "citations": []
}
```

字段名可以适配现有 schema，但必须让实际 mode/policy/run/fallback 可审计。

### Capabilities/UI

不要让 capabilities 触发 provider network probe。若 UI 显示 retrieval mode：

- 明确 lexical/vector/hybrid 当前状态；
- 显示 fallback/degraded/error/empty/loading；
- 不显示 key、URL、路径、raw provider error；
- 默认未配置 embedding 时仍可使用 lexical Q&A；
- 选择 hybrid/vector 时错误可恢复，不能卡死 Q&A thread；
- 新控件使用现有 UI conventions；
- 不为内部 policy version 增加无必要复杂页面。

---

## 7. Backup / restore and operation evidence

如 schema 不变，补现有 backup/restore 专项测试。使用 pytest `tmp_path`，不得提交数据库或 backup artifact。

至少验证：

1. 创建 lexical Q&A answer；
2. 创建 hybrid retrieval run/hits；
3. 创建 fallback retrieval run/hits；
4. 创建 answer/citation/ai_operation 关联；
5. backup → `verify_backup()` → restore 到新空目录；
6. 比较：
   - schema version/history；
   - retrieval run/hit count；
   - policy version；
   - embedding provider/model metadata；
   - lexical/vector/final scores；
   - fallback reason/error code；
   - Q&A answer/operation/retrieval_run_id/citations；
7. 恢复不调用 provider、不重建 embedding、不修改 citation status；
8. deleted/purged source 的 unavailable citation 状态保持。

发现真实 schema gap 才新增连续 migration；若 v5 足够，明确“不新增 migration”。

---

## 8. UI / browser scope

只有在确实需要用户选择 retrieval mode 或显示 fallback/status 时才修改 UI。

如果修改 UI，至少实现并测试：

- mode selection：lexical/vector/hybrid；
- safe default lexical；
- loading state；
- retrieval_not_ready；
- retrieval_empty；
- provider/index unavailable；
- hybrid fallback notice；
- Q&A success with citation navigation；
- invalid citation/source unavailable state；
- thread switch/new thread state 不串 retrieval metadata；
- narrow viewport 无横向溢出；
- keyboard/focus/label/status semantics 继续满足现有 P6-D contract。

使用现有浏览器测试风格和页面结构，不引入新框架或复杂依赖。没有实际 Chromium 结果不得声称 `browser-tested`。

---

## 9. Testing deliverables

至少新增或补充：

### Q&A backend

- default Q&A lexical regression exact pass；
- explicit hybrid Q&A uses `hybrid_rrf_v1`；
- explicit vector Q&A no silent fallback；
- hybrid fallback success/empty/not-ready；
- fallback reason sanitized；
- provider/index unavailable safe failure；
- embedding corrupt/stale candidate does not enter context；
- context blocks and citation keys remain server-verified；
- invalid provider citation output rejected；
- deleted/purged source citation lifecycle；
- multi-material scope；
- thread history and replay；
- idempotency key includes retrieval mode/policy/input fingerprint；
- operation/retrieval run linkage；
- transaction rollback.

### API boundaries/security

- missing/malformed mode；
- unknown mode；
- non-bool fallback；
- invalid top_k/question/material_ids/thread_id；
- project isolation；
- provider failure mapping；
- no secret/path/SQL/traceback/raw provider error/source full text leak。

### Backup/restore

- lexical/hybrid/fallback retrieval metadata；
- answer/operation/citation linkage；
- payload/status/history preserved；
- provider not called on restore；
- deleted/purged unavailable status preserved。

### Browser

如修改 UI，运行对应 focused suites：

```text
D:\miniconda\py310\python.exe -m pytest backend/tests/browser_qa.spec.js
D:\miniconda\py310\python.exe -m pytest backend/tests/browser_p6d.spec.js
D:\miniconda\py310\python.exe -m pytest backend/tests/browser_p6e.spec.js
```

实际命令以仓库浏览器测试工具链为准；不要把 Python pytest 误报为 Chromium 证据。没有运行或失败时如实报告。

### Regression commands

```text
D:\miniconda\py310\python.exe -m pytest backend/tests/test_embedding.py backend/tests/test_ai_provider.py backend/tests/test_ai_indexing.py backend/tests/test_retrieval.py backend/tests/test_context_assembler.py backend/tests/test_qa_api.py backend/tests/test_ai_citation_lifecycle.py backend/tests/test_ai_backup_restore.py backend/tests/test_backup_restore.py
D:\miniconda\py310\python.exe -m pytest backend/tests/
```

---

## 10. Migration and documentation decision

先审计 v5 和现有 Q&A schema。只有发现真实 gap 才创建连续 migration。

如果不新增 migration，文档必须说明：

```text
Phase 7.6 uses existing v5 embedding schema and existing Q&A/citation schema;
no migration was necessary.
```

如果新增 migration，必须：

- 版本连续、事务化、幂等；
- rollback test；
- old database upgrade test；
- `schema_migrations` 与 `PRAGMA user_version` 一致；
- backup/restore history test；
- 不修改 v1–v5 history；
- 不在 startup/repository ad-hoc ALTER/CREATE。

更新：

- `docs/PHASE_ROADMAP.md`；
- `docs/STATUS.md`；
- `docs/TODO.md`；
- `docs/PROJECT_PROGRESS_REPORT.md`；
- 必要时 `docs/ai-learning-architecture.md`。

文档必须明确：

- Phase 7.6 `implemented / backend-tested`、`browser-tested`、`partial` 或 `blocked`；
- Q&A 默认 lexical 和 explicit hybrid/vector 行为；
- fallback 和 citation safety；
- backup/restore evidence；
- 真实 embedding provider、最终验收、规模性能和多进程边界仍未验证。

---

## 11. 完成判定

只有满足以下条件，Phase 7.6 才能标记 `implemented / backend-tested`：

1. Q&A 默认 lexical path 完整回归通过；
2. Q&A 可以显式选择 hybrid/vector/lexical，且 mode/policy 不被客户端任意覆盖；
3. hybrid 使用真实 retrieval run/hits 并正确链接 operation、answer 和 citations；
4. vector-only 不静默 fallback，hybrid fallback 只按显式 policy 发生；
5. context assembler 只接受 active/current/ready、source-bound、server-verified hits；
6. citation 只能来自 assembled context，invalid/deleted/purged citation 安全处理；
7. idempotency、thread history、multi-material scope、stale response 和 export/navigation 不回归；
8. provider/index failure 不泄露 raw error，不让 Q&A 无引用自由回答；
9. backup/restore 保留 retrieval/Q&A/operation/citation metadata；
10. focused tests 与完整 backend suite 通过；
11. 如有 UI 变化，Chromium focused E2E 有实际结果；
12. 文档状态与实现、测试证据一致。

Phase 7.6 完成不等于 Phase 7 完成。仍需 Phase 7.7：

```text
最终 embedding/retrieval backup/restore 专项
→ synthetic benchmark / performance boundary
→ real provider gate（如配置）
→ Chromium final acceptance
→ full regression and final status closeout
```

---

## 12. 最终报告格式

完成后按以下结构报告：

1. 实现摘要；
2. 修改文件（production/migration/tests/docs/ui）；
3. Q&A retrieval mode/policy/fallback 行为；
4. context/citation 验证与 source lifecycle；
5. operation/idempotency/thread/scope linkage；
6. schema/migration/backup/restore 结论；
7. focused/full backend/Chromium 测试结果；
8. 安全边界与未验证限制；
9. Phase 7.6 判断：`implemented` / `partial` / `blocked`；
10. Phase 7.7 剩余任务。
