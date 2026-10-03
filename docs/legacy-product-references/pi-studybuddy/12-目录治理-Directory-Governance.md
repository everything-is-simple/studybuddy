# 12 目录治理

**版本**：v0.1.4
**日期**：2026-08-15
**状态**：✅ 已审查批准；T-M5-011 执行中
**上游**：[AGENTS.md §9.5](../AGENTS.md)、[01-TRD §7 决策 3](./01-TRD-技术需求-Technical-Requirements.md)、[04-Todo §4](./04-任务清单-Todo-List.md)、[11-组件装配 §3](./11-组件装配-Component-Assembly.md)
**用途**：pi-studybuddy 所有目录的职责定义与边界隔离——每个目录有唯一职责，不越界

---

## T-M5-011 当前运行资产口径

当前开发机是第一交付基线：运行资源、默认配置、数据根和启动方式先在开发机固定并验证；使用机只复制已验证拓扑，不另行设计第二套运行方式。真实数据仍不得进入 Git，测试数据仍写隔离运行根。

## 1. 概述

### 1.1 目录治理原则

> **源码不存真实数据，试炼场不变成主系统，运行数据不进入 Git，备份不反向污染当前 SoT。**

每个目录有**唯一职责**，目录之间物理隔离，不交叉存放。

### 1.2 治理目标

1. **职责清晰**：每个目录只做一件事
2. **边界隔离**：源码 / 试炼场 / 运行数据 / 备份互不污染
3. **Git 干净**：运行数据、临时文件、密钥不进 Git
4. **可审计**：每个目录的内容可追溯

### 1.3 与其他文档的关系

```
AGENTS.md §9.5（数据隔离：~/.pi 与业务数据根物理隔离）
    ↓ 细化为目录
docs/12-目录治理（本文件）
    ↓ 指导使用
docs/04-Todo §4（组件治理看板）+ docs/11-组件装配 §3（试炼场）
```

---

## 2. 目录总览

### 2.1 目录地图

```
H:\pi-studybuddy\                    ← 主仓库（Git 仓库）
├── AGENTS.md                        ← 仓库操作宪章
├── README.md                        ← 项目总览
├── .gitignore
├── docs/                            ← 设计文档 + 治理文档
├── .pi/                             ← pi 生态治理资产（skills / prompts）
├── scripts/                         ← 自动化门禁脚本
├── .plan/                           ← 任务计划（唯一执行中）
├── .record/                         ← 实施记录（每任务一份）
└── src/                             ← 源码（M0 启动后创建）

H:\pi-studybuddy-composer\           ← 试炼场（组件独立调通）
├── <component>/                     ← 每个组件一个目录
│   ├── COMPONENT-CARD.md
│   ├── smoke-test.mjs / .py
│   └── fixtures/
└── README.md

H:\pi-studybuddy-tmp\                ← 临时/验证空间（可再生）
└── runs\<task-id>\                  ← 测试运行数据隔离

%LOCALAPPDATA%\PiStudyBuddy\         ← 业务数据根（运行时）
├── global.db                        ← 全局库（学期注册表）
├── semester\<id>\sem.db            ← 每学期独立库
├── storage\                         ← 资料文件存储
├── reports\                         ← 家长报告
└── logs\                            ← 脱敏日志

~/.pi\agent\                         ← pi 会话目录（pi 自管，不侵入）
├── auth.json
├── models.json
├── settings.json
└── sessions\

H:\pi-references\                    ← 参考仓库（只读，不修改）
├── pi\
├── inno-agent\
├── pi-desktop\
└── pi-skills\

H:\pi-studybuddy-backup\             ← 只读阶段备份（可选）
```

### 2.2 目录职责速查

