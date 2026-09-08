# P1-5-2 Connection-Test 实现证据

> 状态：`implemented / 2026-01-09`
> 
> 本文档记录 P1-5-2 Connection-test 实现的范围、测试覆盖和验收结果。

## 1. 实施范围

**P1-5-2：Connection-test 实现**

实现了 Provider（AI LLM / Embedding）和 Email（SMTP / Feishu）配置的独立 connection-test 能力，使用固定 synthetic payload 验证配置的实际可用性。

**切片划分**：
- ✅ P1-5-2-0：Connection-test 核心逻辑（backend adapter）
- ✅ P1-5-2-1：Connection-test API endpoints
- ✅ P1-5-2-3：文档与证据（本文档）

---

## 2. 实现文件清单

### 2.1 核心实现

**`backend/app/connection_test.py`** (12.6 KB)
- `provider_llm_connection_test()`: LLM Provider 连接测试
- `provider_embedding_connection_test()`: Embedding Provider 连接测试
- `smtp_connection_test()`: SMTP 连接测试
- `feishu_connection_test()`: 飞书 Webhook 连接测试
- `ConnectionTestError`: 稳定错误码异常类
- 固定 synthetic payload 常量

**`backend/app/schemas/connection_test.py`** (1.7 KB)
- `ProviderConnectionTestRequest`: Provider 测试请求 schema
- `EmailConnectionTestRequest`: Email 测试请求 schema

**`backend/app/api/system.py`** (修改)
- `POST /api/system/provider-connection-test`: Provider 测试 endpoint
- `POST /api/system/email-connection-test`: Email 测试 endpoint

**`backend/app/app_factory.py`** (修改)
- 导入 connection_test 函数和 schemas

### 2.2 测试文件

**`backend/tests/test_p1_5_2_0_connection_test.py`** (11.3 KB)
- 16 个单元测试覆盖所有 adapter 和错误映射

**`backend/tests/test_p1_5_2_1_api.py`** (8.3 KB)
- 12 个 API 集成测试

---

## 3. 契约合规验证

### 3.1 P1-5-0 契约要求

**显式触发** ✅
- Connection-test 仅通过 POST API 请求触发
- 不在启动时自动执行
- 不在 `GET /api/ai/capabilities` 调用时自动执行

**固定 synthetic payload** ✅
- LLM: `{"model": "...", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 10}`
- Embedding: `{"model": "...", "input": ["test"]}`
- SMTP: 固定主题"StudyBuddy Configuration Test"，固定正文"No study material is included."
- Feishu: `{"msg_type": "text", "content": {"text": "Configuration test"}}`

**不改变配置状态** ✅
- 测试成功/失败不启用或禁用 Provider
- 测试不修改环境变量或配置文件
- 测试不持久化到 SQLite 或 data_root

**响应限制** ✅
- 响应体上限：1 KB (MAX_TEST_RESPONSE_BYTES = 1024)
- 超时默认：Provider 30s、Email 10s
- 不跟随 HTTP 重定向

**稳定错误码映射** ✅
- Provider: 9 个稳定错误码
- Email: 6 个稳定错误码
- 所有异常映射为预定义错误码

### 3.2 固定 Payload 验证

**测试验证**：
```python
def test_connection_test_uses_fixed_synthetic_payloads() -> None:
    assert LLM_TEST_PAYLOAD == {
        "model": "",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 10,
    }
    # ...
```

**Result**: ✅ Passed

### 3.3 边界限制验证

**响应大小限制**：
```python
def test_provider_llm_connection_test_response_too_large() -> None:
    mock_response.headers.get.return_value = str(MAX_TEST_RESPONSE_BYTES + 1)
    # ...
    assert exc.value.code == "provider_response_too_large"
```

**Result**: ✅ Passed

**超时验证**：
```python
def test_provider_llm_connection_test_timeout() -> None:
    with patch("app.connection_test.urlopen", side_effect=TimeoutError):
        # ...
        assert exc.value.code == "provider_timeout"
```

**Result**: ✅ Passed

### 3.4 Secret 不暴露验证

**API 测试**：
```python
def test_provider_connection_test_does_not_expose_secrets(client) -> None:
    response = client.post(
        "/api/system/provider-connection-test",
        json={"api_key": "SECRET_API_KEY_12345", ...},
    )
    assert "SECRET_API_KEY_12345" not in response.text
```

**Result**: ✅ Passed

---

## 4. API 规范

### 4.1 Provider Connection-Test

**Endpoint**: `POST /api/system/provider-connection-test`

**Request Body**:
```json
{
  "provider_type": "llm" | "embedding",
  "base_url": "https://api.example.com",
  "api_key": "your-api-key",
  "model_id": "model-name",
  "timeout_seconds": 30.0  // optional, default: 30.0
}
```

