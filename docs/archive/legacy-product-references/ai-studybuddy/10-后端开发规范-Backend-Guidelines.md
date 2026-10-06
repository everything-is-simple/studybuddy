# AI StudyBuddy 后端开发规范 Backend Guidelines

**版本**：v1.7
**日期**：2026-07-21
**状态**：有效
**用途**：正式后端开发的目录结构、SQLite/migration 约定、Adapter/API 输出、日志、环境变量和验证规则。修改后端服务、API、Worker 或数据模型前必须读本文件。

---

## 一、后端目录结构

```text
packages/backend/src/
  config/         环境变量集中读取
  db/             数据库连接、路径、migration、SQL 文件
    sql/          schema SQL 文件
  adapters/       Adapter 实现（StorageAdapter、PdfConverter、OcrConverter 等）
  api/            Express 路由
  services/       业务服务（SemesterOnboardingService、ReportService 等）
  utils/          日志、ID 生成等工具
  server.ts       Express 启动入口
```

- 业务代码不自行拼接路径，统一走 `db/paths.ts`。
- 业务代码不直接 `require("better-sqlite3")`，统一走 `db/connection.ts`。
- 业务代码不直接 import `I:\ai-studybuddy-composer` 的任何文件。

---

## 二、SQLite 连接约定

### 2.1 双库模型

| 库     | 文件名          | 职责                                                               | 写入频率       |
| ------ | --------------- | ------------------------------------------------------------------ | -------------- |
| 全局库 | `studybuddy.db` | 系统配置、孩子档案、学期索引、备份记录                             | 低频，小而稳定 |
| 学期库 | `semester.db`   | 课程实例、考试尝试、任务、事件、资料索引、知识模块、jobs、报告证据 | 随学习活动写入 |

全局库不写学期业务明细；学期库之间互不共享事务或文件空间。

### 2.2 打开时必做

```typescript
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');
```

### 2.3 关闭或归档前必做

```typescript
db.pragma('wal_checkpoint(TRUNCATE)');
// 然后执行 PRAGMA integrity_check 确认结果为 ok
db.close();
```

### 2.4 并发约束

- 单 Node 进程写入，不并发打开多个写连接。
- 学期库通过 `SemesterDatabaseFactory` 按需打开，使用后关闭。
- 全局库在进程生命周期内保持打开。

---

## 三、路径安全约定

- `APP_DATA_ROOT` 通过环境变量读取，禁止硬编码盘符。
- `paths.ts` 统一生成所有路径，业务代码不自行拼接。
- 所有路径经 `resolveAppDataPath()` 校验：resolved path 必须在 `APP_DATA_ROOT` 内，否则抛错。
- 拒绝包含 `..` 的相对路径段。

存储拓扑：

```text
APP_DATA_ROOT/
  studybuddy.db
  semesters/<semester-id>/
    semester.db
    files/
    tmp/
  tmp/
  backups/
  config/                 # DPAPI 加密的 active/prev 配置与非秘密状态元数据
```

---

## 四、Migration 约定

- Schema 与 migration SQL 以 `src/db/sql/*.ts` 的字符串常量维护，并由 `migrations.ts` 直接 import；不得在运行时读取未复制到 `dist/` 的 `.sql` 文件。
- `schema_migrations` 表记录已执行 version；全局库和学期库各自维护独立记录。
- Migration 版本必须从 1 连续递增。runner 先检查已执行版本，再按顺序执行未执行版本；发现版本缺口必须失败，不得静默跳过。
- 每个 migration 的 SQL 与其 version 记录必须在同一个 SQLite 事务内提交。首版 schema 作为 v1，后续结构变更新增 v2、v3……，不改写已发布版本。
- Schema 可使用 `CREATE TABLE IF NOT EXISTS` 保持首版初始化幂等，但不能以幂等 SQL 代替版本化迁移。
- 构建脚本清理 `dist/` 时必须同步清理 `tsconfig.tsbuildinfo`，再执行 project build；测试必须覆盖干净构建后的 `dist` 运行态。

---

## 五、Adapter 统一输出格式

### 5.1 Converter 输出

所有 Converter（PdfConverter、OcrConverter、TextConverter）统一返回 `ConverterResult`：

```typescript
interface ConverterResult {
  ok: boolean;
  sourceType: 'pdf' | 'image' | 'text';
  text?: string;
  metadata?: { pageCount?: number; charCount?: number; hasFormula?: boolean; hasTable?: boolean };
  warnings?: string[];
  error?: string;
}
```

