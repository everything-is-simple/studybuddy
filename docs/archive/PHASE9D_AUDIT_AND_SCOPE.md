# Phase 9D 现状审计与范围冻结（9D-0 产物）

> 状态：`planned/audit-draft`。本文件是 9D-0 的审计与立项评审产物，不代表 S6/S7 领域能力实现。所有结论以当前源码为准，引用源码路径、函数名或测试名；历史项目 s6/s7、ocr-tools、report/delivery 只作为需求线索，不计入现状能力。

## 0. 任务边界

本任务只做立项评审（go / no-go）、现状审计和范围冻结。不新增 backend/app 代码、不加 migration、不改 tests、不改 README/STATUS/TODO。允许新增/修改的仅为 `docs/prompts/phase9d/` 审计文档。

---

## 1. 现状审计（源码事实）

### 1.1 Schema / 版本

- 当前正式 schema version 为 **v11**，常量 `CURRENT_SCHEMA_VERSION = 11`（`backend/app/migrations/runner.py:8`）。
- migration 注册表 `_MIGRATIONS`（`runner.py:941`）连续到 11：
  - `(7, "phase8_cards_exercises_schema", _migration_v7)`（`runner.py:948`）
  - `(8, "phase8_exercise_provenance", _migration_v8)`（`runner.py:949`）
  - `(9, "phase9a_learning_plan_schema", _migration_v9)`（`runner.py:950`）
  - `(10, "phase9b_material_learning_schema", _migration_v10)`（`runner.py:951`）
  - `(11, "phase9c_exercise_feedback_schema", _migration_v11)`（`runner.py:952`）
- migration runner 是唯一 schema 入口：`schema_migrations` 与 `PRAGMA user_version` 一致性由 `runner.py` 的 apply/verify 段维护（`runner.py:970`、`993-1008`、`1021-1051`）。业务表统一在编号 migration 内建，无运行时旁路建表（`schema_migrations` 的 `CREATE TABLE IF NOT EXISTS` 在 `runner.py:44`，属基础设施表非业务表）。
- 下一个连续版本应为 **v12**（9D-2 使用，命名建议 `phase9d_extended_learning_schema`）。

### 1.2 hash-derived originals 存储与 material lifecycle

- 原件按内容 hash 存储：`store_original`（`backend/app/storage.py:19`）用 `content_hash[:2]` / `content_hash[2:]` 双层目录、atomic replace，`sha256_file`（`storage.py:84`）校验；原件名与 hash 有严格校验（`storage.py:24-27`），命中已存在原件时复用（`storage.py:61-63`）。
- material lifecycle 覆盖 active / deleted / restored / purged，见 `test_lifecycle_invariants.py`、`test_lifecycle_original_races.py` 与前端 `#delete`/`#restore`/`#purge` 按钮（`main.py` INDEX_HTML `#management`）。原件下载走安全路径校验（`main.py:2358` FileResponse，`_safe_original` 在 `restore_acceptance.py:37`）。
- 结论：**采集原件（音频/图片）应直接复用既有 hash-derived originals + material lifecycle，不新建平行原件体系。**

### 1.3 material_revisions / chunks / chunk_spans 摄取与 retrieval / citation 管线

- schema：`material_revisions`（`runner.py:241`）、`chunks`（`runner.py:254`）、`chunk_spans`（`runner.py:276`）、FTS5 `chunks_search`（`runner.py:283`）、`embeddings`（`runner.py:285`、v6 重建于 `runner.py:432`）、`retrieval_runs`/`retrieval_hits`（`runner.py:302`/`315`）、`qa_citations`（`runner.py:329`）。
- 摄取/检索/引用逻辑：`backend/app/chunking.py`、`embedding.py`，retrieval/context/citation 见 `test_retrieval.py`、`test_context_assembler.py`、`test_ai_citation_lifecycle.py`。lexical/vector/hybrid 检索与 fallback 由前端 `#qa-retrieval-mode` / `#qa-allow-fallback` 暴露（INDEX_HTML）。
- source unavailable/stale 契约见 `test_ai_citation_lifecycle.py` 与 9A/9B/9C source_lifecycle 测试。
- 结论：**S7 转写文本应作为 material/revision 接入既有摄取管线，复用现有 retrieval/citation 与 source-unavailable/stale 契约。**

### 1.4 provider registry / ai_operations / fake provider / 幂等 / 安全错误

