# StudyBuddy Phase 7 执行实现 Prompt

> 用途：将本文完整复制给 coding agent，作为 StudyBuddy Phase 7「Embedding 与 Hybrid Retrieval」的执行任务说明。
>
> 文档性质：执行 prompt，不代表 Phase 7 已实现。实现完成后，必须根据代码、测试和可复现验收证据更新 `docs/PHASE_ROADMAP.md`、`docs/STATUS.md`、`docs/TODO.md` 和 `docs/PROJECT_PROGRESS_REPORT.md`。

---

## 0. 你的角色与执行方式

你是 StudyBuddy 仓库中的资深后端、检索系统和测试工程师。请在 `H:\studybuddy` 内直接完成 Phase 7 的可验收实现，不要只给设计方案。

执行要求：

1. 先阅读并遵守根目录 `AGENTS.md`。
2. 阅读以下上下文文件，确认当前正式契约后再改代码：
   - `README.md`
   - `docs/PHASE_ROADMAP.md`
   - `docs/STATUS.md`
   - `docs/TODO.md`
   - `docs/PROJECT_PROGRESS_REPORT.md`
   - `docs/ARCHITECTURE.md`
   - `docs/ai-learning-architecture.md`
   - `backend/app/migrations/runner.py`
   - `backend/app/repository.py`
   - `backend/app/providers.py`
   - 相关 AI indexing/retrieval/Q&A/migration/backup 测试
3. 先检查当前 git diff、测试基线和现有 schema，不要覆盖已有用户改动。
4. 使用项目 Python 环境运行测试：
   ```text
   D:\miniconda\py310\python.exe -m pytest backend/tests/
   ```
5. 先做 focused implementation 和 focused tests，再运行完整 backend suite；如有 UI/API 变化，再运行对应 Chromium E2E。
6. 每一个实现结论必须有代码、测试和可复现证据。`implemented` 不等于 `real-pass`，不能夸大验证范围。
7. 发现现有契约与本 prompt 冲突时，以仓库当前正式实现、`AGENTS.md` 和路线图中的安全边界为准，并在最终报告中说明。

---

## 1. 项目当前上下文

StudyBuddy 是本地、单进程、单实例的学习材料管理系统：

- FastAPI 后端；
- SQLite 数据库；
- 本地 hash-derived original storage；
- 内嵌浏览器 UI；
- 当前支持的部署边界是单进程、单实例、本地磁盘；
- 不支持多个 worker/多个实例共享同一 `data_root`；
- 不引入 React/Vite、Electron、云同步、多用户或外部服务作为本 Phase 的前置条件。

当前已完成的前置能力：

1. 文件解析、导入、批量/文件夹导入、材料列表、搜索、生命周期和导出；
2. I1 migration/schema versioning；
3. I2 backup/restore operator 闭环；
4. I3 最小可观察性；
5. I4 真实环境/容量基线时间盒收口，并明确未验证边界；
6. Phase 4：material revision、deterministic chunking、chunk FTS5 lexical retrieval、retrieval runs/hits、context assembly、citation verification、deterministic fake provider、Q&A API/UI；
7. Phase 5：OpenAI-compatible LLM adapter、配置隔离、稳定错误映射，且 DeepSeek `deepseek-chat` 与 Agnes `agnes-2.5-flash` 有精确 smoke evidence；
8. Phase 6 P6-A–P6-E：Provider 状态、Q&A thread、跨材料 scope、citation 导航/导出、统一导航/状态/响应式/基础可访问性，以及 fake Provider 核心工作流验收。

当前 Phase 7 状态：**延后/未开始**。目标是在已有 lexical retrieval 之上，增加可重建、可验证、可回退的 embedding 与 hybrid retrieval；不能破坏现有 lexical-only 路径和 citation contract。

---

## 2. Phase 7 目标与非目标

### 2.1 总目标

实现一个 SQLite-first 的 embedding 与 hybrid retrieval 最小闭环：

```text
ready chunk
  → content hash / source revision identity
  → embedding provider
  → persisted embedding payload
  → vector similarity candidates
  → lexical + vector hybrid merge
  → deterministic ranking
  → existing context assembly
  → existing verified citations / Q&A
```

要求在 embedding provider 未配置、不可用、超时、返回异常或 embedding 索引缺失时，系统仍可安全运行，并能明确回退到 lexical retrieval 或返回稳定、可诊断但不泄露敏感信息的错误状态。

### 2.2 明确非目标

本 Phase 不做：

- 外部 vector database、ANN 服务或云索引；
- 多进程/多实例 embedding worker；
- 后台队列、真正的 cancel、跨进程协调；
- 自动在 startup 大规模生成 embedding；
- OCR、ASR、cards、exercises、study plans；
- 改变已有 source of truth；
- 让模型自行生成或修改 citation；
- 以 embedding 结果绕过 material deleted/current revision/ready chunk 过滤；
- 声称达到全局生产级 `real-pass`；
- 为了追求“智能”引入未经证据支持的复杂 reranker 或外部依赖。

