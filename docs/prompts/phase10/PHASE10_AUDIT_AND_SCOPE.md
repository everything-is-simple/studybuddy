# Phase 10-0 审计与上线范围冻结

> 状态：`planned/audit-draft`（Gate A：通过）  
> 审计对象：StudyBuddy 当前 `master`，schema v12   
> 审计日期：2026-08-30  
> 审计原则：本文件是 Phase 10 的范围与上线定义证据，不是 Phase 10 实现证据。

## 1. 审计结论

### 1.1 本次 Phase 10 的上线目标：Go

本次批准推进的上线目标是：

> **StudyBuddy 本地单机 v1**：在 Windows 本地机器上，以单进程、单实例、SQLite、本地磁盘和本地浏览器运行，支持材料管理、已完成范围内的 AI/学习工作流、显式任务操作、备份、验证、恢复、重启和升级。

这个目标与当前架构边界一致，不要求先完成多用户互联网服务，也不要求所有真实 Provider、OCR/ASR 和外部交付渠道都通过。

### 1.2 以下目标：No-Go / 不属于本次上线声明

以下能力不作为本次 Phase 10 本地 v1 的隐含前置，也不能从本次结果推断支持：

- 多用户、认证、授权和跨用户数据隔离；
- 多 worker、多进程、多实例共享同一个 `data_root`；
- 云同步、外部存储、协作和互联网 SaaS 部署；
- 真实断电、硬件损坏、网络文件系统和所有资源耗尽场景的可靠恢复；
- 所有 Provider/model 的通用 `real-pass`；
- 真实 OCR/ASR provider 的通用可用性；
- SMTP/飞书等真实生产外发；
- 自动 scheduler、自动定时推送和无限容量承诺；
- 全局 production `real-pass`。

如未来需要其中任何能力，必须另立部署/安全/数据模型范围，不能在 Phase 10 子任务中顺手引入。

### 1.3 Gate A 判定

| 条件 | 结论 | 审计依据 |
|---|---|---|
| 上线对象明确 | 通过 | local single-process / single-instance v1 |
| 已实现能力和未实现能力可区分 | 通过 | 本文件第 3 节矩阵 |
| 数据目录、备份与恢复责任可定义 | 通过 | `backend/app/backup.py`、`docs/BACKUP_RESTORE.md` |
| 安全与隐私边界可冻结 | 通过 | `docs/ARCHITECTURE.md`、`docs/CODE_TEST_GOVERNANCE.md`、现有脱敏测试 |
| Phase 10 的实现边界可拆分 | 通过 | `00_MASTER_PLAN_PROMPT.md`、`EXECUTION_ORDER_AND_GATES.md` |
| 是否允许开始 10-1 | **允许** | 10-0 Gate A 通过 |

## 2. 审计范围与方法

### 2.1 已读取的治理和设计文档

- `AGENTS.md`
- `docs/PHASE_ROADMAP.md`
- `docs/STATUS.md`
- `docs/TODO.md`
- `docs/PROJECT_PROGRESS_REPORT.md`
- `docs/ARCHITECTURE.md`
- `docs/CODE_TEST_GOVERNANCE.md`
- `docs/MIGRATIONS.md`
- `docs/BACKUP_RESTORE.md`
- `docs/ai-learning-architecture.md`
- `docs/prompts/phase9d/` 相关审计、契约、执行顺序和 evidence
- `docs/prompts/phase10/00_COMMON_CONTEXT.md`
- `docs/prompts/phase10/00_MASTER_PLAN_PROMPT.md`
- `docs/prompts/phase10/10-0_上线定义_现状审计与范围冻结.md`

### 2.2 已审计的正式代码和测试

- 启动与 API：`backend/app/main.py:create_app`、`backend/app/main.py:lifespan`
- 配置：`backend/app/config.py:AppConfig`、`config_from_environment`
- 启动预检：`backend/app/startup_preflight.py:preflight`
- 数据库：`backend/app/repository.py:connect`
- migration：`backend/app/migrations/runner.py:migrate`、`_MIGRATIONS`
- 存储：`backend/app/storage.py`
- 启动恢复：`backend/app/recovery.py:reconcile`
- 数据库审计：`backend/app/db_audit.py:run_audit`
- 可观察性：`backend/app/observability.py`
- 备份恢复：`backend/app/backup.py`、`backend/app/restore_acceptance.py`
- Operator CLI：`backend/app/__main__.py`、`backend/app/cli.py:main`
- 测试入口：`backend/scripts/test-backend.ps1`、`backend/scripts/test-browser.ps1`
- 正式测试目录：`backend/tests/`，当前共 83 个 Python 测试文件和 20 个 Chromium spec 文件

### 2.3 本轮可复现测试

执行命令：

