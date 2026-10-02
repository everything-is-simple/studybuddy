# StudyBuddy 文档索引（按角色分类）

> **文档命名规则**：每个文档的文件名都标注了"××角色看"，让团队成员快速找到自己需要的文档。

<!-- STUDYBUDDY-UNIFIED-EXECUTION-PROTOCOL -->
## 统一执行协议（2026-09-27）

本文件与 `H:\studybuddy\docs\[所有角色看]AI_AGENT_TASK_DIALOGUE_TEMPLATES.md` v2.1 使用同一套执行口径。本文档中早于 2026-09-27 的报告、表格和历史标签保留其原始事实；历史标签只能在原日期、原范围和原证据路径下解释，不能升级为当前全局结论。

### 可执行 Prompt 的必填字段
- **角色**：本次执行者的职责。
- **唯一目标**：一个可判定的结果，不把多个目标合并成“全部处理”。
- **当前阶段**：只能填写 `P0`（边界确认）、`P1`（真实状态读取）、`P2`（真实操作执行）、`P3`（证据核对）、`P4`（交付与结论）之一，并按顺序推进。
- **允许读取/写入**：逐项列出绝对路径、URL、端点、数据根和输入；未列出的对象禁止访问或修改。
- **指定工具/命令/端口/输入**：必须原样执行；对象不可用时返回 `BLOCKED`，不得替换。
- **禁止操作、停止条件和证据路径**：逐项写明；每个结论必须有实际命令/动作、结果和绝对证据路径。

### 统一状态与范围
`PASS`、`FAIL`、`BLOCKED`、`LIMITED`、`NOT_APPLICABLE`、`NOT_VERIFIED` 是本项目当前统一结果状态。`implemented`、`configured`、`available`、测试通过、隔离环境通过只能描述实现或可见性，不能单独写成 `real-pass`。`real-pass` 只能表示本次指定真实目标、真实路径、真实输入和真实动作均有证据；未覆盖范围必须写 `NOT_VERIFIED`。

### 统一路径和运行基线
源码 `H:\studybuddy`；正式数据 `H:\studybuddy-data`；验证证据 `H:\studybuddy-test\verification`；隔离数据 `H:\studybuddy-test\data_root`；真实教材 `H:\studybuddy-ChinaTextbook`（只读）；组件测试 `H:\studybuddy-composer`；组合测试 `H:\studybuddy-integration`；日志 `H:\studybuddy-log`；临时目录 `H:\studybuddy-tmp`；正式地址 `http://127.0.0.1:8787`；首页 `http://127.0.0.1:8787/app/buddy.html`。

正式启动命令为：`powershell -ExecutionPolicy Bypass -NoProfile -File H:\studybuddy\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-data -Port 8787`。隔离验证命令为：`powershell -ExecutionPolicy Bypass -NoProfile -File H:\studybuddy\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-test\data_root -Port 8787`。不得把 `python -m backend.app serve`、其他端口、其他数据根或其他浏览器替换到已指定任务中。

### 强制禁止
不得凭推测输出；不得用 HTML 解析、按钮清单、curl/API 请求、静态检查或 headless 结果冒充可视浏览器点击；不得读取、复制、提交或展示密钥、Token、Cookie、真实教材正文、Provider 原始响应、SQL 或完整 traceback；不得在未授权时调用真实 Provider/OCR/ASR、发送 Email/飞书或扩大文件范围。工具、路径、页面、服务状态或证据不满足前置条件时，立即停止并报告 `BLOCKED`。

<!-- /STUDYBUDDY-UNIFIED-EXECUTION-PROTOCOL -->

---

## 🗂️ 系统工作目录地图（2026-09-19 固化）

