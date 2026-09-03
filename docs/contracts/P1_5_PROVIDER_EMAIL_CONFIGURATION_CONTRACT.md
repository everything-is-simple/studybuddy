# P1-5 Provider + Email 配置安全契约

> 状态：`contract-frozen / 2026-01-09`
> 
> 本契约冻结 Provider（AI LLM / Embedding）和 Email（SMTP / Feishu）配置的安全边界、secret 生命周期、runtime source、connection-test 行为和 backup/restore 规则。**P1-5-0 契约冻结切片不修改 `backend/app/` 生产代码、schema、migration 或 API；不新增配置写入 endpoint；不保存 secret 到 SQLite 或 data_root；不改变现有前端只读展示行为。**

## 1. Provider 配置边界（AI LLM / Embedding）

### 1.1 配置字段分类

**敏感字段（secret）**：
- `STUDYBUDDY_AI_API_KEY`：LLM Provider API 密钥
- `STUDYBUDDY_EMBEDDING_API_KEY`：Embedding Provider API 密钥

**非敏感元数据**：
- `STUDYBUDDY_AI_PROVIDER`：Provider 标识符（如 `deepseek`、`fake`）
- `STUDYBUDDY_AI_MODEL`：模型标识符（如 `deepseek-chat`）
- `STUDYBUDDY_AI_BASE_URL`：API 端点 URL（HTTPS 必须，loopback 除外）
- `STUDYBUDDY_AI_TIMEOUT_SECONDS`：请求超时（0.1–120.0s）
- `STUDYBUDDY_AI_MAX_OUTPUT_TOKENS`：输出 token 上限（1–8192）
- `STUDYBUDDY_AI_MAX_PROMPT_CHARS`：提示字符上限（100–200000）
- `STUDYBUDDY_AI_MAX_ANSWER_CHARS`：答案字符上限（100–100000）
- `STUDYBUDDY_AI_MAX_RETRIES`：重试次数（0–2）

Embedding 配置字段结构相同：`STUDYBUDDY_EMBEDDING_{PROVIDER,MODEL,BASE_URL,API_KEY}`。

### 1.2 配置来源与优先级

**当前 runtime source（唯一实现路径）**：
- **进程环境变量**：`os.environ.get("STUDYBUDDY_AI_*")`
- **未配置默认值**：`not_configured`（允许启动，Provider 能力返回 `configured: false`）
- **显式 fake**：`STUDYBUDDY_AI_PROVIDER=fake` 启用确定性演示 Provider（不需要 API key）

**明确排除的持久化路径**：
- ❌ SQLite 数据库（包括 `config` 表、`settings` 表或任何业务表）
- ❌ `data_root/` 文件系统（包括 `config.json`、`.env`、任何配置文件）
- ❌ 浏览器存储（localStorage、sessionStorage、IndexedDB）
- ❌ URL 参数、DOM 属性、HTML 注释
- ❌ 日志输出（包括 `print()`、`logging.*`、`sys.stderr`）
- ❌ diagnostics API 响应
- ❌ backup manifest 或 archive
- ❌ 测试输出文件、trace、screenshot 文件名

### 1.3 Provider 状态契约

**状态枚举**（见 `backend/app/providers/_registry.py`）：
- `not_configured`：未提供任何配置或配置为空
- `invalid_config`：部分配置或不兼容参数（如 fake provider 配置了错误 model）
- `demo`：显式 `fake` provider，确定性输出，无网络
- `configured`：完整非 fake 配置，OpenAI-compatible adapter 可构造
- `verification_status: unverified`：`configured` 状态的 Provider 未经过真实连接验证

**当前行为**：
- `GET /api/ai/capabilities` 返回 `status`、`configured`、`verification_status`、`runtime_kind`、`provider_id`、`model_id`
- 不返回：`api_key`、`base_url`（完整 URL）、Authorization header、原始 Provider 错误、路径、traceback
- `config.py` 中 `ai_api_key` 字段标记 `repr=False`，不出现在 `repr(config)` 中
- `backend/app/providers/_core.py` 定义稳定错误码：`provider_not_configured`、`provider_invalid_config`