### 5.2 报告发送输出

报告发送必须返回按渠道划分的结果，便于只重试失败渠道：

```typescript
interface ReportSendResult {
  channel: 'email' | 'feishu';
  success: boolean;
  errorSummary?: string;
}
```

### 5.3 Adapter 边界

- 业务代码不得直接依赖 Python 命令、绝对路径、SMTP 授权码或 Webhook URL。
- 分级 fallback 的最终人工出口必须明确（参见 `08-共同底座架构` 第四节）。

### 5.4 AI Provider Adapter

- OpenAI-compatible 接入统一通过 `OpenAiProvider`；业务 Service、Job 和 API 不得直接实例化 SDK 客户端。
- `AiProviderRouter` 负责按 priority 轮询、首个成功返回、`fallbackUsed` 标记和失败汇总；未配置抛 `AI_NOT_CONFIGURED`。
- Router 健康状态只存在于单个 Router 实例内，并按 Provider 实例隔离。连续失败第 5 次后固定冷却 10 分钟；冷却期间跳过该 Provider，后续 Provider 成功时 `fallbackUsed` 仍为 `true`。
- 冷却到期允许恢复探测：成功清零，失败立即进入新的 10 分钟冷却。阈值和冷却时间属于当前产品固定规则，不新增环境变量、数据库或跨进程共享。
- 本次至少真实调用过一个 Provider 但最终全部失败时抛 `AI_ALL_PROVIDERS_FAILED`；全部 Provider 均处于冷却且没有外部调用时抛 `AI_ALL_PROVIDERS_COOLING_DOWN`，错误只包含 Provider 名称和最早恢复时间。
- Provider 必须支持构造函数注入 `fetch`，Router 必须支持注入 `now` 与 `logger`，以便测试模拟成功、失败、超时、冷却和恢复；测试不得使用真实 API Key 或真实模型网络请求。

---

## 六、API 响应信封约定

使用 `@ai-studybuddy/shared` 中的 `ApiSuccess<T>` / `ApiError`：

```typescript
// 成功
{ success: true, data: T, meta?: { page?: number; pageSize?: number; total?: number } }

// 失败
{ success: false, error: { code: string; message: string } }
```

- 所有 API 端点必须返回此信封格式。
- 错误码使用大写蛇形命名（如 `SEMESTER_NOT_FOUND`、`DB_INIT_FAILED`）。
- AI 开发验证路由 `POST /api/dev/ai/generate` 校验 `taskType`、`inputText`，并保持 `AI_NOT_CONFIGURED`（503）与 `AI_ALL_PROVIDERS_FAILED`（502）的稳定语义。

---

### 6.1 Phase 2 S5 API 与持久化边界

- 模拟考写接口集中在 `/api/mock-exam-papers` 与 `/api/mock-exam-attempts`，使用学期 migration v9 的五张 `mock_exam_*` 表；学生读取 DTO 不返回正确答案，提交后才返回批改结果。
- `GET /api/assessment-attempts/:id/cram-cards?semesterId=...` 与 `GET /api/assessment-attempts/:id/cram-plan?semesterId=...` 是确定性即时只读聚合；它们必须验证同学期、同课程和已确认考试，不得新增卡片/计划持久化或写回 S3/S4 历史事实。
- T06 考试工作台冲刺区只组合既有考试、模拟考、速背与计划状态，不增加后端端点。
- S5 当前不写 StudyEvent、不调用真实 AI/Provider、不启动 Worker，也不把题干、答案、作答、错题正文或资料原文写入日志和 S6 报告。

## 七、日志规范

### 7.1 禁止输出

- API Key
- SMTP 授权码
- 完整 Feishu Webhook URL
- 学生隐私全文（资料正文、笔记正文、完整答案、聊天内容）
- 完整堆栈跟踪到生产日志（开发环境可输出，生产只记摘要和 error code）

AI Router 请求日志额外只允许记录 `taskType`、Provider 名称、model、token、耗时、fallback 和失败摘要；不得记录请求输入、模型输出或 Provider 配置中的密钥。