| 目录 | 用途 | 关键约束 |
|------|------|----------|
| `H:\studybuddy` | 正式源码仓库：生产代码（`backend/app/`）、正式测试（`backend/tests/`）、必要文档 | 根目录只留入口文档与项目元数据；不存运行数据 |
| `H:\studybuddy-data` | 正式运行数据根（data_root）：SQLite、hash-derived 原文件、配置、日志 | 唯一活跃 data_root 是其**根目录**；`live/` 为已废弃历史根（禁止指向）；不进 Git/网盘；多实例禁止共用 |
| `H:\studybuddy-composer` | 组件独立测试目录 | 组件必须先在此完成独立测试，才能进入 Integration |
| `H:\studybuddy-integration` | 组件组合测试目录 | 通过 Composer 的组件在此完成组合契约验证 |
| `H:\studybuddy-test` | 测试 artifacts/fixtures：合成 fixture、测试运行结果、脱敏 artifact、备份 | 正式测试的数据来源；不写入正式仓库 |
| `H:\studybuddy-ChinaTextbook` | 真实教材与学习资料目录（`小学教材\<年级>\<科目>\`、`基础性作业\`、下载脚本、`教材清单.md`） | 真实素材源，导入正式系统后的原件由 data_root 保存；`智慧教育token.txt` 为密钥，永不清扫 |

> 详细规则见 [`AGENTS.md`](../AGENTS.md) "Directory usage规范" 章节与 [`README.md`](../README.md) 同名章节；各目录"必须保留 / 可清理"边界与清扫操作的**权威文档**为 [`[架构师+运维看]WORKSPACE_DIRECTORIES.md`]([架构师+运维看]WORKSPACE_DIRECTORIES.md)。
>
> ⚠️ **两点易错**：① 活跃 data_root 是 `H:\studybuddy-data` 的**根目录**，其下 `live/` 是已废弃历史根，禁止把 `STUDYBUDDY_DATA_ROOT` 指向它；② `H:\studybuddy-e2e-test*` 属一次性临时 data_root，不是正式目录，可整目录删除。

---

## 📋 所有角色必读

| 文档 | 说明 | 维护者 |
|------|------|--------|
| [`[需求+所有角色看]STATUS.md`]([需求+所有角色看]STATUS.md) | **实现状态与证据索引的权威来源**，所有角色每周必读 | 需求分析师 |
| [`../README.md`](../README.md) | 项目定位、运行入口与当前能力摘要 | 需求分析师 |
| [`../AGENTS.md`](../AGENTS.md) | 贡献和 coding-agent 约束 | 架构师 |
| [`[维护者看]DEVELOPMENT_ENVIRONMENT_BASELINE.md`]([维护者看]DEVELOPMENT_ENVIRONMENT_BASELINE.md) | **当前开发工具、Python 依赖和 StudyBuddy 功能组件基线** | 维护者/运维 |
| [`[维护者看]NEW_MACHINE_SETUP.md`]([维护者看]NEW_MACHINE_SETUP.md) | **新机器目录、组件证据和重建顺序** | 维护者/运维 |
| [`[维护者看]STUDYBUDDY_NEW_MACHINE_PROMPT.md`]([维护者看]STUDYBUDDY_NEW_MACHINE_PROMPT.md) | **可直接交给 AI 的新机器配置提示词** | 维护者/运维 |
| [`[维护者看]STUDYBUDDY_USER_MANUAL_VERIFICATION_PROMPT.md`]([维护者看]STUDYBUDDY_USER_MANUAL_VERIFICATION_PROMPT.md) | **两份用户手册与当前系统的严格发布门禁校验 Prompt** | 维护者/测试 |

---

## 👤 按角色分类

### 1️⃣ 需求分析师（Demand Analyst）

**职责**：定义用户场景、验收标准、优先级、可用性边界

| 文档 | 说明 | 是否可写 |
|------|------|---------|
| [`[需求看]TODO.md`]([需求看]TODO.md) | **唯一可勾选的执行清单** | ✅ 可写 |
| [`[需求+所有角色看]STATUS.md`]([需求+所有角色看]STATUS.md) | 实现状态与测试基线（所有角色共同维护） | ✅ 可写测试基线 |
| [`[需求+架构看]ROADMAP_CAPABILITIES.md`]([需求+架构看]ROADMAP_CAPABILITIES.md) | 已批准的后续能力路线图 | ✅ 可写优先级 |
| [`[需求+测试看]P1_7_REAL_USE_CHECKLIST.md`]([需求+测试看]P1_7_REAL_USE_CHECKLIST.md) | P1-7 真实使用观察清单 | ✅ 可写 |
| [`[架构+需求看]DECISIONS.md`]([架构+需求看]DECISIONS.md) | 重大决策记录 | ✅ 参与决策 |

**禁止修改**：`backend/app/` 代码、test 文件、schema 定义

---

### 2️⃣ 系统架构师（Architect）

**职责**：定义模块边界、数据模型、持久化契约、错误码、生命周期

| 文档 | 说明 | 是否可写 |
|------|------|---------|
| [`[架构师看]ARCHITECTURE.md`]([架构师看]ARCHITECTURE.md) | **正式系统架构、支持边界与核心不变量** | ✅ 可写 |
| [`[架构师看]AI_LEARNING_ARCHITECTURE.md`]([架构师看]AI_LEARNING_ARCHITECTURE.md) | AI/学习功能架构和实施边界 | ✅ 可写 |
| [`[架构师+测试看]CODE_TEST_GOVERNANCE.md`]([架构师+测试看]CODE_TEST_GOVERNANCE.md) | 代码边界、测试层级、证据等级和提交门禁 | ✅ 可写 |
| [`[架构师+运维看]MIGRATIONS.md`]([架构师+运维看]MIGRATIONS.md) | schema version、migration runner 与升级规则 | ✅ 可写 |
| [`[架构+需求看]DECISIONS.md`]([架构+需求看]DECISIONS.md) | 重大决策记录 | ✅ 可写 |

**选读**：`.archive/contracts/` 下的契约文档（参考实现边界）

**禁止修改**：`[需求看]TODO.md` 的优先级、test 文件

---

### 3️⃣ UI/UX 设计师（UI/UX Designer）

**职责**：定义页面结构、交互流程、状态标签、失败/重试体验、隐私边界

| 文档 | 说明 | 是否可写 |
|------|------|---------|
| [`[UI设计+用户看]LOCAL_V1_USER_GUIDE.md`]([UI设计+用户看]LOCAL_V1_USER_GUIDE.md) | **本地 v1 用户指南** | ✅ 可写 |
| [`[用户看]StudyBuddy使用手册.html`]([用户看]StudyBuddy使用手册.html) | **人工使用手册（图示版）**：每页一段落 + 操作示意图，面向最终使用者 | ✅ 可写 |
| [`frontend-contract-fixtures.json`](frontend-contract-fixtures.json) | 前端契约测试 fixtures | ✅ 可写 |
| [`[需求+所有角色看]STATUS.md`]([需求+所有角色看]STATUS.md) | 查看当前功能状态（只读） | ❌ 只读 |

**选读**：`.archive/frontend/` 下的前端盘点和契约审计

**禁止修改**：`backend/app/` 代码、API 定义、schema

---

### 4️⃣ 后端开发者（Backend Developer）

**职责**：实现 API、repository、provider adapter、持久化逻辑

| 文档 | 说明 | 是否可写 |
|------|------|---------|
| [`[架构师看]ARCHITECTURE.md`]([架构师看]ARCHITECTURE.md) | 系统架构（只读，理解边界） | ❌ 只读 |
| [`[架构师+测试看]CODE_TEST_GOVERNANCE.md`]([架构师+测试看]CODE_TEST_GOVERNANCE.md) | 测试层级和门禁（只读） | ❌ 只读 |
| [`[需求看]TODO.md`]([需求看]TODO.md) | 执行清单（只执行不改） | ❌ 只读 |

**必读**：`.archive/contracts/` 下的契约文档（实现依据）

**选读**：`.archive/evidence/` 下的证据文档（理解验收边界）

**禁止修改**：`[需求看]TODO.md` 的优先级、UI 代码、test 文件

---

### 5️⃣ 测试工程师（QA Engineer）

**职责**：编写/运行 backend、browser、governance 测试，验证契约

| 文档 | 说明 | 是否可写 |
|------|------|---------|
| [`[架构师+测试看]CODE_TEST_GOVERNANCE.md`]([架构师+测试看]CODE_TEST_GOVERNANCE.md) | **测试层级、证据等级和门禁** | ✅ 可写测试策略 |
| [`[需求+测试看]P1_7_REAL_USE_CHECKLIST.md`]([需求+测试看]P1_7_REAL_USE_CHECKLIST.md) | 真实使用观察清单 | ✅ 可写验收结果 |
| [`[需求+所有角色看]STATUS.md`]([需求+所有角色看]STATUS.md) | 更新测试基线 | ✅ 可写测试基线 |

**必读**：所有 `backend/tests/test_*.py` 和 `backend/tests/browser_*.js`

**选读**：`.archive/evidence/` 下的证据文档（理解验收标准）

**禁止修改**：产品代码、`[需求看]TODO.md` 的优先级

---

### 6️⃣ 运维/部署工程师（DevOps/Operator）

**职责**：备份/恢复、升级、Provider 配置、环境映射、操作手册

| 文档 | 说明 | 是否可写 |
|------|------|---------|
| [`[运维看]BACKUP_RESTORE.md`]([运维看]BACKUP_RESTORE.md) | **backup / verify / restore 行为边界** | ✅ 可写 |
| [`[架构师+运维看]MIGRATIONS.md`]([架构师+运维看]MIGRATIONS.md) | schema 升级规则（只读升级流程） | ❌ 只读 |
| [`[需求+所有角色看]STATUS.md`]([需求+所有角色看]STATUS.md) | 查看当前功能状态和 limits | ❌ 只读 |

**必读**：`.archive/operations/` 下的操作手册（`AI_PROVIDER_SETUP.md`、`BACKUP_OPERATIONS.md`、`OPERATOR_UPGRADE.md` 等）

**禁止修改**：schema、API、UI、test 文件

---

## 🔧 维护者专用

| 文档 | 说明 | 维护者 |
|------|------|--------|
| [`[维护者看]CLEAN_SYSTEM_PROMPT.md`]([维护者看]CLEAN_SYSTEM_PROMPT.md) | 系统清洁工作指南 | 架构师 + 需求分析师 |
| [`[维护者看]CODE_DOCUMENTATION_PROJECT.md`]([维护者看]CODE_DOCUMENTATION_PROJECT.md) | 代码注释补齐工程总结 | 架构师 |
| [`[维护者看]PI_WORKFLOW.md`]([维护者看]PI_WORKFLOW.md) | Pi 会话、模型默认值和上下文管理工作流 | 维护者 |
| [`[维护者看]PI_DESKTOP_DEVELOPMENT.md`]([维护者看]PI_DESKTOP_DEVELOPMENT.md) | Pi / pi-desktop 正式开发环境和启动入口 | 维护者 |
| [`roles/SIX_ROLES_SYNERGY_LESSONS.md`](roles/SIX_ROLES_SYNERGY_LESSONS.md) | **六角色协同开发系统的经验教训之谈** | 需求分析师 + 架构师 |

---

## 📦 归档文档（历史参考）

所有已完成 Phase 的总结性文档、契约文档、证据文档、操作手册均已归档到：

- **`.archive/contracts/`** - 契约文档（24 个）
- **`.archive/evidence/`** - 证据文档（40+ 个）
- **`.archive/operations/`** - 操作手册（5 个）
- **`.archive/code-documentation-project/`** - 代码注释工程历史文档
- **`.archive/progress-snapshots/`** - 项目进度快照
- **`.archive/historical-roadmaps/`** - 历史阶段路线图
- **`.archive/frontend/`** - 前端盘点与审计历史文档

**归档说明**：归档文档仅供追溯参考，不作为当前事实源。完整归档索引见 [`.archive/README.md`](../.archive/README.md)。

---

## 📏 文档维护规则

### 1. 文档鲜活规则
- **STATUS.md** 每周日更新测试基线
- **TODO.md** 每次完成切片后更新
- **INDEX.md** 新增/移动 Markdown 后运行链接检查
- **已完成 Phase 总结** 7 天内归档到 `.archive/`

### 2. 变更触发链
```
需求改 → 需求分析师更新 TODO/STATUS → 架构师评审 → UI 设计师评审
→ 开发者实现 → 测试工程师跑 governance + regression
→ 运维工程师更新 operations/ 手册
```

### 3. 谁改谁测
- 需求改 → 需求分析师跑 TODO/STATUS 一致性检查
- 架构改 → 架构师跑 CODE_TEST_GOVERNANCE 门禁
- UI 改 → UI 设计师跑 `browser_frontend_page_contract.spec.js`
- 后端改 → 开发者跑 focused backend test + governance
- 测试改 → 测试工程师跑全量 regression
- 运维改 → 运维跑 operations/ 手册验证

---

## 🔍 快速查找

**我是新加入的成员，应该先看什么？**

| 角色 | 第一篇必读 | 第二篇必读 | 第三篇必读 |
|------|-----------|-----------|-----------|
| 需求分析师 | [`README.md`](../README.md) | [`[需求+所有角色看]STATUS.md`]([需求+所有角色看]STATUS.md) | [`[需求看]TODO.md`]([需求看]TODO.md) |
| 架构师 | [`[架构师看]ARCHITECTURE.md`]([架构师看]ARCHITECTURE.md) | [`[架构师+测试看]CODE_TEST_GOVERNANCE.md`]([架构师+测试看]CODE_TEST_GOVERNANCE.md) | [`[架构+需求看]DECISIONS.md`]([架构+需求看]DECISIONS.md) |
| UI/UX 设计师 | [`[UI设计+用户看]LOCAL_V1_USER_GUIDE.md`]([UI设计+用户看]LOCAL_V1_USER_GUIDE.md) | [`[需求+所有角色看]STATUS.md`]([需求+所有角色看]STATUS.md) | `frontend-contract-fixtures.json` |
| 后端开发者 | [`[架构师看]ARCHITECTURE.md`]([架构师看]ARCHITECTURE.md) | [`[需求看]TODO.md`]([需求看]TODO.md) | `.archive/contracts/` |
| 测试工程师 | [`[架构师+测试看]CODE_TEST_GOVERNANCE.md`]([架构师+测试看]CODE_TEST_GOVERNANCE.md) | `backend/tests/` | [`[需求+测试看]P1_7_REAL_USE_CHECKLIST.md`]([需求+测试看]P1_7_REAL_USE_CHECKLIST.md) |
| 运维工程师 | [`[运维看]BACKUP_RESTORE.md`]([运维看]BACKUP_RESTORE.md) | `.archive/operations/` | [`[需求+所有角色看]STATUS.md`]([需求+所有角色看]STATUS.md) |

---

**维护者**：架构师 + 需求分析师  
**更新频率**：每次新增/移动文档后立即更新  
**版本**：v2（2026-09-07，按角色重新分类）
