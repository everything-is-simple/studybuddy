# StudyBuddy Phase 7.2 执行 Prompt：Embedding Provider Protocol、fake provider 与配置

> 用途：将本文完整复制给 coding agent，继续在 `H:\studybuddy` 内实现 Phase 7.2。
>
> 目标：只完成并验收 Phase 7.2，不提前宣称 Phase 7 completed；不得把未实现的 hybrid、fallback、真实 embedding provider 或 Q&A 接入伪装成已完成。

---

## 0. 角色与执行方式

你是 StudyBuddy 仓库中的资深 Python/FastAPI provider、配置、安全和测试工程师。请直接修改仓库代码、测试和文档，不要只给设计方案。

必须遵守：

1. 先阅读根目录 `AGENTS.md`。
2. 阅读并遵守：
   - `README.md`
   - `docs/PHASE7_1_AUDIT_AND_CONTRACT.md`
   - `docs/phase7-prompt.md`
   - `docs/PHASE_ROADMAP.md`
   - `docs/STATUS.md`
   - `docs/TODO.md`
   - `docs/PROJECT_PROGRESS_REPORT.md`
   - `docs/ai-learning-architecture.md`
   - `backend/app/providers.py`
   - `backend/app/embedding.py`
   - `backend/app/config.py`
   - `backend/app/main.py`
   - `backend/app/repository.py`
   - 相关 provider、config、retrieval、migration、backup/restore 测试
3. 先检查当前 `git status`、`git diff`、最近提交和测试基线；不得覆盖已有用户改动。
4. 使用项目 Python 环境：
   ```text
   D:\miniconda\py310\python.exe -m pytest backend/tests/
   ```
5. 先运行 focused tests，再运行完整 backend suite。
6. 每个结论必须有代码、测试和可复现命令证据。`implemented`、`backend-tested`、`browser-tested`、`real-pass` 必须区分。
7. 不提交数据库、上传原件、provider key、secret、私有路径、测试输出或生成 artifact。

---

## 1. 当前代码基线与已存在能力

当前仓库已完成 Phase 7.1 契约冻结，并已提交 Phase 7 embedding foundation：

```text
commit: eaae5d0 feat: add phase 7 embedding foundation
```

当前 schema version 为 **5**，v5 migration 已包含：

- `embeddings.model_revision` 非 NULL；
- `embeddings.updated_at`；
- `status CHECK(running/ready/stale/failed)`；
- 完整 embedding identity 唯一约束：
  ```text
  (chunk_id, source_revision, content_hash, provider_id, model_id,
   model_revision, dimensions, vector_encoding)
  ```
- 旧 v4 embedding rows 不会静默变成 ready。

当前已有但需要审计、补齐和重构的代码：

### `backend/app/embedding.py`

当前已有：

- `EmbeddingError`；
- `EmbeddingProvider` protocol；
- `FakeEmbeddingProvider`；
- `normalize_embedding_text()`；
- `embedding_content_hash()`；
- `encode_vector()` / `decode_vector()`；
- `cosine_similarity()`；
- 常量 `EMBEDDING_ENCODING = "f32le_v1"`、batch/text/dimension 上限。

必须检查并改进：

- protocol 是否足够表达 provider identity、model identity、model revision、dimensions、batch contract 和 capability；
- fake 算法是否明确、稳定、可跨进程/跨运行重复；
- 输入规范化、向量生成、输出校验、错误码是否符合本 prompt；
- 不应删除现有 codec contract 或破坏 Phase 7 已有 tests。

### `backend/app/providers.py`

当前已有 LLM provider registry，并已尝试加入 embedding provider 入口。必须避免把 LLM provider 和 embedding provider 的配置、capability、错误映射混在一起。

要求：

- LLM 旧行为必须保持回归通过；
- embedding provider 应有独立的 protocol、registry 或明确的 embedding registry 结构；
- 测试 monkeypatch 只提供旧 LLM registry 接口时，不能因 indexing 路径强行要求其具备 embedding 方法而回归失败；
- fake embedding 不应依赖 LLM fake provider 的 model id。

### `backend/app/config.py`