### 1.4 Provider Preset 契约（未实现，仅契约冻结）

**Preset 定义**（用于后续 UI 推荐）：
- Preset 仅包含**非敏感元数据**：`provider_id`、`display_name`、`default_model_id`、`default_base_url`、`capability_labels`（如 `["chat", "streaming"]`）
- Preset **不包含**：`api_key`、实时价格、SLA 承诺、额度保证、账户状态
- Preset 可包含**产品推荐备注**：如"社区反馈稳定"、"性价比较高"（主观描述，非技术保证）
- Preset 存储位置：前端静态 JSON 或后端常量（不读取 SQLite、不读取 `data_root`）

**明确非目标**：
- ❌ 动态 Provider 服务发现
- ❌ 实时价格查询或额度检查
- ❌ 自动 Provider 切换或 failover
- ❌ 多 Provider 并行路由

## 2. Email 配置边界（SMTP / Feishu）

### 2.1 配置字段分类

**敏感字段（secret）**：
- `STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD`：SMTP 授权码或密码
- `STUDYBUDDY_REPORT_DELIVERY_SMTP_USERNAME`：SMTP 用户名（可选视为敏感）
- `STUDYBUDDY_REPORT_DELIVERY_FEISHU_WEBHOOK`：飞书自定义机器人 Webhook URL（含 token）
- `STUDYBUDDY_REPORT_DELIVERY_FEISHU_SECRET`：飞书签名密钥（未实现，预留）

**非敏感元数据**：
- `STUDYBUDDY_REPORT_DELIVERY_MODE`：交付模式（`off` / `dry_run` / `live`，默认 `off`）
- `STUDYBUDDY_REPORT_DELIVERY_ENABLED`：启用开关（默认 `false`）
- `STUDYBUDDY_REPORT_DELIVERY_AUTHORIZED`：授权开关（默认 `false`）
- `STUDYBUDDY_REPORT_DELIVERY_SMTP_HOST`：SMTP 服务器地址（如 `smtp.qq.com`）
- `STUDYBUDDY_REPORT_DELIVERY_SMTP_PORT`：SMTP 端口（默认 465）
- `STUDYBUDDY_REPORT_DELIVERY_SMTP_SECURE`：TLS 模式（默认 `true`）
- `STUDYBUDDY_REPORT_DELIVERY_SMTP_TARGETS`：收件人映射（格式 `label=email`，如 `guardian-primary=user@example.com`）
- `STUDYBUDDY_REPORT_DELIVERY_FEISHU_TARGET_LABEL`：飞书目标标签

### 2.2 配置来源与优先级

**当前 runtime source**：
- **进程环境变量**：`os.environ.get("STUDYBUDDY_REPORT_DELIVERY_*")`
- **runtime-only 字段**：`config.report_delivery_smtp_password_runtime`（从环境变量读取，`repr=False`）
- **历史遗留字段**：`config.report_delivery_smtp_password`（标记 `repr=False`，当前与 `_runtime` 同源）

**B4 Delivery 契约继承**（见 `docs/contracts/B4_DELIVERY_COMPONENT_CONTRACT.md`）：
- 默认 `mode=off`、`enabled=false`、`authorized=false`
- `dry_run` 模式不开启网络连接（`DryRunDeliveryAdapter`）
- `live` 模式需显式 `authorization_granted=true` 且 target 在 allowlist 内
- 仅持久化**非敏感 target label**（如 `guardian-primary`），不存储完整邮箱地址或 webhook URL
- Backup/restore **不包含** delivery credentials 或收件人邮箱

**明确排除的持久化路径**（与 Provider 相同）：
- ❌ SQLite、`data_root`、浏览器存储、URL、DOM、日志、diagnostics、backup、测试输出

### 2.3 Delivery 状态契约