- provider 常量与实现：`PROVIDER_NOT_CONFIGURED = "provider_not_configured"`、`FAKE_PROVIDER_ID = "fake"`、`FAKE_MODEL_ID = "fake-studybuddy-v1"`（`backend/app/providers.py:43-45`）。
- `FakeLLMProvider`（`providers.py:90`）为 deterministic；`OpenAICompatibleLLMProvider`（`providers.py:174`）走真实 HTTP；`ProviderRegistry`（`providers.py:500`）按配置解析，fake 走 `runtime_kind="deterministic_demo"`（`providers.py:559`）。
- embedding 侧：`OpenAICompatibleEmbeddingProvider`（`providers.py:357`）、`EmbeddingProviderRegistry`（`providers.py:442`）。
- ai_operations 与幂等：`ai_operations` 表（`runner.py:344`），generation 的 idempotency 处理在 `repository.py:802-820`（key 命中 replay / mismatch raise `generation_idempotency_key_mismatch`）。practice 侧幂等 `practice_submission_idempotency_mismatch`（`repository.py:1406`）。
- 安全错误：HTTP 层统一 `HTTPException(status_code=..., detail=<code>)`，detail 只用稳定 code（如 `main.py:479` `invalid_filename`、`496` `file_too_large`、`522` `material_persist_failed`），不泄露路径/SQL/traceback。
- 结论：**S7 OCR/ASR 转写应复用 ai_operations + provider registry + 幂等模式，默认 fake/loopback provider，raw response 不持久化；真实 OCR/ASR 以显式 gate 接入。**

### 1.5 9A/9B/9C 可聚合的派生事实（S6 报告数据源）

- 9A（v9，`_migration_v9`，`runner.py:565-687`）：`learning_goals`、`knowledge_modules`、`study_plans`、`study_plan_items`、`study_plan_dependencies`、`study_progress_events`（append-only 进度）、`module_source_links`、`plan_item_source_links`。测试 `test_phase9a_domain.py`、`test_phase9a_api.py`。
- 9B（v10，`_migration_v10`，`runner.py:701-784`）：`notes`、`note_blocks`、`note_module_links`、`note_block_source_links`、`rhythm_settings`、`rhythm_allocations`。测试 `test_phase9b_domain.py`、`test_phase9b_rhythm.py`、`test_phase9b_notes.py`。
- 9C（v11，`_migration_v11`，`runner.py:798-904+`）：`cram_goals`、`practice_sessions`、`practice_session_items`、`exercise_attempt_reviews`、`mistake_cases`、`mistake_occurrences`、`mistake_feedback_events`；复用 Phase 8 `exercise_attempts`（`runner.py:534`）。测试 `test_phase9c_domain.py`、`test_phase9c_api.py`。
- 结论：**S6 报告只读聚合的候选数据源为上述计划/进度/练习/错题/薄弱点派生事实；报告不得改写这些事实，且必须脱敏（下节 non-goals）。**

### 1.6 导出 / backup / verify / restore / restore_acceptance

- 导出：`main.py:653` `/api/materials/export`（原文件/正文/bundle），前端 `#batch-export`。`test_material_export.py`。
- backup：`backup_data`（`backup.py:166`）、`verify_backup`（`backup.py:264`）、`restore_backup`（`backup.py:311`，`confirm` 参数），含 `_referenced_hashes`、`_validate_layout`、`_rebase_restored_material_paths`。`test_backup_restore.py`、`test_ai_backup_restore.py`。
- restore 只读验收：`restore_acceptance.py` 的 `_check_database`（`:63`，integrity/foreign_key check）、`_study_checks`（`:92`，required_tables 存在性与计数）、9C 专项检查（`:186-226`，`phase9c_source_statuses`/`phase9c_session_statuses`/session scope/attempt link/review link），`_offline`（`:239`）、`_online`（`:301`）、`verify_restored_data`（`:334`）。restore 走新空目录、non-repair。9A/9B/9C 各有 `test_phase9X_backup_restore.py`。
- 结论：**9D 需扩展 restore_acceptance 的只读 v12 checks，并保证 restore/startup/read/verify 不触发 OCR/ASR、不重算并外发报告、不触发任何交付。**

### 1.7 前端结构

- 单文件内嵌前端 `INDEX_HTML`（`main.py:2476`），由 `GET /`（`main.py:2469`）返回。已有分区导航：`#materials`、`#qa`、`#study`（卡片与练习）、`#phase9c`（练习反馈）、`#plans`（学习计划）、`#notes`（资料笔记）。样式含 `@media(max-width:700px)` 窄屏适配和 focus-visible 可访问性。
- 结论：**9D UI 应作为新的分区接入既有 INDEX_HTML 与导航模式，复用现有窄屏/键盘/toast/dialog 约定。**

### 1.8 当前对外网络交付路径