当前主要是 LLM 配置，尚未完整加入 embedding 专用配置。需要新增安全、边界明确的 embedding 配置字段。

### `backend/app/main.py`

当前 `/api/ai/capabilities` 主要返回 LLM capability；`POST /api/materials/{id}/ai-index` 在 fake 配置下已经有 embedding indexing 最小路径；`POST /api/retrieval` 已有 lexical/vector mode 最小路径。

Phase 7.2 重点是 provider/config/capabilities foundation，不要在本任务重写 retrieval、hybrid 或 Q&A。

### 当前测试基线

Phase 7 foundation 完成时曾验证：

```text
205 passed, 2 skipped
```

当前实现前必须重新运行，因为工作区可能有变更。

---

## 2. Phase 7.2 目标

实现并测试一个独立、安全、可重复的 embedding provider layer：

```text
normalized text
  → EmbeddingProvider
  → deterministic vector / provider response
  → validated dimensions and finite values
  → payload codec/indexing caller
```

本任务必须交付：

1. `EmbeddingProvider` protocol；
2. embedding provider registry；
3. provider capability 描述；
4. deterministic fake provider；
5. batch embedding 接口和输入/输出限制；
6. embedding 专用环境变量配置；
7. `/api/ai/capabilities` 的安全 embedding capability 扩展；
8. stable provider error mapping、retry boundary 和 malformed response 防护；
9. focused tests、完整 backend regression 和文档状态同步。

本任务不做：

- 外部 vector database；
- ANN index；
- 后台 worker、队列、多进程协调；
- startup 自动 indexing；
- hybrid RRF；
- fallback retrieval 行为的最终实现；
- Q&A/citation 全链路重写；
- cards、exercises、study plans；
- 真实 provider 的未经 opt-in 网络 smoke。

---

## 3. 冻结的 provider contract

### 3.1 Protocol

建议实现为清晰的 Python `Protocol`，但以当前项目风格为准：

```python
class EmbeddingProvider(Protocol):
    provider_id: str
    model_id: str
    model_revision: str
    dimensions: int
    encoding: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate one vector per input text, synchronously."""
        ...

    def capabilities(self) -> dict[str, object]:
        ...
```

如果当前正式接口不适合直接增加 `capabilities()`，可以通过 registry/capability descriptor 提供，但必须保证调用方不依赖 provider 私有字段猜测能力。

固定语义：

- `provider_id`、`model_id`、`model_revision` 必须是非空稳定字符串；
- `model_revision` 缺失时在配置/adapter 边界规范化为稳定空字符串或明确版本值，不能使用 nullable identity；
- `dimensions` 必须是正整数且不超过硬上限；
- `encoding` 必须带版本，例如 `f32le_v1`；
- `embed(texts)` 必须返回与输入数量完全相同的 vectors；
- 每个 vector 长度必须等于 `dimensions`；
- 每个值必须是 finite number；
- 空文本、超长文本、超大 batch、malformed output 必须返回稳定 `EmbeddingError.code`，不能泄露 provider 原文。

### 3.2 规范化输入

必须明确并测试规范化算法。建议继续使用：

```python
normalized = " ".join(text.split())
```

要求：

- 同一规范化文本产生相同向量；
- 前后空白、连续 Unicode whitespace 的处理必须有测试；
- 不得把 query normalization 误称为 embedding normalization；
- 不修改原始 chunk 正文；
- content hash 使用 embedding 输入文本的 UTF-8 SHA-256；
- 不把正文写入日志、capability、错误响应或 provider metadata。

---

## 4. Deterministic fake provider

实现或重构 `FakeEmbeddingProvider`，要求：

- 不联网；
- 不依赖 Python 内置 `hash()`；
- 不依赖随机数、时间、进程 ID 或机器路径；
- 同一规范化输入 + 同一 provider/model/model_revision/dimensions 配置，在不同进程和不同运行中产生完全相同结果；
- provider/model/model revision/dimensions 变化时，必须能产生不同 identity 或明确拒绝，而不能静默复用旧 vector；
- 算法必须包含显式版本，例如：
  ```text
  fake_embedding_algorithm = sha256_bucket_v1
  ```