熔断日志只允许两个事件：`AI_PROVIDER_CIRCUIT_OPENED` 记录 `provider`、`cooldownStartedAt`、`cooldownEndsAt`，`AI_PROVIDER_CIRCUIT_CLOSED` 记录 `provider`、`cooldownEndedAt`；除日志自身时间外不得接收或记录原始 Error、Key、URL、正文或完整 UUID。

### 7.2 日志目录

运行日志只能写入与 `APP_DATA_ROOT` 不相交的、受控运行根同级 `logs/` 目录；不得写入 `APP_DATA_ROOT`、仓库、用户目录本身或磁盘根，也不进入主仓库 Git。日志根、允许子目录与可轮转/保留文件必须由显式 allowlist 管理；遇到空路径、越界、受保护根或符号链接/junction 等重解析点时必须拒绝。

### 7.3 错误日志格式

```text
[ERROR] <error_code> <简短摘要> <可选 context 键值对>
```

### 7.4 日志等级与事件命名（T05-2 规范）

#### 等级（level）语义

| level | 用途                                             | 示例事件                                    |
| ----- | ------------------------------------------------ | ------------------------------------------- |
| DEBUG | 诊断细节，默认不落盘；仅开发/排障启用           | 配置快照对比                                |
| INFO  | 正常生命周期事件                                 | `AI_REQUEST_SUCCESS`、`AI_PROVIDER_CIRCUIT_CLOSED` |
| WARN  | 降级、重试、熔断、单渠道失败                     | `AI_REQUEST_FAILURE`、`AI_PROVIDER_CIRCUIT_OPENED` |
| ERROR | 不可恢复或拒绝启动、越界失败                     | `BACKEND_BOOTSTRAP_FAILED`                  |

#### 事件命名格式

事件名统一为 `DOMAIN_ACTION_STATE`（大写蛇形）：

- `AI_REQUEST_SUCCESS` / `AI_REQUEST_FAILURE`：AI 请求成功/失败
- `AI_PROVIDER_CIRCUIT_OPENED` / `AI_PROVIDER_CIRCUIT_CLOSED`：Provider 熔断开/闭
- `MAINTENANCE_*`：维护类事件（由维护日志定义）

#### 允许字段（JSONL 日志白名单）

运行日志写入 `logs/runtime/ai-events.jsonl`（AI）、`logs/errors/maintenance.jsonl`（维护）、`logs/operations/operations.jsonl`（操作），仅允许：

- AI 事件：`event`、`level`、`taskType`、`provider`、`model`、`tokenUsed`、`latencyMs`、`fallbackUsed`、`attemptedProviderCount`、`attemptedProviders`、`cooldownStartedAt`、`cooldownEndsAt`、`cooldownEndedAt`、`errorCode`、`timestamp`
- 维护/操作事件：`event`、`level`、`errorCode`、`cleanupErrorCount`、`cleanupErrorCode`、`status`、`timestamp`

所有事件必须包含 `event`、`level`、`timestamp`；字符串字段长度 ≤ 128；`errorCode` 必须为大写蛇形（`^[A-Z][A-Z0-9_]{1,63}$`）。

#### 面向用户 vs 内部诊断边界

- 面向用户：API 错误只返回固定脱敏错误码与可行动中文信息（`{ success: false, error: { code, message } }`）。
- 内部诊断：日志只记录允许字段与错误码；绝不记录请求正文、模型输出、资料原文、完整答案、完整 UUID、绝对路径或外部原始响应。

---

## 八、环境变量约定

### 8.1 文件管理

- `.env.example` 列出所有变量名（不填真实值），提交到 Git。
- 后端只自动加载名为 `.env.local` 的文件；`.env` 和 `.env.*.local` 不属于后端配置来源。
- 根目录 `.env.local` 由 `.gitignore` 忽略；不得读取、记录或提交其中的真实值。
- 前端由 Vite 5.4 读取 `packages/frontend` 下的 `.env`、`.env.local`、`.env.<mode>`、`.env.<mode>.local`；根目录 `.env.local` 不会被前端自动读取。

### 8.2 读取约定

- 后端仅通过 `src/config/env.ts` 读取 `process.env`；业务代码禁止直接调用 `process.env`。
- 后端依次检查 `process.cwd()/.env.local`、`process.cwd()/../../.env.local`、编译模块目录上溯三级的 `.env.local`，只加载第一个存在的候选文件。
- dotenv 不覆盖已有进程环境，因此同名配置优先级为：进程环境变量 > 首个命中的后端 `.env.local` > 代码默认值。
- 前端同名配置优先级遵循 Vite：启动进程中已有的 `VITE_*` > mode-specific env 文件 > 通用 env 文件；浏览器端仅暴露 `VITE_*`。
- 启动时校验必需变量（如 `APP_DATA_ROOT`）必须存在且可写。