Phase 7 首选 SQLite 内存/数据库内计算。若当前数据规模不足以证明需要 ANN，不得引入外部 vector DB。

---

## 3. 必须遵守的架构与安全原则

### 3.1 Source of truth 与派生数据

`materials`、`extractions`、`text_spans` 是 source of truth。`material_revisions`、`chunks`、`embeddings`、`retrieval_runs`、`retrieval_hits`、Q&A 和学习产物属于可追溯派生数据或用户状态。

- 不修改原始材料正文来生成 embedding；
- embedding 必须绑定 `chunk_id`、`source_revision`、`content_hash`、`provider_id`、`model_id`、`dimensions` 和模型版本语义；
- chunk 文本变化、revision 变化、provider/model 变化、dimensions 变化时，旧 embedding 必须被视为 stale 或 incompatible，不能静默复用；
- deleted material、非 current revision、非 ready chunk 不得进入 vector candidate 或 hybrid result；
- purge 后派生 embedding 必须按已有生命周期规则删除或明确不可用，不能产生 orphan embedding。

### 3.2 Provider 安全边界

实现 `EmbeddingProvider` protocol/adapter/registry 时遵循现有 LLM provider 契约：

- 配置来自环境变量或现有配置对象；
- API key 只能驻留内存，不写入数据库、manifest、日志、错误响应或测试 artifact；
- 不记录完整 prompt、chunk 正文、向量 payload、路径、raw provider response 或 traceback；
- 对 URL、timeout、响应体大小、batch size、文本长度和 vector dimensions 做硬限制；
- provider 错误转换为稳定错误码，不暴露 raw provider error；
- fake embedding provider 必须 deterministic、离线、可重复，便于默认测试；
- provider 未配置时材料管理和 lexical Q&A 必须继续可用。

建议沿用现有稳定错误体系，并在必要时增加明确、脱敏的 embedding 错误码，例如：

- `embedding_provider_not_configured`
- `embedding_provider_unavailable`
- `embedding_provider_timeout`
- `embedding_provider_rate_limited`
- `embedding_provider_auth_failed`
- `embedding_provider_invalid_response`
- `embedding_dimension_mismatch`
- `embedding_index_stale`
- `embedding_index_unavailable`

不要为了凑错误码而重复已有错误；先检查当前 provider 错误映射，再复用或扩展正式契约。

### 3.3 Migration 与备份

所有 schema 变化必须通过 `backend/app/migrations/runner.py`：

- migration 版本必须连续、幂等、事务化；
- 保持 `schema_migrations` 与 `PRAGMA user_version` 一致；
- 不得在业务代码、startup repair 或测试 setup 中 ad-hoc 创建业务表；
- 覆盖升级成功、重复执行、失败 rollback、旧库升级和 backup/restore 版本一致性；
- 如果已有 `embeddings` 预留表，先审计其真实字段、约束和使用情况，优先通过后续 migration 安全补齐，而不是重复创建或破坏已有数据。

新增/调整的 embedding 数据必须进入现有 SQLite Online Backup 和 restore 验证边界。backup/restore 不应隐式调用 embedding rebuild；恢复后应保留已存 embedding、stale 状态和 manifest 元数据。

---

## 4. 执行任务清单

请将 Phase 7 拆成以下 **7 个必须交付的子任务**，按依赖顺序执行。每个子任务都需要实现、测试、文档和验收证据。

### 7.1 现状审计与契约冻结

- 审计已有 `embeddings`、`retrieval_runs`、`retrieval_hits`、chunking、repository 和 migration 实现；
- 列出已有字段、未使用字段、兼容性风险和需要新增的 migration；
- 固定 embedding identity、status、stale、provider/model/dimension 和 retrieval policy 语义；
- 固定 lexical-only、vector-only、hybrid、fallback 的行为；
- 将审计结果写入适当的 `docs/` 文档或决策记录，不创建临时根目录 Markdown。

### 7.2 Embedding Provider Protocol、fake provider 与配置

实现或补齐：

- `EmbeddingProvider` protocol；
- registry 和 provider capability 描述；
- deterministic fake provider：同一规范化输入和 model 配置产生稳定向量；
- batch embedding 接口，限制 batch 数量、文本长度和输出维度；
- 环境变量配置，至少覆盖 provider、model、timeout、batch/text/output limit；
- capabilities API 的安全扩展，不返回 key 或敏感 URL；
- 稳定的 provider error mapping、retry 边界和 malformed response 防护。

