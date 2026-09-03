# P1-5-3 配置持久化评估

> 状态：`evaluation-complete / decision-recorded / 2026-01-09`
>
> 本文档评估 Provider（AI LLM / Embedding）与 Email（SMTP / Feishu）配置在 StudyBuddy 中持久化的可行方案、风险与代价，并给出决策。
>
> **本切片不修改 `backend/app/` 生产代码、schema、migration、API 或前端行为。产出为评估结论与治理测试。**

## 1. 评估目的

P1-5-2 已实现 connection-test（`docs/evidence/P1_5_2_CONNECTION_TEST_EVIDENCE.md`），但配置本身仍**只能**通过进程环境变量提供，且变更必须重启进程。P1-5-1（配置 UI）若要提供"填完即用"体验，前置问题是：

**配置（尤其是 secret）能否、以及应否被持久化？**

本评估回答该问题，并为 P1-5-1 的形态定型。

## 2. 现状事实（已代码核实）

### 2.1 配置加载路径

| 事实 | 位置 | 说明 |
|---|---|---|
| 配置仅从环境变量构造 | `backend/app/config.py:253` `config_from_environment()` | 全文件对 `open(` / `read_text` 的匹配数为 **0**；不读任何文件 |
| 无 `.env` 加载器 | 全 `backend/app/` | `dotenv` / `load_dotenv` 匹配数为 **0**。`.env.example` 是**纯文档模板**，运行时不被读取 |
| 配置为不可变对象 | `backend/app/config.py:45-46` | `@dataclass(frozen=True) class AppConfig` |
| 配置在建 app 时加载一次 | `backend/app/app_factory.py:129` | `app.state.config = config or config_from_environment()` |
| 处理器统一从 `app.state.config` 读取 | `backend/app/api/*.py` | 13 个模块共约 320 处引用；无任何模块级 `config` 全局变量 |
| 启动时校验配置 | `backend/app/startup_preflight.py` `validate_config()` | host / port / concurrency / log level / demo 组合 / backup_root 位置 |

### 2.2 Secret 字段现状

`backend/app/config.py` 共 **8** 个 `repr=False` 字段：

| 行 | 字段 | 分类 |
|---|---|---|
| 53 | `ai_api_key` | secret |
| 62 | `embedding_api_key` | secret |
| 76 | `report_delivery_smtp_password` | secret（历史字段） |
| 77 | `report_delivery_feishu_secret` | secret（预留未使用） |
| 102 | `report_delivery_smtp_username` | 准 secret |
| 103 | `report_delivery_smtp_password_runtime` | secret |
| 104 | `report_delivery_smtp_targets` | 隐私（收件人邮箱） |
| 107 | `report_delivery_feishu_webhook` | secret（含 token） |

契约 §4.2 只列出 5 个，实际为 8 个。差异项（`report_delivery_feishu_secret`、`report_delivery_smtp_username`、`report_delivery_smtp_targets`）已同样 repr 隐藏，属于契约文档少列而非实现缺陷。

### 2.3 持久化载体现状

| 载体 | 现状 | 是否进 backup |
|---|---|---|
| SQLite | schema v14（`backend/app/migrations/runner.py:34`），37 张业务表 | ✅ **整库进入**（`backup.py:190-193` SQLite Online Backup API 全库复制） |
| `data_root/originals/` | hash 派生原件存储 | ✅ 按引用逐文件复制（`backup.py:197-206`） |
| `data_root/` 其他文件 | 仅 `.studybuddy-instance.lock`、`.studybuddy.pid` | ❌ **不进入** backup（backup 只复制 DB + originals + manifest） |
| 环境变量 | 进程内存 | ❌ 不进入任何产物 |

**无任何配置表 / 设置表存在**。`rhythm_settings` 是学习节奏领域表（`_v10_phase9b_material_learning.py:65`），与系统配置无关。

### 2.4 一个被忽略的技术事实

Provider / Embedding / task runner 均为**每请求现场构造**，不是启动时单例：