```powershell
C:\miniconda\py310\python.exe -m pytest backend/tests/ -q -p no:cacheprovider
```

结果：

```text
361 passed, 2 skipped in 115.42s
```

skip 原因：`backend/tests/test_real_provider_smoke.py` 中的 opt-in real-provider smoke 默认关闭。本任务没有修改生产代码，因此没有另行运行 Chromium；既有浏览器基线和范围见 `docs/STATUS.md`、`docs/PHASE9D_ACCEPTANCE_EVIDENCE.md`。

## 3. 当前能力矩阵

### 3.1 可以纳入本地 v1 上线基线的能力

| 领域 | 当前事实 | 证据/入口 | Phase 10 处理 |
|---|---|---|---|
| Web 入口 | FastAPI `create_app`，默认绑定方式由运行命令控制 | `backend/app/main.py:create_app`、README 启动命令 | 10-7 固化安全启动方式 |
| 启动生命周期 | preflight → migration/connect → audit → recovery → ready；未 ready 的 health 返回 503 | `main.py:lifespan`、`startup_preflight.py`、`test_startup_preflight.py` | 10-5/10-7 复核和增强 |
| 数据库 | SQLite，当前 schema v12，migration history 与 `PRAGMA user_version` 受 runner 管理 | `migrations/runner.py`、`docs/MIGRATIONS.md` | 10-2 定义 task schema 兼容 |
| 原文件 | hash-derived originals、containment、regular-file/symlink/hash 校验、生命周期保护 | `storage.py`、`recovery.py`、storage/lifecycle tests | 保持不变量，纳入 10-9 演练 |
| 材料管理 | 导入、批量/文件夹导入、列表、搜索、回收站、恢复、purge、导出 | `main.py` materials routes、相关 Chromium specs | 作为 release smoke 主路径 |
| Q&A/retrieval | lexical/vector/hybrid、citation、Q&A history、显式 indexing 和安全错误 | `repository.py`、`main.py`、`test_qa_api.py` 等 | 10-4 只在批准后接入长任务 |
| Cards/Exercises | fake-provider 范围内 draft、确认、复习、作答、grading、source lifecycle | Phase 8 tests/evidence | 作为已批准学习路径验收 |
| 9A–9D | 9A/9B/9C 限定范围完成；9D 为部分立项范围 scoped closeout | 各 Phase acceptance evidence | 只纳入已明确完成的范围 |
| Provider | fake/default 和部分精确真实 provider evidence；provider 可未配置而启动 | `config.py`、`providers.py`、P6-E evidence | 10-4 保持 provider 可选与精确 gate |
| 备份 | SQLite Online Backup、original snapshot、manifest、hash/integrity/schema 检查 | `backup.py`、`BACKUP_RESTORE.md` | 10-6 做运维闭环复核 |
| 恢复 | 仅恢复到不存在或空目标，显式 `--confirm`，恢复后可离线/在线验收 | `backup.py:restore_backup`、`restore_acceptance.py` | 10-6/10-9 必须保留 |
| 基础可观察性 | 安全 event、request ID、process-local metrics、liveness/readiness/health | `observability.py`、`main.py`、`test_observability.py` | 10-5 扩展 task correlation |
| Operator CLI | backup、verify-backup、restore、schema-version、verify-restored-data | `cli.py:main` | 10-6/10-7 补 runbook 和发布入口 |

### 3.2 当前已实现但不能扩大声明的能力

- Phase 7 的真实 embedding 证据只适用于精确的 Mistral provider/model/gateway 组合；不能扩展为所有 embedding provider。
- DeepSeek `deepseek-chat` 和 Agnes `agnes-2.5-flash` 的真实证据只适用于各自精确配置和 synthetic/local gate。
- Phase 8 Cards/Exercises 真实 Provider generation 尚无通用 evidence。
- Phase 9D 的 OCR/ASR 是 deterministic fake/loopback；真实 OCR/ASR 不在批准范围。
- Phase 9D delivery 是默认关闭的 allowlisted local dry-run；live delivery 仍被固定拒绝。
- 现有浏览器测试通过代表局部 Chromium 用户路径通过，不代表系统级 screen reader、真实离线、极端长内容或长时稳定性通过。

### 3.3 Phase 10 开始时明确缺失的能力