**Success Response (200)**:
```json
{"status": "ok"}
```

**Error Response (400)**:
```json
{"detail": "provider_timeout"}  // 或其他稳定错误码
```

**Error Response (500)**:
```json
{"detail": "connection_test_failed"}  // 意外错误
```

### 4.2 Email Connection-Test

**Endpoint**: `POST /api/system/email-connection-test`

**SMTP Request**:
```json
{
  "channel": "smtp",
  "smtp_host": "smtp.example.com",
  "smtp_port": 465,
  "smtp_secure": true,  // optional, default: true
  "smtp_username": "user@example.com",  // optional
  "smtp_password": "password",          // optional
  "smtp_sender": "sender@example.com",
  "smtp_recipient": "recipient@example.com",
  "timeout_seconds": 10.0  // optional, default: 10.0
}
```

**Feishu Request**:
```json
{
  "channel": "feishu",
  "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/token",
  "timeout_seconds": 10.0  // optional, default: 10.0
}
```

**Responses**: 同 Provider endpoint

---

## 5. 稳定错误码清单

### 5.1 Provider 错误码

**配置错误**：
- `invalid_provider_type`: 请求中 provider_type 不是 "llm" 或 "embedding"
- `provider_invalid_config`: 配置不完整（缺少 base_url、api_key 或 model_id）

**网络错误**：
- `provider_connection_failed`: 网络连接失败（DNS 解析失败、连接被拒绝等）
- `provider_timeout`: 请求超时

**HTTP 错误**：
- `provider_auth_failed`: HTTP 401（认证失败）
- `provider_forbidden`: HTTP 403（权限不足）
- `provider_rate_limited`: HTTP 429（请求过多）
- `provider_unavailable`: HTTP 5xx（服务不可用）

**响应错误**：
- `provider_protocol_error`: 非 JSON 响应、响应格式不符合预期、其他 HTTP 错误
- `provider_response_too_large`: 响应体超过 1 KB

### 5.2 Email 错误码

**配置错误**：
- `invalid_channel`: 请求中 channel 不是 "smtp" 或 "feishu"
- `delivery_configuration_invalid`: 配置不完整或格式错误

**网络错误**：
- `delivery_connection_failed`: 网络连接失败
- `delivery_timeout`: 请求超时

**认证/协议错误**：
- `delivery_auth_failed`: SMTP 认证失败
- `delivery_failed`: SMTP 协议错误或 Feishu 响应错误

**响应错误**：
- `delivery_response_too_large`: 响应体超过 1 KB

---

## 6. 测试覆盖

### 6.1 单元测试（P1-5-2-0）

**`backend/tests/test_p1_5_2_0_connection_test.py`**: 16 passed

| 测试 | 覆盖范围 |
|---|---|
| `test_connection_test_uses_fixed_synthetic_payloads` | 固定 payload 验证 |
| `test_provider_llm_connection_test_success` | LLM 成功路径 |
| `test_provider_llm_connection_test_invalid_config` | LLM 配置验证 |
| `test_provider_llm_connection_test_timeout` | LLM 超时映射 |
| `test_provider_llm_connection_test_http_errors` | LLM HTTP 错误映射（401/429/503） |
| `test_provider_llm_connection_test_response_too_large` | LLM 响应大小限制 |
| `test_provider_llm_connection_test_malformed_response` | LLM 非 JSON 响应 |
| `test_provider_embedding_connection_test_success` | Embedding 成功路径 |
| `test_smtp_connection_test_success` | SMTP 成功路径 |
| `test_smtp_connection_test_invalid_config` | SMTP 配置验证 |
| `test_smtp_connection_test_auth_failed` | SMTP 认证失败映射 |
| `test_smtp_connection_test_timeout` | SMTP 超时映射 |
| `test_feishu_connection_test_success` | Feishu 成功路径 |
| `test_feishu_connection_test_invalid_webhook` | Feishu webhook 验证 |
| `test_feishu_connection_test_failed_response` | Feishu 错误码映射 |
| `test_connection_test_error_has_stable_code` | 错误码稳定性 |

### 6.2 API 集成测试（P1-5-2-1）

**`backend/tests/test_p1_5_2_1_api.py`**: 12 passed

