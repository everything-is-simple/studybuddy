# P1-5-0 契约冻结证据

> 状态：`contract-frozen / 2026-01-09`
> 
> 本文档记录 P1-5-0（Provider + Email 配置安全契约冻结）的审计发现、治理测试和契约冻结范围。

## 1. 审计范围与方法

### 1.1 审计目标

冻结 Provider（AI LLM / Embedding）和 Email（SMTP / Feishu）配置的安全边界，明确：
- Secret 字段分类与生命周期
- Runtime-only source 原则
- 脱敏规则与验证
- Connection-test 触发机制
- Backup/restore 边界
- 当前前端只读状态

**P1-5-0 明确不修改**：
- `backend/app/` 生产代码
- Schema、migration、API endpoint
- 前端配置保存功能
- Secret 持久化路径

### 1.2 审计文件清单

**配置与 Provider 核心**：
- `backend/app/config.py`（17 KB）
- `backend/app/providers/_registry.py`
- `backend/app/providers/_core.py`
- `backend/app/providers/_fake.py`
- `backend/app/providers/_openai_llm.py`
- `backend/app/providers/_openai_embedding.py`

**Delivery 与 Backup**：
- `backend/app/delivery.py`（15 KB）
- `backend/app/backup.py`（23 KB）
- `backend/app/diagnostics.py`（3 KB）
- `backend/app/observability.py`（6 KB）

**API 与前端**：
- `backend/app/api/system.py`（capabilities endpoint）
- `backend/app/api/study_capture_reports.py`（delivery endpoints）
- `backend/app/static/settings.html`
- `backend/app/static/settings-provider.html`
- `backend/app/static/js/api.js`

**文档与测试**：
- `docs/contracts/B4_DELIVERY_COMPONENT_CONTRACT.md`
- `docs/BACKUP_RESTORE.md`
- `docs/operations/AI_PROVIDER_SETUP.md`
- `.env.example`
- `backend/tests/test_b4_delivery_c4_config.py`

## 2. 关键审计发现

### 2.1 Secret 字段与 `repr=False` 实施

**`backend/app/config.py:53-107`**：
```python
ai_api_key: str | None = field(default=None, repr=False)
embedding_api_key: str | None = field(default=None, repr=False)
report_delivery_smtp_password: str | None = field(default=None, repr=False)
report_delivery_smtp_password_runtime: str | None = field(default=None, repr=False)
report_delivery_feishu_webhook: str | None = field(default=None, repr=False)
```

**发现**：
- 5 个敏感字段标记 `repr=False`
- `report_delivery_smtp_password` 和 `report_delivery_smtp_password_runtime` 存在**双字段冗余**（历史遗留）
- 两字段当前同源（均从 `STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD` 读取）

### 2.2 配置来源：Runtime-only 环境变量

**`backend/app/config.py:268-333`**：
- `os.environ.get("STUDYBUDDY_AI_PROVIDER")`
- `os.environ.get("STUDYBUDDY_AI_API_KEY")`
- `os.environ.get("STUDYBUDDY_EMBEDDING_API_KEY")`
- `os.environ.get("STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD")`
- `_env_delivery_feishu_webhook()`

**确认**：
- 所有配置仅从进程环境变量读取
- 无 SQLite 读取、无 `data_root/` 文件读取
- 无运行时热重载或动态修改

### 2.3 Provider 状态契约

**`backend/app/providers/_registry.py:95-117`**：
```python
def capabilities(self) -> dict[str, object]:
    try:
        provider = self.configured_provider()
    except ProviderError as error:
        return {
            "status": "not_configured" if error.code == PROVIDER_NOT_CONFIGURED else "invalid_config",
            "configured": False,
            "verification_status": "not_applicable",
            "runtime_kind": "none",
            "config_source": "process_environment",
            "provider_id": None,
            "model_id": None,
            "supports": {"qa": False},
            "error_code": error.code,
        }
```

**确认**：
- 返回 `status`、`configured`、`verification_status`、`provider_id`、`model_id`
- **不返回**：`api_key`、`base_url`（完整 URL）、`Authorization` header

### 2.4 Delivery 默认值与安全边界

**`backend/app/config.py:18-23`**：
```python
DEFAULT_REPORT_DELIVERY_MODE = "off"
# ...
ENABLED = False
AUTHORIZED = False
```

**`backend/app/delivery.py:22-30`**：
```python
DELIVERY_CHANNELS = {"smtp", "feishu"}
DELIVERY_MODES = {"off", "dry_run", "live"}
MAX_DELIVERY_CONTENT_BYTES = 1 << 20  # 1 MiB
```

**确认**：
- 默认 `mode=off`、`enabled=false`、`authorized=false`
- `DryRunDeliveryAdapter` 不开启网络连接
- B4 契约边界完整继承

### 2.5 Backup Manifest 不含 Secret

**`backend/app/backup.py:manifest_metadata()`**：
- Manifest 包含：`schema_version`、`current_schema_at_backup`、backup 元数据
- Manifest **不包含**：`api_key`、`password`、`webhook`、完整邮箱地址