Fake provider 不得依赖网络或随机数；如使用哈希生成向量，必须定义稳定算法、归一化规则和版本号，避免 Python 内置 hash 的进程随机化。

### 7.3 Embedding schema、payload codec 与 stale semantics

通过 migration 实现可审计的数据模型，至少能表达：

- embedding id、chunk id；
- provider id、model id、model revision；
- dimensions；
- vector encoding/version；
- vector payload；
- content hash；
- source revision；
- status、error code、created/updated 时间；
- 唯一身份约束，避免同一 chunk/provider/model/content 重复写入。

实现 payload codec：

- 明确定义 float 编码、endianness、精度、归一化和版本；
- decode 前校验 payload 长度与 dimensions；
- 损坏 payload 只能进入明确失败/不可用路径，不得让请求崩溃；
- 不把正文或 secret 写入 payload metadata；
- 测试 round-trip、dimension mismatch、截断 payload、NaN/Infinity、空向量和异常编码。

实现 stale 判定：

- content hash 不一致；
- source revision 不一致；
- provider/model/model revision 不一致；
- dimensions/encoding version 不一致；
- 明确区分 `ready`、`stale`、`failed`、`running` 或当前项目采用的等价状态；
- stale 数据可保留用于诊断，但默认不得参与 retrieval。

### 7.4 Indexing、rebuild、verify 与生命周期

实现可重复的 embedding indexing 入口，优先提供 repository/service/CLI 中清晰的离线调用边界：

- 只处理 active material、current revision、ready chunk；
- 支持单材料、单 revision 或项目范围的增量 indexing；
- 已有相同 identity 的 ready embedding 不重复调用 provider；
- 支持失败记录和可重试；
- 不在应用启动时偷偷进行全量 embedding；
- 提供 rebuild/verify 机制或等价的显式命令/服务接口；
- verify 检查 schema、identity、dimensions、payload、content hash、source revision、孤儿记录和状态；
- rebuild 不覆盖用户状态，不删除历史 Q&A/citation；
- purge/delete/restore 行为与现有 material/chunk 生命周期一致。

如果使用 SQLite BLOB，不要额外创建不受 backup/manifest 管理的隐藏索引文件。若确实需要文件索引，必须增加版本化 manifest、content hash、provider/model/policy 信息、verify 和 rebuild，并将其纳入备份设计；在没有必要性证据时不要走此方案。

### 7.5 Vector similarity 与 Hybrid Retrieval

在现有 retrieval contract 上扩展，而不是重写 Phase 4 lexical 路径：

- 保留 lexical retrieval 的确定性排序和 `retrieval_empty` 语义；
- 增加 vector candidate retrieval；
- 明确定义相似度（优先 cosine；说明是否要求向量归一化）；
- 明确定义 top-k、候选池大小、tie-breaker 和数值精度；
- 实现 hybrid merge，例如 reciprocal rank fusion 或可解释加权融合；
- 记录 lexical score、vector score、hybrid/final score；
- 所有排序必须确定性，分数相同时按稳定字段排序；
- 支持 policy version，避免未来调参后无法解释历史 retrieval run；
- `retrieval_runs` / `retrieval_hits` 保存足够元数据用于审计，但不得保存不必要的正文；
- vector 不可用时按明确 policy 回退 lexical，并记录 fallback 原因；
- lexical 和 vector 都没有可用结果时返回 `retrieval_empty`，不能让 Q&A 无引用自由回答。

注意：不要仅因为 embedding 表或 score 字段存在，就宣称 hybrid 已完成。必须有真实调用路径、持久化 run/hit、citation 继续可验证，并有测试证据。

### 7.6 Q&A、citation、API/UI 与兼容性

将 hybrid retrieval 接入现有 Q&A，但必须保持默认路径稳定：

- fake Provider + fake embedding 下可以离线重复验收；
- 未配置 embedding 时现有 lexical-only Q&A 仍能工作；
- provider timeout/rate-limit/unavailable/invalid vector 时 UI 显示安全错误或 lexical fallback；
- citation 只能来自 retrieval/context 中真实存在且通过验证的 chunk key；
- deleted、purged、stale source 的 citation lifecycle 不能回归；
- 现有 thread、multi-material scope、idempotency、stale response guard 和 export/navigation 不能回归；
- 如新增 API，补齐输入边界、权限/项目边界、稳定 response schema、错误码和不泄露数据检查；
- 如不需要新增 UI，不要为了展示而引入复杂前端；但至少应让当前 Provider/retrieval mode/status 可解释。

### 7.7 测试、基线和文档收口

至少补充以下测试类别：

