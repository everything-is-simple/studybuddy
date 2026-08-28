# A2.4：收缩 `backend/app/providers.py`——提供商模块拆分

> 这是 A2.X 的最后一个任务。A2.X 总任务见 [`A2_X_BOUNDDED_CORE_SPLIT_PROMPT.md`](A2_X_BOUNDDED_CORE_SPLIT_PROMPT.md)，任务编号和路线位置见 [`../../ROADMAP_CAPABILITIES.md`](../../ROADMAP_CAPABILITIES.md)。

## 1. 执行位置、阶段与目标

请在 `H:\studybuddy` 执行任务 **A2.4**。

当前路线位置：

```text
A0 已完成
→ A1 已完成：repository.py 兼容 façade 与域出口
→ A2 已完成：main.py 后端应用结构拆分
→ A2.1 已完成：收缩 repositories/_legacy.py (379KB → 30KB)
→ A2.2 已完成：收缩 main.py (157KB → 969 bytes)
→ A2.3 已完成：收缩 migrations/runner.py (68KB → 7.4KB)
→ A2.4 当前任务：收缩 providers.py
→ A3：正式静态前端与多页原生应用壳
```

当前分支和基线：

- 正式仓库：`H:\studybuddy`
- 当前分支：`master`
- 当前 HEAD：`ec3dcd3` (refactor: split migrations/runner.py into versioned modules (A2.3))
- 远端：`origin/master` 已同步
- 当前正式 schema：**v13**

本任务只处理一个生产文件及其拆分产物：

```text
backend/app/providers.py
```

当前大小：

```text
33,593 bytes (650 lines)
```

最终目标：

- `providers.py` <= 32 KiB（32,768 bytes）
- 保持所有公共 API、协议、类型定义和提供商实现不变
- 所有新增或实质重写源码文件不超过 32 KiB，目标 20–30 KiB

## 2. 已完成结构与当前事实

A2.4 已验证的基线：

- 完整 backend：`413 passed, 2 skipped`
- Schema version：v13
- `INDEX_HTML` SHA-256：`1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c`

## 3. 必须保护的不变量

### 3.1 Public API 和导入

必须保持：

- `from app.providers import ProviderError, ProviderRequest, ProviderResult`
- `from app.providers import LLMProvider, FakeLLMProvider, OpenAICompatibleLLMProvider`
- `from app.providers import CaptureTranscriptionRequest, CaptureTranscriptionResult`
- `from app.providers import CaptureProviderError, CaptureTranscriptionProvider`
- `from app.providers import DeterministicFakeCaptureProvider, LoopbackCaptureProvider`
- `from app.providers import EmbeddingProviderRegistry, ProviderRegistry`
- `from app.providers import provider_registry`
- `from app.providers import PROVIDER_NOT_CONFIGURED, FAKE_PROVIDER_ID, FAKE_MODEL_ID`
- `from app.providers import MAX_PROVIDER_PROMPT_CHARS, MAX_PROVIDER_RESPONSE_BYTES`

所有现有导入路径必须保持可用。

### 3.2 协议和类型定义

不得：

- 修改 `LLMProvider` 或 `CaptureTranscriptionProvider` 协议签名
- 修改 `ProviderRequest`, `ProviderResult`, `CaptureTranscriptionRequest`, `CaptureTranscriptionResult` dataclass 字段
- 修改 `ProviderError`, `CaptureProviderError` 异常定义
- 修改 `ProviderRegistry` 或 `EmbeddingProviderRegistry` 的公共方法

### 3.3 提供商行为

不得：

- 修改 OpenAI 兼容提供商的 HTTP 请求格式、端点、headers 或错误处理
- 修改 Fake provider 的响应格式或行为
- 修改 embedding provider 的请求/响应格式
- 修改 provider registry 的查找逻辑、缓存行为或错误码

## 4. 当前 `providers.py` 结构分析

### 4.1 文件组成