### 8.3 变量清单

| 变量名                                 | 用途                                                                         | 必填                          |
| -------------------------------------- | ---------------------------------------------------------------------------- | ----------------------------- |
| `APP_DATA_ROOT`                        | 运行数据根目录                                                               | 是                            |
| `BACKEND_PORT`                         | 后端端口（默认 3000）                                                        | 否                            |
| `BACKEND_HOST`                         | 后端监听地址（默认 127.0.0.1）                                               | 否                            |
| `CONFIG_ALLOWED_ORIGINS`               | 追加本机前端 Origin；仅允许带显式端口的 loopback HTTP Origin，逗号分隔       | 否                            |
| `PYTHON_PATH`                          | OCR 子进程 Python 可执行文件（默认 `python`）                                | 否                            |
| `OCR_TIMEOUT_MS`                       | OCR 子进程超时毫秒数（默认 60000）                                           | 否                            |
| `DOCX_ZIP_MAX_ENTRIES`                 | DOCX ZIP 最大条目数（默认 10000）                                            | 否                            |
| `DOCX_ZIP_MAX_ENTRY_SIZE_BYTES`        | DOCX 单条目解压大小上限                                                      | 否                            |
| `DOCX_ZIP_MAX_TOTAL_SIZE_BYTES`        | DOCX 总解压大小上限                                                          | 否                            |
| `DOCX_ZIP_MAX_DOCUMENT_XML_SIZE_BYTES` | DOCX 正文 XML 大小上限                                                       | 否                            |
| `PPTX_ZIP_MAX_ENTRIES`                 | PPTX ZIP 最大条目数（默认 10000）                                            | 否                            |
| `PPTX_ZIP_MAX_ENTRY_SIZE_BYTES`        | PPTX 单条目解压大小上限                                                      | 否                            |
| `PPTX_ZIP_MAX_TOTAL_SIZE_BYTES`        | PPTX 总解压大小上限                                                          | 否                            |
| `PPTX_ZIP_MAX_SLIDE_XML_SIZE_BYTES`    | PPTX 单页 XML 大小上限                                                       | 否                            |
| `AI_PROVIDERS`                         | OpenAI-compatible Provider JSON 数组；按 `priority` 升序失败切换并冷却       | 否；优先于 legacy 单 Provider |
| `AI_TIMEOUT_MS`                        | 单次 AI 请求超时毫秒数（默认 60000）                                         | 否                            |
| `AI_BASE_URL`                          | legacy 单 Provider Base URL；仅 `AI_PROVIDERS` 为空时使用                    | 否                            |
| `AI_API_KEY`                           | legacy 单 Provider API Key；仅 `AI_PROVIDERS` 为空时使用                     | 否                            |
| `AI_MODEL`                             | legacy 单 Provider 模型名；仅 `AI_PROVIDERS` 为空时使用                      | 否                            |
| `SMTP_HOST`                            | QQ SMTP 主机（默认 `smtp.qq.com`）                                           | 渠道启用时必填                |
| `SMTP_PORT`                            | QQ SMTP 端口（默认 465）                                                     | 否                            |
| `SMTP_SECURE`                          | 是否启用 SSL/TLS                                                             | 否                            |
| `SMTP_USER`                            | QQ 邮箱账号                                                                  | 渠道启用时必填                |
| `SMTP_AUTH_CODE`                       | QQ SMTP 授权码；不得进入日志或提交                                           | 渠道启用时必填                |
| `SMTP_TO`                              | 收件邮箱                                                                     | 渠道启用时必填                |
| `FEISHU_WEBHOOK_URL`                   | 飞书 Webhook；不得进入日志或提交                                             | 渠道启用时必填                |
| `VITE_API_BASE_URL`                    | 前端 API/开发代理基础地址；仅来自前端进程环境或 `packages/frontend` env 文件 | 否                            |

所有 `/api` 路由统一执行 loopback Origin 校验。默认允许 Vite 开发端口 `5173` 与 preview/Playwright 端口 `4173`；无 `Origin` 的本机 CLI 请求允许通过。配置 POST 额外只接受 JSON。`CONFIG_ALLOWED_ORIGINS` 不接受远程 host、`*`、凭据、路径、查询或 fragment。