**`docs/BACKUP_RESTORE.md`**：
- 明确声明 backup 不包含 runtime credentials
- Restore 后需操作员重新配置环境变量

### 2.6 前端只读状态

**`backend/app/static/settings-provider.html`**：
```html
<div class="notice notice-info">
  <p>Provider 配置写入契约尚未完成批准。当前页面仅展示运行时状态。</p>
</div>
```

**`backend/app/static/js/api.js`**：
- 无 `saveProviderConfig()` 或 `saveEmailConfig()` 函数
- 无发送 secret 的 POST/PATCH 请求

### 2.7 已知代码问题（不影响契约冻结）

**`backend/app/diagnostics.py:81-88`**：
```python
except DiagnosticError as error:
    # ...
except DiagnosticError:  # 不可达代码
    return False
```

**问题**：重复的 `except DiagnosticError` 分支，第二个分支不可达。

**影响**：不影响 P1-5-0 契约冻结，但应在后续代码清理中修复。

## 3. 治理测试覆盖

### 3.1 测试文件

**`backend/tests/test_p1_5_0_governance.py`**（新增）：
- `test_p1_5_0_contract_document_exists_and_declares_frozen()`
- `test_p1_5_0_secret_fields_have_repr_false()`
- `test_p1_5_0_config_source_is_runtime_environment_only()`
- `test_p1_5_0_capabilities_api_does_not_expose_secrets()`
- `test_p1_5_0_backup_manifest_excludes_credentials()`
- `test_p1_5_0_frontend_remains_readonly()`
- `test_p1_5_0_delivery_defaults_remain_closed()`
- `test_p1_5_0_no_production_code_modified()`

### 3.2 现有测试复用

**`backend/tests/test_b4_delivery_c4_config.py`**：
- `test_delivery_runtime_mapping_is_parsed_without_exposing_secrets()`：验证 `repr(config)` 不含 secret
- `test_delivery_runtime_mapping_defaults_remain_closed()`：验证默认值 `off` / `false`

## 4. 环境变量命名确认

### 4.1 Provider 环境变量

**AI LLM**：
- `STUDYBUDDY_AI_PROVIDER`
- `STUDYBUDDY_AI_MODEL`
- `STUDYBUDDY_AI_BASE_URL`
- `STUDYBUDDY_AI_API_KEY`
- `STUDYBUDDY_AI_TIMEOUT_SECONDS`
- `STUDYBUDDY_AI_MAX_OUTPUT_TOKENS`
- `STUDYBUDDY_AI_MAX_PROMPT_CHARS`
- `STUDYBUDDY_AI_MAX_ANSWER_CHARS`
- `STUDYBUDDY_AI_MAX_RETRIES`

**Embedding**：
- `STUDYBUDDY_EMBEDDING_PROVIDER`
- `STUDYBUDDY_EMBEDDING_MODEL`
- `STUDYBUDDY_EMBEDDING_BASE_URL`
- `STUDYBUDDY_EMBEDDING_API_KEY`

### 4.2 Email 环境变量

**SMTP**：
- `STUDYBUDDY_REPORT_DELIVERY_SMTP_HOST`
- `STUDYBUDDY_REPORT_DELIVERY_SMTP_PORT`
- `STUDYBUDDY_REPORT_DELIVERY_SMTP_SECURE`
- `STUDYBUDDY_REPORT_DELIVERY_SMTP_USERNAME`
- `STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD`
- `STUDYBUDDY_REPORT_DELIVERY_SMTP_TARGETS`

**Feishu**：
- `STUDYBUDDY_REPORT_DELIVERY_FEISHU_TARGET_LABEL`
- `STUDYBUDDY_REPORT_DELIVERY_FEISHU_WEBHOOK`

**Delivery 控制**：
- `STUDYBUDDY_REPORT_DELIVERY_MODE`
- `STUDYBUDDY_REPORT_DELIVERY_ENABLED`
- `STUDYBUDDY_REPORT_DELIVERY_AUTHORIZED`

**来源**：`.env.example`、`backend/app/config.py`、`docs/operations/AI_PROVIDER_SETUP.md`

## 5. 稳定错误码清单

### 5.1 Provider 错误码

**`backend/app/providers/_core.py`**：
- `provider_not_configured`：未配置任何 Provider
- `provider_invalid_config`：部分配置或参数冲突

**预留（契约冻结，未实现）**：
- `provider_connection_failed`：网络连接失败
- `provider_timeout`：请求超时
- `provider_unavailable`：服务不可用（HTTP 5xx）
- `provider_protocol_error`：协议错误或响应解析失败
- `provider_response_too_large`：响应体超出限制
- `provider_test_not_authorized`：测试未授权

### 5.2 Embedding 错误码

**`backend/app/embedding.py`**：
- `embedding_provider_not_configured`
- `embedding_provider_invalid_config`
- `embedding_invalid_dimensions`

### 5.3 Delivery 错误码