- 仅有的出站 HTTP 是 provider/embedding 调用：`providers.py` 用 `urllib.request`（`_request_json` `providers.py:254-257`、`_request_json_with_limit` `providers.py:413-416`），目标是配置的 `base_url`（`config.py` `ai_base_url`/`embedding_base_url`，`_valid_base_url` 校验于 `config.py:86`）。
- **不存在任何 SMTP、飞书 webhook 或面向家长的外发路径。** 全仓库未发现 `smtplib`/`feishu`/`webhook`（9D-0 扫描）。
- provider secret 只经环境变量读取，`ai_api_key`/`embedding_api_key` 用 `field(repr=False)`（`config.py:33`、`42`）避免 repr 泄露；不入库、不进日志。
- 结论：**S6 对外交付是全新的、仓库此前刻意回避的出站路径；引入时必须默认关闭、显式授权、白名单、可审计，secret 复用「配置读取、不入库、不入日志、不入 backup 明文」模式。**

---

## 2. 立项评审（go / no-go）

Phase 9D 是条件性阶段。以下按五个立项条件评审，不因历史版本存在 s6/s7 就自动判定立项。

| 立项条件 | 评估 | 结论 |
|---|---|---|
| 真实需求 | S7 课堂采集→转写→成为 S2 资料来源，与既有 material/revision/retrieval 管线自然衔接，需求链清晰且可复用现有基础设施。S6 家长报告是历史前辈版本的既定场景（HISTORICAL_SCENARIO_REVIEW S6/S7），但当前正式系统无任何家长/多用户视图，需求真实性偏弱且依赖外发。 | S7 需求成立；S6 需求存在但优先级和形态需更明确 |
| 隐私边界 | S7 引入敏感原件（可能含未成年人语音/影像），但可完全纳入既有 originals/material lifecycle 与隐私响应约定。S6 是只读聚合，边界可用白名单/黑名单严格定义；但外发把数据送往第三方、接收方可能涉及未成年人，是全仓库最高隐私风险点。 | S7 隐私可控；S6 报告聚合可控，但**外发是高风险**，须默认关闭 + 授权 + 白名单 + 审计 |
| 数据保留策略 | 采集原件、转写、报告快照、交付审计的保留与清理需在 9D-1 明确；当前 backup/restore 与 lifecycle 已有可复用范式，可承接。 | 可在 9D-1 冻结；非阻塞 |
| 真实 OCR/ASR/交付组件可验证证据 | 当前仓库**没有**任何真实 OCR/ASR 组件，也没有 SMTP/飞书交付组件或其 smoke 证据。按 AGENTS.md 与 TODO 9D 规则，真实组件须先在 Composer/Integration 验证再由正式系统重实现。 | **真实组件证据缺失**：真实 OCR/ASR 与真实外发不能进入默认交付范围 |
| 运维成本 | 默认 fake/loopback + dry-run 路径运维成本低，落在既有单进程/SQLite/本地边界内。真实 OCR/ASR（外部 API、成本、失败率）与真实外发（SMTP/飞书凭证、送达、退信、合规）运维成本显著且未评估。 | 默认范围成本可控；真实组件成本未评估 |

### 立项结论

**部分立项（conditional go），并对默认交付范围做强约束：**

1. **立项 S7 与 S6 的「本地可重复、无真实外发」范围**：
   - S7 采集/转写/接入以 deterministic fake/loopback OCR/ASR 为默认可重复路径；
   - S6 报告聚合/脱敏/预览/导出，以及交付层的**本地可审计 dry-run**；
   - 全部落在 deterministic fake/loopback、单进程、SQLite、本地 Chromium、backup/restore、dry-run 交付的已验证边界内。

2. **不立项（暂缓）真实外部组件，直至独立评审通过**：
   - 真实 OCR/ASR provider 的通用接入与验证；
   - 真实对外交付（SMTP / 飞书生产端点）；
   - 二者均须先在 Composer/Integration 验证组件、评审隐私/保留/成本后，再以显式 opt-in gate 接入，且**不得默认启用、不得宣称通用 real-pass**。

3. **理由**：五条件中「真实组件证据」不满足、「S6 外发隐私」为最高风险、「真实组件运维成本」未评估。按 9D-0 允许「仅立项可验证部分」的规则，采用部分立项而非全量立项，既推进可复用价值，又不把未评审的高风险外发/真实识别塞进默认范围。

> 若后续用户明确要求且完成真实组件评审，可在不改变本文件其余边界的前提下，将真实 OCR/ASR 或真实外发从「暂缓」提升为「显式 gate 内实现」，并在 9D-11 如实记录范围扩展。

---

## 3. S7 课堂采集：范围冻结