- `provider_registry(...)` — `backend/app/providers/_registry.py:216`，在 `api/system.py`、`api/study_generation.py`、`api/study_notes.py`、`api/ai_retrieval_qa.py`、`api/study_capture_reports.py` 内逐次调用
- `_embedding_provider(config)` — `backend/app/task_handlers.py:21`
- `build_task_runner(config)` — `backend/app/task_handlers.py:96`，在 `api/tasks.py:53` 每次重试请求时重建

**含义**：只要替换 `app.state.config`，下一次请求即可使用新配置，**技术上不需要重启进程**。这使"热重载"从"不可能"降级为"可能但有代价"（见 §4.4）。这一点必须诚实记录 —— 契约 §4.1 声明"不支持热重载"是**策略选择**，不是技术限制。

## 3. 评估维度

每个方案按以下维度评估：

1. **secret 静态暴露面**：secret 落盘后谁能读到
2. **backup 污染**：secret / 隐私是否流入 backup 产物
3. **迁移代价**：是否需要 migration、schema 版本变更、rollback 测试
4. **生效方式**：是否仍需重启（决定 UX 收益）
5. **契约冲突**：是否需要修改已冻结的 P1-5-0 契约
6. **可逆性**：方案失败后回退成本

## 4. 方案评估

### 4.1 方案 0：维持现状（环境变量 + 重启）

**形态**：不做任何持久化。配置变更 = 改环境变量 + 重启进程。

| 维度 | 评估 |
|---|---|
| secret 静态暴露面 | 取决于操作员如何设置环境变量（PowerShell profile / 系统环境变量 / 未跟踪 `.env` 由操作员自行 source）。应用不增加暴露面 |
| backup 污染 | 无 |
| 迁移代价 | 无 |
| 生效方式 | 必须重启 |
| 契约冲突 | 无（即契约现状） |
| 可逆性 | 不适用 |

**优点**：零新增风险，零代价，与 P1-5-0 契约完全一致。

**缺点**：配置门槛高。操作员必须知道 20+ 个环境变量名、正确的取值范围、以及"改完要重启"。目前只有 `.env.example` 和 `docs/operations/AI_PROVIDER_SETUP.md` 提供指引，没有任何交互式校验。这是**真实的可用性缺口**，不是想象的缺口。

### 4.2 方案 A：SQLite `system_config` 表（仅非敏感元数据，secret 仍走环境变量）

**形态**：新增 migration v15 建 `system_config` 表，存 `ai_provider_id` / `ai_model_id` / `ai_base_url` / 各 timeout 与上限；`ai_api_key` 等 secret 仍只从环境变量读。

| 维度 | 评估 |
|---|---|
| secret 静态暴露面 | 不变（secret 不入表） |
| backup 污染 | ⚠️ **provider_id / model_id / base_url 自动进入每一个 backup 归档**。backup 是全库复制，无法选择性排除表。`docs/BACKUP_RESTORE.md` 当前承诺 manifest"不记录 secret"，但库体本身会带上 endpoint 元数据 |
| 迁移代价 | 高：新 migration + `CURRENT_SCHEMA_VERSION` 14→15 + rollback 实现 + rollback 测试。注意 v01–v13 **均无 `rollback()`**，只有 v14 有；治理规则要求 migration"覆盖 rollback 测试"，新表必须补齐 |
| 生效方式 | ⚠️ **仍需重启**，除非同时实现 §4.4 热重载。`AppConfig` 是 frozen dataclass，启动时构造一次 |
| 契约冲突 | ⚠️ 直接冲突。契约 §1.2 明确列出"❌ SQLite 数据库（包括 `config` 表、`settings` 表或任何业务表）"为**排除的持久化路径** |
| 可逆性 | 低。migration 一旦发布并被用户库应用，回退需要再写一个 down migration |

**致命问题**：如果生效仍需重启，那么 UX 收益接近于零 —— 操作员仍要重启，只是把"编辑环境变量"换成"点 UI 保存"。为这点收益支付一次 schema 变更、一次 backup 语义变更和一次契约修订，是明显亏本的交易。