**`backend/app/delivery.py`**：
- `delivery_disabled`
- `delivery_target_not_allowed`
- `delivery_authorization_required`
- `delivery_configuration_invalid`
- `delivery_timeout`
- `delivery_failed`

## 6. Schema 与 Migration 确认

**当前 schema 版本**：v14（`backend/app/migrations/runner.py:34`）

**P1-5-0 确认**：
- 无新增表、列、索引
- 无新增 migration 文件
- 无修改现有 migration

**后续切片注意**：
- 如果 P1-5-1+ 需持久化配置元数据（非 secret），需新增 migration
- Secret 字段**永不进入 schema**

## 7. 契约冻结范围总结

### 7.1 已冻结

✅ Secret 字段分类（5 个 `repr=False` 字段）
✅ Runtime-only 环境变量来源
✅ Provider 状态枚举（`not_configured` / `invalid_config` / `demo` / `configured`）
✅ Capabilities API 响应格式（不含 secret）
✅ Delivery 默认值（`off` / `false` / `false`）
✅ Backup manifest 排除 credentials
✅ 前端只读边界
✅ 稳定错误码清单
✅ Connection-test 触发机制（显式、不自动、不改状态）
✅ Preset 契约（非敏感元数据、无实时价格）

### 7.2 明确未实现（后续切片）

❌ 配置写入 API（P1-5-1）
❌ Connection-test 实现（P1-5-2）
❌ 配置持久化评估（P1-5-3）
❌ 浏览器证据（P1-5-4）
❌ Secret 泄漏扫描（P1-5-5）

### 7.3 明确非目标（v1 范围外）

❌ 配置热重载
❌ 多 Provider failover
❌ KMS 集成
❌ 配置版本管理
❌ HTML 邮件或附件
❌ 邮件发送队列

## 8. 验收标准

### 8.1 契约文档

- [x] `docs/contracts/P1_5_PROVIDER_EMAIL_CONFIGURATION_CONTRACT.md` 已创建
- [x] 覆盖 8 个主要章节：Provider 边界、Email 边界、Preset、自由配置、Secret source、Connection-test、Backup/restore、非目标
- [x] 明确 P1-5-0 不修改生产代码

### 8.2 治理测试

- [x] `backend/tests/test_p1_5_0_governance.py` 已创建
- [x] 8 个治理测试覆盖关键契约点
- [x] 复用现有 `test_b4_delivery_c4_config.py` 验证 delivery 边界

### 8.3 文档更新

- [x] `docs/STATUS.md` 新增 P1-5-0 条目
- [x] `docs/TODO.md` 勾选 P1-5-0
- [x] `docs/INDEX.md` 新增 P1-5 契约索引

### 8.4 验收命令

```powershell
# 治理测试
C:\miniconda\py310\python.exe -m pytest backend/tests/test_p1_5_0_governance.py -q

# 复用 delivery 配置测试
C:\miniconda\py310\python.exe -m pytest backend/tests/test_b4_delivery_c4_config.py -q

# 治理一致性
C:\miniconda\py310\python.exe -m pytest backend/tests/test_governance_consistency.py -q

# 源文件大小检查
C:\miniconda\py310\python.exe backend/scripts/check-source-size.py

# 前端契约审计
C:\miniconda\py310\python.exe backend/scripts/audit-frontend-contract.py --strict

# Git diff 检查
git diff --check
```

### 8.5 预期结果

- 治理测试：8 passed（test_p1_5_0_governance.py）
- Delivery 配置测试：3 passed（test_b4_delivery_c4_config.py）
- 治理一致性：通过
- 源文件大小：通过（契约文档豁免 32 KiB 限制）
- 前端审计：0 findings
- Git diff：无空白错误

## 9. 后续切片依赖

**P1-5-1（配置 UI 实现）**：
- 依赖 P1-5-0 契约批准
- 实现前端配置表单（不保存 secret）
- 实现配置验证 API

**P1-5-2（Connection-test 实现）**：
- 依赖 P1-5-0 契约批准
- 实现 `POST /api/system/provider-connection-test`
- 固定 synthetic payload

**P1-5-3（配置持久化评估）**：
- 依赖 P1-5-0 + P1-5-1 + P1-5-2
- 评估非敏感元数据持久化方案
- Secret 永不持久化

**P1-5-4（浏览器证据）**：
- 依赖 P1-5-1 + P1-5-2
- 验证配置 UI 不回显 secret
- 验证不保存到 localStorage

**P1-5-5（泄漏扫描）**：
- 依赖 P1-5-0 + P1-5-1 + P1-5-2 + P1-5-3 + P1-5-4
- 实现 sentinel secret 扫描
- 验证 DOM / URL / 日志 / backup 无泄漏

---

## 契约冻结声明

- **审计完成日期**：2026-01-09
- **契约文档版本**：`docs/contracts/P1_5_PROVIDER_EMAIL_CONFIGURATION_CONTRACT.md` (contract-frozen)
- **证据文档版本**：本文档 (contract-frozen)
- **生产代码修改**：无
- **Schema/Migration 修改**：无
- **API 修改**：无
- **后续切片状态**：等待 P1-5-0 批准