**稳定错误码**（见 `backend/app/delivery.py`）：
- `delivery_disabled`：delivery 未启用
- `delivery_target_not_allowed`：目标不在 allowlist
- `delivery_authorization_required`：live 模式需显式授权
- `delivery_configuration_invalid`：配置不完整或格式错误
- `delivery_timeout`：发送超时
- `delivery_failed`：发送失败（通用）

**API 契约**（见 `backend/app/api/study_capture_reports.py`）：
- `POST /api/study/reports/{report_id}/delivery`：执行交付，支持 `Idempotency-Key` header
- `GET /api/study/reports/{report_id}/delivery-attempts`：只读审计日志，不返回 payload 内容或 credentials

## 3. 自由配置契约（未实现写入，仅冻结接口形状）

### 3.1 配置写入 API 形状（预留，P1-5-0 不实现）

**假设的 API 形状**（用于后续评审，当前不存在）：
```text
POST /api/system/provider-config
{
  "provider_id": "deepseek",
  "model_id": "deepseek-chat",
  "base_url": "https://api.deepseek.com",
  "api_key": "<redacted>",  // 前端不回显，后端不存储
  "timeout_seconds": 30
}
```

**P1-5-0 明确不实现**：
- ❌ 任何写入 Provider/Email 配置的 API endpoint
- ❌ 任何保存 secret 到持久化存储的逻辑
- ❌ 前端配置表单的"保存"按钮功能
- ❌ 配置热重载或动态切换

### 3.2 当前前端只读边界

**现有页面**（见 `backend/app/static/settings.html`、`settings-provider.html`）：
- 显示 Provider/Email **配置状态**（`configured` / `not_configured` / `demo`）
- 显示**非敏感元数据**（provider_id、model_id、timeout）
- **不回显** API key、password、webhook URL
- **不提供**"保存配置"按钮或表单提交
- 页面明确显示：**"Provider 配置写入契约尚未完成批准"**

**前端安全边界**（见 `backend/app/static/js/api.js`）：
- `api.js` 不包含 `saveProviderConfig()` 或 `saveEmailConfig()` 函数
- 不发送包含 secret 的 POST/PATCH 请求
- 不在 `localStorage`/`sessionStorage` 中缓存 credentials

## 4. Secret Source 契约

### 4.1 Secret 生命周期

**Runtime-only 原则**：
1. **Source**：仅从进程启动时的环境变量读取
2. **In-memory**：加载到进程内存（`config` dataclass 实例）
3. **Request-scoped use**：每次 Provider/Delivery 调用时从 `config` 读取
4. **Never persist**：不写入文件、数据库、日志、backup、前端响应
5. **Process boundary**：进程退出后，secret 从内存消失

**配置变更流程**（当前唯一路径）：
1. 操作员修改环境变量（PowerShell、`.env` 文件、系统设置）
2. **重启进程**（`uvicorn` 或 FastAPI 应用）
3. 新配置生效

**明确不支持**：
- ❌ 运行时热重载配置（不重启进程）
- ❌ 配置版本管理或历史记录
- ❌ 多配置 profile 切换
- ❌ 配置加密存储或密钥管理服务（KMS）

### 4.2 脱敏规则

**`repr=False` 字段**（见 `backend/app/config.py`）：
- `ai_api_key`
- `embedding_api_key`
- `report_delivery_smtp_password`
- `report_delivery_smtp_password_runtime`
- `report_delivery_feishu_webhook`

**脱敏实施**：
- Python `dataclass(repr=False)`：字段不出现在 `repr(config)` 或 `str(config)` 中
- 日志输出：不使用 `print(config)` 或 `logging.info(f"{config}")`
- API 响应：capabilities API 明确不返回 secret 字段
- Traceback：异常处理不暴露 config 实例的完整 repr

**脱敏验证**（治理测试覆盖）：
- `repr(config)` 不包含 `api_key`、`password`、`webhook` 字面值
- `GET /api/ai/capabilities` JSON 响应不包含 secret 键
- Backup manifest 不包含 credentials

### 4.3 脱敏失败处理