| 缺口 | 当前审计结论 | 对上线的影响 |
|---|---|---|
| 统一 task/operation contract | 未实现；已有 `ai_operations` 是按业务演进的同步操作记录 | 10-1/10-2 阻塞后台化 |
| 后台 runner | 未实现；当前 Q&A/indexing 等主要由请求同步执行 | 10-3 阻塞需要长任务的正式接入 |
| 任务 progress/retry/cancel/restart recovery | 未形成统一实现；部分 operation 有局部 retry/stale 语义 | 10-1/10-3 必须先冻结准确语义 |
| 任务扫描和 lease recovery | 没有独立后台扫描；已有部分请求触发 stale reclaim | 不得宣称长任务恢复已完成 |
| 备份保留/轮换自动化 | 当前 CLI 支持显式 backup/verify/restore；自动保留轮换不是已验证的产品能力 | 10-6 需要明确手工 v1 或实现 operator 工具 |
| restore drill 固化 | 有 restore acceptance 和 runbook 资料，但 Phase 10 需形成 release evidence | 10-6/10-9 阻塞收口 |
| corruption/read-only 策略 | 当前 audit/recovery 偏诊断和保守处理；没有完整统一 quarantine/read-only operator 模式 | 10-6 必须选择停机、只读或隔离策略 |
| 安装/发布包 | 当前是源码 + Python/uvicorn + PowerShell 命令，没有正式安装器/发布包 | 10-7 必须先定义 v1 发布方式 |
| 单实例锁 | 当前支持边界禁止多实例共享 `data_root`，但正式发布锁/重复实例体验仍待验证 | 10-7 必须处理 |
| 容量/故障证据 | I4 已完成 S0–S3 和 40-cycle smoke；ACL、磁盘耗尽、S4、peak memory、断电等仍 `not_verified` | 10-8 时间盒验收，不可扩大声明 |
| 生产级 tracing/metrics | 当前 metrics 为进程内低基数 snapshot，operation correlation 仍有限 | 10-5 补 task correlation；不承诺跨进程聚合 |

## 4. 已冻结的本地 v1 上线定义

### 4.1 目标用户和运行模型

- 目标用户：单一本地使用者；本地浏览器访问本机 StudyBuddy。
- 运行主机：本轮只承诺当前已验证的 Windows + Python 3.10 运行环境；其它平台不从源码可运行推断为受支持。
- 服务：单进程、单实例、单一 `data_root`；默认只监听本机地址，不能部署为共享网络服务。
- 存储：SQLite 数据库与 `data_root/originals/` 本地磁盘；数据目录由用户负责保护和备份。
- 浏览器：Chromium 路径是当前正式验收路径；其它浏览器不自动视为通过。
- Provider：未配置时应用仍可启动；fake/demo 和精确真实 provider 必须通过显式配置区分。

### 4.2 启动、停止和升级责任

- 启动必须先通过配置和 storage topology preflight，再完成 migration、audit、recovery，最后才进入 ready。
- 停止必须不破坏已提交数据；运行中的未来 task 必须根据冻结后的 task contract 进入可诊断状态。
- 升级前必须停止服务、创建并验证 backup，再执行 migration 和升级后验收；失败时保留失败数据库和 backup，不覆盖 live data。
- 本次不承诺自动 down migration；恢复路径是 verified backup → 新空 target → restore acceptance。
- 应用启动不自动 backup、restore、repair、rebuild、生成 AI/OCR/ASR 内容或发送报告。

### 4.3 数据保留和删除责任

- 默认不自动删除用户材料、学习事实、历史回答、attempt、报告快照或审计记录。
- soft delete、restore、purge 继续遵守各领域已有显式操作和 source lifecycle；purge 是不可逆动作。
- backup retention/rotation 在 10-6 明确前，采用显式 operator 管理，不宣称自动保留策略已存在。
- 用户必须自行保证 live data root 和 backup 位置的访问控制、磁盘空间和备份保管；系统不把 backup 放入 live data root。
- 任何未来自动清理必须独立定义对象、保留期限、确认方式、审计和恢复影响，不能由 task runner 隐式执行。

### 4.4 本地 v1 上线最低用户路径

release candidate 至少必须在隔离 data root 验证：

```text
安全配置
→ 启动
→ liveness/readiness/health
→ 导入 TXT/Markdown 等已支持材料
→ 材料列表/搜索/详情/导出
→ 显式 indexing（及批准的任务状态路径）
→ fake-provider Q&A/citation
→ 已批准的 Cards/Exercises/9A–9D 学习路径
→ 失败/重试/重启后的安全状态
→ backup
→ verify-backup
→ restore 到全新空目录
→ verify-restored-data
→ 重启恢复后的读取和导出
→ schema/version 诊断
→ 停止
```

### 4.5 上线阻塞等级

**P0：绝对阻塞**

- 数据损坏、跨项目越权、源引用伪造、secret/正文/路径泄露；
- migration/history/user_version 不一致或 backup/restore 不能保留数据；
- 任务重复副作用、终态被覆盖、恢复后伪造成功；
- readiness 在必要启动步骤失败时仍报告 healthy；
- release candidate 无法完成新空目录恢复或无法安全停止/重启。