- 若使用哈希生成 float，必须明确：
  - hash 输入构造；
  - byte order；
  - 每个维度的映射方式；
  - float 范围；
  - 是否归一化；
  - zero-vector 如何处理；
  - 算法版本升级时的兼容语义。

建议使用 SHA-256 派生每一维的稳定 bytes，再映射到 `[-1, 1]`，最后按固定规则归一化；不要使用 Python `hash()`。

建议增加公开或内部常量：

```python
FAKE_EMBEDDING_PROVIDER_ID = "fake"
FAKE_EMBEDDING_MODEL_ID = "fake-embedding-v1"
FAKE_EMBEDDING_MODEL_REVISION = "1"
FAKE_EMBEDDING_ALGORITHM_VERSION = "sha256_bucket_v1"
```

Fake provider 的 capability 必须明确标记：

```json
{
  "runtime_kind": "deterministic_demo",
  "verification_status": "not_applicable",
  "network_required": false,
  "supports": {
    "embeddings": true,
    "batch": true
  }
}
```

不得把 fake provider 宣称为真实 provider verified。

---

## 5. Batch contract 与硬限制

至少增加或明确以下配置和硬限制：

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

可以采用不同命名，但必须在代码、`.env.example` 或正式文档中冻结实际名称。

建议边界：

- timeout：`0.1`–`120` 秒；
- batch size：`1`–`32`；
- text chars：`1`–`12000`；
- dimensions：`1`–`4096`；
- response bytes：合理硬上限，不能无限读取；
- retries：默认 `0`，最多 `2`；
- 不能接受 bool 冒充 int；
- 配置解析失败必须返回稳定 `invalid_*` 错误，不暴露原始 `ValueError`。

`embed(texts)` 必须拒绝：

- 非 list；
- 空 list（如果项目选择允许空 batch，必须明确并全程一致）；
- 超过 batch 上限；
- 非字符串 item；
- 空规范化文本；
- 超过文本长度；
- provider 返回数量不匹配；
- provider 返回非 list/non-number/NaN/Infinity；
- vector dimensions 不匹配；
- response bytes 超限。

---

## 6. Registry 与 capability descriptor

实现独立 embedding registry，推荐接口类似：

```python
class EmbeddingProviderRegistry:
    def configured_provider(self) -> EmbeddingProvider:
        ...

    def capabilities(self) -> dict[str, object]:
        ...
```

必须支持：

### 未配置

```json
{
  "status": "not_configured",
  "configured": false,
  "runtime_kind": "none",
  "verification_status": "not_applicable",
  "provider_id": null,
  "model_id": null,
  "model_revision": null,
  "supports": {"embeddings": false, "batch": false}
}
```

### fake/demo

必须显示：

- `status: demo`；
- provider/model/model revision；
- dimensions 和 encoding；
- batch/text/output limits；
- `runtime_kind: deterministic_demo`；
- `network_required: false`；
- 不包含 key 或 URL。

### 配置不完整/非法

返回或映射为稳定错误，例如：

```text
embedding_provider_invalid_config
embedding_provider_not_configured
embedding_invalid_timeout
embedding_invalid_batch_size
embedding_invalid_text_limit
embedding_invalid_dimensions
embedding_invalid_response_limit
```

不要把 secret、Authorization、完整 base URL、环境变量值或 traceback 返回给 API/UI。

### generic configured provider

Phase 7.2 可以先只建立 registry/capability skeleton，不必在无明确协议证据时实现真实网络 adapter；但如果实现 generic adapter，必须：

- 使用显式 HTTPS/loopback URL policy；
- API key 只在内存中；
- 不写数据库、manifest、日志或响应；
- 对 response body 设置读取上限；
- 对 timeout、429、401/403、5xx、网络错误、malformed JSON、schema mismatch 做稳定映射；
- 默认不 retry，或仅对明确 retryable error 重试有限次数；
- 不对 auth、invalid request、dimension mismatch、malformed response 自动 retry。

---

## 7. 配置对象和环境变量