```text
33,593 bytes, 650 lines

主要部分：
1. Imports (lines 1-16): ~500 bytes
2. SSL setup (lines 18-41): ~1,000 bytes
3. Constants (lines 43-48): ~200 bytes
4. Core types (lines 50-80): ~1,200 bytes
   - ProviderError, ProviderRequest, ProviderResult
   - LLMProvider protocol
5. Capture types (lines 82-119): ~1,500 bytes
   - CaptureTranscriptionRequest, CaptureTranscriptionResult
   - CaptureProviderError, CaptureTranscriptionProvider protocol
   - DeterministicFakeCaptureProvider, LoopbackCaptureProvider
6. Fake LLM Provider (lines 151-228): ~4,000 bytes
7. OpenAI-compatible LLM (lines 235-304): ~3,500 bytes
8. Helper functions (lines 230-232, 306-415): ~4,000 bytes
9. OpenAI-compatible Embedding (lines 418-501): ~4,000 bytes
10. Registries (lines 503-648): ~7,000 bytes
    - EmbeddingProviderRegistry: ~3,000 bytes
    - ProviderRegistry: ~4,000 bytes
11. Factory (lines 649-650): ~100 bytes
```

### 4.2 类和协议分布

| Class/Protocol | Lines | Size | Description |
|----------------|-------|------|-------------|
| ProviderError | 50-55 | ~150 B | Exception |
| ProviderRequest | 57-67 | ~500 B | Dataclass |
| ProviderResult | 69-80 | ~600 B | Dataclass |
| LLMProvider | 82-89 | ~400 B | Protocol |
| Capture types | 91-119 | ~1,500 B | Request/Result/Error/Protocol |
| DeterministicFakeCaptureProvider | 120-138 | ~800 B | Fake capture impl |
| LoopbackCaptureProvider | 140-149 | ~400 B | Loopback capture |
| FakeLLMProvider | 151-228 | ~4,000 B | Fake LLM impl |
| OpenAICompatibleLLMProvider | 235-304 | ~3,500 B | OpenAI LLM adapter |
| OpenAICompatibleEmbeddingProvider | 418-472 | ~2,500 B | OpenAI embedding adapter |
| EmbeddingProviderRegistry | 503-559 | ~3,000 B | Embedding registry |
| ProviderRegistry | 561-647 | ~4,500 B | Main provider registry |

### 4.3 大小超限原因

文件刚好超出 32 KiB 限制（33,593 bytes = 32 KiB + 825 bytes）。

超限因素：
1. **单文件包含所有提供商**: FakeLLMProvider, OpenAI LLM, OpenAI Embedding 都在一个文件
2. **Registry 实现**: 两个 registry 类共 ~7,500 bytes
3. **Helper 函数**: 分散在文件中的多个辅助函数
4. **SSL setup**: Windows 证书兜底逻辑占 ~1,000 bytes

## 5. A2.4 工作方式：按职责拆分提供商模块

### 5.1 推荐结构

```text
backend/app/providers/
  __init__.py                          # 公共 API 导出（原 providers.py 的导出）
  _core.py                             # 核心类型、协议、常量
  _ssl.py                              # SSL context setup
  _helpers.py                          # 共享 helper 函数
  _fake.py                             # FakeLLMProvider
  _capture.py                          # Capture providers (Deterministic, Loopback)
  _openai_llm.py                       # OpenAICompatibleLLMProvider
  _openai_embedding.py                 # OpenAICompatibleEmbeddingProvider
  _registry.py                         # EmbeddingProviderRegistry, ProviderRegistry, factory
```

或者更简单的两文件方案（如果上述拆分不够）：

```text
backend/app/providers.py              # <= 32 KiB: 核心 + registry + factory
backend/app/providers_impl.py         # 提供商实现 (Fake, OpenAI adapters)
```

**推荐：目录方案**，因为：
1. 清晰的职责分离
2. 更容易添加新提供商
3. 每个文件保持在 20 KiB 以内
4. 向后兼容：`from app.providers import X` 仍然可用

### 5.2 实施步骤（目录方案）

1. **创建 `backend/app/providers/` 目录**

2. **创建 `_core.py`**：
   - 移动 constants: `PROVIDER_NOT_CONFIGURED`, `FAKE_PROVIDER_ID`, etc.
   - 移动 core types: `ProviderError`, `ProviderRequest`, `ProviderResult`
   - 移动 protocols: `LLMProvider`
   - 移动 capture types: `CaptureTranscriptionRequest`, etc.
   - 预计大小: ~3,000 bytes