| 目录 | 唯一职责 | 是否进 Git | 是否存真实数据 |
|---|---|---|---|
| `H:\pi-studybuddy\` | 主系统 Git 仓库（源码 + 文档 + 测试 + 计划） | ✅ 是 | ❌ 否 |
| `H:\pi-studybuddy-composer\` | 外部组件/能力试炼场 | ❌ 独立 | ❌ 否 |
| `H:\pi-studybuddy-tmp\` | 可再生临时/验证空间 | ❌ 否 | ❌ 否（测试数据） |
| `%LOCALAPPDATA%\PiStudyBuddy\` | 业务数据根（运行时） | ❌ 否 | ✅ 是 |
| `~/.pi\agent\` | pi 会话目录（pi 自管） | ❌ 否 | ✅ 是（pi 会话） |
| `H:\pi-references\` | 参考仓库（只读） | ❌ 否 | ❌ 否 |
| `H:\pi-studybuddy-backup\` | 只读阶段备份（可选） | ❌ 否 | ✅ 是（备份） |

---

## 3. 主仓库目录（H:\pi-studybuddy\）

### 3.1 主仓库职责

主仓库是 pi-studybuddy 的 **Git 仓库**，存放：
- 源码（`src/`）
- 文档（`docs/`）
- 测试（`tests/` 或 `src/**/*.test.mjs`）
- 治理资产（`AGENTS.md` / `README.md` / `.pi/` / `scripts/`）
- 任务计划与记录（`.plan/` / `.record/`）

### 3.2 主仓库规则

1. **不存真实数据**：源码不存学生资料原文 / 完整 UUID / 真实密钥
2. **不存运行数据**：`%LOCALAPPDATA%\PiStudyBuddy\` 的运行数据不进 Git
3. **不存试炼场代码**：试炼场代码不 `import`，不复制副本
4. **不存 node_modules / venv**：`.gitignore` 排除
5. **不存临时文件**：临时文件写 `H:\pi-studybuddy-tmp\`

### 3.3 主仓库子目录

| 子目录 | 职责 | 创建时机 |
|---|---|---|
| `docs/` | 设计文档（00-12）+ 治理文档 | ✅ 已创建 |
| `.pi/skills/` | 治理用 Skill（task-complete / component-assembly） | 📝 待创建 |
| `.pi/prompts/` | 工作流模板（wr / plan）+ `task-execution/` 任务启动提示词资产；后者只统一范围、过程与验收主题，不得替代唯一 `.plan/` | ✅ 已创建 |
| `scripts/` | 自动化门禁（verify / check-docs / check-contract） | 📝 待创建 |
| `.plan/` | 任务计划（唯一执行中） | 📝 待创建 |
| `.record/` | 实施记录（每任务一份） | 📝 待创建 |
| `src/` | 源码（contract / main / preload / agent-host / renderer / shared） | M0 启动 |
| `tests/` | 测试（或就近 `.test.mjs`） | M0 启动 |

### 3.4 .gitignore 规则

```gitignore
# 依赖
node_modules/
venv/
.pnpm-store/

# 构建产物
dist/
build/
*.tsbuildinfo

# 环境与密钥
.env
.env.local
.env.*.local
credentials.json
*.key

# 运行数据（绝不进 Git）
# %LOCALAPPDATA%\PiStudyBuddy\ 不在仓库内，但防止误配置
data/
logs/
*.db
*.db-journal

# 临时文件
tmp/
*.tmp
*.log

# 试炼场（独立目录，不在仓库内）
# H:\pi-studybuddy-composer\ 不在仓库内

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
Thumbs.db
.DS_Store

# Python
__pycache__/
*.pyc
*.pyo
.pytest_cache/