| 测试 | 覆盖范围 |
|---|---|
| `test_provider_connection_test_endpoint_llm_success` | Provider LLM API 成功 |
| `test_provider_connection_test_endpoint_embedding_success` | Provider Embedding API 成功 |
| `test_provider_connection_test_endpoint_invalid_type` | Provider 无效类型拒绝 |
| `test_provider_connection_test_endpoint_error_mapping` | Provider 错误码映射 |
| `test_email_connection_test_endpoint_smtp_success` | Email SMTP API 成功 |
| `test_email_connection_test_endpoint_feishu_success` | Email Feishu API 成功 |
| `test_email_connection_test_endpoint_invalid_channel` | Email 无效 channel 拒绝 |
| `test_email_connection_test_endpoint_smtp_missing_fields` | SMTP 不完整配置拒绝 |
| `test_email_connection_test_endpoint_feishu_missing_webhook` | Feishu 缺少 webhook 拒绝 |
| `test_email_connection_test_endpoint_error_mapping` | Email 错误码映射 |
| `test_provider_connection_test_does_not_expose_secrets` | Provider secret 不暴露 |
| `test_email_connection_test_does_not_expose_secrets` | Email secret 不暴露 |

### 6.3 治理测试（P1-5-0）

**`backend/tests/test_p1_5_0_governance.py`**: 9 passed

P1-5-0 契约治理测试继续通过，验证 P1-5-2 未破坏契约边界。

---

## 7. 验收结果

### 7.1 功能验收

```
✅ Provider LLM connection-test: 实现完成，测试通过
✅ Provider Embedding connection-test: 实现完成，测试通过
✅ SMTP connection-test: 实现完成，测试通过
✅ Feishu connection-test: 实现完成，测试通过
✅ API endpoints: 2 个 endpoint 实现完成，测试通过
✅ Request/Response schemas: 实现完成，验证通过
```

### 7.2 测试验收

```
✅ P1-5-2-0 单元测试:     16 passed
✅ P1-5-2-1 API 测试:     12 passed
✅ P1-5-0 治理测试:        9 passed
✅ Source size check:      passed
```

**总计**: 37 passed

### 7.3 契约验收

```
✅ 显式触发
✅ 固定 synthetic payload
✅ 不改变配置状态
✅ 响应限制（1 KB、超时）
✅ 稳定错误码映射
✅ Secret 不暴露
```

---

## 8. 未验证边界

### 8.1 真实网络测试

**当前状态**: 所有测试使用 mock，未进行真实网络请求

**未验证场景**：
- ❌ 真实 Provider API 连接（DeepSeek、Agnes 等）
- ❌ 真实 SMTP 服务器连接
- ❌ 真实飞书 Webhook 连接
- ❌ 网络分区、DNS 失败等边界情况

**验证方式**（可选，需显式 opt-in）：
- 设置环境变量 `STUDYBUDDY_RUN_CONNECTION_TEST_SMOKE=1`
- 配置真实 credentials
- 运行 `pytest backend/tests/test_p1_5_2_smoke.py`（未创建）

### 8.2 并发测试

**当前状态**: 测试为串行单次调用

**未验证场景**：
- ❌ 多个并发 connection-test 请求
- ❌ 同一 Provider 的并发测试
- ❌ 混合 Provider/Email 的并发测试

### 8.3 性能测试

**当前状态**: 测试未测量性能

**未验证指标**：
- ❌ Connection-test 响应时间
- ❌ 超时准确性
- ❌ 资源使用（内存、CPU）

---

## 9. 明确非目标

**P1-5-2 不包含**：
- ❌ 配置持久化（P1-5-3）
- ❌ 配置 UI（P1-5-1，前端实现）
- ❌ 自动定期健康检查
- ❌ Connection-test 历史记录
- ❌ 批量测试多个 Provider
- ❌ Connection-test 结果缓存
- ❌ 自动 Provider 选择或 failover

---

## 10. Commit 历史

- **P1-5-2-0**: `cae5cce` - feat: implement p1-5-2-0 connection-test adapters
- **P1-5-2-1**: `c7289aa` - feat: implement p1-5-2-1 connection-test api endpoints

---

## 11. 后续切片

**P1-5-3（配置持久化评估）**：
- 评估非敏感元数据持久化方案
- Secret 永不持久化
- 配置变更需重启进程

**P1-5-4（浏览器证据）**：
- 验证配置 UI 不回显 secret
- 验证不保存到 localStorage/sessionStorage

**P1-5-5（泄漏扫描）**：
- Sentinel secret 扫描
- DOM/URL/日志/backup 扫描

---

## 12. 证据声明

- **实施完成日期**: 2026-01-09
- **测试状态**: 28 passed (16 单元 + 12 API)
- **契约合规**: 完全符合 P1-5-0 契约
- **代码质量**: Source size check passed
- **未验证边界**: 真实网络测试、并发测试、性能测试
- **生产就绪**: ⚠️ 仅限 mock 测试范围，真实网络测试需显式 opt-in
