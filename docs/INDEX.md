# StudyBuddy 文档索引

## 核心入口

- [`../README.md`](../README.md)：项目定位、运行入口与当前能力摘要。
- [`../AGENTS.md`](../AGENTS.md)：贡献和 coding-agent 约束。
- [`ARCHITECTURE.md`](ARCHITECTURE.md)：正式系统架构、支持边界与核心不变量。
- [`CODE_TEST_GOVERNANCE.md`](CODE_TEST_GOVERNANCE.md)：代码边界、测试层级、证据等级和提交门禁。
- [`STATUS.md`](STATUS.md)：实现状态与证据索引的权威来源。
- [`TODO.md`](TODO.md)：唯一可勾选的执行清单。
- [`PHASE_ROADMAP.md`](PHASE_ROADMAP.md)：已完成 Phase 与长期阶段、依赖和完成标准。
- [`ROADMAP_CAPABILITIES.md`](ROADMAP_CAPABILITIES.md)：已批准的后续能力路线图。

## 设计、使用与维护

- [`ai-learning-architecture.md`](ai-learning-architecture.md)：AI/学习功能架构和实施边界。
- [`MIGRATIONS.md`](MIGRATIONS.md)：schema version、migration runner 与升级规则。
- [`BACKUP_RESTORE.md`](BACKUP_RESTORE.md)：backup / verify / restore 行为边界。
- [`LOCAL_V1_USER_GUIDE.md`](LOCAL_V1_USER_GUIDE.md)：本地 v1 首次配置、启动、验收和日常使用。
- [`frontend-plan.md`](frontend-plan.md)：保留的前端实现契约与范围（**目标设计**，不是当前实现快照）。
- [`frontend-inventory-report.md`](frontend-inventory-report.md)：前端**事实盘点**（21 页面、共享层、测试与后端路由覆盖的当前事实与结论。
- [`frontend-inventory-scan.md`](frontend-inventory-scan.md)：由 `backend/scripts/scan-frontend-inventory.py` 生成的逐页/逐端点可复算明细。

## 分类资料

- [`contracts/`](contracts/)：持久领域、API、Provider、媒体和前端工作流契约；实现应以对应契约为准。
- [`evidence/`](evidence/)：正式验收与 scoped gate 证据，不把未验证范围写成 `real-pass`。
- [`operations/`](operations/)：Provider、备份、恢复、升级和本地环境的操作手册。
- [`archive/`](archive/)：保留的历史审计、阶段范围和重构记录；它们只提供历史背景，不是当前事实源。

### 常用分类入口