# 测试覆盖
coverage/
.nyc_output/
```

---

## 4. 试炼场目录（H:\pi-studybuddy-composer\）

### 4.1 试炼场职责

试炼场是组件**独立调通**的专用空间（详见 docs/11-组件装配 §3）。

### 4.2 试炼场规则

1. **独立目录**：与主仓库物理隔离（`H:\pi-studybuddy-composer\`）
2. **不进 Git**：试炼场不初始化 Git 仓库（或独立 Git，不与主仓关联）
3. **每组件一目录**：`<component-name>/` 独立
4. **不 import 主仓**：试炼场代码不依赖主仓 `src/`
5. **运行数据不进 Git**：试炼场运行产物不提交

### 4.3 试炼场创建时机

M0 启动时创建（当前阶段待创建）。

---

## 5. 临时目录（H:\pi-studybuddy-tmp\）

### 5.1 临时目录职责

临时目录是**可再生**的验证空间，存放：
- 测试运行数据（`runs/<task-id>/`）
- 构建缓存
- 验证中间产物

### 5.2 临时目录规则

1. **可再生**：可随时清空，不影响系统
2. **不进 Git**：`.gitignore` 排除（虽不在主仓内，防止误配置）
3. **测试隔离**：每个 task-id 独立子目录 `runs/<task-id>/`
4. **绝不污染真实业务数据根**：`%LOCALAPPDATA%\PiStudyBuddy\` 是真实数据，临时目录是测试数据

### 5.3 测试运行数据隔离（08-Test §1.3 第 5 条）

```
H:\pi-studybuddy-tmp\
└── runs\
    ├── T-M0-001\           ← M0 第 001 任务测试数据
    ├── T-M1-042\           ← M1 第 042 任务测试数据
    └── ...