若要拿到 UX 收益，必须同时做热重载 —— 于是方案 A 的真实代价是 A + D 的总和。

### 4.3 方案 B：`data_root/config.json`

**形态**：配置写入 `data_root` 下的 JSON 文件，启动时读取。

| 维度 | 评估 |
|---|---|
| secret 静态暴露面 | 若存 secret：**明文落盘**，任何能读 `data_root` 的进程/用户可读。若不存 secret：与方案 A 同 |
| backup 污染 | ❌ 不进入 backup（backup 只复制 DB + originals + manifest）。这是方案 B 相对 A 的**唯一优势** |
| 迁移代价 | 低：无 migration、无 schema 变更 |
| 生效方式 | 仍需重启（同 §4.2） |
| 契约冲突 | ⚠️ 直接冲突。契约 §1.2 明确列出"❌ `data_root/` 文件系统（包括 `config.json`、`.env`、任何配置文件）" |
| 可逆性 | 高：删文件即回退 |

**问题**：虽不进 backup，但文件与 backup 源目录相邻，操作员手工打包 `data_root` 时会一起带走。且若存明文 secret，比现状的"环境变量"严格更差。

### 4.4 方案 C：运行时热重载（不落盘，仅替换内存配置）

**形态**：新增受控 endpoint，接受配置并替换 `app.state.config`；不写任何持久化载体。进程重启后配置归零。

| 维度 | 评估 |
|---|---|
| secret 静态暴露面 | 无落盘。secret 仅在进程内存中，与现状同级 |
| backup 污染 | 无 |
| 迁移代价 | 无 migration |
| 生效方式 | ✅ 立即生效，无需重启（因 §2.4 的每请求构造特性） |
| 契约冲突 | ⚠️ 冲突。契约 §4.1 明确"❌ 运行时热重载配置（不重启进程）" |
| 可逆性 | 中 |

**真实风险（比看上去大）**：

1. **单请求内的撕裂读取**。多个处理器在一次请求内多次读 `app.state.config`（`api/ai_retrieval_qa.py` 有 37 处引用，`api/study_plans.py` 有 61 处）。若在请求执行中途替换配置，同一请求可能一半用旧 Provider、一半用新 Provider。要正确做，必须引入请求级配置快照，这是跨 13 个 API 模块的改造。
2. **闭包捕获**。`build_task_runner(config)` 把 config 捕获进 handler 闭包（`task_handlers.py:100`）。已构造的 runner 不会看到新配置。
3. **不持久 = UX 陷阱**。用户在 UI 里配好、测试通过、正常使用，进程一重启全部消失且无任何提示。这比"从一开始就要求改环境变量"更容易造成困惑和数据/额度误用。
4. **绕过启动校验**。`startup_preflight.validate_config()` 只在启动路径跑。热重载需要复刻等价校验，否则可注入启动时会被拒绝的配置组合（如 `demo_mode` + 真实 AI 设置）。

### 4.5 方案 D：操作系统凭据存储（Windows Credential Manager / DPAPI）

**形态**：secret 存入 OS 凭据库，非敏感元数据存 SQLite 或 JSON。

**依赖现状（已核实）**：`keyring` 25.7.0 在 `C:\miniconda\py310` 中**可用**，后端为 `keyring.backends.Windows.WinVaultKeyring`；`cryptography` 亦可用。但两者**均未列入 `backend/requirements.txt`**（当前仅 fastapi / pydantic / pypdf / python-docx / python-multipart / pytest / uvicorn 共 7 项）。它们的存在是环境巧合，不是项目依赖。