**当前行为**：
- 如果 `repr(config)` 意外暴露 secret，属于**代码缺陷**，需修复 `config.py`
- 如果 API 响应意外暴露 secret，返回 `500` 并记录错误（不暴露实际 secret）

**明确不实现**（超出 v1 范围）：
- ❌ 自动 PII/secret 扫描或编辑
- ❌ 动态脱敏策略配置
- ❌ Secret 泄漏检测或撤销流程

## 5. Connection-Test 契约（未实现，仅冻结行为）

### 5.1 触发机制

**明确要求**：
- Connection-test **必须显式触发**（UI 按钮、CLI 命令、专用 API）
- **不得自动触发**：不在启动时、不在配置读取时、不在 capabilities API 调用时
- **不改变配置状态**：测试成功/失败不自动启用或禁用 Provider

**假设 API 形状**（未实现）：
```text
POST /api/system/provider-connection-test
{
  "provider_id": "deepseek",
  "model_id": "deepseek-chat",
  "base_url": "https://api.deepseek.com",
  "api_key": "<test-only-key>"  // 不保存到配置
}
```

### 5.2 测试 Payload 和边界

**固定 synthetic payload**：
- LLM test：`messages: [{"role": "user", "content": "Hello"}]`，`max_tokens: 10`
- Embedding test：`input: ["test"]`
- SMTP test：固定主题"StudyBuddy Configuration Test"，固定正文"No study material is included."
- Feishu test：固定 `msg_type: "text"`，固定内容"Configuration test"

**响应限制**：
- 读取前 1024 字节响应体，截断超出部分
- 超时限制：Provider 30s、SMTP 10s、Feishu 10s
- 不跟随 HTTP 重定向（`allow_redirects=False`）

**错误映射**（稳定错误码）：
- 网络错误 → `provider_connection_failed` / `delivery_timeout`
- 超时 → `provider_timeout` / `delivery_timeout`
- HTTP 4xx → `provider_invalid_config`
- HTTP 5xx → `provider_unavailable`
- 协议错误 → `provider_protocol_error`
- 响应过大 → `provider_response_too_large`

### 5.3 测试权限边界

**授权要求**（未实现，预留）：
- Connection-test 可能需要**显式用户授权**（防止滥用或意外网络请求）
- 测试失败不阻止应用启动或正常使用（已配置 Provider 仍可用于实际请求）

**明确排除**：
- ❌ 自动定期健康检查（无 cron、无 scheduler）
- ❌ 测试结果持久化或历史记录
- ❌ 测试流量计入配额或计费
- ❌ 批量测试多个 Provider

## 6. Email/Feishu 配置契约（继承 B4）

### 6.1 B4 Delivery 契约继承

**安全默认值**：
- `STUDYBUDDY_REPORT_DELIVERY_MODE=off`（不发送）
- `STUDYBUDDY_REPORT_DELIVERY_ENABLED=false`
- `STUDYBUDDY_REPORT_DELIVERY_AUTHORIZED=false`

**Dry-run 保证**：
- `DryRunDeliveryAdapter` 不开启网络连接（见 `backend/app/delivery.py`）
- 返回确定性成功响应，不依赖真实 SMTP/Feishu

**Live 模式门槛**：
- 需显式 `authorization_granted=true`（每次请求）
- 需 target 在 allowlist 内（`STUDYBUDDY_REPORT_DELIVERY_SMTP_TARGETS`）
- 失败不自动重试（需显式 `retry_of` 参数）

### 6.2 Email 配置特定规则

**SMTP Targets 格式**：
- 格式：`label1=email1,label2=email2`（逗号分隔）
- Label 允许字符：`[a-zA-Z0-9_-]`
- 不允许重复 label
- Email 必须符合基本格式（`@` 分隔、域名存在）

**Feishu Webhook 格式**（见 `backend/app/config.py:_env_delivery_feishu_webhook`）：
- 必须以 `https://open.feishu.cn/open-apis/bot/v2/hook/` 开头
- 不允许 `username`、`password`、`query`、`fragment`（路径形式 token 除外）