> Phase 0.7 已验证 QQ SMTP 与飞书 Webhook 的真实送达；Phase 0.8 T06 只实现 S1 学习节奏核心 API，不消费这些报告发送变量。正式业务发送留到 S6 ParentReport。

### 8.4 本机配置中心边界（Phase 1-T08 已实现）

- 配置 API 只能返回普通配置、掩码值、`configured`、`lastTestAt`、`lastTestStatus` 和固定错误码；禁止提供读取完整 API Key、SMTP 授权码或 Webhook URL 的接口。
- 秘密由后端配置服务接收后在内存中完成测试，测试成功才写入 Windows 当前用户加密存储，并以临时文件 + 原子替换方式激活。
- 运行时 Adapter 依赖配置服务提供的不可变快照；不得在业务代码中新增对 `process.env` 的直接读取，也不得把秘密写入普通 SQLite 表、JSON 明文文件或日志。
- AI 测试必须使用最小无隐私请求；SMTP 测试分为连接验证与用户显式触发的测试邮件；飞书测试必须发送固定无隐私测试卡片。
- 保存失败、测试失败、解密失败和配置损坏必须返回固定脱敏错误码；不得把第三方 SDK 原始 Error、请求 URL、响应正文或秘密传入日志和 API 响应。
- 已按 `.plans/phase1-t08-config-center-plan.md` v6 实现。后续修改仍必须独立登记任务和计划，不能绕过连接测试直接写 active 配置。
- 配置初始化必须先于 Express listen、Material Worker 和家长报告投递；运行时消费者只从 `config-registry` 读取不可变快照。
- API 全局执行 loopback Origin 策略，配置 POST 只接受 JSON；候选配置测试失败直接丢弃，不生成未验证磁盘状态。
- 运行时配置优先级固定为：当前 Windows 用户 DPAPI 加密的 active 快照 > 环境变量 fallback > 未配置；加密快照位于 `APP_DATA_ROOT/config`，不写入 SQLite。
- AI 环境 fallback 内部优先级为：非空 `AI_PROVIDERS` > legacy `AI_BASE_URL` / `AI_API_KEY` / `AI_MODEL`；QQ SMTP 仅在 host、账号、授权码、收件邮箱均存在时识别为已配置；飞书以 Webhook 是否存在判断。
- 设置页只能展示后端生成的普通摘要与固定星号掩码；新输入秘密的显示/隐藏仅保存在当前 React 组件状态，刷新恢复遮挡，不写入 `localStorage` 或 `sessionStorage`。

---

## 九、试炼场边界

- `packages/` 不得 import `I:\ai-studybuddy-composer` 的任何代码。
- 试炼场代码只作思路参考，Phase 0.8 以 Adapter 方式重新实现。
- 试炼场的 `.env.local`、`.venv`、`node_modules`、输出和真实凭据不进入主仓库。

---

## 十、测试与验证命令

```powershell
# 类型检查
pnpm type-check

# 编译
pnpm build

# 文档治理检查
powershell -ExecutionPolicy Bypass -File scripts\check-docs-governance.ps1

# 空白行检查
git diff --check
```

涉及 API 变更时，额外手动验证：

```powershell
Invoke-RestMethod http://localhost:3000/api/health
```

## S7-MVP 后端补充规则（2026-07-25）

- `whisper.cpp` 只能由独立 Adapter 以参数数组启动；用户文件名、标题、文本不得拼接到 shell 命令。
- CLI/模型、超时和最大字节数只能由 `env.ts` 集中读取；未配置返回稳定 `ASR_RUNTIME_UNAVAILABLE`，不猜路径、不回退云端。
- 临时 WAV 目录必须由 `paths.ts` 从 `APP_DATA_ROOT` 派生，并在 `finally` 清理；API、日志和 DTO 不得泄漏路径、stdout/stderr、原始音频或转写全文。
- S7-MVP 只在学生显式保存后调用 S2 的窄文本 handoff；不得创建 S7 Worker/Job，不得自动创建 `material_convert` 或 `note_generate` Job。
- API 测试使用真实 SQLite 与受控 fake CLI，不 mock 数据库；开发机真实 CLI smoke 使用隔离数据根和脱敏合成 WAV。