3. **创建 `_ssl.py`**：
   - 移动 `_ensure_ssl_context()` 及其调用
   - 预计大小: ~1,000 bytes

4. **创建 `_helpers.py`**：
   - 移动 `_snippet()`, `_prompt_content()`, `_request_json()`, `_parse_openai_response()`
   - 移动 `_optional_int()`, `_safe_request_id()`, `_extract_citation_keys()`
   - 移动 `_request_json_with_limit()`
   - 预计大小: ~4,000 bytes

5. **创建 `_fake.py`**：
   - 移动 `FakeLLMProvider`
   - 预计大小: ~4,000 bytes

6. **创建 `_capture.py`**：
   - 移动 `DeterministicFakeCaptureProvider`, `LoopbackCaptureProvider`
   - 预计大小: ~1,500 bytes

7. **创建 `_openai_llm.py`**：
   - 移动 `OpenAICompatibleLLMProvider`
   - Import helpers from `_helpers`
   - 预计大小: ~3,500 bytes

8. **创建 `_openai_embedding.py`**：
   - 移动 `OpenAICompatibleEmbeddingProvider`
   - Import helpers from `_helpers`
   - 预计大小: ~2,500 bytes

9. **创建 `_registry.py`**：
   - 移动 `EmbeddingProviderRegistry`, `ProviderRegistry`
   - 移动 `provider_registry()` factory
   - Import providers from other modules
   - 预计大小: ~7,500 bytes

10. **创建 `__init__.py`**：
    - 从各模块导入所有公共 API
    - 保持原 `providers.py` 的所有导出
    - 预计大小: ~1,000 bytes
    
    ```python
    from ._core import (
        PROVIDER_NOT_CONFIGURED,
        FAKE_PROVIDER_ID,
        FAKE_MODEL_ID,
        MAX_PROVIDER_PROMPT_CHARS,
        MAX_PROVIDER_RESPONSE_BYTES,
        ProviderError,
        ProviderRequest,
        ProviderResult,
        LLMProvider,
        CaptureTranscriptionRequest,
        CaptureTranscriptionResult,
        CaptureProviderError,
        CaptureTranscriptionProvider,
    )
    from ._fake import FakeLLMProvider
    from ._capture import DeterministicFakeCaptureProvider, LoopbackCaptureProvider
    from ._openai_llm import OpenAICompatibleLLMProvider
    from ._openai_embedding import OpenAICompatibleEmbeddingProvider
    from ._registry import (
        EmbeddingProviderRegistry,
        ProviderRegistry,
        provider_registry,
    )
    
    __all__ = [
        "PROVIDER_NOT_CONFIGURED",
        "FAKE_PROVIDER_ID",
        "FAKE_MODEL_ID",
        "MAX_PROVIDER_PROMPT_CHARS",
        "MAX_PROVIDER_RESPONSE_BYTES",
        "ProviderError",
        "ProviderRequest",
        "ProviderResult",
        "LLMProvider",
        "CaptureTranscriptionRequest",
        "CaptureTranscriptionResult",
        "CaptureProviderError",
        "CaptureTranscriptionProvider",
        "FakeLLMProvider",
        "DeterministicFakeCaptureProvider",
        "LoopbackCaptureProvider",
        "OpenAICompatibleLLMProvider",
        "OpenAICompatibleEmbeddingProvider",
        "EmbeddingProviderRegistry",
        "ProviderRegistry",
        "provider_registry",
    ]
    ```

11. **删除原 `providers.py`** 或将其重命名为备份

12. **验证**：
    - Compile check: `python -m compileall -q backend/app`
    - Import smoke: `from app.providers import ProviderRegistry, FakeLLMProvider, provider_registry`
    - Source size: `python backend/scripts/check-source-size.py --main-html-sha256 1e111288...`
    - Full backend: `python -m pytest backend/tests/ -q`

### 5.3 替代方案：简单两文件拆分