- [`contracts/MEDIA_CAPABILITY_DECISION.md`](contracts/MEDIA_CAPABILITY_DECISION.md)：ASR、OCR、TTS 与 PPTX 候选及 Formal 边界。
- [`contracts/P1_5_PROVIDER_EMAIL_CONFIGURATION_CONTRACT.md`](contracts/P1_5_PROVIDER_EMAIL_CONFIGURATION_CONTRACT.md)：Provider（AI LLM/Embedding）和 Email（SMTP/Feishu）配置安全契约，secret 生命周期、runtime-only source、connection-test 触发机制和 backup/restore 边界。
- [`contracts/P1_5_3_CONFIGURATION_PERSISTENCE_EVALUATION.md`](contracts/P1_5_3_CONFIGURATION_PERSISTENCE_EVALUATION.md)：配置持久化五方案评估与“不引入持久化”决策，并定型 P1-5-1 配置 UI 为“组装 → 校验 → 导出”。
- [`../backend/app/static/settings-provider.html`](../backend/app/static/settings-provider.html)：Provider/Email 配置 UI，先测后存（P2-USE-3 起支持保存并立即生效）。
- [`evidence/P1_5_0_CONTRACT_EVIDENCE.md`](evidence/P1_5_0_CONTRACT_EVIDENCE.md)：P1-5-0 契约冻结审计发现和治理测试覆盖。
- [`evidence/P1_5_2_CONNECTION_TEST_EVIDENCE.md`](evidence/P1_5_2_CONNECTION_TEST_EVIDENCE.md)：P1-5-2 connection-test 实现证据，包含 adapter、API、测试覆盖和未验证边界。
- [`evidence/P1_5_4_BROWSER_SECURITY_EVIDENCE.md`](evidence/P1_5_4_BROWSER_SECURITY_EVIDENCE.md)：P1-5-4 浏览器配置安全证据，覆盖 secret 生命周期、DOM/URL/storage 和 mock connection-test。
- [`evidence/P1_5_5_SECRET_LEAK_SCAN_EVIDENCE.md`](evidence/P1_5_5_SECRET_LEAK_SCAN_EVIDENCE.md)：P1-5-5 synthetic secret 扫描证据、范围与未验证边界。
- [`contracts/P1_6_VERIFICATION_SCOPE_CONTRACT.md`](contracts/P1_6_VERIFICATION_SCOPE_CONTRACT.md)：P1-6-0 B1-B4 扩大验证范围、门禁与后续切片契约。
- [`evidence/P1_6_0_AUDIT_EVIDENCE.md`](evidence/P1_6_0_AUDIT_EVIDENCE.md)：P1-6-0 B1-B4 缺口审计、立项顺序与未验证边界。
- [`evidence/P1_6_1_ASR_INPUT_CANCELLATION_EVIDENCE.md`](evidence/P1_6_1_ASR_INPUT_CANCELLATION_EVIDENCE.md)：P1-6-1 B1 ASR 输入拒绝、timeout/受控中断与清理证据。
- [`evidence/P1_6_2_OCR_INPUT_RECOVERY_EVIDENCE.md`](evidence/P1_6_2_OCR_INPUT_RECOVERY_EVIDENCE.md)：P1-6-2 B2 OCR 图片输入、边界拒绝与 timeout 清理证据。
- [`evidence/P1_6_3_0_COMPONENT_AUDIT_EVIDENCE.md`](evidence/P1_6_3_0_COMPONENT_AUDIT_EVIDENCE.md)：P1-6-3-0 真实 PaddleOCR/RapidOCR 组件、C2 门禁与 Formal 边界审计证据。
- [`evidence/P1_6_3_1_OCR_INTEGRATION_EVIDENCE.md`](evidence/P1_6_3_1_OCR_INTEGRATION_EVIDENCE.md)：RapidOCR 真实格式 smoke 重跑结果与严格 C2 `integration-not-passed` 判定。
- [`evidence/PHASE9D_ACCEPTANCE_EVIDENCE.md`](evidence/PHASE9D_ACCEPTANCE_EVIDENCE.md)：Phase 9D 限定范围 closeout。
- [`evidence/PHASE10_RELEASE_CANDIDATE_EVIDENCE.md`](evidence/PHASE10_RELEASE_CANDIDATE_EVIDENCE.md)：local-v1 release candidate drill。
- [`operations/AI_PROVIDER_SETUP.md`](operations/AI_PROVIDER_SETUP.md)：真实 Provider 的显式 opt-in 配置边界。
- [`archive/A2_X_SERIES_SUMMARY.md`](archive/A2_X_SERIES_SUMMARY.md)：A2.X 模块化拆分历史总结。

## 文档维护规则

- 根目录只保留 `README.md`、`AGENTS.md` 与项目元数据；活跃事实源位于 `docs/` 根目录。
- `STATUS.md`、`TODO.md`、`PHASE_ROADMAP.md` 与 `ROADMAP_CAPABILITIES.md` 分别负责当前状态、唯一执行清单、阶段顺序与已批准路线；当前状态冲突时以 `STATUS.md` 为准，执行项冲突时以 `TODO.md` 为准。历史证据只保留原始快照，不能覆盖当前状态。完整规则见 `CODE_TEST_GOVERNANCE.md`。
- 非核心资料必须按用途放入 `contracts/`、`evidence/`、`operations/` 或 `archive/`，不要恢复已移除的规划 prompt 目录或复制第二份状态摘要。
- 新增或移动 Markdown 后，运行治理测试中的链接检查；历史归档中的已移除资料应改为文字 provenance，而不是保留失效链接。