扩展 `AppConfig`，但必须保持旧构造调用兼容。现有测试经常使用：

```python
AppConfig(data_root=root, max_upload_bytes=4096)
```

新增字段必须有安全默认值，不得要求既有测试和未配置环境必须提供 embedding 配置。

建议新增：

```python
embedding_provider_id: str | None
embedding_model_id: str | None
embedding_model_revision: str
embedding_timeout_seconds: float
embedding_max_batch_size: int
embedding_max_text_chars: int
embedding_max_dimensions: int
embedding_max_response_bytes: int
embedding_max_retries: int
embedding_api_key: str | None  # 如当前任务不实现网络 adapter，可暂不新增
embedding_base_url: str | None # 如当前任务不实现网络 adapter，可暂不新增
```

注意：

- `repr(AppConfig)` 不得显示 key；
- capabilities 不能通过 `dataclasses.asdict()` 直接暴露 secret；
- provider/model 字段不能接受任意超长字符串，至少有长度和控制字符边界；
- model revision 缺失统一规范化为稳定字符串；
- fake embedding 是否由 `STUDYBUDDY_EMBEDDING_PROVIDER=fake` 显式启用必须冻结并测试；
- 不要因为 LLM provider 是 fake 就无条件启用 embedding fake，除非明确写入正式 contract。推荐 embedding 单独显式配置；若为了现有离线 indexing 流程保留兼容 fallback，必须记录为兼容行为并防止 capabilities 误报。

---

## 8. API capabilities 安全扩展

扩展现有：

```text
GET /api/ai/capabilities
```

推荐响应结构：

```json
{
  "llm": {
    "status": "demo",
    "provider_id": "fake",
    "model_id": "fake-studybuddy-v1",
    "supports": {"qa": true}
  },
  "embedding": {
    "status": "demo",
    "configured": true,
    "runtime_kind": "deterministic_demo",
    "verification_status": "not_applicable",
    "network_required": false,
    "provider_id": "fake",
    "model_id": "fake-embedding-v1",
    "model_revision": "1",
    "dimensions": 32,
    "encoding": "f32le_v1",
    "limits": {
      "max_batch_size": 32,
      "max_text_chars": 12000,
      "max_dimensions": 4096,
      "max_response_bytes": 0
    },
    "supports": {"embeddings": true, "batch": true}
  }
}
```

如果为了兼容现有 API 暂时保留旧顶层字段，必须同时保持旧测试和旧客户端兼容。

安全断言必须覆盖：

- response 不含 API key；
- response 不含 Authorization；
- response 不含完整敏感 URL 或 query token；
- response 不含 data root、database path、原始异常、traceback、SQL、chunk 正文或 vector payload；
- 未配置 embedding 不影响材料管理和 lexical-only retrieval；
- capability endpoint 不执行网络 health probe。

---

## 9. 错误映射与 retry boundary

统一使用稳定、脱敏的 embedding 错误码。至少覆盖：

```text
embedding_provider_not_configured
embedding_provider_invalid_config
embedding_provider_unavailable
embedding_provider_timeout
embedding_provider_rate_limited
embedding_provider_auth_failed
embedding_provider_forbidden
embedding_provider_protocol_error
embedding_provider_malformed_response
embedding_provider_schema_mismatch
embedding_invalid_request
embedding_batch_too_large
embedding_text_too_long
embedding_invalid_response
embedding_dimension_mismatch
embedding_response_too_large
embedding_invalid_vector
embedding_payload_length_mismatch
```

retry 规则：

- 默认 `max_retries = 0`；
- 只有 timeout、连接失败、明确 429/暂时不可用可按配置有限 retry；
- auth、forbidden、invalid request、malformed response、schema mismatch、dimension mismatch 不 retry；
- 每次 retry 必须有明确次数上限；
- 不记录 raw provider body；
- 最终只向调用方返回稳定错误码；
- 错误消息不包含 key、URL、请求正文、响应正文、路径或 traceback。

---

## 10. 测试交付清单

至少新增或补充以下测试：

### Protocol / fake