**配置验证**：
- 无效格式抛出 `ValueError("invalid_studybuddy_report_delivery_smtp_targets")`
- 无效 webhook 抛出 `ValueError("invalid_report_delivery_feishu_webhook")`

### 6.3 Delivery Adapter 错误映射

**见 `backend/app/delivery.py`**：
- `DeliveryAdapterError`：基类，包含 `code` 字段
- 网络错误、超时、认证失败均映射为稳定错误码
- API 层捕获 `ValueError` 并返回对应 HTTP 状态码

## 7. Backup/Restore 契约

### 7.1 明确排除 Credentials

**Backup manifest 不包含**（见 `backend/app/backup.py`）：
- ❌ `STUDYBUDDY_AI_API_KEY`
- ❌ `STUDYBUDDY_EMBEDDING_API_KEY`
- ❌ `STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD`
- ❌ `STUDYBUDDY_REPORT_DELIVERY_SMTP_USERNAME`
- ❌ `STUDYBUDDY_REPORT_DELIVERY_FEISHU_WEBHOOK`
- ❌ 完整收件人邮箱地址（仅存 label）

**Backup manifest 包含**：
- ✅ `schema_version`、`current_schema_at_backup`
- ✅ 非敏感 Provider 元数据（`provider_id`、`model_id`，如果需要）
- ✅ Delivery target labels（不含邮箱）

**Restore 行为**：
- Restore 后，Provider/Email 配置**仍需从环境变量重新读取**
- Restore 不尝试恢复 credentials（进程启动时统一加载）

### 7.2 B4 Delivery Backup 边界

**见 B4 C5/C6 evidence**：
- Backup archive 不包含 delivery adapter credentials
- `delivery_attempts` 审计表仅记录非敏感元数据：`target_label`、`status`、`error_code`、`timestamp`
- Restore 后，delivery 配置仍需操作员手动配置环境变量

## 8. 非目标与未来扩展

### 8.1 明确非目标（P1-5 及 v1 范围外）

**配置管理**：
- ❌ 配置版本管理或审计日志
- ❌ 配置热重载（不重启进程）
- ❌ 多环境配置（dev/staging/prod）
- ❌ 配置导入/导出（作为独立功能）

**高级 Provider 能力**：
- ❌ 多 Provider 并行或自动 failover
- ❌ Provider 服务发现或注册中心
- ❌ 动态额度查询或计费集成
- ❌ Provider 性能监控或 SLA 追踪

**高级 Email 能力**：
- ❌ HTML 邮件或附件
- ❌ 批量邮件或邮件列表
- ❌ 邮件模板管理
- ❌ 邮件发送队列或后台任务
- ❌ 邮件发送历史或重试策略

**企业级安全**：
- ❌ 密钥管理服务（KMS）集成
- ❌ 加密配置存储或传输
- ❌ 审计日志或合规报告
- ❌ 多用户权限或角色管理

### 8.2 未来扩展评估条件

**如果需要实现配置写入（P1-5-1 及后续）**，必须先通过：
1. P1-5-0 契约评审（本文档）
2. Secret 泄漏扫描测试（P1-5-5）
3. Browser evidence：配置写入不回显 secret、不保存到 SQLite/localStorage
4. Operator runbook：配置变更流程、失败恢复、安全审计

**评估标准**：
- Secret 泄漏风险可控（日志、DOM、URL、backup 均无泄漏）
- 用户理解"配置重启后失效"（runtime-only）或"配置存储风险"（如果持久化）
- 配置写入不破坏现有 B4 delivery 安全默认值
- 配置写入不引入新的攻击面（如 SSRF、注入）

---

## 契约批准与生效

- **契约冻结日期**：2026-01-09
- **批准状态**：待评审
- **生效条件**：P1-5-0 治理测试通过、文档更新完成、无代码修改
- **后续切片依赖**：P1-5-1（配置 UI 实现）、P1-5-2（connection-test 实现）、P1-5-3（配置持久化评估）、P1-5-4（浏览器证据）、P1-5-5（泄漏扫描）均需等待 P1-5-0 批准后启动
