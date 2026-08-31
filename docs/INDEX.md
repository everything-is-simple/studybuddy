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
- [`frontend-plan.md`](frontend-plan.md)：保留的前端实现契约与范围。

## 分类资料

- [`contracts/`](contracts/)：持久领域、API、Provider、媒体和前端工作流契约；实现应以对应契约为准。
- [`evidence/`](evidence/)：正式验收与 scoped gate 证据，不把未验证范围写成 `real-pass`。
- [`operations/`](operations/)：Provider、备份、恢复、升级和本地环境的操作手册。
- [`archive/`](archive/)：保留的历史审计、阶段范围和重构记录；它们只提供历史背景，不是当前事实源。

### 常用分类入口

- [`contracts/MEDIA_CAPABILITY_DECISION.md`](contracts/MEDIA_CAPABILITY_DECISION.md)：ASR、OCR、TTS 与 PPTX 候选及 Formal 边界。
- [`evidence/PHASE9D_ACCEPTANCE_EVIDENCE.md`](evidence/PHASE9D_ACCEPTANCE_EVIDENCE.md)：Phase 9D 限定范围 closeout。
- [`evidence/PHASE10_RELEASE_CANDIDATE_EVIDENCE.md`](evidence/PHASE10_RELEASE_CANDIDATE_EVIDENCE.md)：local-v1 release candidate drill。
- [`operations/AI_PROVIDER_SETUP.md`](operations/AI_PROVIDER_SETUP.md)：真实 Provider 的显式 opt-in 配置边界。
- [`archive/A2_X_SERIES_SUMMARY.md`](archive/A2_X_SERIES_SUMMARY.md)：A2.X 模块化拆分历史总结。

## 文档维护规则

- 根目录只保留 `README.md`、`AGENTS.md` 与项目元数据；活跃事实源位于 `docs/` 根目录。
- `STATUS.md`、`TODO.md`、`PHASE_ROADMAP.md` 与 `ROADMAP_CAPABILITIES.md` 分别负责状态、执行清单、阶段顺序与已批准路线；发生冲突时先修正这些事实源。
- 非核心资料必须按用途放入 `contracts/`、`evidence/`、`operations/` 或 `archive/`，不要恢复已移除的规划 prompt 目录或复制第二份状态摘要。
- 新增或移动 Markdown 后，运行治理测试中的链接检查；历史归档中的已移除资料应改为文字 provenance，而不是保留失效链接。