**P1：本地 v1 默认阻塞，除非 10-0 明确接受并记录**

- 关键用户路径不可用；
- runner 的 progress/retry/cancel/lease 语义无法诊断；
- 升级、备份、恢复或失败操作没有可执行 operator 步骤；
- 单实例冲突会破坏数据或启动状态；
- 发布方式不能在干净环境复现。

**P2：可在声明限制内接受**

- 未验证的真实断电、网络盘、硬件损坏、真实磁盘耗尽、极限容量；
- 未覆盖的 provider/model/OCR/ASR/外发真实组合；
- 系统级辅助技术、极端长回答和长时整批稳定性；
- 不影响已冻结本地路径的体验改进。

所有 P2 必须记录为 `not_verified`，不能写成通过。

## 5. Phase 10 实施范围冻结

### 5.1 必须完成的范围

1. 统一 operation/task 契约和状态机；
2. 最小 migration/schema 和 v12 升级兼容；
3. 单进程 runner、lease、progress、retry、cooperative cancel、stale/restart recovery；
4. 只接入经审计批准的必要长任务，保持现有同步 API 或提供明确兼容层；
5. task/request/operation correlation、脱敏 logging、metrics、readiness/degraded；
6. backup/verify/restore、migration upgrade、retention/rotation 决策、restore drill、corruption 处理；
7. 安全配置、单实例运行、启动/停止、版本和本地发布方式；
8. 容量、性能、长时 smoke 和已声明故障边界证据；
9. release candidate 全路径、正式 evidence、状态和 operator 文档收口。

### 5.2 明确不做

- 不把所有同步 endpoint 一次性异步化；
- 不引入共享 data_root 的多进程/多 worker 协议；
- 不做用户账户、认证、授权、云同步、协作；
- 不实现真实 OCR/ASR 或真实 SMTP/飞书生产发送；
- 不实现自动 scheduler/定时推送；
- 不引入外部 vector database；
- 不在 restore/startup 中自动 repair/rebuild/run task/send；
- 不用 fake、loopback、benchmark 或局部 browser pass 代替真实生产证据；
- 不把“后台任务实现”解释成“跨进程故障恢复已实现”。

## 6. 后续任务阻塞关系

- **10-1**：可开始；必须把现有 `ai_operations` 的兼容关系和 task contract 冻结清楚。
- **10-2**：必须等待 10-1 contract；任何 schema 变更只能通过 migration runner。
- **10-3**：必须等待 10-2；runner 先做通用生命周期和恢复，不接入全部业务。
- **10-4**：必须等待 10-3；逐项批准 indexing/embedding/generation/OCR/ASR/report 操作。
- **10-5**：可在 10-3 后实施，但 task correlation 字段必须服从 10-1。
- **10-6/10-7/10-8**：可在核心 runner 稳定后执行，均阻塞 10-9。
- **10-9**：必须等 Gate A-I 通过、所有 P0/P1 关闭或正式接受。

发现以下情况必须停工并回到范围评审：需要多用户/云同步/共享 data_root；需要真实外发；需要强制取消不可中断的外部 HTTP；需要破坏既有 source/user-state 不变量；需要修改已确认的领域状态机但没有契约变更记录。

## 7. 准确状态措辞

本任务完成后只能使用：

> Phase 10-0 已完成上线定义、现状审计和范围冻结；Gate A 通过，批准以 local single-process / single-instance / SQLite / local-disk v1 为目标继续执行 10-1。Phase 10 尚未实现，StudyBuddy 尚未完成生产化或上线。

不能使用：

- “Phase 10 已完成”；
- “StudyBuddy 已成功上线”；
- “production-ready”；
- “支持多用户、多 worker、云同步或全局 real-pass”。

## 8. 10-0 交付与推荐提交

- 审计产物：本文件；
- 规划索引：`docs/prompts/phase10/README.md`、`EXECUTION_ORDER_AND_GATES.md`；
- 同步事实源：`docs/TODO.md`、`docs/STATUS.md`、`docs/PHASE_ROADMAP.md`、`docs/PROJECT_PROGRESS_REPORT.md`、`docs/INDEX.md`、必要时 `README.md`；
- 生产代码：本任务不修改；
- migration：本任务不新增；
- 测试：使用现有完整 backend 基线，不新增业务测试；
- 推荐提交：`docs: define local v1 launch scope and phase 10 gates`。

## 9. Gate A 结论

**Gate A：通过（scoped go）**。

批准范围：本地单进程 v1 的生产化和上线收口。  
未批准范围：多用户、多进程共享、云同步、真实 OCR/ASR、真实外发、自动定时推送和全局 production real-pass。  
下一步：执行 `docs/prompts/phase10/10-1_operation_task_契约与状态机.md`。