- provider protocol、fake determinism、配置脱敏；
- payload codec round-trip 和损坏边界；
- migration upgrade/idempotence/rollback；
- stale semantics 与 content/revision/model 变化；
- indexing 去重、失败重试、部分成功、生命周期；
- cosine/vector ranking、hybrid merge、tie-breaker、empty/fallback；
- deleted/current/ready/source-unavailable 过滤；
- retrieval run/hit 审计字段；
- backup/restore 后 embedding 可用性和 stale 保留；
- Q&A citation regression、idempotency、thread/scope stale response；
- API secret/path/raw error/source text 不泄露；
- 如有用户可见路径，增加 Chromium focused E2E。

建立可复现的检索质量和性能基线：

- 使用合成材料和固定 query，不上传私有材料、不提交 provider key；
- 比较 lexical-only、vector-only、hybrid 的候选命中和排序；
- 记录环境、数据规模、provider/model、policy version、耗时和限制；
- 不把单一 synthetic benchmark 夸大为通用质量结论。

---

## 5. 建议的实现顺序

```text
现状审计/契约冻结
→ migration/schema 补齐
→ EmbeddingProvider + deterministic fake
→ payload codec + stale semantics
→ indexing/rebuild/verify
→ vector similarity
→ hybrid retrieval
→ Q&A/citation/API/UI 接入
→ focused tests
→ backup/restore tests
→ full backend suite
→ browser E2E/基线
→ 文档和 TODO 收口
```

不要在 Phase 7 中同时开发 cards、exercises、study plans、worker 或多用户能力。

---

## 6. Phase 7 完成标准

只有同时满足以下条件，才可将 Phase 7 标记为 completed：

1. 有正式 migration（如 schema 需要变化），且 migration 连续、幂等、事务化、有 rollback 测试；
2. EmbeddingProvider protocol、registry、deterministic fake provider 和安全配置已实现；
3. embedding identity、payload encoding、dimensions、content hash、source revision 和 stale semantics 已实现并测试；
4. 有显式 indexing/rebuild/verify 边界，不在 startup 偷跑，不产生未纳入 backup 的隐式状态；
5. vector similarity 和 hybrid merge 有确定性排序、policy version、fallback 和 empty 语义；
6. retrieval runs/hits 能记录 lexical/vector/final 分数，并继续支持可验证 citation；
7. deleted material、非 current revision、非 ready chunk、purged source 均不被错误检索；
8. fake embedding 下有离线、可重复的完整用户路径：
   ```text
   material → ready chunk → embedding → hybrid retrieval → context → Q&A → citation
   ```
9. 未配置或 embedding 失败时，lexical-only 旧路径不回归，且错误安全可解释；
10. backup/restore、API 安全边界、Q&A history/thread/idempotency/citation regression 已通过；
11. focused tests、完整 backend suite 和必要的 Chromium E2E 均有结果；
12. `STATUS.md`、`PHASE_ROADMAP.md`、`TODO.md`、`PROJECT_PROGRESS_REPORT.md` 与真实状态一致；
13. 最终报告明确区分 `implemented`、`backend-tested`、`browser-tested`、`real-pass` 和 `not_verified`；
14. 没有提交数据库、上传原件、生成 artifact、secret、provider key、私有路径或测试输出。

如果只完成 lexical/vector 的部分底层能力，必须标记为 partial，而不是完成 Phase 7。

---

## 7. 最终交付报告格式

完成或暂停时，请用以下结构报告：

1. **实现摘要**：完成了哪些子任务，哪些未完成；
2. **修改文件**：按 production code、migration、tests、docs 分类列出；
3. **Schema/migration**：版本、升级、rollback、backup/restore 结果；
4. **Provider 与 payload**：配置、错误码、codec、dimension/stale 规则；
5. **Retrieval 行为**：lexical/vector/hybrid/fallback/empty 的精确定义；
6. **测试结果**：focused、完整 backend、Chromium、benchmark 命令与结果；
7. **安全检查**：secret、路径、正文、raw error、payload 和日志边界；
8. **已知限制**：真实 embedding provider、规模、性能、长时间运行、断电、多进程等未验证项；
9. **Phase 7 完成判断**：`completed` / `partial` / `blocked`，并给出证据理由；
10. **下一步**：若 Phase 7 completed，下一阶段按路线图进入 Phase 8 Cards/Exercises；否则列出剩余阻塞项。

---

## 8. 重要提醒

- 不要把已有 schema 预留字段当作已实现功能。
- 不要为了通过测试删除或放宽安全边界。
- 不要暴露原始 provider 错误、API key、文件路径、SQL、traceback 或完整源文本。
- 不要声称支持多进程、多 worker、共享 data root、真实断电恢复或外部 vector DB。
- 不要让 embedding provider 的接入阻塞 lexical-only 可用性。
- 不要让模型生成的 citation 绕过 server-side validation。
- 不要静默覆盖用户已有的 Q&A、卡片、练习或确认状态。
- 所有不确定项都记录为 `not_verified`，并在最终报告中诚实说明。