| 维度 | 评估 |
|---|---|
| secret 静态暴露面 | 加密静态存储，按 Windows 用户隔离。**但同一用户下任何进程可读** —— 对单用户本地应用，这是可接受的隔离级别，且严格优于明文 `.env` |
| backup 污染 | 无（不在 DB、不在 data_root） |
| 迁移代价 | 无 migration；但**新增运行时依赖** + Windows 平台耦合 |
| 生效方式 | 仍需重启（除非叠加 §4.4） |
| 契约冲突 | ⚠️ 部分。契约 §4.1 已把"OS secret source"写入 secret 来源链，方向一致；但 §4.1 同时声明"❌ 配置加密存储或密钥管理服务（KMS）" |
| 可逆性 | 中：删凭据项即回退，但依赖已进 requirements |

**评价**：这是**唯一在安全上真正优于现状**的持久化方案。但它引入平台耦合（项目声明"local single-process"，未声明"Windows-only"）、新增依赖，且在不叠加热重载时仍需重启 —— UX 收益依旧受限。

### 4.6 方案对比汇总

| 方案 | secret 落盘 | backup 污染 | migration | 免重启 | 契约冲突 | 净评价 |
|---|---|---|---|---|---|---|
| 0 现状 | 否 | 无 | 无 | ❌ | 无 | 安全，可用性差 |
| A SQLite | 否（仅元数据） | ⚠️ 有 | ⚠️ v15 + rollback | ❌ | ⚠️ 是 | **代价 > 收益** |
| B data_root JSON | 可选 | 无 | 无 | ❌ | ⚠️ 是 | 收益有限，冲突明确 |
| C 热重载 | 否 | 无 | 无 | ✅ | ⚠️ 是 | 收益真实，改造面跨 13 模块 |
| D OS 凭据库 | 加密 | 无 | 无 | ❌ | ⚠️ 部分 | 安全最优，需新依赖 |

**secret 载体安全排序**（从优到劣）：

```text
环境变量（不持久）
  > OS 凭据库（加密、不进 backup）
  > data_root 明文文件（不进 backup，但与 backup 源相邻）
  > SQLite（明文，且自动进入每个 backup）
```

**SQLite 是 secret 的最差载体**，因为 backup 是全库复制，没有选择性排除机制。这一点直接否决了"把 secret 存进数据库"的任何变体。

## 5. 决策

### 5.1 结论

**本切片不引入任何配置持久化。方案 0 保持不变。**

理由：

1. **方案 A / B 的 UX 收益是幻觉**。在不做热重载的前提下，"UI 保存"与"编辑环境变量"对操作员的实际负担相同（都要重启），却额外支付 schema 变更、backup 语义变更或契约修订。
2. **SQLite 明确不适合承载配置**，因为 backup 全库复制会把配置元数据（乃至将来误加入的 secret）带进每一个归档。这个耦合无法通过代码规范约束，只能通过"不建表"避免。
3. **热重载（方案 C）的收益真实，但改造面跨 13 个 API 模块**（撕裂读取、闭包捕获、启动校验复刻），不属于一个配置切片能安全吸收的范围，需要独立立项与独立契约。
4. **OS 凭据库（方案 D）方向正确但时机未到**：单独引入它不解决重启问题，需要与热重载配套才有完整价值；且需先批准新增运行时依赖与 Windows 平台耦合。

### 5.2 P1-5-1（配置 UI）定型

P1-5-1 采用 **"组装 → 校验 → 导出"** 形态，不含持久化：

**做**：
- 表单收集非敏感元数据（`provider_id` / `model_id` / `base_url` / timeout 与各上限），带客户端范围校验（对齐 `config.py` 的 min/max）
- secret 输入框：`type="password"`、`autocomplete="off"`、`spellcheck="false"`
- "测试连接"按钮调用 P1-5-2 的 `POST /api/system/provider-connection-test` / `POST /api/system/email-connection-test`
- 稳定错误码 → 中文可读提示映射
- **客户端**组装环境变量片段供操作员复制，并明确提示"需重启进程后生效"
- 页面显著位置声明：**测试通过 ≠ 已保存**

**不做**：
- 任何"保存配置"按钮或写入 endpoint
- 任何 localStorage / sessionStorage / cookie / URL 参数写入
- 服务端生成含 secret 的文件或响应