- fake provider 同输入同配置跨重复调用结果一致；
- 新 Python 进程中结果一致；
- whitespace normalization 一致；
- model/model revision/dimensions/algorithm version identity 变化不会静默复用；
- 不使用 Python 内置 hash 的回归约束；
- fake 无网络调用。

### Batch / boundary

- batch size 0、1、最大值、超过最大值；
- 空文本、全 whitespace；
- 非字符串输入；
- 文本长度边界；
- dimensions 边界；
- provider 返回数量不足/过多；
- vector 长度错误；
- NaN、Infinity、非数字；
- 空向量/zero vector；
- malformed response；
- response bytes 超限。

### Config

- 未配置；
- fake 配置；
- 缺 model；
- 缺 provider；
- 非法 timeout；
- 非法 batch/text/dimension/response/retry；
- bool 冒充 int；
- 超长或控制字符 provider/model/revision；
- `repr(AppConfig)` 和 API capability 不泄露 secret。

### Registry / capabilities

- no-config capability；
- fake/demo capability；
- invalid-config capability；
- 不执行 network probe；
- embedding capability 与 LLM capability 分离；
- 旧 `/api/ai/capabilities` 客户端/测试兼容。

### Provider failure / retry

如果 Phase 7.2 实现 generic HTTP adapter，使用 mock HTTP，不访问真实 provider：

- timeout；
- connection failure；
- 429；
- 401/403；
- 5xx；
- malformed JSON；
- schema mismatch；
- oversized response；
- retry 次数和不可 retry 错误矩阵。

### Regression

至少运行：

```text
D:\miniconda\py310\python.exe -m pytest backend/tests/test_ai_provider.py backend/tests/test_embedding.py backend/tests/test_retrieval.py backend/tests/test_ai_indexing.py
D:\miniconda\py310\python.exe -m pytest backend/tests/
```

如 `/api/ai/capabilities` 或 UI provider status 有用户可见变化，再运行对应 Chromium focused E2E；没有 E2E 证据不能宣称 browser-tested。

---

## 11. 文档收口

实现后同步：

- `docs/PHASE_ROADMAP.md`；
- `docs/STATUS.md`；
- `docs/TODO.md`；
- `docs/PROJECT_PROGRESS_REPORT.md`；
- 必要时更新 `docs/ai-learning-architecture.md`；
- 如新增正式环境变量，更新 `.env.example` 和相关配置说明。

文档必须明确：

- Phase 7.2 是 implemented/backend-tested 还是 partial；
- fake provider 是 deterministic demo，不等于真实 provider verified；
- 真实网络 provider 是否实现、是否验收；
- 未配置 embedding 时 lexical-only 的兼容行为；
- 未完成的 hybrid/fallback/Q&A integration 不能被提前宣称。

---

## 12. 完成判断

只有满足以下条件，Phase 7.2 才能标记 `implemented / backend-tested`：

1. protocol、registry、capability descriptor 已有真实调用路径；
2. fake provider 算法确定、版本化、跨进程稳定；
3. batch/text/dimensions/output limits 已实现并测试；
4. embedding 专用配置已实现，旧未配置运行不回归；
5. `/api/ai/capabilities` 返回 embedding 安全元数据且不泄露 secret；
6. 错误码和 retry boundary 有 focused tests；
7. 完整 backend suite 通过；
8. 文档与实际状态一致。

如果只完成 fake provider 和局部配置，必须标记 `partial`；如果没有真实调用路径或测试证据，不得标记 implemented。

Phase 7.2 完成不等于 Phase 7 完成。Phase 7 仍需 7.3–7.7 的 stale semantics、index verify/rebuild、vector/hybrid/fallback、Q&A/citation 接入、backup/restore 专项证据和最终验收。

---

## 13. 最终报告格式

完成后按以下结构报告：

1. 实现摘要；
2. 修改文件；
3. Protocol、registry、fake algorithm；
4. 配置项和边界；
5. capability API 响应和安全检查；
6. 错误映射和 retry 规则；
7. focused/full backend/Chromium 测试结果；
8. 未验证限制；
9. Phase 7.2 判断：`implemented` / `partial` / `blocked`；
10. Phase 7 后续剩余任务。