- **用户价值**：把课堂录音/板书图片转成可检索、可引用的资料，接入既有 S2 note/module/retrieval 能力。
- **依赖**：hash-derived originals（`storage.py`）、material/revision/chunk 摄取（`chunking.py`）、provider registry/ai_operations（`providers.py`/`repository.py`）、source lifecycle。
- **默认范围（立项）**：capture session 生命周期、原件上传纳入 originals、deterministic fake/loopback OCR/ASR 转写、置信度与 uncertain 标注、转写作为 material/revision 接入并保留 citation、draft→confirm/reject/archive、source lifecycle 降级。
- **隐私/运维风险**：敏感原件（可能含未成年人）；低置信/乱码；真实 OCR/ASR 的成本与失败率。
- **non-goals**：真实 OCR/ASR 通用验证（仅显式 gate）、平行正文体系、后台自动扫描/worker、视频流处理、TTS。

## 4. S6 家长观察：范围冻结

- **用户价值**：家长/监护人获得脱敏的学习进度聚合（日/周/月/考前提醒），不接触原文、答案、聊天。
- **依赖**：9A 计划/进度、9B note/rhythm、9C practice/mistake/weak-point 派生事实；导出范式；（交付层）全新出站路径。
- **默认范围（立项）**：只读报告聚合、强制脱敏、报告状态机、本地生成/预览/导出、交付层默认关闭且只走可审计 dry-run（授权 + 白名单 + 审计骨架）。
- **隐私/运维风险**：外发把数据送往第三方、接收方可能涉及未成年人（最高风险）；报告若脱敏不严会泄露答案/原文/路径；真实外发的凭证、送达、合规成本。
- **non-goals（默认范围外，须独立评审）**：真实 SMTP/飞书发送、自动定时推送/提醒、scheduler/worker、多用户/家长账号体系、报告写回学习事实、把原文/答案 key/Q&A 原文/路径带入报告。

## 5. 明确不当作现状能力

以下均**不是**当前正式系统能力，不得据历史存在而视为已实现：历史项目 s6/s7 与 ocr-tools、真实 OCR/ASR、真实 SMTP/飞书交付、自动定时推送、scheduler/worker/queue、多用户/认证/云同步、Phase 10 后台任务、外部 vector DB。

---

## 6. 交给 9D-1 决定的未决问题清单

1. **采集原件边界**：允许的音频/图片类型与大小上限；capture session 与 material 的 1:1 还是 1:N；原件是否始终经 material 导入路径还是新增采集专用入口。
2. **转写置信度语义**：置信度取值范围与阈值；`uncertain`/low-confidence 的判定与展示；乱码/空转写/超时的稳定表达；真实 vs fake provider 的置信度可比性。
3. **转写接入 S2 的方式**：新建 material 还是新 revision；citation_key 生成与 source 校验；draft→confirm 的状态机；用户编辑保护如何与既有 note/module 契约衔接。
4. **报告脱敏白名单/黑名单**：可进入报告的安全聚合字段精确清单；绝对禁止字段清单（答案 key、提交原文、Q&A 原文、原文全文、文件路径、可反推隐私明细）；报告快照 vs 动态与可重算校验。
5. **对外交付模型**：渠道抽象；配置与 secret 存放（不入库/不入日志/不入 backup 明文）；默认关闭开关；显式授权与收件白名单；dry-run vs 真实发送的边界；审计记录字段；重试与去重；禁止自动定时推送。
6. **真实组件与 dry-run 的 gate 划分**：真实 OCR/ASR 与真实外发各自的 opt-in 环境开关命名、默认关闭、skip 策略；哪些测试默认 skip；如何避免把 opt-in 结果扩大为通用 real-pass。
7. **数据保留**：采集原件、转写、报告快照、交付审计的保留期与清理路径；purge 时的连带降级；backup/restore 覆盖。
8. **schema 归属**：哪些是 append-only 事实（转写 operation、交付审计），哪些是可重算 projection（报告聚合）；SQLite 约束与 domain transaction 的分工。

---

## 7. 9D-0 验收自检

- 立项结论：**部分立项**，有五条件评审依据（第 2 节）。
- 审计可复核：所有结论引用源码路径/函数/测试名（第 1 节）。
- S6/S7 边界无重叠：S7 采集/转写/接入 vs S6 只读聚合/交付，职责分离（第 3–4 节）。
- 隐私与交付风险明确：S6 外发标为最高风险并强约束默认关闭（第 2、4、6 节）。
- 阻塞项清晰：真实 OCR/ASR 与真实外发暂缓，须独立评审（第 2 节）；未决问题移交 9D-1（第 6 节）。
- 状态：`planned/audit-draft`。本任务停在审计与范围冻结，不进入实现。