```

每个 task-id 的测试数据独立，不交叉污染。

---

## 6. 业务数据根（%LOCALAPPDATA%\PiStudyBuddy\）

### 6.1 业务数据根职责

业务数据根是 pi-studybuddy 运行时的**真实数据**存放地（01-TRD §7 决策 3）。

### 6.2 业务数据根结构

```
%LOCALAPPDATA%\PiStudyBuddy\
├── global.db                        ← 全局库（学期注册表 / parent_report_targets / backup_records / backup_schedules）
├── semester\
│   └── <semester-id>\
│       ├── sem.db                   ← 学期库（S1-S7 全量表）
│       └── storage\                 ← 资料文件存储
│           └── semester\<id>\storage\<relative-path>
├── reports\                         ← 家长报告（冻结快照）
├── config\
│   ├── models.json                  ← 默认模型选型（__studybuddy_managed 标记，T-M3-005）
│   └── credentials.json             ← credential-vault 的 DPAPI 加密 JSON（不提交）
├── logs\                            ← 脱敏日志
└── backups\                         ← 备份 zip（课程独立）
```

### 6.3 业务数据根规则

1. **绝不进 Git**：业务数据是运行时数据，不提交
2. **物理隔离**：与 pi 会话目录 `~/.pi` 物理隔离（01-TRD §7 决策 3）
3. **单写进程**：只有 pi-studybuddy 主进程写入（AGENTS.md §1.1 单写进程）
4. **脱敏日志**：logs 遵循 allowlist（AGENTS.md §9.3）
5. **备份隔离**：backups 是备份 zip，不与当前业务数据混淆

### 6.4 storage_key 路径防护（05-ERD §6.1）

资料文件存储路径必须：
- 相对路径（`semester/<id>/storage/<relative-path>`）
- 不含 `..`（防逃逸）
- 不含 `:\` 或 `:/`（防盘符逃逸）
- 触发器拦截非法路径

---

## 7. pi 会话目录（~/.pi\agent\）

### 7.1 pi 会话目录职责

pi 会话目录由 **pi 自管**，pi-studybuddy 不侵入（01-TRD §7 决策 3）。

### 7.2 pi 会话目录结构

```
~/.pi\agent\
├── auth.json                        ← pi 认证
├── models.json                      ← pi 模型配置（pi 自管，studybuddy 默认模型选型在业务数据根 config/models.json）
├── settings.json                    ← pi 设置
└── sessions\                        ← pi 会话（JSONL 格式）
```

### 7.3 pi 会话目录规则

1. **pi 自管**：pi-studybuddy 不修改 `~/.pi` 内文件（默认模型选型走业务数据根 `config/models.json`，不侵入 `~/.pi/agent/models.json`，03-Arch §2.3）
2. **物理隔离**：业务数据在 `%LOCALAPPDATA%\PiStudyBuddy\`，不在 `~/.pi`
3. **会话读取**：pi-desktop session-reader 读 `~/.pi/agent/sessions/`（03-Arch §6.7）
4. **不侵入**：pi-studybuddy 的扩展层 / 业务 Adapter 不写 `~/.pi`

---

## 8. 参考仓库目录（H:\pi-references\）

### 8.1 参考仓库职责

参考仓库是**只读**的参考来源，不修改（01-TRD §2 + AGENTS.md §3.2）。

### 8.2 参考仓库清单

| 仓库 | 路径 | 用途 |
|---|---|---|
| pi | `H:\pi-references\pi` | AI 底座 + AGENTS.md 范式 |
| inno-agent | `H:\pi-references\inno-agent` | 业务化范本 |
| pi-desktop | `H:\pi-references\pi-desktop` | 桌面壳架构 |
| pi-skills | `H:\pi-references\pi-skills` | 技能供给 |

### 8.3 参考仓库规则

1. **只读**：不修改参考仓库内文件
2. **不进 Git**：参考仓库不与主仓关联
3. **仅参考**：不构成权威（AGENTS.md §3.2）
4. **不 import**：主仓 `src/` 不 `import` 参考仓库内部模块
5. **可克隆更新**：`git pull` 更新参考仓库，但不修改其内容

---

## 9. 备份目录（H:\pi-studybuddy-backup\，可选）

### 9.1 备份目录职责

只读阶段备份，用于阶段交付前的安全快照（可选，按需创建）。

### 9.2 备份目录规则

1. **只读**：备份后不修改
2. **不进 Git**：备份不提交
3. **不反向污染**：备份不覆盖当前 SoT
4. **与业务数据根备份区分**：
   - `H:\pi-studybuddy-backup\`：**阶段交付**备份（源码 + 文档快照）
   - `%LOCALAPPDATA%\PiStudyBuddy\backups\`：**业务数据**备份（课程 zip，07-Workflow §5）

---

## 10. 目录边界隔离矩阵

### 10.1 写权限矩阵

| 目录 | 主进程写 | 测试写 | 试炼场写 | Git 提交 |
|---|---|---|---|---|
| `H:\pi-studybuddy\src\` | ✅ | ❌ | ❌ | ✅ |
| `H:\pi-studybuddy\docs\` | ✅ | ❌ | ❌ | ✅ |
| `H:\pi-studybuddy\.plan\` | ✅ | ❌ | ❌ | ✅（计划文件） |
| `H:\pi-studybuddy\.record\` | ✅ | ❌ | ❌ | ✅（实施记录） |
| `H:\pi-studybuddy-composer\` | ❌ | ❌ | ✅ | ❌ |
| `H:\pi-studybuddy-tmp\` | ❌ | ✅ | ✅ | ❌ |
| `%LOCALAPPDATA%\PiStudyBuddy\` | ✅ | ❌ | ❌ | ❌ |
| `~/.pi\agent\` | pi 自管 | ❌ | ❌ | ❌ |
| `H:\pi-references\` | ❌（只读） | ❌ | ❌ | ❌ |
| `H:\pi-studybuddy-backup\` | ❌（只读） | ❌ | ❌ | ❌ |

### 10.2 数据流矩阵

```
源码流向：
  H:\pi-references\（参考）  →  学习  →  H:\pi-studybuddy\src\（独立实现）
  H:\pi-studybuddy-composer\（试炼）  →  学习  →  H:\pi-studybuddy\src\（独立实现 Adapter）

测试数据流：
  H:\pi-studybuddy\tests\  →  写入  →  H:\pi-studybuddy-tmp\runs\<task-id>\

运行数据流：
  H:\pi-studybuddy\src\（主进程）  →  写入  →  %LOCALAPPDATA%\PiStudyBuddy\

pi 会话流：
  pi 底座  →  自管  →  ~/.pi\agent\sessions\

备份流：
  %LOCALAPPDATA%\PiStudyBuddy\  →  备份  →  %LOCALAPPDATA%\PiStudyBuddy\backups\（业务备份）
  H:\pi-studybuddy\  →  备份  →  H:\pi-studybuddy-backup\（阶段备份，可选）