**secret 在 DOM 中的边界（需精确区分）**：
- ✅ 允许：用户自己键入的值留在其键入的 `type=password` 输入框内（不可避免）
- ❌ 禁止：服务端在任何响应中回显 secret
- ❌ 禁止：把 secret 写入非 password 元素、`value` 属性快照、`data-*`、HTML 注释、错误提示文本
- ❌ 禁止：把 secret 写入任何 storage 或 URL
- 要求：导航离开或提交后清空输入框

环境变量片段必须由前端从用户刚键入的内容拼装，**不得**由服务端返回。

### 5.3 未来切片的前置条件

| 未来能力 | 前置条件 |
|---|---|
| 配置持久化（任何载体） | 先完成热重载设计与契约冻结；否则收益不成立 |
| 热重载（方案 C） | 独立立项：请求级配置快照设计、闭包捕获处理、启动校验复刻、撕裂读取测试 |
| OS 凭据库（方案 D） | 显式批准新增 `keyring` 运行时依赖 + 接受 Windows 平台耦合 + 定义 backup/restore 语义 |
| SQLite 配置表（方案 A） | **不推荐**。若仍要推进，须先解决 backup 选择性排除，否则配置元数据将永久混入归档 |

### 5.4 契约状态

P1-5-0 契约 **无需修改**。本决策与契约 §1.2、§4.1 完全一致：

- §1.2 排除 SQLite / data_root / 浏览器存储 → 维持
- §4.1 runtime-only 原则、"配置变更需重启进程"、"不支持热重载" → 维持

契约 §4.2 建议后续补正：secret 字段实际为 8 个而非 5 个（见 §2.2）。该差异不影响任何安全属性，属文档完备性问题，记录于此不单独立项。

## 6. 治理测试

`backend/tests/test_p1_5_3_persistence.py` 将本决策转为可执行断言：

| 测试 | 断言内容 |
|---|---|
| `test_no_config_or_settings_table_in_migrations` | 全部 migration 未创建 `config` / `settings` / `secret` / `credential` 类系统配置表 |
| `test_config_is_loaded_from_environment_only` | `config.py` 不含文件读取调用（`open` / `read_text` / `read_bytes`） |
| `test_no_dotenv_loader_in_production_code` | `backend/app/` 无 `dotenv` / `load_dotenv` 引用 |
| `test_appconfig_remains_frozen` | `AppConfig` 保持 `frozen=True` |
| `test_all_secret_fields_have_repr_false` | 8 个 secret / 隐私字段全部 `repr=False` |
| `test_backup_does_not_copy_arbitrary_data_root_files` | backup 只复制 DB、originals、manifest |
| `test_no_config_write_endpoint_exists` | 无 provider-config / email-config 写入路由 |
| `test_evaluation_document_records_decision` | 本文档存在且记录决策 |

## 7. 未验证边界

- ❌ 未评估多用户 / 多进程 / 共享 `data_root` 下的配置语义（项目边界之外）
- ❌ 未评估配置版本管理、审计追踪、回滚（契约 §4.1 已排除）
- ❌ 未实测热重载的撕裂读取实际影响（仅静态分析引用计数）
- ❌ 未测试 `keyring` 在非 Windows 平台或无凭据库环境的行为
- ❌ 未评估操作员环境变量本身的安全性（属操作系统与操作习惯范畴）

## 8. 证据声明

- **评估完成日期**：2026-01-09
- **评估性质**：静态代码审计 + 方案对比，**无生产代码变更**
- **核实范围**：`config.py`、`app_factory.py`、`lifespan.py`、`startup_preflight.py`、`backup.py`、`diagnostics.py`、`task_handlers.py`、`providers/_registry.py`、14 个 migration、13 个 API 模块、`backend/requirements.txt`、`backend/scripts/*.ps1`、`.env.example`、`.gitignore`
- **决策**：不引入持久化；P1-5-1 采用"组装 → 校验 → 导出"形态
- **契约影响**：无（与 P1-5-0 一致）
- **schema 影响**：无（维持 v14）