如果目录方案过于复杂，可以采用简单拆分：

1. **保留 `providers.py`**：
   - 保留所有类型、协议、常量
   - 保留 registries
   - 保留 factory
   - 从 `providers_impl` 导入实现类
   - 目标大小: ~20 KiB

2. **创建 `providers_impl.py`**：
   - 所有提供商实现：Fake, OpenAI LLM, OpenAI Embedding, Capture providers
   - 所有 helper 函数
   - SSL setup
   - 目标大小: ~15 KiB

3. **更新 `providers.py`**：
   ```python
   from .providers_impl import (
       FakeLLMProvider,
       DeterministicFakeCaptureProvider,
       LoopbackCaptureProvider,
       OpenAICompatibleLLMProvider,
       OpenAICompatibleEmbeddingProvider,
   )
   ```

这个方案更简单，但不如目录方案清晰。

## 6. 禁止事项

- 不修改任何公共 API 签名或协议定义
- 不修改提供商的请求/响应格式
- 不修改错误码或异常行为
- 不修改 registry 的查找逻辑或缓存
- 不修改 embedding 提供商的向量处理
- 不新增提供商实现（A2.4 只是重构）
- 不修改 fake provider 的行为（测试依赖它）

## 7. 测试和验收

### 7.1 每个变更后

```powershell
python -m compileall -q backend/app
PYTHONPATH=backend python -c "from app.providers import ProviderRegistry, FakeLLMProvider, provider_registry; print('OK')"
python backend/scripts/check-source-size.py --main-html-sha256 1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c
git diff --check
```

### 7.2 Provider Tests

```powershell
python -m pytest backend/tests/ -k provider -xvs
```

必须通过所有 provider 相关测试。

### 7.3 最终 A2.4 门禁

必须验证：

1. `providers.py` <= 32 KiB（如果是目录方案，则所有 `providers/*.py` 文件 <= 32 KiB）
2. 所有公共 API 可从 `app.providers` 导入
3. `python -m compileall -q backend/app` 通过
4. Schema version 仍为 v13
5. `INDEX_HTML` SHA-256 仍为 `1e111288...`
6. 完整 backend regression 不低于当前基线：

```powershell
python -m pytest backend/tests/ -q
```

目标：`413 passed, 2 skipped`；若测试数量变化，必须解释变化。

7. Provider-specific tests：

```powershell
python -m pytest backend/tests/ -k provider -q
```

必须全部通过。

## 8. 文档、提交和回退

### 8.1 文档

完成后更新：

- `docs/prompts/architecture/A2_4_PROVIDERS_SPLIT_EVIDENCE.md`
- `docs/ROADMAP_CAPABILITIES.md` 中 A2.4 状态

文档必须明确：

- 最终 `providers.py` 大小和结构（或目录方案的模块列表）
- 公共 API 兼容性验证
- Compile、import、provider、backend 测试命令和结果
- 未验证边界

### 8.2 提交

推荐提交信息：

```text
refactor: split providers.py into module directory (A2.4)
```

或（如果是两文件方案）：

```text
refactor: split provider implementations from providers.py (A2.4)
```

提交必须可回退、可解释、通过所有必须门禁。

### 8.3 回退

失败时：

- 只回退当前代码提交
- 不删除 data root、数据库、原件或 verified backup
- 保留脱敏测试结果和 failure evidence
- 先恢复上一个可运行提交，再分析问题

## 9. 完成报告格式

最终报告必须包含：

1. A2.4 的实际实施方式（目录方案或两文件方案）
2. `providers.py` 的初始/最终大小与最终结构
3. 新增模块列表及各自大小（如果是目录方案）
4. 公共 API 兼容性验证
5. Compile、import smoke、源码大小检查结果
6. Schema/INDEX_HTML 验证结果
7. Backend/provider 测试的实际命令与结果
8. Skip 项、未验证边界和残余风险
9. Commit hash、推送分支和最终 `git status`

只有在所有门禁真实通过后，才可以将 A2.4 标记为完成。**A2.4 完成意味着 A2.X 全部完成**，所有超过 32 KiB 的生产源码文件已被收缩或拆分。