```

---

## 11. 目录创建时机

| 目录 | 创建时机 | 状态 |
|---|---|---|
| `H:\pi-studybuddy\` | 已创建 | ✅ |
| `H:\pi-studybuddy\docs\` | 已创建 | ✅ |
| `H:\pi-studybuddy\AGENTS.md` | 已创建 | ✅ |
| `H:\pi-studybuddy\README.md` | 已创建 | ✅ |
| `H:\pi-studybuddy\.pi\` | 第三批 | 📝 待创建 |
| `H:\pi-studybuddy\scripts\` | 第四批 | 📝 待创建 |
| `H:\pi-studybuddy\.plan\` | 第五批 | 📝 待创建 |
| `H:\pi-studybuddy\.record\` | 第五批 | 📝 待创建 |
| `H:\pi-studybuddy\src\` | M0 启动 | 📝 待创建 |
| `H:\pi-studybuddy-composer\` | M0 启动 | 📝 待创建 |
| `H:\pi-studybuddy-tmp\` | M0 启动（首次测试） | 📝 待创建 |
| `%LOCALAPPDATA%\PiStudyBuddy\` | M0 启动（首次建库） | 📝 待创建 |
| `H:\pi-references\` | 已创建 | ✅ |
| `H:\pi-studybuddy-backup\` | 按需 | 📝 可选 |

---

## 12. 目录治理检查

### 12.1 检查项

目录治理检查可作为 `scripts/check-docs-governance.mjs`（待创建）的一部分，或独立检查：

1. **主仓无运行数据**：`H:\pi-studybuddy\` 内无 `.db` / `logs/` / `data/`
2. **主仓无 node_modules**：`.gitignore` 排除 `node_modules/`
3. **主仓无试炼场代码**：`src/` 不 `import` `H:\pi-studybuddy-composer\`
4. **业务数据根不进 Git**：`%LOCALAPPDATA%\PiStudyBuddy\` 不在 Git 仓库内
5. **pi 会话目录不侵入**：`~/.pi` 内文件不被 pi-studybuddy 修改（默认模型选型走业务数据根 `config/models.json`）
6. **参考仓库只读**：`H:\pi-references\` 内文件无修改

### 12.2 检查时机

- 步骤 14 文档治理检查时一并检查
- 步骤 15 diff 检查时确认无运行数据/试炼场代码误提交

---

## 13. 版本历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v0.1.3 | 2026-08-10 | `.pi/prompts/task-execution/` 目录登记为受控治理资产：保存标准执行提示词、README 与 T-M4-014~021 任务启动提示词；职责仅为统一任务范围、过程与验收主题，不能作为执行计划或绕过单一 `.plan/`、04-Todo 和用户授权。原因：用户明确要求建立剩余任务提示词并让治理系统可发现。影响：目录职责同步，不改运行数据/API/任务状态。依据：用户明确指令 + AGENTS.md §4.4、§11.1、§11.2。 |
| v0.1.2 | 2026-08-09 | 交叉审查修订：业务数据根 `config/` 补记实际的 credential-vault 文件 `credentials.json`；保持 `~/.pi` 与业务数据根物理隔离。 |
|---|---|---|
| v0.1.1 | 2026-08-08 | §6.2 业务数据根结构补 `config/models.json`（默认模型选型，`__studybuddy_managed` 标记）+ §7.2/§7.3/§12.1 models.json 标记异位修订（T-M3-005 裁决 1：默认模型选型落业务数据根 `<dataRoot>/config/models.json`，`~/.pi/agent/models.json` 归 pi 自管不标记；AGENTS.md §9.5 物理隔离，与 03-Arch v0.1.2 supersedes 同步） |
| v0.1.0 | 2026-08-07 | 初始草案：目录职责隔离 SoT。13 章：治理原则 + 目录总览（7 个目录）+ 主仓库规则 + .gitignore + 试炼场 + 临时目录 + 业务数据根 + pi 会话目录 + 参考仓库 + 备份目录 + 写权限矩阵 + 数据流矩阵 + 创建时机 + 治理检查。参考 ai-studybuddy docs/06（8 目录隔离）+ ai-malf-riskbench 目录治理.md + AGENTS.md §9.5（数据隔离）+ 01-TRD §7 决策 3（~/.pi 物理隔离）+ docs/11-组件装配 §3（试炼场） |
